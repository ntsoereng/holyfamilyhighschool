"""Academic state transitions with shared class locks and optimistic revisions.

Roster, assignment, mark and report writes lock the affected stream classes in
primary-key order first. This serializes marks and position changes on MySQL/MariaDB
without a queue or new hosting service.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from school.models import SiteSettings
from .models import (AcademicSubject, AuditEvent, Enrollment, FamilyAccess, FeeClearance, Mark, PortalAccount,
                     ReportingPeriod, ReportDetails, ReportPolicy, SchoolClass, Student, StudentReport, TeachingAssignment)
from .permissions import require_manager
from .reports import make_snapshot, render_pdf


class Conflict(ValidationError):
    """The page is stale; no part of the requested write was applied."""


def audit(actor, action, obj, **details):
    AuditEvent.objects.create(actor=actor, actor_name=actor.get_username(), action=action,
        target=f'{obj._meta.label_lower}:{obj.pk}', details=details)


def check_revision(obj, revision):
    if obj.revision != revision:
        raise Conflict('This record changed after you opened it. Reload the page and review the latest values.')


def class_scope(classroom):
    scope = SchoolClass.objects.filter(pk=classroom.pk)
    if classroom.stream:
        scope = SchoolClass.objects.filter(year=classroom.year, stream=classroom.stream)
    return scope


def lock_class_scope(classroom_id):
    classroom = SchoolClass.objects.get(pk=classroom_id)
    # All writers lock stream classes in the same order before updating reports.
    list(class_scope(classroom).order_by('pk').select_for_update())


def invalidate(classroom_id, period_id=None):
    classroom = SchoolClass.objects.get(pk=classroom_id)
    reports = StudentReport.objects.filter(enrollment__classroom__in=class_scope(classroom))
    if period_id:
        period = ReportingPeriod.objects.get(pk=period_id)
        reports = reports.filter(period__year=period.year, period__quarter__gte=period.quarter)
    reports.update(valid=False, published=False, published_at=None, published_by=None)


@transaction.atomic
def create_account(actor, form):
    require_manager(actor)
    user = form.save(commit=False)
    user.is_staff = user.is_superuser = False
    user.save()
    account = PortalAccount.objects.create(user=user, role=form.cleaned_data['role'], reviewed_by=actor, reviewed_at=timezone.now())
    audit(actor, 'account.created', account, role=account.role, username=user.username)
    return account


@transaction.atomic
def review_account(actor, account_id, action, reason, password_form=None):
    require_manager(actor)
    account = PortalAccount.objects.get(pk=account_id)
    # Match the User -> PortalAccount lock order used by password changes.
    user = get_user_model().objects.select_for_update().get(pk=account.user_id)
    account = PortalAccount.objects.select_for_update().get(pk=account_id)
    # Portal administrators cannot alter privileged staff, each other or themselves.
    if user.is_staff or user.is_superuser or user.pk == actor.pk or user.user_permissions.exists() or user.groups.exists():
        raise PermissionDenied('Manage privileged accounts through the school administrator.')
    if action == 'reset-password':
        user.set_password(password_form.cleaned_data['new_password1'])
        account.must_change_password = True
    elif action in {'deactivate', 'activate'}:
        if action == 'activate' and not user.has_usable_password():
            raise ValidationError('Reset this account’s password before reactivating it.')
        user.is_active = action == 'activate'
        # Rotate the password hash salt to invalidate all existing sessions,
        # including if the account is subsequently reactivated.
        if not user.is_active:
            user.set_unusable_password()
    elif action != 'review':
        raise ValidationError('Choose a valid account action.')
    user.save()
    account.reviewed_at, account.reviewed_by = timezone.now(), actor
    account.save()
    audit(actor, 'account.' + action, account, reason=reason)


@transaction.atomic
def add_setup_record(actor, form):
    require_manager(actor)
    obj = form.save(commit=False)
    if isinstance(obj, (Enrollment, TeachingAssignment)):
        lock_class_scope(obj.classroom_id)
        if isinstance(obj, Enrollment):
            if Enrollment.objects.filter(classroom_id=obj.classroom_id).count() >= 200:
                raise ValidationError('Classes support up to 200 students. Create another class for additional students.')
            obj.year = obj.classroom.year
        else:
            obj.reviewed_by, obj.reviewed_at = actor, timezone.now()
        obj.full_clean()
        obj.save()
        invalidate(obj.classroom_id, obj.period_id if isinstance(obj, TeachingAssignment) else None)
        if isinstance(obj, Enrollment):
            TeachingAssignment.objects.filter(classroom_id=obj.classroom_id).update(
                status='draft', submitted_at=None, submitted_by=None, revision=F('revision') + 1)
    else:
        if isinstance(obj, FamilyAccess):
            obj.reviewed_by, obj.reviewed_at = actor, timezone.now()
        obj.full_clean()
        obj.save()
    details = {'verification_note': form.cleaned_data['verification_note']} if isinstance(obj, FamilyAccess) else {}
    if isinstance(obj, TeachingAssignment):
        details.update(teacher=obj.teacher_id, classroom=obj.classroom_id, period=obj.period_id, subject=obj.subject_id)
    audit(actor, 'setup.created', obj, **details)
    return obj


@transaction.atomic
def save_sheet(actor, assignment_id, revision, rows, submit=False):
    initial = TeachingAssignment.objects.get(pk=assignment_id)
    lock_class_scope(initial.classroom_id)
    assignment = TeachingAssignment.objects.select_for_update().get(pk=assignment_id)
    period = ReportingPeriod.objects.select_for_update().get(pk=assignment.period_id)
    if (assignment.teacher.user_id != actor.pk or not actor.is_active or not assignment.teacher.user.is_active
            or assignment.teacher.role != 'teacher' or not assignment.active):
        raise PermissionDenied
    check_revision(assignment, revision)
    if assignment.status != 'draft' or not period.is_open:
        raise Conflict('This marks sheet is locked. Ask the administrator to reopen it and the reporting period.')
    enrollments = list(Enrollment.objects.filter(classroom=assignment.classroom))
    expected = {e.pk for e in enrollments}
    received = [row['enrollment'] for row in rows]
    if len(received) != len(set(received)) or set(received) != expected:
        raise Conflict('The class roster changed or the submitted student list is invalid. Reload the marks sheet.')
    if submit and (not rows or any(not row.get('status') for row in rows)):
        raise ValidationError('Record a mark, absence or exemption for every student before submitting.')
    policy = ReportPolicy.objects.filter(pk=1).first() or ReportPolicy()
    allowed_remarks = {b['description'] for b in policy.bands}
    by_id = {e.pk: e for e in enrollments}
    for row in rows:
        if not row.get('status'):
            Mark.objects.filter(assignment=assignment, enrollment_id=row['enrollment']).delete()
            continue
        remark = row.get('teacher_remark', '')
        if remark and (remark not in allowed_remarks or row['status'] != 'scored'):
            raise ValidationError('Choose a teacher remark from the current grading lookup for numeric marks only.')
        mark = Mark(assignment=assignment, enrollment=by_id[row['enrollment']],
                    status=row['status'], score=row.get('score'), comment=row.get('comment', ''), teacher_remark=remark)
        mark.full_clean(validate_unique=False, validate_constraints=False)
        Mark.objects.update_or_create(assignment=assignment, enrollment=mark.enrollment,
            defaults={'status': mark.status, 'score': mark.score, 'comment': mark.comment, 'teacher_remark': mark.teacher_remark})
    assignment.revision += 1
    if submit:
        assignment.status, assignment.submitted_at, assignment.submitted_by = 'submitted', timezone.now(), actor
    assignment.save()
    invalidate(assignment.classroom_id, assignment.period_id)
    audit(actor, 'marks.submitted' if submit else 'marks.saved', assignment,
          revision=assignment.revision, student_count=len(rows))


@transaction.atomic
def review_assignment(actor, pk, revision, action, reason, teacher=None, active=None):
    require_manager(actor)
    initial = TeachingAssignment.objects.get(pk=pk)
    lock_class_scope(initial.classroom_id)
    assignment = TeachingAssignment.objects.select_for_update().get(pk=pk)
    check_revision(assignment, revision)
    if action == 'reopen':
        assignment.status, assignment.submitted_at, assignment.submitted_by = 'draft', None, None
        invalidate(assignment.classroom_id, assignment.period_id)
    elif action == 'access':
        if assignment.teacher_id != teacher.pk:
            invalidate(assignment.classroom_id, assignment.period_id)
        assignment.teacher, assignment.active = teacher, active
    else:
        raise ValidationError('Choose a valid assignment action.')
    assignment.revision += 1
    assignment.reviewed_at, assignment.reviewed_by = timezone.now(), actor
    assignment.full_clean()
    assignment.save()
    audit(actor, 'assignment.' + action, assignment, reason=reason, teacher=assignment.teacher_id, active=assignment.active)


@transaction.atomic
def review_family_access(actor, pk, action, reason):
    require_manager(actor)
    grant = FamilyAccess.objects.select_for_update().get(pk=pk)
    if action in {'revoke', 'restore'}:
        grant.active = action == 'restore'
    elif action != 'review':
        raise ValidationError('Choose a valid access action.')
    grant.reviewed_at, grant.reviewed_by = timezone.now(), actor
    grant.save()
    audit(actor, 'family-access.' + action, grant, reason=reason)


@transaction.atomic
def update_fees(actor, student, period, revision, values):
    require_manager(actor)
    Student.objects.select_for_update().get(pk=student.pk)
    clearance, _ = FeeClearance.objects.get_or_create(student=student, period=period)
    check_revision(clearance, revision)
    before = {'outstanding': str(clearance.outstanding), 'cleared': clearance.cleared}
    clearance.outstanding, clearance.cleared, clearance.note = values['outstanding'], values['cleared'], values['note']
    clearance.revision += 1
    clearance.reviewed_at, clearance.reviewed_by = timezone.now(), actor
    clearance.full_clean()
    clearance.save()
    audit(actor, 'fees.reviewed', clearance, before=before, outstanding=str(clearance.outstanding), cleared=clearance.cleared, note=clearance.note)


@transaction.atomic
def generate_reports(actor, classroom, period):
    require_manager(actor)
    lock_class_scope(classroom.pk)
    classroom = SchoolClass.objects.get(pk=classroom.pk)
    period = ReportingPeriod.objects.get(pk=period.pk)
    if classroom.year != period.year:
        raise ValidationError('The class and reporting period must have the same year.')
    assignments = list(TeachingAssignment.objects.filter(classroom=classroom, period=period).select_related('subject', 'teacher__user'))
    enrollments = list(Enrollment.objects.filter(classroom=classroom).select_related('student', 'classroom'))
    if not assignments or not enrollments:
        raise ValidationError('Add students and all required subject assignments before generating reports.')
    if any(a.status != 'submitted' for a in assignments):
        raise ValidationError('Every required subject must be submitted before reports can be generated, including assignments with revoked teacher access.')
    marks = list(Mark.objects.filter(assignment__in=assignments).select_related('assignment__subject', 'assignment__teacher__user', 'assignment__period'))
    mark_map = {(m.enrollment_id, m.assignment_id): m for m in marks}
    if any((e.pk, a.pk) not in mark_map for e in enrollments for a in assignments):
        raise ValidationError('Marks are missing for the current class roster. Reopen the affected sheets and submit them again.')
    policy = ReportPolicy.objects.filter(pk=1).first() or ReportPolicy()
    school = SiteSettings.objects.first() or SiteSettings()
    history = list(Mark.objects.filter(enrollment__classroom=classroom, assignment__period__year=period.year,
        assignment__period__quarter__lt=period.quarter, assignment__status='submitted').select_related('assignment__period'))
    details = {d.enrollment_id: d for d in ReportDetails.objects.filter(enrollment__classroom=classroom, period=period)}
    snapshots = {}
    for enrollment in enrollments:
        snapshots[enrollment.pk] = make_snapshot(enrollment, period,
            [mark_map[(enrollment.pk, a.pk)] for a in assignments], policy, school,
            [m for m in history if m.enrollment_id == enrollment.pk], details.get(enrollment.pk))
    # Rank from complete submitted sheets, including other classes in the explicit stream.
    peer_scores = dict((pk, snap['average']) for pk, snap in snapshots.items())
    peers_complete = True
    peer_enrollments = list(Enrollment.objects.filter(classroom__in=class_scope(classroom)).exclude(classroom=classroom).select_related('student', 'classroom'))
    peer_assignments = list(TeachingAssignment.objects.filter(classroom__in=class_scope(classroom), period=period).exclude(classroom=classroom).select_related('subject', 'teacher__user'))
    peer_marks = list(Mark.objects.filter(assignment__in=peer_assignments).select_related('assignment__subject', 'assignment__teacher__user', 'assignment__period'))
    peer_map = {(m.enrollment_id, m.assignment_id): m for m in peer_marks}
    peer_history = list(Mark.objects.filter(enrollment__in=peer_enrollments, assignment__period__year=period.year,
        assignment__period__quarter__lt=period.quarter, assignment__status='submitted').select_related('assignment__period')) if policy.result_basis == 'final' else []
    for peer in peer_enrollments:
        expected = [a for a in peer_assignments if a.classroom_id == peer.classroom_id]
        if not expected or any(a.status != 'submitted' or (peer.pk, a.pk) not in peer_map for a in expected):
            peers_complete = False
            continue
        snap = make_snapshot(peer, period, [peer_map[(peer.pk, a.pk)] for a in expected], policy, school,
            [m for m in peer_history if m.enrollment_id == peer.pk])
        peer_scores[peer.pk] = snap['average']
    def rank(value, population, complete=True):
        valid = value is not None and complete and all(v is not None for v in population)
        return {'position': 1 + sum(Decimal(v) > Decimal(value) for v in population) if valid else None, 'total': len(population)}
    class_scores = [snap['average'] for snap in snapshots.values()]
    for pk, snap in snapshots.items():
        snap['class_rank'] = rank(snap['average'], class_scores)
        snap['stream_rank'] = rank(snap['average'], list(peer_scores.values()), peers_complete) if classroom.stream else None
        if snap['stream_rank']:
            snap['stream_rank']['total'] = len(enrollments) + len(peer_enrollments)
    now = timezone.now()
    for enrollment in enrollments:
        snapshot = snapshots[enrollment.pk]
        report, _ = StudentReport.objects.get_or_create(enrollment=enrollment, period=period)
        report.revision += 1
        reference = f'HFHS-{period.year}-Q{period.quarter}-{report.pk}-R{report.revision}'
        report.snapshot, report.pdf = snapshot, render_pdf(snapshot, reference, timezone.localtime(now))
        report.valid, report.published = True, False
        report.generated_by, report.generated_at = actor, now
        report.published_at = report.published_by = None
        report.save()
        audit(actor, 'report.generated', report, revision=report.revision, policy_revision=policy.revision)
    return len(enrollments)


@transaction.atomic
def publish_reports(actor, classroom, period, action, revisions):
    require_manager(actor)
    lock_class_scope(classroom.pk)
    reports = list(StudentReport.objects.filter(enrollment__classroom=classroom, period=period).defer('pdf'))
    actual = {str(r.pk): r.revision for r in reports}
    if actual != revisions:
        raise Conflict('Reports changed after this preview. Review the latest reports before publishing or withdrawing.')
    if not reports or (action == 'publish' and (any(not r.valid for r in reports)
            or len(reports) != Enrollment.objects.filter(classroom=classroom).count())):
        raise ValidationError('Generate a complete, current set of reports first.')
    if action not in {'publish', 'withdraw'}:
        raise ValidationError('Choose a valid publication action.')
    for report in reports:
        report.published = action == 'publish'
        report.published_at = timezone.now() if report.published else None
        if report.published and report.snapshot.get('schema_version') == 2:
            report.snapshot = dict(report.snapshot, published_at=timezone.localtime(report.published_at).strftime('%d %B %Y, %H:%M %Z'))
            reference = f'HFHS-{period.year}-Q{period.quarter}-{report.pk}-R{report.revision}'
            report.pdf = render_pdf(report.snapshot, reference, timezone.localtime(report.generated_at))
        report.published_by = actor if report.published else None
        fields = ['published', 'published_at', 'published_by']
        if report.published and report.snapshot.get('schema_version') == 2:
            fields += ['snapshot', 'pdf']
        report.save(update_fields=fields)
        audit(actor, 'report.' + action, report, revision=report.revision)


@transaction.atomic
def update_policy(actor, form):
    require_manager(actor)
    policy, _ = ReportPolicy.objects.get_or_create(pk=1)
    policy = ReportPolicy.objects.select_for_update().get(pk=policy.pk)
    check_revision(policy, form.cleaned_data['revision'])
    for field in ('heading', 'closing_note', 'show_average', 'pass_mark', 'result_basis', 'principal_name', 'report_footer'):
        setattr(policy, field, form.cleaned_data[field])
    policy.bands = form.cleaned_data['grading_bands']
    policy.revision += 1
    policy.full_clean()
    policy.save()
    audit(actor, 'policy.updated', policy, revision=policy.revision, bands=policy.bands)


@transaction.atomic
def update_report_details(actor, enrollment, period, revision, values):
    require_manager(actor)
    lock_class_scope(enrollment.classroom_id)
    details, _ = ReportDetails.objects.get_or_create(enrollment=enrollment, period=period)
    check_revision(details, revision)
    for field in ('days_absent', 'class_teacher_remark', 'principal_remark'):
        setattr(details, field, values[field])
    details.revision += 1
    details.full_clean()
    details.save()
    StudentReport.objects.filter(enrollment=enrollment, period=period).update(
        valid=False, published=False, published_at=None, published_by=None)
    audit(actor, 'report.details-updated', details, revision=details.revision)


@transaction.atomic
def update_setup_record(actor, model, pk, values, expected):
    require_manager(actor)
    # Shared metadata writes serialize with report generation in affected classes.
    list(SchoolClass.objects.order_by('pk').select_for_update())
    obj = model.objects.select_for_update().get(pk=pk)
    if {field: str(getattr(obj, field)) for field in expected} != expected:
        raise Conflict('This record changed. Reload and review the latest values.')
    if isinstance(obj, SchoolClass):
        invalidate(obj.pk)
    for field, value in values.items():
        setattr(obj, field, value)
    obj.full_clean()
    obj.save()
    if isinstance(obj, SchoolClass):
        invalidate(obj.pk)
    elif isinstance(obj, Student):
        for enrollment in obj.enrollments.all():
            invalidate(enrollment.classroom_id)
    elif isinstance(obj, AcademicSubject):
        for assignment in TeachingAssignment.objects.filter(subject=obj):
            invalidate(assignment.classroom_id, assignment.period_id)
    elif isinstance(obj, ReportingPeriod):
        for assignment in TeachingAssignment.objects.filter(period=obj):
            invalidate(assignment.classroom_id, obj.pk)
    audit(actor, 'setup.updated', obj, fields=list(values))
    return obj
