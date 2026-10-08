from unittest.mock import patch

from django.db import OperationalError
from django.test import SimpleTestCase, override_settings


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=['testserver'])
class ProductionErrorTests(SimpleTestCase):
    def test_unknown_page_remains_a_generic_404_without_database_access(self):
        with patch('school.models.SiteSettings.objects.first',
                   side_effect=OperationalError('Database unavailable')):
            response = self.client.get('/a-page-that-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'This page isn’t here.', status_code=404)
        self.assertNotContains(response, 'Database unavailable', status_code=404)
