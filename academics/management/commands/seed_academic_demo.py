"""Create a clearly fictional review dataset once, without resetting user edits."""
import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from academics import services
from academics.models import (AcademicSubject, AuditEvent, Enrollment, FamilyAccess,
    PortalAccount, ReportingPeriod, ReportPolicy, SchoolClass, Student, StudentReport,
    TeachingAssignment)


DATASET = 'hfhs-academics-demo-v1'
ACCOUNTS = (
    ('demo.admin', 'Demo', 'Administrator', 'manager'),
    ('demo.teacher.maths', 'Demo Thabo', 'Molefe', 'teacher'),
    ('demo.teacher.languages', 'Demo Palesa', 'Mokoena', 'teacher'),
    ('demo.teacher.humanities', 'Demo Kabelo', 'Mofokeng', 'teacher'),
    ('demo.parent', 'Demo Lerato', 'Parent', 'family'),
    ('demo.parent.other', 'Demo Neo', 'Guardian', 'family'),
    ('demo.student', 'Demo Mpho', 'Student', 'family'),
    ('demo.firstlogin', 'Demo First', 'Login', 'family'),
    ('demo.revoked', 'Demo Revoked', 'Guardian', 'family'),
)
SUBJECTS = (
    ('Mathematics', 'demo.teacher.maths'),
    ('English Language', 'demo.teacher.languages'),
    ('Sesotho', 'demo.teacher.languages'),
    ('Physical Science', 'demo.teacher.maths'),
    ('Geography', 'demo.teacher.humanities'),
    ('Religious Education', 'demo.teacher.humanities'),
)
NAMES = (
    'Mpho Mokoena', 'Lerato Mohapi', 'Thabo Molefe', 'Palesa Mofokeng',
    'Kabelo Nthunya', 'Lineo Rasekoele', 'Neo Seema', 'Bokang Motsoane',
    'Refiloe Mohlomi', 'Teboho Makhakhe', 'Nthabiseng Tau', 'Tshepo Phiri',
    'Mamello Lebesa', 'Khotso Ntlama', 'Limpho Mokhethi', 'Relebohile Rantso',
)


class Command(BaseCommand):
    help = 'Seed local-only fictional academic accounts, marks, fees and PDF reports. Existing demo edits are preserved.'

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        local_hosts = {'localhost', '127.0.0.1', '::1', '[::1]', 'testserver'}
        if (not settings.DEBUG or not settings.ALLOWED_HOSTS
                or not set(settings.ALLOWED_HOSTS).issubset(local_hosts)
                or database.get('HOST', '') not in {'', 'localhost', '127.0.0.1', '::1'}):
            raise CommandError('Demo data is allowed only with DEBUG=True, local allowed hosts, and a local database.')
        with transaction.atomic():
            marker = AuditEvent.objects.filter(action='demo.seeded', details__dataset=DATASET).first()
            if marker:
                self.stdout.write(self.style.SUCCESS(
                    f"The {marker.details['year']} academic demo already exists. Accounts, passwords, marks and testing edits were preserved."))
                return
            self.seed()

    def seed(self):
        user_model = get_user_model()
        subject_names = [f'Demo {name}' for name, _ in SUBJECTS]
        if (user_model.objects.filter(username__in=[row[0] for row in ACCOUNTS]).exists()
                or Student.objects.filter(admission_number__startswith='DEMO-ACADEMIC-').exists()
                or SchoolClass.objects.filter(name__in=['Demo Form 1A', 'Demo Form 2A']).exists()
                or AcademicSubject.objects.filter(name__in=subject_names).exists()):
            raise CommandError('A reserved demo name is already in use without a completed seed marker. No records were changed.')

        year, now = timezone.localdate().year, timezone.now()
        periods = [ReportingPeriod.objects.get_or_create(year=year, quarter=q)[0] for q in range(1, 5)]
        if any(not period.is_open for period in periods):
            raise CommandError('An existing quarter is closed. No records were changed; demo seeding does not reopen school reporting periods.')
        ReportPolicy.objects.get_or_create(pk=1)
        permission = Permission.objects.get(content_type__app_label='academics', codename='manage_academics')
        group, _ = Group.objects.get_or_create(name='Reporting administrators')
        group.permissions.add(permission)
        password = 'Local-demo-' + secrets.token_urlsafe(10) + '!'
        users, accounts = {}, {}
        for username, first_name, last_name, role in ACCOUNTS:
            user = user_model.objects.create_user(username=username, first_name=first_name,
                last_name=last_name, email=username + '@example.invalid', password=password, is_staff=role == 'manager')
            users[username] = user
            if role == 'manager':
                user.groups.add(group)
            else:
                accounts[username] = PortalAccount.objects.create(user=user, role=role,
                    must_change_password=username == 'demo.firstlogin', reviewed_at=now,
                    reviewed_by=users['demo.admin'])
            services.audit(users['demo.admin'], 'demo.account-created', user, dataset=DATASET, role=role)
        manager = users['demo.admin']
        classes = [SchoolClass.objects.create(name=f'Demo Form {i}A', year=year) for i in (1, 2)]
        students, enrollments = [], []
        for index, name in enumerate(NAMES):
            student = Student.objects.create(admission_number=f'DEMO-ACADEMIC-{year}-{index + 1:03}', full_name=f'Demo {name}')
            students.append(student)
            enrollments.append(Enrollment.objects.create(student=student, classroom=classes[index // 8]))
        subjects = [AcademicSubject.objects.create(name=name) for name in subject_names]

        def link(username, index, relationship='parent'):
            grant = FamilyAccess.objects.create(account=accounts[username], student=students[index],
                relationship=relationship, reviewed_at=now, reviewed_by=manager)
            services.audit(manager, 'demo.family-linked', grant, verification_note='Fictional relationship for local testing only.')
            return grant

        for index in (0, 1, 2, 8):
            link('demo.parent', index)
        link('demo.parent.other', 3, 'guardian')
        link('demo.student', 4, 'student')
        link('demo.firstlogin', 5, 'parent')
        revoked = link('demo.revoked', 0, 'guardian')
        services.review_family_access(manager, revoked.pk, 'revoke', 'Demo: access revoked after a relationship review.')

        for class_index, classroom in enumerate(classes):
            roster = enrollments[class_index * 8:(class_index + 1) * 8]
            for period in periods:
                for subject_index, subject in enumerate(subjects):
                    teacher_username = SUBJECTS[subject_index][1]
                    assignment = TeachingAssignment.objects.create(classroom=classroom, period=period,
                        subject=subject, teacher=accounts[teacher_username], reviewed_at=now, reviewed_by=manager)
                    rows = []
                    for student_index, enrollment in enumerate(roster):
                        score = Decimal(40 + ((student_index * 11 + subject_index * 7 + period.quarter * 3) % 59))
                        row = {'enrollment': enrollment.pk, 'status': 'scored', 'score': score,
                            'comment': ('Excellent participation; keep challenging yourself.' if score >= 80
                                else 'Steady progress. Revise difficult topics and practise regularly.' if score >= 60
                                else 'Please arrange extra practice with your subject teacher.')}
                        if student_index == 6 and subject_index == 1:
                            row.update(status='absent', score=None, comment='Demo: absent on assessment day; follow up with the subject teacher.')
                        elif student_index == 7 and subject_index == 3:
                            row.update(status='exempt', score=None, comment='Demo: authorised exemption from this assessment.')
                        elif student_index == 5 and subject_index == 0:
                            row.update(score=Decimal('0'), comment='Demo: a genuine zero mark, not a missing mark.')
                        # Q4 has submitted language sheets, a partial maths draft,
                        # and blank humanities sheets for the teacher to complete.
                        if period.quarter == 4 and ((subject_index == 0 and student_index >= 4) or subject_index >= 4):
                            row.update(status='', score=None, comment='')
                        rows.append(row)
                    services.save_sheet(users[teacher_username], assignment.pk, 0, rows,
                        submit=period.quarter != 4 or subject_index in (1, 2, 3))
                if period.quarter in (1, 2):
                    services.generate_reports(manager, classroom, period)
                    if period.quarter == 1:
                        reports = StudentReport.objects.filter(enrollment__classroom=classroom, period=period)
                        services.publish_reports(manager, classroom, period, 'publish', {str(r.pk): r.revision for r in reports})

        for index, student in enumerate(students):
            outstanding = Decimal('1250.50') if index % 4 == 1 else Decimal('0.00')
            cleared = index % 4 in (0, 3)
            for period in periods:
                services.update_fees(manager, student, period, 0, {'outstanding': outstanding, 'cleared': cleared,
                    'note': 'Fictional local demo: payment confirmed.' if cleared else 'Fictional local demo: outstanding balance.' if outstanding else 'Fictional local demo: zero balance awaiting office confirmation.'})
        revoked_assignment = TeachingAssignment.objects.get(classroom=classes[1], period=periods[0], subject=subjects[0])
        services.review_assignment(manager, revoked_assignment.pk, 1, 'access',
            'Demo: teacher access revoked; submitted marks remain required.', accounts['demo.teacher.maths'], False)
        services.audit(manager, 'demo.seeded', classes[0], dataset=DATASET, year=year,
            accounts=len(ACCOUNTS), students=len(students), classes=len(classes), reports=32)
        self.stdout.write(self.style.SUCCESS(f'Created {year} academic demo: 9 accounts, 16 students, 2 classes, 6 subjects, 4 quarters, 32 PDF reports.'))
        self.stdout.write('All names, marks, balances and payment notes in this dataset are fictional.')
        self.stdout.write(f'Local demo password (all demo accounts): {password}')
        for username, _, _, role in ACCOUNTS:
            self.stdout.write(f'  {username}: {role}' + ('; first sign-in password change required' if username == 'demo.firstlogin' else ''))
        self.stdout.write('Q1: published; Q2: private generated previews; Q3: submitted, ready to generate; Q4: editable drafts and submitted sheets.')
        self.stdout.write('demo.parent: Mpho and Refiloe released; Lerato owes M 1,250.50; Thabo awaits explicit fee clearance.')
        self.stdout.write('Run again safely to keep the existing dataset and all review edits. Passwords are not reset.')
