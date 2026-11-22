"""Render only validated, stored snapshots; no remote URLs or uploaded templates."""
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image


def grade_for(score, bands):
    return next(b for b in bands if score >= Decimal(str(b['minimum'])))


def mean(scores, places='0.1'):
    return (sum((Decimal(str(score)) for score in scores), Decimal('0')) / len(scores)).quantize(Decimal(places), rounding=ROUND_HALF_UP) if scores else None


def display(value):
    return str(value) if value is not None else None


def lookup_ranges(bands):
    ordered = sorted(bands, key=lambda b: Decimal(str(b['minimum'])), reverse=True)
    upper = Decimal('100')
    result = []
    for i, band in enumerate(ordered):
        minimum = Decimal(str(band['minimum']))
        # Use an exclusive upper bound for fractional marks; there are no gaps.
        label = f'{minimum:g} - {upper:g}' if i == 0 else f'{minimum:g} - <{upper:g}'
        result.append(dict(band, range=label))
        upper = minimum
    return result


def make_snapshot(enrollment, period, marks, policy, school, history=(), details=None):
    historical = {(m.assignment.subject_id, m.assignment.period.quarter): m for m in history}
    quarters = list(range(1, period.quarter + 1))
    quarter_scores = {q: [] for q in quarters}
    rows, final_scores = [], []
    passed = 0
    for mark in sorted(marks, key=lambda m: (m.assignment.subject.code, m.assignment.subject.name)):
        subject = mark.assignment.subject
        values, numeric = [], []
        for q in quarters:
            item = mark if q == period.quarter else historical.get((subject.pk, q))
            score = item.score if item and item.status == 'scored' else None
            values.append(display(score) if score is not None else item.get_status_display() if item else 'Not recorded')
            if score is not None:
                numeric.append(score)
                if subject.include_in_summary:
                    quarter_scores[q].append(score)
        # A current absence/exemption stays visible and receives no final grade.
        final = mean(numeric, '1') if mark.status == 'scored' else None
        band = grade_for(final, policy.bands) if final is not None else None
        if final is not None and subject.include_in_summary:
            final_scores.append(final)
            passed += final >= policy.pass_mark
        rows.append({'code': subject.code, 'subject': subject.name, 'quarter_scores': values,
                     'status': mark.get_status_display(), 'score': display(final),
                     'grade': band['grade'] if band else '-', 'description': band['description'] if band else '',
                     'teacher_remark': (mark.teacher_remark or band['description']) if band else '',
                     'teacher': mark.assignment.teacher.user.get_full_name() or mark.assignment.teacher.user.username,
                     'comment': mark.comment, 'include_in_summary': subject.include_in_summary})
    averages = [display(mean(quarter_scores[q])) for q in quarters]
    average = mean(quarter_scores[period.quarter]) if policy.result_basis == 'current' else mean(final_scores)
    level = grade_for(average, policy.performance_levels) if average is not None else None
    return {'schema_version': 2, 'school': school.name, 'address': school.address, 'phone': school.phone, 'email': school.email,
            'student': enrollment.student.full_name, 'admission_number': enrollment.student.admission_number,
            'student_number': enrollment.student.student_number,
            'classroom': enrollment.classroom.name, 'stream': enrollment.classroom.stream,
            'year': period.year, 'quarter': period.quarter, 'quarters': quarters,
            'heading': policy.heading, 'closing_note': policy.closing_note, 'policy_revision': policy.revision,
            'bands': lookup_ranges(policy.bands), 'show_average': policy.show_average, 'rows': rows,
            'performance_levels': lookup_ranges(policy.performance_levels),
            'performance_level': level['level'] if level else None,
            'average': display(average), 'quarter_averages': averages,
            'scored_subjects': len(quarter_scores[period.quarter]), 'subjects_passed': passed, 'pass_mark': policy.pass_mark,
            'result_basis': policy.result_basis, 'result_basis_label': policy.get_result_basis_display(),
            'excluded_subjects': [r['subject'] for r in rows if not r['include_in_summary']],
            'days_absent': details.days_absent if details else None,
            'class_teacher_remark': details.class_teacher_remark if details else '',
            'principal_remark': details.principal_remark if details else '',
            'class_teacher_name': enrollment.classroom.class_teacher_name, 'principal_name': policy.principal_name,
            'reopens_on': period.reopens_on.isoformat() if period.reopens_on else None,
            'published_at': None, 'report_footer': policy.report_footer}


def _render_legacy_pdf(snapshot, reference, generated_at):
    # Bundled font preserves Sesotho names and avoids host font dependencies.
    if 'HFHSReport' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('HFHSReport', str(settings.BASE_DIR / 'static/fonts/school-font-2.ttf')))
    font = 'HFHSReport'
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = font
    normal = ParagraphStyle('ReportBody', parent=styles['Normal'], fontSize=9, leading=14, spaceAfter=6)
    small = ParagraphStyle('ReportSmall', parent=normal, fontSize=8, leading=11, spaceAfter=3)
    cell = ParagraphStyle('ReportCell', parent=small, spaceAfter=0)
    title = ParagraphStyle('ReportTitle', parent=normal, fontSize=19, leading=26, textColor=colors.HexColor('#174b3b'), spaceAfter=10)
    heading = ParagraphStyle('ReportHeading', parent=normal, fontSize=12, leading=18, spaceBefore=8, spaceAfter=5, keepWithNext=True)

    def p(value, style=normal):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), style)

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=17*mm, bottomMargin=21*mm, title=snapshot['heading'], author=snapshot['school'])
    story = [p(snapshot['school'], title), p(snapshot['address'], small),
             p(' | '.join(filter(None, [snapshot['phone'], snapshot['email']])), small),
             Spacer(1, 4*mm), p(snapshot['heading'], heading),
             p(f"{snapshot['year']} - Quarter {snapshot['quarter']}"),
             p(snapshot['student'], heading),
             p(f"Student number: {snapshot['admission_number']} | Class: {snapshot['classroom']}"), Spacer(1, 3*mm)]
    data = [[p('Subject', cell), p('Mark / 100', cell), p('Grade', cell), p('Comment', cell)]]
    for row in snapshot['rows']:
        comment = '\n'.join(filter(None, [row['description'], row['comment']]))
        data.append([p(row['subject'], cell), p(row['score'] if row['score'] is not None else row['status'], cell),
                     p(row['grade'], cell), p(comment, cell)])
    table = Table(data, colWidths=[46*mm, 26*mm, 19*mm, 83*mm], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9f0ec')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f6f8f6')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, 0), .8, colors.HexColor('#174b3b')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 4*mm)])
    summary = []
    if snapshot['show_average']:
        summary.append(p(f"Average: {snapshot['average'] or 'Not available'}{'%' if snapshot['average'] is not None else ''}", heading))
        summary.append(p(f"Equal weighting across {snapshot['scored_subjects']} subjects with numeric marks. Absences and exemptions are excluded from the average.", small))
    summary.append(p('Grading scale', heading))
    summary.append(p(' | '.join(f"{b['grade']}: {b['minimum']}%+" for b in snapshot['bands']), small))
    summary.extend([Spacer(1, 3*mm), p(snapshot['closing_note']), Spacer(1, 3*mm),
                  p(f"Report reference: {reference} | Generated: {generated_at:%d %b %Y %H:%M} | Policy: {snapshot['policy_revision']}", small)])
    story.append(KeepTogether(summary))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(font, 8)
        canvas.setFillColor(colors.HexColor('#52685d'))
        canvas.drawString(18*mm, 15*mm, 'Confidential student report - ' + snapshot['admission_number'])
        canvas.drawString(18*mm, 10*mm, reference)
        canvas.drawRightString(A4[0]-18*mm, 12*mm, f'Page {document.page}')
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def render_pdf(snapshot, reference, generated_at):
    if snapshot.get('schema_version') != 2:
        return _render_legacy_pdf(snapshot, reference, generated_at)
    if 'HFHSReport' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('HFHSReport', str(settings.BASE_DIR / 'static/fonts/school-font-2.ttf')))
    font = 'HFHSReport'
    body = ParagraphStyle('BodyV2', fontName=font, fontSize=7.5, leading=10, spaceAfter=3)
    cell = ParagraphStyle('CellV2', parent=body, fontSize=6.8, leading=9, spaceAfter=0)
    small = ParagraphStyle('SmallV2', parent=body, fontSize=6.5, leading=8.5)
    title = ParagraphStyle('TitleV2', parent=body, fontSize=19, leading=24, alignment=1, spaceAfter=4)
    heading = ParagraphStyle('HeadingV2', parent=body, fontSize=10, leading=14, alignment=1, spaceBefore=7, spaceAfter=6, keepWithNext=True)
    center = ParagraphStyle('CenterV2', parent=cell, alignment=1)
    def p(value, style=body):
        return Paragraph(escape(str(value if value is not None else 'Not recorded')).replace('\n', '<br/>'), style)
    def table(data, widths, header=True):
        t = Table(data, colWidths=[w*mm for w in widths], repeatRows=1 if header else 0, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#6d7c74')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e9f0ec') if header else colors.white),
            ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return t
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=10*mm, bottomMargin=17*mm, title=snapshot['heading'], author=snapshot['school'])
    contact = ParagraphStyle('ContactV2', parent=body, alignment=1)
    logo = settings.BASE_DIR / 'static/images/holy-family-original.png'
    header = [p(snapshot['school'], title), p(snapshot['address'], contact),
              p(' | '.join(filter(None, [snapshot['phone'], snapshot['email']])), contact),
              p(f"{snapshot['heading']} for Quarter {snapshot['quarter']} ({snapshot['year']})", heading)]
    story = [Table([[Image(str(logo), width=23*mm, height=25*mm, kind='proportional') if logo.exists() else '', header]],
                   colWidths=[28*mm, 158*mm]), Spacer(1, 3*mm)]
    position = lambda key: f"{snapshot[key]['position']} out of {snapshot[key]['total']}" if snapshot.get(key) and snapshot[key]['position'] is not None else 'Not available'
    metadata = [p(f"Name of student: {snapshot['student']}"), p(f"Class: {snapshot['classroom']}"),
                p(f"Student no: {snapshot['student_number'] or 'Not recorded'} | Admission no: {snapshot['admission_number']}"),
                p(f"Position in class: {position('class_rank')}"),
                p(f"Position in stream: {position('stream_rank')}" + (f" ({snapshot['stream']})" if snapshot['stream'] else '')),
                p(f"Days absent: {snapshot['days_absent'] if snapshot['days_absent'] is not None else 'Not recorded'}"),
                p(f"Subjects passed: {snapshot['subjects_passed']} (pass mark: {snapshot['pass_mark']}%)")]
    scale = table([[p('Range', small), p('Grade', small), p('Evaluation', small)]] +
                  [[p(b['range'], small), p(b['grade'], small), p(b['description'], small)] for b in snapshot['bands']], [22, 12, 33])
    scale.setStyle(TableStyle([('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
    story.extend([Table([[metadata, scale]], colWidths=[117*mm, 69*mm], style=[('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),0)]),
                  p('Student performance (%)', heading)])
    quarters = snapshot['quarters']
    # The teacher column absorbs space released by future quarters.
    widths = [11, 35] + [13]*len(quarters) + [13, 12, 30, 85-13*len(quarters)]
    labels = ['Code', 'Name of subject'] + [f'Quarter {q}' for q in quarters] + ['Final mark', 'Grade', "Teacher's remarks", 'Teacher']
    data = [[p(label, center) for label in labels]]
    for row in snapshot['rows']:
        remark = '\n'.join(filter(None, [row['teacher_remark'], row['comment']]))
        data.append([p(row['code'], cell), p(row['subject'] + (' *' if not row['include_in_summary'] else ''), cell)] +
                    [p(value, center) for value in row['quarter_scores']] +
                    [p(row['score'] if row['score'] is not None else row['status'], center), p(row['grade'], center), p(remark, cell), p(row['teacher'], cell)])
    if snapshot['show_average']:
        data.append([p('Average', cell), ''] + [p(v if v is not None else '-', center) for v in snapshot['quarter_averages']] +
                    [p(snapshot['average'] if snapshot['average'] is not None else '-', center), '', '', ''])
    performance = table(data, widths)
    if snapshot['show_average']:
        performance.setStyle(TableStyle([('SPAN', (0, -1), (1, -1))]))
    story.extend([performance, Spacer(1, 2*mm),
                  p(f"Result: {snapshot['performance_level'] or 'Not available'}", heading)])
    explanation = f"Final subject marks: equal average of available numeric quarters to date, rounded to a whole mark. Result and positions: {snapshot['result_basis_label'].lower()}. Absences, exemptions and missing marks are excluded; a current absence/exemption has no final grade."
    if snapshot['excluded_subjects']:
        explanation += ' * Excluded from summaries: ' + ', '.join(snapshot['excluded_subjects']) + '.'
    story.extend([p(explanation, small), p('Pass Ranges And Performance Level', heading)])
    story.append(table([[p('Performance', cell), p('Score range', cell), p('Skills and competences displayed', cell)]] +
        [[p(b['level'], cell), p(b['range'], center), p(b['description'], cell)] for b in snapshot['performance_levels']], [35, 25, 126]))
    story.extend([Spacer(1, 3*mm), table([
        [p('Class teacher remarks', cell), p(snapshot['class_teacher_remark'] or 'Not recorded', cell), p(snapshot['class_teacher_name'] or 'Class teacher', cell)],
        [p('Principal remarks', cell), p(snapshot['principal_remark'] or 'Not recorded', cell), p(snapshot['principal_name'] or 'Principal', cell)],
    ], [33, 118, 35], header=False), Spacer(1, 3*mm),
    p(f"School reopens on: {snapshot['reopens_on'] or 'Not recorded'}", small),
    p(f"Date of publication of result: {snapshot['published_at'] or 'Awaiting publication'}", small),
    p(snapshot['closing_note'], small),
    p(f"Report reference: {reference} | Generated: {generated_at:%d %b %Y %H:%M} | Policy: {snapshot['policy_revision']}", small)])
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.drawString(12*mm, 8*mm, snapshot.get('report_footer', ''))
        canvas.drawRightString(A4[0]-12*mm, 8*mm, f'Confidential | Page {document.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
