# Beachcomber API diagnostics on Coolify

The repository does not contain `.env`. In the application's Environment
Variables, set these as production **runtime** variables, not just build variables:

- `BEACHCOMBER_API_KEY`
- `BEACHCOMBER_USERNAME`
- `BEACHCOMBER_PASSWORD`
- `SECRET_KEY` (one stable, securely generated value shared by all workers)
- `DATABASE_URL` (the production database connection)

Use the exact names and enter the raw values privately in Coolify. Save and
redeploy. Preview deployments need their own appropriate runtime configuration.
Never put credentials in Git, Docker build arguments, browser code or chat.

## Run inside the running application container

Open Coolify's application terminal, not the host terminal or build container:

```sh
python -m website.api_monitor --runtime-only
```

This checks credential presence, DNS, TLS and agent authentication. It never prints
credential values, response bodies or authentication tokens. JSON reports go to
stdout; safe supplier request events go to stderr. Exit code 1 indicates failure.

To also test an actual synthetic quote (Mauricia, Johannesburg, 7 nights, 2 adults,
30 days ahead, flights requested):

```sh
python -m website.api_monitor --runtime-only --quote
```

This calls the supplier and may create a supplier quote reference; it does not
book anything or write to the local database. An empty room list is not a network
failure. Other dates may be needed to obtain a price.

For a finite monitoring run, checking every five minutes for one hour:

```sh
python -m website.api_monitor --runtime-only --checks 12 --interval 300
```

Keep this a private operator command, not a public health-check URL. Frequent
probes consume supplier requests. Do not enable verbose requests/HTTP debug logs.

## Interpret results

| Outcome | Check next |
| --- | --- |
| `missing_configuration` | Missing/blank runtime variables; redeploy after saving. |
| `dns_error` | Container DNS and outbound network access. |
| `tls_error` | CA certificates, system clock, outbound TLS inspection. Never disable verification. |
| `connection_error` / `connect_timeout` | Outbound port 443, firewall, supplier reachability. |
| `read_timeout` | Supplier latency; check worker and reverse-proxy timeouts. |
| `authentication_rejected` | Credentials or API permission; ask Beachcomber whether server IP allowlisting is required. |
| `rate_limited` | Reduce request frequency and check supplier limits. |
| `http_error` | Supplier HTTP status in the report; 5xx may be a supplier outage. |
| `invalid_json` | Supplier/proxy returned a non-JSON response. |
| `supplier_rejected` | Supplier returned an API error; contact supplier with UTC time and endpoint. |
| `invalid_token_response` / `invalid_token_expiry` / `expired_token` | Supplier authentication response and server time. |

Live application logs now include `beachcomber_api` events with endpoint, outcome,
HTTP status, elapsed time and a locally generated trace ID (not a supplier ID).
No customer payload or supplier error text is logged. HTTP `ok` means the response
transport succeeded; quote validation and availability can still fail afterwards.

If the monitor succeeds but the browser does not, inspect the browser request to
`/resorts/.../seasonal-prices/...` and Coolify runtime logs: 400 may indicate CSRF,
429 an application rate limit, and 502/504 a worker/proxy timeout. Maintain a stable
`SECRET_KEY` across workers and replicas. Do not share cookies, CSRF tokens or
customer details when reporting errors.

The Dockerfile uses a 180-second Gunicorn worker timeout to accommodate sequential
authentication and quote requests, each with a 10-second connection and 70-second
read timeout. Confirm the proxy timeout too. This is not proof that
a timeout caused the current incident, and a slow queue may still require tuning.
The image installs system CA certificates and timezone data. `.dockerignore`
excludes local credentials, databases and uploads from image builds; mount existing
uploads and private database storage separately.

Deploy these changes before running the new diagnostic. This command diagnoses
the supplier connection only, not the full browser, proxy or database workflow.
