from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Resort(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(8), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    location = db.Column(db.String(120), default='Mauritius', nullable=False)
    category = db.Column(db.String(32), default='Luxury', nullable=False)
    description = db.Column(db.Text, default='', nullable=False)
    image_url = db.Column(db.String(1000), default='/static/images/mauritius-hero.png', nullable=False)
    published = db.Column(db.Boolean, default=True, nullable=False)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    supplier_content = db.Column(db.JSON, nullable=True)
    planning_tags = db.Column(db.String(250), default='', nullable=False)
    planning_source = db.Column(db.String(1000), default='', nullable=False)
    planning_reviewed = db.Column(db.String(10), default='', nullable=False)
    consideration = db.Column(db.Text, default='', nullable=False)
    advisor_notes = db.Column(db.Text, default='', nullable=False)
    unavailable_from = db.Column(db.String(10), default='', nullable=False)
    unavailable_to = db.Column(db.String(10), default='', nullable=False)


class Package(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resort_id = db.Column(db.Integer, db.ForeignKey('resort.id'), nullable=False)
    resort = db.relationship('Resort', backref=db.backref('packages', lazy=True))
    title = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(32), default='All-Inclusive', nullable=False)
    nights = db.Column(db.Integer, default=7, nullable=False)
    description = db.Column(db.Text, default='', nullable=False)
    meal_plan = db.Column(db.String(120), default='Choose your meal plan', nullable=False)
    inclusions = db.Column(db.Text, default='', nullable=False)
    published = db.Column(db.Boolean, default=False, nullable=False)
    featured = db.Column(db.Boolean, default=False, nullable=False)
    supplier_identity = db.Column(db.String(100), unique=True, nullable=True)
    supplier_rate = db.Column(db.JSON, nullable=True)
    supplier_updated = db.Column(db.DateTime(timezone=True), nullable=True)


class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    body = db.Column(db.Text, default='', nullable=False)
    published = db.Column(db.Boolean, default=False, nullable=False)


class Enquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(40), default='', nullable=False)
    resort = db.Column(db.String(180), default='', nullable=False)
    message = db.Column(db.Text, nullable=False)
    quote_id = db.Column(db.String(36), nullable=True)
    status = db.Column(db.String(24), default='New', nullable=False)
    created = db.Column(db.DateTime(timezone=True), default=now, nullable=False)


class Quote(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    owner = db.Column(db.String(64), nullable=False, index=True)
    request = db.Column(db.JSON, nullable=False)
    result = db.Column(db.JSON, nullable=False)
    created = db.Column(db.DateTime(timezone=True), default=now, nullable=False)
    expires = db.Column(db.DateTime(timezone=True), nullable=False)
    # Agent tokens deliberately stay server-side. This v1 does not make bookings.


class Setting(db.Model):
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, default='', nullable=False)
