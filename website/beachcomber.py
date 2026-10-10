import threading
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

HOTEL_CODES = {'PAR', 'DIN', 'TAB', 'RP', 'SHA', 'VIC', 'CAN', 'MAU'}
CITIES = ('JOHANNESBURG', 'CAPE TOWN', 'DURBAN', 'PORT ELIZABETH', 'EAST LONDON', 'BLOEMFONTEIN')


class SupplierError(Exception):
    pass


class BeachcomberClient:
    BASE_URL = 'https://api.beachcomberonline.co.za'

    def __init__(self, key='', username='', password='', transport=None):
        self.key, self.username, self.password = key, username, password
        self.transport = transport or requests.Session()
        self._token = None
        self._token_until = 0
        self._lock = threading.Lock()

    @property
    def configured(self):
        return bool(self.key and self.username and self.password)

    def post(self, path, payload=None, auth=None):
        if not self.key:
            raise SupplierError('Live pricing is not connected yet. Please send Dirk an enquiry.')
        try:
            response = self.transport.post(
                self.BASE_URL + path, json=payload if payload is not None else {},
                headers={'BeachcomberKey': self.key, 'Content-Type': 'application/json'},
                auth=auth, timeout=(10, 70),
            )
        except requests.RequestException as exc:
            # Do not expose credentials, tokens, raw payloads, or TLS internals to visitors.
            raise SupplierError('Beachcomber could not be reached. Please try again or send an enquiry.') from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise SupplierError('Beachcomber returned an unreadable response. Please try again.') from exc
        if not response.ok or (isinstance(data, dict) and data.get('errorMsg')):
            raise SupplierError('Beachcomber could not complete this search. Please adjust your dates or contact Dirk.')
        return data

    def token(self):
        if not self.configured:
            raise SupplierError('Live pricing is not connected yet. Please send Dirk an enquiry.')
        with self._lock:
            if self._token and time.monotonic() < self._token_until:
                return self._token
            result = self.post('/getToken', auth=(self.username, self.password))
            if not isinstance(result, dict) or not result.get('userToken'):
                raise SupplierError('Agent authentication did not return a valid token.')
            expires = result.get('expires')
            try:
                expiry = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=ZoneInfo('Africa/Johannesburg'))
                seconds = (expiry - datetime.now(expiry.tzinfo)).total_seconds()
            except (ValueError, TypeError, AttributeError):
                raise SupplierError('Agent authentication returned an invalid expiry.')
            if seconds <= 60:
                raise SupplierError('Agent authentication returned an expired token.')
            self._token, self._token_until = result['userToken'], time.monotonic() + min(seconds - 60, 43140)
            return self._token

    def quote(self, data):
        payload = build_quote_payload(data)
        payload['requestToken'] = self.token()
        result = self.post('/getQuote', payload)
        if not isinstance(result, dict) or not result.get('quoteRef') or not isinstance(result.get('roomOptions', []), list):
            raise SupplierError('Beachcomber returned an incomplete quote. Please try again.')
        for room in result.get('roomOptions', []):
            if (not isinstance(room, dict) or not isinstance(room.get('packages', []), list)
                    or any(not isinstance(option, dict) for option in room.get('packages', []))):
                raise SupplierError('Beachcomber returned incomplete room information. Please try again.')
        if 'airGDS' in result and (not isinstance(result['airGDS'], list) or any(not isinstance(flight, dict) for flight in result['airGDS'])):
            raise SupplierError('Beachcomber returned incomplete flight information. Please try again.')
        # Whitelist presentation data; never return requestToken/userToken to the browser.
        allowed = ('quoteRef', 'hotelName', 'hotelDescription', 'hotelImages', 'travelFromDate',
                   'travelToDate', 'includeAir', 'departFrom', 'includeTransfers', 'transferType',
                   'roomOptions', 'airGDS', 'inclusions', 'exclusions', 'termsAndConditions')
        return {key: result[key] for key in allowed if key in result}


def integer(data, key, minimum, maximum):
    try:
        value = int(data.get(key, 0))
    except (TypeError, ValueError):
        raise ValueError(f'Please enter a valid {key}.')
    if not minimum <= value <= maximum:
        raise ValueError(f'{key} must be between {minimum} and {maximum}.')
    return value


def build_quote_payload(data, today=None):
    today = today or datetime.now(ZoneInfo('Africa/Johannesburg')).date()
    if data.get('hotelCode') not in HOTEL_CODES:
        raise ValueError('Please select a Beachcomber resort.')
    try:
        departure = date.fromisoformat(data.get('dateDeparture', ''))
        returning = date.fromisoformat(data.get('dateReturn', ''))
    except (TypeError, ValueError):
        raise ValueError('Please enter valid departure and return dates.')
    if departure < today + timedelta(days=10):
        raise ValueError('Departure must be at least 10 days from today.')
    if not 1 <= (returning - departure).days <= 60:
        raise ValueError('Your return date must be 1 to 60 days after departure.')
    if data.get('departureCity') not in CITIES:
        raise ValueError('Please select a departure city.')
    adults = integer(data, 'nbrAdults', 1, 6)
    children = integer(data, 'nbrChildren', 0, 4)
    infants = integer(data, 'nbrInfants', 0, 2)
    if infants > adults:
        raise ValueError('Each infant must travel with an adult.')
    cabin = data.get('flightCabin', 'Cheapest')
    airline = data.get('flightAdvanced', 'All Airlines')
    if cabin not in {'Cheapest', 'Economy', 'Business'} or airline not in {'All Airlines', 'MK Only', 'SAA Only'}:
        raise ValueError('Please select a valid airline and cabin.')
    payload = dict(hotelCode=data['hotelCode'], dateDeparture=f'{departure}T00:00:00',
                   dateReturn=f'{returning}T00:00:00', includeAir='true' if data.get('includeAir') in ('on', 'true', True) else 'false',
                   departureCity=data['departureCity'], flightAdvanced=airline, flightCabin=cabin,
                   nbrAdults=str(adults), nbrChildren=str(children), nbrInfants=str(infants), requestToken='',
                   weddingDate='', honeymoonRates='false', weddingRates='false', repeaterRates='false')
    for flag in ('honeymoonRates', 'weddingRates', 'repeaterRates'):
        payload[flag] = 'true' if data.get(flag) in ('on', 'true', True) else 'false'
    if payload['honeymoonRates'] == 'true' or payload['weddingRates'] == 'true':
        try:
            wedding = date.fromisoformat(data.get('weddingDate', ''))
        except (TypeError, ValueError):
            raise ValueError('Please enter your wedding date for this offer.')
        payload['weddingDate'] = f'{wedding}T00:00:00'
    for index in range(1, 5):
        payload[f'childAge{index}'] = str(integer(data, f'childAge{index}', 2, 17)) if index <= children else '0'
    for index in range(1, 3):
        key = f'infantDOB{index}'
        payload[key] = ''
        if index <= infants:
            try:
                dob = date.fromisoformat(data.get(key, ''))
            except (TypeError, ValueError):
                raise ValueError('Please enter a valid date of birth for each infant.')
            age = departure.year - dob.year - ((departure.month, departure.day) < (dob.month, dob.day))
            if dob > today or age not in (0, 1):
                raise ValueError('Infants must be under 2 on the departure date.')
            payload[key] = f'{dob}T00:00:00'
    return payload
