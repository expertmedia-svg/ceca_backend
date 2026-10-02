from app.config import settings
from conftest import login

def test_cross_site_production_cookie_attributes(client,monkeypatch):
    monkeypatch.setattr(settings,'cookie_secure',True)
    monkeypatch.setattr(settings,'cookie_samesite','none')
    response=login(client)
    header=response.headers['set-cookie'].lower()
    assert 'samesite=none' in header and 'secure' in header and 'httponly' in header
