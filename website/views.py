import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from xml.etree.ElementTree import Element, SubElement, tostring

from flask import Blueprint, Response, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from . import limiter
from .beachcomber import CITIES, SupplierError, build_quote_payload
from .models import Enquiry, Package, Page, Quote, Resort, db
from .planning import DEPARTURES, PRIORITIES, TRAVELLERS, brief_text, reviewed_tags, shortlist, validate_brief
from .hybrid_content import GUIDES

public = Blueprint('public', __name__)


def resorts_query():
    return db.select(Resort).where(Resort.published.is_(True)).order_by(Resort.featured.desc(), Resort.id)


@public.get('/')
@public.get('/previews/home-grey', endpoint='home_grey_preview')
def home():
    from .reviews import public_reviews
    resorts = db.session.execute(resorts_query()).scalars().all()
    collection = request.args.get('collection', '')
    query = db.select(Package).join(Resort).where(Package.published.is_(True), Resort.published.is_(True))
    if collection in ('Family', 'Honeymoon', 'Luxury'):
        query = query.where(Package.category == collection)
    else:
        collection = ''
    packages = db.session.execute(query.order_by(Package.featured.desc(), Package.id).limit(3)).scalars().all()
    preview = request.endpoint == 'public.home_grey_preview'
    response = current_app.make_response(render_template('home_grey_preview.html' if preview else 'home.html',
                           resorts=resorts, packages=packages, cities=CITIES, guides=guide_items()[:3], collection=collection,
                           reviews=public_reviews(), home_endpoint=request.endpoint))
    if preview:
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        response.headers['Cache-Control'] = 'no-store'
    return response


@public.get('/quote-search')
def quote_search():
    return render_template('search.html', resorts=db.session.execute(resorts_query()).scalars().all(), cities=CITIES, values={})


@public.get('/previews/home-start-options')
def home_start_options_preview():
    response = current_app.make_response(render_template('home_start_options.html'))
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['Cache-Control'] = 'no-store'
    return response


@public.get('/previews/mauricia-package')
def mauricia_package_preview():
    from .resort_research import research_for
    resort = db.session.execute(db.select(Resort).where(Resort.code == 'MAU', Resort.published.is_(True))).scalar_one_or_none()
    if not resort:
        abort(404)
    response = current_app.make_response(render_template('package_preview.html', resort=resort, research=research_for(resort)))
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['Cache-Control'] = 'no-store'
    return response


@public.get('/previews/mauricia-rooms')
def mauricia_rooms_preview():
    from .resort_research import research_for
    from .resort_media import media_for, room_details
    resort = db.session.execute(db.select(Resort).where(Resort.code == 'MAU', Resort.published.is_(True))).scalar_one_or_none()
    if not resort:
        abort(404)
    research = research_for(resort)
    media = media_for(resort, research)
    response = current_app.make_response(render_template('rooms_preview.html', resort=resort,
        photos=[photo for photo in media if photo['category'] == 'room'],
        plans=[photo for photo in media if photo['category'] == 'plan'], room_details=room_details(resort, research, media)))
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['Cache-Control'] = 'no-store'
    return response


def guide_items():
    pages = db.session.execute(db.select(Page).where(Page.published.is_(True), Page.slug.startswith('guide-')).order_by(Page.id)).scalars().all()
    metadata = {slug: (summary, image) for slug, _, summary, image, _ in GUIDES}
    return [dict(page=p, slug=p.slug[6:], summary=metadata.get(p.slug[6:], ('Practical Mauritius planning advice.', 'resort-1.jpg'))[0],
                 image=metadata.get(p.slug[6:], ('', 'resort-1.jpg'))[1]) for p in pages]


@public.get('/guides')
def guides():
    return render_template('guides.html', guides=guide_items())


@public.get('/guides/<slug>')
def guide_detail(slug):
    page = db.session.execute(db.select(Page).where(Page.slug == 'guide-' + slug, Page.published.is_(True))).scalar_one_or_none()
    if not page:
        abort(404)
    return render_template('guide.html', page=page, guides=[g for g in guide_items() if g['page'].id != page.id][:3])


@public.route('/resort-finder', methods=['GET', 'POST'])
@limiter.limit('20 per minute')
def resort_finder():
    values = request.form.to_dict() if request.method == 'POST' else session.get('planning_brief', {})
    if request.method == 'POST':
        values['priorities'] = request.form.getlist('priorities')
        try:
            session['planning_brief'] = validate_brief(request.form)
            session.pop('comparison_codes', None)
            return redirect(url_for('public.finder_results'), code=303)
        except ValueError as exc:
            flash(str(exc), 'error')
            return render_template('finder.html', values=values, priorities=PRIORITIES, travellers=TRAVELLERS, departures=DEPARTURES), 400
    return render_template('finder.html', values=values, priorities=PRIORITIES, travellers=TRAVELLERS, departures=DEPARTURES)


@public.get('/resort-finder/results')
def finder_results():
    brief = session.get('planning_brief')
    if not brief:
        return redirect(url_for('public.resort_finder'))
    matches = shortlist(db.session.execute(resorts_query()).scalars().all(), brief)
    return render_template('finder_results.html', matches=matches, brief=brief, priorities=PRIORITIES,
                           travellers=TRAVELLERS, summary=brief_text(brief, [m['resort'] for m in matches]))


def selected_resorts(codes):
    codes = list(dict.fromkeys(codes))
    if len(codes) > 3:
        abort(400, description='Choose up to three Beachcomber resorts.')
    items = db.session.execute(resorts_query()).scalars().all()
    lookup = {r.code: r for r in items}
    if any(code not in lookup for code in codes):
        abort(404)
    return [lookup[code] for code in codes]


@public.get('/compare')
def compare():
    from .resort_research import research_for
    selected = selected_resorts(request.args.getlist('resort'))
    return render_template('compare.html', resorts=db.session.execute(resorts_query()).scalars().all(),
                           selected=selected, priorities=PRIORITIES, tags=reviewed_tags,
                           research_by_code={r.code: research_for(r) for r in selected})


@public.post('/compare/enquire')
def compare_enquire():
    selected = selected_resorts(request.form.getlist('resort'))
    if not selected:
        abort(400, description='Choose at least one resort to discuss.')
    session['comparison_codes'] = [r.code for r in selected]
    return redirect(url_for('public.contact'), code=303)


@public.post('/planning/clear')
def clear_planning():
    session.pop('planning_brief', None)
    session.pop('comparison_codes', None)
    return redirect(url_for('public.resort_finder'), code=303)


@public.get('/packages')
def packages():
    query = db.select(Package).join(Resort).where(Package.published.is_(True), Resort.published.is_(True))
    category = request.args.get('category', '')
    search = request.args.get('q', '').strip()[:100]
    if category:
        query = query.where(Package.category == category)
    if search:
        query = query.where(Package.title.ilike('%' + search.replace('%', '').replace('_', '') + '%'))
    items = db.session.execute(query.order_by(Package.featured.desc(), Package.id)).scalars().all()
    return render_template('packages.html', packages=items, category=category, search=search)


@public.get('/resorts')
def resorts():
    return render_template('resorts.html', resorts=db.session.execute(resorts_query()).scalars().all())


@public.get('/resorts/<slug>')
def resort_detail(slug):
    resort = db.session.execute(db.select(Resort).where(Resort.slug == slug, Resort.published.is_(True))).scalar_one_or_none()
    if not resort:
        abort(404)
    from .resort_research import research_for, resort_faqs, similar_resorts, source_date
    from .resort_media import media_for, room_details, seasonal_photos
    from .seasonal_offers import travel_dates
    items = db.session.execute(resorts_query()).scalars().all()
    research = research_for(resort)
    packages = db.session.execute(db.select(Package).where(Package.resort_id == resort.id, Package.published.is_(True))
                                  .order_by(Package.featured.desc(), Package.id)).scalars().all()
    media = media_for(resort, research)
    offers = travel_dates(resort)
    return render_template('resort.html', resort=resort, resorts=items, cities=CITIES, research=research,
                           packages=packages, alternatives=similar_resorts(resort, items, research),
                           faqs=resort_faqs(research) if research else [], checked=source_date(research) if research else '',
                           media=media, room_details=room_details(resort, research, media), seasonal_offers=offers,
                           seasonal_photos=seasonal_photos(resort, media, len(offers)))


@public.post('/resorts/<slug>/seasonal-prices/<offer_key>')
@limiter.limit('30 per minute; 120 per hour')
def seasonal_price(slug, offer_key):
    from .seasonal_offers import travel_dates
    resort = db.session.execute(db.select(Resort).where(Resort.slug == slug, Resort.published.is_(True))).scalar_one_or_none()
    if not resort:
        abort(404)
    offer = next((row for row in travel_dates(resort) if row['key'] == offer_key), None)
    if not offer:
        abort(404)
    result = current_app.extensions['seasonal_offers'].quote(current_app.extensions['beachcomber'], resort.code, offer)
    response = jsonify(result)
    response.headers['Cache-Control'] = 'no-store'
    return response


@public.get('/packages/<int:item_id>')
def package_detail(item_id):
    package = db.get_or_404(Package, item_id)
    if not package.published or not package.resort.published:
        abort(404)
    return render_template('package.html', package=package, resort=package.resort,
                           resorts=db.session.execute(resorts_query()).scalars().all(), cities=CITIES)


@public.get('/pages/<slug>')
def page(slug):
    if slug.startswith('guide-'):
        return redirect(url_for('public.guide_detail', slug=slug[6:]), code=301)
    page = db.session.execute(db.select(Page).where(Page.slug == slug, Page.published.is_(True))).scalar_one_or_none()
    if not page:
        abort(404)
    from .about_content import ABOUT_SECTIONS
    from .reviews import public_reviews
    return render_template('about.html' if slug == 'about' else 'page.html', page=page,
                           about_defaults=ABOUT_SECTIONS, reviews=public_reviews() if slug == 'about' else None)


def quote_owner():
    if 'quote_owner' not in session:
        session['quote_owner'] = secrets.token_hex(24)
    return session['quote_owner']


@public.post('/quote')
@limiter.limit('6 per minute; 30 per hour')
def search_quote():
    data = request.form.to_dict()
    resort = db.session.execute(db.select(Resort).where(Resort.code == data.get('hotelCode'), Resort.published.is_(True))).scalar_one_or_none()
    try:
        if not resort:
            raise ValueError('Please select a published resort.')
        build_quote_payload(data)
    except ValueError as exc:
        flash(str(exc), 'error')
        return render_template('search.html', resorts=db.session.execute(resorts_query()).scalars().all(),
                               cities=CITIES, values=data), 400
    try:
        result = current_app.extensions['beachcomber'].quote(data)
    except SupplierError as exc:
        return render_template('quote_unavailable.html', message=str(exc), search=data, resort=resort), 503
    timestamp = datetime.now(timezone.utc)
    item = Quote(id=str(uuid.uuid4()), owner=quote_owner(), request={key: value for key, value in data.items() if key != 'csrf_token'},
                 result=result, expires=timestamp + timedelta(hours=1))
    db.session.add(item)
    db.session.commit()
    return redirect(url_for('public.quote_result', quote_id=item.id))


def owned_quote(quote_id):
    item = db.get_or_404(Quote, quote_id)
    if item.owner != session.get('quote_owner'):
        abort(404)
    expiry = item.expires.replace(tzinfo=timezone.utc) if item.expires.tzinfo is None else item.expires
    if expiry <= datetime.now(timezone.utc):
        abort(400, description='This quote has expired. Please search again for current prices.')
    return item


@public.get('/quotes/<quote_id>')
def quote_result(quote_id):
    quote = owned_quote(quote_id)
    return render_template('quote.html', quote=quote, result=quote.result)


@public.route('/contact', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def contact():
    values = request.form.to_dict() if request.method == 'POST' else request.args.to_dict()
    brief = session.get('planning_brief')
    compared = selected_resorts([code for code in session.get('comparison_codes', [])
                                if db.session.execute(db.select(Resort).where(Resort.code == code, Resort.published.is_(True))).scalar_one_or_none()])
    planning_summary = brief_text(brief, compared or [m['resort'] for m in shortlist(db.session.execute(resorts_query()).scalars().all(), brief)]) if brief else ('Resorts to discuss: ' + ', '.join(r.name for r in compared) if compared else '')
    if request.method == 'POST':
        name, email = values.get('name', '').strip(), values.get('email', '').strip()
        message = values.get('message', '').strip()
        quote_id = values.get('quote_id') or None
        if quote_id:
            owned_quote(quote_id)
        if not (2 <= len(name) <= 120 and len(email) <= 254 and re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email)
                and 10 <= len(message) <= 5000 and len(values.get('phone', '')) <= 40 and values.get('consent') == 'on'):
            flash('Please enter your name, a valid email, a message of 10 to 5000 characters, and consent to be contacted.', 'error')
            return render_template('contact.html', values=values, planning_summary=planning_summary), 400
        db.session.add(Enquiry(name=name, email=email, phone=values.get('phone', '').strip(),
                               resort=values.get('resort', '')[:180], message=message + ('\n\n' + planning_summary if planning_summary else ''), quote_id=quote_id))
        db.session.commit()
        session.pop('planning_brief', None)
        session.pop('comparison_codes', None)
        return redirect(url_for('public.enquiry_received'))
    return render_template('contact.html', values=values, planning_summary=planning_summary)


@public.get('/enquiry-received')
def enquiry_received():
    return render_template('received.html')


@public.get('/sitemap.xml')
def sitemap():
    root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    urls = [url_for('public.' + endpoint, _external=True) for endpoint in
            ('home', 'packages', 'resorts', 'resort_finder', 'compare', 'guides')]
    urls += [url_for('public.resort_detail', slug=r.slug, _external=True) for r in db.session.execute(resorts_query()).scalars()]
    urls += [url_for('public.package_detail', item_id=p.id, _external=True) for p in
             db.session.execute(db.select(Package).join(Resort).where(Package.published.is_(True), Resort.published.is_(True))).scalars()]
    for page in db.session.execute(db.select(Page).where(Page.published.is_(True))).scalars():
        urls.append(url_for('public.guide_detail', slug=page.slug[6:], _external=True) if page.slug.startswith('guide-')
                    else url_for('public.page', slug=page.slug, _external=True))
    for location in urls:
        SubElement(SubElement(root, 'url'), 'loc').text = location
    return Response(tostring(root, encoding='utf-8', xml_declaration=True), mimetype='application/xml')


@public.get('/robots.txt')
def robots():
    return Response('User-agent: *\nDisallow: /admin\nDisallow: /quotes/\nSitemap: ' + url_for('public.sitemap', _external=True) + '\n', mimetype='text/plain')


@public.get('/favicon.ico')
def favicon():
    return redirect(url_for('static', filename='images/dirk-ross-logo.jpg'), code=302)
