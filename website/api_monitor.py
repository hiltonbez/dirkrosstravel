"""Private container diagnostic: python -m website.api_monitor [--quote]."""
import argparse
import json
import logging
import os
import socket
import ssl
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from . import ROOT
from .beachcomber import BeachcomberClient, SupplierError

ENV_NAMES = ('BEACHCOMBER_API_KEY', 'BEACHCOMBER_USERNAME', 'BEACHCOMBER_PASSWORD')
HOST = 'api.beachcomberonline.co.za'


def configuration():
    return {name: ('missing' if name not in os.environ else
                   'blank' if not os.environ[name].strip() else 'present') for name in ENV_NAMES}


def probe(client, check_quote=False):
    report = dict(timestamp=datetime.now(timezone.utc).isoformat(), configuration=configuration(), checks=[], ok=False)

    def record(stage, outcome, **details):
        report['checks'].append(dict(stage=stage, outcome=outcome, **details))

    if not all(value == 'present' for value in report['configuration'].values()):
        record('configuration', 'missing_configuration')
        return report
    try:
        socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        record('dns', 'ok')
    except OSError:
        record('dns', 'dns_error')
        return report
    try:
        with socket.create_connection((HOST, 443), timeout=10) as connection:
            with ssl.create_default_context().wrap_socket(connection, server_hostname=HOST):
                record('tls', 'ok')
    except ssl.SSLError:
        record('tls', 'tls_error')
        return report
    except OSError:
        record('tls', 'connection_error')
        return report
    stage = 'authentication'
    try:
        client.token()
        record(stage, 'ok')
        if check_quote:
            stage = 'quote'
            departure = datetime.now(ZoneInfo('Africa/Johannesburg')).date() + timedelta(days=30)
            result = client.quote(dict(hotelCode='MAU', departureCity='JOHANNESBURG',
                dateDeparture=departure.isoformat(), dateReturn=(departure + timedelta(days=7)).isoformat(),
                nbrAdults='2', nbrChildren='0', nbrInfants='0', includeAir='on'))
            rooms = result.get('roomOptions', [])
            record(stage, 'ok' if rooms else 'no_room_options', room_option_count=len(rooms))
    except SupplierError as exc:
        record(stage, exc.code, http_status=exc.status, trace_id=exc.trace_id)
        return report
    report['ok'] = True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quote', action='store_true', help='Also request a synthetic 7-night, 2-adult quote; no booking or local database write.')
    parser.add_argument('--checks', type=int, default=1, help='Number of checks, 1 to 100.')
    parser.add_argument('--interval', type=int, default=300, help='Seconds between checks, at least 60.')
    parser.add_argument('--runtime-only', action='store_true', help='Do not load the local .env file (recommended in Coolify).')
    args = parser.parse_args(argv)
    if not 1 <= args.checks <= 100 or args.interval < 60:
        parser.error('Use 1 to 100 checks and an interval of at least 60 seconds.')
    if not args.runtime_only:
        load_dotenv(ROOT / '.env')
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    failed = False
    for index in range(args.checks):
        # A fresh client tests authentication on every cycle rather than reusing a token.
        client = BeachcomberClient(*(os.getenv(name, '') for name in ENV_NAMES))
        report = probe(client, args.quote)
        print(json.dumps(report), flush=True)
        failed = failed or not report['ok']
        client.transport.close()
        if index + 1 < args.checks:
            time.sleep(args.interval)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
