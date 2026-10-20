# Holy Family High School

A Django school website with a custom, permission-controlled staff workspace. The design draws on Sacred Heart High School's minimalist page flow, with an original editorial hero, numbered navigation cards, and Holy Family's original crest, forest green and gold, warm neutral backgrounds, locally hosted Libre Baskerville and Rubik fonts, and Tailwind CSS **4.3.3**. No frontend framework or external font request is required at runtime.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci
cp .env.example .env
# Set a private, random DJANGO_SECRET_KEY in .env.
python manage.py migrate
python manage.py import_google_sites
python manage.py seed_school_defaults
python manage.py setup_staff_groups
python manage.py createsuperuser
npm run build:css
python manage.py runserver
```

For the existing checkout, retain `.env`, the database and media. Migrations and school defaults have already been applied. Existing staff credentials remain valid. No default password is supplied.

- Website: http://127.0.0.1:8000/
- Staff workspace: http://127.0.0.1:8000/staff/
- CSS watch mode: `npm run watch:css`

## Site structure

The primary pages are Home (`/`), About (`/about/`), Contact (`/contact/`), Curriculum (`/curriculum/`), Staff (`/our-staff/`), Calendar (`/events/`) and Admissions (`/apply/`). News, subject and event details, privacy and the application receipt remain supporting routes. About submenu pages can be added later in code.

Navigation and public page layouts are fixed in templates rather than configured through database page records. The home page uses a light split hero with an unobstructed photograph or crest panel, a motto below the image, four numbered quick links, school information, and a combined news/calendar section. School and admissions copy addresses learners directly; history and community updates use a general tone. Inner pages share centered headers and rounded cards, with distinct layouts for history, subjects, staff, dates and forms. Headers use Holy Family gradients with optional staff-uploaded photographs. Clearing a photograph restores the themed gradient. The footer displays editable school information and links. Contextual actions sit within each page; there is no repeated admissions banner above the footer. Layouts adapt to smaller screens, navigation works without JavaScript, SVG icons are decorative, and forms have visible labels, error messages and keyboard focus styles.

Anchor links scroll smoothly with an offset for the sticky header. Brief page introductions, menu transitions, interactive card/button states and one-time section reveals give the public pages a consistent pace. Scroll reveals keep content visible without JavaScript, leave forms and the initial viewport still, and stop immediately for keyboard focus or a reduced-motion preference. Reduced-motion mode also turns off CSS animations, transitions and smooth scrolling.

## Search and sharing metadata

`SITE_URL=https://holyfamily.ac.ls` is the preferred public origin. Canonical links, Open Graph/Twitter previews and `/sitemap.xml` use that configured origin, never an incoming request host. Each primary and published detail page has a unique title and a plain-text description capped at 160 characters. Featured images supply sharing previews; the attached crest is the fallback. The homepage includes safely encoded School JSON-LD using the public school name, logo and available contact information.

`/robots.txt` and the sitemap expose only published public routes. Drafts, scheduled stories, hidden departments and their private profiles, staff/admin pages, private receipts and arbitrary archived database pages are excluded. Local development and School settings → Preview mode return `noindex`, block crawling and suppress sitemap entries. Disable preview only when publishing the reviewed website. Error responses also carry `noindex`.

The new attached transparent crest is stored unchanged at `assets/branding/holy-family-favicon-source.png`. It supplies the public/staff ICO and 48/96-pixel PNG favicons plus the Apple touch icon. To rebuild all icon sizes, run `python scripts/build_favicons.py`, then collect static files. Header and hero branding remain editable separately.

## Manage content without Django admin

Sign in at `/staff/`:

| Area | Staff can manage |
| --- | --- |
| School settings | School identity, home hero text/image, About history/mission/vision, page header text/images, curriculum introduction, contact details/map, calendar introduction, admissions guidance |
| School values | Titles, descriptions and order; shown on Home and About |
| News & articles | Rich text, embedded image uploads, tables, featured images, categories, drafts and scheduled publication |
| Events | Rich text with embedded images, featured images, dates, venue and publication; displayed in a monthly calendar |
| Departments & staff | Department descriptions/order/publication, full names, optional title and start date, roles, biographies, profile photographs and department membership |
| Messages | Search contact enquiries, review status, private notes and confirmed deletion |
| Applications | Review admissions enquiries, private notes, status and confirmed deletion |
| Staff access | Administrators create staff accounts and enable or disable access |

Content editors can manage public content and upload images. School office staff (the **Admissions officers** group) can access applications and contact messages. Content editors cannot read private inboxes. Administrators can access all areas. All staff mutations require sign-in, server-side permissions and CSRF protection. Django admin is a superuser maintenance fallback, not the editing interface.

### Rich-text images

Use the image button’s Upload tab, or paste/drag an image into the editor. Only authorised content editors can POST to `/staff/images/upload/`. JPEG, PNG and WebP images must be under 5 MB and 20 megapixels. Uploaded images are re-encoded as JPEG, reduced to at most 2400 pixels per side, stripped of metadata, and stored under unique names in `media/editor/`. Inline images are public content; do not upload confidential files.

Saving waits for image uploads to finish. Upload failures retain the unsaved editor content and show an error. Sanitisation retains headings, lists, links, tables, captions and local uploaded images while removing scripts, arbitrary embeds, unsafe attributes and external image URLs. Google Maps is managed separately through the validated school setting. JavaScript is required for the visual rich-text editor; a textarea remains available if it fails to load.

### Contact form and map

Contact submissions are persisted in the staff Messages inbox. A confirmation appears after a successful submission. This does **not** send an email. Invalid fields, missing consent and honeypot submissions are rejected. Attempts are limited to five per IP per hour; the simple database throttle has a small possible overrun under simultaneous requests.

In School settings → Contact page & school office, paste the Google Maps **embed URL** or the iframe copied from Share → Embed a map. The workspace extracts and stores only its validated HTTPS source URL; pasted markup and attributes are never rendered. Short share links are not accepted. Accepted endpoints are `google.com/maps/embed`, `www.google.com/maps/embed`, and `maps.google.com/maps?...&output=embed`. Clearing the field hides the map. The default is a search-based map for Holy Family High School, Maputsoe; staff can replace it with the exact location’s embed URL. Google Maps connects to Google when loaded.

### Calendar and staff browsing

Calendar (`/events/`) shows a Monday-first month grid with Previous, Next and Today controls, and a dated agenda on small screens. Published past events remain available in their month. Multi-day events appear on every affected school-local day; an end at midnight does not add the following day. Times always follow `DJANGO_TIME_ZONE`, even if a different display timezone is active. Supported navigation spans 1900–2100. Event links open the full detail page.

Staff (`/our-staff/`) begins with published departments. Open a department for linked staff previews, then select a profile for its photograph, full names, title, role, biography and optional date from. The title and date are optional and existing names are preserved. Unassigned published profiles appear under School team. Drafts and profiles assigned only to hidden departments have no public page. Public previews from the staff workspace follow the same visibility rules.

### Admissions

The native application form follows the school's [Grade 8 2027 Google Form](https://docs.google.com/forms/d/e/1FAIpQLSeFREgd9piREXFBs1W1IsD77Cb10oEyeMpXl5Q00s5_Xdydzw/viewform): surname, name, date of birth, optional physical address, district (including Other), primary school, parent/guardian name and contacts, and a required Yes/No boarding preference. Guardian consent is also required. Guardian email is optional; a free-form message is not requested. Applications are saved in the private staff inbox; submission does not send data to Google.

School settings contains editable admission grade/year, the M50.00 non-refundable fee, M-pesa merchant 5184, the 14 October 2026 deadline, and the 17 October 2026 interview at 08:00 local school time. Interview subjects and stationery instructions are editable too. Update these settings for subsequent intakes and use Admissions open to control acceptance. Each new application records the configured grade and year when submitted; changing the intake later preserves that record. Existing submissions retain their names, contact details, messages and review status.

## Content defaults and source

The school's original Google Site supplies the mission, history, staff list, curriculum, student writing, research project and office contacts:
https://sites.google.com/view/holyfamaily-maputsoe/home

The snapshot is stored in `school/data/google_sites.json`. Starter curriculum and subject descriptions are adapted to speak directly to learners; migrations replace only recognised original wording and preserve staff-written changes, photographs and other school records. `import_google_sites` retains these as editable records, unpublishes recognizable demonstration news/events, and preserves subsequent staff edits on repeat runs. `seed_school_defaults` fills blank contact fields and supplies mission-derived vision wording. The vision is a proposed default, not a verbatim statement from the original site; staff should review it. Historical enrolment totals remain attributed source material. The 2025 calendar is an editable archive link. Student writing is distinguished from official school statements.

The exact user-attached crest is saved in `assets/branding/holy-family-original.png` and `static/images/holy-family-original.png`. Original Google Site photos could not be downloaded; staff can upload school photos through the workspace. Older generated crest files remain as unused references.

Preview mode is an editable setting. It displays a notice but still saves submissions; use fictional details while previewing. Admissions availability remains under staff control. No school fees or current event dates were invented.

## Verification

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
node scripts/test-editor.cjs
node --check static/js/editor.js
node --check static/js/site.js
npm run build:css
python manage.py collectstatic --noinput
```

The tests cover public/draft/scheduled content, staff and department visibility, calendar navigation and timezone boundaries, staff permissions, contact delivery and validation, review and deletion, image upload permissions and validation, rich-text sanitisation, safe Google Maps paste handling, preservation of staff-edited copy, CSRF, login throttling, settings and admissions. The editor check verifies CSRF upload requests and prevents saving when an image upload fails. Browser validation has checked 320–1920px widths, phone landscape, 200% text, the calendar controls, staff browsing, contact map, and navigation without JavaScript. Those ad hoc browser scripts are not part of the repository test command.

Build CSS and collect static files together when deploying style changes. WhiteNoise serves the collected assets, so rebuilding only the source stylesheet can leave visitors seeing an older layout. The redesigned public styles have an explicit cascade layer after shared components to prevent legacy rules from changing card layouts at different widths.

## Deploy to Python hosting

This application needs a Python-capable host with persistent database and media storage. Sites' JavaScript Worker hosting cannot execute the Django backend.

1. On the server, copy `.env.production.example` to `.env` in the application root. Replace the secret (at least 50 random characters), cPanel database credentials and absolute static/media paths. Use a separate database and user for Holy Family.
2. In cPanel's Python application setup, use this repository as the application root, `passenger_wsgi.py` as the startup file and `application` as the entry point. Select the application's virtual environment when installing dependencies and running management commands.
3. Install `pip install -r requirements-production.txt`. PyMySQL supplies the pure-Python MySQL/MariaDB driver; mysqlclient and MySQL development headers are not required. The rsa extra supports MySQL SHA-256 authentication. Create the database with utf8mb4 support and grant the configured user access.
4. Build CSS with `npm ci && npm run build:css` locally or on the host, then deploy the built assets. Run `python manage.py migrate`, `python manage.py setup_staff_groups`, `python manage.py createsuperuser` and `python manage.py collectstatic --noinput` in the server environment. For a new database, run the import and seed commands from the local setup instructions. Switching database engines does not copy existing SQLite data; transfer existing content separately if required.
5. Configure Apache to serve the selected static and media directories. Media must be public and non-executable. Keep `DJANGO_MEDIA_URL=/media/` for the existing editor image sanitiser. Keep application source and `.env` outside the public document root.
6. Enable HTTPS. Set `DJANGO_TRUST_X_FORWARDED_PROTO=True` only if the host confirms it sets and sanitises that header. Production HSTS starts at one hour (`DJANGO_SECURE_HSTS_SECONDS=3600`); increase it after confirming HTTPS works reliably. Subdomain coverage and preload remain opt-in. Preload requires at least one year of HSTS and HTTPS on all subdomains. Run `python manage.py check --deploy` with the actual production environment before restarting. Missing `SITE_URL` is a deployment error; malformed or unmatched production origins fail startup. The default HSTS configuration produces `security.W005` and `security.W021` because subdomain coverage and preload are deliberately opt-in; resolve them only after confirming that policy for every subdomain.
7. Restart the Python application through cPanel. Confirm school contacts, map, admissions and privacy text, then disable preview mode when ready. Back up MySQL and media, monitor Passenger logs and schedule `python manage.py purge_submission_attempts`.

Settings use `python-decouple`: process environment variables override the repository-root `.env`. The older `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and `TRUST_PROXY_HTTPS` names remain supported as fallbacks; prefer the new `DJANGO_*` names. Production defaults to MySQL; `DATABASE_ENGINE=mysql` and `DATABASE_ENGINE=mariadb` both use Django's MySQL backend and the `MYSQL_*` credentials in `.env`. SQLite is allowed only with `DJANGO_DEBUG=True`. Root `.env` discovery is independent of Passenger's working directory. Local development uses `.env.example` with SQLite. Contact environment values are fallbacks only when no School settings record exists.

If saving an announcement with an emoji fails with MySQL error 1366 (`Incorrect string value`), the existing columns may still use `utf8mb3` or `latin1` even though the connection uses `utf8mb4`. Back up the production database, deploy migration `0022`, and run `python manage.py migrate` in the application's server virtual environment. It converts the announcement and project tables (including existing text columns and table defaults) to `utf8mb4_unicode_ci`; SQLite is unchanged. Conversion may rebuild and lock these tables, so run it during a quiet period. It is deliberately irreversible because converting back could lose emoji. Retry the failed save after migration. Other tables are outside this migration's scope. For new tables, also set the database default to `utf8mb4` through cPanel/phpMyAdmin; changing a database default alone does not repair existing columns.

TinyMCE is self-hosted through django-tinymce in GPL mode; its licence is bundled. Google Fonts’ OFL licences are included under `static/fonts/`.


## Production security configuration

Startup rejects placeholder, short or low-diversity secrets; empty, wildcard or localhost-only host lists; insecure or wildcard CSRF origins; placeholder/empty database credentials; and disabled HTTPS redirects or secure cookies. Use a unique random production secret and list each permitted domain explicitly. CSRF trusted origins, when needed, must be HTTPS origins without paths. Log levels are validated against DEBUG, INFO, WARNING, ERROR and CRITICAL.

Static and media roots must be absolute, separate directories that do not contain the application source. Replace account placeholders before deployment. `DJANGO_MEDIA_URL` must remain `/media/` because uploaded editor images are restricted to that path. Keep `.env` outside the web document root and readable only by the application account (`chmod 600 .env`). Apache must prevent script execution and directory listing in uploaded media; Django settings cannot configure the host's web server.

Existing protections include five-attempt login lockouts, submission throttling and honeypots, CSRF checks, role-based staff permissions, HTML sanitization, verified image formats and dimensions, a self-hosted editor, restrictive content security and permissions policies, clickjacking protection, and private no-store responses for staff and submission pages. HTTPS responses also use HSTS, secure cookies and same-origin opener isolation. These protections are covered by automated tests.

Forwarding headers remain untrusted by default. Enable `DJANGO_TRUST_X_FORWARDED_PROTO` only behind a proxy that strips client-supplied headers and sets its own HTTPS value. Login and submission throttles use `REMOTE_ADDR`; a reverse proxy must supply the real client address there to avoid grouping all visitors under the proxy's address. Set a request-body limit at the web server too; Django's image validators reject oversized images, but upload memory thresholds alone do not cap incoming traffic. Schedule `python manage.py clearsessions` alongside submission-attempt cleanup and keep database/media backups and dependencies current.

Runtime values are read with `python-decouple` and retain typed defaults when omitted: language/time zone, localization, login lockout limits, password minimum length, session lifetime and cookie settings, security headers, and upload memory/file-count limits. `.env.example` and `.env.production.example` list the environment names. The real root `.env` retains the existing secret under `DJANGO_SECRET_KEY`; credentials remain private. Production guards continue to reject unsafe values. PyMySQL is registered as `MySQLdb` in `config/__init__.py` for Django’s MySQL backend.

The fixed-page migration preserves history, mission, vision, introductions and header images from legacy About, Curriculum and Staff page records in School settings. Legacy records are retained as an archive; page creation, layout selection, publication and navigation controls are no longer exposed. Existing `/school/about/`, `/school/curriculum/` and `/school/our-staff/` links remain valid. Other legacy pages are outside this initial page set. Run `python manage.py migrate` when deploying these changes.


### Form submissions and duplicate applications

All form writes (including staff/admin forms) share an atomic SQL-backed limit of 120 writes per IP per minute. Public contact and admission forms additionally allow 5 attempts per form per hour and 20 combined attempts per day. Invalid forms, honeypots and CSRF failures count too. Limits return HTTP 429 with Retry-After; blocked requests do not create unbounded attempt rows. IPv6 clients share a /64 allowance. IP subjects are stored as keyed hashes; forwarding headers are never trusted. Configure FORM_WRITE_RATE_PER_MINUTE, PUBLIC_FORM_RATE_PER_HOUR and PUBLIC_FORM_RATE_PER_DAY for real school traffic, especially shared school/mobile networks.

Public submissions accept at most 64 KiB (PUBLIC_FORM_MAX_BYTES), no files, no repeated parameters, and only normal browser form content types. DJANGO_DATA_UPLOAD_MAX_NUMBER_FIELDS defaults to 500 for all forms. Keep the existing CSRF, honeypot, field-length, consent and image validation protections. Run purge_submission_attempts daily to remove expired counters and historical attempt logs. Apply request-size/connection limits and DDoS protection at Apache or the upstream proxy as well; application limits do not replace network controls.

Names use Unicode-aware title case; email is lowercase, whitespace is trimmed/collapsed, and hidden control characters are removed. The unique applicant key covers normalized given name, surname, birth date, intake year and grade, independent of guardian email/phone. Simultaneous submissions are rejected by the database constraint, with a useful conflict message and no disclosure of an existing reference. Siblings and later intakes remain allowed. Existing duplicates are preserved; the earliest complete record owns the duplicate key. Incomplete historical identities are not guessed or merged.

New references use HFHS-<intake year>-<24 random uppercase hex characters>, generated with cryptographic randomness rather than personal details or a sequential ID. References are unique, searchable by staff and shown only on the session-protected receipt. Previously issued UUID references remain valid and unchanged. Apply migration 0015 before restarting the application.


### School Life and student writing

Community in the public navigation contains general News and School Life. School Life is separate from official news and publishes student stories, poems and articles at `/school-life/<readable-title>/`. Category filters and pagination preserve the selected category. Only published posts whose publication time has arrived appear publicly, in metadata or in the sitemap.

Content editors manage School Life and reusable Student authors under Community in the staff workspace. Select a saved student author, or leave that selection blank and enter a new student name and grade in the author section of a post. No student login is created. Each post saves its name/grade credit so later grade changes do not rewrite older writing; choosing a different author updates the credit. Credited authors cannot be deleted while posts refer to them. Migration 0016 adds these permissions to the existing Content editors group without removing other permissions. New installations continue to use `python manage.py setup_staff_groups`. Existing general news and source material are preserved; no writing is automatically attributed to a student.

The public mobile menu animates open and closed, closes on outside click/Escape/link selection, prevents focus entering hidden links, and resets correctly at the desktop breakpoint. Navigation remains available without JavaScript and reduced-motion preferences disable transitions. School Life uses soft forest/gold gradients, restrained card transitions, readable article widths and a separate author credit beneath each piece.


### Automatic content addresses

Articles, events, subjects, staff profiles and School Life posts generate unique readable slugs on first save. Editors do not enter slugs. Duplicate titles/names receive numeric suffixes, and the database constraint plus retry handles concurrent writers. Long titles are shortened to fit the field, and titles without usable ASCII characters receive a safe fallback. Existing addresses are preserved on title/name edits. Administrator views display generated slugs as read-only. Migration 0017 fills any previously blank content slugs without rewriting existing addresses, including archived page records. Direct imports can still supply an existing slug to preserve legacy links; normal model saves provide automatic generation when it is absent.


### Public navigation and search metadata

Detail pages link back to News, the calendar, Curriculum, the staff directory or School Life. News page numbers and School Life category/page selections survive the round trip. Calendar details return to the event’s local month. Return destinations are constructed from known routes and validated list parameters. Header links mark their parent section on detail pages; the footer groups School, Community and Contact links. Repeated cross-page action banners were removed to keep reading flows focused.

One metadata provider supplies HTML titles, descriptions, Open Graph/Twitter previews and canonical URLs. Optional or HTML-only content receives a meaningful page-specific description; paginated/category lists receive distinct titles and descriptions. Tracking/return parameters are excluded from detail canonicals. This follows Google’s guidance on [page-specific descriptions](https://developers.google.com/search/docs/appearance/snippet) and [canonical URLs in sitemaps](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap).

`/sitemap.xml` includes primary pages and visible published details, with scheduled writing excluded until publication. `/robots.txt` advertises that sitemap in production and excludes staff/admin/editor/receipt paths. DEBUG or preview mode intentionally disables indexing and returns an empty sitemap. Set the real HTTPS SITE_URL, use production settings, and disable website preview before launch. Error pages and private receipts remain noindex. Public pages support GET/HEAD; reading a receipt with HEAD does not consume it.

Regression checks in `school.test_public_sweep` crawl internal links and anchors, verify public metadata and HEAD responses, exercise list/detail return paths, and validate sitemap/robots visibility rules.

The calendar uses a shorter header and tighter month cells. On phones, the seven-column grid fits the viewport; marked dates link to the agenda below, where titles, local times and locations remain readable. Upcoming dates collapse by default on phones and remain expanded on larger screens; the native disclosure still works without JavaScript. Repeated contact prompts and event “View details” labels were removed from the calendar, while event cards remain clickable.

### Sign-in protection (Django AXES)

AXES protects both staff and Django admin authentication against repeated password guesses. The defaults block an IP after five failures, with a 30-minute cooldown; a successful sign-in resets its failure count. `DJANGO_AXES_FAILURE_LIMIT`, `DJANGO_AXES_COOLOFF_MINUTES` and `DJANGO_AXES_RESET_ON_SUCCESS` override these defaults. This is separate from public application/contact submission limits and does not replace strong passwords or network protection.

Website superusers can inspect **AXES → Access attempts** in Django administration to investigate failed sign-ins and remove a verified user's attempt record to clear a lockout. From the deployment environment, `python manage.py axes_reset_ip <IP_ADDRESS>` clears only that address. Verify the requester before resetting; avoid clearing every lockout during an attack. Review repeated failures in security logs and establish a retention schedule for authentication records. AXES does not automatically send security alerts in this project.

Lockouts currently use the network address supplied in `REMOTE_ADDR`. Confirm that production's reverse proxy supplies the real visitor address: otherwise everyone can share the proxy's lockout. People on a shared school connection can also share an IP lockout. Do not trust arbitrary forwarded headers to solve this; configure the trusted proxy correctly first.

### Standard staff roles

The **Staff access** screen includes a role guide and inline account-creation help. `school/roles.py` is the shared source for the guide, role choices and group setup. Content editors manage every current public content type and Site Settings; school office staff manage admissions settings and handle private applications and messages, including deletion and Excel export. Combined access includes both. Only website superusers manage staff accounts and use Django administration. School management profile titles do not grant login permissions.

Creating a staff account automatically creates missing standard groups and adds any missing standard permissions, while preserving custom grants. No setup command is required before adding users. Run `python manage.py setup_staff_groups` when you intentionally want to reset standard group permissions to the current role definition. It synchronises the two standard groups to their defined model permissions, so review intentional customisations before running it; other groups and individual user permissions are not changed. Add new managed content types to the role registry and keep its descriptions current. The role coverage test checks this registry against the workspace content registry.


### Admissions workspace and Excel exports

Admissions has a dedicated sidebar group with **Applications** and **Admissions settings**. General school settings no longer display intake/payment/interview fields. School office users receive the narrowly scoped `school.change_admissions_settings` permission; it does not grant general school settings access. Existing office groups receive it through migration 0019; automatic group provisioning and `setup_staff_groups` also include it. Content editors with general settings permission can continue to manage admissions settings.

Closing admissions hides the application form, intake/payment/interview details and promotional introduction. The page shows a closure notice, and Admissions remains the final link in the public **Our school** menu.

Applications offer **Export to Excel** for users with application-view permission. The `.xlsx` download includes every record matching the current search/status filters, across all list pages. It includes submitted information, application reference, review status and local submission time, but excludes internal staff notes. Phone numbers remain text and submitted spreadsheet formulas are stored as literal text. Exports are marked private/no-store and an export count is recorded in the audit history without applicant names or the search text. Handle downloaded files as private school records; downloaded copies are outside website access controls. Install the updated requirements before deploying this feature (`openpyxl` and `et-xmlfile`), and run migrations.


### Announcements and projects

Announcements are separate from news, events and student writing. Editors can draft, schedule, pin and optionally expire a notice. Only published notices whose publication time has arrived and whose expiry has not passed appear on the homepage, public list, detail pages and sitemap. Expired notices remain in the staff workspace for editing or reuse.

Projects have their own published list/detail pages, summary, rich content, optional image, planned/ongoing/completed status and display order. The homepage shows up to three active announcements and three published projects; empty sections are omitted. Both types use automatically generated, stable slugs and support embedded editor images. Their public lists are paginated and detail pages return to the originating list page.

Run migrations on deployment. Migration 0020 adds the models and grants their permissions to existing Content editors without changing unrelated grants. New groups use the shared role registry. Admissions officers retain their existing admissions-only access. Both types are managed under Community in the staff menu; News is labelled separately from School Life.

General settings no longer expose the unused motto display or the title for the removed homepage welcome section. Existing data is retained. The about/history introduction now appears with the About settings rather than Homepage settings. Current school values, statistics, admissions and student-author management remain available because they are still used by the website.

### Public email address protection

Public contact addresses display ` [at] ` in place of `@`, with a reusable protected-email component and a contact-page fallback when JavaScript is unavailable. The email-app link is assembled only when activated; public HTML does not ship a raw `mailto:` address. Donation links retain their enquiry subject. Rich published content also obfuscates addresses and converts email links, and metadata descriptions omit raw email addresses. The School JSON-LD no longer includes an email property.

Stored contact settings, private staff records, application exports and visitor-entered form values remain unchanged. This discourages basic address scraping; it cannot prevent a determined scraper from reconstructing a visible address. Existing contact-form throttles, validation and honeypot protections remain in force. Mail-server spam filtering and sender authentication are managed separately by the email provider.

### Private admission results

School office staff use **Admissions → Admission results** in the staff workspace to import one academic year's admitted students in bulk. Download the blank CSV template from that page or upload a values-only Excel `.xlsx` workbook with exactly one worksheet. The header row must be `Year,Surname,First Name(s),Primary School,Boarding`, in that order. Include all first names; `Y` grants boarding, while `N` or blank means boarding was not granted. All rows must match the selected year. The importer rejects malformed files, formulas, duplicate matching identities, missing details, extra columns and invalid values before making changes. Limits are 2 MB compressed, 20 MB unpacked, and 5,000 student rows. Old `.xls` and macro-enabled formats are not supported. XML parsing is hardened with `defusedxml`, as recommended by the [openpyxl security documentation](https://openpyxl.readthedocs.io/en/stable/index.html#security).

A valid upload replaces that year's entire dataset atomically and hides it. Staff review student and boarding totals, then separately publish. They can withdraw results immediately or permanently delete a year. Replacement and publication lock the year during the transaction; stale publication/deletion forms are rejected. These actions are audited without student names. Standard Admissions officers receive the new release permissions; content editors do not. No per-student entry or editing is required or exposed.

The result checker is linked from Admissions, including when applications are closed. Only at least two letters of a surname are required. The latest published intake is selected automatically; academic year is displayed with the form, matches and boarding details rather than entered by visitors. Older published years and unpublished intakes are excluded, and old selection links stop working when a newer intake is published. Case-insensitive partial surname matching is supported, with an optional partial first name to refine the search. School-only searches are rejected. Up to five matching admitted students are shown with their primary schools; broader matches require refinement and have no pagination or offset. Appearing in the results confirms admission. Clicking the related primary school displays that student's boarding status directly, with no school-name entry, confirmation, acceptance or collection step. School names are displayed as supplied in the spreadsheet (with whitespace normalised), so punctuation variants do not block access. Each school click submits a CSRF-protected POST with a signed selection valid for ten minutes. Withdrawn/replaced releases and invalid or expired selections cannot be viewed. Submitted names, primary schools and boarding status are not stored in session receipts or URLs. Searches and detail selections use post-redirect-get: a handled POST returns HTTP 303 to a GET URL containing only a random opaque receipt reference. Receipts are bound to the browser session, expire after ten minutes and retain at most ten recent views for Back and multiple tabs. The default database-backed session stores signed record references and generic validation messages, rather than student details or the submitted search text. Each receipt GET checks the current published intake/revision and reloads current records; withdrawn, replaced, superseded, deleted and expired results cannot be replayed. A copied URL without its originating session cannot retrieve results. GET/HEAD reloads neither consume another search quota nor extend receipt validity. Middleware-rejected requests retain their original security status codes. Run Django `clearsessions` as scheduled maintenance to remove expired database sessions; expired receipt references are also pruned on subsequent lookup activity. Pages and errors are private/no-store/noindex and excluded from the sitemap. Referrer policy is same-origin so native forms retain valid CSRF origins while external links receive no referrer.

The database retains surnames, first names and primary schools to identify matching students, a secret-keyed HMAC of the complete imported identity for deduplication, and boarding status. Source spreadsheets are not retained. Keep the original workbook securely offline for corrections and re-imports. Migration `0024` adds name storage (and utf8mb4 support for the results table on MySQL/MariaDB); migration `0025` adds primary school storage. Existing imports cannot recover names or schools from fingerprints: re-upload and publish each existing year to enable the revised search. The staff page marks years that need this step; original records remain intact until replaced. Rotating `DJANGO_SECRET_KEY` invalidates selection links and resets derived throttle keys; a fresh search creates new links without requiring re-import. Stored student details, fingerprints and boarding records need the same access, backup and retention controls as other admissions records. Deleting a year removes its active records; audit entries and protected backups have their own lifecycles.

Deploy with `pip install -r requirements-production.txt`, `python manage.py migrate`, and `python manage.py collectstatic --noinput`, then restart the application. Migration `0023` grants existing Admissions officers the new release permissions; `python manage.py setup_staff_groups` also synchronises standard roles when needed. Production results remain empty until school staff upload and publish a year.

Lookup POSTs, including invalid and CSRF-rejected attempts, share SQL-backed limits across workers: `ADMISSION_LOOKUP_RATE_PER_MINUTE=15`, `ADMISSION_LOOKUP_RATE_PER_HOUR=120`, and `ADMISSION_LOOKUP_RATE_PER_DAY=300` per network address (IPv6 uses /64). A normalised search also has an `ADMISSION_SEARCH_RATE_PER_DAY=100` allowance across addresses, and each selected student has an `ADMISSION_DETAIL_RATE_PER_DAY=60` boarding-detail view allowance across addresses. Search submissions and school clicks each count as one request; these allowances accommodate several family lookups. Limits apply to successful and unsuccessful checks. A rejected request returns HTTP 429 with `Retry-After`. Shared school/mobile networks share an allowance, so office staff may need to help families who hit it. Existing `REMOTE_ADDR` proxy guidance applies; arbitrary forwarded headers are not trusted. Do not enable request-body logging at the proxy, host or monitoring service. Existing `purge_submission_attempts` maintenance also removes expired throttle counters.

Partial name matching exposes a bounded set of admitted student names and primary schools. Anyone who finds a match can click its school to see boarding status; this workflow does not authenticate the visitor. Rate limits reduce automated collection but cannot guarantee secrecy. Use a private reference code or authenticated family access if the school later needs stronger identity verification.

### School prospectus

**Admissions → Prospectus** in the staff workspace accepts one PDF, up to **8 MB and 40 pages**. Authorised school office staff and administrators can upload, preview all prepared pages, publish, withdraw and delete it. A replacement upload is validated and converted before it atomically replaces the current document; it stays hidden until published. Invalid files, failed conversion and failed database writes leave the existing prospectus intact. Actions are audited and stale publication/deletion forms are rejected. Migration `0026` adds the models and grants existing Admissions officers the new permissions; standard role setup also includes them. Content editors do not gain this access.

The public `/prospectus/` page is linked under **Our school**, in the footer, and from an admitted student's boarding detail. It provides a scrollable page viewer and **Download PDF**. If no prospectus is published, including after withdrawal, it says **“The prospectus will be uploaded soon.”** On mobile, the download button appears below the displayed pages.

PDF conversion runs in a separate Linux process using [PDFium](https://pypdfium2.readthedocs.io/en/stable/python_api.html) and ReportLab, with a 30-second wall timeout, a maximum 20 CPU seconds and up to 768 MB virtual memory (respecting stricter host limits). Pages are rasterised at up to 144 DPI and three million pixels per page. Images and the rebuilt PDF are each limited to 8 MB; extracted text is bounded to 20,000 characters per page. Malformed and password-locked PDFs fail closed. The original file is discarded after preparation. Only freshly encoded JPEG pages, escaped plain text and a newly constructed image-only PDF are retained, removing original JavaScript, forms, attachments, links and document actions from the delivered PDF. The browser never embeds the original uploaded PDF. Rasterisation changes the download: original text selection, interactive features and vector resolution are not preserved. This is resource-limited conversion, not an operating-system security sandbox or antivirus scan; keep dependencies updated.

Prepared data lives in database records, not public media files. Every page and PDF request checks publication and revision, uses `no-store`/`nosniff` headers, and old URLs fail after withdrawal, replacement or deletion. The viewer’s page list is also checked against the publication revision to avoid displaying a concurrent draft replacement. The PDF is served as an attachment, while browser viewing uses image pages. Withdrawal blocks subsequent access; it cannot erase files already downloaded, screenshots or content already loaded in another browser.

Install the updated `requirements-production.txt`, run `python manage.py migrate` and `python manage.py collectstatic --noinput`, then restart the application. PDFium is installed from its platform wheel; no Poppler system package is required. Ensure hosting supports Linux subprocesses, the worker's resource limits, and enough MySQL `max_allowed_packet` for the prepared PDF (at least 16 MB recommended). Include these database records in the school's normal backups and retention practices. Page-image and download URLs are not added to the sitemap and carry noindex headers; only the stable public prospectus page is listed.
