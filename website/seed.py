from .models import Page, Package, Resort, Setting, db
from .profile import ABOUT_BODY, ABOUT_TITLE, PROFILE_SETTINGS

RESORTS = [
    ('MAU', 'Mauricia Beachcomber', 'Grand Baie', 'Family', 'Stay close to Grand Baie and explore the island from its north coast.'),
    ('VIC', 'Victoria Beachcomber', 'Pointe aux Piments', 'Family', 'A west-coast base for days by the lagoon and time together.'),
    ('TAB', 'Trou aux Biches Beachcomber', 'Trou aux Biches', 'Honeymoon', 'Plan a beach escape on the northwest coast of Mauritius.'),
    ('DIN', 'Dinarobin Beachcomber', 'Le Morne', 'Luxury', 'Discover the Le Morne peninsula and plan your own island retreat.'),
    ('PAR', 'Paradis Beachcomber', 'Le Morne', 'Golf', 'Combine time by the beach with a holiday on the Le Morne peninsula.'),
    ('SHA', 'Shandrani Beachcomber', 'Blue Bay', 'All-Inclusive', 'Explore the southeast coast and choose the package that suits your stay.'),
    ('CAN', 'Canonnier Beachcomber', 'Pointe aux Canonniers', 'Family', 'Make the northern coast your base for a Mauritius holiday.'),
    ('RP', 'Royal Palm Beachcomber', 'Grand Baie', 'Luxury', 'Arrange a personal luxury escape on the north coast of Mauritius.'),
]


def seed():
    if db.session.get(Setting, 'starter_content_initialized'):
        return
    for index, (code, name, location, category, description) in enumerate(RESORTS):
        if not db.session.execute(db.select(Resort).where(Resort.code == code)).scalar_one_or_none():
            resort = Resort(code=code, name=name, slug=name.lower().replace(' ', '-'), location=location,
                            category=category, description=description, featured=index < 3,
                            image_url={'MAU':'/static/images/resort-1.jpg', 'VIC':'/static/images/resort-vic.jpg',
                                       'TAB':'/static/images/resort-3.jpg', 'DIN':'/static/images/resort-2.jpg'}.get(code, '/static/images/mauritius-hero.png'))
            db.session.add(resort)
            db.session.flush()
            db.session.add(Package(resort_id=resort.id, title=f'{name} escape', category=category, nights=7,
                                   description='Choose your travel dates for a quote tailored to your holiday.',
                                   featured=index < 3, published=True))
    settings = {'brand_name': 'Mauritius Holiday Packages', 'hero_title': 'Mauritius Holiday Packages',
                       'hero_subtitle': "Don't just search for a Mauritius holiday. Find the Mauritius holiday that's right for you.",
                       'about_text': 'Plan your Mauritius holiday with Dirk Ross, Flight Centre Independent.',
                       'contact_email': '', 'contact_phone': '', 'whatsapp_number': ''}
    from .about_content import ABOUT_SECTIONS, ABOUT_STORY
    settings.update(PROFILE_SETTINGS)
    settings.update(ABOUT_SECTIONS)
    for key, value in settings.items():
        if not db.session.get(Setting, key):
            db.session.add(Setting(key=key, value=value))
    if not db.session.execute(db.select(Page).where(Page.slug == 'about')).scalar_one_or_none():
        db.session.add(Page(slug='about', title=ABOUT_TITLE, published=True, body=ABOUT_STORY))
    db.session.add(Setting(key='starter_content_initialized', value='yes'))
    db.session.commit()
