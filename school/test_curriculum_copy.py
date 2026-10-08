"""Verify imported learner-facing copy without overwriting school edits."""
import json
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from django.apps import apps
from django.core.management import call_command
from django.test import TestCase
from django.utils.text import Truncator, slugify

from .editorial_copy import CURRICULUM_COPY, SUBJECT_COPY
from .management.commands.structure_school_content import plain, sections
from .models import Page, SiteSettings, Subject
from .security import clean_html


COPY_MIGRATION = import_module('school.migrations.0012_learner_curriculum_copy')


class CurriculumCopyTests(TestCase):
    def refresh_copy(self):
        COPY_MIGRATION.refresh_curriculum_copy(
            apps, SimpleNamespace(connection=SimpleNamespace(alias='default')))

    def test_frozen_source_matches_imported_snapshot_and_keeps_all_subjects(self):
        data = json.loads((Path(__file__).parent / 'data/google_sites.json').read_text())
        body = ''.join(f'<{block["tag"]}>{block["html"]}</{block["tag"]}>'
                       for block in data['curriculum']['blocks'][1:])
        body = clean_html(body)
        found = {}
        started = False
        overview = []
        for heading, content in sections(body):
            if heading == 'English':
                started = True
            if started:
                found[slugify(heading)] = content.strip()
            else:
                overview.append((f'<h2>{heading}</h2>' if heading else '') + content)
        self.assertEqual(set(found), set(SUBJECT_COPY))
        self.assertEqual(len(found), 13)
        self.assertEqual(''.join(overview), CURRICULUM_COPY['old_body'])
        for slug, source_body in found.items():
            with self.subTest(subject=slug):
                self.assertEqual(source_body, SUBJECT_COPY[slug]['old_body'])
                self.assertEqual(Truncator(plain(source_body)).words(26),
                                 SUBJECT_COPY[slug]['old_introduction'])
                self.assertIn('you', SUBJECT_COPY[slug]['body'].lower())

    def test_exact_source_migrates_each_field_and_preserves_other_metadata(self):
        site = SiteSettings.objects.create(curriculum_body=CURRICULUM_COPY['old_body'],
                                          curriculum_intro=CURRICULUM_COPY['old_introduction'])
        page = Page.objects.create(title='Curriculum', slug='curriculum',
                                   body=CURRICULUM_COPY['old_body'],
                                   introduction=CURRICULUM_COPY['old_introduction'])
        for slug, copy in SUBJECT_COPY.items():
            Subject.objects.create(title='School-approved ' + copy['title'], slug=slug,
                                   body=copy['old_body'], introduction=copy['old_introduction'],
                                   image='school/approved-photo.png', image_alt='Approved photograph',
                                   order=42, published=False)
        self.refresh_copy()
        site.refresh_from_db()
        page.refresh_from_db()
        self.assertEqual(site.curriculum_body, CURRICULUM_COPY['body'])
        self.assertEqual(site.curriculum_intro, CURRICULUM_COPY['introduction'])
        self.assertEqual(page.body, CURRICULUM_COPY['body'])
        self.assertEqual(page.introduction, CURRICULUM_COPY['introduction'])
        for subject in Subject.objects.all():
            copy = SUBJECT_COPY[subject.slug]
            self.assertEqual(subject.body, copy['body'])
            self.assertEqual(subject.introduction, copy['introduction'])
            self.assertEqual(subject.title, 'School-approved ' + copy['title'])
            self.assertEqual(subject.image.name, 'school/approved-photo.png')
            self.assertEqual(subject.image_alt, 'Approved photograph')
            self.assertEqual(subject.order, 42)
            self.assertFalse(subject.published)

    def test_custom_and_blank_fields_survive_while_independent_source_fields_update(self):
        site = SiteSettings.objects.create(curriculum_body='<p>School-approved overview.</p>',
                                          curriculum_intro=CURRICULUM_COPY['old_introduction'])
        custom = Subject.objects.create(title='English', slug='english',
                                        body='<p>Our own English course.</p>',
                                        introduction=SUBJECT_COPY['english']['old_introduction'])
        blank = Subject.objects.create(title='Sesotho', slug='sesotho', body='', introduction='')
        unrelated = Subject.objects.create(title='New subject', slug='new-subject',
                                           body=SUBJECT_COPY['english']['old_body'])
        self.refresh_copy()
        site.refresh_from_db()
        custom.refresh_from_db()
        blank.refresh_from_db()
        unrelated.refresh_from_db()
        self.assertEqual(site.curriculum_body, '<p>School-approved overview.</p>')
        self.assertEqual(site.curriculum_intro, CURRICULUM_COPY['introduction'])
        self.assertEqual(custom.body, '<p>Our own English course.</p>')
        self.assertEqual(custom.introduction, SUBJECT_COPY['english']['introduction'])
        self.assertEqual((blank.body, blank.introduction), ('', ''))
        self.assertEqual(unrelated.body, SUBJECT_COPY['english']['old_body'])
        self.refresh_copy()
        custom.refresh_from_db()
        self.assertEqual(custom.body, '<p>Our own English course.</p>')

    def test_new_import_uses_learner_copy_and_repeat_import_preserves_edits(self):
        call_command('import_google_sites', verbosity=0)
        site = SiteSettings.objects.get(pk=1)
        self.assertEqual(site.curriculum_body, CURRICULUM_COPY['body'])
        self.assertEqual(site.curriculum_intro, CURRICULUM_COPY['introduction'])
        self.assertIn('support you', site.staff_intro)
        self.assertEqual(Subject.objects.count(), 13)
        for subject in Subject.objects.all():
            self.assertEqual(subject.body, SUBJECT_COPY[subject.slug]['body'])
            self.assertEqual(subject.introduction, SUBJECT_COPY[subject.slug]['introduction'])
        english = Subject.objects.get(slug='english')
        english.body = '<p>Our approved update.</p>'
        english.save()
        site.curriculum_body = '<p>Our approved curriculum.</p>'
        site.save()
        call_command('import_google_sites', verbosity=0)
        call_command('structure_school_content', verbosity=0)
        english.refresh_from_db()
        site.refresh_from_db()
        self.assertEqual(english.body, '<p>Our approved update.</p>')
        self.assertEqual(site.curriculum_body, '<p>Our approved curriculum.</p>')
