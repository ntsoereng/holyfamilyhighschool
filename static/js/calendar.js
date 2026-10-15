// Keep future dates available without repeating an expanded list on phones.
const upcomingDates = document.querySelector('[data-calendar-upcoming]');
if (upcomingDates) {
  const compactCalendar = window.matchMedia('(max-width: 760px)');
  const updateUpcoming = () => { upcomingDates.open = !compactCalendar.matches; };
  compactCalendar.addEventListener('change', updateUpcoming);
  updateUpcoming();
}
