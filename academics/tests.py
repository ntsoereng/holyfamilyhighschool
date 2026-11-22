from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.urls import reverse

from school.models import SiteSettings
from . import forms, services
from .models import (AcademicSubject, AuditEvent, Enrollment, FamilyAccess, FeeClearance, Mark,
    PortalAccount, ReportingPeriod, ReportDetails, ReportPolicy, SchoolClass, Student, StudentReport, TeachingAssignment)


@override_settings(SECURE_SSL_REDIRECT=False, AXES_ENABLED=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class AcademicWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = 'Temporary-school-access-382!'
        cls.owner = User.objects.create_superuser('academic-owner', 'owner@example.com', cls.password)
        cls.editor = User.objects.create_user('website-editor', password=cls.password, is_staff=True)
        cls.manager = User.objects.create_user('report-manager', password=cls.password, is_staff=True)
        cls.manager.user_permissions.add(Permission.objects.get(codename='manage_academics'))
        cls.teacher_user = User.objects.create_user('teacher-one', password=cls.password)
        cls.teacher = PortalAccount.objects.create(user=cls.teacher_user, role='teacher', must_change_password=False)
        cls.other_teacher = PortalAccount.objects.create(user=User.objects.create_user('teacher-two', password=cls.password), role='teacher', must_change_password=False)
        cls.family_user = User.objects.create_user('family-one', password=cls.password)
        cls.family = PortalAccount.objects.create(user=cls.family_user, role='family', must_change_password=False)
        cls.other_family = PortalAccount.objects.create(user=User.objects.create_user('family-two', password=cls.password), role='family', must_change_password=False)
        cls.classroom = SchoolClass.objects.create(name='Form 1A', year=2026)
        cls.other_class = SchoolClass.objects.create(name='Form 1B', year=2026)
        cls.period = ReportingPeriod.objects.create(year=2026, quarter=1)
        cls.subject = AcademicSubject.objects.create(name='Mathematics')
        cls.student = Student.objects.create(admission_number='HF-0001', full_name='Mpho Mokoena')
        cls.other_student = Student.objects.create(admission_number='HF-0002', full_name='Lerato Mohapi')
        cls.enrollment = Enrollment.objects.create(student=cls.student, classroom=cls.classroom)
        cls.other_enrollment = Enrollment.objects.create(student=cls.other_student, classroom=cls.classroom)
        cls.grant = FamilyAccess.objects.create(account=cls.family, student=cls.student, relationship='parent')
        cls.assignment = TeachingAssignment.objects.create(teacher=cls.teacher, classroom=cls.classroom, period=cls.period, subject=cls.subject)
        SiteSettings.objects.create(phone='+266 5550 0000', email='office@example.com', address='School office, Leribe')

    def rows(self, first='81.25', second='62.00'):
        return [{'enrollment': e.pk, 'status': 'scored', 'score': Decimal(score), 'comment': 'Progressing well.'}
                for e, score in [(self.enrollment, first), (self.other_enrollment, second)]]

    def submit(self):
        services.save_sheet(self.teacher_user, self.assignment.pk, 0, self.rows(), submit=True)

    def generate(self, publish=False, clear=False):
        self.submit()
        services.generate_reports(self.owner, self.classroom, self.period)
        reports = StudentReport.objects.filter(period=self.period)
        if publish:
            services.publish_reports(self.owner, self.classroom, self.period, 'publish', {str(r.pk): r.revision for r in reports})
        if clear:
            services.update_fees(self.owner, self.student, self.period, 0, {'outstanding': Decimal('0'), 'cleared': True, 'note': 'Verified office ledger.'})
        return StudentReport.objects.get(enrollment=self.enrollment, period=self.period)

    def test_sample_quarter_three_calculations_and_pdf(self):
        from .reports import make_snapshot
        import pypdfium2 as pdfium
        entries = [
            ('0175', 'English Language', [42, 76, 70], 63, 'D+', 'Good'),
            ('0176', 'Sesotho', [64, 56, 61], 60, 'D+', 'Good'),
            ('0178', 'Mathematics', [65, 84, 56], 68, 'C', 'Much Better'),
            ('0180', 'Biology', [53, 71, 59], 61, 'D+', 'Good'),
            ('0181', 'Physical Science', [62, 68, 69], 66, 'C', 'Much Better'),
            ('0186', 'Religious Studies', [92, 82, 81], 85, 'A', 'Super'),
            ('0187', 'Accounting', [62, 64, 57], 61, 'D+', 'Good'),
            ('0190', 'ICT', [60, 63, 78], 67, 'C', 'Much Better'),
            ('2030', 'LBSE', [49, 48, 73], 57, 'D', 'Fair'),
        ]
        periods = [self.period] + [ReportingPeriod.objects.create(year=2026, quarter=q) for q in [2, 3]]
        current, history = [], []
        for code, name, values, final, grade, remark in entries:
            subject, _ = AcademicSubject.objects.update_or_create(name=name, defaults={'code': code, 'include_in_summary': name != 'LBSE'})
            for period, value in zip(periods, values):
                assignment, _ = TeachingAssignment.objects.update_or_create(classroom=self.classroom, period=period, subject=subject,
                    defaults={'teacher': self.teacher, 'status': 'submitted'})
                for enrollment in [self.enrollment, self.other_enrollment]:
                    mark = Mark.objects.create(assignment=assignment, enrollment=enrollment, score=value)
                    if enrollment == self.enrollment:
                        (current if period.quarter == 3 else history).append(mark)
        details = ReportDetails.objects.create(enrollment=self.enrollment, period=periods[2], days_absent=0,
            class_teacher_remark='Apply more effort.', principal_remark='Capable of better performance.')
        policy = ReportPolicy()
        snap = make_snapshot(self.enrollment, periods[2], current, policy, SiteSettings.objects.first(), history, details)
        self.assertEqual(snap['quarter_averages'], ['62.5', '70.5', '66.4'])
        self.assertEqual(snap['average'], '66.4')
        self.assertEqual(snap['subjects_passed'], 8)
        self.assertEqual(snap['performance_level'], 'PROFICIENT')
        self.assertEqual(snap['excluded_subjects'], ['LBSE'])
        for row, entry in zip(snap['rows'], entries):
            self.assertEqual((row['score'], row['grade'], row['teacher_remark']), (str(entry[3]), entry[4], entry[5]))
        policy.result_basis = 'final'
        final_snap = make_snapshot(self.enrollment, periods[2], current, policy, SiteSettings.objects.first(), history)
        self.assertEqual(final_snap['average'], '66.4')
        services.generate_reports(self.owner, self.classroom, periods[2])
        report = StudentReport.objects.get(enrollment=self.enrollment, period=periods[2])
        self.assertEqual(report.snapshot['class_rank'], {'position': 1, 'total': 2})
        document = pdfium.PdfDocument(bytes(report.pdf))
        self.assertEqual(len(document), 1)
        content = document[0].get_textpage().get_text_range()
        for value in ['0175', 'Quarter 3', '66.4', 'PROFICIENT', 'Apply more effort.', 'LBSE']:
            self.assertIn(value, content)
        document.close()
        self.client.force_login(self.owner)
        response = self.client.get(reverse('academics:report', args=[report.pk]))
        self.assertContains(response, "Teacher's remarks")
        self.assertContains(response, 'Apply more effort.')
        # Reopening Q1 also withdraws cumulative Q3 reports.
        services.review_assignment(self.owner, self.assignment.pk, 0, 'reopen', 'Correct an earlier mark.')
        report.refresh_from_db()
        self.assertFalse(report.valid)

    def test_zero_history_and_result_basis_are_distinct_from_missing_marks(self):
        from .reports import make_snapshot
        second = ReportingPeriod.objects.create(year=2026, quarter=2)
        assignment = TeachingAssignment.objects.create(teacher=self.teacher, classroom=self.classroom, period=second, subject=self.subject)
        history = [Mark(assignment=self.assignment, enrollment=self.enrollment, score=Decimal('0'))]
        current = [Mark(assignment=assignment, enrollment=self.enrollment, score=Decimal('100'))]
        policy = ReportPolicy()
        snap = make_snapshot(self.enrollment, second, current, policy, SiteSettings.objects.first(), history)
        self.assertEqual(snap['rows'][0]['quarter_scores'], ['0', '100'])
        self.assertEqual(snap['rows'][0]['score'], '50')
        self.assertEqual(snap['subjects_passed'], 1)
        self.assertEqual(snap['performance_level'], 'ADVANCE')
        policy.result_basis = 'final'
        snap = make_snapshot(self.enrollment, second, current, policy, SiteSettings.objects.first(), history)
        self.assertEqual(snap['performance_level'], 'BASIC')
        snap = make_snapshot(self.enrollment, second, current, policy, SiteSettings.objects.first())
        self.assertEqual(snap['rows'][0]['quarter_scores'][0], 'Not recorded')
        self.assertEqual(snap['rows'][0]['score'], '100')

    def test_lookup_migration_preserves_custom_policy_and_stored_snapshots(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection
        migration = import_module('academics.migrations.0003_adopt_sample_grading_lookup')
        policy = ReportPolicy.objects.create(bands=[{'minimum': 0, 'grade': 'Custom', 'description': 'School approved'}])
        editor = SimpleNamespace(connection=connection)
        migration.adopt_sample_lookup(apps, editor)
        policy.refresh_from_db()
        self.assertEqual(policy.bands[0]['grade'], 'Custom')
        policy.bands = [
            {'minimum': 80, 'grade': 'A', 'description': 'Excellent'},
            {'minimum': 70, 'grade': 'B', 'description': 'Very good'},
            {'minimum': 60, 'grade': 'C', 'description': 'Good'},
            {'minimum': 50, 'grade': 'D', 'description': 'Satisfactory'},
            {'minimum': 40, 'grade': 'E', 'description': 'Needs improvement'},
            {'minimum': 0, 'grade': 'F', 'description': 'Needs support'},
        ]
        policy.save()
        snapshot = {'heading': 'Stored historical report', 'rows': [{'grade': 'A'}]}
        report = StudentReport.objects.create(enrollment=self.enrollment, period=self.period, snapshot=snapshot, pdf=b'%PDF-stored')
        migration.adopt_sample_lookup(apps, editor)
        policy.refresh_from_db()
        report.refresh_from_db()
        self.assertEqual(policy.bands[0]['grade'], 'A*')
        self.assertEqual(policy.revision, 2)
        self.assertEqual(report.snapshot, snapshot)
        self.assertEqual(bytes(report.pdf), b'%PDF-stored')

    def test_lookup_dropdown_validation_and_automatic_remark(self):
        from .reports import grade_for
        policy = ReportPolicy()
        self.assertEqual(grade_for(Decimal('89.99'), policy.bands)['grade'], 'A')
        self.assertEqual(grade_for(Decimal('90'), policy.bands)['grade'], 'A*')
        self.assertEqual(grade_for(Decimal('0'), policy.bands)['grade'], 'U')
        row = {'enrollment': self.enrollment.pk, 'status': 'scored', 'score': 70, 'teacher_remark': 'Good Work'}
        self.assertTrue(forms.MarkRowForm(row).is_valid())
        row['teacher_remark'] = 'Unapproved remark'
        self.assertFalse(forms.MarkRowForm(row).is_valid())
        with self.assertRaises(ValidationError):
            services.save_sheet(self.teacher_user, self.assignment.pk, 0, [row, self.rows()[1]])
        self.assertFalse(Mark.objects.exists())
        rows = self.rows()
        rows[0]['teacher_remark'] = 'Keep It Up'
        services.save_sheet(self.teacher_user, self.assignment.pk, 0, rows, submit=True)
        services.generate_reports(self.owner, self.classroom, self.period)
        report = StudentReport.objects.get(enrollment=self.enrollment)
        self.assertEqual(report.snapshot['rows'][0]['teacher_remark'], 'Keep It Up')
        self.assertEqual(report.snapshot['rows'][0]['quarter_scores'], ['81.25'])
        self.assertEqual(report.snapshot['rows'][0]['score'], '81')
        self.client.force_login(self.teacher_user)
        self.assertContains(self.client.get(reverse('academics:sheet', args=[self.assignment.pk])), 'Keep It Up')

    def test_report_details_access_stale_writes_and_blank_attendance(self):
        report = self.generate(publish=True)
        url = reverse('academics:report-details', args=[self.enrollment.pk, self.period.pk])
        for user in [self.teacher_user, self.family_user]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {'revision': 0, 'days_absent': 0, 'class_teacher_remark': 'Apply more effort.', 'principal_remark': 'Good progress.'})
        self.assertEqual(response.status_code, 302)
        record = ReportDetails.objects.get(enrollment=self.enrollment)
        self.assertEqual(record.days_absent, 0)
        report.refresh_from_db()
        self.assertFalse(report.valid)
        self.assertFalse(report.published)
        self.assertEqual(self.client.post(url, {'revision': 0, 'days_absent': 4}).status_code, 409)
        self.assertEqual(self.client.post(url, {'revision': 1, 'days_absent': -1}).status_code, 200)
        self.assertEqual(self.client.post(url, {'revision': 1, 'days_absent': ''}).status_code, 302)
        record.refresh_from_db()
        self.assertIsNone(record.days_absent)

    def test_metadata_edit_can_configure_existing_subject_and_reject_stale_edit(self):
        report = self.generate()
        url = reverse('academics:setup-edit', args=['subjects', self.subject.pk])
        self.client.force_login(self.owner)
        response = self.client.get(url)
        token = response.context['form'].fields['edit_token'].initial
        values = {'name': 'Injected identity', 'code': '0178', 'edit_token': token}
        self.assertEqual(self.client.post(url, values).status_code, 302)
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.name, 'Mathematics')
        self.assertEqual(self.subject.code, '0178')
        self.assertFalse(self.subject.include_in_summary)
        report.refresh_from_db()
        self.assertFalse(report.valid)
        self.assertEqual(self.client.post(url, dict(values, code='9999')).status_code, 409)
        self.subject.refresh_from_db()
        self.assertEqual(self.subject.code, '0178')
        for section, obj in [('students', self.student), ('classes', self.classroom), ('periods', self.period)]:
            self.assertEqual(self.client.get(reverse('academics:setup-edit', args=[section, obj.pk])).status_code, 200)
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.post(url, values).status_code, 403)

    def test_stream_ranking_uses_complete_peer_sheets_and_ties(self):
        self.classroom.stream = self.other_class.stream = 'Form 1'
        self.classroom.save()
        self.other_class.save()
        peer = Enrollment.objects.create(student=Student.objects.create(full_name='Peer', admission_number='PEER-1'), classroom=self.other_class)
        assignment = TeachingAssignment.objects.create(teacher=self.other_teacher, classroom=self.other_class, period=self.period, subject=self.subject)
        self.submit()
        services.generate_reports(self.owner, self.classroom, self.period)
        report = StudentReport.objects.get(enrollment=self.enrollment)
        self.assertIsNone(report.snapshot['stream_rank']['position'])
        services.save_sheet(self.other_teacher.user, assignment.pk, 0, [{'enrollment': peer.pk, 'status': 'scored', 'score': Decimal('81.25')}], submit=True)
        report.refresh_from_db()
        self.assertFalse(report.valid)
        services.generate_reports(self.owner, self.classroom, self.period)
        report.refresh_from_db()
        self.assertEqual(report.snapshot['stream_rank'], {'position': 1, 'total': 3})
        second = StudentReport.objects.get(enrollment=self.other_enrollment)
        self.assertEqual(second.snapshot['stream_rank'], {'position': 3, 'total': 3})

    def test_publication_date_is_written_to_snapshot_and_pdf(self):
        report = self.generate()
        self.assertIsNone(report.snapshot['published_at'])
        services.publish_reports(self.owner, self.classroom, self.period, 'publish', {str(r.pk): r.revision for r in StudentReport.objects.all()})
        report.refresh_from_db()
        self.assertIsNotNone(report.snapshot['published_at'])
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(bytes(report.pdf))
        text = pdf[0].get_textpage().get_text_range()
        self.assertIn(report.snapshot['published_at'], text)
        self.assertNotIn('Awaiting publication', text)
        pdf.close()


    def test_anonymous_portal_and_all_office_routes_require_login(self):
        for url in ['/portal/', '/portal/office/', '/portal/office/accounts/', '/portal/office/policy/', '/portal/office/audit/', f'/portal/marks/{self.assignment.pk}/']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn('/portal/login/', response.url)

    def test_editor_teacher_family_cannot_access_any_office_writes(self):
        urls = ['/portal/office/', '/portal/office/accounts/', '/portal/office/policy/', '/portal/office/audit/',
                '/portal/office/setup/students/', '/portal/office/setup/assignments/',
                f'/portal/office/fees/{self.enrollment.pk}/{self.period.pk}/', f'/portal/office/family-access/{self.grant.pk}/']
        for user in [self.editor, self.teacher_user, self.family_user]:
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 403, (user, url))
                self.assertIn(self.client.post(url, {}).status_code, [403, 405], (user, url))

    def test_manager_can_render_all_setup_review_pages(self):
        self.client.force_login(self.manager)
        urls = ['/portal/office/', '/portal/office/accounts/', '/portal/office/policy/', '/portal/office/audit/',
                f'/portal/office/accounts/{self.teacher.pk}/', f'/portal/office/family-access/{self.grant.pk}/',
                f'/portal/office/periods/{self.period.pk}/', f'/portal/marks/{self.assignment.pk}/',
                f'/portal/office/fees/{self.enrollment.pk}/{self.period.pk}/',
                f'/portal/office/reports/?classroom={self.classroom.pk}&period={self.period.pk}']
        urls += [f'/portal/office/setup/{s}/' for s in ['students', 'classes', 'subjects', 'periods', 'enrollments', 'assignments', 'family-access']]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            parser = ElementIds()
            parser.feed(response.content.decode())
            self.assertEqual(len(parser.ids), len(set(parser.ids)), f'Duplicate HTML IDs: {url}')

    def test_first_login_requires_password_change_and_safe_redirect(self):
        self.teacher.must_change_password = True
        self.teacher.save()
        response = self.client.post('/portal/login/?next=https://evil.example/', {'username': self.teacher_user.username, 'password': self.password})
        self.assertRedirects(response, '/portal/password/', fetch_redirect_response=False)
        self.assertRedirects(self.client.get(f'/portal/marks/{self.assignment.pk}/'), '/portal/password/')
        response = self.client.post('/portal/password/', {'old_password': self.password,
            'new_password1': 'My-private-school-password-984!', 'new_password2': 'My-private-school-password-984!'})
        self.assertEqual(response.status_code, 302)
        self.teacher.refresh_from_db()
        self.assertFalse(self.teacher.must_change_password)
        self.assertEqual(self.client.get(f'/portal/marks/{self.assignment.pk}/').status_code, 200)

    def test_login_rejects_nonportal_user_and_external_next(self):
        response = self.client.post('/portal/login/', {'username': self.editor.username, 'password': self.password})
        self.assertContains(response, 'does not have school portal access')
        self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post('/portal/login/?next=https://evil.example/', {'username': self.family_user.username, 'password': self.password})
        self.assertRedirects(response, '/portal/', fetch_redirect_response=False)

    def test_account_creation_ignores_privilege_injection_and_audits_no_password(self):
        self.client.force_login(self.owner)
        response = self.client.post('/portal/office/accounts/', {'username': 'new-teacher', 'first_name': 'New', 'last_name': 'Teacher',
            'email': 'teacher@example.com', 'role': 'teacher', 'password1': self.password, 'password2': self.password,
            'is_superuser': 'on', 'is_staff': 'on'})
        self.assertEqual(response.status_code, 302)
        account = PortalAccount.objects.get(user__username='new-teacher')
        self.assertFalse(account.user.is_staff)
        self.assertFalse(account.user.is_superuser)
        self.assertTrue(account.must_change_password)
        self.assertNotIn(self.password, str(list(AuditEvent.objects.values('details'))))

    def test_account_creation_rejects_weak_password(self):
        form = forms.AccountCreationForm({'username': 'weak', 'first_name': 'New', 'last_name': 'User',
            'role': 'teacher', 'password1': '123', 'password2': '123'})
        self.assertFalse(form.is_valid())

    def test_teacher_cannot_read_or_write_another_assignment(self):
        self.client.force_login(self.other_teacher.user)
        self.assertEqual(self.client.get(f'/portal/marks/{self.assignment.pk}/').status_code, 404)
        with self.assertRaises(PermissionDenied):
            services.save_sheet(self.other_teacher.user, self.assignment.pk, 0, self.rows())
        self.client.force_login(self.family_user)
        self.assertEqual(self.client.get(f'/portal/marks/{self.assignment.pk}/').status_code, 404)

    def test_partial_draft_then_complete_submit_and_lock(self):
        rows = self.rows()
        rows[1] = {'enrollment': self.other_enrollment.pk, 'status': '', 'score': None, 'comment': ''}
        services.save_sheet(self.teacher_user, self.assignment.pk, 0, rows)
        self.assertEqual(Mark.objects.count(), 1)
        with self.assertRaises(ValidationError):
            services.save_sheet(self.teacher_user, self.assignment.pk, 1, rows, submit=True)
        services.save_sheet(self.teacher_user, self.assignment.pk, 1, self.rows(), submit=True)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, 'submitted')
        with self.assertRaises(services.Conflict):
            services.save_sheet(self.teacher_user, self.assignment.pk, 2, self.rows())

    def test_stale_sheet_rejected_without_partial_writes(self):
        services.save_sheet(self.teacher_user, self.assignment.pk, 0, self.rows())
        with self.assertRaises(services.Conflict):
            services.save_sheet(self.teacher_user, self.assignment.pk, 0, self.rows('99', '99'))
        self.assertEqual(Mark.objects.get(enrollment=self.enrollment).score, Decimal('81.25'))

    def test_tampered_roster_missing_duplicate_or_foreign_student_rejected(self):
        invalid = [self.rows()[:1], [self.rows()[0], self.rows()[0]], [self.rows()[0], {**self.rows()[1], 'enrollment': 987654}]]
        for rows in invalid:
            with self.assertRaises(services.Conflict):
                services.save_sheet(self.teacher_user, self.assignment.pk, 0, rows)
        self.assertFalse(Mark.objects.exists())

    def test_mark_validation_and_explicit_absence(self):
        for score in ['-1', '100.01', 'NaN', '10.123']:
            form = forms.MarkRowForm({'enrollment': self.enrollment.pk, 'status': 'scored', 'score': score})
            self.assertFalse(form.is_valid(), score)
        for data in [{'status': 'scored'}, {'status': 'absent', 'score': '0', 'comment': 'Away'}, {'status': 'exempt'}]:
            self.assertFalse(forms.MarkRowForm({'enrollment': self.enrollment.pk, **data}).is_valid())
        rows = self.rows()
        rows[1] = {'enrollment': self.other_enrollment.pk, 'status': 'absent', 'score': None, 'comment': 'Absent on assessment day.'}
        services.save_sheet(self.teacher_user, self.assignment.pk, 0, rows, submit=True)
        services.generate_reports(self.owner, self.classroom, self.period)
        absent_report = StudentReport.objects.get(enrollment=self.other_enrollment)
        self.assertIsNone(absent_report.snapshot['average'])
        self.assertEqual(absent_report.snapshot['rows'][0]['status'], 'Absent')

    def test_database_rejects_out_of_range_marks_and_negative_fees(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Mark.objects.create(assignment=self.assignment, enrollment=self.enrollment, score=101)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FeeClearance.objects.create(student=self.student, period=self.period, outstanding=-1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FeeClearance.objects.create(student=self.student, period=self.period, outstanding=1, cleared=True)

    def test_closed_period_and_revoked_assignment_block_teacher(self):
        self.period.is_open = False
        self.period.save()
        with self.assertRaises(services.Conflict):
            services.save_sheet(self.teacher_user, self.assignment.pk, 0, self.rows())
        self.period.is_open = True
        self.period.save()
        services.review_assignment(self.owner, self.assignment.pk, 0, 'access', 'Teacher left', self.teacher, False)
        with self.assertRaises(PermissionDenied):
            services.save_sheet(self.teacher_user, self.assignment.pk, 1, self.rows())
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.get(f'/portal/marks/{self.assignment.pk}/').status_code, 404)

    def test_generation_requires_all_required_subjects_and_complete_roster(self):
        with self.assertRaises(ValidationError):
            services.generate_reports(self.owner, self.classroom, self.period)
        self.submit()
        second = TeachingAssignment.objects.create(teacher=self.other_teacher, classroom=self.classroom, period=self.period,
            subject=AcademicSubject.objects.create(name='English'), active=False)
        with self.assertRaises(ValidationError):
            services.generate_reports(self.owner, self.classroom, self.period)
        second.delete()
        Mark.objects.filter(enrollment=self.other_enrollment).delete()
        with self.assertRaises(ValidationError):
            services.generate_reports(self.owner, self.classroom, self.period)
        self.assertFalse(StudentReport.objects.exists())

    def test_generated_report_is_private_and_valid_pdf(self):
        import pypdfium2 as pdfium
        report = self.generate()
        self.assertFalse(report.published)
        self.assertTrue(bytes(report.pdf).startswith(b'%PDF-'))
        pdf = pdfium.PdfDocument(bytes(report.pdf))
        text_page = pdf[0].get_textpage()
        text = text_page.get_text_range()
        self.assertIn('Mpho Mokoena', text)
        self.assertIn('81.25', text)
        self.assertIn('Quarter 1', text)
        text_page.close()
        pdf.close()
        self.client.force_login(self.family_user)
        self.assertEqual(self.client.get(f'/portal/reports/{report.pk}/download/').status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f'/portal/reports/{report.pk}/download/').status_code, 200)

    def test_pdf_failure_rolls_back_the_whole_class_generation(self):
        self.submit()
        with patch('academics.services.render_pdf', side_effect=[b'%PDF-test', RuntimeError('Renderer unavailable')]):
            with self.assertRaises(RuntimeError):
                services.generate_reports(self.owner, self.classroom, self.period)
        self.assertFalse(StudentReport.objects.exists())
        self.assertFalse(AuditEvent.objects.filter(action='report.generated').exists())

    def test_release_requires_publication_zero_balance_and_explicit_clearance(self):
        report = self.generate(publish=True)
        self.client.force_login(self.family_user)
        url = f'/portal/reports/{report.pk}/'
        self.assertEqual(self.client.get(url).status_code, 403)
        services.update_fees(self.owner, self.student, self.period, 0, {'outstanding': Decimal('250.50'), 'cleared': False, 'note': 'Office statement.'})
        response = self.client.get(url)
        self.assertContains(response, '250.50', status_code=403)
        self.assertContains(response, '+266 5550 0000', status_code=403)
        self.assertNotContains(response, '81.25', status_code=403)
        services.update_fees(self.owner, self.student, self.period, 1, {'outstanding': Decimal('0'), 'cleared': False, 'note': 'Pending confirmation.'})
        self.assertEqual(self.client.get(url).status_code, 403)
        services.update_fees(self.owner, self.student, self.period, 2, {'outstanding': Decimal('0'), 'cleared': True, 'note': 'Payment confirmed.'})
        self.assertContains(self.client.get(url), '81.25')
        self.assertEqual(self.client.get(url + 'download/').status_code, 200)
        self.assertTrue(AuditEvent.objects.filter(actor=self.family_user, action='report.downloaded').exists())

    def test_debt_reintroduction_blocks_existing_pdf_url(self):
        report = self.generate(publish=True, clear=True)
        self.client.force_login(self.family_user)
        url = f'/portal/reports/{report.pk}/download/'
        self.assertEqual(self.client.get(url).status_code, 200)
        services.update_fees(self.owner, self.student, self.period, 1, {'outstanding': Decimal('1'), 'cleared': False, 'note': 'Ledger correction.'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(response['Content-Type'], 'application/pdf')

    def test_report_isolation_and_revoked_family_access(self):
        report = self.generate(publish=True, clear=True)
        for user in [self.other_family.user, self.teacher_user]:
            self.client.force_login(user)
            for suffix in ['', 'download/']:
                self.assertEqual(self.client.get(f'/portal/reports/{report.pk}/{suffix}').status_code, 404)
        self.client.force_login(self.family_user)
        services.review_family_access(self.owner, self.grant.pk, 'revoke', 'Relationship review pending.')
        self.assertEqual(self.client.get(f'/portal/reports/{report.pk}/download/').status_code, 404)
        self.assertNotContains(self.client.get('/portal/'), self.student.full_name)

    def test_inactive_student_is_hidden_from_family(self):
        report = self.generate(publish=True, clear=True)
        self.student.active = False
        self.student.save()
        self.client.force_login(self.family_user)
        self.assertEqual(self.client.get(f'/portal/reports/{report.pk}/').status_code, 404)

    def test_reopening_invalidates_reports_and_requires_resubmission(self):
        report = self.generate(publish=True, clear=True)
        services.review_assignment(self.owner, self.assignment.pk, 1, 'reopen', 'Correct assessment entry.')
        report.refresh_from_db()
        self.assertFalse(report.valid)
        self.assertFalse(report.published)
        self.client.force_login(self.family_user)
        self.assertEqual(self.client.get(f'/portal/reports/{report.pk}/download/').status_code, 403)
        with self.assertRaises(ValidationError):
            services.generate_reports(self.owner, self.classroom, self.period)

    def test_new_enrollment_reopens_sheets_and_invalidates_reports(self):
        report = self.generate(publish=True)
        student = Student.objects.create(admission_number='HF-003', full_name='New Learner')
        form = forms.EnrollmentForm({'student': student.pk, 'classroom': self.classroom.pk})
        self.assertTrue(form.is_valid(), form.errors)
        services.add_setup_record(self.owner, form)
        report.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertFalse(report.valid)
        self.assertEqual(self.assignment.status, 'draft')
        self.assertEqual(self.assignment.revision, 2)

    def test_unique_student_class_per_year_and_year_matching(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(student=self.student, classroom=self.other_class)
        next_year = ReportingPeriod.objects.create(year=2027, quarter=1)
        form = forms.AssignmentForm({'teacher': self.teacher.pk, 'classroom': self.classroom.pk, 'period': next_year.pk, 'subject': self.subject.pk})
        self.assertFalse(form.is_valid())

    def test_family_cannot_be_assigned_as_teacher_or_teacher_as_parent(self):
        form = forms.AssignmentForm({'teacher': self.family.pk, 'classroom': self.classroom.pk, 'period': self.period.pk, 'subject': self.subject.pk})
        self.assertFalse(form.is_valid())
        form = forms.FamilyAccessForm({'account': self.teacher.pk, 'student': self.student.pk, 'relationship': 'parent', 'verification_note': 'Test'})
        self.assertFalse(form.is_valid())

    def test_fee_forms_and_stale_fee_updates(self):
        self.assertFalse(forms.FeeForm({'outstanding': '100', 'cleared': 'on', 'note': 'Wrong', 'revision': 0}).is_valid())
        services.update_fees(self.owner, self.student, self.period, 0, {'outstanding': Decimal('40'), 'cleared': False, 'note': 'First review.'})
        with self.assertRaises(services.Conflict):
            services.update_fees(self.owner, self.student, self.period, 0, {'outstanding': Decimal('0'), 'cleared': True, 'note': 'Stale review.'})
        self.assertEqual(FeeClearance.objects.get(student=self.student).outstanding, 40)

    def test_grading_policy_configuration_and_historical_snapshot(self):
        report = self.generate()
        self.assertEqual(report.snapshot['rows'][0]['grade'], 'B+')
        form = forms.PolicyForm({'heading': 'School assessment report', 'closing_note': 'Contact your class teacher.',
            'show_average': 'on', 'pass_mark': 50, 'result_basis': 'current', 'revision': 1, 'grading_bands': '90 | Distinction | Excellent\n0 | Developing | Keep working'})
        self.assertTrue(form.is_valid(), form.errors)
        services.update_policy(self.owner, form)
        report.refresh_from_db()
        self.assertEqual(report.snapshot['rows'][0]['grade'], 'B+')
        services.generate_reports(self.owner, self.classroom, self.period)
        report.refresh_from_db()
        self.assertEqual(report.snapshot['rows'][0]['grade'], 'Developing')
        self.assertEqual(report.snapshot['heading'], 'School assessment report')
        self.assertEqual(report.snapshot['policy_revision'], 2)
        self.assertFalse(report.published)

    def test_policy_validation_rejects_ambiguous_or_incomplete_bands(self):
        for bands in ['80 | A | Great', '0 | A | Good\n0 | B | Bad', '-1 | F | Bad', 'NaN | F | Bad', '0 | A', '0 | | Description']:
            form = forms.PolicyForm({'heading': 'Report', 'closing_note': 'A note', 'revision': 1, 'grading_bands': bands})
            self.assertFalse(form.is_valid(), bands)

    def test_stale_report_preview_cannot_publish_newly_regenerated_reports(self):
        self.generate()
        revisions = {str(r.pk): r.revision for r in StudentReport.objects.all()}
        services.generate_reports(self.owner, self.classroom, self.period)
        with self.assertRaises(services.Conflict):
            services.publish_reports(self.owner, self.classroom, self.period, 'publish', revisions)
        self.assertFalse(StudentReport.objects.filter(published=True).exists())

    def test_csrf_and_http_methods_and_private_headers(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/portal/logout/').status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post('/portal/office/accounts/', {}).status_code, 403)
        self.assertEqual(csrf.post('/portal/office/policy/', {}).status_code, 403)
        for url in ['/portal/login/', '/portal/office/', '/portal/not-found/']:
            response = self.client.get(url)
            self.assertEqual(response['Cache-Control'], 'no-store, private')
            self.assertIn('noindex', response['X-Robots-Tag'])
        report = self.generate()
        response = self.client.get(f'/portal/reports/{report.pk}/download/')
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_deactivation_and_password_reset_revoke_existing_sessions(self):
        self.client.force_login(self.family_user)
        services.review_account(self.owner, self.family.pk, 'deactivate', 'End of enrolment.')
        self.assertEqual(self.client.get('/portal/').status_code, 302)
        with self.assertRaises(ValidationError):
            services.review_account(self.owner, self.family.pk, 'activate', 'Verified again.')
        reset = SetPasswordForm(self.family_user, {'new_password1': 'New-private-family-access-843!', 'new_password2': 'New-private-family-access-843!'})
        self.assertTrue(reset.is_valid(), reset.errors)
        services.review_account(self.owner, self.family.pk, 'reset-password', 'Identity verified.', reset)
        services.review_account(self.owner, self.family.pk, 'activate', 'Identity verified.')
        self.assertEqual(self.client.get('/portal/').status_code, 302)

    def test_portal_account_review_cannot_change_privileged_staff(self):
        self.teacher_user.is_staff = True
        self.teacher_user.save()
        with self.assertRaises(PermissionDenied):
            services.review_account(self.owner, self.teacher.pk, 'deactivate', 'Not allowed here.')

    def test_setup_command_is_idempotent_and_least_privilege(self):
        call_command('setup_academic_access', verbosity=0)
        call_command('setup_academic_access', verbosity=0)
        group = Group.objects.get(name='Reporting administrators')
        self.assertEqual(list(group.permissions.values_list('codename', flat=True)), ['manage_academics'])

    def test_family_home_shows_only_linked_student_and_no_mark_when_held(self):
        self.generate(publish=True)
        self.client.force_login(self.family_user)
        response = self.client.get('/portal/')
        self.assertContains(response, self.student.full_name)
        self.assertNotContains(response, self.other_student.full_name)
        self.assertNotContains(response, '81.25')

    def test_teacher_form_submission_end_to_end(self):
        self.client.force_login(self.teacher_user)
        data = {'marks-TOTAL_FORMS': '2', 'marks-INITIAL_FORMS': '2', 'marks-MIN_NUM_FORMS': '0',
            'marks-MAX_NUM_FORMS': '200', 'revision': '0', 'action': 'submit'}
        for i, row in enumerate(self.rows()):
            for key, value in row.items():
                data[f'marks-{i}-{key}'] = value
        response = self.client.post(f'/portal/marks/{self.assignment.pk}/', data)
        self.assertEqual(response.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, 'submitted')

    def test_publication_requires_signed_preview_and_audits_withdrawal(self):
        self.generate()
        self.client.force_login(self.owner)
        url = f'/portal/office/reports/?classroom={self.classroom.pk}&period={self.period.pk}'
        response = self.client.get(url)
        token = response.context['preview']
        payload = {'classroom': self.classroom.pk, 'period': self.period.pk, 'action': 'publish', 'preview': 'tampered'}
        self.assertEqual(self.client.post('/portal/office/reports/', payload).status_code, 409)
        payload['preview'] = token
        self.assertEqual(self.client.post('/portal/office/reports/', payload).status_code, 302)
        self.assertTrue(StudentReport.objects.filter(published=True).exists())
        payload['action'] = 'withdraw'
        self.assertEqual(self.client.post('/portal/office/reports/', payload).status_code, 302)
        self.assertFalse(StudentReport.objects.filter(published=True).exists())
        self.assertTrue(AuditEvent.objects.filter(action='report.withdraw').exists())


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class PortalLoginThrottlingTests(TestCase):
    def test_axes_protects_portal_login(self):
        user = User.objects.create_user('limited-teacher', password='Private-school-password-200!')
        PortalAccount.objects.create(user=user, role='teacher')
        for _ in range(5):
            self.client.post('/portal/login/', {'username': user.username, 'password': 'incorrect'})
        response = self.client.post('/portal/login/', {'username': user.username, 'password': 'Private-school-password-200!'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Cache-Control'], 'no-store, private')


class AcademicConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_concurrent_class_writes_preserve_the_winner_and_reject_stale_marks(self):
        teacher_user = User.objects.create_user('concurrent-teacher')
        teacher = PortalAccount.objects.create(user=teacher_user, role='teacher', must_change_password=False)
        classroom = SchoolClass.objects.create(name='Form 2', year=2026)
        student = Student.objects.create(full_name='Concurrency Test Student', admission_number='CT-1')
        enrollment = Enrollment.objects.create(student=student, classroom=classroom)
        assignment = TeachingAssignment.objects.create(teacher=teacher, classroom=classroom,
            period=ReportingPeriod.objects.create(year=2026, quarter=2), subject=AcademicSubject.objects.create(name='Science'))
        barrier = Barrier(2)

        def write(score):
            try:
                actor = User.objects.get(pk=teacher_user.pk)
                barrier.wait(timeout=10)
                services.save_sheet(actor, assignment.pk, 0, [{'enrollment': enrollment.pk, 'status': 'scored',
                    'score': Decimal(score), 'comment': ''}])
                return 'saved'
            except services.Conflict:
                return 'conflict'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(write, ['70.00', '90.00']))
        self.assertCountEqual(results, ['saved', 'conflict'])
        self.assertEqual(Mark.objects.filter(assignment=assignment).count(), 1)
        self.assertIn(Mark.objects.get(assignment=assignment).score, [Decimal('70'), Decimal('90')])
        assignment.refresh_from_db()
        self.assertEqual(assignment.revision, 1)


class ElementIds(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        self.ids.extend(value for name, value in attrs if name == 'id')
