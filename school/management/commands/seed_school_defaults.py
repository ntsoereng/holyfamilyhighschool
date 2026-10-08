"""Non-destructive defaults for the rebuilt school site."""
from django.core.management.base import BaseCommand
from django.db import transaction
from school.models import SiteSettings, Page, SchoolValue

class Command(BaseCommand):
    help = 'Fill blank school information using the imported source and mission-derived defaults.'

    @transaction.atomic
    def handle(self, *args, **options):
        site, _ = SiteSettings.objects.get_or_create(pk=1)
        defaults = {
            'address': 'Ha-Barete, St. Monica’s, Maputsoe, Leribe, Lesotho\nPostal address: P.O. Box 56, Maputsoe 350, Leribe',
            'email': 'holyfamilyhighschool56@gmail.com', 'phone': '+266 2243 0282',
            'google_maps_embed_url': 'https://maps.google.com/maps?q=Holy+Family+High+School+Maputsoe+Lesotho&output=embed',
        }
        for key, value in defaults.items():
            if not getattr(site, key):
                setattr(site, key, value)
        # Expand only the original default notice, preserving any staff wording.
        if site.privacy_text.startswith('We use application details only'):
            site.privacy_text = ('We use the information you submit through our admissions and contact forms to respond to your enquiry and, where relevant, assess an application. '
                'Messages and applications are stored securely and are accessible only to authorised school staff. Contact the school office to request a correction or deletion. '
                'Please do not submit sensitive records through these forms. Essential cookies support staff sign-in, form security and submission confirmations. '
                'The contact page includes a Google Maps embed, which connects to Google when loaded.')
        site.save()
        about = Page.objects.filter(slug='about').first()
        if about:
            if not about.vision:
                about.vision = 'Girls equipped with the knowledge, character and confidence to contribute to every sphere of life.'
            about.show_school_values = True
            about.save()
        for order, (title, description) in enumerate([
            ('Faith & character', 'Growing in faith, moral responsibility and respect for one another.'),
            ('Learning with purpose', 'Developing knowledge and intellectual curiosity for higher education and life beyond school.'),
            ('Belonging & service', 'A caring community where day scholars and boarders learn to contribute with confidence.'),
        ]):
            SchoolValue.objects.get_or_create(title=title, defaults={'description': description, 'order': order})
        from school.page_content import copy_legacy_content
        copy_legacy_content()
        self.stdout.write(self.style.SUCCESS('School defaults ready. Vision wording is derived from the published mission and can be edited by staff.'))
