from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from website.beachcomber import SupplierError, build_quote_payload
from website.seasonal_offers import SeasonalOffers, search_values, summarise, travel_dates
from test_resort_research import app, csrf


def resort(**changes):
    return SimpleNamespace(code='MAU', unavailable_from='', unavailable_to='', **changes)


def result():
    return dict(includeAir=True, airGDS=[{'carrier': 'test'}], requestToken='never-public', quoteRef='private-reference',
                travelFromDate='2026-12-12T00:00:00', travelToDate='2026-12-19T00:00:00',
                roomOptions=[dict(accomProductName='Standard Room', numberOfNights='7', roomStatus='On Request',
                                  packages=[dict(packageDesc='Breakfast and dinner', packagePriceZARFrom=40000,
                                                 pricePerPersonZARFrom=20000)])])


def test_future_dates_and_fixed_party():
    rows = travel_dates(resort(), date(2026, 10, 7))
    assert rows[0]['departure'] == '2026-12-12'
    for row in rows:
        payload = build_quote_payload(search_values('MAU', row), today=date(2026, 10, 7))
        assert payload['departureCity'] == 'JOHANNESBURG'
        assert payload['nbrAdults'] == '2' and payload['nbrChildren'] == '0'
        assert payload['includeAir'] == 'true'
        assert (date.fromisoformat(row['returning']) - date.fromisoformat(row['departure'])).days == 7
    assert travel_dates(resort(), date(2028, 1, 1)) == []


def test_mauricia_package_photos_are_landscape(app):
    import re
    html = app.test_client().get('/resorts/mauricia-beachcomber').text
    images = re.findall(r'class="seasonal-photo"[^>]*><img src="([^"]+)"', html)
    assert images
    from pathlib import Path
    from PIL import Image
    assert len(images) == len(set(images))
    for src in images:
        assert src.startswith('/static/uploads/mauricia-beachcomber/')
        with Image.open(Path(app.root_path).parent / src.lstrip('/')) as image:
            assert image.width > image.height


def test_package_design_preview_is_separate_and_not_a_live_offer(app):
    supplier = Mock()
    app.extensions['beachcomber'] = supplier
    client = app.test_client()
    response = client.get('/previews/mauricia-package')
    assert response.status_code == 200
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'Illustrative price from' in response.text
    assert 'not a current bookable offer' in response.text
    assert 'R36,409' in response.text
    assert 'This deal expires' not in response.text
    assert 'STAYS &amp; EATS FREE' not in response.text
    assert supplier.quote.call_count == 0
    assert 'offer-preview-inclusions' not in client.get('/resorts/mauricia-beachcomber').text


def test_closed_resort_dates_excluded():
    item = resort()
    item.unavailable_from, item.unavailable_to = '2026-12-10', '2027-02-01'
    assert all(row['departure'] >= '2027-02-01' for row in travel_dates(item, date(2026, 10, 7)))


def test_room_carousel_preview_and_live_page_do_not_call_supplier(app):
    supplier = Mock()
    app.extensions['beachcomber'] = supplier
    client = app.test_client()
    response = client.get('/previews/mauricia-rooms')
    assert response.status_code == 200
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'rooms-preview-track' in response.text
    assert 'data-room-next' in response.text
    live = client.get('/resorts/mauricia-beachcomber').text
    assert 'rooms-preview-track' in live
    assert 'data-room-next' in live
    assert live.count('class="rooms-preview-track"') == 2
    assert 'resort photographs carousel' in live
    assert 'Compare room sizes, occupancy &amp; layouts' in live
    assert supplier.quote.call_count == 0


def test_room_details_only_match_known_categories_and_plans():
    from website.resort_media import room_details
    standard = dict(name='Standard Room', capacity='2 adults', size='32', detail='Shower only')
    media = [dict(name='Standard Room', room='Standard Room', category='room', src='/photo.jpg'),
             dict(name='The Village', room='The Village', category='room', src='/village.jpg'),
             dict(name='Standard plan', room='Standard Room', category='plan', src='/plan.jpg'),
             dict(name='Resort map', room='', category='map', src='/map.jpg')]
    rows = room_details(resort(), {'rooms': [standard]}, media)
    assert rows[0]['facts']['name'] == 'Standard Room'
    assert [plan['src'] for plan in rows[0]['plans']] == ['/plan.jpg']
    assert rows[1]['facts'] is None and rows[1]['plans'] == []


def test_live_room_details_are_accessible_and_missing_plans_are_explicit(app):
    html = app.test_client().get('/resorts/mauricia-beachcomber').text
    assert 'aria-haspopup="dialog"' in html
    assert 'id="room-detail-3"' in html
    assert 'Maximum occupancy' in html and 'Approximate area' in html
    assert 'A verified floor plan for this room type is not currently available' in html
    assert '<h3>Room floor plans</h3>' not in html
    assert '<h3>Room floor plan</h3>' in html
    assert '/static/resorts/mau/rooms/standard-room-plan.jpg' in html.split('id="room-detail-0"', 1)[1].split('</dialog>', 1)[0]


def test_exact_room_plans_remain_accessible_without_unconfirmed_facts():
    from website.resort_media import room_details
    resort = SimpleNamespace(code='CAN')
    media = [dict(name='Room photograph', room='Family Apartment', category='room', src='/photo.jpg'),
             dict(name='Family plan', room='Family Apartment', category='plan', src='/family.jpg'),
             dict(name='Other plan', room='Suite', category='plan', src='/suite.jpg')]
    rows = room_details(resort, {'rooms': []}, media)
    assert rows[0]['facts'] is None
    assert [plan['src'] for plan in rows[0]['plans']] == ['/family.jpg']


def test_resort_headings_are_inside_the_grey_panels(app):
    html = app.test_client().get('/resorts/mauricia-beachcomber').text
    assert html.count('resort-headed-panel') == 6
    assert 'class="seasonal-glance resort-media-band resort-headed-panel"' in html
    for title in ('Restaurants &amp; bars', 'Beach, pools &amp; activities',
                  'Important considerations', 'Also consider', 'Mauricia Beachcomber: your questions'):
        heading = html.split(title, 1)[0].rsplit('<h2', 1)[-1]
        assert 'resort-icon-heading' in heading and 'data-lucide' in heading
    assert 'class="resort-media-band resort-map-band"><h2' in html


def test_quote_form_is_once_before_family_panel(app):
    html = app.test_client().get('/resorts/mauricia-beachcomber').text
    assert html.count('id="quote"') == 1
    quote = html.split('id="quote"', 1)[1].split('</section>', 1)[0]
    assert 'Ask Dirk for help' not in quote and 'WhatsApp Dirk' not in quote
    assert html.count('id="rooms"') == 1
    assert html.index('id="quote"') < html.index('id="rooms"') < html.index('Bringing the family?')
    assert 'Photographs do not identify the quoted room.' not in html
    assert 'The lowest returned room and meal plan are shown.' not in html
    assert 'School-break examples follow the' not in html


def test_mauricia_has_location_map_and_property_map(app):
    html = app.test_client().get('/resorts/mauricia-beachcomber').text
    maps = html.split('id="map"', 1)[1].split('</section>', 1)[0]
    assert 'mauricia-mauritius-location-map-2025-26.png' in maps
    assert 'Mauricia_Beachcomber_Property_Map_2023-24.jpg' in maps
    assert 'class="resort-location-map"' in maps


def test_grey_quote_panel_is_live_and_old_preview_still_works(app):
    client = app.test_client()
    live = client.get('/resorts/mauricia-beachcomber').text
    preview = client.get('/resorts/mauricia-beachcomber?quote_preview=grey').text
    assert 'resort-media-band resort-quote-panel' in live
    assert 'resort-media-band resort-quote-panel' in preview
    assert 'data-lucide="calculator"' in live
    assert 'noindex, nofollow' not in live
    assert 'data-lucide="calculator"' in preview
    assert 'noindex, nofollow' in preview
    assert preview.count('id="quote"') == 1


def test_mauricia_official_categories_and_area_are_separate(app):
    from website.resort_media import mauricia_rooms, media_for, room_details
    from website.models import Resort
    from website.resort_research import research_for
    with app.app_context():
        mau = Resort.query.filter_by(code='MAU').first()
        research = research_for(mau)
        media = media_for(mau, research)
        rows = room_details(mau, research, media)
        assert len(rows) == 9
        assert [row['name'] for row in rows] == [row['name'] for row in mauricia_rooms()]
        assert len({row['name'] for row in rows}) == 9
        assert all(photo['room'] == row['name'] for row in rows for photo in row['photos'])
        assert all(plan['room'] == row['name'] for row in rows for plan in row['plans'])
        assert sum(bool(row['plans']) for row in rows) == 8
        assert rows[-1]['name'] == 'Pool Apartment' and rows[-1]['plans'] == []
        assert any(item['category'] == 'resort' and item['name'] == 'The Village accommodation area' for item in media)


def test_lowest_valid_package_and_private_fields_removed():
    data = result()
    data['roomOptions'][0]['packages'].append(dict(packageDesc='All-inclusive', packagePriceZARFrom=60000, pricePerPersonZARFrom=30000))
    summary = summarise(data)
    assert summary['person'] == 20000 and summary['total'] == 40000
    assert summary['availability'] == 'On Request'
    assert 'quoteRef' not in summary and 'requestToken' not in summary


@pytest.mark.parametrize('included, expected', [(True, True), (False, False), ('true', True), ('false', False), (None, None)])
def test_inclusions_only_report_supplier_confirmed_values(included, expected):
    data = result()
    data.update(includeTransfers=included, transferType='Private transfer',
                airGDS=[{'carrier': 'MK'}, {'carrier': 'MK'}])
    summary = summarise(data)
    assert summary['transfers_included'] is expected
    assert summary['carriers'] == ['MK']
    assert summary['transfer_type'] == 'Private transfer'


def test_live_glance_has_date_selector_without_example_prices(app):
    html = app.test_client().get('/resorts/mauricia-beachcomber').text
    assert 'Your holiday, at a glance' in html
    assert 'Your next Mauritius escape' not in html
    assert 'YOUR NEXT STEP' not in html
    assert 'A WEEK ON THE ISLAND' not in html
    for field in ['select', 'flights', 'transfers', 'room', 'meal', 'note']:
        assert 'data-glance-' + field in html
    assert 'Illustrative price from' not in html


@pytest.mark.parametrize('value', [None, 0, -20, 'NaN', float('inf'), 'bad'])
def test_invalid_price_not_advertised(value):
    data = result()
    data['roomOptions'][0]['packages'][0]['pricePerPersonZARFrom'] = value
    assert summarise(data)['status'] == 'unavailable'


def test_flights_nights_party_total_and_unavailable_rooms_checked():
    offer = travel_dates(resort(), date(2026, 10, 7))[0]
    mismatched = result()
    mismatched['travelFromDate'] = '2026-12-13'
    assert summarise(mismatched, offer)['status'] == 'unavailable'
    for field, value in [('includeAir', False), ('airGDS', [])]:
        data = result()
        data[field] = value
        assert summarise(data)['status'] == 'unavailable'
    for field, value in [('numberOfNights', 6), ('roomStatus', 'Not Available')]:
        data = result()
        data['roomOptions'][0][field] = value
        assert summarise(data)['status'] == 'unavailable'
    data = result()
    data['roomOptions'][0]['packages'][0]['packagePriceZARFrom'] = 99999
    assert summarise(data)['status'] == 'unavailable'


def test_cache_expiry_and_failure_hides_old_price(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr('website.seasonal_offers.time.monotonic', lambda: clock[0])
    client = Mock()
    client.quote.return_value = result()
    cache = SeasonalOffers()
    offer = travel_dates(resort(), date(2026, 10, 7))[0]
    assert cache.quote(client, 'MAU', offer)['person'] == 20000
    cache.quote(client, 'MAU', offer)
    assert client.quote.call_count == 1
    clock[0] += 1801
    client.quote.side_effect = SupplierError('sensitive internals')
    response = cache.quote(client, 'MAU', offer)
    assert response['status'] == 'unavailable' and 'person' not in response
    assert 'sensitive' not in str(response)


def test_public_endpoint_is_csrf_protected_and_whitelisted(app, monkeypatch):
    monkeypatch.setattr('website.seasonal_offers.travel_dates', lambda item: travel_dates(item, date(2026, 10, 7)))
    client = app.test_client()
    supplier = Mock()
    supplier.quote.return_value = result()
    app.extensions['beachcomber'] = supplier
    path = '/resorts/mauricia-beachcomber'
    from website.models import Resort, db
    with app.app_context():
        item = db.session.execute(db.select(Resort).where(Resort.code == 'MAU')).scalar_one()
        key = travel_dates(item, date(2026, 10, 7))[0]['key']
    endpoint = path + '/seasonal-prices/' + key
    assert client.get(endpoint).status_code == 405
    assert client.post(endpoint).status_code == 400
    token = csrf(client, path)
    response = client.post(endpoint, headers={'X-CSRFToken': token})
    assert response.status_code == 200 and response.json['person'] == 20000
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'private-reference' not in response.text and 'never-public' not in response.text
    assert client.post(path + '/seasonal-prices/arbitrary', headers={'X-CSRFToken': token}).status_code == 404
    assert supplier.quote.call_count == 1
