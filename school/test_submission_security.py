from datetime import timedelta
from importlib import import_module
import uuid

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .forms import ApplicationForm, ContactForm
from .models import Application, ContactMessage, SiteSettings, SubmissionAttempt, SubmissionThrottle
from .submissions import consume_limit, rate_subject


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SubmissionSecurityTests(TestCase):
    def setUp(self):
        self.school = SiteSettings.objects.create()
        self.payload = dict(given_name='Lerato', surname='Mokoena', date_of_birth='2013-03-05',
                            district='Maseru', current_school='Example Primary', guardian_name='Mpho Mokoena',
                            phone='58881234', boarding_required='no', consent='on')
        self.contact = dict(name='Jane Example', email='jane@example.com', phone='',
                            subject='School enquiry', message='Please contact me.', consent='on')

    def test_normalization_and_optional_email_are_saved_once(self):
        response = self.client.post('/apply/', {**self.payload, 'given_name': '  lERATO\tANNA  ',
            'surname': '  o’NEILL-mOKOENA ', 'guardian_name': '  mPHO   mOKOENA ',
            'email': ' GUARDIAN@EXAMPLE.COM ', 'current_school': ' Primary   School ', 'phone': ' 58881234 '})
        self.assertEqual(response.status_code, 302)
        record = Application.objects.get()
        self.assertEqual(record.given_name, 'Lerato Anna')
        self.assertEqual(record.surname, "O'Neill-Mokoena")
        self.assertEqual(record.learner_name, "Lerato Anna O'Neill-Mokoena")
        self.assertEqual(record.guardian_name, 'Mpho Mokoena')
        self.assertEqual(record.email, 'guardian@example.com')
        self.assertEqual(record.current_school, 'Primary School')
        self.assertEqual(record.phone, '58881234')
        self.assertRegex(record.reference, rf'^HFHS-{self.school.admissions_year}-[A-F0-9]{{24}}$')
        reference = record.reference
        record.status = 'reviewing'
        record.save()
        self.assertEqual(record.reference, reference)

    def test_duplicate_changes_to_contact_details_do_not_bypass_identity(self):
        self.assertEqual(self.client.post('/apply/', self.payload).status_code, 302)
        original = Application.objects.get()
        response = Client().post('/apply/', {**self.payload, 'given_name': ' LERATO ', 'surname': ' MOKOENA ',
                                 'phone': '59999999', 'email': 'other@example.com', 'boarding_required': 'yes'})
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'already been received', status_code=409)
        self.assertNotContains(response, original.reference, status_code=409)
        self.assertEqual(Application.objects.count(), 1)
        self.assertEqual(original.phone, '58881234')

    def test_database_rejects_racing_forms_but_siblings_and_later_intakes_are_allowed(self):
        first = ApplicationForm(self.payload, school=self.school)
        second = ApplicationForm(self.payload, school=self.school)
        self.assertTrue(first.is_valid(), first.errors)
        self.assertTrue(second.is_valid(), second.errors)
        first.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.save()
        sibling = ApplicationForm({**self.payload, 'given_name': 'Anna'}, school=self.school)
        self.assertTrue(sibling.is_valid(), sibling.errors)
        sibling.save()
        self.school.admissions_year += 1
        next_intake = ApplicationForm(self.payload, school=self.school)
        self.assertTrue(next_intake.is_valid(), next_intake.errors)
        next_intake.save()
        self.assertEqual(Application.objects.count(), 3)
        self.assertEqual(len(set(Application.objects.values_list('reference', flat=True))), 3)

    def test_contact_normalization_validation_honeypot_and_escaping(self):
        self.client.post('/contact/', {**self.contact, 'name': ' JANE   eXAMPLE ', 'email': ' JANE@EXAMPLE.COM ',
                                      'message': '  First line. \r\n Second line.  '})
        record = ContactMessage.objects.get()
        self.assertEqual(record.name, 'Jane Example')
        self.assertEqual(record.email, 'jane@example.com')
        self.assertEqual(record.message, 'First line.\nSecond line.')
        for changes in [{'website': 'spam'}, {'email': 'not-an-email'}, {'consent': ''}]:
            form = ContactForm({**self.contact, **changes})
            self.assertFalse(form.is_valid())
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_invalid_attempts_are_counted_across_clients_and_forged_headers(self):
        for _ in range(5):
            self.assertEqual(Client().post('/apply/', {}, HTTP_X_FORWARDED_FOR='198.51.100.1').status_code, 200)
        response = Client().post('/apply/', self.payload, HTTP_X_FORWARDED_FOR='198.51.100.2')
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response['Retry-After']), 0)
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertFalse(Application.objects.exists())
        keys = list(SubmissionThrottle.objects.values_list('key', flat=True))
        self.assertTrue(all(len(key) == 64 and '127.0.0.1' not in key for key in keys))
        count = SubmissionThrottle.objects.count()
        for _ in range(5):
            self.client.post('/apply/', {})
        self.assertEqual(SubmissionThrottle.objects.count(), count)
        self.assertFalse(SubmissionAttempt.objects.exists())

    @override_settings(PUBLIC_FORM_RATE_PER_DAY=3)
    def test_combined_daily_limit_and_get_requests(self):
        for url in ['/apply/', '/contact/', '/apply/']:
            self.client.post(url, {})
        self.assertEqual(self.client.post('/contact/', self.contact).status_code, 429)
        self.assertEqual(self.client.get('/contact/').status_code, 200)
        self.assertEqual(self.client.get('/apply/').status_code, 200)

    @override_settings(FORM_WRITE_RATE_PER_MINUTE=2)
    def test_other_form_writes_are_limited_and_safe_methods_remain_available(self):
        self.client.post('/staff/login/', {})
        self.client.post('/staff/login/', {})
        self.assertEqual(self.client.post('/staff/login/', {}).status_code, 429)
        self.assertEqual(self.client.get('/staff/login/').status_code, 200)

    def test_csrf_failures_consume_limits_and_never_create_records(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/apply/', self.payload).status_code, 403)
        self.assertTrue(SubmissionThrottle.objects.exists())
        self.assertFalse(Application.objects.exists())

    def test_payload_limits_parameter_pollution_and_public_uploads(self):
        cases = [
            ({'data': 'name=Jane&name=Joe', 'content_type': 'application/x-www-form-urlencoded'}, 400),
            ({'data': '{}', 'content_type': 'application/json'}, 415),
            ({'data': {'file': SimpleUploadedFile('test.txt', b'test')}}, 400),
            ({'data': 'a' * 65537, 'content_type': 'application/x-www-form-urlencoded'}, 413),
        ]
        for index, (kwargs, status) in enumerate(cases):
            with self.subTest(status=status):
                response = self.client.post('/contact/', REMOTE_ADDR=f'198.51.100.{index}', **kwargs)
                self.assertEqual(response.status_code, status)
        self.assertFalse(ContactMessage.objects.exists())

    def test_atomic_counters_reset_and_ipv6_addresses_share_a_network_allowance(self):
        now = timezone.now()
        self.assertEqual(consume_limit('subject', 'test', 1, 60, now), 0)
        self.assertEqual(consume_limit('subject', 'test', 1, 60, now), 60)
        self.assertEqual(consume_limit('subject', 'test', 1, 60, now + timedelta(seconds=60)), 0)
        self.assertEqual(SubmissionThrottle.objects.count(), 1)
        self.assertEqual(rate_subject('2001:db8::1'), rate_subject('2001:db8::ffff'))
        self.assertNotEqual(rate_subject('2001:db8::1'), rate_subject('2001:db8:0:1::1'))

    def test_purge_removes_only_long_expired_counters(self):
        consume_limit('old', 'test', 1, 60, timezone.now()-timedelta(days=2))
        consume_limit('active', 'test', 1, 60)
        call_command('purge_submission_attempts', verbosity=0)
        self.assertEqual(SubmissionThrottle.objects.count(), 1)

    def test_backfill_preserves_issued_references_and_historical_duplicate_records(self):
        first = ApplicationForm(self.payload, school=self.school)
        self.assertTrue(first.is_valid())
        record = first.save()
        original_uuid = uuid.uuid4()
        Application.objects.filter(pk=record.pk).update(reference=original_uuid.hex, duplicate_key=None)
        original_pk = record.pk
        record.pk = None
        record.reference = str(uuid.uuid4())
        record.given_name = 'Another'
        record.save()
        Application.objects.filter(pk=record.pk).update(given_name=' LERATO ', duplicate_key=None)
        backfill = import_module('school.migrations.0015_submissionthrottle_application_duplicate_key_and_more').backfill_identity_and_preserve_references
        backfill(apps, connection.schema_editor())
        self.assertEqual(Application.objects.get(pk=original_pk).reference, str(original_uuid))
        self.assertEqual(Application.objects.filter(duplicate_key__isnull=False).count(), 1)
        self.assertEqual(Application.objects.count(), 2)
