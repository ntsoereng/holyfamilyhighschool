import json
import re

from django.test import TestCase, override_settings
from .models import SiteSettings


@override_settings(SITE_URL='https://holyfamily.ac.ls', SECURE_SSL_REDIRECT=False,
                   STORAGES={'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class SchoolStructuredDataTests(TestCase):
    def test_school_identity_uses_public_content_and_safe_json(self):
        school = SiteSettings.objects.create(name='Holy </script><script>unsafe()</script> Family',
                                            email='school@example.test', phone='+266 2000 0000',
                                            address='Maputsoe, Lesotho', facebook_url='https://facebook.com/example-school')
        response = self.client.get('/')
        scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>',
                             response.content.decode(), re.S)
        self.assertEqual(len(scripts), 1)
        data = json.loads(scripts[0])
        self.assertEqual(data['@type'], 'School')
        self.assertEqual(data['name'], school.name)
        self.assertEqual(data['url'], 'https://holyfamily.ac.ls/')
        self.assertEqual(data['logo'], 'https://holyfamily.ac.ls/static/images/holy-family-favicon-512.png')
        self.assertEqual(data['address'], school.address)
        self.assertEqual(data['telephone'], school.phone)
        self.assertEqual(data['email'], school.email)
        self.assertNotIn('</script>', scripts[0])
        self.assertNotContains(response, '<script>unsafe()</script>')
        self.assertNotIn('unsafe-inline', response['Content-Security-Policy'])

    def test_private_and_inner_pages_do_not_repeat_school_schema(self):
        SiteSettings.objects.create()
        for path in ['/about/', '/apply/', '/staff/login/']:
            with self.subTest(path=path):
                self.assertNotContains(self.client.get(path), 'application/ld+json')
