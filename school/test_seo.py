from datetime import timedelta
from html.parser import HTMLParser
import uuid
from xml.etree import ElementTree

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Article, Department, Event, Page, SiteSettings, StaffMember, Subject


SITE_URL = 'https://school.example.test'
TEST_STORAGE = {
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


class MetadataParser(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.canonicals = []
        self.title = ''
        self.in_title = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'meta':
            key = attrs.get('name') or attrs.get('property')
            if key:
                self.meta.setdefault(key, []).append(attrs.get('content', ''))
        elif tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs.get('href', ''))
        elif tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


@override_settings(
    DEBUG=False, SITE_URL=SITE_URL, SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGE,
    ALLOWED_HOSTS=['testserver', 'visitor.example.test'],
    STATIC_URL='/static/', MEDIA_URL='/media/',
)
class SearchMetadataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = SiteSettings.objects.create(demo_mode=False)
        now = timezone.now()
        cls.article = Article.objects.create(
            title='Learning in the community', slug='community-learning',
            excerpt='Learners share their knowledge with the community.', body='<p>A school story.</p>',
            image='school/story.jpg', published=True, published_at=now - timedelta(days=1),
        )
        cls.event = Event.objects.create(
            title='School open day', slug='open-day', description='<p>Meet our school team.</p>',
            image='school/open-day.jpg', location='School grounds', starts_at=now + timedelta(days=7),
            published=True,
        )
        cls.subject = Subject.objects.create(
            title='Mathematics', slug='mathematics', introduction='Explore mathematical ideas.',
            body='<p>Study and practise mathematics.</p>', image='school/mathematics.jpg', published=True,
        )
        cls.member = StaffMember.objects.create(
            title='Mpho Example', honorific='Ms.', biography='Supports learners in the classroom.',
            image='school/teacher.jpg', published=True,
        )

    def metadata(self, response):
        return MetadataParser(response.content.decode())

    def one_meta(self, metadata, name):
        values = metadata.meta.get(name, [])
        self.assertEqual(len(values), 1, f'Expected exactly one {name} meta element: {values}')
        return values[0]

    def assert_noindex(self, response, inspect_html=False):
        header = response.get('X-Robots-Tag', '').lower()
        self.assertIn('noindex', header)
        self.assertIn('nofollow', header)
        if inspect_html:
            robots = self.one_meta(self.metadata(response), 'robots').lower()
            self.assertIn('noindex', robots)
            self.assertIn('nofollow', robots)

    def test_public_metadata_uses_trusted_site_origin_and_fallback_image(self):
        response = self.client.get('/?utm_source=example', HTTP_HOST='visitor.example.test')
        self.assertEqual(response.status_code, 200)
        metadata = self.metadata(response)
        self.assertEqual(metadata.canonicals, [SITE_URL + '/'])
        self.assertEqual(metadata.title, self.school.name)
        self.assertEqual(self.one_meta(metadata, 'og:title'), self.school.name)
        self.assertEqual(self.one_meta(metadata, 'twitter:title'), self.school.name)
        description = self.one_meta(metadata, 'description')
        self.assertTrue(description)
        self.assertLessEqual(len(description), 160)
        self.assertEqual(self.one_meta(metadata, 'og:description'), description)
        self.assertEqual(self.one_meta(metadata, 'twitter:description'), description)
        self.assertEqual(self.one_meta(metadata, 'og:url'), SITE_URL + '/')
        self.assertEqual(self.one_meta(metadata, 'twitter:url'), SITE_URL + '/')
        expected_image = SITE_URL + '/static/images/holy-family-favicon-512.png'
        self.assertEqual(self.one_meta(metadata, 'og:image'), expected_image)
        self.assertEqual(self.one_meta(metadata, 'twitter:image'), expected_image)
        for values in metadata.meta.values():
            for value in values:
                self.assertNotIn('visitor.example.test', value)
        for directive in metadata.meta.get('robots', []):
            self.assertNotIn('noindex', directive.lower())
        self.assertNotIn('noindex', response.get('X-Robots-Tag', '').lower())

    def test_page_title_blocks_are_preserved_and_descriptions_use_page_content(self):
        for path, title, description in [
            ('/about/', f'About · {self.school.name}', self.school.about_intro),
            ('/curriculum/', f'Curriculum · {self.school.name}', self.school.curriculum_intro),
            ('/contact/', f'Contact · {self.school.name}', self.school.contact_text),
            ('/our-staff/', f'Our staff · {self.school.name}', self.school.staff_intro),
            ('/events/', f'Calendar · {self.school.name}', self.school.calendar_intro),
            ('/apply/', f'Admissions · {self.school.name}', self.school.admissions_text),
        ]:
            with self.subTest(path=path):
                metadata = self.metadata(self.client.get(path))
                self.assertEqual(metadata.title, title)
                self.assertEqual(metadata.canonicals, [SITE_URL + path])
                actual_description = self.one_meta(metadata, 'description')
                self.assertLessEqual(len(actual_description), 160)
                if len(description) <= 160:
                    self.assertEqual(actual_description, description)
                else:
                    self.assertTrue(actual_description.startswith(description[:60]))

    def test_description_is_plain_whitespace_normalized_and_bounded(self):
        self.school.hero_text = '<p>Faith &amp; learning.\n  <strong>Learning together.</strong></p> ' + 'Purposeful learning. ' * 30
        self.school.save()
        metadata = self.metadata(self.client.get('/'))
        description = self.one_meta(metadata, 'description')
        self.assertTrue(description.startswith('Faith & learning. Learning together.'))
        self.assertLessEqual(len(description), 160)
        self.assertNotIn('<', description)
        self.assertNotIn('>', description)
        self.assertNotIn('&amp;', description)
        self.assertNotIn('\n', description)
        self.assertNotIn('  ', description)
        self.assertEqual(self.one_meta(metadata, 'og:description'), description)
        self.assertEqual(self.one_meta(metadata, 'twitter:description'), description)

    def test_published_detail_images_use_absolute_trusted_urls(self):
        for route, kwargs, image, description in [
            ('article', {'slug': self.article.slug}, self.article.image, self.article.excerpt),
            ('event', {'slug': self.event.slug}, self.event.image, 'Meet our school team.'),
            ('subject', {'slug': self.subject.slug}, self.subject.image, self.subject.introduction),
            ('school-staff-profile', {'pk': self.member.pk}, self.member.image, self.member.biography),
        ]:
            with self.subTest(route=route):
                path = reverse(route, kwargs=kwargs)
                metadata = self.metadata(self.client.get(path, HTTP_HOST='visitor.example.test'))
                self.assertEqual(metadata.canonicals, [SITE_URL + path])
                self.assertEqual(self.one_meta(metadata, 'og:image'), SITE_URL + image.url)
                self.assertEqual(self.one_meta(metadata, 'twitter:image'), SITE_URL + image.url)
                self.assertEqual(self.one_meta(metadata, 'og:url'), SITE_URL + path)
                self.assertEqual(self.one_meta(metadata, 'description'), description)

    def test_dynamic_title_and_description_are_escaped_in_metadata(self):
        self.article.title = 'A "quoted" story & <script>bad()</script>'
        self.article.excerpt = 'A "quoted" introduction & <strong>learning</strong>.'
        self.article.save()
        response = self.client.get(reverse('article', kwargs={'slug': self.article.slug}))
        metadata = self.metadata(response)
        self.assertEqual(metadata.title, f'{self.article.title} · {self.school.name}')
        self.assertNotContains(response, '<script>bad()</script>')
        description = self.one_meta(metadata, 'description')
        self.assertEqual(description, 'A "quoted" introduction & learning.')
        self.assertEqual(self.one_meta(metadata, 'og:description'), description)
        self.assertEqual(self.one_meta(metadata, 'twitter:description'), description)
        self.assertEqual(len(metadata.meta['og:title']), 1)
        self.assertEqual(len(metadata.meta['twitter:title']), 1)

    def test_news_pagination_canonical_preserves_real_page_two_and_discards_tracking(self):
        for number in range(10):
            Article.objects.create(
                title=f'Published story {number}', slug=f'published-{number}', excerpt='School story.',
                body='<p>Story.</p>', published=True, published_at=timezone.now() - timedelta(days=1),
            )
        response = self.client.get('/news/?page=2&utm_source=example')
        self.assertEqual(response.context['items'].number, 2)
        self.assertEqual(self.metadata(response).canonicals, [SITE_URL + '/news/?page=2'])
        for query in ['?page=1&utm_source=example', '?page=invalid', '?utm_source=example']:
            with self.subTest(query=query):
                self.assertEqual(self.metadata(self.client.get('/news/' + query)).canonicals, [SITE_URL + '/news/'])

    def test_legacy_school_aliases_and_calendar_queries_use_primary_canonical(self):
        for path, canonical in [
            ('/school/about/', '/about/'), ('/school/about-us/', '/about/'),
            ('/school/curriculum/', '/curriculum/'), ('/school/our-staff/', '/our-staff/'),
            ('/school/staff/', '/our-staff/'), ('/events/?month=2027-01', '/events/'),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.metadata(response).canonicals, [SITE_URL + canonical])

    def test_private_pages_redirects_receipts_and_errors_are_not_indexable(self):
        for path in ['/staff/', '/staff/login/', '/admin/', '/admin/login/', '/apply/received/', '/missing-page/']:
            with self.subTest(path=path):
                self.assert_noindex(self.client.get(path))
        host_error = self.client.get('/', HTTP_HOST='untrusted.example.test')
        self.assertEqual(host_error.status_code, 400)
        self.assert_noindex(host_error)
        method_error = self.client.put('/apply/')
        self.assertEqual(method_error.status_code, 405)
        self.assert_noindex(method_error)

        session = self.client.session
        session['application_receipt'] = str(uuid.uuid4())
        session.save()
        response = self.client.get('/apply/received/')
        self.assertEqual(response.status_code, 200)
        self.assert_noindex(response, inspect_html=True)


@override_settings(
    DEBUG=False, SITE_URL=SITE_URL, SECURE_SSL_REDIRECT=False, STORAGES=TEST_STORAGE,
    ALLOWED_HOSTS=['testserver', 'visitor.example.test'],
)
class SearchDiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = SiteSettings.objects.create(demo_mode=False)
        now = timezone.now()
        cls.article = Article.objects.create(
            title='Published news', slug='published-news', excerpt='School news.', body='<p>News.</p>',
            published=True, published_at=now - timedelta(days=1),
        )
        cls.draft_article = Article.objects.create(title='Draft news', slug='draft-news', excerpt='Draft.', body='Draft.')
        cls.scheduled_article = Article.objects.create(
            title='Scheduled news', slug='scheduled-news', excerpt='Future.', body='Future.',
            published=True, published_at=now + timedelta(days=1),
        )
        cls.past_event = Event.objects.create(
            title='Past event', slug='past-event', description='Past.', location='School',
            starts_at=now - timedelta(days=7), published=True,
        )
        cls.future_event = Event.objects.create(
            title='Future event', slug='future-event', description='Future.', location='School',
            starts_at=now + timedelta(days=7), published=True,
        )
        cls.draft_event = Event.objects.create(
            title='Draft event', slug='draft-event', description='Draft.', location='School', starts_at=now,
        )
        cls.subject = Subject.objects.create(title='Published subject', slug='published-subject', published=True)
        cls.draft_subject = Subject.objects.create(title='Draft subject', slug='draft-subject')
        cls.department = Department.objects.create(title='Published department')
        cls.second_department = Department.objects.create(title='Another published department')
        cls.empty_department = Department.objects.create(title='Empty published department')
        cls.hidden_department = Department.objects.create(title='Hidden department', published=False)
        cls.member = StaffMember.objects.create(title='Published member', published=True)
        cls.member.departments.add(cls.department, cls.second_department, cls.hidden_department)
        cls.unassigned = StaffMember.objects.create(title='Unassigned member', published=True)
        cls.hidden_member = StaffMember.objects.create(title='Hidden department member', published=True)
        cls.hidden_member.departments.add(cls.hidden_department)
        cls.draft_member = StaffMember.objects.create(title='Draft member')
        cls.draft_member.departments.add(cls.department)
        cls.legacy_page = Page.objects.create(
            title='Legacy arbitrary page', slug='legacy-arbitrary', introduction='Archived content.', published=True,
        )

    def sitemap_urls(self, response):
        self.assertEqual(response.status_code, 200)
        root = ElementTree.fromstring(response.content)
        self.assertEqual(root.tag, '{http://www.sitemaps.org/schemas/sitemap/0.9}urlset')
        return [element.text for element in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]

    def test_sitemap_includes_public_static_pages_and_only_visible_published_content(self):
        response = self.client.get('/sitemap.xml', HTTP_HOST='visitor.example.test')
        urls = self.sitemap_urls(response)
        public_paths = {
            '/', '/about/', '/contact/', '/curriculum/', '/our-staff/', '/events/',
            '/apply/', '/news/', '/privacy/',
            reverse('article', kwargs={'slug': self.article.slug}),
            reverse('event', kwargs={'slug': self.past_event.slug}),
            reverse('event', kwargs={'slug': self.future_event.slug}),
            reverse('subject', kwargs={'slug': self.subject.slug}),
            reverse('school-department', kwargs={'pk': self.department.pk}),
            reverse('school-department', kwargs={'pk': self.second_department.pk}),
            reverse('school-department', kwargs={'pk': self.empty_department.pk}),
            reverse('school-staff-profile', kwargs={'pk': self.member.pk}),
            reverse('school-staff-profile', kwargs={'pk': self.unassigned.pk}),
        }
        self.assertEqual(set(urls), {SITE_URL + path for path in public_paths})
        self.assertEqual(len(urls), len(set(urls)))
        for excluded_path in [
            reverse('article', kwargs={'slug': self.draft_article.slug}),
            reverse('article', kwargs={'slug': self.scheduled_article.slug}),
            reverse('event', kwargs={'slug': self.draft_event.slug}),
            reverse('subject', kwargs={'slug': self.draft_subject.slug}),
            reverse('school-department', kwargs={'pk': self.hidden_department.pk}),
            reverse('school-staff-profile', kwargs={'pk': self.hidden_member.pk}),
            reverse('school-staff-profile', kwargs={'pk': self.draft_member.pk}),
            '/school/legacy-arbitrary/', '/staff/', '/admin/', '/apply/received/',
        ]:
            self.assertNotIn(SITE_URL + excluded_path, urls)
        self.assertNotContains(response, 'visitor.example.test')

    def test_live_robots_allows_public_site_and_blocks_private_routes(self):
        response = self.client.get('/robots.txt', HTTP_HOST='visitor.example.test')
        self.assertEqual(response.status_code, 200)
        lines = response.content.decode().splitlines()
        self.assertIn('User-agent: *', lines)
        for path in ['/staff/', '/admin/', '/apply/received/']:
            self.assertIn(f'Disallow: {path}', lines)
        self.assertNotIn('Disallow: /', lines)
        self.assertIn(f'Sitemap: {SITE_URL}/sitemap.xml', lines)
        self.assertNotContains(response, 'visitor.example.test')

    def assert_preview_blocked(self):
        response = self.client.get('/')
        metadata = MetadataParser(response.content.decode())
        robots = metadata.meta.get('robots', [])
        self.assertEqual(len(robots), 1)
        self.assertIn('noindex', robots[0].lower())
        self.assertIn('nofollow', robots[0].lower())
        self.assertIn('noindex', response.get('X-Robots-Tag', '').lower())
        self.assertIn('nofollow', response.get('X-Robots-Tag', '').lower())
        robot_response = self.client.get('/robots.txt')
        self.assertEqual(robot_response.status_code, 200)
        self.assertIn('Disallow: /', robot_response.content.decode().splitlines())
        self.assertNotIn('Sitemap:', robot_response.content.decode())
        self.assertEqual(self.sitemap_urls(self.client.get('/sitemap.xml')), [])
        return metadata

    @override_settings(DEBUG=True)
    def test_debug_preview_blocks_indexing_and_sitemap_discovery(self):
        self.assert_preview_blocked()

    def test_demo_preview_blocks_indexing_and_sitemap_discovery(self):
        self.school.demo_mode = True
        self.school.save()
        self.assert_preview_blocked()

    @override_settings(SITE_URL='')
    def test_missing_production_origin_omits_canonical_and_blocks_discovery(self):
        metadata = self.assert_preview_blocked()
        self.assertEqual(metadata.canonicals, [])
        self.assertNotIn('testserver', self.client.get('/').content.decode())
