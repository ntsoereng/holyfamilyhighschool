from django import forms as django_forms
from django.contrib import messages
from django.contrib.auth import get_user_model, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.views import LoginView
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from . import forms, services
from .models import (AcademicSubject, AuditEvent, Enrollment, FamilyAccess, FeeClearance, PortalAccount,
                     ReportingPeriod, ReportDetails, ReportPolicy, SchoolClass, Student, StudentReport, TeachingAssignment)
from .permissions import is_manager, manager_required, portal_required


SETUP = {
    'students': (Student, forms.StudentForm, 'Students'),
    'classes': (SchoolClass, forms.ClassForm, 'Classes'),
    'subjects': (AcademicSubject, forms.SubjectForm, 'Academic subjects'),
    'periods': (ReportingPeriod, forms.PeriodForm, 'Reporting periods'),
    'enrollments': (Enrollment, forms.EnrollmentForm, 'Class rosters'),
    'assignments': (TeachingAssignment, forms.AssignmentForm, 'Teacher assignments'),
    'family-access': (FamilyAccess, forms.FamilyAccessForm, 'Verified family access'),
}


def error_message(exc):
    return ' '.join(exc.messages)


class PortalLoginView(LoginView):
    template_name = 'academics/login.html'
    authentication_form = forms.PortalAuthenticationForm

    def get_success_url(self):
        account = PortalAccount.objects.filter(user=self.request.user).first()
        if account and account.must_change_password:
            return reverse('academics:password')
        return self.get_redirect_url() or reverse('academics:home')


@require_POST
@login_required(login_url='academics:login')
def sign_out(request):
    logout(request)
    return redirect('academics:login')


@require_http_methods(['GET', 'POST'])
@login_required(login_url='academics:login')
def password(request):
    account = PortalAccount.objects.filter(user=request.user).first()
    if not account and not is_manager(request.user):
        raise PermissionDenied
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            current_user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if current_user.password != request.user.password:
                form.add_error(None, 'Your credentials changed during this request. Sign in again before changing your password.')
                return render(request, 'academics/form.html', {'form': form, 'title': 'Change your password', 'button': 'Change password'}, status=409)
            form.save()
            if account:
                account.must_change_password = False
                account.save(update_fields=['must_change_password'])
            services.audit(request.user, 'account.password-changed', account or request.user)
        update_session_auth_hash(request, form.user)
        messages.success(request, 'Your password has been changed.')
        return redirect('academics:home')
    return render(request, 'academics/form.html', {'form': form, 'title': 'Change your password',
        'intro': 'Choose a private password before accessing student records. Use at least 12 characters.', 'button': 'Change password'})


@require_safe
@portal_required
def home(request):
    if is_manager(request.user):
        return redirect('academics:office')
    account = request.portal_account
    if account.role == 'teacher':
        sheets = account.assignments.filter(active=True).select_related('classroom', 'period', 'subject')
        return render(request, 'academics/teacher.html', {'sheets': sheets})
    access = FamilyAccess.objects.filter(account=account, active=True, student__active=True)
    enrollments = Enrollment.objects.filter(student__family_access__in=access).select_related('student', 'classroom').distinct()
    page = Paginator(enrollments, 12).get_page(request.GET.get('page'))
    cards = []
    for enrollment in page:
        reports = {r.period_id: r for r in enrollment.reports.defer('pdf', 'snapshot')}
        fees = {f.period_id: f for f in enrollment.student.fee_clearances.all()}
        for period in ReportingPeriod.objects.filter(year=enrollment.year):
            report, fee = reports.get(period.pk), fees.get(period.pk)
            available = bool(report and report.valid and report.published and fee and fee.cleared and fee.outstanding == 0)
            cards.append({'enrollment': enrollment, 'period': period, 'report': report, 'fee': fee, 'available': available})
    return render(request, 'academics/family.html', {'cards': cards, 'page': page})


@require_http_methods(['GET', 'POST'])
@portal_required
def sheet(request, pk):
    manager = is_manager(request.user)
    queryset = TeachingAssignment.objects.select_related('classroom', 'period', 'subject', 'teacher__user')
    if not manager:
        queryset = queryset.filter(teacher=request.portal_account, teacher__role='teacher', active=True)
    assignment = get_object_or_404(queryset, pk=pk)
    roster = list(assignment.classroom.enrollments.select_related('student'))
    marks = {m.enrollment_id: m for m in assignment.marks.all()}
    initial = []
    for enrollment in roster:
        mark = marks.get(enrollment.pk)
        initial.append({'enrollment': enrollment.pk, 'status': mark.status if mark else '',
                        'score': mark.score if mark else None, 'comment': mark.comment if mark else '',
                        'teacher_remark': mark.teacher_remark if mark else ''})
    editable = not manager and assignment.status == 'draft' and assignment.period.is_open
    policy = ReportPolicy.objects.filter(pk=1).first() or ReportPolicy()
    formset = forms.MarkFormSet(request.POST if request.method == 'POST' and not manager else None, initial=initial, prefix='marks', form_kwargs={'bands': policy.bands})
    access_form = forms.AssignmentAccessForm(instance=assignment, initial={'revision': assignment.revision}, auto_id='access_%s')
    reason_form = forms.RevisionActionForm(initial={'revision': assignment.revision}, auto_id='reopen_%s')
    error, status = '', 200
    if request.method == 'POST':
        try:
            if manager:
                if request.POST.get('action') == 'access':
                    access_form = forms.AssignmentAccessForm(request.POST, instance=assignment, auto_id='access_%s')
                    if not access_form.is_valid():
                        raise ValidationError('Review the assignment access form.')
                    data = access_form.cleaned_data
                    services.review_assignment(request.user, pk, data['revision'], 'access', data['reason'], data['teacher'], data['active'])
                elif request.POST.get('action') == 'reopen':
                    reason_form = forms.RevisionActionForm(request.POST, auto_id='reopen_%s')
                    if not reason_form.is_valid():
                        raise ValidationError('Provide a reason for reopening this sheet.')
                    services.review_assignment(request.user, pk, reason_form.cleaned_data['revision'], 'reopen', reason_form.cleaned_data['reason'])
                else:
                    raise ValidationError('Choose a valid review action.')
            else:
                action_form = forms.SheetActionForm(request.POST)
                if not action_form.is_valid() or not formset.is_valid():
                    raise ValidationError('Correct the marked fields before saving.')
                services.save_sheet(request.user, pk, action_form.cleaned_data['revision'], formset.cleaned_data,
                                    submit=action_form.cleaned_data['action'] == 'submit')
            messages.success(request, 'Marks sheet updated.')
            return redirect('academics:sheet', pk=pk)
        except ValidationError as exc:
            error, status = error_message(exc), 409 if isinstance(exc, services.Conflict) else 400
            if isinstance(exc, services.Conflict):
                editable = False
    return render(request, 'academics/sheet.html', {'assignment': assignment, 'formset': formset,
        'rows': zip(roster, formset.forms), 'editable': editable, 'manager': manager,
        'access_form': access_form, 'reason_form': reason_form, 'error': error, 'grading_bands': policy.bands}, status=status)


@require_safe
@manager_required
def office(request):
    return render(request, 'academics/office.html', {'setup': SETUP,
        'student_count': Student.objects.count(), 'draft_count': TeachingAssignment.objects.filter(status='draft').count(),
        'report_count': StudentReport.objects.filter(valid=True).count(), 'recent': AuditEvent.objects.all()[:12]})


@require_http_methods(['GET', 'POST'])
@manager_required
def setup(request, section):
    if section not in SETUP:
        raise Http404
    model, form_class, title = SETUP[section]
    form = form_class(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.add_setup_record(request.user, form)
            messages.success(request, 'Record created. Changes to rosters or required subjects withdraw affected reports for regeneration.')
            return redirect('academics:setup', section=section)
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, error_message(exc) if isinstance(exc, ValidationError) else 'This record already exists. Refresh the page and check the records below.')
    records = model.objects.all()
    if model == Enrollment:
        records = records.select_related('student', 'classroom')
    elif model == TeachingAssignment:
        records = records.select_related('teacher__user', 'classroom', 'subject', 'period')
    elif model == FamilyAccess:
        records = records.select_related('account__user', 'student')
    page = Paginator(records.order_by('-pk'), 25).get_page(request.GET.get('page'))
    return render(request, 'academics/setup.html', {'form': form, 'title': title, 'section': section, 'page': page})


@require_http_methods(['GET', 'POST'])
@manager_required
def accounts(request):
    form = forms.AccountCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            account = services.create_account(request.user, form)
            messages.success(request, 'Account created. Share its username and temporary password privately after verifying the recipient. A password change is required at first sign in.')
            return redirect('academics:account', pk=account.pk)
        except IntegrityError:
            form.add_error('username', 'This username already exists.')
    page = Paginator(PortalAccount.objects.select_related('user', 'reviewed_by').order_by('user__username'), 25).get_page(request.GET.get('page'))
    return render(request, 'academics/accounts.html', {'form': form, 'page': page})


@require_http_methods(['GET', 'POST'])
@manager_required
def account(request, pk):
    record = get_object_or_404(PortalAccount.objects.select_related('user'), pk=pk)
    reset_form = SetPasswordForm(record.user, request.POST if request.POST.get('action') == 'reset-password' else None)
    reason_form = forms.ReasonForm(request.POST or None)
    reset_reason_form = forms.ReasonForm(request.POST or None, auto_id='reset_reason_%s')
    error = ''
    if request.method == 'POST' and reason_form.is_valid():
        action = request.POST.get('action')
        if action != 'reset-password' or reset_form.is_valid():
            try:
                services.review_account(request.user, pk, action, reason_form.cleaned_data['reason'], reset_form)
                messages.success(request, 'Account access reviewed. Deactivated accounts require a password reset before reactivation.')
                return redirect('academics:account', pk=pk)
            except ValidationError as exc:
                error = error_message(exc)
    return render(request, 'academics/account.html', {'record': record, 'reset_form': reset_form,
        'reset_reason_form': reset_reason_form, 'form': reason_form, 'error': error})


@require_http_methods(['GET', 'POST'])
@manager_required
def family_access(request, pk):
    grant = get_object_or_404(FamilyAccess.objects.select_related('account__user', 'student', 'reviewed_by'), pk=pk)
    form = forms.ReasonForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            services.review_family_access(request.user, pk, request.POST.get('action'), form.cleaned_data['reason'])
            messages.success(request, 'Family access reviewed.')
            return redirect('academics:family-access', pk=pk)
        except ValidationError as exc:
            form.add_error(None, error_message(exc))
    return render(request, 'academics/access.html', {'grant': grant, 'form': form})


@require_http_methods(['GET', 'POST'])
@manager_required
def period_access(request, pk):
    period = get_object_or_404(ReportingPeriod, pk=pk)
    form = forms.ReasonForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        action = request.POST.get('action')
        if action in {'open', 'close'}:
            with transaction.atomic():
                period = ReportingPeriod.objects.select_for_update().get(pk=pk)
                period.is_open = action == 'open'
                period.save(update_fields=['is_open'])
                services.audit(request.user, 'period.' + action, period, reason=form.cleaned_data['reason'])
            messages.success(request, 'Reporting period updated. Submitted sheets stay locked until explicitly reopened.')
            return redirect('academics:period', pk=pk)
        form.add_error(None, 'Choose a valid action.')
    return render(request, 'academics/period.html', {'period': period, 'form': form})


@require_http_methods(['GET', 'POST'])
@manager_required
def batch(request):
    form = forms.ReportBatchForm(request.POST if request.method == 'POST' else request.GET or None)
    classroom = period = None
    reports, rows, assignments = [], [], []
    error, status = '', 200
    if form.is_bound and form.is_valid():
        classroom, period = form.cleaned_data['classroom'], form.cleaned_data['period']
        if request.method == 'POST':
            try:
                token = signing.loads(request.POST.get('preview', ''), salt='academic-report-preview', max_age=7200)
                if token['classroom'] != classroom.pk or token['period'] != period.pk:
                    raise signing.BadSignature
                action = request.POST.get('action')
                if action == 'generate':
                    count = services.generate_reports(request.user, classroom, period)
                    messages.success(request, f'{count} reports generated privately. Preview them before publishing.')
                else:
                    services.publish_reports(request.user, classroom, period, action, token['revisions'])
                    messages.success(request, 'Reports published. Families with explicit fee clearance can now access them.' if action == 'publish' else 'Reports withdrawn.')
                return redirect(reverse('academics:batch') + f'?classroom={classroom.pk}&period={period.pk}')
            except (signing.BadSignature, KeyError, TypeError):
                error, status = 'This preview expired or changed. Reload the page before continuing.', 409
            except ValidationError as exc:
                error, status = error_message(exc), 409 if isinstance(exc, services.Conflict) else 400
        reports = list(StudentReport.objects.filter(enrollment__classroom=classroom, period=period).defer('pdf', 'snapshot'))
        by_enrollment = {r.enrollment_id: r for r in reports}
        clearances = {f.student_id: f for f in FeeClearance.objects.filter(period=period, student__enrollments__classroom=classroom)}
        for enrollment in classroom.enrollments.select_related('student'):
            rows.append({'enrollment': enrollment, 'report': by_enrollment.get(enrollment.pk), 'fee': clearances.get(enrollment.student_id)})
        assignments = classroom.assignments.filter(period=period).select_related('subject', 'teacher__user')
    token = signing.dumps({'classroom': classroom.pk, 'period': period.pk, 'revisions': {str(r.pk): r.revision for r in reports}}, salt='academic-report-preview') if classroom else ''
    return render(request, 'academics/batch.html', {'form': form, 'classroom': classroom, 'period': period,
        'rows': rows, 'assignments': assignments, 'preview': token, 'error': error}, status=status)


@require_http_methods(['GET', 'POST'])
@manager_required
def fees(request, enrollment_pk, period_pk):
    enrollment = get_object_or_404(Enrollment.objects.select_related('student', 'classroom'), pk=enrollment_pk)
    period = get_object_or_404(ReportingPeriod, pk=period_pk, year=enrollment.year)
    clearance = FeeClearance.objects.filter(student=enrollment.student, period=period).first()
    form = forms.FeeForm(request.POST or None, instance=clearance, initial={'revision': clearance.revision if clearance else 0})
    status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            services.update_fees(request.user, enrollment.student, period, form.cleaned_data['revision'], form.cleaned_data)
            messages.success(request, 'Fee status reviewed. Report access now reflects this balance and clearance.')
            return redirect(reverse('academics:batch') + f'?classroom={enrollment.classroom_id}&period={period.pk}')
        except ValidationError as exc:
            form.add_error(None, error_message(exc))
            status = 409 if isinstance(exc, services.Conflict) else 400
    return render(request, 'academics/form.html', {'form': form, 'title': f'Fee clearance: {enrollment.student}',
        'intro': f'{period}. Enter the total fees preventing this report’s release. A zero balance still needs explicit clearance. Notes remain private to administrators.', 'button': 'Save fee review'}, status=status)


def accessible_report(request, pk):
    queryset = StudentReport.objects.select_related('enrollment__student', 'enrollment__classroom', 'period').defer('pdf')
    if not is_manager(request.user):
        if request.portal_account.role != 'family':
            raise Http404
        queryset = queryset.filter(enrollment__student__active=True,
            enrollment__student__family_access__account=request.portal_account, enrollment__student__family_access__active=True)
    report = get_object_or_404(queryset, pk=pk)
    fee = FeeClearance.objects.filter(student_id=report.enrollment.student_id, period=report.period).first()
    allowed = is_manager(request.user) or bool(report.valid and report.published and fee and fee.cleared and fee.outstanding == 0)
    return report, fee, allowed


@require_safe
@portal_required
def report(request, pk):
    document, fee, allowed = accessible_report(request, pk)
    if not allowed:
        return render(request, 'academics/held.html', {'document': document, 'fee': fee}, status=403)
    return render(request, 'academics/report.html', {'document': document, 'snapshot': document.snapshot, 'manager': is_manager(request.user)})


@require_safe
@portal_required
def download(request, pk):
    document, fee, allowed = accessible_report(request, pk)
    if not allowed:
        return render(request, 'academics/held.html', {'document': document, 'fee': fee}, status=403)
    if not document.valid:
        raise Http404('This report needs regeneration.')
    services.audit(request.user, 'report.downloaded', document, revision=document.revision, administrator=is_manager(request.user))
    response = HttpResponse(bytes(document.pdf), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="HFHS-{document.period.year}-Q{document.period.quarter}-{document.pk}.pdf"'
    return response


@require_http_methods(['GET', 'POST'])
@manager_required
def policy(request):
    record = ReportPolicy.objects.filter(pk=1).first() or ReportPolicy()
    form = forms.PolicyForm(request.POST or None, instance=record)
    status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            services.update_policy(request.user, form)
            messages.success(request, 'Report policy updated. Existing snapshots keep their original policy; regenerate a class’s reports to apply the new policy, then publish again.')
            return redirect('academics:policy')
        except ValidationError as exc:
            form.add_error(None, error_message(exc))
            status = 409 if isinstance(exc, services.Conflict) else 400
    return render(request, 'academics/form.html', {'form': form, 'title': 'Report template and grading policy',
        'intro': 'Settings apply to newly generated reports. Subject evaluations supply the teacher remarks dropdown. Final subject marks average numeric quarters to date and round to a whole mark. The result basis controls the overall average, performance level and positions. Subject exclusions are configured under Academic subjects.', 'button': 'Save report policy'}, status=status)


@require_safe
@manager_required
def audit_log(request):
    events = AuditEvent.objects.select_related('actor')
    action = request.GET.get('action', '').strip()[:50]
    if action:
        events = events.filter(action=action)
    page = Paginator(events, 50).get_page(request.GET.get('page'))
    return render(request, 'academics/audit.html', {'page': page, 'action': action})


@require_http_methods(['GET', 'POST'])
@manager_required
def report_details(request, enrollment_pk, period_pk):
    enrollment = get_object_or_404(Enrollment.objects.select_related('student', 'classroom'), pk=enrollment_pk)
    period = get_object_or_404(ReportingPeriod, pk=period_pk, year=enrollment.year)
    record = ReportDetails.objects.filter(enrollment=enrollment, period=period).first()
    form = forms.ReportDetailsForm(request.POST or None, instance=record, initial={'revision': record.revision if record else 0})
    status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            services.update_report_details(request.user, enrollment, period, form.cleaned_data['revision'], form.cleaned_data)
            messages.success(request, 'Attendance and report remarks saved. Regenerate and review the report before publishing.')
            return redirect(reverse('academics:batch') + f'?classroom={enrollment.classroom_id}&period={period.pk}')
        except ValidationError as exc:
            form.add_error(None, error_message(exc))
            status = 409 if isinstance(exc, services.Conflict) else 400
    return render(request, 'academics/form.html', {'form': form, 'title': f'Report details: {enrollment.student}',
        'intro': f'{period}. Leave days absent blank if not recorded; enter 0 for confirmed full attendance. Class teacher and principal remarks are separate from subject grading remarks.',
        'button': 'Save report details'}, status=status)


@require_http_methods(['GET', 'POST'])
@manager_required
def setup_edit(request, section, pk):
    if section not in {'students', 'classes', 'subjects', 'periods'}:
        raise Http404
    model, form_class, title = SETUP[section]
    obj = get_object_or_404(model, pk=pk)
    field_names = form_class.Meta.fields
    expected = {field: str(getattr(obj, field)) for field in field_names}
    token = signing.dumps({'section': section, 'pk': pk, 'values': expected}, salt='academic-setup-edit')
    form = form_class(request.POST or None, instance=obj)
    # Relationships with existing marks retain their identity.
    locked = {'students': ['admission_number'], 'classes': ['name', 'year'], 'subjects': ['name'], 'periods': ['year', 'quarter', 'is_open']}[section]
    for field in locked:
        form.fields[field].disabled = True
    status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            original = signing.loads(request.POST.get('edit_token', ''), salt='academic-setup-edit', max_age=7200)
            if original['section'] != section or original['pk'] != pk:
                raise signing.BadSignature
            services.update_setup_record(request.user, model, pk,
                {field: form.cleaned_data[field] for field in field_names if field not in locked}, original['values'])
            messages.success(request, 'Record updated. Affected reports need regeneration and review.')
            return redirect('academics:setup', section=section)
        except (signing.BadSignature, KeyError, TypeError):
            form.add_error(None, 'This edit expired. Reload the page and review the record.')
            status = 409
        except ValidationError as exc:
            form.add_error(None, error_message(exc))
            status = 409 if isinstance(exc, services.Conflict) else 400
    # Preserve the submitted token on validation errors so stale edits cannot overwrite changes.
    form.fields['edit_token'] = django_forms.CharField(widget=django_forms.HiddenInput, required=False, initial=request.POST.get('edit_token', token))
    return render(request, 'academics/form.html', {'form': form, 'title': f'Edit {title.lower()}: {obj}',
        'intro': 'Changes withdraw affected reports. Regenerate and review them before publishing.', 'button': 'Save changes'}, status=status)
