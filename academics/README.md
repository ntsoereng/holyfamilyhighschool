# Marks and student reports

This private Django app runs in the existing cPanel/Passenger application using
the existing MySQL/MariaDB database, sessions, CSRF protection, Axes login
throttling, WhiteNoise and ReportLab installation. It needs no additional service,
public file bucket, scheduled worker, or PDF executable on the server.

## Deploy

Back up the database first. In the hosting account's application virtualenv:

```sh
python manage.py migrate
python manage.py setup_academic_access
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Restart Passenger through cPanel. Retain the site's existing HTTPS, proxy, secure
cookie, database and backup configuration. No new environment variables or Python
dependencies are required. If rebuilding the shared CSS, use `npm run build:css`
before collecting static assets. The academic stylesheet is a separate static file.

Superusers already have academic access. For delegated administration, a superuser
must explicitly give an **active staff user** the **Reporting administrators** group
in Django administration. Membership grants management of all private academic
records, including accounts, financial clearance and reports. Give this group only
to school personnel authorised for all of those responsibilities. Existing content
editors and admissions officers receive no academic permissions automatically.
Review the Reporting administrators group and superuser membership in Django
administration as part of each access review.

Open `/portal/office/`, or use **Marks & student reports** in the staff navigation.
The public website footer links to **School portal** (`/portal/`).

## First reporting cycle

1. **Accounts & access:** create teacher and family accounts. These are ordinary
   Django users with a portal role, no staff or superuser flag, no groups and no
   model permissions. Use individual accounts, verify recipients, and share their
   username and temporary password privately. First sign in requires a password
   change. The existing minimum length and Django password validators apply.
2. **Grading policy:** the default lookup follows the supplied school report:
   A* 90+, A 85+, B+ 80+, B 75+, C+ 70+, C 65+, D+ 60+, D 55+, E 40+,
   F 30+, G 20+, H 10+, U 0+. Each line is `minimum | grade | evaluation`.
   Evaluations populate the subject teacher remarks dropdown. Review the pass
   threshold (default 50%), principal name, report footer and result basis.
   The default result basis is the **current quarter average**, as confirmed
   from the sample. Existing custom grading policies are preserved on migration.
   Existing report snapshots retain their original grading and layout until
   deliberately regenerated. Layout is maintained in `reports.py`; arbitrary
   HTML, uploaded templates and remote resources are not executed.
3. Add **classes** with an academic year, **academic subjects**, **students** and
   **reporting periods**. Private academic subjects and students are deliberately
   separate from public website subjects and student authors. Add an enrollment
   for each student. A student can have only one class in a given year; the next
   year's enrollment preserves previous records. A class supports up to 200
   students to keep synchronous marks entry and generation bounded on Passenger.
4. Add a **teacher assignment** for **every subject expected on the class's
   report**, for each quarter. It specifies teacher, class, year/quarter and
   subject. The system cannot infer an omitted subject, so review the list before
   generation. Classes and quarters must belong to the same year. Multiple
   teachers cannot simultaneously own the same class/subject/quarter sheet.
5. Add **verified family access** after checking the person's identity and their
   relationship with the student's school records. Record the verification
   method in the private note. A family account can link to multiple children;
   multiple family accounts can link to a student. Student accounts use the
   family role and a `Student` relationship. There is no public registration or
   linking by an admission number/name: the office provisions and verifies access.
6. Teachers sign in at `/portal/`, save partial drafts and submit complete sheets.
   All percentages are out of 100, with at most two decimal places. Zero is a
   valid mark. Absence/exemption needs a note and no numeric mark. Missing
   marks cannot be submitted. Subject remarks are selected from the grading
   lookup, or left on **Automatic from final mark**. Notes/absence reasons are
   separate. Final subject marks average available submitted numeric quarters
   to date, rounded half up to a whole mark; missing historical marks display
   **Not recorded**. A current absence/exemption receives no final grade.
   Each quarter average weights included numeric subjects equally and rounds
   half up to one decimal place. Absences/exemptions are excluded.
7. In **Reports & fees**, choose the class and quarter, inspect every submitted
   sheet, then **Generate / regenerate privately**. Generation is refused if any
   required subject is still a draft or any student's mark is missing. All report
   writes for the class are one transaction. Use **Attendance & report remarks**
   beside each student to capture days absent (blank means not recorded; 0 is
   confirmed full attendance), class teacher remarks and principal remarks.
   Review the HTML and PDF previews.
8. Review fees for each student and quarter. Record the **total amount preventing
   release**, not a payment transaction. An amount greater than zero cannot be
   cleared. Zero alone is insufficient: an administrator must explicitly confirm
   clearance and enter a review note or reference. A missing review is held by
   default; families are asked to contact the office to confirm their balance.
9. **Publish reviewed reports**. Family access requires a current report,
   publication, an active verified student link, an active account/student, and
   explicit zero-fee clearance. The administrator's preview bypasses publication
   and fee holds but is never shared through a public URL.

## Report information and calculations

Use **Edit report information** on existing setup records to configure:

- **Students:** full name, separate student number and admission number.
- **Classes:** explicit stream/grade label (e.g. Grade 9) and class teacher name.
  Classes in the same year with the same nonblank stream share stream positions.
- **Subjects:** official code (including leading zeros) and **Include in summary**.
  Clear this for LBSE if following the sample; subject exclusions are configurable
  and are never inferred from the subject's name. Excluded subjects remain visible
  with their marks, grade and teacher, but do not count in averages or passes.
- **Periods:** school reopening date. Publication date is the actual release time,
  recorded in both the HTML snapshot and PDF when reports are published.

The default result/position score is the current quarter average. Subject passes
use the rounded final mark and configured pass threshold. Performance levels are
ADVANCE (80+), VERY PROFICIENT (70+), PROFICIENT (60+), BASIC (50+) and BELOW BASIC
(0+), with the sample's competence descriptions expressed without gendered pronouns.
Class and stream positions use competition ranking (1, 1, 3 for a tie). A position
is unavailable until every student in that population has complete submitted
sheets and a numeric summary. Stream positions are unavailable without an explicit
stream label; class names are not parsed to guess a grade. No ranks, enrollment
counts or personal details from the sample are imported into school records.

The report shows all quarter columns to date, final subject marks, grades,
evaluations, teacher names, quarter averages, result, performance lookup,
attendance, signoff names/remarks, reopening date and publication date. A typical
nine-subject report fits one A4 page; longer notes/rosters flow onto additional
pages with repeated table headers. No handwritten signatures are fabricated.
Setup edits and report detail edits withdraw affected reports for regeneration.
Earlier-quarter marks changes also withdraw later cumulative reports; affected
stream peers are withdrawn because their positions may change.

Held reports show the outstanding amount in LSL (M), plus the school's current
phone, email, address, office hours and contact page. Private payment references,
teacher drafts and academic marks are not included in held responses. Confirm
school contact details in the existing Site Settings before launch.

## Corrections and access reviews

- Submitted sheets are locked. An administrator **reopens** a sheet with a reason
  for teacher correction. This immediately invalidates and withdraws **all**
  reports for the class/quarter. Resubmit the sheet, regenerate, review and publish
  again. Reopening a closed period's sheet also requires reopening the period
  before the teacher can save. Closing a period does not withdraw reports.
- Adding a student to a roster reopens all of that class's sheets and withdraws
  its reports. Adding a required subject withdraws that quarter's reports.
  Configure rosters and subject lists before marks entry. Class/year, enrollment
  and subject identity are intentionally immutable in this first workflow; do not
  edit academic relationships directly in SQL after marks exist. Administrative
  data corrections or transfers require a reviewed data migration that accounts
  for prior marks and reports. Records use protected foreign keys rather than
  cascading deletion of student history.
- Teacher access reviews can reassign a sheet, revoke access or confirm the
  assignment. Revocation does **not** remove the subject from the required list or
  discard submitted marks. The replacement teacher can continue the sheet;
  submitted sheets still need reopening for corrections.
- Family link reviews record reviewer/date and can revoke or restore a verified
  relationship. Revoked users cannot use previously copied report/download URLs.
- Account reviews record reviewer/date and reason. Deactivation removes the
  usable password as well as disabling the user, invalidating existing sessions
  even after later reactivation. Verify identity and reset the temporary password
  before reactivating. Password resets invalidate other sessions and require
  another first-use password change. Portal managers cannot use these controls to
  modify privileged staff users, group members or accounts with extra grants.
- A fee change is checked on **each** report view and PDF request. Reintroducing a
  balance or withdrawing clearance blocks further access immediately, including
  old URLs. Previously downloaded copies cannot be revoked from a recipient's
  device. Withdrawal similarly blocks further family access.
- Regeneration replaces the current report snapshot/PDF and increments its
  revision; it always withdraws publication. Historical reports from other
  quarters/years keep their policy. Changing grading settings never silently
  changes a generated document: explicitly regenerate and republish if needed.
  Keep database backups for recovery of superseded revisions.

The **Audit log** is read-only in the portal. It records actors, timestamps,
targets, account and access reviews, submissions, fee changes (including previous
balance), policy changes, generated revisions, publication/withdrawal and PDF
downloads. Passwords are never logged. These logs contain private financial
review notes and must be included in the school's retention and backup policy.
Application administrators and database operators retain privileged access.

## Access matrix

| Capability | Teacher | Verified family | Reporting administrator |
| --- | --- | --- | --- |
| Read marks sheets | Active assigned sheets | No | All |
| Save/submit marks | Own active draft, open quarter | No | Return to teacher for correction |
| View/download student reports | No | Linked active student, published current report, zero-fee clearance | All generated previews |
| View outstanding balance | No | Linked student only | All |
| Change roster, assignments or grade policy | No | No | Yes |
| Provision/review/revoke portal accounts and links | No | No | Yes, unprivileged portal accounts only |
| Review fees or publish/withdraw reports | No | No | Yes |
| Read academic audit trail | No | No | Yes |

## Implementation and verification

- `models.py`: protected academic relationships, database uniqueness and mark/fee
  constraints. `forms.py`: field validation and bounded class formsets.
- `permissions.py`: active-account, role, first-password-change and manager gates.
- `services.py`: auditable state transitions, transaction boundaries, class-level
  locks and optimistic revision checks. Views do not save marks directly.
- `reports.py`: escaped, locally rendered, font-embedded PDFs and policy snapshots.
  PDFs are stored as private database blobs. There are no student PDFs in public
  `/media/` or `/static/` and no permanent bearer download tokens.
- `views.py` / `urls.py`: a namespaced `/portal/` UI. Every report request checks
  object access and current fee state. Portal pages, errors and PDFs receive
  `no-store, private`, noindex/noarchive, same-origin referrer and nosniff headers.
  Mutation endpoints require POST and Django CSRF. Login uses the existing Axes
  backend. Logout requires POST.
- SQLite is suitable for local functional tests. Production requires the
  existing transactional MySQL/MariaDB configuration (InnoDB); `select_for_update`
  is ineffective on SQLite. Class writes lock the parent class and explicit stream peers in primary-key
  order before roster, assignment, marks or report changes; fee writes lock the student. Stale marks,
  fee, policy and publication forms must be reviewed again before saving.

```sh
# Isolated SQLite tests, without changing the configured database:
DJANGO_DEBUG=True DATABASE_ENGINE=sqlite SQLITE_PATH=/tmp/hfhs-academics-test.sqlite3 \
  .venv/bin/python manage.py test academics --noinput

# In a configured non-production MySQL/MariaDB test environment:
python manage.py test academics

# Full regressions:
python manage.py test
```

The app tests cover the full report lifecycle, percentage and presence validation,
role/object isolation, CSRF, login lockout, password/session revocation, family
links, fee holds and restored debt, immutable grading snapshots, report previews,
PDF text/content, class roster changes, stale writes and audit events.

## Local demonstration data

Run `python manage.py seed_academic_demo` after migrations to create a fictional
review dataset in the configured **local development database**. The command
requires `DEBUG=True`, local-only allowed hosts and a local database host. It
refuses reserved-name collisions and preserves existing school records and report
policy. Rerunning it preserves passwords, marks and any changes made during review.

It creates 16 students in **Demo Form 1A** and **Demo Form 2A**, six subjects, all
four quarters and 32 generated PDFs. Quarter 1 is published, quarter 2 has private
generated previews, quarter 3 has complete submitted marks ready for generation,
and quarter 4 has editable drafts alongside submitted sheets. Absences,
exemptions, zero marks, access revocation and fee holds are represented.

The command prints a newly generated shared **local test password** on its first
successful run. It does not store a plaintext password in source or reset it on
subsequent runs. Sign in at `/portal/login/` using:

| Account | Review scenario |
| --- | --- |
| `demo.admin` | Academic administration, generation, publication, fees, policy and access reviews; no superuser permission |
| `demo.teacher.maths` | Mathematics and Physical Science; quarter 4 includes a partial editable maths sheet |
| `demo.teacher.languages` | English and Sesotho, including submitted sheets and an absence |
| `demo.teacher.humanities` | Geography and Religious Education; quarter 4 has blank editable sheets |
| `demo.parent` | Four linked children: released reports, M 1,250.50 outstanding, and zero balance awaiting clearance |
| `demo.parent.other` | A different family, with access only to its own linked student |
| `demo.student` | A student account with access to its own released report |
| `demo.firstlogin` | First-use password change, followed by family access |
| `demo.revoked` | A revoked student relationship: no student reports are visible |

All regular demo accounts skip the initial password change for convenient role
switching; `demo.firstlogin` explicitly exercises that step. The demo administrator
can use **Accounts & access** to reset passwords or require another password
change. Existing administrator credentials are not changed.
