"""Import the school's reviewed Google Sites snapshot; reruns preserve staff edits."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.db import transaction
from school.models import SiteSettings, Page, Article, Event

SOURCE = Path(__file__).resolve().parents[2] / 'data' / 'google_sites.json'

class Command(BaseCommand):
    help = 'Import the original school website. Existing imported pages are never overwritten.'

    @transaction.atomic
    def handle(self, *args, **options):
        data = json.loads(SOURCE.read_text())
        from school.page_content import copy_legacy_content
        if Page.objects.filter(slug='curriculum').exists():
            copy_legacy_content()
            self.stdout.write('Source content already imported; staff edits preserved.')
            return
        settings, _ = SiteSettings.objects.get_or_create(pk=1)
        settings.hero_eyebrow = 'Maputsoe, Lesotho · Catholic girls’ school'
        settings.hero_title = 'Holy Family High School'
        settings.hero_text = 'Grow in knowledge, faith and confidence. At Holy Family, you can discover your strengths and prepare to contribute to every sphere of life.'
        settings.about_title = 'An education for the whole person.'
        settings.about_text = 'Holy Family High School is a Catholic school for girls under the management of the Holy Family Sisters. The school caters for both day scholars and boarders.'
        settings.address = 'Ha-Barete, St. Monica’s, Maputsoe, Leribe, Lesotho\nPostal address: P.O. Box 56, Maputsoe 350, Leribe'
        settings.email = 'holyfamilyhighschool56@gmail.com'
        settings.phone = '+266 2243 0282'
        settings.save()
        pages = [
            ('home','about','About & history','A school founded in 1956, with roots in St Monica’s Mission.'),
            ('st-monicas','st-monicas','St Monica’s Mission','Our Catholic identity and connection to the Diocese of Leribe.'),
            ('staff','our-staff','Our staff','Meet the people who teach, guide and support you at Holy Family.'),
            ('curriculum','curriculum','Curriculum','A broad education in languages, sciences, humanities and practical subjects.'),
            ('school-life','school-life','School life','Student writing from our school community. These pieces reflect their authors’ voices and are not official school statements or verified reporting.'),
            ('action-research','action-research','Action research','Computer-based learning, teacher development and the school’s education research partnership.'),
        ]
        for order,(source,slug,title,introduction) in enumerate(pages):
            blocks = data[source]['blocks'][1:]
            if source == 'home': blocks = data[source]['blocks'][4:]
            body=[]
            for block in blocks:
                tag=block['tag']
                if tag in ('h1','h3'):tag='h2'
                if source=='school-life' and (block['text'].isupper() or block['text'] in ['Zailah goes further with Volley Ball','Witchcraft leaves grandmother and granddaughter in shock']):tag='h2'
                body.append(f'<{tag}>{block["html"]}</{tag}>')
            if source=='home':
                body.insert(0,'<p>This history is by Sr. Crescentia Lelimo. Enrolment and staffing figures below are reproduced from the original website and are not dated current totals.</p>')
            defaults=dict(title=title,introduction=introduction,body=''.join(body),published=True,show_in_navigation=True,order=order,show_school_values=False)
            if source=='home':defaults['mission']=data['home']['blocks'][2]['text']
            existing=Page.objects.filter(slug=slug).first()
            if existing and source=='home' and 'demonstration' in existing.body:
                for key,value in defaults.items():setattr(existing,key,value)
                existing.save()
            else:Page.objects.get_or_create(slug=slug,defaults=defaults)
        Page.objects.filter(slug='academics',body__contains='confirmed curriculum').update(published=False,show_in_navigation=False)
        Article.objects.filter(body__contains='example article for the website pitch').update(published=False)
        Event.objects.filter(description__contains='demonstration calendar entry').update(published=False)
        from django.core.management import call_command
        call_command('structure_school_content', verbosity=0)
        copy_legacy_content()
        self.stdout.write(self.style.SUCCESS('School source content imported. Staff editing and admissions settings preserved.'))
