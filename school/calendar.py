"""Server-rendered school calendar dates, using the configured school timezone."""

import calendar as month_calendar
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import date_format

from .models import Event


MIN_YEAR = 1900
MAX_YEAR = 2100


def _bounded_number(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if minimum <= number <= maximum else default


def _school_time(value, school_timezone):
    return timezone.localtime(value, school_timezone) if timezone.is_aware(value) else value


def _date_boundary(value, school_timezone):
    boundary = datetime.combine(value, time.min)
    return timezone.make_aware(boundary, school_timezone) if settings.USE_TZ else boundary


def _last_event_date(start, end):
    # A midnight end belongs to the preceding day. Instant events stay on their start date.
    return (end - timedelta(microseconds=1)).date() if end > start else start.date()


def build_calendar_context(params):
    school_timezone = timezone.get_default_timezone()
    now = timezone.now()
    today = _school_time(now, school_timezone).date()
    year = _bounded_number(params.get('year'), min(max(today.year, MIN_YEAR), MAX_YEAR), MIN_YEAR, MAX_YEAR)
    month = _bounded_number(params.get('month'), today.month, 1, 12)
    month_start = date(year, month, 1)
    next_start = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_start - timedelta(days=1)
    weeks = month_calendar.Calendar(firstweekday=month_calendar.MONDAY).monthdatescalendar(year, month)
    grid_start, grid_end = weeks[0][0], weeks[-1][-1]
    window_start = _date_boundary(grid_start, school_timezone)
    window_end = _date_boundary(grid_end + timedelta(days=1), school_timezone)
    displayed_events = Event.objects.filter(published=True, starts_at__lt=window_end).filter(
        Q(starts_at__gte=window_start) | Q(ends_at__gt=window_start)
    ).order_by('starts_at', 'pk')

    entries_by_date = {day: [] for week in weeks for day in week}
    month_events = []
    for event in displayed_events:
        start = _school_time(event.starts_at, school_timezone)
        end = _school_time(event.ends_at or event.starts_at, school_timezone)
        last_date = _last_event_date(start, end)
        if start.date() <= month_end and last_date >= month_start:
            month_events.append(event)
        day = max(start.date(), grid_start)
        last_visible_date = min(last_date, grid_end)
        while day <= last_visible_date:
            entries_by_date[day].append({
                'event': event,
                'start_local': start,
                'end_local': end,
                'is_first_day': day == start.date(),
                'is_last_day': day == last_date,
                'continues_before': day > start.date(),
                'continues_after': day < last_date,
            })
            day += timedelta(days=1)

    calendar_weeks = [[{
        'date': day,
        'is_current_month': day.month == month and day.year == year,
        'is_today': day == today,
        'entries': entries_by_date[day],
    } for day in week] for week in weeks]
    month_agenda = [cell for week in calendar_weeks for cell in week
                    if cell['is_current_month'] and cell['entries']]
    previous_month = (month_start - timedelta(days=1)).replace(day=1) if (year, month) > (MIN_YEAR, 1) else None
    upcoming_events = Event.objects.filter(published=True).filter(
        Q(starts_at__gte=now) | Q(ends_at__gt=now)
    ).order_by('starts_at', 'pk')[:4]
    return {
        'events': month_events,
        'calendar_timezone': school_timezone,
        'month_start': month_start,
        'month_end': month_end,
        'month_label': date_format(month_start, 'F Y'),
        'previous_month': previous_month,
        'next_month': next_start if (year, month) < (MAX_YEAR, 12) else None,
        'today': today,
        'today_year': today.year,
        'today_month': today.month,
        'calendar_weeks': calendar_weeks,
        'calendar_weekdays': [{'short': short, 'full': full} for short, full in zip(
            ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
        )],
        'month_agenda': month_agenda,
        'has_month_events': bool(month_agenda),
        'upcoming_events': upcoming_events,
    }
