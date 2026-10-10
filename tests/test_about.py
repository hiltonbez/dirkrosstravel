from html.parser import HTMLParser

from website import create_app
from website.models import Page, Setting, db
from website.seed import seed


class ProfileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_about_profile_metadata_and_contact_details():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'RATELIMIT_ENABLED': False})
    with app.app_context():
        db.create_all()
        seed()
    response = app.test_client().get('/pages/about')
    assert response.status_code == 200
    parser = ProfileParser()
    parser.feed(response.text)
    assert sum(tag == 'h1' for tag, _ in parser.tags) == 1
    assert any(attrs.get('itemtype') == 'https://schema.org/ProfilePage' for _, attrs in parser.tags)
    assert any(attrs.get('itemtype') == 'https://schema.org/Person' for _, attrs in parser.tags)
    assert any(attrs.get('name') == 'description' and '20+' in attrs.get('content', '') for _, attrs in parser.tags)
    assert any(attrs.get('rel') == 'canonical' and attrs.get('href') == 'http://localhost/pages/about' for _, attrs in parser.tags)
    assert 'mailto:dirk.ross@flightcentre.co.za' in response.text
    assert 'tel:+27824475370' in response.text
    assert 'https://wa.me/27824475370' in response.text
    assert '299 Pendoring Road' in response.text
    assert 'through my Flight Centre affiliation' in response.text
    assert '<h2>Meet Dirk</h2>' in response.text
    assert 'Mauritius is one of my specialties.' in response.text
    assert 'Online resort searches on this site cover Beachcomber Mauritius.' in response.text
    assert 'Start planning my holiday' in response.text
    assert 'aggregateRating' not in response.text
    assert 'BreadcrumbList' in response.text
    assert 'og:image' in response.text
    assert 'srcset=' in response.text
    client = app.test_client()
    assert 'BEACHCOMBER RESORTS AND PACKAGES' in client.get('/').text
    contact = client.get('/contact').text
    assert 'WhatsApp Dirk' in contact
    assert 'https://wa.me/27824475370' in contact


def test_about_content_is_editable_and_markdown_is_sanitized():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'RATELIMIT_ENABLED': False})
    with app.app_context():
        db.create_all()
        seed()
        page = db.session.execute(db.select(Page).where(Page.slug == 'about')).scalar_one()
        page.body = '## Updated heading\n\nUpdated words. <script>alert(1)</script>\n\n[Unsafe](javascript:alert(1))'
        db.session.get(Setting, 'advisor_name').value = 'Updated Name'
        db.session.commit()
    response = app.test_client().get('/pages/about')
    assert '<h2>Updated heading</h2>' in response.text
    assert 'Updated Name' in response.text
    assert '<script>alert(1)</script>' not in response.text
    assert 'href="javascript:' not in response.text
    with app.app_context():
        db.session.get(Setting, 'about_benefits').value = '## My updated benefits\n\nSafe text <script>unsafe()</script>'
        db.session.commit()
    edited = app.test_client().get('/pages/about').text
    assert '<h2>My updated benefits</h2>' in edited
    assert '<script>unsafe()</script>' not in edited


def test_about_general_enquiry_path_has_relevant_copy():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'RATELIMIT_ENABLED': False})
    with app.app_context():
        db.create_all()
        seed()
    client = app.test_client()
    assert 'Not sure where to go?' in client.get('/contact?interest=travel').text
    assert 'which Beachcomber resort' in client.get('/contact').text
