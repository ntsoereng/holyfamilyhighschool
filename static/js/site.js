document.documentElement.classList.add('js-enabled');

const toggle = document.querySelector('[data-menu-toggle]');
const menu = document.querySelector('[data-menu]');
if (toggle && menu) {
  const setMenuOpen = (open, restoreFocus = false) => {
    toggle.setAttribute('aria-expanded', String(open));
    menu.classList.toggle('is-open', open);
    if (!open) {
      menu.querySelectorAll('.nav-dropdown[open]').forEach(dropdown => dropdown.removeAttribute('open'));
    }
    if (restoreFocus) toggle.focus();
  };
  toggle.addEventListener('click', () => {
    setMenuOpen(toggle.getAttribute('aria-expanded') !== 'true');
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
      setMenuOpen(false, true);
    }
  });
  menu.addEventListener('click', (event) => {
    if (event.target.closest('a')) setMenuOpen(false);
  });
  document.addEventListener('click', (event) => {
    if (!menu.contains(event.target) && !toggle.contains(event.target)) setMenuOpen(false);
  });
}

// Native details dropdowns also work without JavaScript.
document.querySelectorAll('.nav-dropdown').forEach(dropdown => {
  document.addEventListener('click', event => {
    if (!dropdown.contains(event.target)) dropdown.removeAttribute('open');
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && dropdown.open) {
      dropdown.removeAttribute('open');
      dropdown.querySelector('summary').focus();
    }
  });
});

// Scroll effects are optional: content stays visible without these browser APIs.
(() => {
  if (!document.body.classList.contains('public-site') ||
      !('IntersectionObserver' in window) ||
      typeof Element.prototype.animate !== 'function' ||
      typeof window.matchMedia !== 'function') return;

  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const selectors = [
    '.common-paths .section-heading',
    '.welcome-copy', '.welcome-visual', '.value-card', '.article-card',
    '.hf-about-opening > *', '.hf-about-principles article',
    '.subject-card', '.hf-department-card', '.staff-profile-card',
    '.hf-profile-layout', '.hf-page-next',
    '.calendar-board', '.calendar-upcoming',
    '.hf-contact-sidebar', '.map-section', '.hf-admissions-sidebar',
  ].join(', ');
  const candidates = [...document.querySelectorAll(selectors)];
  // Avoid animating both a section and its children, or moving active forms.
  const pending = new Set(candidates.filter(element =>
    !element.querySelector('form') &&
    !candidates.some(parent => parent !== element && parent.contains(element))
  ));
  const animations = new Map();
  let observer;

  const stop = () => {
    if (observer) observer.disconnect();
    observer = undefined;
    animations.forEach(animation => animation.cancel());
    animations.clear();
  };

  const start = () => {
    if (motionPreference.matches || observer) return;
    // Keep the initial viewport and restored scroll position immediately still.
    pending.forEach(element => {
      if (element.getBoundingClientRect().top < window.innerHeight) pending.delete(element);
    });
    if (!pending.size) return;

    observer = new IntersectionObserver(entries => {
      if (!observer || motionPreference.matches) return;
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const element = entry.target;
        observer.unobserve(element);
        pending.delete(element);
        if (motionPreference.matches || element.contains(document.activeElement)) return;

        const animation = element.animate([
          { opacity: 0, transform: 'translateY(14px)' },
          { opacity: 1, transform: 'translateY(0)' },
        ], { duration: 400, easing: 'cubic-bezier(.22, 1, .36, 1)', fill: 'none' });
        animations.set(element, animation);
        const forget = () => animations.delete(element);
        animation.onfinish = forget;
        animation.oncancel = forget;
      });
    }, { rootMargin: '0px 0px -20px 0px', threshold: 0 });
    pending.forEach(element => observer.observe(element));
  };

  // Keyboard users never have to wait for a focused link to finish appearing.
  document.addEventListener('focusin', event => {
    animations.forEach((animation, element) => {
      if (element.contains(event.target)) animation.cancel();
    });
  });
  const updatePreference = () => motionPreference.matches ? stop() : start();
  if (typeof motionPreference.addEventListener === 'function') {
    motionPreference.addEventListener('change', updatePreference);
  } else if (typeof motionPreference.addListener === 'function') {
    motionPreference.addListener(updatePreference);
  }
  start();
})();
