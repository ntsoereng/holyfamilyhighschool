from io import BytesIO
import subprocess
from unittest.mock import patch
import uuid

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.handlers.wsgi import WSGIHandler
from django.core.management import call_command
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfdoc
from reportlab.lib.pdfencrypt import StandardEncryption

from .models import Prospectus, ProspectusPage
from .prospectus_forms import prepare_pdf
from .prospectus_limits import MAX_PDF_BYTES


def sample_pdf(pages=2, active=False, password=None):
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(420, 595), encrypt=StandardEncryption(password) if password else None)
    if active:
        pdf._doc.Catalog.OpenAction = pdfdoc.PDFDictionary({
            'S': pdfdoc.PDFName('JavaScript'), 'JS': pdfdoc.PDFString('app.alert("untrusted-pdf")')})
    for number in range(1, pages + 1):
        pdf.setFont('Helvetica', 20)
        pdf.drawString(35, 540, f'Holy Family Prospectus - Page {number}')
        pdf.setFont('Helvetica', 12)
        pdf.drawString(35, 505, 'Welcome to Holy Family High School.')
        pdf.drawString(35, 480, '<script>alert("text only")</script>')
        if active:
            pdf.linkURL('https://untrusted.example.test/', (30, 470, 350, 500))
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def upload(data=None, name='prospectus.pdf'):
    return SimpleUploadedFile(name, data if data is not None else sample_pdf(), content_type='application/pdf')


class ProspectusConversionTests(SimpleTestCase):
    def test_conversion_has_readable_pages_text_and_only_flattened_pdf(self):
        source = sample_pdf(active=True)
        self.assertIn(b'/JavaScript', source)
        prepared = prepare_pdf(upload(source))
        self.assertEqual(len(prepared['pages']), 2)
        for page in prepared['pages']:
            image = Image.open(BytesIO(page['image']))
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.size, (page['width'], page['height']))
            self.assertIn('Welcome to Holy Family', page['text'])
        self.assertTrue(prepared['pdf'].startswith(b'%PDF-'))
        for active_key in (b'/JavaScript', b'/OpenAction', b'/Annots', b'/EmbeddedFiles', b'/AcroForm'):
            self.assertNotIn(active_key, prepared['pdf'])
        self.assertNotEqual(source, prepared['pdf'])

    def test_rejects_wrong_types_empty_corrupt_encrypted_and_oversized_pdfs(self):
        files = [upload(b'<!doctype html>', 'bad.pdf'), upload(b'', 'empty.pdf'),
            upload(b'%PDF-not-valid', 'corrupt.pdf'), upload(name='bad.html'),
            upload(b'%PDF-' + b'A' * MAX_PDF_BYTES), upload(sample_pdf(password='private')),
            upload(sample_pdf(pages=41))]
        for file in files:
            with self.subTest(name=file.name), self.assertRaises(ValidationError):
                prepare_pdf(file)

    def test_renderer_timeout_fails_closed(self):
        with patch('school.prospectus_forms.subprocess.run', side_effect=subprocess.TimeoutExpired('renderer', 30)):
            with self.assertRaises(ValidationError):
                prepare_pdf(upload())


@override_settings(SECURE_SSL_REDIRECT=False, DEBUG=False, SITE_URL='https://school.example.test',
                   ALLOWED_HOSTS=['testserver'], STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ProspectusWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_staff_groups', verbosity=0)
        cls.office = User.objects.create_user('prospectus-office', is_staff=True)
        cls.office.groups.add(Group.objects.get(name='Admissions officers'))
        cls.editor = User.objects.create_user('prospectus-editor', is_staff=True)
        cls.editor.groups.add(Group.objects.get(name='Content editors'))
        cls.prepared = prepare_pdf(upload())
        cls.document = Prospectus.objects.create(page_count=2, pdf=cls.prepared['pdf'])
        ProspectusPage.objects.bulk_create([ProspectusPage(prospectus=cls.document, **page) for page in cls.prepared['pages']])

    def action(self, action, revision=None):
        self.document.refresh_from_db()
        return self.client.post(reverse('staff-prospectus'), {
            'action': action, 'revision': str(revision or self.document.revision)})

    def publish(self):
        self.document.published = True
        self.document.save()

    def test_missing_and_hidden_prospectus_show_coming_soon_without_files(self):
        response = self.client.get(reverse('prospectus'))
        self.assertContains(response, 'The prospectus will be uploaded soon.')
        self.assertNotContains(response, 'Download PDF')
        for route, args in [('prospectus-page', [self.document.revision, 1]),
                            ('prospectus-download', [self.document.revision])]:
            response = self.client.get(reverse(route, args=args))
            self.assertEqual(response.status_code, 404)
            self.assertIn('no-store', response['Cache-Control'])
        self.document.delete()
        self.assertContains(self.client.get(reverse('prospectus')), 'The prospectus will be uploaded soon.')

    def test_public_viewer_serves_images_and_safe_download(self):
        self.publish()
        response = self.client.get(reverse('prospectus'))
        self.assertContains(response, 'Download PDF')
        self.assertNotContains(response, 'Read page 1 text')
        self.assertNotContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert("text only")</script>')
        self.assertIn('no-store', response['Cache-Control'])
        image = self.client.get(reverse('prospectus-page', args=[self.document.revision, 1]))
        self.assertEqual(image['Content-Type'], 'image/jpeg')
        self.assertEqual(image['X-Content-Type-Options'], 'nosniff')
        self.assertIn('noindex', image['X-Robots-Tag'])
        self.assertEqual(image['Content-Security-Policy'], "default-src 'none'; sandbox")
        self.assertEqual(Image.open(BytesIO(image.content)).format, 'JPEG')
        response = self.client.get(reverse('prospectus-download', args=[self.document.revision]))
        data = response.content
        self.assertEqual(data, self.prepared['pdf'])
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('no-store', response['Cache-Control'])

        head = self.client.head(reverse('prospectus-download', args=[self.document.revision]))
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        self.assertEqual(int(head['Content-Length']), len(data))

    def test_concurrent_replacement_cannot_leak_unpublished_page_text(self):
        self.publish()
        stale = Prospectus.objects.defer('pdf').get(pk=1)
        self.document.published = False
        self.document.revision = uuid.uuid4()
        self.document.save()
        self.document.pages.update(text='PRIVATE DRAFT CONTENT')
        with patch('school.prospectus_views.current_prospectus', return_value=stale):
            response = self.client.get(reverse('prospectus'))
        self.assertNotContains(response, 'PRIVATE DRAFT CONTENT')

    def test_download_works_with_wsgi_wrapper_requiring_file_descriptor(self):
        self.publish()
        path = reverse('prospectus-download', args=[self.document.revision])

        def file_wrapper(file, block_size):
            # Some production WSGI wrappers require a real OS file descriptor.
            file.fileno()
            return iter(lambda: file.read(block_size), b'')

        environ = RequestFactory().get(path).environ
        environ['wsgi.file_wrapper'] = file_wrapper
        started = []
        response = WSGIHandler()(environ, lambda status, headers: started.append((status, dict(headers))))
        try:
            data = b''.join(response)
        finally:
            response.close()
        status, headers = started[0]
        self.assertEqual(status, '200 OK')
        self.assertEqual(data, self.prepared['pdf'])
        self.assertEqual(headers['Content-Type'], 'application/pdf')
        self.assertEqual(int(headers['Content-Length']), len(self.prepared['pdf']))
        self.assertEqual(headers['Content-Disposition'],
            'attachment; filename="Holy-Family-High-School-prospectus.pdf"')
        self.assertIn('no-store', headers['Cache-Control'])

    def test_office_uploads_hidden_reviews_and_publishes_then_withdraws(self):
        self.client.force_login(self.office)
        old_revision = self.document.revision
        response = self.client.post(reverse('staff-prospectus'), {'action': 'upload', 'pdf': upload()})
        self.assertRedirects(response, reverse('staff-prospectus'))
        self.document.refresh_from_db()
        self.assertFalse(self.document.published)
        self.assertNotEqual(self.document.revision, old_revision)
        preview = reverse('staff-prospectus-page', args=[self.document.revision, 1])
        self.assertEqual(self.client.get(preview).status_code, 200)
        self.assertEqual(self.client.get(reverse('prospectus-page', args=[self.document.revision, 1])).status_code, 404)
        self.assertEqual(self.action('publish').status_code, 302)
        self.document.refresh_from_db()
        image_url = reverse('prospectus-page', args=[self.document.revision, 1])
        download_url = reverse('prospectus-download', args=[self.document.revision])
        self.assertEqual(self.client.get(image_url).status_code, 200)
        self.assertEqual(self.action('unpublish').status_code, 302)
        self.assertContains(self.client.get(reverse('prospectus')), 'The prospectus will be uploaded soon.')
        self.assertEqual(self.client.get(image_url).status_code, 404)
        self.assertEqual(self.client.get(download_url).status_code, 404)
        self.assertEqual(LogEntry.objects.filter(user=self.office).count(), 3)

    def test_replacement_revokes_old_urls_and_stale_actions(self):
        self.publish()
        self.client.force_login(self.office)
        old_revision = self.document.revision
        with patch('school.prospectus_forms.prepare_pdf', return_value=self.prepared):
            self.assertEqual(self.client.post(reverse('staff-prospectus'), {'action': 'upload', 'pdf': upload()}).status_code, 302)
        self.assertEqual(self.client.get(reverse('prospectus-download', args=[old_revision])).status_code, 404)
        self.assertEqual(self.client.get(reverse('prospectus-page', args=[old_revision, 1])).status_code, 404)
        self.assertEqual(self.action('publish', old_revision).status_code, 409)
        self.assertEqual(self.action('delete', old_revision).status_code, 409)
        self.document.refresh_from_db()
        self.assertFalse(self.document.published)

    def test_invalid_upload_and_database_failure_preserve_existing_publication(self):
        self.publish()
        self.client.force_login(self.office)
        self.assertEqual(self.client.post(reverse('staff-prospectus'), {'action': 'upload', 'pdf': upload(b'bad')}).status_code, 400)
        with patch('school.prospectus_forms.prepare_pdf', return_value=self.prepared), patch(
                'school.prospectus_views.ProspectusPage.objects.bulk_create', side_effect=RuntimeError('Test failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('staff-prospectus'), {'action': 'upload', 'pdf': upload()})
        self.document.refresh_from_db()
        self.assertTrue(self.document.published)
        self.assertEqual(self.document.pages.count(), 2)
        self.assertEqual(bytes(self.document.pdf), self.prepared['pdf'])
        self.assertFalse(LogEntry.objects.filter(user=self.office).exists())

    def test_delete_removes_all_pages_and_public_page_returns_soon(self):
        self.client.force_login(self.office)
        self.assertEqual(self.action('delete').status_code, 302)
        self.assertFalse(Prospectus.objects.exists())
        self.assertFalse(ProspectusPage.objects.exists())
        self.assertContains(self.client.get(reverse('prospectus')), 'The prospectus will be uploaded soon.')

    def test_permissions_preview_and_navigation(self):
        path = reverse('staff-prospectus')
        preview = reverse('staff-prospectus-page', args=[self.document.revision, 1])
        self.assertEqual(self.client.get(path).status_code, 302)
        self.assertEqual(self.client.get(preview).status_code, 302)
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get(preview).status_code, 403)
        with patch('school.prospectus_forms.prepare_pdf') as prepare:
            self.assertEqual(self.client.post(path, {'action': 'upload', 'pdf': upload()}).status_code, 403)
            prepare.assert_not_called()
        self.client.force_login(self.office)
        self.assertContains(self.client.get(path), 'Publish prospectus')
        readonly = User.objects.create_user('prospectus-reader', is_staff=True)
        readonly.user_permissions.add(Permission.objects.get(codename='view_prospectus'))
        self.client.force_login(readonly)
        self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get(preview).status_code, 200)
        self.assertEqual(self.action('publish').status_code, 403)
        self.assertEqual(self.action('delete').status_code, 403)
        self.assertContains(self.client.get('/'), 'href="/prospectus/"')

    def test_bad_actions_ids_upload_size_and_csrf_do_not_change_document(self):
        self.client.force_login(self.office)
        self.assertEqual(self.client.post(reverse('staff-prospectus'), {'action': 'unknown'}).status_code, 400)
        self.assertEqual(self.client.get(reverse('prospectus-page', args=[uuid.uuid4(), 1])).status_code, 404)
        response = self.client.post(reverse('staff-prospectus'), b'x', content_type='application/pdf', CONTENT_LENGTH=str(MAX_PDF_BYTES + 70000))
        self.assertEqual(response.status_code, 413)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.office)
        self.assertEqual(csrf_client.post(reverse('staff-prospectus'), {'action': 'publish'}).status_code, 403)
        self.document.refresh_from_db()
        self.assertFalse(self.document.published)
