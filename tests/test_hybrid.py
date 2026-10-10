from datetime import date, timedelta
import re

import pytest
from werkzeug.datastructures import MultiDict

from website import create_app
from website.hybrid_content import setup_hybrid
from website.models import Enquiry, Page, Resort, User, db
from website.planning import reviewed_tags, shortlist, validate_brief
from website.seed import seed


@pytest.fixture
def hybrid():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'hybrid-test', 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'RATELIMIT_ENABLED': False})
    with app.app_context():
        db.create_all()
        seed()
        setup_hybrid()
        admin = User(email='hybrid@example.test')
        admin.set_password('Hybrid-test-password-only')
        db.session.add(admin)
        db.session.commit()
    return app


def token(client, path):
    return re.search(r'name="csrf_token" value="([^"]+)"', client.get(path).text).group(1)


def form():
    return MultiDict(dict(traveller='family', priorities=['family', 'beach'], adults='2', children='2', infants='0',
                          budget='80000', budget_basis='Total party', travel_date='', nights='7', departure='Johannesburg'))


@pytest.mark.parametrize('path', ['/', '/resort-finder', '/compare', '/compare?resort=VIC&resort=MAU', '/guides',
                                  '/guides/meal-plans', '/guides/family-rooms', '/quote-search', '/sitemap.xml', '/robots.txt'])
def test_hybrid_routes(hybrid, path):
    assert hybrid.test_client().get(path).status_code == 200


def test_finder_enquiry_handoff_private_and_persisted(hybrid):
    client = hybrid.test_client()
    data = form()
    data['csrf_token'] = token(client, '/resort-finder')
    response = client.post('/resort-finder', data=data)
    assert response.status_code == 303
    assert response.location.endswith('/resort-finder/results') and '?' not in response.location
    result = client.get(response.location)
    assert 'Why explore it?' in result.text
    assert result.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert result.headers['Cache-Control'] == 'no-store'
    assert '80000' not in client.get('/compare?resort=VIC').text
    contact = client.get('/contact')
    assert 'R 80,000 (Total party)' in contact.text
    assert client.post('/contact', data={'csrf_token': token(client, '/contact'), 'name': 'Test Person',
                                        'email': 'person@example.test', 'message': 'Please help with my shortlist.', 'consent': 'on'}).status_code == 302
    with hybrid.app_context():
        enquiry = db.session.execute(db.select(Enquiry)).scalar_one()
        assert 'Budget preference: R 80,000' in enquiry.message
        assert 'Party: 2 adults, 2 children' in enquiry.message
    with client.session_transaction() as session:
        assert 'planning_brief' not in session


@pytest.mark.parametrize('key,value', [('traveller', 'invalid'), ('budget', '-1'), ('adults', '7'),
                                     ('nights', '0'), ('departure', 'Unknown'), ('travel_date', '2020-01-01'),
                                     ('budget_basis', 'random'), ('priorities', ['family', 'beach', 'spa', 'golf'])])
def test_finder_validates_inputs(key, value):
    data = form()
    if isinstance(value, list):
        data.setlist(key, value)
    else:
        data[key] = value
    with pytest.raises(ValueError):
        validate_brief(data)


def test_family_age_context_and_value_are_not_pricing(hybrid):
    data = form()
    data['traveller'] = 'couple'
    with pytest.raises(ValueError, match='Family'):
        validate_brief(data)
    data['children'], data['traveller'] = '0', 'couple'
    data.setlist('priorities', ['value'])
    with hybrid.app_context():
        resorts = db.session.execute(db.select(Resort)).scalars().all()
        assert shortlist(resorts, validate_brief(data)) == []


def test_source_freshness_drafts_and_closure(hybrid):
    with hybrid.app_context():
        resort = db.session.execute(db.select(Resort).where(Resort.code == 'DIN')).scalar_one()
        data = form()
        data['travel_date'] = '2027-05-20'
        assert shortlist([resort], validate_brief(data)) == []
        data['travel_date'] = ''
        assert shortlist([resort], validate_brief(data))
        resort.planning_tags = 'adults-only,beach'
        assert shortlist([resort], validate_brief(data)) == []
        resort.planning_tags = 'family,beach'
        resort.planning_reviewed = (date.today() - timedelta(days=181)).isoformat()
        assert reviewed_tags(resort) == set()
        assert shortlist([resort], validate_brief(data)) == []
        resort.planning_reviewed = date.today().isoformat()
        resort.published = False
        assert shortlist([resort], validate_brief(data)) == []


def test_comparison_limits_csrf_and_unpublished(hybrid):
    client = hybrid.test_client()
    assert client.get('/compare?resort=VIC&resort=MAU&resort=TAB&resort=DIN').status_code == 400
    assert client.get('/compare?resort=OTHER').status_code == 404
    assert client.post('/compare/enquire', data={'resort': 'VIC'}).status_code == 400
    assert client.post('/resort-finder', data=form()).status_code == 400
    with hybrid.app_context():
        db.session.get(Resort, 1).published = False
        db.session.commit()
    assert client.get('/compare?resort=MAU').status_code == 404
    response = client.post('/compare/enquire', data={'csrf_token': token(client, '/contact'), 'resort': ['VIC', 'TAB']})
    assert response.status_code == 303
    assert 'Victoria Beachcomber' in client.get('/contact').text


def test_guides_hide_drafts_and_setup_preserves_deletions(hybrid):
    client = hybrid.test_client()
    with hybrid.app_context():
        guide = db.session.execute(db.select(Page).where(Page.slug == 'guide-meal-plans')).scalar_one()
        guide.published = False
        resort = db.session.get(Resort, 1)
        resort.advisor_notes = 'My approved note.'
        removed = db.session.execute(db.select(Page).where(Page.slug == 'guide-family-rooms')).scalar_one()
        db.session.delete(removed)
        db.session.commit()
        setup_hybrid()
        assert resort.advisor_notes == 'My approved note.'
    assert client.get('/guides/meal-plans').status_code == 404
    assert client.get('/guides/family-rooms').status_code == 404
    sitemap = client.get('/sitemap.xml').text
    assert '/guides/meal-plans' not in sitemap
    assert '/guides/family-rooms' not in sitemap
    assert '/quotes/' not in sitemap
    assert '/admin' not in sitemap
    assert '/guides/choose-your-resort' in sitemap


def test_admin_can_edit_sourced_facts_and_advisor_notes(hybrid):
    client = hybrid.test_client()
    assert client.post('/admin/login', data={'csrf_token': token(client, '/admin/login'), 'email': 'hybrid@example.test',
                                           'password': 'Hybrid-test-password-only'}).status_code == 302
    data = dict(csrf_token=token(client, '/admin/content/resorts/1/edit'), code='MAU', name='Mauricia Beachcomber',
                slug='mauricia-beachcomber', location='Grand Baie', category='Family', description='Existing description.',
                image_url='/static/images/resort-1.jpg', published='on', planning_tags=['family', 'beach'],
                planning_source='https://www.beachcomber.co.za/', planning_reviewed=date.today().isoformat(),
                advisor_notes='An approved personal note.', consideration='Confirm your room category.')
    assert client.post('/admin/content/resorts/1/edit', data=data).status_code == 302
    assert 'An approved personal note.' in client.get('/resorts/mauricia-beachcomber').text
    data['planning_source'] = 'javascript:alert(1)'
    assert 'Use a public HTTPS source address.' in client.post('/admin/content/resorts/1/edit', data=data).text


def test_results_cannot_be_read_in_another_browser(hybrid):
    client = hybrid.test_client()
    data = form()
    data['csrf_token'] = token(client, '/resort-finder')
    client.post('/resort-finder', data=data)
    assert hybrid.test_client().get('/resort-finder/results').status_code == 302
    assert client.post('/planning/clear', data={'csrf_token': token(client, '/contact')}).status_code == 303
    assert client.get('/resort-finder/results').status_code == 302
