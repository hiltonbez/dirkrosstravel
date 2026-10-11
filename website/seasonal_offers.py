"""Public, fixed-party quote summaries; never cache customer details or agent tokens."""
import math
import logging
import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .beachcomber import SupplierError

logger = logging.getLogger(__name__)

CALENDAR_SOURCE = 'https://www.gov.za/about-sa/school-calendar'
# Representative departures within the verified public-school breaks, not school-specific calendars.
DEPARTURES = (
    ('early-december-2026', 'December school holidays', '2026-12-12'),
    ('christmas-2026', 'Christmas holidays', '2026-12-19'),
    ('new-year-2026', 'New Year escape', '2026-12-26'),
    ('january-2027', 'January school holidays', '2027-01-02'),
    ('march-2027', 'March school holidays', '2027-03-20'),
    ('june-2027', 'June school holidays', '2027-06-26'),
    ('july-2027', 'July school holidays', '2027-07-03'),
    ('december-2027', 'December school holidays', '2027-12-11'),
    ('christmas-2027', 'Christmas holidays', '2027-12-18'),
    ('new-year-2027', 'New Year escape', '2027-12-25'),
)


def travel_dates(resort, today=None):
    today = today or datetime.now(ZoneInfo('Africa/Johannesburg')).date()
    rows = []
    for key, label, value in DEPARTURES:
        departure = date.fromisoformat(value)
        returning = departure + timedelta(days=7)
        if not today + timedelta(days=10) <= departure <= today + timedelta(days=365):
            continue
        if resort.unavailable_from and resort.unavailable_to:
            if departure < date.fromisoformat(resort.unavailable_to) and returning > date.fromisoformat(resort.unavailable_from):
                continue
        rows.append(dict(key=key, label=label, departure=value, returning=returning.isoformat(),
                         dates=f'{departure:%d %b %Y} - {returning:%d %b %Y}'))
    return rows


def search_values(code, offer):
    return dict(hotelCode=code, dateDeparture=offer['departure'], dateReturn=offer['returning'],
                departureCity='JOHANNESBURG', nbrAdults='2', nbrChildren='0', nbrInfants='0',
                includeAir='on', flightCabin='Cheapest', flightAdvanced='All Airlines')


def positive_price(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    return amount if math.isfinite(amount) and amount > 0 else None


def summarise(result, offer=None):
    if offer and (str(result.get('travelFromDate', ''))[:10] != offer['departure']
                  or str(result.get('travelToDate', ''))[:10] != offer['returning']):
        return dict(status='unavailable', message='The supplier returned different dates. Ask Dirk to check this holiday.')
    if result.get('includeAir') not in (True, 'true', 'True') or not result.get('airGDS'):
        return dict(status='unavailable', message='The supplier returned no flight-inclusive price for these dates. Ask Dirk to check them.')
    options = []
    for room in result.get('roomOptions', []):
        if str(room.get('numberOfNights')) != '7':
            continue
        status = str(room.get('roomStatus', 'Confirm with Dirk'))
        if any(word in status.lower() for word in ('unavailable', 'sold out', 'closed', 'not available')):
            continue
        for package in room.get('packages', []):
            total = positive_price(package.get('packagePriceZARFrom'))
            person = positive_price(package.get('pricePerPersonZARFrom'))
            if total is None or person is None or abs(total - person * 2) > 2:
                continue
            options.append(dict(total=total, person=person, room=str(room.get('accomProductName', 'Room option')),
                                meal=str(package.get('packageDesc', 'Confirm meal plan')), availability=status))
    if not options:
        return dict(status='unavailable', message='The supplier returned no suitable priced 7-night room. Ask Dirk to check alternatives.')
    transfers = result.get('includeTransfers')
    transfer_included = True if transfers in (True, 'true', 'True') else False if transfers in (False, 'false', 'False') else None
    carriers = sorted({str(flight['carrier']) for flight in result.get('airGDS', []) if flight.get('carrier')})
    return dict(status='priced', **min(options, key=lambda row: row['total']),
                carriers=carriers, transfers_included=transfer_included,
                transfer_type=str(result.get('transferType') or ''))


class SeasonalOffers:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def quote(self, client, code, offer):
        key = (code, offer['departure'])
        # Single-flight refresh avoids duplicate supplier calls for simultaneous visitors.
        with self._lock:
            now = time.monotonic()
            cached = self._cache.get(key)
            if cached and cached[0] > now:
                return dict(cached[1])
            try:
                result = summarise(client.quote(search_values(code, offer)), offer)
            except SupplierError as exc:
                logger.warning('Seasonal quote unavailable: code=%s status=%s trace_id=%s',
                               exc.code, exc.status, exc.trace_id)
                result = dict(status='unavailable', message='Live pricing is temporarily unavailable. Ask Dirk for a quote.')
            result['checked'] = datetime.now(ZoneInfo('Africa/Johannesburg')).strftime('%d %b %Y, %H:%M SAST')
            ttl = 1800 if result['status'] == 'priced' else 120
            result['expires'] = time.time() + ttl
            self._cache[key] = (time.monotonic() + ttl, result)
            return dict(result)
