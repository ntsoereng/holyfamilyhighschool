# Holy Family High School

A Django school website with a custom, permission-controlled staff workspace. The design draws on Sacred Heart High School's minimalist page flow, with an original editorial hero, numbered navigation cards, and Holy Family's original crest, forest green and gold, warm neutral backgrounds, locally hosted Libre Baskerville and Manrope fonts, and Tailwind CSS **4.3.3**. No frontend framework or external font request is required at runtime.

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
| School settings | School identity, home hero text/image, About history/mission/vision, page header text/images, curriculum introduction, contact details/map, calendar introduction, admissions guidance and privacy |
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

The native application form follows the school's [Grade 8 2027 Google Form](https://docs.google.com/forms/d/e/1FAIpQLSeFREgd9piREXFBs1W1IsD77Cb10oEyeMpXl5Q00s5_Xdydzw/viewform): surname, name, date of birth, optional physical address, district (including Other), primary school, parent/guardian name and contacts, and a required Yes/No boarding preference. Guardian consent is also required. Email and a message are no longer requested. Applications are saved in the private staff inbox; submission does not send data to Google.

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

TinyMCE is self-hosted through django-tinymce in GPL mode; its licence is bundled. Google Fonts’ OFL licences are included under `static/fonts/`.


## Production security configuration

Startup rejects placeholder, short or low-diversity secrets; empty, wildcard or localhost-only host lists; insecure or wildcard CSRF origins; placeholder/empty database credentials; and disabled HTTPS redirects or secure cookies. Use a unique random production secret and list each permitted domain explicitly. CSRF trusted origins, when needed, must be HTTPS origins without paths. Log levels are validated against DEBUG, INFO, WARNING, ERROR and CRITICAL.

Static and media roots must be absolute, separate directories that do not contain the application source. Replace account placeholders before deployment. `DJANGO_MEDIA_URL` must remain `/media/` because uploaded editor images are restricted to that path. Keep `.env` outside the web document root and readable only by the application account (`chmod 600 .env`). Apache must prevent script execution and directory listing in uploaded media; Django settings cannot configure the host's web server.

Existing protections include five-attempt login lockouts, submission throttling and honeypots, CSRF checks, role-based staff permissions, HTML sanitization, verified image formats and dimensions, a self-hosted editor, restrictive content security and permissions policies, clickjacking protection, and private no-store responses for staff and submission pages. HTTPS responses also use HSTS, secure cookies and same-origin opener isolation. These protections are covered by automated tests.

Forwarding headers remain untrusted by default. Enable `DJANGO_TRUST_X_FORWARDED_PROTO` only behind a proxy that strips client-supplied headers and sets its own HTTPS value. Login and submission throttles use `REMOTE_ADDR`; a reverse proxy must supply the real client address there to avoid grouping all visitors under the proxy's address. Set a request-body limit at the web server too; Django's image validators reject oversized images, but upload memory thresholds alone do not cap incoming traffic. Schedule `python manage.py clearsessions` alongside submission-attempt cleanup and keep database/media backups and dependencies current.

Runtime values are read with `python-decouple` and retain typed defaults when omitted: language/time zone, localization, login lockout limits, password minimum length, session lifetime and cookie settings, security headers, and upload memory/file-count limits. `.env.example` and `.env.production.example` list the environment names. The real root `.env` retains the existing secret under `DJANGO_SECRET_KEY`; credentials remain private. Production guards continue to reject unsafe values. PyMySQL is registered as `MySQLdb` in `config/__init__.py` for Django’s MySQL backend.

The fixed-page migration preserves history, mission, vision, introductions and header images from legacy About, Curriculum and Staff page records in School settings. Legacy records are retained as an archive; page creation, layout selection, publication and navigation controls are no longer exposed. Existing `/school/about/`, `/school/curriculum/` and `/school/our-staff/` links remain valid. Other legacy pages are outside this initial page set. Run `python manage.py migrate` when deploying these changes.
