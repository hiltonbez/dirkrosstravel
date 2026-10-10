"""Apply Dirk's supplied public biography to the configured database."""
from website import create_app
from website.models import Page, Setting, db
from website.profile import ABOUT_BODY, ABOUT_TITLE, PROFILE_SETTINGS


def main():
    app = create_app()
    with app.app_context():
        page = db.session.execute(db.select(Page).where(Page.slug == 'about')).scalar_one_or_none()
        if page is None:
            page = Page(slug='about', published=True)
            db.session.add(page)
        page.title, page.body = ABOUT_TITLE, ABOUT_BODY
        for key, value in PROFILE_SETTINGS.items():
            setting = db.session.get(Setting, key) or Setting(key=key)
            setting.value = value
            db.session.add(setting)
        db.session.commit()
        print('About page and supplied public contact details updated.')


if __name__ == '__main__':
    main()
