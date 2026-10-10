import json
from datetime import date, timedelta

import pytest

from website import create_app
from website.models import Setting, User, db
from website.reviews import DEFAULTS, KEY, load_reviews, public_reviews, save_reviews
from website.seed import seed


@pytest.fixture
def review_app():
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test', 'SQLALCHEMY_DATABASE_URI': 'sqlite://',
                      'RATELIMIT_ENABLED': False, 'WTF_CSRF_ENABLED': False})
    with app.app_context():
        db.create_all()
        seed()
        user = User(email='reviews@example.test')
        user.set_password('test-password')
        db.session.add(user)
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_source_labels_and_no_unverified_rating(review_app):
    text = review_app.test_client().get('/pages/about').text
    assert text.count('Website testimonial') == 2
    assert text.count('Google review <') == 3
    assert 'Read my Google reviews' in text
    assert '/5 on Google' not in text
    assert 'AggregateRating' not in text and 'aggregateRating' not in text


def test_existing_three_slot_settings_remain_editable(review_app):
    with review_app.app_context():
        data = json.loads(json.dumps(DEFAULTS))
        data['items'] = data['items'][-2:]
        for item in data['items']:
            item.pop('source', None)
        save_reviews(data)
        assert len(load_reviews()['items']) == 2
        assert all(item['source'] == 'Website testimonial' for item in load_reviews()['items'])


def test_google_source_requires_google_url(review_app):
    with review_app.app_context():
        data = load_reviews()
        data['items'][0]['url'] = 'https://example.com/'
        with pytest.raises(ValueError):
            save_reviews(data)


def test_rating_expires_and_future_date_rejected(review_app):
    with review_app.app_context():
        data = load_reviews()
        data.update(rating='5.0', count='4', checked=date.today().isoformat())
        save_reviews(data)
        assert public_reviews()['show_rating']
        data['checked'] = (date.today() - timedelta(days=31)).isoformat()
        save_reviews(data)
        assert not public_reviews()['show_rating']
        data['checked'] = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValueError):
            save_reviews(data)


def test_review_editor_requires_login_and_saves_safely(review_app):
    client = review_app.test_client()
    assert client.get('/admin/reviews').status_code == 302
    client.post('/admin/login', data={'email': 'reviews@example.test', 'password': 'test-password'})
    assert client.get('/admin/reviews').status_code == 200
    form = {'google_url': DEFAULTS['google_url']}
    for index, item in enumerate(DEFAULTS['items']):
        form.update({f'{index}_{key}': value for key, value in item.items() if key != 'published'})
        form[f'{index}_published'] = 'on'
    form['0_quote'] = '<script>alert(1)</script>'
    form.pop('1_published')
    assert client.post('/admin/reviews', data=form).status_code == 303
    text = client.get('/pages/about').text
    assert '<script>alert(1)</script>' not in text
    assert '&lt;script&gt;' in text
    assert text.count('Website testimonial') == 2
    form['0_url'] = 'javascript:alert(1)'
    response = client.post('/admin/reviews', data=form)
    assert 'public HTTPS' in response.text
    with review_app.app_context():
        assert load_reviews()['items'][0]['url'].startswith('https://')


def test_corrupt_saved_data_fails_closed(review_app):
    with review_app.app_context():
        db.session.add(Setting(key=KEY, value=json.dumps({'items': 'bad'})))
        db.session.commit()
        assert public_reviews()['items'] == []
        assert not public_reviews()['show_rating']
