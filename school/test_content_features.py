from io import BytesIO
from PIL import Image
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import models
from django.test import TestCase, override_settings
from .models import SiteSettings, Page, Event, SchoolValue
from .security import validate_google_maps_embed
from .staff_forms import SettingsForm


@override_settings(SECURE_SSL_REDIRECT=False, STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ContentFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_staff_groups', verbosity=0)
        cls.editor = User.objects.create_user('editor', is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Content editors'))
        cls.site = SiteSettings.objects.create()

    def image(self, name='school.png'):
        buffer = BytesIO()
        Image.new('RGB', (120, 80), '#103f35').save(buffer, format='PNG')
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')

    def settings_data(self, **changes):
        return {**{name: getattr(self.site, name) for name in SettingsForm._meta.fields
                   if not isinstance(self.site._meta.get_field(name), models.ImageField)}, **changes}

    def test_map_embed_validation(self):
        for url in ['', 'https://www.google.com/maps/embed?pb=example',
                    'https://google.com/maps/embed/v1/place?key=example&q=school',
                    'https://maps.google.com/maps?q=school&output=embed']:
            with self.subTest(url=url): validate_google_maps_embed(url)
        for url in ['javascript:alert(1)', 'http://www.google.com/maps/embed?pb=example',
                    'https://evil.example/maps/embed', 'https://www.google.com.evil.example/maps/embed',
                    'https://www.google.com@evil.example/maps/embed', 'https://user@www.google.com/maps/embed',
                    'https://www.google.com:8443/maps/embed', 'https://www.google.com/url?q=https://evil.example',
                    'https://maps.app.goo.gl/example', 'https://www.google.com/maps/place/school',
                    '<iframe src="https://www.google.com/maps/embed"></iframe>']:
            with self.subTest(url=url), self.assertRaises(ValidationError): validate_google_maps_embed(url)

    def test_map_saved_in_workspace_and_rendered_only_on_contact(self):
        self.client.force_login(self.editor)
        url = 'https://www.google.com/maps/embed?pb=example&hl=en'
        self.assertRedirects(self.client.post('/staff/settings/', self.settings_data(google_maps_embed_url=url)), '/staff/settings/')
        response = self.client.get('/contact/')
        self.assertContains(response, 'src="https://www.google.com/maps/embed?pb=example&amp;hl=en"')
        self.assertContains(response, 'title="Map showing the location of Holy Family High School"')
        self.assertContains(response, 'loading="lazy"')
        self.assertIn("frame-src 'self' https://www.google.com", response['Content-Security-Policy'])
        self.assertNotIn('https://www.google.com', self.client.get('/')['Content-Security-Policy'])
        bad = self.client.post('/staff/settings/', self.settings_data(google_maps_embed_url='https://evil.example/maps/embed'))
        self.assertEqual(bad.status_code, 200)
        self.site.refresh_from_db()
        self.assertEqual(self.site.google_maps_embed_url, url)

    def test_copied_google_iframe_saves_only_decoded_url_and_uses_school_markup(self):
        self.client.force_login(self.editor)
        url = 'https://www.google.com/maps/embed?pb=example&hl=en'
        embed = (
            '\n  <iframe src="https://www.google.com/maps/embed?pb=example&amp;hl=en" '
            'width="600" height="450" style="border:0;" allowfullscreen="" '
            'loading="lazy" referrerpolicy="no-referrer-when-downgrade" '
            'title="Copied Google embed"></iframe>  \n'
        )
        response = self.client.post('/staff/settings/', self.settings_data(google_maps_embed_url=embed))
        self.assertRedirects(response, '/staff/settings/')
        self.site.refresh_from_db()
        self.assertEqual(self.site.google_maps_embed_url, url)
        self.assertNotIn('<iframe', self.site.google_maps_embed_url)
        self.assertNotIn('&amp;', self.site.google_maps_embed_url)

        response = self.client.get('/contact/')
        self.assertContains(response, '<iframe', count=1)
        self.assertContains(response, 'src="https://www.google.com/maps/embed?pb=example&amp;hl=en"')
        self.assertContains(response, 'title="Map showing the location of Holy Family High School"')
        self.assertContains(response, 'loading="lazy"')
        for discarded in [
            'Copied Google embed', 'width="600"', 'height="450"',
            'style="border:0;"', 'no-referrer-when-downgrade',
        ]:
            self.assertNotContains(response, discarded)
        self.assertIn("frame-src 'self' https://www.google.com", response['Content-Security-Policy'])
        for path in ['/', '/about/', '/curriculum/', '/our-staff/', '/events/', '/apply/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertNotContains(response, '<iframe')
                self.assertNotIn('https://www.google.com', response['Content-Security-Policy'])
        with self.assertRaises(ValidationError):
            validate_google_maps_embed(embed)

    def test_google_iframe_sources_follow_existing_url_allowlist(self):
        for url in [
            'https://www.google.com/maps/embed?pb=example',
            'https://google.com/maps/embed/v1/place?key=example&q=school',
            'https://maps.google.com/maps?q=school&output=embed',
        ]:
            with self.subTest(url=url):
                embed = f'<iframe src="{url.replace("&", "&amp;")}" allowfullscreen></iframe>'
                form = SettingsForm(self.settings_data(google_maps_embed_url=embed), instance=self.site)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['google_maps_embed_url'], url)

    def test_unsafe_or_ambiguous_map_paste_is_rejected_and_preserves_existing_map(self):
        self.client.force_login(self.editor)
        existing_url = 'https://www.google.com/maps/embed?pb=existing'
        self.site.google_maps_embed_url = existing_url
        self.site.save()
        allowed_url = 'https://www.google.com/maps/embed?pb=example'
        iframe = f'<iframe src="{allowed_url}"></iframe>'
        invalid_pastes = {
            'external origin': '<iframe src="https://evil.example/maps/embed"></iframe>',
            'deceptive origin': '<iframe src="https://www.google.com.evil.example/maps/embed"></iframe>',
            'insecure origin': '<iframe src="http://www.google.com/maps/embed?pb=example"></iframe>',
            'script URL': '<iframe src="javascript:alert(1)"></iframe>',
            'short link': '<iframe src="https://maps.app.goo.gl/example"></iframe>',
            'ordinary map page': '<iframe src="https://www.google.com/maps/place/school"></iframe>',
            'script before iframe': '<script>alert(1)</script>' + iframe,
            'script inside iframe': f'<iframe src="{allowed_url}"><script>alert(1)</script></iframe>',
            'multiple iframes': iframe + iframe,
            'nested iframes': f'<iframe src="{allowed_url}">{iframe}</iframe>',
            'duplicate source': f'<iframe src="{allowed_url}" src="{allowed_url}"></iframe>',
            'duplicate case-insensitive source': f'<iframe src="{allowed_url}" SRC="https://evil.example/"></iframe>',
            'missing source': '<iframe width="600"></iframe>',
            'empty source': '<iframe src=""></iframe>',
            'unclosed iframe': f'<iframe src="{allowed_url}">',
            'self-closing iframe': f'<iframe src="{allowed_url}" />',
            'extra closing tag': iframe + '</iframe>',
            'other element': '<p>Map</p>' + iframe,
            'comment': '<!-- copied map -->' + iframe,
            'outside text': 'Copied map: ' + iframe,
            'inside text': f'<iframe src="{allowed_url}">Map</iframe>',
        }
        for reason, paste in invalid_pastes.items():
            with self.subTest(reason=reason):
                response = self.client.post('/staff/settings/', self.settings_data(google_maps_embed_url=paste))
                self.assertEqual(response.status_code, 200)
                self.assertIn('google_maps_embed_url', response.context['form'].errors)
                self.site.refresh_from_db()
                self.assertEqual(self.site.google_maps_embed_url, existing_url)

    def test_normalized_google_iframe_can_be_cleared_without_retaining_pasted_markup(self):
        self.client.force_login(self.editor)
        iframe = '<iframe src="https://www.google.com/maps/embed?pb=example" width="600"></iframe>'
        self.assertRedirects(
            self.client.post('/staff/settings/', self.settings_data(google_maps_embed_url=iframe)),
            '/staff/settings/',
        )
        self.site.refresh_from_db()
        self.assertRedirects(
            self.client.post('/staff/settings/', self.settings_data(google_maps_embed_url='')),
            '/staff/settings/',
        )
        self.site.refresh_from_db()
        self.assertEqual(self.site.google_maps_embed_url, '')
        response = self.client.get('/contact/')
        self.assertNotContains(response, '<iframe')

    def test_blank_or_unsafe_map_does_not_render(self):
        self.assertNotContains(self.client.get('/contact/'), '<iframe')
        SiteSettings.objects.filter(pk=1).update(google_maps_embed_url='https://evil.example/maps/embed')
        self.assertNotContains(self.client.get('/contact/'), '<iframe')

    def test_mission_vision_values_and_page_image(self):
        self.client.force_login(self.editor)
        SchoolValue.objects.create(title='Compassion', description='Care for each other.', order=1)
        data = self.settings_data(about_heading='About us', about_intro='Welcome',
            about_history='<p>Our story.</p>', about_mission='Support every learner.',
            about_vision='A confident future.', about_image=self.image(),
            about_image_alt='Learners in the school grounds')
        self.assertRedirects(self.client.post('/staff/settings/', data), '/staff/settings/')
        self.site.refresh_from_db()
        response = self.client.get('/about/')
        for text in ['Our mission', 'Support every learner.', 'Our vision', 'A confident future.',
                     'Our values', 'Compassion', self.site.about_image.url, 'Learners in the school grounds']:
            self.assertContains(response, text)
        self.assertContains(self.client.get('/staff/settings/'), 'staff-image-preview')
        # Layout and navigation are fixed, regardless of archived page records.
        self.assertEqual(self.client.post('/staff/content/pages/new/', {'title': 'Injected page'}).status_code, 404)

    def test_event_featured_image_and_clear(self):
        self.client.force_login(self.editor)
        data = {'title':'Open day','slug':'open-day','description':'<p>Join us.</p>','location':'School hall',
                'starts_at':'2099-01-01T09:00','ends_at':'2099-01-01T12:00','published':'on',
                'image':self.image(),'image_alt':'The school hall'}
        self.assertEqual(self.client.post('/staff/content/events/new/', data).status_code,302)
        event = Event.objects.get(slug='open-day')
        self.assertContains(self.client.get('/events/open-day/'),event.image.url)
        self.assertContains(self.client.get('/events/open-day/'),'alt="The school hall"')
        self.assertContains(self.client.get('/events/'),'event-thumbnail')
        del data['image']
        data['image-clear'] = 'on'
        self.assertEqual(self.client.post(f'/staff/content/events/{event.pk}/',data).status_code,302)
        event.refresh_from_db()
        self.assertFalse(event.image)
        self.assertNotContains(self.client.get('/events/open-day/'),'class="detail-image"')

    def test_hero_upload_and_clear_restores_themed_fallback(self):
        self.client.force_login(self.editor)
        self.assertContains(self.client.get('/'), 'class="feature-center"')
        response = self.client.post('/staff/settings/',self.settings_data(hero_image=self.image(),hero_image_alt='School courtyard'))
        self.assertRedirects(response,'/staff/settings/')
        self.site.refresh_from_db()
        response=self.client.get('/')
        self.assertContains(response,self.site.hero_image.url)
        self.assertContains(response,'alt="School courtyard"')
        self.assertNotContains(response,'class="feature-center"')
        self.assertContains(self.client.get('/staff/settings/'),'staff-image-preview')
        self.assertRedirects(self.client.post('/staff/settings/',self.settings_data(**{'hero_image-clear':'on'})),'/staff/settings/')
        self.assertContains(self.client.get('/'),'class="feature-center"')

    def test_invalid_featured_images_rejected(self):
        self.client.force_login(self.editor)
        data={'title':'Bad image','slug':'bad','introduction':'Test','body':'Text','order':0,
              'image':SimpleUploadedFile('bad.png',b'<script>bad()</script>',content_type='image/png')}
        self.assertEqual(self.client.post('/staff/settings/',self.settings_data(about_image=data['image'])).status_code,200)
        self.assertFalse(Page.objects.filter(slug='bad').exists())
        data={'title':'Bad event','slug':'bad','description':'Text','location':'School','starts_at':'2099-01-01T09:00',
              'image':SimpleUploadedFile('bad.png',b'not an image',content_type='image/png')}
        self.assertEqual(self.client.post('/staff/content/events/new/',data).status_code,200)
        self.assertFalse(Event.objects.filter(slug='bad').exists())

    def test_new_fields_keep_staff_permissions(self):
        user=User.objects.create_user('officer',is_staff=True)
        user.groups.add(Group.objects.get(name='Admissions officers'))
        self.client.force_login(user)
        self.assertEqual(self.client.post('/staff/settings/', self.settings_data(google_maps_embed_url='https://www.google.com/maps/embed?pb=example')).status_code,403)
        self.assertEqual(self.client.post('/staff/settings/',self.settings_data(about_mission='Unapproved edit')).status_code,403)
        self.assertEqual(self.client.post('/staff/content/events/new/',{'image':self.image()}).status_code,403)
