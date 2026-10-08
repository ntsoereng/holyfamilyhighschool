"""One-time conversion of the imported lists into editable school records."""
import html
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.html import strip_tags
from django.utils.text import slugify, Truncator
from school.models import Page, Department, StaffMember, Subject, SchoolStatistic, SiteSettings
from school.editorial_copy import learner_curriculum_copy, learner_subject_copy


def plain(value):
    return html.unescape(strip_tags(value)).strip()


def sections(body):
    parts = re.split(r'(<h2\b[^>]*>.*?</h2>)', body, flags=re.S | re.I)
    yield '', parts[0]
    for i in range(1, len(parts), 2):
        yield plain(parts[i]), parts[i+1] if i+1 < len(parts) else ''


def display_name(value):
    return ' '.join(value.replace('`', '’').split()).title()


class Command(BaseCommand):
    help = 'Convert school staff, subjects and figures into editable records and remove guide-site links.'

    @transaction.atomic
    def handle(self, *args, **options):
        for page in Page.objects.all():
            body = re.sub(r'<p>\s*<a\b[^>]*href="https://sites\.google\.com/view/holyfamaily-maputsoe/[^" ]*"[^>]*>.*?</a>\s*</p>', '', page.body, flags=re.I | re.S)
            if page.slug == 'our-staff' and page.layout != 'staff' and 'SCHOOL MANAGEMENT' in body:
                for order, (heading, content) in enumerate(sections(body)):
                    if not heading:
                        continue
                    label = heading.replace('DEPARTMENT OF ', '').title()
                    department, _ = Department.objects.get_or_create(title=label, defaults={'order': order, 'published': True})
                    for index, value in enumerate(re.findall(r'<p\b[^>]*>(.*?)</p>', content, flags=re.S)):
                        text = plain(value)
                        if not text:
                            continue
                        if ':' in text:
                            role, names = text.split(':', 1)
                            role = 'Head of department' if role.lower().startswith('heads') else role.strip().capitalize()
                            names = names.split(',')
                        else:
                            role, names = 'Teacher', [text]
                        for name in names:
                            name = display_name(name)
                            if not name:
                                continue
                            # The source lists the principal and deputy by full and abbreviated names.
                            aliases = {'Mrs Tefo': 'Mrs ’Matumane B. Tefo', 'Mrs Kopeka': 'Mrs ’Mafonti Kopeka'}
                            name = aliases.get(name, name)
                            member, _ = StaffMember.objects.get_or_create(title=name, defaults={
                                'position': role, 'order': index, 'published': True})
                            member.departments.add(department)
                page.layout = 'staff'
                page.introduction = 'Meet the people who teach, guide and support you at Holy Family.'
                body = ''
            elif page.slug == 'curriculum' and page.layout != 'curriculum' and '<h2>English</h2>' in body:
                intro = []
                subject_started = False
                for order, (heading, content) in enumerate(sections(body)):
                    if heading == 'English':
                        subject_started = True
                    if subject_started:
                        slug = slugify(heading)
                        subject_body, subject_intro = learner_subject_copy(
                            slug, content.strip(), Truncator(plain(content)).words(26))
                        Subject.objects.get_or_create(slug=slug, defaults={
                            'title': heading, 'body': subject_body,
                            'introduction': subject_intro, 'order': order, 'published': True})
                    else:
                        intro.append((f'<h2>{html.escape(heading)}</h2>' if heading else '') + content)
                page.layout = 'curriculum'
                body = ''.join(intro)
                body, page.introduction = learner_curriculum_copy(body, page.introduction)
            if page.slug in ['about', 'about-us']:
                match = re.search(r'<h2[^>]*>Current numbers</h2>\s*<p>(.*?)</p>', body, re.S | re.I)
                if match:
                    numbers = plain(match.group(1))
                    for order, (label, pattern, icon) in enumerate([
                        ('Students', r'Roll\s*=\s*(\d+)', 'people'),
                        ('Academic staff', r'Academic Staff\s*=\s*(\d+)', 'book'),
                        ('Support staff', r'Non-academic staff\s*=\s*(\d+)', 'shield'),
                    ]):
                        value = re.search(pattern, numbers, re.I)
                        if value:
                            SchoolStatistic.objects.get_or_create(title=label, defaults={
                                'value': f'{int(value.group(1)):,}', 'icon': icon, 'order': order, 'published': True})
                    body = body[:match.start()] + body[match.end():]
                    page.show_statistics = True
                    SiteSettings.objects.filter(statistics_text='').update(statistics_text='Contact the school office for the latest enrolment and staffing information.')
                body = re.sub(r'<p>This history is by Sr\. Crescentia Lelimo\. Enrolment and staffing figures below.*?</p>', '', body, flags=re.S)
            if page.slug == 'school-life':
                page.introduction = 'Student writing from our school community. These pieces reflect their authors’ voices and are not official school statements or verified reporting.'
            page.body = body
            page.save()
        self.stdout.write(self.style.SUCCESS('Staff, subjects and statistics are ready to manage. Guide-site links removed.'))
