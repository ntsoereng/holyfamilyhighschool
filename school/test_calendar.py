from datetime import date, datetime, timezone as datetime_timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Event, SiteSettings


@override_settings(
    TIME_ZONE='Africa/Maseru', USE_TZ=True, SECURE_SSL_REDIRECT=False,
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class MonthlyCalendarTests(TestCase):
    def setUp(self):
        SiteSettings.objects.create()
        # Already 8 October in Lesotho, although the UTC date is still 7 October.
        clock = patch('school.calendar.timezone.now', return_value=datetime(2026, 10, 7, 22, 30, tzinfo=datetime_timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
        self.school_zone = ZoneInfo('Africa/Maseru')

    def local(self, year, month, day, hour=9, minute=0):
        return datetime(year, month, day, hour, minute, tzinfo=self.school_zone)

    def event(self, slug, start, end=None, published=True, **extra):
        return Event.objects.create(title=slug.replace('-', ' ').title(), slug=slug,
                                    starts_at=start, ends_at=end, published=published,
                                    description='School event.', location='School hall', **extra)

    def cells(self, response):
        return {cell['date']: cell for week in response.context['calendar_weeks'] for cell in week}

    def event_ids(self, cell):
        return [entry['event'].pk for entry in cell['entries']]

    def test_default_month_uses_school_date_with_accessible_monday_first_grid(self):
        response = self.client.get('/events/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['month_start'], date(2026, 10, 1))
        self.assertEqual(response.context['today'], date(2026, 10, 8))
        for week in response.context['calendar_weeks']:
            self.assertEqual(len(week), 7)
            self.assertEqual([cell['date'].weekday() for cell in week], list(range(7)))
        self.assertTrue(self.cells(response)[date(2026, 10, 8)]['is_today'])
        self.assertContains(response, '<abbr title="Monday">Mon</abbr>')
        self.assertContains(response, 'aria-current="date"')
        self.assertContains(response, 'href="?year=2026&amp;month=9"')
        self.assertContains(response, 'href="?year=2026&amp;month=11"')
        self.assertContains(response, 'href="?year=2026&amp;month=10"')
        self.assertContains(response, 'class="calendar-agenda"')
        self.assertContains(response, 'Ask about an event')
        self.assertEqual(response.content.count(b'<h1'), 1)
        self.assertNotContains(response, 'style=')
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])

    def test_requested_archive_month_includes_past_published_events_and_hides_drafts(self):
        archive = self.event('archive-school-day', self.local(2003, 5, 12))
        self.event('private-planning-day', self.local(2003, 5, 13), published=False)
        self.event('unrelated-past-event', self.local(2003, 4, 10))
        response = self.client.get('/events/?year=2003&month=5')
        self.assertEqual(response.context['events'], [archive])
        self.assertContains(response, 'Archive School Day')
        self.assertNotContains(response, 'Private Planning Day')
        self.assertNotContains(response, 'Unrelated Past Event')
        self.assertContains(response, '/events/archive-school-day/')

    def test_overlapping_multi_day_event_appears_on_each_affected_date(self):
        event = self.event('school-retreat', self.local(2026, 9, 30, 18), self.local(2026, 10, 2, 12))
        response = self.client.get('/events/?year=2026&month=10')
        cells = self.cells(response)
        self.assertEqual(response.context['events'], [event])
        for day in [date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)]:
            self.assertIn(event.pk, self.event_ids(cells[day]))
        self.assertNotIn(event.pk, self.event_ids(cells[date(2026, 10, 3)]))
        self.assertTrue(cells[date(2026, 9, 30)]['entries'][0]['is_first_day'])
        self.assertTrue(cells[date(2026, 10, 1)]['entries'][0]['continues_before'])
        self.assertTrue(cells[date(2026, 10, 2)]['entries'][0]['is_last_day'])
        self.assertEqual([day['date'] for day in response.context['month_agenda']], [date(2026, 10, 1), date(2026, 10, 2)])

    def test_midnight_end_is_exclusive_and_does_not_add_a_day(self):
        event = self.event('sports-weekend', self.local(2026, 10, 1, 9), self.local(2026, 10, 4, 0))
        previous = self.event('september-event', self.local(2026, 9, 30, 9), self.local(2026, 10, 1, 0))
        response = self.client.get('/events/?year=2026&month=10')
        cells = self.cells(response)
        self.assertEqual(response.context['events'], [event])
        self.assertNotIn(previous.pk, self.event_ids(cells[date(2026, 10, 1)]))
        self.assertIn(event.pk, self.event_ids(cells[date(2026, 10, 3)]))
        self.assertNotIn(event.pk, self.event_ids(cells[date(2026, 10, 4)]))

    def test_utc_month_boundary_and_rendered_times_use_school_timezone(self):
        event = self.event('early-school-event', datetime(2026, 9, 30, 22, 15, tzinfo=datetime_timezone.utc),
                           datetime(2026, 10, 1, 23, tzinfo=datetime_timezone.utc))
        with timezone.override('UTC'):
            response = self.client.get('/events/?year=2026&month=10')
        cells = self.cells(response)
        self.assertIn(event.pk, self.event_ids(cells[date(2026, 10, 1)]))
        self.assertIn(event.pk, self.event_ids(cells[date(2026, 10, 2)]))
        self.assertContains(response, 'datetime="2026-10-01T00:15:00+02:00"')
        self.assertContains(response, '>00:15</time>')

    def test_instant_events_without_or_with_equal_end_dates_are_retained(self):
        without_end = self.event('morning-assembly', self.local(2026, 10, 1, 0))
        equal_end = self.event('opening-bell', self.local(2026, 10, 1, 0), self.local(2026, 10, 1, 0))
        response = self.client.get('/events/?year=2026&month=10')
        self.assertCountEqual(self.event_ids(self.cells(response)[date(2026, 10, 1)]), [without_end.pk, equal_end.pk])

    def test_invalid_and_out_of_range_parameters_fall_back_safely(self):
        for year, month in [('invalid', '13'), ('0', '-1'), ('999999999999', 'invalid'), ('9' * 5000, '0')]:
            with self.subTest(year=year[:20], month=month):
                response = self.client.get('/events/', {'year': year, 'month': month})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['month_start'], date(2026, 10, 1))

    def test_navigation_stops_at_year_bounds_and_leap_day_is_present(self):
        earliest = self.client.get('/events/?year=1900&month=1')
        latest = self.client.get('/events/?year=2100&month=12')
        self.assertIsNone(earliest.context['previous_month'])
        self.assertIsNone(latest.context['next_month'])
        self.assertContains(earliest, 'aria-disabled="true"')
        leap = self.client.get('/events/?year=2024&month=2')
        self.assertTrue(self.cells(leap)[date(2024, 2, 29)]['is_current_month'])

    def test_upcoming_panel_includes_ongoing_and_future_published_events_only(self):
        ongoing = self.event('ongoing-retreat', self.local(2026, 10, 7, 9), self.local(2026, 10, 9, 12))
        future = self.event('next-open-day', self.local(2099, 1, 1), image='school/upcoming.png')
        self.event('secret-upcoming-day', self.local(2026, 10, 9), published=False)
        response = self.client.get('/events/')
        self.assertEqual(list(response.context['upcoming_events']), [ongoing, future])
        self.assertContains(response, 'event-thumbnail')
        self.assertNotContains(response, 'Secret Upcoming Day')

    def test_titles_are_escaped_in_the_grid_and_agenda(self):
        Event.objects.create(title='<script>bad()</script>', slug='escaped-event', description='Safe body',
                             location='School hall', starts_at=self.local(2026, 10, 8), published=True)
        response = self.client.get('/events/')
        self.assertNotContains(response, '<script>bad()</script>')
        self.assertContains(response, '&lt;script&gt;bad()&lt;/script&gt;')

    @override_settings(USE_TZ=False)
    def test_calendar_also_supports_naive_datetime_development_settings(self):
        self.event('development-event', datetime(2026, 10, 8, 9))
        with patch('school.calendar.timezone.now', return_value=datetime(2026, 10, 8, 12)):
            response = self.client.get('/events/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '>09:00</time>')
