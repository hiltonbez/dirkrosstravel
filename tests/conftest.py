import pytest


@pytest.fixture(autouse=True)
def isolate_supplier_credentials(monkeypatch):
    # Empty values prevent dotenv from loading real supplier credentials in tests.
    for name in ('BEACHCOMBER_API_KEY', 'BEACHCOMBER_USERNAME', 'BEACHCOMBER_PASSWORD'):
        monkeypatch.setenv(name, '')
