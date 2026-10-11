from unittest.mock import Mock

import pytest
import requests

from website.api_monitor import ENV_NAMES, configuration, probe
from website.beachcomber import BeachcomberClient, SupplierError


@pytest.mark.parametrize('error,code', [
    (requests.exceptions.SSLError('SECRET'), 'tls_error'),
    (requests.ConnectTimeout('SECRET'), 'connect_timeout'),
    (requests.ReadTimeout('SECRET'), 'read_timeout'),
    (requests.ConnectionError('SECRET'), 'connection_error')])
def test_transport_diagnostics_are_redacted(error, code, caplog):
    transport = Mock()
    transport.post.side_effect = error
    with pytest.raises(SupplierError) as caught:
        BeachcomberClient('PRIVATE-KEY', 'PRIVATE-USER', 'PRIVATE-PASSWORD', transport).post('/getToken')
    assert caught.value.code == code
    assert caught.value.trace_id
    assert code in caplog.text
    assert 'SECRET' not in caplog.text and 'PRIVATE' not in caplog.text


@pytest.mark.parametrize('status,code', [(401, 'authentication_rejected'), (403, 'authentication_rejected'),
                                      (429, 'rate_limited'), (503, 'http_error')])
def test_http_failure_classification(status, code, caplog):
    transport = Mock()
    transport.post.return_value = Mock(ok=False, status_code=status)
    with pytest.raises(SupplierError) as caught:
        BeachcomberClient('SECRET', transport=transport).post('/getQuote', {'requestToken': 'TOKEN'})
    assert caught.value.code == code and caught.value.status == status
    assert 'SECRET' not in caplog.text and 'TOKEN' not in caplog.text


def test_monitor_missing_config_does_not_call_supplier(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    client = Mock()
    report = probe(client, True)
    assert not report['ok'] and set(configuration().values()) == {'missing'}
    client.token.assert_not_called()
    client.quote.assert_not_called()


def test_monitor_synthetic_quote_and_redaction(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.setenv(name, 'PRIVATE')
    monkeypatch.setattr('website.api_monitor.socket.getaddrinfo', Mock(return_value=[]))
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    monkeypatch.setattr('website.api_monitor.socket.create_connection', Mock(return_value=connection))
    context = Mock()
    context.wrap_socket.return_value = connection
    monkeypatch.setattr('website.api_monitor.ssl.create_default_context', Mock(return_value=context))
    client = Mock()
    client.token.return_value = 'PRIVATE-TOKEN'
    client.quote.return_value = {'quoteRef': 'PRIVATE-REF', 'roomOptions': []}
    report = probe(client, True)
    assert report['ok'] and report['checks'][-1]['outcome'] == 'no_room_options'
    assert 'PRIVATE' not in str(report)
    payload = client.quote.call_args.args[0]
    assert payload['nbrAdults'] == '2' and payload['departureCity'] == 'JOHANNESBURG'


def test_monitor_dns_failure(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.setenv(name, 'PRIVATE')
    monkeypatch.setattr('website.api_monitor.socket.getaddrinfo', Mock(side_effect=OSError('PRIVATE')))
    report = probe(Mock())
    assert not report['ok'] and report['checks'][-1]['outcome'] == 'dns_error'
    assert 'PRIVATE' not in str(report)
