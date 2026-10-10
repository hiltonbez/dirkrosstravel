"""Local interactive setup. Secrets are entered privately, never in chat."""
import getpass
import secrets
from pathlib import Path

from dotenv import dotenv_values, set_key
from sqlalchemy import URL, create_engine, text

ROOT = Path(__file__).resolve().parent


def main():
    env = ROOT / '.env'
    saved = dotenv_values(env) if env.exists() else {}
    print('Configure your local PostgreSQL database. No database is deleted or recreated.')
    host = input('Database host [localhost]: ').strip() or 'localhost'
    port = input('Database port [5432]: ').strip() or '5432'
    database = input('Database name [mauritius_holidays]: ').strip() or 'mauritius_holidays'
    username = input('Database user [postgres]: ').strip() or 'postgres'
    password = getpass.getpass('PostgreSQL password (hidden): ')
    try:
        url = URL.create('postgresql+psycopg', username=username, password=password, host=host, port=int(port), database=database)
        engine = create_engine(url, connect_args={'connect_timeout': 10})
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        engine.dispose()
    except Exception:
        print('Connection failed. Check the database name, password, port, and PostgreSQL service. Settings were not changed.')
        return 1
    values = {'DATABASE_URL': url.render_as_string(hide_password=False),
              'SECRET_KEY': saved.get('SECRET_KEY') or secrets.token_hex(32)}
    if input('Configure Beachcomber live quotes now? [y/N]: ').strip().lower() == 'y':
        for key, label in [('BEACHCOMBER_API_KEY', 'Beachcomber API key'), ('BEACHCOMBER_USERNAME', 'Beachcomber agent username'),
                           ('BEACHCOMBER_PASSWORD', 'Beachcomber agent password')]:
            values[key] = getpass.getpass(label + ' (hidden; blank keeps existing): ') or saved.get(key, '')
    for key, value in values.items():
        set_key(str(env), key, value)
    print('Connection verified. Settings saved privately in .env.')
    print('Next: .\\.venv\\Scripts\\python.exe -m flask --app app init-db')
    print('Then: .\\.venv\\Scripts\\python.exe -m flask --app app create-admin')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
