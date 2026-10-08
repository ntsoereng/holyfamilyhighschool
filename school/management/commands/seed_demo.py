from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from school.models import SiteSettings, SchoolValue, Page, Article, Event

class Command(BaseCommand):
    help = 'Create editable pitch content without overwriting existing records.'
    @transaction.atomic
    def handle(self, *args, **options):
        SiteSettings.objects.get_or_create(pk=1)
        values = [
            ('Faith & character', 'A community shaped by compassion, integrity, and respect for one another.'),
            ('Learning with purpose', 'Encouraging curiosity, thoughtful questions, and the confidence to keep growing.'),
            ('Belonging & service', 'Discovering our gifts and using them to make a positive difference in the lives of others.'),
        ]
        for order, (title, description) in enumerate(values):
            SchoolValue.objects.get_or_create(title=title, defaults={'description': description, 'order': order})
        pages = [
            ('About us', 'about', 'Rooted in faith. Focused on the future.', '<h2>A community where learners belong</h2><p>Holy Family High School is presented here as a place of learning, faith, and shared purpose. This demonstration introduces the school’s online presence; the school will confirm its history, leadership, and mission before launch.</p><h2>Our approach</h2><p>We value care for one another, a commitment to learning, and the courage to contribute. Families and staff work together to support every learner.</p>'),
            ('Academics', 'academics', 'Curiosity today. Possibility tomorrow.', '<h2>Learning that builds confidence</h2><p>Our academic page will give you a clear view of the school’s subjects, entry levels, and approach to teaching.</p><h2>Subjects and pathways</h2><p>The confirmed curriculum, subject choices, assessment information, and learner support details will be added by the school. Please contact the office to discuss your learning needs.</p>'),
        ]
        for order, (title, slug, intro, body) in enumerate(pages):
            Page.objects.get_or_create(slug=slug, defaults={'title':title,'introduction':intro,'body':body,'published':True,'order':order,'show_school_values':slug == 'about'})
        stories = [
            ('A new chapter for our school community', 'welcome-to-holy-family', 'School news', 'A first look at a welcoming online home for learners, families, and friends of Holy Family.'),
            ('Making room for curiosity', 'making-room-for-curiosity', 'Learning', 'Celebrating the questions, conversations, and small discoveries that make learning meaningful.'),
            ('Growing through service', 'growing-through-service', 'Community', 'A school community is strengthened by the care we show and the contributions we make.'),
        ]
        for title, slug, category, excerpt in stories:
            Article.objects.get_or_create(slug=slug, defaults={'title':title,'category':category,'excerpt':excerpt,
                'body':f'<p>{excerpt}</p><p>This is an example article for the website pitch. Staff can replace this story, add a photograph, format the article, and choose when it is published using the school administration area.</p>', 'published':True})
        for days, title, slug in [(14,'Meet the school · example event','meet-the-school'), (28,'Family conversation · example event','family-conversation'), (42,'Celebrating learning · example event','celebrating-learning')]:
            start = (timezone.now() + timedelta(days=days)).replace(hour=8, minute=0, second=0, microsecond=0)
            Event.objects.get_or_create(slug=slug, defaults={'title':title,'starts_at':start,'ends_at':start+timedelta(hours=2),
                'location':'Venue to be confirmed', 'description':'<p>This is a demonstration calendar entry, not a confirmed school event. Staff can replace it with an approved date, venue, and event details.</p>', 'published':True})
        self.stdout.write(self.style.SUCCESS('Demo content is ready. Existing content was preserved.'))
