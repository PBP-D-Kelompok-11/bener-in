(() => {
  'use strict';
  const nav = document.querySelector('[data-navigation]');
  if (!nav || nav.hasAttribute('data-enhanced')) return;
  const toggle = nav.querySelector('[data-nav-toggle]');
  const panel = nav.querySelector('[data-nav-panel]');
  const mobile = window.matchMedia('(max-width: 900px)');
  let open = false;

  function render() {
    toggle.hidden = !mobile.matches;
    panel.hidden = mobile.matches && !open;
    toggle.setAttribute('aria-expanded', String(mobile.matches && open));
    toggle.setAttribute('aria-label', open ? 'Tutup menu navigasi' : 'Buka menu navigasi');
  }
  function close(restoreFocus = false) {
    open = false;
    render();
    if (restoreFocus) toggle.focus();
  }
  toggle.addEventListener('click', () => { open = !open; render(); });
  nav.addEventListener('keydown', event => {
    if (event.key === 'Escape' && mobile.matches && open) {
      event.preventDefault();
      close(true);
    }
  });
  panel.addEventListener('click', event => {
    if (mobile.matches && event.target.closest('a')) close();
  });
  document.addEventListener('click', event => {
    if (open && !nav.contains(event.target)) close();
  });
  document.addEventListener('focusin', event => {
    if (open && !nav.contains(event.target)) close();
  });
  mobile.addEventListener('change', () => { open = false; render(); });
  nav.setAttribute('data-enhanced', '');
  render();
})();
