from pathlib import Path
from xml.sax.saxutils import escape
from decimal import Decimal, ROUND_HALF_UP
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle, Spacer, Frame, KeepTogether, Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path.cwd()
OUT = ROOT / 'output/pdf/report-module-testing-walkthrough.pdf'
pdfmetrics.registerFont(TTFont('Guide', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('GuideBold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
pdfmetrics.registerFontFamily('Guide', normal='Guide', bold='GuideBold', italic='Guide', boldItalic='GuideBold')
GREEN = colors.HexColor('#163e32')
GOLD = colors.HexColor('#b7914d')
INK = colors.HexColor('#24362e')
MUTED = colors.HexColor('#59685f')
PALE = colors.HexColor('#edf3ef')
LINE = colors.HexColor('#cbd8d0')
W, H = A4
WIDTH = W - 32*mm
styles = {
    'body': ParagraphStyle('body', fontName='Guide', fontSize=9.5, leading=14, textColor=INK, spaceAfter=7),
    'small': ParagraphStyle('small', fontName='Guide', fontSize=8.2, leading=11.5, textColor=MUTED, spaceAfter=5),
    'h1': ParagraphStyle('h1', fontName='GuideBold', fontSize=21, leading=27, textColor=GREEN, spaceAfter=12),
    'h2': ParagraphStyle('h2', fontName='GuideBold', fontSize=12, leading=16, textColor=GREEN, spaceBefore=7, spaceAfter=7),
    'case': ParagraphStyle('case', fontName='GuideBold', fontSize=12.3, leading=16.5, textColor=GREEN, spaceAfter=5),
    'kicker': ParagraphStyle('kicker', fontName='GuideBold', fontSize=8, leading=11, textColor=GOLD, spaceAfter=7),
    'cell': ParagraphStyle('cell', fontName='Guide', fontSize=8, leading=11, textColor=INK),
    'head': ParagraphStyle('head', fontName='GuideBold', fontSize=8, leading=11, textColor=GREEN),
    'cover': ParagraphStyle('cover', fontName='GuideBold', fontSize=32, leading=39, textColor=GREEN, spaceAfter=18),
}

def p(text='', style='body'):
    return Paragraph(text, styles[style])

def table(rows, widths=None, header=True, row_heights=None):
    widths = widths or [WIDTH / len(rows[0])] * len(rows[0])
    converted = [[v if not isinstance(v, str) else p(v, 'head' if header and i == 0 else 'cell') for v in row] for i,row in enumerate(rows)]
    t = Table(converted, colWidths=widths, rowHeights=row_heights, hAlign='LEFT')
    cmds = [('VALIGN',(0,0),(-1,-1),'TOP'), ('LINEBELOW',(0,0),(-1,0),0.8,GREEN),
            ('LINEBELOW',(0,1),(-1,-1),0.35,LINE), ('LEFTPADDING',(0,0),(-1,-1),7),
            ('RIGHTPADDING',(0,0),(-1,-1),7), ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6)]
    if header:
        cmds += [('BACKGROUND',(0,0),(-1,0),PALE)]
    t.setStyle(TableStyle(cmds))
    return t

def callout(title, body):
    t = Table([[p(title,'head')],[p(body,'body')]], colWidths=[WIDTH])
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),0.5,LINE),
                          ('LEFTPADDING',(0,0),(-1,-1),11),('RIGHTPADDING',(0,0),(-1,-1),11),
                          ('TOPPADDING',(0,0),(-1,0),9),('BOTTOMPADDING',(0,-1),(-1,-1),6)]))
    return t

def writing(label, lines=2):
    result=[p(label,'small')]
    for _ in range(lines):
        t=Table([['']],colWidths=[WIDTH],rowHeights=[15])
        t.setStyle(TableStyle([('LINEBELOW',(0,0),(-1,-1),0.4,LINE)]))
        result.append(t)
    return result

pages=[]
def add_page(kicker, title, content):
    pages.append((title,[p(kicker,'kicker'),p(title,'h1')]+content))

# 01 - Cover
logo=ROOT/'static/images/holy-family-original.png'
cover=[]
if logo.exists():
    cover += [Image(str(logo),width=27*mm,height=30*mm,kind='proportional',hAlign='LEFT'),Spacer(1,12)]
cover += [p('HOLY FAMILY HIGH SCHOOL','kicker'),p('Report module<br/>Testing walkthrough','cover'),
          p('A practical workbook for school administrators, teachers, students and parents.'),
          p('Version 1.0 | 22 November 2026 | 30 scenarios','small'),Spacer(1,12),
          callout('Purpose','Follow the complete reporting cycle, compare actual results with expected results, and record strengths, weaknesses and improvement requests. All scenario results start as <b>Not run</b>.'),
          Spacer(1,16),table([['Testing route','Pages'],['Prepare roles, records and expected marks','2-5'],['Run the step-by-step scenarios T01-T30','6-20'],['Assess gaps and record execution results','21-22'],['Log findings, decide readiness and reset','23-24']],[WIDTH*0.8,WIDTH*0.2]),Spacer(1,14)]
cover += writing('Tester / team: _________________________   Run date: _________________________',1)
cover += writing('Test site URL: _________________________   Build / revision: ___________________',1)
cover += [p('Use fictional records on a test installation. This document creates no accounts, changes no school records and does not constitute a completed test report.','small')]
pages.append(('Testing walkthrough',cover))

# 02 - How to run
add_page('PREPARE / 01','How to run this workbook',[
    p('Work through T01-T18 first. These establish a clean baseline. Record screenshots and expected totals before T19-T30, which deliberately withdraw reports or alter access. Restore the baseline between independent destructive scenarios.'),
    table([['Role / session','Responsibility'],['Reporting administrator','Creates setup records and accounts; reviews marks, generates, checks fees and publishes. Start with an existing authorised administrator.'],['Teacher A / Teacher B','Each uses a separate teacher account and assigned subject sheets. Administrators review sheets; teachers enter the marks.'],['Student / parent / other family','Use separate accounts and browser profiles or private windows. A student uses the family portal role with relationship Student.']],[WIDTH*0.29,WIDTH*0.71]),
    p('Before starting','h2'),
    p('1. Ask the technical owner to identify the test site and confirm a restorable baseline backup.<br/>2. Use the manual fixture on pages 3-4. Use fresh TEST identifiers for each run; do not reuse real admission numbers.<br/>3. Record the site URL, date, browser/device and build on page 1. Check school contact details on held-report pages.<br/>4. Obtain individual test credentials privately. Do not write passwords in this workbook or screenshots.<br/>5. Keep report PDFs and screenshots together under the run date. Note the role, class, quarter and report revision in each evidence filename.'),
    table([['Outcome','When to use it'],['PASS','Actual result matches every expected check; keep evidence.'],['FAIL','A supported feature behaves differently from the expected result.'],['BLOCKED','You cannot execute because access, data or an external dependency is missing.'],['GAP','The school needs a workflow the module does not currently provide.'],['NOT RUN','No test execution or evidence yet. Do not count as a pass.']],[WIDTH*.19,WIDTH*.81]),
    p('Where expected results came from','h2'),
    p('Reviewed against the local implementation on 22 November 2026: academics/README.md, models.py, forms.py, services.py, reports.py, views.py, urls.py and portal templates. Expected results describe the current build, not a guarantee that a deployment has passed testing.','small'),
    p('Optional existing demo: demo.admin, demo.teacher.maths, demo.teacher.languages, demo.parent and demo.student may exist on a seeded local copy. Its names, marks and fee states differ from this workbook. Use its actual data for exploratory tests; use pages 3-4 for exact arithmetic checks. Demo passwords are generated locally and are not printed here.','small')
])

# 03 - fixture
add_page('PREPARE / 02','Create a small test school',[
    p('Use academic year <b>2026</b>, open reporting periods <b>Q1, Q2 and Q3</b>, and reopening date <b>12 January 2027</b> for Q3. If these periods already exist on the test copy, reuse them without creating duplicates.'),
    table([['Setup record','Values'],['Classes','TEST Grade 9A and TEST Grade 9B; stream TEST Grade 9 on both; class teacher names Test Class Teacher A / B.'],['Grading policy','Use the supplied 13-band school lookup; pass mark 50; result basis Current quarter average; show average enabled; principal name Test Principal.'],['Subjects','TEST English - code 0175; TEST Mathematics - code 0178; TEST LBSE - code 2030. Include English and Mathematics in summary; clear Include in summary for LBSE.']],[WIDTH*.24,WIDTH*.76]),
    p('Students and enrollment','h2'),
    table([['Admission / student no.','Fictional full name','Class'],['TEST-001 / TS-001','TEST Lerato Mokoena','TEST Grade 9A'],['TEST-002 / TS-002','TEST Thabo Molefe','TEST Grade 9A'],['TEST-003 / TS-003','TEST Mpho Mohapi','TEST Grade 9B'],['TEST-004 / TS-004','TEST Neo Rantso','Leave unenrolled until T22']],[WIDTH*.31,WIDTH*.37,WIDTH*.32]),
    p('Accounts and assignments','h2'),
    p('Create teacher accounts <b>test.teacher.a</b> and <b>test.teacher.b</b>. Assign Teacher A to English and LBSE, Teacher B to Mathematics, in both classes for each of Q1-Q3. This gives <b>18 subject sheets</b>; enter three subject records for each enrolled student each quarter.'),
    p('Create family-role accounts <b>test.student.lerato</b>, <b>test.parent</b> and <b>test.other.family</b>. Link the student account only to TEST-001 with relationship Student; link test.parent to TEST-001 and TEST-002 as Parent; link test.other.family only to TEST-003 as Guardian. Record "Fictional identity verified for scenario testing" as the verification note.'),
    callout('Keep the baseline complete','Create all required subjects and assignments before generating reports. Finish marks entry in both classes before checking stream positions. Do not enroll TEST-004 yet; its later arrival is an intentional failure test.'),
    p('New-run suffix: __________   Administrator: __________   Fixture verified by: __________','small')
])

# 04 - arithmetic oracle
add_page('PREPARE / 03','Marks and calculation answer key',[
    p('Enter the following numeric marks. Leave teacher remarks on <b>Automatic from final mark</b> and notes blank for the baseline. Each score is a percentage out of 100.'),
    table([['Student','Subject / code','Q1','Q2','Q3','Final / grade / remark'],
           ['TEST-001','English / 0175','42','76','70','63 / D+ / Good'],
           ['TEST-001','Mathematics / 0178','65','84','56','68 / C / Much Better'],
           ['TEST-001','LBSE / 2030 *','49','48','73','57 / D / Fair'],
           ['TEST-002','English / 0175','80','80','80','80 / B+ / Keep It Up'],
           ['TEST-002','Mathematics / 0178','90','90','90','90 / A* / Excellent'],
           ['TEST-002','LBSE / 2030 *','10','10','10','10 / H / Work Hard'],
           ['TEST-003','English / 0175','60','60','63','61 / D+ / Good'],
           ['TEST-003','Mathematics / 0178','60','60','63','61 / D+ / Good'],
           ['TEST-003','LBSE / 2030 *','100','100','100','100 / A* / Excellent']],
          [WIDTH*.13,WIDTH*.24,WIDTH*.065,WIDTH*.065,WIDTH*.065,WIDTH*.365]),
    p('* LBSE stays visible but is excluded from averages, positions and subjects passed. The low and high LBSE marks deliberately test that exclusion.','small'),
    table([['Q3 summary','TEST-001','TEST-002','TEST-003'],['Quarter averages Q1 / Q2 / Q3','53.5 / 80.0 / 63.0','85.0 / 85.0 / 85.0','60.0 / 60.0 / 63.0'],['Final-mark summary column','63.0','85.0','63.0'],['Result / subjects passed','PROFICIENT / 2','ADVANCE / 2','PROFICIENT / 2'],['Class position','2 out of 2','1 out of 2','1 out of 1'],['Stream position','2 out of 3','1 out of 3','2 out of 3']],[WIDTH*.31,WIDTH*.23,WIDTH*.23,WIDTH*.23]),
    p('Why these are the answers','h2'),
    p('TEST-001 English: (42 + 76 + 70) / 3 = 62.666..., rounded half up to 63. Mathematics rounds to 68. Its Q3 average is (70 + 56) / 2 = 63.0. The overall result uses this current-quarter average, <b>not</b> the mean of its final marks (65.5). TEST-001 and TEST-003 tie in the stream.'),
    p('The final-mark average cell intentionally repeats the configured result average (63.0 here). Check this carefully with staff: the column label may need clarification even when the current calculation is correct.','small')
])

# 05 - navigation, gates
add_page('PREPARE / 04','Navigation and release rules',[
    table([['Screen / route','What to do there'],['School portal: /portal/','Teacher sheets or student/family report cards, according to role.'],['Administration: /portal/office/','Classes, students, subjects, periods, class rosters and teacher assignments.'],['Accounts & access: /portal/office/accounts/','Create/review accounts; open family links and teacher assignments.'],['Grading policy: /portal/office/policy/','Lookup evaluations, pass mark, result basis and principal name.'],['Reports & fees: /portal/office/reports/','Select class and quarter; review sheets, details, fee status, PDFs and publication.'],['Audit log: /portal/office/audit/','Read the recorded actions and actors.']],[WIDTH*.46,WIDTH*.54]),
    p('Family release gate: every requirement must hold','h2'),
    p('The student and account are active; the family relationship is active and verified; the report is current and published; a fee review exists with outstanding amount exactly zero and Cleared explicitly checked. Administrator preview bypasses publication and fees, so it cannot prove student access.'),
    table([['Q3 fee review','Cleared?','Expected family result after publication'],['No fee review','No','Held; contact office to confirm balance.'],['M 250.00','No','Held; show outstanding amount and school contact.'],['M 0.00','No','Held; zero alone does not release the report.'],['M 0.00','Yes','Available if every other release condition is met.'],['M 250.00','Yes attempted','Validation error; cannot clear a positive balance.']],[WIDTH*.26,WIDTH*.17,WIDTH*.57]),
    callout('Approval and release are separate checks','There is no separate Approved state or Approve button. The administrator checks submissions and previews, then chooses Publish reviewed reports. Fee clearance controls each student\'s release. The same administrator can do all these steps; independent approval is a capability to assess.'),
    p('Use Q3 for release tests. Complete Q1-Q2 sheets to supply history; generating Q1-Q2 reports is optional until T20. Do not edit an earlier quarter while measuring the page 4 baseline.','small')
])

# Scenario data: id, title, role/precondition, steps, expected, focus
cases = [
('T01','Create accounts and complete first sign-in','Administrator, then each new account. Existing reporting administrator available.',[
'Open Accounts & access. Create the two teacher and three family-role accounts from page 3 with individual temporary passwords.',
'Sign in as a new teacher and a new family user in separate sessions. Try to go directly to the portal before changing the temporary password.',
'Complete the required password change (at least 12 characters, subject to the password rules). Sign out and sign in again.'
], 'First-use accounts must change passwords before records are accessible. Teacher sees assigned sheets; family sees only linked students, or no linked reports yet. Ordinary portal accounts gain no website editing or administration rights.', 'Record clarity of account creation, password prompts and role-specific landing pages.'),
('T02','Configure classes, quarters and grading','Administrator. Use the fixture on page 3.',[
'Create the two TEST classes for 2026 with the same TEST Grade 9 stream; create/reuse Q1-Q3 periods and keep them open.',
'Create the three TEST subjects with the exact codes. Clear Include in summary for TEST LBSE.',
'In Grading policy verify all 13 bands, pass mark 50 and Current quarter average. Enter the principal name; add class teacher names and the Q3 reopening date through Edit report information.'
], 'Leading zero in 0175/0178 is preserved. Bands include zero and have unique minimums. Invalid or incomplete band definitions are rejected. Test configuration is saved; existing custom policy may need deliberate adjustment on this test copy.', 'Can a school administrator find the difference between subject grading, pass threshold and overall performance?'),
('T03','Add students and reject duplicate identities','Administrator. Classes exist.',[
'Open Students and create TEST-001 to TEST-004 with admission and separate student numbers as on page 3.',
'Try a second student with admission number TEST-001. Try submitting a new student with no full name or no admission number.',
'Open Edit report information for TEST-001. Confirm the name and student number can be corrected; leave original values after checking.'
], 'Valid records save; duplicate admission number and missing required fields are rejected. The admission number is locked in the edit workflow. Student numbers are separate from admission numbers and are not a unique identity check.', 'Assess duplicate prevention and whether staff need additional student identifiers or import tools.'),
('T04','Enroll students and protect year boundaries','Administrator. T03 complete.',[
'Open Class rosters. Enroll TEST-001 and TEST-002 in TEST Grade 9A, and TEST-003 in TEST Grade 9B.',
'Attempt to enroll TEST-001 again in 9A, then in 9B for the same 2026 year.',
'Open teacher sheets after assignment setup and confirm the intended students appear. Keep TEST-004 unenrolled.'
], 'One enrollment per student per year: duplicate and same-year second-class enrollment are rejected. Creating a student by itself does not place that student on a marks sheet. Next-year enrollment is a separate record.', 'Assess roster visibility, error wording and how a same-year transfer request should be handled.'),
('T05','Assign every required subject','Administrator. Teacher accounts and fixture records exist.',[
'Create English/LBSE assignments for Teacher A and Mathematics for Teacher B, for each class and each of Q1-Q3.',
'Try assigning the same class/subject/quarter to a second teacher. If an existing other-year period is available, try using it with a 2026 class.',
'Compare the Reports & fees subject list with the complete three-subject checklist before anyone submits marks.'
], 'Duplicate sheet ownership and mismatched class/period years are rejected. Every subject expected on a report must have an assignment. An entirely omitted subject cannot be inferred by the system; detecting that omission is a manual review responsibility.', 'Record a GAP if the school requires an automatic curriculum completeness check.'),
('T06','Link students and families correctly','Administrator, then each family account. T03-T04 complete.',[
'Open Verified family access and create the three sets of links on page 3 with the stated relationships and a verification note.',
'Sign in as test.student.lerato, test.parent and test.other.family in separate sessions.',
'Confirm the student sees TEST-001 only, the parent sees TEST-001/002, and the other family sees TEST-003. Do not enter marks yet if testing an unprepared report card.'
], 'Only linked students appear; a student account uses the family role with Student relationship. Reports remain unavailable before publication/clearance. No public self-registration or admission-number-based self-linking is provided.', 'Check whether identity-verification instructions and multi-child navigation are clear.'),
('T07','Save a partial marks draft','Teacher A. Open Q1 English for TEST Grade 9A.',[
'Enter TEST-001 English mark 42 with Mark recorded status. Leave TEST-002 completely unentered and choose Save draft.',
'Leave the page, return to the sheet and confirm 42 is retained and the second row is still blank.',
'Try Submit & lock marks while TEST-002 remains unentered; then enter 80 and save the draft.'
], 'Partial drafts save without inventing marks. Blank is distinct from zero. Submission is blocked until each roster row has a valid score, absence or exemption. Revision changes after a successful save.', 'Note whether unsaved changes, draft status and validation errors are easy to understand.'),
('T08','Validate zero, decimals and invalid marks','Assigned teacher. Use an editable sheet and restore page 4 marks afterward.',[
'Try marks -1, 101, 70.123 and nonnumeric text; try a numeric score with Not entered status.',
'Enter a genuine 0 with Mark recorded status, save, leave and reopen. Repeat with 81.25.',
'Restore the baseline score from page 4 before submission. If a browser blocks input before save, record that behaviour too.'
], 'Scores accept 0 through 100 and at most two decimal places. Invalid combinations/values do not save. Zero and 81.25 persist as numeric marks; no blank row is silently converted into zero.', 'Assess field hints, accessible errors and whether invalid data causes any valid draft work to be lost.'),
('T09','Use the teacher remarks dropdown','Assigned teacher, then administrator. Test on an editable Q3 sheet.',[
'Inspect Grading lookup & teacher remarks. Leave Automatic from final mark for the baseline.',
'In a separate variation select another permitted evaluation, such as Excellent, on a low numeric mark; save and generate after completing the sheet.',
'Check the selected phrase in the report. Add a short test note and check its visibility. Restore Automatic and clear the note.'
], 'Options come from the policy evaluations; Automatic uses the rounded cumulative final mark at generation. A permitted manual choice is not forced to match the numeric grade. Subject notes appear in family reports/PDFs; they are not private staff notes.', 'Record whether manual overrides need a reason or approval. Never put confidential notes into this field.'),
('T10','Record absence, exemption and missing history','Assigned teacher. Run as a variation, then restore baseline marks.',[
'On one current-quarter row choose Absent, clear the numeric mark and leave the note empty. Try saving; then add "Test absence" and save.',
'Repeat with Exempt and an explanatory note. Try retaining a numeric mark or grading-lookup remark for these statuses.',
'Generate a complete class report with a current absence/exemption. Separately, on a fresh test copy leave an earlier-quarter sheet unsubmitted to inspect missing history.'
], 'Absence/exemption needs a note and no score or grading-lookup remark. A current absence/exemption gets no final grade and is excluded from its numeric summary. Missing historical marks show Not recorded; available numeric quarters are used, so missing history does not by itself block generation.', 'Confirm staff accept partial-history final marks and understand absence is different from an unentered mark.'),
('T11','Submit complete sheets and lock changes','Each assigned teacher. Restore the exact baseline first.',[
'Enter all page 4 marks for Q1-Q3 across both classes and all three subjects. Submit each complete sheet with Submit & lock marks.',
'Reopen a submitted sheet in the teacher session and try to change a mark.',
'As administrator, open the same sheet and verify review is read-only. Do not reopen it yet.'
], 'All 18 sheets show Submitted for review with submission details. Submitted sheets cannot be changed directly by the teacher or administrator. An administrator must return the sheet for correction before a teacher can resubmit.', 'Check that the boundary between saving, submitting and correcting a sheet is unmistakable.'),
('T12','Review submissions before generation','Administrator. Use a test variation with one Q3 draft, then restore and submit it.',[
'In Reports & fees select TEST Grade 9A and Q3. Follow each subject link and compare the roster/marks with the fixture.',
'Attempt Generate / regenerate privately while one assigned subject is still a draft. Confirm no complete-looking release is created.',
'Have the teacher submit the remaining sheet, then generate. Repeat for TEST Grade 9B.'
], 'Generation is refused until every assigned subject is submitted and the current roster has entries. Complete reports generate privately, not published. Review is manual: there is no distinct Approved status or recorded second-approver decision.', 'Log a GAP if independent teacher/head/principal approval is required before publication.'),
('T13','Capture attendance and report-level remarks','Administrator. Q3 reports can be generated.',[
'In Reports & fees use Attendance & report remarks for TEST-001. Save blank days absent, inspect the preview after regeneration, then save 0 and regenerate again.',
'Try negative days absent; enter class teacher remark "Apply more effort." and principal remark "Capable of better performance."',
'Confirm class teacher/principal names and reopening date come from class/policy/period settings. Save any correction, regenerate and review again.'
], 'Blank attendance means Not recorded; zero means confirmed no absences. Negative attendance is rejected. These remarks are separate from subject dropdowns. Detail edits withdraw the affected student report until regenerated; blank remarks/signoff names do not automatically block generation.', 'Decide whether the school needs mandatory attendance, signoff fields or a dedicated class-teacher entry role.'),
('T14','Verify totals, grades and stream positions','Administrator. Baseline marks restored and submitted in both classes.',[
'Generate Q3 reports for both classes, then compare every value with the page 4 answer key.',
'Check TEST-001 final marks 63/68/57, result average 63.0, two passes and LBSE exclusion. Compare the two tied stream positions.',
'In a separate variation reopen a peer class sheet; regenerate the other class and inspect stream position. Restore, resubmit and regenerate both classes.'
], 'The baseline matches the answer key exactly. Ties share position. With incomplete peer submissions the stream position is unavailable rather than guessed; an unset stream also gives no stream position. A student without any numeric summary prevents a complete population rank.', 'Record any disagreement about rounding, tie rules, pass thresholds or which average determines the result.'),
('T15','Inspect the HTML and PDF report','Administrator. Current Q3 reports generated privately.',[
'Open Preview report and Preview PDF for each student. Compare codes, quarter columns, final marks, evaluations, teacher names and all summary values.',
'Check performance descriptions, remarks/signoff names, attendance, reopening date, footer, reference and revision. Before publication the date must say Awaiting publication.',
'Download and open the PDF in a second reader; print or preview at A4 size. Keep a baseline copy for later corrections.'
], 'HTML and PDF agree. Text is legible, names and codes are intact, and no row/text is clipped. Reports are private and generation alone does not grant family access. School logos/contacts and the displayed publication state are accurate.', 'Note layout strengths, ambiguous labels, excessive pages and any difference between screen and printed output.'),
('T16','Test every fee-clearance state','Administrator and linked family. Q3 preview reviewed; publish 9A for this fee-gate test.',[
'After reviewing the PDF, publish TEST Grade 9A Q3. Use Review fees to check no review, positive M 250.00 without clearance, zero without clearance, and zero with Cleared checked. Enter a test review note for each save.',
'Attempt positive outstanding amount with Cleared checked, a negative amount, and saving without the required review note.',
'Use the linked family session after each state, with both the report page and download URL. Compare the release matrix on page 5.'
], 'Only an explicit zero-balance clearance satisfies the fee gate. Invalid amounts/clearance combinations or missing review notes are rejected. Held responses expose no marks or private payment-reference notes. This records the balance preventing release; it is not a payment transaction ledger.', 'Assess whether fees language, LSL/M amounts and office contact instructions are understandable.'),
('T17','Publish reviewed reports; student opens one','Administrator, then student. Current Q3 reports previewed; TEST-001 has zero cleared fees.',[
'In Reports & fees choose the class/quarter and Publish reviewed reports. Repeat for the second class once reviewed.',
'Sign in as test.student.lerato at /portal/. Choose View report, then Download PDF. Repeat as test.parent for the same student.',
'Inspect the publication date in both formats. Compare all marks with the administrator preview and check the downloaded file opens.'
], 'The linked, active and cleared student sees the published current report and can download its PDF. The actual publication time appears in HTML and PDF. Publication is class/quarter-wide; each student release still depends on that student\'s fee clearance.', 'Measure how easily a student can find the correct year, quarter and download action.'),
('T18','Try another student\'s report and office pages','Student, other family and teacher. Save test report/download URLs from the administrator session.',[
'As test.other.family, paste TEST-001 report and download URLs. As test.student.lerato, paste TEST-003 URLs.',
'As a teacher, paste a family report URL and another teacher\'s marks-sheet URL.',
'As student/family/teacher, try /portal/office/, /portal/office/accounts/ and /portal/office/policy/. Sign out and retry a private report URL.'
], 'Unauthorised records are denied or not found without exposing marks; office administration is inaccessible to ordinary portal roles. Signed-out users must authenticate. Do not accept hidden navigation links as proof: direct URLs must also be blocked.', 'Treat cross-student disclosure, unauthorised editing or downloadable private PDFs as Critical findings.'),
('T19','Withdraw reports and restore a fee hold','Administrator and student. Begin with a released report; keep its old URLs and downloaded copy.',[
'Choose Withdraw reports for Q3. Refresh the student portal and open the saved report/download URLs.',
'Republish the current class after review. Change TEST-001 fees to M 1.00, not cleared, with a note; retry the old URLs.',
'Restore zero with explicit clearance and verify access returns if publication/currentness still hold.'
], 'Withdrawal and new debt block further family report/PDF access immediately on a fresh request. Restored clearance restores access when all gates pass. A PDF already downloaded or an already-rendered screen cannot be remotely erased; test fresh requests separately.', 'Assess whether messages distinguish publication withdrawal from fee holds without leaking academic content.'),
('T20','Correct an earlier quarter after release','Administrator and assigned teacher. Keep baseline PDFs; Q3 released in both classes.',[
'Open TEST Grade 9A Q1 English as administrator. Give a reason and Reopen marks sheet. If Q1 was closed, open the period too.',
'Confirm dependent Q3 reports for 9A and affected TEST Grade 9 stream peers are withdrawn. Teacher changes TEST-001 Q1 English from 42 to 45, then resubmits.',
'Regenerate and review Q3 for both classes, then republish. Restore 42 and repeat the correction process to return to baseline.'
], 'Later cumulative reports and affected stream peers cannot remain available with stale values. With 45, TEST-001 English final becomes 64; its Q3 result stays 63.0 and two passes. Regeneration increments report revision and withdraws publication until reviewed/released again.', 'Check whether the breadth of invalidation is clear and whether staff can track all reports needing regeneration.'),
('T21','Close a quarter and reopen for correction','Administrator, then teacher. Prepare a draft Q3 sheet in a separate test class/stream; keep baseline reports published.',[
'Open Reporting periods, choose Q3 and Open or close period. Enter a reason and Close marks entry.',
'Try saving/submitting a draft teacher sheet. Check an unchanged published current report remains accessible when otherwise released.',
'Open marks entry with a reason. Confirm submitted sheets stay locked until a separate Reopen marks sheet action. Restore and complete any draft variation.'
], 'Closed periods block teacher saves/submissions. Closing does not withdraw existing reports. Reopening a period does not itself reopen submitted sheets; both period and sheet must allow editing for a correction.', 'Evaluate whether staff understand the two locks and can find each control.'),
('T22','Add a late student after reports exist','Administrator and assigned teachers. Baseline evidence saved; TEST-004 still unenrolled.',[
'Enroll TEST-004 into TEST Grade 9A for 2026 using Class rosters.',
'Inspect all 9A subject sheets, affected stream reports and existing family access. Attempt generating Q3 before entering the new student\'s marks.',
'Enter valid rows for the new student in relevant sheets and have teachers resubmit. Decide how to record genuine missing history, then regenerate/review/republish both classes as needed.'
], 'Adding an enrollment reopens all sheets for that class, retains existing marks and withdraws affected reports/stream positions. The late student appears on every class sheet; incomplete current-quarter rows block generation. Adding only a Student record does not change the roster.', 'Measure the work required for late enrollment and whether bulk assistance is needed. Rankings now use the changed population.'),
('T23','Remove a student from family availability','Administrator and the linked family. Use TEST-002 after saving baseline evidence.',[
'Open Students &gt; TEST-002 &gt; Edit report information. Clear Active and save.',
'As test.parent refresh the portal and try a saved TEST-002 report/PDF URL. As teacher inspect the class roster; as administrator inspect historical records.',
'Re-enable Active when finished. Regenerate affected reports and republish after review; restore clearance/link state if changed elsewhere.'
], 'An inactive student is hidden/blocked from family access, while marks, enrollments and history remain. Inactivation does not remove the student from marks sheets or automatically exclude them from ranking/population counts. Metadata edits withdraw affected reports.', 'This is deactivation, not deletion or roster removal. Record a GAP if a leaver should disappear from current assessment populations.'),
('T24','Assess transfer and permanent-deletion needs','Administrator. Read-only boundary test; no direct database edits.',[
'Look for a supported action to remove an existing enrollment, transfer a student between classes in the same year or delete their academic history.',
'Check the disabled identity fields in existing class/subject/student edits. Try the same-year second enrollment only on the test fixture, as in T04.',
'Write down the school\'s intended transfer/leaver process, the records to retain and who should authorise it. Send the requirement to the technical owner rather than modifying data outside the workflow.'
], 'The portal has no self-service enrollment deletion or same-year transfer workflow; identity relationships are deliberately restricted and history uses protected links. A blocked second enrollment is expected. Required transfers need a reviewed technical correction/migration.', 'Classify the missing workflow as a GAP, separate from a malfunction in supported deactivation.'),
('T25','Revoke family access and deactivate an account','Administrator and family. Keep an already-signed-in test family session.',[
'In Verified family access open a link, give a reason and Revoke access. Test both old report URLs and portal cards; restore the verified link afterward.',
'In Accounts & access open that ordinary family account, enter a reason and Deactivate account. Try the existing session and a new login.',
'Attempt reactivation before a password reset. Then verify the test recipient, set a temporary password, reactivate and complete the required first-use password change.'
], 'Link revocation blocks that relationship; other valid links are unaffected. Deactivation invalidates sessions and removes the usable password. Reactivation requires a reset first. Old sessions must not regain access after later reactivation.', 'Evaluate whether the office can distinguish student inactivity, link revocation and account deactivation.'),
('T26','Reassign a teacher without losing a subject','Administrator, outgoing and replacement teachers. Use a copied or reset sheet variation.',[
'Open a marks sheet and Review teacher access. Reassign it to another active teacher account and save with a reason.',
'Try the old teacher\'s direct sheet URL; open it as the replacement teacher. On a submitted sheet, confirm a separate reopening is needed for corrections.',
'Disable teacher access and inspect Reports & fees. Restore the correct assignment/access, then complete or resubmit before regeneration.'
], 'Only the current active assigned teacher can edit an open draft. Reassignment preserves marks and withdraws affected reports. Revoking access alone does not remove the subject or discard submitted marks; an unsubmitted revoked sheet still blocks generation until reassigned/completed.', 'Check whether responsibilities remain visible when a teacher leaves and whether staff can distinguish revoke from remove-subject.'),
('T27','Test stale pages and competing saves','Two sessions for the same authorised role. Use disposable test variations; note both starting revisions.',[
'Open one editable marks sheet in two tabs. Save 70 in tab A, then try saving 90 from the stale tab B.',
'Repeat with two copies of a fee review, grading policy or Edit report information form. Save A first, then stale B.',
'Open a Reports & fees preview in A; regenerate in B; try publishing from the old preview in A. Reload and review before retrying.'
], 'The stale write/publication is rejected and the first saved values survive; the user is told to reload/review. Expired report preview tokens also require reload. Browser tab tests check stale forms; simultaneous transaction locking still needs a technical MySQL/MariaDB test.', 'Record field preservation, error wording and how easily a user can recover without overwriting another person\'s work.'),
('T28','Review audit evidence and private information','Administrator and family. Execute after lifecycle/access scenarios.',[
'Open Audit log and locate recent setup edits, marks saves/submissions, report generations/revisions, fee reviews, publication/withdrawal and downloads.',
'Compare actor, time and target with your test evidence. Confirm family-link and account reviews show the relevant actions.',
'As family inspect a held report response and any downloaded report. Confirm private fee review notes and account credentials are not exposed; subject notes are intentionally report-visible.'
], 'Relevant actions are attributable in the administrator-only audit log. No portal editing of audit entries is offered. Financial review notes remain private. The log is an action history; it does not provide a full prior-marks version browser or recover superseded report PDFs.', 'Assess whether the evidence is sufficient for resolving disputes, not just whether an audit row exists.'),
('T29','Check usability and report readability','Administrator, teacher and family on desktop plus a phone-sized viewport. Use test records only.',[
'Navigate using the keyboard; check labels, focus visibility, errors, save/submit buttons and whether tables can be scrolled on a small screen.',
'Enter a long fictional student name and remarks; include a Sesotho name with punctuation. Generate and download the report, including Q4 on a separate fixture if needed.',
'Open/print the PDF at A4 and compare HTML. Record task time and any unclear wording, crowded columns, broken characters, clipped text or missing repeated table headings.'
], 'Core tasks remain usable; validation is understandable; names, leading-zero codes and all quarter columns survive. Longer reports may use additional pages but must not lose or overlap content. Restore the baseline values after the variation.', 'Capture successful examples as strengths as well as usability problems. Do not assume a short report proves long-report quality.'),
('T30','Check capacity, recovery and repeatability','Technical owner with administrator; use a dedicated test copy.',[
'Time loading, saving and generating for the 2-student baseline. On a separate prepared class, repeat near the supported 200-student limit and record timings/errors.',
'Try adding a 201st enrollment only to that dedicated class. Ask the technical owner to test simultaneous writes and generation failure rollback on MySQL/MariaDB.',
'Have the technical owner demonstrate a backup restore into a separate test database, then repeat a small report release. Keep application data untouched during restore.'
], 'Portal enrollment enforces the 200-student class limit. Realistic sheets and PDFs finish without lost marks or partial visible releases. Concurrent writes, all-or-nothing generation and recoverability require technical evidence, not just UI confidence. No fixed speed target is built into this workbook.', 'Agree response-time targets before testing; record technical checks as BLOCKED if the environment/permissions are unavailable.'),
]

for idx in range(0,len(cases),2):
    batch=cases[idx:idx+2]
    flows=[]
    for n,(cid,title,setup,steps,expected,focus) in enumerate(batch):
        flows += [p(f'{cid}  {escape(title)}','case'),p('<b>Who / starting point:</b> '+setup,'small')]
        flows += [p('<b>Steps</b><br/>'+'<br/>'.join(f'{i+1}. {s}' for i,s in enumerate(steps)))]
        flows += [p('<b>Expected:</b> '+expected),p('<b>Observe:</b> '+focus,'small')]
        flows += [p('Result: PASS / FAIL / BLOCKED / GAP / NOT RUN &nbsp; Date / initials: ______________','small')]
        flows += writing('Evidence / issue reference / actual difference:',1)
        if n == 0:
            flows += [Spacer(1,13)]
    add_page('SCENARIO WALKTHROUGH',f'{batch[0][0]}-{batch[-1][0]} | '+['Setup and access','Students and enrollment','Assignments and family links','Drafts and validation','Remarks and exceptions','Submission and review','Report details and calculations','PDFs and fee checks','Release and isolation','Withdrawals and corrections','Periods and late enrollment','Removal and transfer boundaries','Account and teacher changes','Stale edits and audit','Usability, capacity and recovery'][idx//2],flows)

# 21 - known capabilities and gaps
add_page('EVALUATE / 01','Separate strengths from gaps',[
    p('Use these implementation observations as prompts. They are <b>not passed test results</b>. Confirm the capability in your run, then record whether it fits school practice.'),
    table([['Candidate strength to verify','Evidence scenarios'],['Teachers save drafts, submit and lose edit access until a reasoned reopening.','T07, T11, T20-T21'],['Reports require current marks, publication, verified access and explicit zero-fee clearance.','T12, T16-T19'],['Lookup remarks, configurable subject exclusions and reproducible quarter calculations.','T09, T14-T15'],['Earlier-quarter changes withdraw dependent reports; stale forms reject overwrites.','T20, T22, T27'],['Actions and releases are attributable; history is retained rather than cascaded away.','T23-T24, T28']],[WIDTH*.78,WIDTH*.22]),
    p('Current boundaries to assess','h2'),
    table([['Current boundary','School decision / improvement question'],['No separate approval state or independent approver role.','Should teacher/head/principal signoff be mandatory before release?'],['Inactive students remain enrolled and in marks/ranking populations. No portal transfer/deletion.','How should leavers, transfers and corrected enrollment mistakes be handled?'],['Assignments define the required-subject list; omissions are not inferred.','Do you need a grade curriculum template and automatic completeness check?'],['Missing history and blank attendance/signoff details can still yield reports.','Which fields/quarters must be mandatory before generation/publication?'],['A selected evaluation may disagree with the grade; notes are family-visible.','Should overrides require a reason? Is a separate private staff note needed?'],['Fee clearance is a reviewed balance; no payment ledger or installment workflow.','Is linkage to the school\'s accounts process needed?'],['Regeneration replaces the current PDF; no historical revision viewer.','Are retained report versions, diffs or stronger approval evidence required?']],[WIDTH*.48,WIDTH*.52]),
    p('Record a FAIL when supported behaviour breaks. Record a GAP when the supported behaviour works but is insufficient for school needs. If both occur, log them separately.','small')
])

# 22 - run register
register=[['ID','Scenario','Status','Issue / evidence ref.']]
for cid,title,*_ in cases:
    register.append([cid,title,'Not run',''])
register_table = table(register,[WIDTH*.09,WIDTH*.54,WIDTH*.14,WIDTH*.23])
register_table.setStyle(TableStyle([('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
add_page('RECORD / 01','Execution register',[
    p('Replace Not run as you execute. Use the page 2 status definitions. Fill one row per scenario; repeat this page for another browser, role configuration or build.','small'),
    register_table,
    Spacer(1,10),p('Run ID: ___________________   Tester: ___________________   Build: ___________________','small'),
    p('PASS: ____   FAIL: ____   BLOCKED: ____   GAP: ____   NOT RUN: ____   Total: 30','small')
])

# 23 - finding log
add_page('RECORD / 02','Finding and evidence worksheet',[
    p('Copy this page for each significant defect, weakness, strength or improvement request. Use fictional IDs in shared screenshots and never include passwords.'),
    table([['Finding ID','____________','Scenario / run','____________'],['Type','Defect / Gap / Strength','Severity / priority','____________'],['Tester / date','____________','Owner / target date','____________']],[WIDTH*.17,WIDTH*.33,WIDTH*.23,WIDTH*.27],header=False),Spacer(1,10),
    p('Severity guide','h2'),
    p('<b>Critical:</b> another student\'s data exposed, unauthorised edits or unrecoverable data loss.<br/><b>High:</b> wrong marks/results/recipient, blocked core release or stale reports still accessible.<br/><b>Medium:</b> recoverable workflow error or misleading status with a workable alternative.<br/><b>Low:</b> cosmetic, wording or minor convenience issue. For strengths and feature gaps, mark severity N/A and set an improvement priority instead.','small'),
    *writing('Short title and why it matters:',2),
    *writing('Preconditions: role, class, quarter, student test ID, browser/device and report revision:',2),
    *writing('Exact steps to reproduce (include both sessions if relevant):',3),
    *writing('Expected result versus actual result:',3),
    *writing('Evidence file / screenshot / PDF reference and audit time:',1),
    *writing('Workaround, recommended improvement and retest result:',2),
])

# 24 - review decision and cleanup
add_page('REVIEW / 01','Decide readiness and plan improvements',[
    table([['Area','Score 1-5 / N.T.','Evidence / principal concern'],['Student setup and roster changes','',''],['Teacher marks and error recovery','',''],['Review, calculations and report layout','',''],['Fees, publication and student access','',''],['Privacy and access revocation','',''],['Usability, performance and recoverability','','']],[WIDTH*.44,WIDTH*.22,WIDTH*.34]),
    p('Scoring: 1 = unusable, 2 = major difficulty, 3 = workable with issues, 4 = good, 5 = reliable and easy; N.T. = not tested. Scores summarise observations and do not override a failed privacy or correctness check.','small'),
    *writing('Three strongest points, with scenario/evidence references:',2),
    *writing('Three highest-priority weaknesses or gaps, with an owner and next action:',3),
    p('Readiness decision','h2'),
    p('Ready for limited pilot / Ready with agreed conditions / Not ready / Incomplete testing'),
    p('Before a pilot, require correct answer-key calculations, working release/access checks, no unresolved Critical findings and an explicit decision on every High finding and essential workflow gap. Mark unfinished technical checks as BLOCKED rather than silently passing them.'),
    *writing('Decision, agreed conditions, reviewer and date:',2),
    p('Reset and retest','h2'),
    p('1. Keep the execution register, finding sheets, screenshots and PDFs under the run ID.<br/>2. Restore the test baseline between destructive runs, or use a new TEST prefix. The portal does not supply a complete test-data purge; have the technical owner reset an isolated copy.<br/>3. Revoke test access when no longer needed. Keep test data out of the production school records.<br/>4. Retest each fix, then repeat T14 and T16-T20 to check calculations, release, isolation, withdrawal and corrections.'),
    p('This workbook was prepared for scenario testing only. No test case is certified as passed until your team executes it and records evidence.','small')
])

c=canvas.Canvas(str(OUT),pagesize=A4)
c.setTitle('Holy Family High School - Report module testing walkthrough')
c.setAuthor('Holy Family High School')
c.setSubject('Manual scenario testing workbook, expected results and evaluation records')
for page_no,(title,flows) in enumerate(pages,1):
    c.bookmarkPage(f'page{page_no}')
    c.addOutlineEntry(f'{page_no:02d} {title}',f'page{page_no}',level=0,closed=False)
    c.setStrokeColor(GOLD);c.setLineWidth(1.4);c.line(16*mm,H-16*mm,W-16*mm,H-16*mm)
    c.setFont('GuideBold',7);c.setFillColor(GREEN)
    c.drawString(16*mm,H-12*mm,'HOLY FAMILY HIGH SCHOOL')
    c.setFont('Guide',7);c.setFillColor(MUTED)
    c.drawRightString(W-16*mm,H-12*mm,'REPORT MODULE / SCENARIO TESTING')
    c.setStrokeColor(LINE);c.setLineWidth(.4);c.line(16*mm,15*mm,W-16*mm,15*mm)
    c.setFont('Guide',7);c.drawString(16*mm,10.5*mm,'Version 1.0 | 22 November 2026 | Test results: record during execution')
    c.drawRightString(W-16*mm,10.5*mm,f'{page_no} / {len(pages)}')
    frame=Frame(16*mm,20*mm,WIDTH,H-43*mm,leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0,showBoundary=0)
    remaining=list(flows)
    frame.addFromList(remaining,c)
    if remaining:
        raise RuntimeError(f'Page {page_no} ({title}) overflow: {len(remaining)} flowables remain')
    c.showPage()
c.save()
print(f'Created {OUT} ({len(pages)} pages; {len(cases)} scenarios)')
