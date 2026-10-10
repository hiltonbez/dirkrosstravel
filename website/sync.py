from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from .beachcomber import SupplierError
from .models import Package, Resort, Setting, db


def match_resort(hotel_name, resorts):
    name = str(hotel_name).lower()
    return next((r for r in resorts if name.startswith(r.name.lower().split(' beachcomber')[0])), None)


def sync_catalogue(client):
    if not client.key:
        raise SupplierError('Configure your Beachcomber API key first.')
    timestamp = client.post('/getLastRatesUpdate')
    if not isinstance(timestamp, dict) or not timestamp.get('lastRatesUpdate'):
        raise ValueError('Unexpected supplier rates timestamp.')
    products = client.post('/getProducts')
    previous = db.session.get(Setting, 'last_rates_update')
    rates = None
    if not previous or previous.value != timestamp.get('lastRatesUpdate'):
        rates = client.post('/getRates')
    if not isinstance(products, list) or not isinstance(timestamp, dict) or not timestamp.get('lastRatesUpdate'):
        raise ValueError('Unexpected supplier catalogue response.')
    if rates is not None and (not isinstance(rates, dict) or not isinstance(rates.get('beachcomberRates'), list)):
        raise ValueError('Unexpected supplier rates response.')
    resorts = db.session.execute(db.select(Resort)).scalars().all()
    for product in products:
        resort = match_resort(product.get('hotelName', ''), resorts)
        if resort:
            resort.supplier_content = product
    count = 0
    if rates is not None:
        seen = set()
        for rate in rates['beachcomberRates']:
            identity = rate.get('identity')
            resort = match_resort(rate.get('hotelName', ''), resorts)
            if not identity or not resort or rate.get('country', '').lower() != 'mauritius':
                continue
            seen.add(identity)
            package = db.session.execute(db.select(Package).where(Package.supplier_identity == identity)).scalar_one_or_none()
            if not package:
                package = Package(resort_id=resort.id, title=str(rate.get('bcReference') or resort.name)[:180],
                                  category=resort.category, nights=max(1, min(60, int(rate.get('numberOfNights') or 7))),
                                  description='Supplier special. Select dates to check current availability.',
                                  supplier_identity=identity, published=False)
                db.session.add(package)
            package.supplier_rate = rate
            package.supplier_updated = datetime.now(timezone.utc)
            count += 1
        # Keep editor-owned publication choices, but invalidate offers removed upstream.
        for package in db.session.execute(db.select(Package).where(Package.supplier_identity.is_not(None))).scalars():
            if package.supplier_identity not in seen:
                package.supplier_rate = None
        setting = previous or Setting(key='last_rates_update')
        setting.value = str(rates.get('lastRatesUpdate') or timestamp['lastRatesUpdate'])
        db.session.add(setting)
    else:
        for package in db.session.execute(db.select(Package).where(Package.supplier_rate.is_not(None))).scalars():
            package.supplier_updated = datetime.now(timezone.utc)
    checked = db.session.get(Setting, 'supplier_checked') or Setting(key='supplier_checked')
    checked.value = datetime.now(timezone.utc).isoformat()
    db.session.add(checked)
    db.session.commit()
    return f'Resort content refreshed. {count} specials refreshed; new specials are drafts for your review.'


def current_rate_price(package):
    rate = package.supplier_rate
    if not rate or not package.supplier_updated:
        return None
    updated = package.supplier_updated
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - updated).total_seconds() > 48 * 3600:
        return None
    today = date.today()
    try:
        if not date.fromisoformat(rate['bookingFromDate'][:10]) <= today <= date.fromisoformat(rate['bookingToDate'][:10]):
            return None
        if date.fromisoformat(rate['travelToDate'][:10]) < today:
            return None
        prices = [Decimal(str(option['pricePerPersonZARFrom'])) for option in rate.get('packages', [])]
        prices = [price for price in prices if price.is_finite() and price > 0]
        return min(prices) if prices else None
    except (ValueError, TypeError, KeyError, InvalidOperation):
        return None
