from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from .models import SiteSettings, Page, Article, Event


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class HomepageTests(TestCase):
    def setUp(self):
        self.site = SiteSettings.objects.create(hero_title='Learning for tomorrow', about_title='Our school community')

    def test_removed_welcome_section_is_independent_of_page_builder(self):
        self.assertContains(self.client.get('/'), '/about/')
        self.site.about_image = 'school/about.png'
        self.site.about_image_alt = 'Our learners'
        self.site.save()
        Page.objects.create(title='Injected menu entry', slug='injected', introduction='Private', published=True)
        response = self.client.get('/')
        self.assertNotContains(response, 'src="/media/school/about.png"')
        self.assertNotContains(response, 'alt="Our learners"')
        self.assertNotContains(response, 'Injected menu entry')
        self.assertNotContains(response, '/school/injected/')

    def test_closed_admissions_do_not_advertise_apply_now(self):
        self.site.admissions_open = False
        self.site.save()
        response = self.client.get('/')
        self.assertContains(response, 'Contact us')
        self.assertNotContains(response, 'Apply now')
        self.assertNotContains(response, 'Start your application')
        self.assertNotContains(response, 'Apply to Holy Family')

    def test_homepage_respects_publication_and_uses_featured_images(self):
        Article.objects.create(title='Featured story', slug='featured', excerpt='A school story', body='Body',
                               image='school/story.png', image_alt='School story photo', published=True)
        Article.objects.create(title='Secret draft', slug='secret', excerpt='Unpublished', body='Body')
        Article.objects.create(title='Future article', slug='future', excerpt='Scheduled', body='Body',
                               published=True, published_at=timezone.now()+timedelta(days=2))
        Event.objects.create(title='Next open day', slug='open-day', description='Visit', location='School hall',
                             starts_at=timezone.now()+timedelta(days=5), published=True, image='school/event.png')
        Event.objects.create(title='Past gathering', slug='past', description='Past', location='School hall',
                             starts_at=timezone.now()-timedelta(days=5), published=True)
        response = self.client.get('/')
        for text in ['Featured story', 'school/story.png', 'School story photo', 'Next open day', 'school/event.png']:
            self.assertContains(response, text)
        for text in ['Secret draft', 'Future article', 'Past gathering']:
            self.assertNotContains(response, text)
        self.assertContains(response, 'Learning for tomorrow')
        self.assertNotContains(response, 'Our school community')
        self.assertLess(response.content.index(b'Upcoming dates'), response.content.index(b'Latest news'))
        self.assertNotContains(response, 'hero-invitation')

    def test_closed_admissions_replace_prominent_links_with_phone_action(self):
        self.site.admissions_open = False
        self.site.phone = '+266 2222 3333'
        self.site.save()
        response = self.client.get('/')
        self.assertContains(response, 'href="tel:+266 2222 3333"')
        self.assertContains(response, 'Call us', count=2)
        self.assertNotContains(response, 'Start your application')
        self.assertNotContains(response, '>Admissions <span')

    def test_donation_page_uses_school_contact_settings(self):
        self.site.phone = '+266 2222 3333'
        self.site.email = 'office@example.com'
        self.site.save()
        response = self.client.get('/donation/')
        for text in ['Monetary donations', 'In-kind donations', 'How to donate',
                     'tel:+266 2222 3333', 'office [at] example.com', 'data-email-subject="Donation enquiry"']:
            self.assertContains(response, text)
        self.assertContains(response, '/donation/')
        self.site.phone = self.site.email = ''
        self.site.save()
        response = self.client.get('/donation/')
        self.assertContains(response, 'Contact the school office')
        self.assertNotContains(response, 'href="tel:')
        self.assertNotContains(response, 'href="mailto:')

    @override_settings(TIME_ZONE='Africa/Maseru')
    def test_today_events_stay_visible_after_start_and_use_school_local_date(self):
        from datetime import datetime, timezone as dt_timezone
        from unittest.mock import patch
        # It is 02:30 on 18 October in Lesotho, including events from 22:00 UTC on the 17th.
        now = datetime(2026, 10, 18, 0, 30, tzinfo=dt_timezone.utc)
        past_today = Event.objects.create(title='Early school gathering', location='Hall',
            description='Earlier this morning', starts_at=datetime(2026, 10, 17, 22, 5, tzinfo=dt_timezone.utc), published=True)
        later_today = Event.objects.create(title='Afternoon gathering', location='Hall',
            description='Later today', starts_at=datetime(2026, 10, 18, 12, 0, tzinfo=dt_timezone.utc), published=True)
        tomorrow = Event.objects.create(title='Tomorrow gathering', location='Hall',
            description='Tomorrow', starts_at=datetime(2026, 10, 18, 22, 5, tzinfo=dt_timezone.utc), published=True)
        Event.objects.create(title='Yesterday gathering', location='Hall', description='Past',
            starts_at=datetime(2026, 10, 17, 21, 59, tzinfo=dt_timezone.utc), published=True)
        Event.objects.create(title='Private gathering', location='Hall', description='Draft',
            starts_at=datetime(2026, 10, 18, 1, 0, tzinfo=dt_timezone.utc), published=False)
        with patch('school.views.timezone.now', return_value=now):
            response = self.client.get('/')
        self.assertEqual(list(response.context['events']), [past_today, later_today, tomorrow])
        self.assertContains(response, 'Happening today', count=2)
        self.assertNotContains(response, 'Yesterday gathering')
        self.assertNotContains(response, 'Private gathering')
        with patch('school.views.timezone.now', return_value=datetime(2026, 10, 18, 22, 0, tzinfo=dt_timezone.utc)):
            response = self.client.get('/')
        self.assertNotContains(response, 'Early school gathering')
        self.assertNotContains(response, 'Afternoon gathering')
        self.assertContains(response, 'Tomorrow gathering')
        self.assertContains(response, 'Happening today', count=1)
