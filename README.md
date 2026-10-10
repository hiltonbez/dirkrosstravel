# Mauritius Holiday Packages by Dirk Ross

A Flask website with PostgreSQL support, content administration, and a server-side Beachcomber live quote adapter. The homepage uses your Flight Centre Independent logo and red #d40922.

## First-time setup on your desktop

## GitHub checkout and private data

Git contains the application source and bundled static assets, not a complete
backup of the running website. The `.env` credentials, `instance/` database and
runtime files, and `static/uploads/` Admin Photos library are intentionally ignored.
Transfer those privately when moving the existing site, and preserve their paths.
Never upload client enquiries, stored quotes, database backups or API credentials
to the repository. A fresh checkout needs a new virtual environment and private
configuration before it can run. Imported resort images require the matching
Admin Photos folders to reproduce the current image selections.

## First-time setup commands

Open C:\dirkrosswebsite in Visual Studio Code. Open Terminal > New Terminal. Run each command separately and wait for it to finish.

1. Install all project dependencies in your existing environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

2. Connect the PostgreSQL database you created:

```powershell
.\.venv\Scripts\python.exe configure.py
```

Accept localhost, 5432, mauritius_holidays, and postgres unless you chose different settings. Enter your PostgreSQL password privately. The script verifies the connection before saving settings. It does not delete or recreate your database. Choose y to configure Beachcomber and enter the API key, agent username, and agent password privately. Leave this option for later if you are not ready.

3. Apply the database migration and add starter content:

```powershell
.\.venv\Scripts\python.exe -m flask --app app init-db
```

4. Create your administrator account:

```powershell
.\.venv\Scripts\python.exe -m flask --app app create-admin
```

Enter your email address and a password of at least 12 characters. There is no default admin password. Password input is hidden. Once created, use this account at /admin/login. To reset a forgotten password, contact your developer; this initial version has no password-reset email service.

5. Start the website:

```powershell
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1 --port 5000
```

Open http://localhost:5000. Admin: http://localhost:5000/admin/login. Keep the terminal running. Stop with Ctrl+C. If the preview server already occupies port 5000, use --port 5002 and open http://localhost:5002.

## Everyday use

On Dirk's computer, double-click **Start Website** on the desktop. It runs
`Start Website.ps1`, starts the local server on port 5002 in the background,
waits for the Packages page to respond, and opens it in your browser. Repeated
clicks reuse the running server. It never initialises or resets the database.
After restarting Windows, click the shortcut again; automatic startup is not enabled.
Startup errors are shown in a dialog, with logs under `instance/launcher`.
If another program occupies port 5002, the launcher reports the conflict without
stopping that program. The old `start.ps1` remains a separate setup command on port 5000.

Start the website with the last command above. Admin sections include Packages, Resorts, Pages, Photos, Enquiries, and Settings. Use Settings to add your real contact details and WhatsApp number. Upload JPEG, PNG, or WebP files under Photos and use the resulting /static/uploads/... path in a resort's photo field.

Publication controls determine which content visitors see. Hiding a resort hides its packages too. To remove a resort permanently, remove its packages first. New supplier offers are imported as drafts; review them before publishing. Deleted starter content is not recreated on restart.

Enquiries are saved to the database for review. The application does not automatically send email, make bookings, or collect payments. Visitors can enquire about a quoted room, and you can manage each enquiry's status. Only your authenticated admin account can read the inbox.

## Beachcomber integration

Source: your Beachcomber API - Direct Integration Guide, dated 20 April 2026, plus https://api.beachcomberonline.co.za/testbookingconsole.html.

The adapter implements POST /getToken, /getQuote, /getProducts, /getLastRatesUpdate, and /getRates. It uses BeachcomberKey on the server, Basic agent authentication only on /getToken, and the returned requestToken for each quote. Tokens are cached only until the supplier expiry. API keys and tokens are never placed in browser forms or cookies. TLS verification remains enabled; truststore uses your operating system's certificate roots.

The test console uses MK Only as the submitted airline value for the Air Mauritius Only label; the adapter follows that console value. Quote departure must be at least 10 days ahead. Child ages and infant dates of birth are required when applicable. Honeymoon/wedding offers require a wedding date.

Quote results show room statuses, meal plan prices, flights, inclusions, exclusions, and terms. They are not booking confirmations. The live quote reference is cached server-side for one hour and can only be viewed by its originating browser. /sendQuote and /createBooking are deliberately not exposed in this initial version, matching the live-quote-and-enquiry scope you selected. No supplier emails or bookings are sent during tests.

Refresh supplier content using the admin dashboard's Refresh supplier control, or run:

```powershell
.\.venv\Scripts\python.exe -m flask --app app sync-supplier
```

The lightweight timestamp endpoint avoids downloading unchanged rates. Local editing choices and publication status are preserved. New specials are drafts. Offers removed upstream, outside their booking window, or not verified within 48 hours display no from-price. Supplier prices are not manually editable. Schedule a daily sync only after live credentials are verified.

Remove expired cached quotes with:

```powershell
.\.venv\Scripts\python.exe -m flask --app app purge-quotes
```

## Preview and database notes

With DATABASE_URL blank, the app uses a separate SQLite preview file at instance/preview.db. This is for local review only. Configure PostgreSQL before using real customer data. Changing DATABASE_URL does not move preview content or enquiries into PostgreSQL. Each database must be initialised with init-db and have its own admin account.

All 57 automated tests passed using your installed Python 3.14 environment. Project dependencies are installed in .venv.

## Concept 5 hybrid update

The homepage now combines personal advice, packages, a Beachcomber resort finder, comparisons and six original planning guides. WhatsApp uses your confirmed 082 447 5370 business number. The existing supplier quote form remains at /quote-search and on resort/package detail pages.

For an existing database, run .\\.venv\\Scripts\\python.exe -m flask --app app init-db. This applies the additive resort planning migration and adds the hybrid content once. It preserves existing content and never restores deleted hybrid guides on later runs. DATABASE_URL still determines whether this applies to your preview SQLite database or PostgreSQL; no automatic data transfer is performed.

Edit resort interests, source URLs, facts-checked dates, booking cautions, closure dates and your approved personal advice under Admin > Resorts. Facts without a source checked in the last 180 days are excluded from finder matching. Supplier refresh does not overwrite these editor-owned fields. The initial planning facts are researched from Beachcomber's public resort pages, not invented first-hand recommendations. Dinarobin's announced 15 May-16 October 2027 closure is included.

Guides are ordinary editable Pages whose slug begins guide-. They appear at /guides/<slug-without-prefix> and can be unpublished or deleted. Their Markdown is sanitised. Review and personalise the starter guides before public launch; no expert-review claim or fabricated author history is attached.

Finder budget is a preference for Dirk, not a price filter. Results do not confirm rooms, flights or availability. Family results exclude properties tagged adults-only, and entered stays overlapping recorded closures are excluded. Other departures and complex room arrangements need manual advice. Unsourced priorities are not presented as confirmed matches.

Finder preferences are kept in the browser's signed session cookie, not a public URL. No passenger names or dates of birth are collected by the finder. The travel brief is appended server-side to a successful enquiry and cleared from the session afterward. Shareable comparison URLs contain only public resort codes, not quotes or personal details. The finder works without JavaScript as a single form.

Published content is listed in /sitemap.xml. Admin, private quote, contact and personalised-result responses have noindex protections. Final production-domain canonicals, crawling and search indexing must be tested after public hosting; localhost is not a public launch. No SEO or AI citation guarantees are made.

The About page includes your supplied biography, contact information, and profile markup. Edit its Markdown body under Pages, and its contact/profile fields and search description under Settings. ASATA and IATA connections are described through your Flight Centre affiliation. Fourways is an area served, not the business address. To apply the supplied profile to another existing database, run .\\.venv\\Scripts\\python.exe update_profile.py after reviewing its public profile values; this overwrites the About title/body and profile settings.

## Tests and limitations

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Automated tests cover protected admin routes, CSRF, draft publication, enquiry consent and escaping, quote validation, supplier error handling, token cache/header rules, owner-only quote access, expiry, photo rejection, supplier draft import, stale prices, and preservation of edits.

Live authenticated supplier calls and a real PostgreSQL connection still require your locally entered credentials. They are not claimed to have been tested. Browser tests use isolated sample quote data, not actual supplier prices.

The homepage hero at static/images/mauritius-hero.png was generated with the built-in imagegen tool. Prompt: "Bright clear daylight photograph of Mauritius beach lagoon at Le Morne. Calm vivid turquoise clear water foreground and lower left, pristine white sandy beach sweeping toward right, healthy tropical palms and restrained thatched beach parasols on right, dramatic green Le Morne mountain in upper middle distance. Authentic believable resort coastline, photographic realism, crisp natural textures, blue sky, warm inviting sunshine. No logos, text, or watermarks. Leave an uncluttered left area for a website headline. Illustrative travel imagery, not a documentary image of a specific hotel."

Starter resort photos for Mauricia, Victoria, Trou aux Biches, and Dinarobin were retrieved from Beachcomber's public images. Other starter resorts use the illustrative hero until you add approved photographs. Confirm supplier media usage permissions before public launch.

Before public deployment: add your approved privacy/terms content, configure HTTPS and secure cookies, use a production WSGI server and persistent rate-limit storage, restrict the database user, implement backups, and establish enquiry retention. The current server binds to your desktop only and is intended for localhost development.

## Project layout

## Resort research pages

All eight Mauritius resorts use `templates/resort.html` and structured defaults in
`website/resort_research_data.py`. Original summaries were checked against official
Beachcomber pages and linked 2025-26 factsheets on 3 October 2026. Conflicting room
sizes and unverified transfer times are left for confirmation, not estimated.

In Admin > Resorts, the book icon opens the resort-information editor. Saved
overrides use `Setting` keys `resort_research_CODE`; supplier refresh does not
overwrite them. Update the checked date only after reviewing the linked sources.
Rooms and dining venues are editable rows; the final blank row adds an entry.
Clear every field in a row to remove it. No database migration is required.

Approved personal commentary belongs in the existing Dirk's Take field. Empty
commentary shows a neutral invitation, never an invented visit or recommendation.
Photograph approval applies only to the image URL approved at save time. Changing
the photograph requires renewed resort-identity and usage-rights approval. Current
unapproved imagery is labelled as inspiration; verify rights before public launch.

Published packages are filtered to the current resort. Prices retain the existing
48-hour freshness and booking-validity checks. A missing or stale rate shows
"Quote required"; flights, room, transfers and extras are confirmed in the quote.
Comparison, guides, package details and enquiry links remain on this website.
Official supplier links are secondary attribution, not the main next action.

## Source files

- app.py: Flask entry point.
- website/: routes, models, supplier adapter, CLI commands, and supplier sync.
- templates/ and static/: public/admin interface, logo, local icons, and imagery.
- migrations/: initial database migration compatible with PostgreSQL and SQLite.
- configure.py: private local database/API setup.
- tests/: automated tests.
- .env: your private credentials, excluded from the source archive and Git.
