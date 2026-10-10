import json
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote, urlsplit

MEDIA_FIELDS = [('name', 'Caption'), ('src', 'Local image path'), ('category', 'Type'),
                ('room', 'Room category (optional)'), ('source', 'Supplier source URL'), ('note', 'Edition or caution')]
CATEGORIES = ('resort', 'room', 'plan', 'map')
FEATURED_CAPTIONS = {'VIC': 'Aerial view', 'MAU': 'Beach', 'CAN': 'Aerial view',
                     'TAB': 'Aerial pool and beach', 'SHA': 'Resort & Blue Bay',
                     'DIN': 'Aerial view', 'PAR': 'Classic view of Le Morne', 'RP': 'Resort & beach views'}
ADMIN_GALLERIES = {
    'RP': ('royal-palm-beachcomber', ['royal_palm_aerial1.jpg', 'royal_palm_reception6.jpg', 'royal_palm_pool_gardens.jpg', 'royal_palm_beach5.jpg']),
    'DIN': ('dinarobin-beachcomber', ['dinarobin_aerial8.jpg', 'dinarobin_aerial_crescent_pool-25.jpg', 'dinarobin_pool_le_morne6.jpg', 'dinarobin_beach_bean_bags1.jpg']),
    'PAR': ('paradis-beachcomber', ['paradis_aerial_7.jpg', 'paradis_entrance.jpg', 'paradis_pool1.jpg', 'paradis_aerial_1_pristine_peninsula.jpg']),
    'TAB': ('trou-aux-biches-beachcomber', ['tab_pool12-aerial.jpg', 'tab_reception6.jpg', 'tab_caravelle.jpg', 'tab_beach11.jpg']),
    'SHA': ('shandrani-beachcomber', ['shandrani_aerial4.jpg', 'shandrani_reception-25.jpg', 'shandrani_aerial3.jpg', 'shandrani_aerial_water_sports-25.jpg']),
    'VIC': ('victoria-beachcomber', ['victoria_aerial1.jpg', 'victoria_reception1.jpg', 'victoria_pool2.jpg', 'victoria_beach4.jpg']),
    'CAN': ('canonnier-beachcomber', ['Canonnier_aerial_4.jpg', 'canonnier_25_reception.jpg', 'canonnier_pool7.jpg', 'canonnier_beach4.jpg']),
    'MAU': ('mauricia-beachcomber', ['mauricia_beach5.jpg', 'mauricia_reception_arrival1-25.jpg', 'mauricia_pool14.jpg', 'mauricia_aerial2-25.jpg']),
}


def admin_gallery(resort):
    selection = ADMIN_GALLERIES.get(resort.code)
    if not selection:
        return {}, []
    slug, filenames = selection
    root = Path(__file__).resolve().parent.parent
    folder = root / 'static/uploads' / slug
    try:
        manifest = json.loads((folder / 'source-manifest.json').read_text(encoding='utf-8'))
        items = [item for item in manifest['items'] if not item.get('error')
                 and Path(item['filename']).name == item['filename'] and (folder / item['filename']).is_file()]
        library = {unquote(item['url']): '/static/uploads/' + slug + '/' + item['filename'] for item in items}
        by_filename = {item['filename']: item for item in items}
        photos = []
        for index, filename in enumerate(filenames):
            item = by_filename.get(filename)
            if not item:
                continue
            caption = FEATURED_CAPTIONS[resort.code] if index == 0 else item['caption']
            if caption == 'Royal Palm Beachcomber Luxury' and 'beach' in filename:
                caption = 'Beach'
            elif caption == 'Trou aux Biches Beachcomber Golf Resort & Spa' and 'beach' in filename:
                caption = 'Beach'
            elif caption == 'Mauricia Beachcomber Resort & Spa' and 'aerial' in filename:
                caption = 'Aerial View'
            elif resort.code == 'CAN' and 'beach' in filename:
                caption = 'Beach'
            photos.append(dict(name=caption, src=library[unquote(item['url'])], category='resort', room='',
                               source=item['url'], note='Official supplier photograph from the admin photo library.'))
        return library, photos
    except (OSError, ValueError, TypeError, KeyError):
        return {}, []


def admin_photo(row, library):
    # Match the exact supplier asset rather than guessing its room category from its filename.
    replacement = library.get(unquote(row.get('source', '')))
    return dict(row, src=replacement) if replacement and not row['src'].startswith('/static/uploads/') else row


def seasonal_photos(resort, media, count):
    from PIL import Image

    selection = ADMIN_GALLERIES.get(resort.code)
    if not selection or count <= 0:
        return []
    slug, _ = selection
    root = Path(__file__).resolve().parent.parent
    folder = root / 'static/uploads' / slug
    try:
        items = json.loads((folder / 'source-manifest.json').read_text(encoding='utf-8'))['items']
    except (OSError, ValueError, KeyError):
        return []
    used = {row['src'] for row in media}
    fingerprints = set()
    for src in used:
        path = root / src.lstrip('/')
        if path.is_file():
            fingerprints.add(sha256(path.read_bytes()).digest())
    photos = []
    for item in items:
        filename = item.get('filename', '')
        if item.get('error') or Path(filename).name != filename:
            continue
        if not any(word in filename.lower() for word in ('aerial', 'beach', 'pool', 'garden', 'reception')):
            continue
        src = '/static/uploads/' + slug + '/' + filename
        if src in used:
            continue
        path = folder / filename
        try:
            with Image.open(path) as image:
                if image.width <= image.height:
                    continue
            fingerprint = sha256(path.read_bytes()).digest()
        except (OSError, ValueError):
            continue
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        photos.append(dict(src=src, name=item.get('caption') or resort.name))
        if len(photos) >= count:
            break
    return photos


def mauricia_rooms():
    path = Path(__file__).resolve().parent.parent / 'static/resorts/mau/rooms/catalogue.json'
    return json.loads(path.read_text(encoding='utf-8'))


def validate_media(rows):
    if not isinstance(rows, list) or len(rows) > 60:
        raise ValueError('Use at most 60 media entries.')
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) or len(row[key]) > 1000 for key, _ in MEDIA_FIELDS):
            raise ValueError('Media entries must contain valid caption, path, type and source text.')
        path = row['src']
        if not row['name'] or row['category'] not in CATEGORIES:
            raise ValueError('Each image needs a caption and valid type.')
        if not path.startswith(('/static/resorts/', '/static/uploads/')) or any(value in path for value in ('..', '\\', '?', '#', '%', '\n', '\r')):
            raise ValueError('Use an approved local image under /static/resorts/ or /static/uploads/.')
        if not path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            raise ValueError('Use a JPEG, PNG or WebP image.')
        if row.get('rotation', 0) not in (0, 180):
            raise ValueError('Invalid plan orientation.')
        if row['source']:
            source = urlsplit(row['source'])
            if source.scheme != 'https' or not source.netloc or source.username or source.password:
                raise ValueError('Use a public HTTPS supplier source URL.')
    return rows


def media_for(resort, research):
    root = Path(__file__).resolve().parent.parent
    try:
        if research and 'media' in research:
            rows = research['media']
        else:
            catalogue = json.loads((root / 'static/resorts/catalogue.json').read_text(encoding='utf-8'))
            rows = catalogue.get(resort.code, [])
        if resort.code == 'MAU':
            # Replace the legacy combined supplier categories, retaining uploaded media.
            rows = [dict(row, category='resort', room='', name='The Village accommodation area')
                    if row['name'] == 'The Village' else row
                    for row in rows]
            rows = [row for row in rows if row['category'] not in ('room', 'plan')
                    or row['src'].startswith('/static/uploads/')]
            official = mauricia_rooms()
            rows = [room['photos'][0] for room in official] + rows
            rows += [plan for room in official for plan in room['plans']]
        library, gallery = admin_gallery(resort)
        rows = [admin_photo(row, library) for row in rows]
        if gallery:
            rows = [row for row in rows if row['category'] != 'resort' or row['name'] == 'The Village accommodation area' or
                    (row['src'].startswith('/static/uploads/') and row['src'] not in library.values())]
            rows += gallery
        return [row for row in validate_media(rows) if (root / row['src'].lstrip('/')).is_file()]
    except (OSError, ValueError, TypeError, KeyError):
        return []


def featured_photo(resort, research):
    photos = [row for row in media_for(resort, research) if row['category'] == 'resort']
    preferred = FEATURED_CAPTIONS.get(resort.code)
    return next((row for row in photos if row['name'] == preferred), photos[0] if photos else None)


def room_details(resort, research, media):
    rooms = mauricia_rooms() if resort.code == 'MAU' else research.get('rooms', []) if research else []
    library, _ = admin_gallery(resort)
    def label(photo):
        return (photo.get('room') or photo['name']).casefold()
    def match(photo):
        name = label(photo)
        return next((room for room in rooms if room['name'].casefold() == name), None)
    photos = [photo for photo in media if photo['category'] == 'room']
    details = []
    for index, photo in enumerate(photos):
        facts = match(photo)
        matching = [item for item in photos if label(item) == label(photo)]
        if facts and facts.get('photos'):
            root = Path(__file__).resolve().parent.parent
            extras = [admin_photo(item, library) for item in facts['photos']]
            matching += [item for item in extras if item['src'] not in {row['src'] for row in matching}
                         and (root / item['src'].lstrip('/')).is_file()]
        plans = [item for item in media if item['category'] == 'plan' and label(item) == label(photo)]
        details.append(dict(id=index, name=photo.get('room') or photo['name'], facts=facts,
                            photos=matching, plans=plans))
    return details
