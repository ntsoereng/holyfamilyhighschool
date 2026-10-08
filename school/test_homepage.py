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

    def test_about_link_and_image_are_independent_of_page_builder(self):
        self.assertContains(self.client.get('/'), '/about/')
        self.site.about_image = 'school/about.png'
        self.site.about_image_alt = 'Our learners'
        self.site.save()
        Page.objects.create(title='Injected menu entry', slug='injected', introduction='Private', published=True)
        response = self.client.get('/')
        self.assertContains(response, 'src="/media/school/about.png"')
        self.assertContains(response, 'alt="Our learners"')
        self.assertNotContains(response, 'Injected menu entry')
        self.assertNotContains(response, '/school/injected/')

    def test_closed_admissions_do_not_advertise_apply_now(self):
        self.site.admissions_open = False
        self.site.save()
        response = self.client.get('/')
        self.assertContains(response, 'Admissions information')
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
        self.assertContains(response, 'Our school community')
