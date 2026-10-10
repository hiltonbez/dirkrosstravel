import copy
import json
import re
from unittest.mock import Mock
from datetime import date, datetime, timedelta, timezone

import pytest

from website import create_app
from website.hybrid_content import setup_hybrid
from website.models import Enquiry, Package, Quote, Resort, Setting, User, db
from website.resort_research import TEXT_FIELDS, ROW_FIELDS, research_for, save_research, validate_research
from website.resort_research_data import RESEARCH
from website.seed import seed


@pytest.fixture
def app():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'research-test', 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'RATELIMIT_ENABLED': False})
    with app.app_context():
        db.create_all()
        seed()
        setup_hybrid()
        user = User(email='research@example.test')
        user.set_password('Research-test-only')
        db.session.add(user)
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def csrf(client, path):
    return re.search(r'name="csrf_token" value="([^"]+)"', client.get(path).text).group(1)


def test_resort_galleries_use_matching_admin_photos(app):
    from pathlib import Path
    from PIL import Image
    from website.resort_media import ADMIN_GALLERIES, admin_gallery, featured_photo, media_for

    with app.app_context():
        for resort in Resort.query.all():
            slug, _ = ADMIN_GALLERIES[resort.code]
            research = research_for(resort)
            library, gallery = admin_gallery(resort)
            assert library and len(gallery) == 4
            assert featured_photo(resort, research)['src'].startswith('/static/uploads/' + slug + '/')
            for photo in gallery:
                assert photo['src'].startswith('/static/uploads/' + slug + '/')
                with Image.open(Path(app.root_path).parent / photo['src'].lstrip('/')) as image:
                    assert image.width > image.height
            media = media_for(resort, research)
            assert all(photo in media for photo in gallery)


def test_seasonal_cards_have_unique_photos_not_reused_from_resort_sections(app):
    from hashlib import sha256
    from pathlib import Path
    from website.resort_media import media_for, seasonal_photos
    from website.seasonal_offers import travel_dates

    root = Path(app.root_path).parent
    with app.app_context():
        for resort in Resort.query.all():
            media = media_for(resort, research_for(resort))
            photos = seasonal_photos(resort, media, len(travel_dates(resort)))
            assert len(photos) == len(travel_dates(resort))
            sources = [photo['src'] for photo in photos]
            assert len(sources) == len(set(sources))
            assert not set(sources) & {row['src'] for row in media}
            hashes = [sha256((root / src.lstrip('/')).read_bytes()).digest() for src in sources]
            assert len(hashes) == len(set(hashes))


def test_admin_original_quote_is_historical_private_and_never_repriced(app):
    with app.app_context():
        quote = Quote(id='historical-test', owner='another-browser',
                      request={'nbrAdults': '2', 'nbrChildren': '0', 'nbrInfants': '0',
                               'departureCity': 'Johannesburg', 'dateDeparture': '2027-03-11', 'dateReturn': '2027-03-18'},
                      result={'quoteRef': 'ORIGINAL-REF', 'hotelName': 'Mauricia Beachcomber',
                              'roomOptions': [{'accomProductName': 'Standard Beachfront', 'roomStatus': 'On Request',
                                               'packages': [{'packageDesc': 'Breakfast and Dinner',
                                                             'packagePriceZARFrom': 72818, 'pricePerPersonZARFrom': 36409}]}]},
                      created=datetime(2026, 10, 1, tzinfo=timezone.utc),
                      expires=datetime(2026, 10, 1, 1, tzinfo=timezone.utc))
        enquiry = Enquiry(name='Test Client', email='client@example.test', message='Standard Beachfront please', quote_id=quote.id)
        db.session.add_all([quote, enquiry])
        db.session.commit()
        item_id = enquiry.id
    api = Mock(side_effect=AssertionError('Historical views must not call supplier'))
    app.extensions['beachcomber'].quote = api
    client = app.test_client()
    path = f'/admin/enquiries/{item_id}/quote'
    assert client.get(path).status_code == 302
    client.post('/admin/login', data={'csrf_token': csrf(client, '/admin/login'),
                                    'email': 'research@example.test', 'password': 'Research-test-only'})
    assert path in client.get('/admin/enquiries').text
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    for text in ['Historical Rate - Not A Current Offer', 'ORIGINAL-REF', 'R 72 818', 'R 36 409',
                 'Standard Beachfront', 'On Request', 'Breakfast and Dinner', '2027-03-11', '01 Oct 2026']:
        assert text in response.text
    assert 'another-browser' not in response.text
    api.assert_not_called()
    assert client.get('/admin/enquiries/999999/quote').status_code == 404


@pytest.mark.parametrize('quote_id', [None, 'missing-quote'])
def test_admin_missing_historical_quote_has_clear_fallback(app, quote_id):
    with app.app_context():
        item = Enquiry(name='Test Client', email='client@example.test', message='Please help', quote_id=quote_id)
        db.session.add(item)
        db.session.commit()
        item_id = item.id
    client = app.test_client()
    client.post('/admin/login', data={'csrf_token': csrf(client, '/admin/login'),
                                    'email': 'research@example.test', 'password': 'Research-test-only'})
    response = client.get(f'/admin/enquiries/{item_id}/quote')
    assert response.status_code == 200
    assert 'Original Quote Unavailable' in response.text


@pytest.mark.parametrize('name,slug', [('Mauricia Beachcomber', 'mauricia-beachcomber'), ('Canonnier Beachcomber', 'canonnier-beachcomber')])
def test_home_and_package_resort_links(app, name, slug):
    client = app.test_client()
    with app.app_context():
        selected = Resort.query.filter_by(slug=slug).first()
        for package in Package.query.all():
            package.featured = package.resort_id == selected.id
        db.session.commit()
    home = client.get('/').text
    card = next(row for row in re.findall(r'<article class="package-card">(.*?)</article>', home, re.S) if name in row)
    assert re.findall(r'href="([^"]+)"', card) == [f'/resorts/{slug}'] * 3
    packages = client.get('/packages').text
    card = next(row for row in re.findall(r'<article class="package-card">(.*?)</article>', packages, re.S) if name in row)
    links = re.findall(r'href="([^"]+)"', card)
    assert links[:2] == [f'/resorts/{slug}'] * 2
    assert links[2].startswith('/packages/')


@pytest.mark.parametrize('code', list(RESEARCH))
def test_every_home_resort_name_and_photo_links_to_matching_resort(app, code):
    with app.app_context():
        resort = Resort.query.filter_by(code=code).one()
        slug = resort.slug
        name = resort.name
        for package in Package.query.all():
            package.featured = package.resort_id == resort.id
        db.session.commit()
    html = app.test_client().get('/').text
    cards = [card for card in re.findall(r'<article class="package-card">(.*?)</article>', html, re.S) if name in card]
    assert cards
    for card in cards:
        links = re.findall(r'href="([^"]+)"', card)
        assert links[:2] == [f'/resorts/{slug}'] * 2


def test_all_package_card_names_and_photos_link_to_matching_resort(app):
    html = app.test_client().get('/packages').text
    cards = re.findall(r'<article class="package-card">(.*?)</article>', html, re.S)
    assert len(cards) == 8
    for card in cards:
        links = re.findall(r'href="([^"]+)"', card)
        assert links[0] == links[1] and links[0].startswith('/resorts/')
        assert links[2].startswith('/packages/')


def test_start_layout_options_preview_keeps_live_home_unchanged(app):
    client = app.test_client()
    preview = client.get('/previews/home-start-options')
    assert preview.status_code == 200
    assert preview.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert preview.headers['Cache-Control'] == 'no-store'
    assert preview.text.count('class="start-option ') == 3
    assert preview.text.count('<h3>Find My Resort</h3>') == 3
    assert preview.text.count('<h3>Compare Resorts</h3>') == 3
    assert preview.text.count('<h3>Ask Dirk</h3>') == 3
    assert 'home-start-options.css' not in client.get('/').text


def test_home_grey_preview_is_separate_and_keeps_collection_links(app):
    client = app.test_client()
    live = client.get('/')
    preview = client.get('/previews/home-grey?collection=Family')
    assert preview.status_code == 200
    assert preview.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert preview.headers['Cache-Control'] == 'no-store'
    assert 'home-grey-preview.css' in preview.text
    assert '<div class="home-grey-preview">' in preview.text
    assert 'home-grey-preview.css' not in live.text
    assert '<div class="home-grey-preview">' not in live.text
    assert 'home-layout.css' in live.text
    assert '<div class="home-layout">' in live.text
    assert 'home-layout.css' not in preview.text
    assert '/previews/home-grey?collection=Luxury' in preview.text
    assert '/?collection=Luxury' in live.text


@pytest.mark.parametrize('path', ['/', '/packages', '/contact'])
def test_flight_centre_policy_links_in_public_footer(app, path):
    html = app.test_client().get(path).text
    for slug, label in [('booking-terms-and-conditions-za', 'Flight Centre booking terms &amp; conditions'),
                        ('terms-of-use-za', 'Flight Centre website terms of use')]:
        assert f'href="https://help.flightcentre.co.za/s/article/{slug}" target="_blank" rel="noopener noreferrer">{label}</a>' in html
    assert '_ga=' not in html


@pytest.mark.parametrize('code', list(RESEARCH))
def test_every_resort_resource(app, code):
    assert validate_research(copy.deepcopy(RESEARCH[code]))
    with app.app_context():
        resort = db.session.execute(db.select(Resort).where(Resort.code == code)).scalar_one()
        slug = resort.slug
    client = app.test_client()
    response = client.get('/resorts/' + slug)
    assert response.status_code == 200
    html = response.text
    assert html.count('<h1>') == 1
    assert html.count('id="packages"') == 1
    assert html.index('id="packages"') < html.index('id="facts"')
    assert html.index('id="packages"') < html.index('id="photos"')
    assert html.index('id="rooms"') < html.index('id="photos"')
    assert html.count('id="rooms"') == 1 and html.count('id="quote"') == 1
    assert html.index('id="quote"') < html.index('id="rooms"')
    assert 'resort-media-band resort-quote-panel' in html
    assert '<h3>Room floor plans</h3>' not in html
    assert 'aria-haspopup="dialog"' in html and '<h3>Room floor plan</h3>' in html
    assert 'resort-facts-band' in html and 'resort-headed-panel' in html
    for section in ('Quick resort facts', 'Rooms &amp; accommodation', 'Restaurants &amp; bars', 'Families &amp; children', 'Also consider'):
        assert section in html
    assert 'Supplier planning source' not in html
    for section_id in ('dining', 'families', 'activities'):
        section = re.search(r'<section id="' + section_id + r'".*?</section>', html, re.S).group(0)
        assert '<details' not in section and '<summary' not in section
    assert 'resort-map-band' in html
    assert '<section id="map"' in html
    assert 'Quote required' in html
    assert 'Room factsheet' in html
    assert 'All rights reserved - Beachcomber Resorts &amp; Hotels' not in html
    assert 'Independent specialist. Not owned by Beachcomber Resorts &amp; Hotels.' in html
    assert f'value="{code}" selected' in html or f'value="{code}"\n' in html or re.search(f'value="{code}"[^>]*selected', html)
    blocks = [json.loads(value) for value in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert any(value.get('@type') == 'Hotel' and value['name'] == RESEARCH[code]['title'] for value in blocks)
    assert all('aggregateRating' not in value for value in blocks)
    assert ('Standard Room' if code == 'MAU' else RESEARCH[code]['rooms'][0]['name']) in html
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith(('/guides/', '/packages/', '/compare?', '/resorts/')):
            assert client.get(href.replace('&amp;', '&')).status_code == 200


def test_internal_comparison_and_contact(app):
    client = app.test_client()
    html = client.get('/compare?resort=VIC&resort=CAN').text
    assert 'Meal plans' in html and 'Families and children' in html
    assert 'Supplier source' not in html
    assert 'https://www.beachcomber.co.za/' not in html
    assert 'Victoria Beachcomber' in client.get('/contact?resort=Victoria+Beachcomber').text
    assert 'Research Mauricia Beachcomber' in client.get('/packages/1').text


def test_corrupt_override_and_drafts_fail_closed(app):
    with app.app_context():
        resort = db.session.execute(db.select(Resort).where(Resort.code == 'VIC')).scalar_one()
        slug = resort.slug
        db.session.add(Setting(key='resort_research_VIC', value='{"alternatives": [{}]}'))
        db.session.commit()
        assert research_for(resort) is None
    client = app.test_client()
    assert 'awaiting source review' in client.get('/resorts/' + slug).text
    with app.app_context():
        resort = db.session.execute(db.select(Resort).where(Resort.code == 'VIC')).scalar_one()
        resort.published = False
        db.session.commit()
    assert client.get('/resorts/' + slug).status_code == 404


@pytest.mark.parametrize('key,value', [('source','javascript:alert(1)'), ('reviewed','2099-01-01'), ('rooms',[{'name':'Bad'}]), ('alternatives',[{}]), ('image_verified','yes')])
def test_validation(key, value):
    data = copy.deepcopy(RESEARCH['VIC'])
    data[key] = value
    with pytest.raises(ValueError):
        validate_research(data)


def test_editor_auth_csrf_roundtrip_and_escape(app):
    client = app.test_client()
    path = '/admin/resort-research/2'
    assert client.get(path).status_code == 302
    assert client.post(path, data={}).status_code == 400
    client.post('/admin/login', data={'csrf_token':csrf(client, '/admin/login'), 'email':'research@example.test', 'password':'Research-test-only'})
    assert client.get(path).status_code == 200
    data = copy.deepcopy(RESEARCH['VIC'])
    form = {key: data[key] for key, _ in TEXT_FIELDS}
    form['intro'] = '<script>alert(1)</script>'
    form['csrf_token'] = csrf(client, path)
    for collection, fields in ROW_FIELDS.items():
        form[collection + '_count'] = str(len(data[collection]))
        for index, row in enumerate(data[collection]):
            form.update({f'{collection}_{index}_{key}':row[key] for key, _ in fields})
    assert client.post(path, data=form).status_code == 303
    assert 'Edit resort information' in client.get('/admin/content/resorts').text
    html = client.get('/resorts/victoria-beachcomber').text
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html
    form['source'] = 'http://unverified.example'
    assert 'Use public HTTPS' in client.post(path, data=form).text
    with app.app_context():
        resort = db.session.execute(db.select(Resort).where(Resort.code == 'VIC')).scalar_one()
        assert research_for(resort)['source'] == data['source']


def test_resort_packages_filtered_and_prices_fresh(app):
    today = date.today()
    with app.app_context():
        package = db.session.get(Package, 2)
        package.supplier_updated = datetime.now(timezone.utc)
        package.supplier_rate = {'packages':[{'pricePerPersonZARFrom':22000}], 'bookingFromDate':(today-timedelta(days=1)).isoformat(), 'bookingToDate':(today+timedelta(days=20)).isoformat(), 'travelFromDate':(today+timedelta(days=30)).isoformat(), 'travelToDate':(today+timedelta(days=60)).isoformat()}
        db.session.add(Package(resort_id=package.resort_id, title='Private draft package', published=False))
        db.session.commit()
    client = app.test_client()
    html = client.get('/resorts/victoria-beachcomber').text
    assert 'Private draft package' not in html
    assert 'Mauricia Beachcomber escape' not in html
    assert 'From R 22 000' in html
    with app.app_context():
        package = db.session.get(Package, 2)
        package.supplier_updated = datetime.now(timezone.utc) - timedelta(days=3)
        db.session.commit()
    assert 'From R' not in client.get('/resorts/victoria-beachcomber').text


def test_photo_approval_applies_only_to_the_approved_image(app):
    with app.app_context():
        resort = db.session.get(Resort, 2)
        data = copy.deepcopy(RESEARCH['VIC'])
        data['image_verified'] = True
        save_research(resort, data)
        assert research_for(resort)['image_verified']
        resort.image_url = '/static/images/replacement.jpg'
        db.session.commit()
        assert not research_for(resort)['image_verified']


def test_phase_one_customer_confidence(app):
    client = app.test_client()
    home = client.get('/').text
    assert 'Trusted by my travellers' in home
    assert 'dirk-profile-480.webp' in home
    assert 'What happens after you enquire?' in home
    for path in ('/', '/contact', '/enquiry-received'):
        html = client.get(path).text
        assert 'Monday-Friday, 9am-5pm (South African time)' in html
        assert 'Review before you book' in html
    for path in ('/packages', '/resorts', '/packages/1', '/compare?resort=VIC&resort=TAB'):
        response = client.get(path)
        assert response.status_code == 200
        assert '/static/uploads/' in response.text
        assert 'holiday inspiration' not in response.text
