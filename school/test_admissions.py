from datetime import date, time, timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import models
from django.test import TestCase, override_settings
from django.utils import timezone

from .forms import ApplicationForm
from .models import Application, SiteSettings
from .staff_forms import SettingsForm


TEST_STORAGE = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGE)
class AdmissionApplicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = SiteSettings.objects.create()

    def payload(self, **changes):
        return {
            'surname': 'Mokoena',
            'given_name': 'Lerato',
            'date_of_birth': '2013-03-05',
            'physical_address': '',
            'district': 'Maseru',
            'district_other': '',
            'current_school': 'Example Primary School',
            'guardian_name': 'Mpho Mokoena',
            'phone': '58881234',
            'boarding_required': 'no',
            'consent': 'on',
            **changes,
        }

    def test_public_questions_and_required_fields_match_admission_form(self):
        form = ApplicationForm(school=self.school)
        required_questions = {
            'surname', 'given_name', 'date_of_birth', 'district',
            'current_school', 'guardian_name', 'phone', 'boarding_required',
        }
        self.assertEqual(
            {name for name, field in form.fields.items() if field.required},
            required_questions | {'consent'},
        )
        self.assertEqual(
            set(form.fields),
            required_questions | {'physical_address', 'district_other', 'consent', 'website'},
        )
        self.assertEqual(form.fields['given_name'].label, 'Your name')
        self.assertEqual(form.fields['current_school'].label, 'Your primary school')
        self.assertIsInstance(form.fields['boarding_required'], forms.TypedChoiceField)
        self.assertIsInstance(form.fields['boarding_required'].widget, forms.RadioSelect)
        self.assertTrue(form.fields['website'].widget.is_hidden)

    def test_every_source_question_requires_an_answer_but_address_is_optional(self):
        form = ApplicationForm(self.payload(), school=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        for field in (
            'surname', 'given_name', 'date_of_birth', 'district',
            'current_school', 'guardian_name', 'phone', 'boarding_required',
        ):
            with self.subTest(field=field):
                form = ApplicationForm(self.payload(**{field: ''}), school=self.school)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_district_options_cover_lesotho_and_other(self):
        choices = dict(ApplicationForm(school=self.school).fields['district'].choices)
        choices.pop('', None)
        self.assertEqual(set(choices), {
            'Berea', 'Botha-Bothe', 'Leribe', 'Mafeteng', 'Maseru',
            "Mohale's Hoek", 'Mokhotlong', "Qacha's Nek", 'Quthing',
            'Thaba-Tseka', 'Other',
        })

    def test_other_district_requires_details_and_is_saved(self):
        form = ApplicationForm(self.payload(district='Other'), school=self.school)
        self.assertFalse(form.is_valid())
        self.assertIn('district_other', form.errors)

        form = ApplicationForm(
            self.payload(district='Other', district_other='Outside Lesotho'),
            school=self.school,
        )
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        application.refresh_from_db()
        self.assertEqual(application.district, 'Other')
        self.assertEqual(application.district_other, 'Outside Lesotho')

    def test_known_district_discards_stale_other_details(self):
        form = ApplicationForm(
            self.payload(district='Maseru', district_other='Previous other answer'),
            school=self.school,
        )
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save()
        application.refresh_from_db()
        self.assertEqual(application.district_other, '')

    def test_boarding_choices_are_saved_as_booleans(self):
        for answer, expected in [('no', False), ('yes', True)]:
            with self.subTest(answer=answer):
                form = ApplicationForm(self.payload(boarding_required=answer), school=self.school)
                self.assertTrue(form.is_valid(), form.errors)
                application = form.save()
                application.refresh_from_db()
                self.assertIs(application.boarding_required, expected)

    def test_maximum_length_names_fit_the_derived_legacy_name(self):
        surname = 'S' * 80
        given_name = 'G' * 80
        form = ApplicationForm(
            self.payload(surname=surname, given_name=given_name), school=self.school,
        )
        self.assertTrue(form.is_valid(), form.errors)
        application = form.save(commit=False)
        # Full model validation also checks the MySQL column length before save.
        application.full_clean()
        application.save()
        application.refresh_from_db()
        self.assertEqual(application.learner_name, f'{given_name} {surname}')
        self.assertEqual(application.surname, surname)
        self.assertEqual(application.given_name, given_name)

    def test_malformed_choices_and_dates_are_rejected(self):
        for changes, expected_field in [
            ({'district': 'Unrecognised district'}, 'district'),
            ({'boarding_required': 'maybe'}, 'boarding_required'),
            ({'date_of_birth': 'not-a-date'}, 'date_of_birth'),
            ({'date_of_birth': '2013-02-30'}, 'date_of_birth'),
            ({'date_of_birth': '1899-12-31'}, 'date_of_birth'),
            ({'date_of_birth': timezone.localdate().isoformat()}, 'date_of_birth'),
            ({'date_of_birth': (timezone.localdate() + timedelta(days=1)).isoformat()}, 'date_of_birth'),
        ]:
            with self.subTest(changes=changes):
                form = ApplicationForm(self.payload(**changes), school=self.school)
                self.assertFalse(form.is_valid())
                self.assertIn(expected_field, form.errors)
        self.assertFalse(Application.objects.exists())

    def test_oversized_answers_are_rejected(self):
        for changes, expected_field in [
            ({'physical_address': 'A' * 1001}, 'physical_address'),
            ({'district': 'Other', 'district_other': 'A' * 121}, 'district_other'),
            ({'surname': 'A' * 81}, 'surname'),
            ({'given_name': 'A' * 81}, 'given_name'),
            ({'current_school': 'A' * 181}, 'current_school'),
            ({'guardian_name': 'A' * 161}, 'guardian_name'),
            ({'phone': '5' * 41}, 'phone'),
        ]:
            with self.subTest(field=expected_field):
                form = ApplicationForm(self.payload(**changes), school=self.school)
                self.assertFalse(form.is_valid())
                self.assertIn(expected_field, form.errors)
        self.assertFalse(Application.objects.exists())

    def test_submission_uses_school_cycle_and_ignores_client_cycle_or_legacy_fields(self):
        self.school.admissions_grade = 'Grade 9'
        self.school.admissions_year = 2028
        self.school.save()
        response = self.client.post('/apply/', self.payload(
            entry_level='Form 5', application_year=2099,
            admissions_grade='Form 5', admissions_year=2099,
            learner_name='Injected learner', email='injected@example.com',
            message='Injected legacy message',
        ))
        self.assertRedirects(response, '/apply/received/', fetch_redirect_response=False)
        application = Application.objects.get()
        self.assertEqual(application.learner_name, 'Lerato Mokoena')
        self.assertEqual(application.surname, 'Mokoena')
        self.assertEqual(application.given_name, 'Lerato')
        self.assertEqual(application.entry_level, 'Grade 9')
        self.assertEqual(application.application_year, 2028)
        self.assertEqual(application.email, '')
        self.assertEqual(application.message, '')
        self.assertIs(application.boarding_required, False)

        self.school.admissions_grade = 'Grade 8'
        self.school.admissions_year = 2029
        self.school.save()
        application.refresh_from_db()
        self.assertEqual(application.entry_level, 'Grade 9')
        self.assertEqual(application.application_year, 2028)


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGE)
class AdmissionSettingsTests(TestCase):
    def settings_payload(self, school, omit=()):
        return {
            name: getattr(school, name)
            for name in SettingsForm._meta.fields
            if name not in omit and not isinstance(school._meta.get_field(name), models.ImageField)
        }

    def test_published_admission_details_have_structured_source_defaults(self):
        school = SiteSettings.objects.create()
        self.assertEqual(school.admissions_grade, 'Grade 8')
        self.assertEqual(school.admissions_year, 2027)
        self.assertEqual(school.admissions_fee, Decimal('50.00'))
        self.assertIn('non-refundable', school._meta.get_field('admissions_fee').help_text.lower())
        self.assertEqual(school.admissions_payment_method.lower(), 'm-pesa')
        self.assertEqual(school.admissions_merchant_number, '5184')
        self.assertEqual(school.admissions_deadline, date(2026, 10, 14))
        self.assertEqual(school.admissions_interview_date, date(2026, 10, 17))
        self.assertEqual(school.admissions_interview_time, time(8, 0))
        self.assertEqual(school.admissions_interview_location, 'Holy Family High School')
        for subject in ['English', 'Sesotho', 'Science', 'Maths']:
            self.assertIn(subject, school.admissions_interview_subjects)
        for item in ['pen', 'pencil', 'mathematical instruments']:
            self.assertIn(item, school.admissions_stationery_note.lower())

    def test_admission_details_can_be_edited_in_school_settings(self):
        school = SiteSettings.objects.create()
        changes = {
            'admissions_grade': 'Grade 9',
            'admissions_year': 2028,
            'admissions_fee': Decimal('60.00'),
            'admissions_payment_method': 'Bank transfer',
            'admissions_merchant_number': '1234',
            'admissions_deadline': date(2027, 10, 14),
            'admissions_interview_date': date(2027, 10, 17),
            'admissions_interview_time': time(9, 30),
            'admissions_interview_location': 'School hall',
            'admissions_interview_subjects': 'English and Mathematics',
            'admissions_stationery_note': 'Bring a pen and pencil.',
        }
        form = SettingsForm({**self.settings_payload(school), **changes}, instance=school)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        school.refresh_from_db()
        for name, value in changes.items():
            with self.subTest(field=name):
                self.assertEqual(getattr(school, name), value)

    def test_older_settings_submission_preserves_new_admission_details(self):
        school = SiteSettings.objects.create(
            admissions_grade='Grade 9', admissions_year=2028,
            admissions_fee=Decimal('60.00'), admissions_payment_method='Bank transfer',
            admissions_merchant_number='1234', admissions_deadline=date(2027, 10, 14),
            admissions_interview_date=date(2027, 10, 17), admissions_interview_time=time(9, 30),
            admissions_interview_location='School hall',
            admissions_interview_subjects='English and Mathematics',
            admissions_stationery_note='Bring a pen and pencil.',
        )
        new_fields = (
            'admissions_grade', 'admissions_year', 'admissions_fee',
            'admissions_payment_method', 'admissions_merchant_number', 'admissions_deadline',
            'admissions_interview_date', 'admissions_interview_time',
            'admissions_interview_location', 'admissions_interview_subjects',
            'admissions_stationery_note',
        )
        before = {name: getattr(school, name) for name in new_fields}
        data = self.settings_payload(school, omit=new_fields)
        data['hero_title'] = 'Updated homepage title'
        form = SettingsForm(data, instance=school)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        school.refresh_from_db()
        self.assertEqual(school.hero_title, 'Updated homepage title')
        for name, value in before.items():
            with self.subTest(field=name):
                self.assertEqual(getattr(school, name), value)


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGE)
class AdmissionStaffReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_staff_groups', verbosity=0)
        cls.school = SiteSettings.objects.create()
        cls.officer = User.objects.create_user('admission-officer', is_staff=True)
        cls.officer.groups.add(Group.objects.get(name='Admissions officers'))
        cls.editor = User.objects.create_user('admission-editor', is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Content editors'))
        cls.historical = Application.objects.create(
            learner_name='Historic Learner', date_of_birth=date(2012, 1, 1),
            entry_level='Form 1', current_school='Historic Primary School',
            guardian_name='Historic Guardian', email='historic@example.com',
            phone='58889999', message='Historic application message', consent=True,
        )
        cls.application = Application.objects.create(
            learner_name='Lerato Mokoena', surname='Mokoena', given_name='Lerato',
            date_of_birth=date(2013, 3, 5), entry_level='Grade 8', application_year=2027,
            physical_address='Private address for review', district='Other',
            district_other='Private district for review', current_school='Example Primary School',
            guardian_name='Mpho Mokoena', phone='58881234', boarding_required=False, consent=True,
        )

    def test_historical_application_remains_readable_without_new_answers(self):
        self.client.force_login(self.officer)
        response = self.client.get(f'/staff/applications/{self.historical.pk}/')
        for value in (
            'Historic Learner', 'Form 1', 'Historic Primary School',
            'Historic Guardian', 'historic@example.com', 'Historic application message',
        ):
            self.assertContains(response, value)
        self.assertIsNone(self.historical.boarding_required)
        self.assertIsNone(self.historical.application_year)

    def test_new_private_answers_are_visible_only_to_admission_staff(self):
        path = f'/staff/applications/{self.application.pk}/'
        self.assertEqual(self.client.get(path).status_code, 302)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get('/staff/applications/').status_code, 403)
        self.client.force_login(self.officer)
        response = self.client.get(path)
        for value in ('Grade 8', '2027', 'Private address for review', 'Private district for review'):
            self.assertContains(response, value)
        for path in ['/', '/apply/']:
            response = self.client.get(path)
            self.assertNotContains(response, 'Private address for review')
            self.assertNotContains(response, 'Private district for review')

    def test_review_cannot_change_new_application_answers_or_cycle(self):
        self.client.force_login(self.officer)
        path = f'/staff/applications/{self.application.pk}/'
        response = self.client.post(path, {
            'status': 'reviewing', 'staff_notes': 'Arrange follow-up',
            'surname': 'Changed', 'given_name': 'Changed',
            'physical_address': 'Changed', 'district': 'Maseru', 'district_other': '',
            'boarding_required': 'yes', 'entry_level': 'Grade 9', 'application_year': 2028,
        })
        self.assertRedirects(response, path, fetch_redirect_response=False)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'reviewing')
        self.assertEqual(self.application.staff_notes, 'Arrange follow-up')
        self.assertEqual(self.application.surname, 'Mokoena')
        self.assertEqual(self.application.given_name, 'Lerato')
        self.assertEqual(self.application.physical_address, 'Private address for review')
        self.assertEqual(self.application.district, 'Other')
        self.assertEqual(self.application.district_other, 'Private district for review')
        self.assertIs(self.application.boarding_required, False)
        self.assertEqual(self.application.entry_level, 'Grade 8')
        self.assertEqual(self.application.application_year, 2027)
