"""Private academic records. Reports are database blobs, never public media files."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


YEAR_VALIDATORS = [MinValueValidator(2000), MaxValueValidator(2100)]


def default_bands():
    return [
        {'minimum': minimum, 'grade': grade, 'description': description}
        for minimum, grade, description in [
            (90, 'A*', 'Excellent'), (85, 'A', 'Super'), (80, 'B+', 'Keep It Up'),
            (75, 'B', 'Very Good'), (70, 'C+', 'Good Work'), (65, 'C', 'Much Better'),
            (60, 'D+', 'Good'), (55, 'D', 'Fair'), (40, 'E', 'Try Harder'),
            (30, 'F', 'Try Harder'), (20, 'G', 'Put More Effort'),
            (10, 'H', 'Work Hard'), (0, 'U', 'Work Hard'),
        ]
    ]


def default_performance_levels():
    return [
        {'minimum': minimum, 'level': level, 'description': description}
        for minimum, level, description in [
            (80, 'ADVANCE', 'Solves complex problems independently, using logical and abstract thinking.'),
            (70, 'VERY PROFICIENT', 'Uses logical thinking giving attention to details with very little help.'),
            (60, 'PROFICIENT', 'Uses some critical thinking to solve problems.'),
            (50, 'BASIC', 'Provides superficial reasoned arguments.'),
            (0, 'BELOW BASIC', 'Can recall facts and simple or basic principles only.'),
        ]
    ]


class ReportPolicy(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    heading = models.CharField(max_length=120, default='Performance report')
    closing_note = models.TextField(max_length=1500, default='Please discuss this report with your child and contact the school if you need support.')
    show_average = models.BooleanField(default=True)
    bands = models.JSONField(default=default_bands)
    performance_levels = models.JSONField(default=default_performance_levels)
    pass_mark = models.PositiveSmallIntegerField(default=50, validators=[MaxValueValidator(100)], help_text='Minimum final subject mark counted as a pass.')
    result_basis = models.CharField(max_length=10, choices=[('current', 'Current quarter average'), ('final', 'Cumulative final mark average')], default='current')
    principal_name = models.CharField(max_length=160, blank=True)
    report_footer = models.CharField(max_length=160, blank=True, default='232002 - QUID RETRIBUAM')
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name='one_academic_report_policy')]
        permissions = [('manage_academics', 'Manage academic accounts, marks, fees and reports')]


class PortalAccount(models.Model):
    class Role(models.TextChoices):
        TEACHER = 'teacher', 'Teacher'
        FAMILY = 'family', 'Student / parent / guardian'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='portal_account')
    role = models.CharField(max_length=10, choices=Role.choices)
    must_change_password = models.BooleanField(default=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.get_role_display()})'


class SchoolClass(models.Model):
    stream = models.CharField(max_length=60, blank=True, help_text='Shared grade/form for stream positions, e.g. Grade 9. Leave blank to omit stream ranking.')
    class_teacher_name = models.CharField(max_length=160, blank=True)
    name = models.CharField(max_length=60)
    year = models.PositiveSmallIntegerField(validators=YEAR_VALIDATORS)

    class Meta:
        ordering = ['-year', 'name']
        constraints = [models.UniqueConstraint(fields=['year', 'name'], name='unique_academic_class')]

    def __str__(self):
        return f'{self.name} ({self.year})'


class ReportingPeriod(models.Model):
    reopens_on = models.DateField('School reopens on', null=True, blank=True)
    year = models.PositiveSmallIntegerField(validators=YEAR_VALIDATORS)
    quarter = models.PositiveSmallIntegerField(choices=[(i, f'Quarter {i}') for i in range(1, 5)])
    is_open = models.BooleanField(default=True, help_text='Teachers can save and submit only while this period is open.')

    class Meta:
        ordering = ['-year', '-quarter']
        constraints = [
            models.UniqueConstraint(fields=['year', 'quarter'], name='unique_academic_quarter'),
            models.CheckConstraint(condition=models.Q(quarter__gte=1, quarter__lte=4), name='academic_quarter_1_to_4'),
        ]

    def __str__(self):
        return f'{self.year} - Quarter {self.quarter}'


class AcademicSubject(models.Model):
    code = models.CharField(max_length=20, blank=True, help_text='Official subject code; leading zeros are preserved.')
    include_in_summary = models.BooleanField(default=True, help_text='Include in averages, positions and subjects passed. Clear for non-counting subjects such as LBSE if school policy requires it.')
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Student(models.Model):
    student_number = models.CharField(max_length=40, blank=True, help_text='Student number, separate from the admission number.')
    admission_number = models.CharField(max_length=40, unique=True)
    full_name = models.CharField(max_length=160)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['full_name', 'admission_number']

    def __str__(self):
        return f'{self.full_name} ({self.admission_number})'


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='enrollments')
    classroom = models.ForeignKey(SchoolClass, on_delete=models.PROTECT, related_name='enrollments')
    year = models.PositiveSmallIntegerField(editable=False)

    class Meta:
        ordering = ['student__full_name', 'student__admission_number']
        constraints = [models.UniqueConstraint(fields=['student', 'year'], name='one_student_class_per_year')]

    def clean(self):
        super().clean()
        if self.classroom_id:
            self.year = self.classroom.year

    def save(self, *args, **kwargs):
        self.year = self.classroom.year
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.student} - {self.classroom}'


class FamilyAccess(models.Model):
    account = models.ForeignKey(PortalAccount, on_delete=models.PROTECT, related_name='student_access')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='family_access')
    relationship = models.CharField(max_length=10, choices=[('student', 'Student'), ('parent', 'Parent'), ('guardian', 'Guardian')])
    active = models.BooleanField(default=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['account', 'student'], name='unique_family_student_access')]

    def clean(self):
        if self.account_id and self.account.role != PortalAccount.Role.FAMILY:
            raise ValidationError({'account': 'Choose a family account.'})


class TeachingAssignment(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted for review'

    teacher = models.ForeignKey(PortalAccount, on_delete=models.PROTECT, related_name='assignments')
    classroom = models.ForeignKey(SchoolClass, on_delete=models.PROTECT, related_name='assignments')
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT, related_name='assignments')
    subject = models.ForeignKey(AcademicSubject, on_delete=models.PROTECT)
    active = models.BooleanField(default=True, help_text='Disable to revoke teacher access; the subject remains required for reports.')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['classroom__name', 'subject__name']
        constraints = [models.UniqueConstraint(fields=['classroom', 'period', 'subject'], name='one_subject_per_class_quarter')]

    def clean(self):
        errors = {}
        if self.teacher_id and self.teacher.role != PortalAccount.Role.TEACHER:
            errors['teacher'] = 'Choose a teacher account.'
        if self.period_id and self.classroom_id and self.period.year != self.classroom.year:
            errors['period'] = 'The class and reporting period must have the same year.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.classroom} / {self.subject} / {self.period.get_quarter_display()}'


class Mark(models.Model):
    class Status(models.TextChoices):
        SCORED = 'scored', 'Mark recorded'
        ABSENT = 'absent', 'Absent'
        EXEMPT = 'exempt', 'Exempt'

    assignment = models.ForeignKey(TeachingAssignment, on_delete=models.PROTECT, related_name='marks')
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name='marks')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCORED)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    comment = models.CharField(max_length=300, blank=True)
    teacher_remark = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['assignment', 'enrollment'], name='one_mark_per_student_subject'),
            models.CheckConstraint(condition=(models.Q(status='scored', score__isnull=False, score__gte=0, score__lte=100) |
                models.Q(status__in=['absent', 'exempt'], score__isnull=True)), name='valid_academic_mark'),
        ]

    def clean(self):
        if self.assignment_id and self.enrollment_id and self.assignment.classroom_id != self.enrollment.classroom_id:
            raise ValidationError('The student is not enrolled in this class.')
        if self.status == self.Status.SCORED and self.score is None:
            raise ValidationError({'score': 'Enter a mark out of 100.'})
        if self.status != self.Status.SCORED and (self.score is not None or not self.comment.strip()):
            raise ValidationError('Absence or exemption requires a comment and no numeric mark.')


class ReportDetails(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name='report_details')
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT)
    days_absent = models.PositiveSmallIntegerField(null=True, blank=True)
    class_teacher_remark = models.CharField(max_length=500, blank=True)
    principal_remark = models.CharField(max_length=500, blank=True)
    revision = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['enrollment', 'period'], name='unique_student_report_details')]

    def clean(self):
        if self.enrollment_id and self.period_id and self.enrollment.year != self.period.year:
            raise ValidationError('The enrollment and reporting period must have the same year.')


class FeeClearance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='fee_clearances')
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT)
    outstanding = models.DecimalField('Outstanding amount (LSL)', max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0)])
    cleared = models.BooleanField(default=False, help_text='Explicitly confirm there are no pending fees. Only zero balances can be cleared.')
    note = models.CharField('Private review note / payment reference', max_length=500)
    revision = models.PositiveIntegerField(default=0)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'period'], name='unique_student_quarter_clearance'),
            models.CheckConstraint(condition=models.Q(outstanding__gte=0), name='nonnegative_report_fees'),
            models.CheckConstraint(condition=models.Q(cleared=False) | models.Q(outstanding=0), name='cleared_report_has_no_debt'),
        ]

    def clean(self):
        if self.cleared and self.outstanding:
            raise ValidationError({'cleared': 'Set the outstanding amount to zero before clearing fees.'})


class StudentReport(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name='reports')
    period = models.ForeignKey(ReportingPeriod, on_delete=models.PROTECT)
    snapshot = models.JSONField(default=dict, editable=False)
    pdf = models.BinaryField(default=b'', editable=False)
    valid = models.BooleanField(default=False)
    published = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=0)
    generated_at = models.DateTimeField(null=True, blank=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-period__year', '-period__quarter', 'enrollment__student__full_name']
        constraints = [models.UniqueConstraint(fields=['enrollment', 'period'], name='unique_student_quarter_report')]


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_name = models.CharField(max_length=150)
    action = models.CharField(max_length=50, db_index=True)
    target = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-pk']
