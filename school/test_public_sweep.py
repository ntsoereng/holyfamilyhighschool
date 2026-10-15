from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, unquote
from xml.etree import ElementTree

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Article, Department, Event, SchoolLifePost, SiteSettings, StaffMember, StudentAuthor, Subject
from .seo import PRIMARY_PAGES


class ParsedPage(HTMLParser):
    def __init__(self, response):
        super().__init__(); self.links=[]; self.ids=set(); self.meta={}; self.canonicals=[]; self.h1=0; self.title=''; self.in_title=False
        self.feed(response.content.decode())

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        if tag=='a' and attrs.get('href'):self.links.append(attrs['href'])
        if tag=='meta':self.meta.setdefault(attrs.get('name') or attrs.get('property'),[]).append(attrs.get('content',''))
        if tag=='link' and attrs.get('rel')=='canonical':self.canonicals.append(attrs['href'])
        if tag=='h1':self.h1+=1
        if tag=='title':self.in_title=True

    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False

    def handle_data(self,text):
        if self.in_title:self.title+=text


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=False, SITE_URL='https://school.example.test',
                   ALLOWED_HOSTS=['testserver'], STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class PublicSiteSweepTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school=SiteSettings.objects.create(demo_mode=False)
        cls.department=Department.objects.create(title='Science',published=True)
        cls.member=StaffMember.objects.create(title='Teacher Example',published=True)
        cls.member.departments.add(cls.department)
        cls.subject=Subject.objects.create(title='Mathematics',published=True)
        cls.event=Event.objects.create(title='Open day',location='School hall',starts_at=timezone.now()+timedelta(days=40),published=True)
        cls.author=StudentAuthor.objects.create(title='Student Example',grade='Grade 8')
        for number in range(11):
            Article.objects.create(title=f'School news {number}',excerpt=f'News item {number}',body='<p>News body.</p>',published=True)
            SchoolLifePost.objects.create(title=f'Student poem {number}',category='poem',excerpt=f'Poem {number}',body='<p>Poem body.</p>',author=cls.author,published=True)

    def detail_paths(self):
        return [reverse('article',args=[Article.objects.live().first().slug]),reverse('event',args=[self.event.slug]),
                reverse('subject',args=[self.subject.slug]),reverse('school-department',args=[self.department.pk]),
                reverse('school-staff-profile',args=[self.member.slug]),reverse('school-life-post',args=[SchoolLifePost.objects.live().first().slug])]

    def test_public_links_and_fragments_resolve_without_broken_destinations(self):
        paths=[reverse(route) for route in PRIMARY_PAGES]+self.detail_paths()+['/news/?page=2','/school-life/?category=poem&page=2']
        cache={}
        def fetch(path):
            if path not in cache:
                response=self.client.get(path,follow=True)
                self.assertEqual(response.status_code,200,path)
                cache[path]=ParsedPage(response)
            return cache[path]
        for path in paths:
            page=fetch(path)
            self.assertEqual(page.h1,1,path)
            for href in page.links:
                parsed=urlsplit(urljoin('https://school.example.test'+path,href))
                if parsed.scheme not in {'http','https'} or parsed.hostname!='school.example.test':continue
                target=parsed.path+('?' + parsed.query if parsed.query else '')
                linked=fetch(target)
                if parsed.fragment:self.assertIn(unquote(parsed.fragment),linked.ids,(path,href))

    def test_all_public_pages_have_consistent_titles_descriptions_and_canonicals(self):
        for path in [reverse(route) for route in PRIMARY_PAGES]+self.detail_paths():
            with self.subTest(path=path):
                response=self.client.get(path); page=ParsedPage(response)
                self.assertTrue(page.title.strip())
                self.assertEqual(page.meta['og:title'],[page.title])
                self.assertEqual(page.meta['twitter:title'],[page.title])
                descriptions=page.meta['description']
                self.assertEqual(len(descriptions),1)
                self.assertTrue(descriptions[0].strip())
                self.assertLessEqual(len(descriptions[0]),160)
                self.assertEqual(page.meta['og:description'],descriptions)
                self.assertEqual(page.meta['twitter:description'],descriptions)
                self.assertEqual(page.canonicals,['https://school.example.test'+path])
                self.assertNotIn('noindex',page.meta['robots'][0])
                self.assertEqual(self.client.head(path).status_code,200)

    def test_blank_or_html_only_content_still_has_page_specific_descriptions(self):
        for field in ['hero_text','about_intro','about_text','contact_text','curriculum_intro','staff_intro','calendar_intro','admissions_text','privacy_text']:
            setattr(self.school,field,'<p> </p>')
        self.school.save()
        descriptions=[]
        for route in PRIMARY_PAGES:
            page=ParsedPage(self.client.get(reverse(route)))
            self.assertTrue(page.meta['description'][0].strip(),route)
            descriptions+=page.meta['description']
        self.assertEqual(len(descriptions),len(set(descriptions)))
        for path in self.detail_paths():
            page=ParsedPage(self.client.get(path))
            self.assertTrue(page.meta['description'][0].strip(),path)

    def test_detail_return_links_preserve_lists_filters_and_calendar_months(self):
        article=Article.objects.first()
        detail=self.client.get(reverse('article',args=[article.slug])+'?page=2')
        self.assertContains(detail,'href="/news/?page=2"')
        page=ParsedPage(self.client.get('/news/?page=2'))
        detail_links=[href for href in page.links if href.startswith('/news/') and '?page=2' in href]
        self.assertTrue(detail_links)
        post=SchoolLifePost.objects.first()
        detail=self.client.get(reverse('school-life-post',args=[post.slug])+'?category=poem&page=2')
        self.assertContains(detail,'href="/school-life/?category=poem&amp;page=2"')
        self.assertEqual(ParsedPage(detail).canonicals,['https://school.example.test'+reverse('school-life-post',args=[post.slug])])
        response=self.client.get(reverse('subject',args=[self.subject.slug]))
        self.assertContains(response,'href="/curriculum/#subjects"')
        response=self.client.get(reverse('event',args=[self.event.slug]))
        local=timezone.localtime(self.event.starts_at)
        self.assertContains(response,f'href="/events/?year={local.year}&amp;month={local.month}#calendar-month-heading"')
        for path in self.detail_paths()[3:5]:
            self.assertContains(self.client.get(path),'Back to staff')

    def test_return_links_never_trust_foreign_destinations(self):
        article=Article.objects.first()
        response=self.client.get(reverse('article',args=[article.slug])+'?page=//evil.example&next=https://evil.example')
        self.assertContains(response,'href="/news/"')
        self.assertNotContains(response,'evil.example')

    def test_pagination_and_categories_have_distinct_metadata(self):
        first=ParsedPage(self.client.get('/news/')); second=ParsedPage(self.client.get('/news/?page=2&utm_source=test'))
        self.assertNotEqual(first.title,second.title)
        self.assertNotEqual(first.meta['description'],second.meta['description'])
        self.assertIn('Page 2',second.title)
        self.assertEqual(second.canonicals,['https://school.example.test/news/?page=2'])
        poems=ParsedPage(self.client.get('/school-life/?category=poem&page=2'))
        self.assertIn('Poems',poems.title)
        self.assertIn('Page 2',poems.title)
        self.assertEqual(poems.meta['og:title'],[poems.title])

    def test_sitemap_and_robots_are_valid_and_exclude_private_or_unpublished_pages(self):
        hidden=Article.objects.create(title='Private draft',excerpt='Hidden',body='Hidden')
        future=SchoolLifePost.objects.create(title='Future poem',category='poem',excerpt='Later',body='Later',author=self.author,published=True,published_at=timezone.now()+timedelta(days=1))
        response=self.client.get('/sitemap.xml')
        urls=[node.text for node in ElementTree.fromstring(response.content).iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        for path in [reverse(route) for route in PRIMARY_PAGES]+self.detail_paths():self.assertIn('https://school.example.test'+path,urls)
        self.assertEqual(len(urls),len(set(urls)))
        for fragment in ['/staff/','/admin/','/apply/received/',hidden.slug,future.slug]:self.assertFalse(any(fragment in url for url in urls))
        robots=self.client.get('/robots.txt')
        self.assertEqual(robots['Content-Type'],'text/plain; charset=utf-8')
        self.assertContains(robots,'Sitemap: https://school.example.test/sitemap.xml')
        self.assertContains(robots,'Disallow: /staff/')
        self.assertContains(robots,'Disallow: /apply/received/')
        self.assertNotContains(robots,'Disallow: /\n')

    def test_preview_stays_noindex_and_receipt_head_does_not_consume_it(self):
        self.school.demo_mode=True;self.school.save()
        self.assertContains(self.client.get('/robots.txt'),'Disallow: /')
        self.assertIn('noindex',ParsedPage(self.client.get('/')).meta['robots'][0])
        session=self.client.session;session['application_receipt']='HFHS-2027-TEST';session.save()
        self.assertEqual(self.client.head('/apply/received/').status_code,200)
        self.assertContains(self.client.get('/apply/received/'),'HFHS-2027-TEST')
        self.assertEqual(self.client.get('/apply/received/').status_code,302)
