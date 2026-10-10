"""Small, source-attributed testimonial selection with manual verification."""
import json
from datetime import date
from urllib.parse import urlsplit

from .models import Setting, db

KEY = 'about_reviews'
DEFAULTS = {
    'google_url': 'https://www.google.com/maps?cid=17467375791387667682',
    'rating': '', 'count': '', 'checked': '',
    'items': [
        {'name': 'Tarien Breytenbach',
         'quote': 'He really went out of his way to make our admin for the trip as effortless as possible. We will definitely book out future trips through him as well.',
         'theme': 'Making travel easier', 'context': 'Personal assistance and plans to book again.',
         'source': 'Google review',
         'url': 'https://www.google.com/maps/contrib/111223823858236032936/reviews?hl=en-GB', 'published': True},
        {'name': 'Colleen Potgieter',
         'quote': "We have been using Dirk\u2019s services for many years, and his expertise and attention to detail are outstanding.",
         'theme': 'Trusted over the years', 'context': 'Long-term service and attention to detail.',
         'source': 'Google review',
         'url': 'https://www.google.com/maps/contrib/115014433093562527639/reviews?hl=en-GB', 'published': True},
        {'name': 'Adolph Van Der Westhuizen',
         'quote': 'Great service and kept in touch with us and made sure we always updated. Appreciated his effort and hard work',
         'theme': 'Keeping you informed', 'context': 'Communication and support throughout the arrangements.',
         'source': 'Google review',
         'url': 'https://www.google.com/maps/contrib/117521462191770585336/reviews?hl=en-GB', 'published': True},
        {'name': 'Graham Damp', 'quote': 'all our travel arrangements were flawless.',
         'theme': 'Careful arrangements', 'context': 'Feedback on travel planning.',
         'url': 'https://dirkrosstravel.com/', 'published': True},
        {'name': 'Veronica Magola', 'quote': 'on a public holiday and after hours.',
         'theme': 'Help when it mattered', 'context': "Help arranging her mother's airline ticket.",
         'url': 'https://dirkrosstravel.com/', 'published': True},
    ],
}


def https_url(value, google=False):
    parsed = urlsplit(value)
    host = parsed.hostname or ''
    if parsed.scheme != 'https' or not host or parsed.username or parsed.password:
        raise ValueError('Source links must be public HTTPS addresses.')
    if google and host not in ('g.page', 'maps.app.goo.gl', 'google.com', 'www.google.com', 'maps.google.com'):
        raise ValueError('Use a Google Business Profile or Google Maps share link.')
    return value


def validate(data):
    if len(data['google_url']) > 1000 or not 0 <= len(data['items']) <= 5:
        raise ValueError('Check the profile link and testimonial selection.')
    data['google_url'] = https_url(data['google_url'], google=True)
    rating, count, checked = data['rating'], data['count'], data['checked']
    if any((rating, count, checked)):
        try:
            numeric_rating = float(rating)
            numeric_count = int(count)
            checked_date = date.fromisoformat(checked)
        except (ValueError, TypeError):
            raise ValueError('Enter a rating, positive review count and verification date together.') from None
        if not 1 <= numeric_rating <= 5 or numeric_count < 1 or checked_date > date.today():
            raise ValueError('Check the rating, review count and verification date.')
    for item in data['items']:
        item.setdefault('source', 'Website testimonial')
        if item['source'] not in ('Website testimonial', 'Google review'):
            raise ValueError('Select a website testimonial or Google review source.')
        if not isinstance(item['published'], bool):
            raise ValueError('Invalid publication status.')
        for key, limit in [('name', 100), ('quote', 1200), ('theme', 100), ('context', 250), ('url', 1000)]:
            if len(item[key]) > limit:
                raise ValueError('A testimonial field exceeds its maximum length.')
        if item['published'] and not all(item[key] for key in ('name', 'quote', 'url')):
            raise ValueError('Published testimonials need a name, exact excerpt and source link.')
        if item['url']:
            https_url(item['url'], google=item['source'] == 'Google review')
    return data


def load_reviews():
    setting = db.session.get(Setting, KEY)
    try:
        data = json.loads(setting.value) if setting else json.loads(json.dumps(DEFAULTS))
        if not isinstance(data, dict) or not isinstance(data['items'], list):
            raise ValueError('Invalid review data')
        return validate(data)
    except (ValueError, TypeError, KeyError, AttributeError):
        return {'google_url': DEFAULTS['google_url'], 'rating': '', 'count': '', 'checked': '', 'items': []}


def public_reviews():
    data = load_reviews()
    data['items'] = [item for item in data['items'] if item['published']]
    data['show_rating'] = bool(data['checked'] and 0 <= (date.today() - date.fromisoformat(data['checked'])).days <= 30)
    return data


def save_reviews(data):
    setting = db.session.get(Setting, KEY) or Setting(key=KEY)
    setting.value = json.dumps(validate(data), ensure_ascii=True)
    db.session.add(setting)
    db.session.commit()
