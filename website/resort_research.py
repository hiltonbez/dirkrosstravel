import copy
import json
from datetime import date
from urllib.parse import urlsplit

from .models import Setting, db
from .resort_research_data import RESEARCH
from .resort_media import validate_media

TEXT_FIELDS = [('title', 'Full resort name'), ('stars', 'Verified classification'), ('area', 'Area'),
               ('coast', 'Coast'), ('intro', 'Positioning'), ('best_for', 'Best for (comma-separated)'),
               ('why', 'Why choose this resort'), ('beach', 'Beach'), ('pools', 'Pools'),
               ('families', 'Families and children'), ('meals', 'Meal plans'),
               ('included', 'Included activities'), ('paid', 'Activities at additional cost'),
               ('wellness', 'Spa, fitness, golf and entertainment'), ('location', 'Location'),
               ('transfer', 'Verified transfer estimate or confirmation needed'), ('caution', 'Important considerations'),
               ('source', 'Official source (HTTPS)'), ('factsheet', 'Official factsheet (HTTPS)'),
               ('reviewed', 'Information checked on (YYYY-MM-DD)')]
ROW_FIELDS = {'rooms': [('name', 'Category'), ('capacity', 'Maximum occupancy'), ('size', 'Approx. sq m'), ('detail', 'Location and layout')],
              'dining': [('name', 'Venue'), ('detail', 'Cuisine and practical details')]}


def validate_research(data):
    if not isinstance(data, dict):
        raise ValueError('Invalid resort information.')
    for key, _ in TEXT_FIELDS:
        if not isinstance(data.get(key), str) or len(data[key]) > 2000:
            raise ValueError('Resort text must be no more than 2,000 characters per field.')
    if not data['title'] or not data['source'] or not data['reviewed']:
        raise ValueError('A resort name, official source and checked date are required.')
    checked = date.fromisoformat(data['reviewed'])
    if checked > date.today():
        raise ValueError('The checked date cannot be in the future.')
    for key in ('source', 'factsheet'):
        if data[key]:
            url = urlsplit(data[key])
            if url.scheme != 'https' or not url.hostname or url.username or url.password:
                raise ValueError('Use public HTTPS source links.')
    for collection, fields in ROW_FIELDS.items():
        if not isinstance(data.get(collection), list) or len(data[collection]) > 20:
            raise ValueError('Use at most 20 rows per section.')
        for row in data[collection]:
            if not isinstance(row, dict) or any(not isinstance(row.get(key), str) or len(row[key]) > 400 for key, _ in fields):
                raise ValueError('Room and dining entries must be text up to 400 characters.')
            if not row['name']:
                raise ValueError('Each room or dining venue needs a name.')
    if not isinstance(data.get('image_verified'), bool):
        raise ValueError('Invalid photo approval.')
    if 'media' in data:
        validate_media(data['media'])
    if not isinstance(data.get('alternatives', []), list) or any(not isinstance(code, str) for code in data.get('alternatives', [])):
        raise ValueError('Invalid alternative resort codes.')
    for key in ('closure_from', 'closure_to'):
        if data.get(key):
            date.fromisoformat(data[key])
    return data


def research_for(resort):
    setting = db.session.get(Setting, 'resort_research_' + resort.code)
    try:
        data = json.loads(setting.value) if setting else copy.deepcopy(RESEARCH.get(resort.code))
        if not data:
            return None
        validate_research(data)
        if data['image_verified'] and data.get('approved_image_url') != resort.image_url:
            data['image_verified'] = False
        return data
    except (ValueError, TypeError, KeyError):
        return None


def save_research(resort, data):
    data = copy.deepcopy(data)
    data['approved_image_url'] = resort.image_url if data.get('image_verified') else ''
    setting = db.session.get(Setting, 'resort_research_' + resort.code) or Setting(key='resort_research_' + resort.code)
    setting.value = json.dumps(validate_research(data), ensure_ascii=True)
    db.session.add(setting)
    db.session.commit()


def source_date(data):
    return date.fromisoformat(data['reviewed']).strftime('%d %B %Y').lstrip('0')


def resort_faqs(data):
    return [(f"Which rooms are available at {data['title']}?", 'Compare the categories in the room table. Capacity depends on child ages, bedding and the exact booked category.'),
            (f"Is {data['title']} suitable for children?", data['families']),
            ('Which meal plans are available?', data['meals']),
            ('What is the beach and pool setting?', data['beach'] + ' ' + data['pools']),
            ('Are water sports included?', data['included'] + ' Additional cost: ' + data['paid']),
            ('How do I arrange the airport transfer?', data['transfer'] + ' Ask Dirk to include the correct transfer in your written quote.')]


def similar_resorts(resort, resorts, data):
    # These are editorial suitability comparisons, never claims of matching prices.
    codes = data.get('alternatives', []) if data else []
    available = {item.code: item for item in resorts if item.id != resort.id and item.published}
    return [available[code] for code in codes if code in available][:3]
