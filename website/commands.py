import re

import click
from flask_migrate import upgrade

from . import ROOT
from .models import User, db
from .seed import seed
from .sync import sync_catalogue


def register_commands(app):
    @app.cli.command('init-db')
    def init_db():
        """Apply migrations and add starter resort content (no invented prices)."""
        upgrade(directory=str(ROOT / 'migrations'))
        seed()
        from .hybrid_content import setup_hybrid
        setup_hybrid()
        click.echo('Database ready. Starter resorts added without placeholder prices.')

    @app.cli.command('setup-hybrid')
    def setup_hybrid_content():
        """Add Concept 5 content once without replacing editorial changes."""
        from .hybrid_content import setup_hybrid
        setup_hybrid()
        click.echo('Hybrid guides and sourced planning facts ready.')

    @app.cli.command('create-admin')
    @click.option('--email', prompt=True)
    @click.password_option()
    def create_admin(email, password):
        email = email.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 254:
            raise click.ClickException('Please use a valid email address.')
        if len(password) < 12:
            raise click.ClickException('Use an admin password of at least 12 characters.')
        if db.session.execute(db.select(User).where(User.email == email)).scalar_one_or_none():
            raise click.ClickException('An administrator with this email already exists.')
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo('Administrator created. Sign in at /admin/login.')

    @app.cli.command('sync-supplier')
    def sync_supplier():
        """Refresh supplier content and daily specials; new specials are drafts."""
        from flask import current_app
        click.echo(sync_catalogue(current_app.extensions['beachcomber']))

    @app.cli.command('purge-quotes')
    def purge_quotes():
        """Remove expired locally cached quotes."""
        from datetime import datetime, timezone
        from .models import Quote
        db.session.execute(db.delete(Quote).where(Quote.expires < datetime.now(timezone.utc)))
        db.session.commit()
        click.echo('Expired quotes removed.')
