import io
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests

from website import create_app
from website.beachcomber import BeachcomberClient, SupplierError, build_quote_payload
from website.models import Enquiry, Package, Page, Quote, Resort, Setting, User, db
from website.seed import seed
from website.sync import current_rate_price, sync_catalogue


@pytest.fixture
def app(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret', 'SQLALCHEMY_DATABASE_URI': 'sqlite://',
                      'RATELIMIT_ENABLED': False, 'UPLOAD_FOLDER': str(tmp_path / 'uploads')})
    with app.app_context():
        db.create_all()
        seed()
        user = User(email='admin@example.test')
        user.set_password('A-test-password-only')
        db.session.add(user)
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client, path='/contact'):
    response = client.get(path)
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


def signin(client):
    return client.post('/admin/login', data={'csrf_token': csrf(client, '/admin/login'), 'email': 'admin@example.test', 'password': 'A-test-password-only'})


def valid_search():
    departure = datetime.now().date() + timedelta(days=20)
    return dict(hotelCode='MAU', dateDeparture=departure.isoformat(), dateReturn=(departure + timedelta(days=7)).isoformat(),
                departureCity='JOHANNESBURG', nbrAdults='2', nbrChildren='0', nbrInfants='0', includeAir='on')


@pytest.mark.parametrize('path', ['/', '/packages', '/resorts', '/contact', '/pages/about', '/packages/1', '/resorts/mauricia-beachcomber', '/admin/login'])
def test_public_pages(client, path):
    assert client.get(path).status_code == 200


def test_admin_protected_and_csrf(client):
    assert client.get('/admin/').status_code == 302
    assert client.post('/admin/content/pages/new', data={'title': 'Unsafe'}).status_code == 400
    assert client.post('/contact', data={'name': 'Person'}).status_code == 400
    assert client.get('/admin/content/pages/1/delete').status_code == 405


def test_admin_crud_and_draft_visibility(app, client):
    assert signin(client).status_code == 302
    data = dict(csrf_token=csrf(client, '/admin/content/pages/new'), slug='travel-notes', title='Travel notes', body='Useful travel information.')
    assert client.post('/admin/content/pages/new', data=data).status_code == 302
    assert client.get('/pages/travel-notes').status_code == 404
    with app.app_context():
        item_id = db.session.execute(db.select(Page).where(Page.slug == 'travel-notes')).scalar_one().id
    data['published'] = 'on'
    assert client.post(f'/admin/content/pages/{item_id}/edit', data=data).status_code == 302
    assert client.get('/pages/travel-notes').status_code == 200
    assert client.post(f'/admin/content/pages/{item_id}/delete', data={'csrf_token': csrf(client, '/admin/content/pages')}).status_code == 302
    assert client.get('/pages/travel-notes').status_code == 404


def test_resort_delete_with_packages_is_blocked(app, client):
    signin(client)
    assert client.post('/admin/content/resorts/1/delete', data={'csrf_token': csrf(client, '/admin/content/resorts')}).status_code == 302
    with app.app_context():
        assert db.session.get(Resort, 1) is not None


def test_seed_does_not_restore_deleted_content(app):
    with app.app_context():
        package = db.session.get(Package, 1)
        db.session.delete(package)
        db.session.commit()
        seed()
        assert db.session.get(Package, 1) is None


def test_enquiry_persists_and_escapes_content(app, client):
    data = dict(csrf_token=csrf(client), name='Test Traveller', email='traveller@example.test', message='<script>alert(1)</script> A family holiday please.', consent='on')
    assert client.post('/contact', data=data).status_code == 302
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Enquiry)) == 1
    signin(client)
    response = client.get('/admin/enquiries')
    assert '<script>alert(1)</script>' not in response.text
    assert '&lt;script&gt;' in response.text


def test_enquiry_requires_consent(client):
    assert client.post('/contact', data=dict(csrf_token=csrf(client), name='Test Person', email='person@example.test', message='Please arrange a holiday.')).status_code == 400


def test_dashboard_counts_enquiries_in_all_statuses(app, client):
    data = dict(csrf_token=csrf(client), name='Test Traveller', email='traveller@example.test',
                message='Please arrange a family holiday.', consent='on')
    assert client.post('/contact', data=data).status_code == 302
    with app.app_context():
        item = db.session.execute(db.select(Enquiry)).scalar_one()
        item.status = 'In progress'
        db.session.commit()
    signin(client)
    response = client.get('/admin/')
    assert '<span>Enquiries</span><strong>1</strong>' in response.text


def test_about_sections_can_be_saved_through_admin(app, client):
    signin(client)
    with app.app_context():
        data = {item.key: item.value for item in db.session.execute(db.select(Setting)).scalars()}
    data['csrf_token'] = csrf(client, '/admin/settings')
    data['about_benefits'] = '## Updated benefits\n\n' + 'Personal advice. ' * 40
    assert client.post('/admin/settings', data=data).status_code == 302
    assert '<h2>Updated benefits</h2>' in client.get('/pages/about').text
    assert 'maxlength="4000"' in client.get('/admin/settings').text


def test_quote_payload_types_and_minimum_dates():
    data = valid_search()
    payload = build_quote_payload(data)
    assert all(isinstance(value, str) for value in payload.values())
    assert payload['includeAir'] == 'true' and payload['dateDeparture'].endswith('T00:00:00')
    data['dateDeparture'] = datetime.now().date().isoformat()
    with pytest.raises(ValueError, match='10 days'):
        build_quote_payload(data)


def test_child_age_and_wedding_date_required():
    data = valid_search()
    data['nbrChildren'] = '1'
    with pytest.raises(ValueError):
        build_quote_payload(data)
    data['childAge1'] = '8'
    assert build_quote_payload(data)['childAge1'] == '8'
    data['honeymoonRates'] = 'on'
    with pytest.raises(ValueError, match='wedding date'):
        build_quote_payload(data)


def test_infant_validation():
    data = valid_search()
    data['nbrInfants'] = '1'
    data['infantDOB1'] = '2000-01-01'
    with pytest.raises(ValueError, match='under 2'):
        build_quote_payload(data)


def response(data, ok=True):
    result = Mock()
    result.ok = ok
    result.json.return_value = data
    return result


def test_supplier_token_cache_headers_and_quote_mapping():
    transport = Mock()
    transport.post.side_effect = [response({'userToken': 'PRIVATE-TOKEN', 'expires': (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()}),
                                  response({'quoteRef': 'QR-123', 'roomOptions': [], 'userToken': 'PRIVATE-TOKEN'})]
    client = BeachcomberClient('PRIVATE-KEY', 'agent', 'PRIVATE-PASSWORD', transport)
    result = client.quote(valid_search())
    assert 'userToken' not in result
    assert client.token() == 'PRIVATE-TOKEN'
    assert transport.post.call_count == 2
    call = transport.post.call_args_list[0]
    assert call.kwargs['headers']['BeachcomberKey'] == 'PRIVATE-KEY'
    assert call.kwargs['auth'] == ('agent', 'PRIVATE-PASSWORD')
    assert transport.post.call_args.kwargs['json']['requestToken'] == 'PRIVATE-TOKEN'
    assert 'verify' not in transport.post.call_args.kwargs


@pytest.mark.parametrize('data,ok', [({'errorMsg': 'failure'}, True), ({'message': 'failure'}, False)])
def test_supplier_http_and_application_errors(data, ok):
    transport = Mock()
    transport.post.return_value = response(data, ok)
    with pytest.raises(SupplierError):
        BeachcomberClient('KEY', transport=transport).post('/getRates')


def test_supplier_transport_error_and_bad_json():
    transport = Mock()
    transport.post.side_effect = requests.Timeout('private details')
    with pytest.raises(SupplierError, match='could not be reached'):
        BeachcomberClient('KEY', transport=transport).post('/getRates')
    transport.post.side_effect = None
    transport.post.return_value.json.side_effect = ValueError()
    with pytest.raises(SupplierError, match='unreadable'):
        BeachcomberClient('KEY', transport=transport).post('/getRates')


def test_unconfigured_quote_has_enquiry_fallback(client):
    data = valid_search()
    data['csrf_token'] = csrf(client, '/quote-search')
    response = client.post('/quote', data=data)
    assert response.status_code == 503
    assert 'Let Dirk arrange your quote' in response.text
    assert 'name="message"' in response.text


def test_quote_ownership_and_expiry(app, client):
    app.extensions['beachcomber'].quote = Mock(return_value={'quoteRef': 'QR-123', 'roomOptions': []})
    data = valid_search()
    data['csrf_token'] = csrf(client, '/quote-search')
    location = client.post('/quote', data=data).headers['Location']
    assert client.get(location).status_code == 200
    assert app.test_client().get(location).status_code == 404
    with app.app_context():
        item = db.session.execute(db.select(Quote)).scalar_one()
        item.expires = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
    assert client.get(location).status_code == 400


def test_hidden_resort_hides_its_packages(app, client):
    with app.app_context():
        db.session.get(Resort, 1).published = False
        db.session.commit()
    assert client.get('/packages/1').status_code == 404
    assert client.get('/resorts/mauricia-beachcomber').status_code == 404


def test_invalid_photo_upload_rejected(client):
    signin(client)
    response = client.post('/admin/photos', data={'csrf_token': csrf(client, '/admin/photos'), 'photo': (io.BytesIO(b'<svg onload="alert(1)"></svg>'), 'image.svg')}, content_type='multipart/form-data', follow_redirects=True)
    assert 'Please choose a valid' in response.text


def test_rates_import_draft_and_stale_prices(app):
    with app.app_context():
        today = datetime.now().date()
        rate = dict(identity='SUPPLIER-1', bcReference='Supplier special', country='Mauritius', hotelName='Mauricia Beachcomber Resort & Spa',
                    numberOfNights='7', bookingFromDate=(today-timedelta(days=1)).isoformat(), bookingToDate=(today+timedelta(days=20)).isoformat(),
                    travelToDate=(today+timedelta(days=60)).isoformat(), packages=[{'pricePerPersonZARFrom': 25000}])
        client = Mock()
        client.key = 'KEY'
        client.post.side_effect = [{'lastRatesUpdate': 'today'}, [], {'lastRatesUpdate': 'today', 'beachcomberRates': [rate]}]
        sync_catalogue(client)
        package = db.session.execute(db.select(Package).where(Package.supplier_identity == 'SUPPLIER-1')).scalar_one()
        assert not package.published
        assert current_rate_price(package) == 25000
        package.supplier_updated = datetime.now(timezone.utc) - timedelta(days=3)
        assert current_rate_price(package) is None
        package.title = 'My curated title'
        db.session.commit()
        client.post.side_effect = [{'lastRatesUpdate': 'today'}, []]
        sync_catalogue(client)
        assert current_rate_price(package) == 25000
        assert package.title == 'My curated title'


def test_invalid_image_urls(client):
    from website.admin import valid_image_url
    assert not valid_image_url('javascript:alert(1)')
    assert not valid_image_url('/static/../../private')
    assert valid_image_url('/static/images/resort-1.jpg')


def test_valid_photo_upload_and_delete(app, client):
    from pathlib import Path
    from PIL import Image
    signin(client)
    content = io.BytesIO()
    Image.new('RGB', (16, 16), 'red').save(content, 'PNG')
    content.seek(0)
    response = client.post('/admin/photos', data={'csrf_token': csrf(client, '/admin/photos'),
                           'photo': (content, 'fixture.png')}, content_type='multipart/form-data')
    assert response.status_code == 302
    files = list(Path(app.config['UPLOAD_FOLDER']).glob('*.jpg'))
    assert len(files) == 1
    assert client.post('/admin/photos/' + files[0].name + '/delete', data={'csrf_token': csrf(client, '/admin/photos')}).status_code == 302
    assert not files[0].exists()


def test_photo_folders_list_upload_delete_and_block_traversal(app, client):
    from pathlib import Path
    from PIL import Image
    folder = Path(app.config['UPLOAD_FOLDER']) / 'royal-palm-beachcomber'
    folder.mkdir(parents=True)
    original = folder / 'royal_palm_aerial.jpg'
    Image.new('RGB', (16, 16), 'blue').save(original)
    assert client.get('/admin/photos?folder=royal-palm-beachcomber').status_code == 302
    signin(client)
    listing = client.get('/admin/photos?folder=royal-palm-beachcomber')
    assert listing.status_code == 200
    assert 'Royal Palm Beachcomber' in listing.text
    assert '/static/uploads/royal-palm-beachcomber/royal_palm_aerial.jpg' in listing.text
    assert '1 photographs' in listing.text
    content = io.BytesIO()
    Image.new('RGB', (16, 16), 'red').save(content, 'PNG')
    content.seek(0)
    response = client.post('/admin/photos?folder=royal-palm-beachcomber',
                           data={'csrf_token': csrf(client, '/admin/photos'), 'photo': (content, 'fixture.png')},
                           content_type='multipart/form-data')
    assert response.status_code == 302
    assert 'folder=royal-palm-beachcomber' in response.location
    assert len(list(folder.glob('*.jpg'))) == 2
    assert client.get('/admin/photos?folder=../outside').status_code == 404
    assert client.get('/admin/photos?folder=nonexistent').status_code == 404
    assert client.post('/admin/photos/royal-palm-beachcomber/../outside.jpg/delete',
                       data={'csrf_token': csrf(client, '/admin/photos')}).status_code == 404
    with app.app_context():
        resort = db.session.execute(db.select(Resort).limit(1)).scalar_one()
        resort.image_url = '/static/uploads/royal-palm-beachcomber/royal_palm_aerial.jpg'
        db.session.commit()
    endpoint = '/admin/photos/royal-palm-beachcomber/royal_palm_aerial.jpg/delete'
    client.post(endpoint, data={'csrf_token': csrf(client, '/admin/photos')})
    assert original.exists()
    with app.app_context():
        resort = db.session.execute(db.select(Resort).limit(1)).scalar_one()
        resort.image_url = '/static/images/resort-1.jpg'
        db.session.commit()
    client.post(endpoint, data={'csrf_token': csrf(client, '/admin/photos')})
    assert not original.exists()


@pytest.mark.parametrize('rooms', [[None], [{'packages': 'invalid'}]])
def test_malformed_supplier_rooms_are_rejected(rooms):
    client = BeachcomberClient('KEY', 'agent', 'password')
    client.token = Mock(return_value='TOKEN')
    client.post = Mock(return_value={'quoteRef': 'QR', 'roomOptions': rooms})
    with pytest.raises(SupplierError, match='room information'):
        client.quote(valid_search())
