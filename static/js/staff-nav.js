document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('#staff-navigation');
  const toggle = document.querySelector('[data-staff-nav-toggle]');
  const backdrop = document.querySelector('.staff-nav-backdrop');
  if (!sidebar || !toggle) return;
  const mobile = window.matchMedia('(max-width: 760px)');
  let desktopHidden = false;
  try { desktopHidden = localStorage.getItem('staff-navigation-hidden') === 'true'; } catch (_) {}
  let open;
  function setOpen(value, restoreFocus = false) {
    open = value;
    document.body.classList.add('staff-nav-ready');
    document.body.classList.toggle('staff-nav-hidden', !open);
    document.body.classList.toggle('staff-nav-mobile-open', mobile.matches && open);
    sidebar.inert = !open;
    sidebar.setAttribute('aria-hidden', String(!open));
    toggle.setAttribute('aria-expanded', String(open));
    backdrop.hidden = !(mobile.matches && open);
    if (restoreFocus) toggle.focus();
  }
  toggle.addEventListener('click', () => {
    setOpen(!open);
    if (!mobile.matches) {
      desktopHidden = !open;
      try { localStorage.setItem('staff-navigation-hidden', String(desktopHidden)); } catch (_) {}
    } else if (open) sidebar.querySelector('[data-staff-nav-close]').focus();
  });
  document.querySelectorAll('[data-staff-nav-close]').forEach(button => {
    button.addEventListener('click', () => {
      setOpen(false, true);
      if (!mobile.matches) {
        desktopHidden = true;
        try { localStorage.setItem('staff-navigation-hidden', 'true'); } catch (_) {}
      }
    });
  });
  document.addEventListener('keydown', event => {
    if (!open) return;
    if (event.key === 'Escape') { setOpen(false, true); return; }
    if (event.key !== 'Tab' || !mobile.matches) return;
    const items = [...sidebar.querySelectorAll('a[href], button')].filter(item => !item.disabled);
    const first = items[0], last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
  mobile.addEventListener('change', () => setOpen(mobile.matches ? false : !desktopHidden, sidebar.contains(document.activeElement)));
  setOpen(mobile.matches ? false : !desktopHidden);
});
