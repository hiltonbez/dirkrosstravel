import re
import uuid
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from PIL import Image, UnidentifiedImageError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from . import ROOT, limiter
from .beachcomber import HOTEL_CODES, SupplierError
from .models import Enquiry, Package, Page, Quote, Resort, Setting, User, db
from .about_content import ABOUT_SECTIONS
from .sync import sync_catalogue
from .planning import TAG_OPTIONS
from .reviews import load_reviews, save_reviews
from .resort_research import research_for, save_research, TEXT_FIELDS, ROW_FIELDS
from .resort_media import media_for, MEDIA_FIELDS, CATEGORIES as MEDIA_CATEGORIES

admin = Blueprint('admin', __name__, url_prefix='/admin')
CATEGORIES = ('Family', 'Honeymoon', 'All-Inclusive', 'Golf', 'Luxury')
MODELS = {'resorts': Resort, 'packages': Package, 'pages': Page}


@admin.route('/resort-research/<int:item_id>', methods=['GET', 'POST'])
@login_required
def resort_research(item_id):
    resort = db.get_or_404(Resort, item_id)
    values = research_for(resort) or {**{key: '' for key, _ in TEXT_FIELDS}, 'rooms': [], 'dining': [], 'image_verified': False}
    values.setdefault('media', media_for(resort, values))
    if request.method == 'POST':
        values = {**values, **{key: request.form.get(key, '').strip() for key, _ in TEXT_FIELDS}}
        values['image_verified'] = request.form.get('image_verified') == 'on'
        try:
            for collection, fields in ROW_FIELDS.items():
                count = int(request.form.get(collection + '_count', '0'))
                if not 0 <= count <= 20:
                    raise ValueError('Use at most 20 entries per section.')
                values[collection] = []
                for index in range(count):
                    row = {key: request.form.get(f'{collection}_{index}_{key}', '').strip() for key, _ in fields}
                    if any(row.values()):
                        values[collection].append(row)
            if 'media_count' in request.form:
                count = int(request.form['media_count'])
                if not 0 <= count <= 60:
                    raise ValueError('Use at most 60 media entries.')
                existing = {row['src']: row for row in values['media']}
                values['media'] = []
                for index in range(count):
                    row = {key: request.form.get(f'media_{index}_{key}', '').strip() for key, _ in MEDIA_FIELDS}
                    if any(value for key, value in row.items() if key != 'category'):
                        row['rotation'] = existing.get(row['src'], {}).get('rotation', 0)
                        values['media'].append(row)
            save_research(resort, values)
            flash('Resort research saved.', 'success')
            return redirect(url_for('admin.resort_research', item_id=resort.id), code=303)
        except ValueError as exc:
            flash(str(exc), 'error')
    return render_template('admin/resort_research.html', resort=resort, values=values, fields=TEXT_FIELDS, row_fields=ROW_FIELDS,
                           media_fields=MEDIA_FIELDS, media_categories=MEDIA_CATEGORIES)


@admin.route('/reviews', methods=['GET', 'POST'])
@login_required
def reviews():
    values = load_reviews()
    if request.method == 'POST':
        values = {key: request.form.get(key, '').strip() for key in ('google_url', 'rating', 'count', 'checked')}
        values['items'] = []
        for index in range(5):
            item = {key: request.form.get(f'{index}_{key}', '').strip()
                    for key in ('name', 'quote', 'theme', 'context', 'url')}
            item['published'] = request.form.get(f'{index}_published') == 'on'
            item['source'] = request.form.get(f'{index}_source', 'Website testimonial')
            values['items'].append(item)
        try:
            save_reviews(values)
            flash('Testimonials saved.', 'success')
            return redirect(url_for('admin.reviews'), code=303)
        except ValueError as exc:
            flash(str(exc), 'error')
    return render_template('admin/reviews.html', values=values)


FIELDS = {
    'resorts': [('code', 'Supplier hotel code', 'code'), ('name', 'Resort name', 'text'), ('slug', 'Page address', 'slug'),
                ('location', 'Location', 'text'), ('category', 'Holiday category', 'category'),
                ('description', 'Description', 'textarea'), ('image_url', 'Photo URL or uploaded path', 'url'),
                ('planning_tags', 'Planning interests', 'tags'),
                ('planning_source', 'Planning facts source (HTTPS)', 'optional_url'),
                ('planning_reviewed', 'Facts checked on', 'date'),
                ('consideration', 'What to check before booking', 'textarea'),
                ('advisor_notes', "Dirk's Take (publish only your approved advice)", 'textarea'),
                ('unavailable_from', 'Closure starts (optional)', 'date'),
                ('unavailable_to', 'Closure ends (optional)', 'date'),
                ('published', 'Published', 'checkbox'), ('featured', 'Featured', 'checkbox')],
    'packages': [('resort_id', 'Resort', 'resort'), ('title', 'Package title', 'text'), ('category', 'Holiday category', 'category'),
                 ('nights', 'Number of nights', 'number'), ('description', 'Description', 'textarea'),
                 ('meal_plan', 'Meal plan', 'text'), ('inclusions', 'Inclusions (one per line)', 'textarea'),
                 ('published', 'Published', 'checkbox'), ('featured', 'Featured', 'checkbox')],
    'pages': [('slug', 'Page address', 'slug'), ('title', 'Page title', 'text'), ('body', 'Page text', 'textarea'),
              ('published', 'Published', 'checkbox')],
}


def valid_image_url(value):
    if value.startswith('/static/') and not any(char in value for char in ('\\', '..', '\n', '\r')):
        return True
    parsed = urlsplit(value)
    return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password


@admin.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute; 50 per hour')
def login_view():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none()
        if user and user.check_password(request.form.get('password', '')):
            login_user(user)
            session.permanent = True
            return redirect(url_for('admin.dashboard'))
        flash('The email address or password is incorrect.', 'error')
    return render_template('admin/login.html')


@admin.post('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('admin.login_view'))


@admin.get('/')
@login_required
def dashboard():
    counts = {name: db.session.scalar(db.select(db.func.count()).select_from(model)) for name, model in MODELS.items()}
    counts['enquiries'] = db.session.scalar(db.select(db.func.count()).select_from(Enquiry))
    recent = db.session.execute(db.select(Enquiry).order_by(Enquiry.created.desc()).limit(5)).scalars().all()
    return render_template('admin/dashboard.html', counts=counts, enquiries=recent)


@admin.get('/content/<kind>')
@login_required
def content(kind):
    if kind not in MODELS:
        abort(404)
    items = db.session.execute(db.select(MODELS[kind]).order_by(MODELS[kind].id)).scalars().all()
    return render_template('admin/content.html', kind=kind, items=items)


@admin.route('/content/<kind>/new', methods=['GET', 'POST'], defaults={'item_id': None})
@admin.route('/content/<kind>/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(kind, item_id):
    if kind not in MODELS:
        abort(404)
    item = db.get_or_404(MODELS[kind], item_id) if item_id else MODELS[kind]()
    if request.method == 'POST':
        try:
            for key, label, field_type in FIELDS[kind]:
                value = request.form.get(key, '').strip()
                if field_type == 'tags':
                    tags = list(dict.fromkeys(request.form.getlist(key)))
                    if any(tag not in TAG_OPTIONS for tag in tags) or ('adults-only' in tags and 'family' in tags):
                        raise ValueError('Choose valid interests; an adults-only property cannot be tagged for families.')
                    setattr(item, key, ','.join(tags))
                    continue
                if field_type == 'checkbox':
                    setattr(item, key, key in request.form)
                    continue
                if not value:
                    if key in ('description', 'inclusions', 'body', 'consideration', 'advisor_notes') or field_type in ('optional_url', 'date'):
                        setattr(item, key, '')
                        continue
                    raise ValueError(f'{label} is required.')
                if field_type == 'number':
                    value = int(value)
                    if not 1 <= value <= 60:
                        raise ValueError('Number of nights must be 1 to 60.')
                elif field_type == 'resort':
                    value = int(value)
                    if not db.session.get(Resort, value):
                        raise ValueError('Please choose an existing resort.')
                elif field_type == 'code':
                    value = value.upper()
                    if value not in HOTEL_CODES:
                        raise ValueError('Please use a documented Beachcomber hotel code.')
                elif field_type == 'slug' and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value):
                    raise ValueError('Page addresses use lowercase letters, numbers, and hyphens.')
                elif field_type == 'url' and not valid_image_url(value):
                    raise ValueError('Use an HTTPS photo address or a /static/ uploaded path.')
                elif field_type == 'optional_url':
                    parsed = urlsplit(value)
                    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                        raise ValueError('Use a public HTTPS source address.')
                elif field_type == 'date':
                    date.fromisoformat(value)
                    if key == 'planning_reviewed' and date.fromisoformat(value) > date.today():
                        raise ValueError('The facts checked date cannot be in the future.')
                elif field_type == 'category' and value not in CATEGORIES:
                    raise ValueError('Please select a holiday category.')
                column = MODELS[kind].__table__.columns[key]
                length = getattr(column.type, 'length', None)
                if isinstance(value, str) and len(value) > (length or 15000):
                    raise ValueError(f'{label} is too long.')
                setattr(item, key, value)
            if kind == 'resorts':
                if bool(item.unavailable_from) != bool(item.unavailable_to) or (item.unavailable_from and item.unavailable_to < item.unavailable_from):
                    raise ValueError('Enter both closure dates, with the end on or after the start.')
                if item.planning_tags and not (item.planning_source and item.planning_reviewed):
                    raise ValueError('Planning interests require a source and a facts checked date.')
            db.session.add(item)
            db.session.commit()
            flash('Content saved.', 'success')
            return redirect(url_for('admin.content', kind=kind))
        except (ValueError, IntegrityError) as exc:
            db.session.rollback()
            flash('That supplier code or page address already exists.' if isinstance(exc, IntegrityError) else str(exc), 'error')
    return render_template('admin/edit.html', kind=kind, item=item, fields=FIELDS[kind], categories=CATEGORIES,
                           resorts=db.session.execute(db.select(Resort).order_by(Resort.name)).scalars().all(), tag_options=TAG_OPTIONS)


@admin.post('/content/<kind>/<int:item_id>/delete')
@login_required
def delete(kind, item_id):
    if kind not in MODELS:
        abort(404)
    item = db.get_or_404(MODELS[kind], item_id)
    if kind == 'resorts' and item.packages:
        flash('Remove this resort\'s packages first, or unpublish the resort to hide it.', 'error')
    else:
        db.session.delete(item)
        db.session.commit()
        flash('Content removed.', 'success')
    return redirect(url_for('admin.content', kind=kind))


@admin.route('/enquiries', methods=['GET', 'POST'])
@login_required
def enquiries():
    if request.method == 'POST':
        try:
            item_id = int(request.form.get('id', ''))
        except ValueError:
            abort(400)
        item = db.get_or_404(Enquiry, item_id)
        status = request.form.get('status')
        if status not in ('New', 'In progress', 'Closed'):
            abort(400)
        item.status = status
        db.session.commit()
        return redirect(url_for('admin.enquiries'))
    return render_template('admin/enquiries.html', enquiries=db.session.execute(db.select(Enquiry).order_by(Enquiry.created.desc())).scalars().all())


@admin.get('/enquiries/<int:item_id>/quote')
@login_required
def enquiry_quote(item_id):
    enquiry = db.get_or_404(Enquiry, item_id)
    quote = db.session.get(Quote, enquiry.quote_id) if enquiry.quote_id else None
    response = current_app.make_response(render_template('admin/enquiry_quote.html', enquiry=enquiry,
                                                        quote=quote, result=quote.result if quote else {}))
    response.headers['Cache-Control'] = 'no-store'
    return response


@admin.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    fields = [('brand_name', 'Site name'), ('hero_title', 'Homepage heading'), ('hero_subtitle', 'Homepage supporting text'),
              ('about_text', 'Introduction'), ('contact_email', 'Contact email'), ('contact_phone', 'Contact phone'),
              ('whatsapp_number', 'WhatsApp number (international digits, no +)'),
              ('advisor_name', 'Advisor name'), ('advisor_roles', 'Advisor professional titles'),
              ('advisor_summary', 'About page introduction'), ('advisor_experience', 'Travel experience'),
              ('advisor_street', 'Business street address'), ('advisor_city', 'Business city'),
              ('advisor_postcode', 'Business postal code'), ('advisor_country', 'Business country'),
              ('advisor_service_area', 'Areas served'), ('contact_phone_international', 'Phone in international format'),
              ('about_meta_description', 'About page search description'),
              ('about_benefits', 'About: advisor benefits (Markdown)'),
              ('about_mauritius', 'About: Mauritius specialty (Markdown)'),
              ('about_expertise', 'About: holiday ideas (Markdown)'),
              ('about_process', 'About: planning journey (Markdown)'),
              ('about_travel', 'About: travel photographs introduction (Markdown)'),
              ('about_final', 'About: final invitation (Markdown)')]
    if request.method == 'POST':
        values = {key: request.form.get(key, '').strip() for key, _ in fields}
        if (not values['brand_name'] or not values['hero_title'] or any(len(v) > (4000 if key in ABOUT_SECTIONS else 500) for key, v in values.items())
                or (values['whatsapp_number'] and not re.fullmatch(r'\d{8,15}', values['whatsapp_number']))
                or (values['contact_phone_international'] and not re.fullmatch(r'\+\d{8,15}', values['contact_phone_international']))
                or (values['contact_email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['contact_email']))):
            flash('Check your site name, heading, email, and WhatsApp number.', 'error')
        else:
            for key, value in values.items():
                setting = db.session.get(Setting, key) or Setting(key=key)
                setting.value = value
                db.session.add(setting)
            db.session.commit()
            flash('Settings saved.', 'success')
            return redirect(url_for('admin.settings'))
    return render_template('admin/settings.html', fields=fields)


@admin.route('/photos', methods=['GET', 'POST'])
@login_required
def photos():
    root = Path(current_app.config['UPLOAD_FOLDER'])
    root.mkdir(parents=True, exist_ok=True)
    folders = sorted(p.name for p in root.iterdir() if p.is_dir() and not p.is_symlink() and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', p.name))
    selected = request.args.get('folder', '')
    if selected and selected not in folders:
        abort(404)
    folder = root / selected if selected else root
    if request.method == 'POST':
        upload = request.files.get('photo')
        try:
            if not upload:
                raise ValueError('Please select a photograph.')
            image = Image.open(upload.stream)
            if image.format not in ('JPEG', 'PNG', 'WEBP'):
                raise ValueError('Use a JPEG, PNG, or WebP photograph.')
            image.load()
            image.thumbnail((2400, 2400))
            filename = uuid.uuid4().hex + '.jpg'
            image.convert('RGB').save(folder / filename, 'JPEG', quality=88)
            flash('Photo uploaded. Its path is shown below.', 'success')
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
            flash('Please choose a valid JPEG, PNG, or WebP photograph under 8 MB.', 'error')
        return redirect(url_for('admin.photos', folder=selected) if selected else url_for('admin.photos'))
    files = sorted((p for p in folder.iterdir() if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp')), key=lambda p: p.stat().st_mtime, reverse=True)
    images = [dict(name=p.name, filename=p.relative_to(root).as_posix()) for p in files]
    return render_template('admin/photos.html', images=images, folders=folders, selected_folder=selected)


@admin.post('/photos/<path:filename>/delete')
@login_required
def delete_photo(filename):
    if not re.fullmatch(r'(?:[a-z0-9]+(?:-[a-z0-9]+)*/)?[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)', filename):
        abort(404)
    root = Path(current_app.config['UPLOAD_FOLDER']).resolve()
    target = (root / filename).resolve()
    if not target.is_relative_to(root) or (root / filename).is_symlink():
        abort(404)
    path = '/static/uploads/' + filename
    if db.session.execute(db.select(Resort).where(Resort.image_url == path)).first():
        flash('This photo is used by a resort. Change the resort photo first.', 'error')
    else:
        target.unlink(missing_ok=True)
        flash('Photo removed.', 'success')
    selected = filename.split('/')[0] if '/' in filename else ''
    return redirect(url_for('admin.photos', folder=selected) if selected else url_for('admin.photos'))


@admin.post('/sync')
@login_required
@limiter.limit('3 per hour')
def sync():
    try:
        summary = sync_catalogue(current_app.extensions['beachcomber'])
        flash(summary, 'success')
    except (SupplierError, ValueError, TypeError, KeyError, SQLAlchemyError) as exc:
        db.session.rollback()
        current_app.logger.warning('Supplier refresh failed: %s', exc)
        flash('Supplier refresh failed. Existing content has been kept. Check credentials and try again.', 'error')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Unexpected supplier refresh failure')
        flash('Supplier refresh failed unexpectedly. Existing content has been kept.', 'error')
    return redirect(url_for('admin.dashboard'))
