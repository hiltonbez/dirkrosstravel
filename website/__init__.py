import os
import secrets
import math
from html import unescape
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import bleach
import markdown
import truststore
from dotenv import load_dotenv
from flask import Flask, g, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from markupsafe import Markup

from .beachcomber import BeachcomberClient
from .models import Page, Setting, User, db

truststore.inject_into_ssl()

ROOT = Path(__file__).resolve().parent.parent
limiter = Limiter(key_func=get_remote_address, default_limits=['300 per hour'], storage_uri='memory://')
login = LoginManager()
csrf = CSRFProtect()


def create_app(config=None):
    load_dotenv(ROOT / '.env')
    app = Flask(__name__, template_folder=str(ROOT / 'templates'), static_folder=str(ROOT / 'static'),
                instance_path=str(ROOT / 'instance'))
    Path(app.instance_path).mkdir(exist_ok=True)
    secret = os.getenv('SECRET_KEY')
    if not secret:
        secret_file = Path(app.instance_path) / 'secret-key'
        if not secret_file.exists():
            secret_file.write_text(secrets.token_hex(32), encoding='ascii')
        secret = secret_file.read_text(encoding='ascii').strip()
    database = os.getenv('DATABASE_URL') or 'sqlite:///' + str(ROOT / 'instance' / 'preview.db')
    app.config.update(SECRET_KEY=secret, SQLALCHEMY_DATABASE_URI=database, SQLALCHEMY_TRACK_MODIFICATIONS=False,
                      MAX_CONTENT_LENGTH=8 * 1024 * 1024, UPLOAD_FOLDER=str(ROOT / 'static' / 'uploads'),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8), WTF_CSRF_TIME_LIMIT=28800)
    if config:
        app.config.update(config)
    import logging
    logging.getLogger('website.beachcomber').setLevel(logging.INFO)
    app.logger.warning('Beachcomber configuration presence: %s', {
        name: bool(os.getenv(name, '').strip()) for name in
        ('BEACHCOMBER_API_KEY', 'BEACHCOMBER_USERNAME', 'BEACHCOMBER_PASSWORD')})
    from .seasonal_offers import SeasonalOffers
    app.extensions['seasonal_offers'] = SeasonalOffers()
    db.init_app(app)
    with app.app_context():
        db.create_all()
    Migrate(app, db)
    login.init_app(app)
    login.login_view = 'admin.login_view'
    csrf.init_app(app)
    limiter.init_app(app)
    app.extensions['beachcomber'] = BeachcomberClient(os.getenv('BEACHCOMBER_API_KEY', ''),
                                                     os.getenv('BEACHCOMBER_USERNAME', ''), os.getenv('BEACHCOMBER_PASSWORD', ''))
    from .views import public
    from .admin import admin
    from .commands import register_commands
    app.register_blueprint(public)
    app.register_blueprint(admin)
    register_commands(app)

    @login.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    @app.context_processor
    def common():
        from .sync import current_rate_price
        from .resort_media import featured_photo
        from .resort_research import research_for
        def resort_photo(resort):
            if not hasattr(g, 'resort_featured_photos'):
                g.resort_featured_photos = {}
            if resort.id not in g.resort_featured_photos:
                g.resort_featured_photos[resort.id] = featured_photo(resort, research_for(resort))
            return g.resort_featured_photos[resort.id]
        settings = {item.key: item.value for item in db.session.execute(db.select(Setting)).scalars()}
        all_pages = db.session.execute(db.select(Page).where(Page.published.is_(True)).order_by(Page.id)).scalars().all()
        pages = [page for page in all_pages if not page.slug.startswith('guide-')]
        return dict(site=settings, live_connected=app.extensions['beachcomber'].configured, rate_price=current_rate_price, resort_photo=resort_photo,
                    published_pages=pages, published_about=any(page.slug == 'about' for page in pages),
                    min_departure=(datetime.now(ZoneInfo('Africa/Johannesburg')).date() + timedelta(days=10)).isoformat(),
                    current_year=datetime.now().year,
                    demo_database=app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:'))

    @app.template_filter('plain')
    def plain(value):
        return unescape(bleach.clean(str(value or ''), tags=[], strip=True))

    @app.template_filter('money')
    def money(value):
        try:
            amount = float(value)
            if not math.isfinite(amount) or amount < 0:
                return 'Price on enquiry'
            return 'R ' + f'{amount:,.0f}'.replace(',', ' ')
        except (ValueError, TypeError):
            return 'Price on enquiry'

    @app.template_filter('profile_markdown')
    def profile_markdown(value):
        html = markdown.markdown(str(value or ''))
        return Markup(bleach.clean(html, tags=['p', 'h2', 'h3', 'strong', 'em', 'ul', 'ol', 'li', 'a'],
                                  attributes={'a': ['href', 'title']}, protocols=['https', 'mailto', 'tel'], strip=True))

    @app.after_request
    def secure_response(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' https: data:; script-src 'self'; style-src 'self'; font-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"
        if '/admin' in request.path or '/quote' in request.path or request.path.startswith(('/resort-finder', '/contact', '/compare')):
            response.headers['Cache-Control'] = 'no-store'
        if '/admin' in request.path or '/quote' in request.path or request.path in ('/resort-finder/results', '/contact', '/enquiry-received') or (request.path == '/compare' and request.args):
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    for code in (400, 403, 404, 413, 429):
        app.register_error_handler(code, lambda error: (render_template('error.html', error=error), error.code))
    return app
