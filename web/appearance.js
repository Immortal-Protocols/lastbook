'use strict';
/* Shared by the library and setup/manage pages; runs before CSS to avoid a theme flash. */
const Appearance = (() => {
  const system = matchMedia('(prefers-color-scheme: dark)');
  const valid = choice => ['system', 'light', 'dark'].includes(choice);
  function controls(root = document) {
    root.querySelectorAll('[data-appearance]').forEach(el => { el.value = document.documentElement.dataset.appearance || 'system' });
  }
  function apply(choice) {
    if (!valid(choice)) choice = 'system';
    const html = document.documentElement;
    html.dataset.appearance = choice;
    html.dataset.theme = choice === 'system' ? (system.matches ? 'dark' : 'light') : choice;
    document.querySelectorAll('meta[name="theme-color"]').forEach(el => { el.content = html.dataset.theme === 'dark' ? '#1e1e1f' : '#ffffff' });
    controls();
  }
  let choice = 'system';
  try { choice = localStorage.getItem('sg.theme') || 'system' } catch { }
  apply(choice);
  system.addEventListener('change', () => {
    if (document.documentElement.dataset.appearance === 'system') apply('system');
  });
  return { apply, controls };
})();
