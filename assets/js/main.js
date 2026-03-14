/**
 * Main JS — bootstrap, scroll, dropdowns, FAQ, command tabs
 */
(function () {
  window.API_BASE = window.location.hostname === 'localhost'
    ? 'http://localhost:8099'
    : 'https://htchserver.tail21b05e.ts.net';

  document.addEventListener('DOMContentLoaded', async () => {
    if (window.i18nInit) await window.i18nInit();
    if (window.particlesInit) window.particlesInit();
    if (window.counterInit) window.counterInit();
    if (window.statsInit) window.statsInit();

    // Scroll reveal
    const obs = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          setTimeout(() => e.target.classList.add('visible'), e.target.dataset.delay || 0);
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.1 });
    document.querySelectorAll('.reveal, .reveal-stagger').forEach((el, i) => {
      if (el.classList.contains('reveal-stagger')) el.dataset.delay = i * 60;
      obs.observe(el);
    });

    // Dropdowns
    document.querySelectorAll('.nav-dropdown-btn').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        const dd = btn.closest('.nav-dropdown');
        document.querySelectorAll('.nav-dropdown.open').forEach(d => { if (d !== dd) d.classList.remove('open'); });
        dd.classList.toggle('open');
      });
    });
    document.addEventListener('click', () => { document.querySelectorAll('.nav-dropdown.open').forEach(d => d.classList.remove('open')); });
    document.querySelectorAll('[data-theme-value]').forEach(el => {
      el.addEventListener('click', () => { window.setTheme(el.dataset.themeValue); el.closest('.nav-dropdown').classList.remove('open'); });
    });
    document.querySelectorAll('[data-lang-value]').forEach(el => {
      el.addEventListener('click', () => { window.setLang(el.dataset.langValue); el.closest('.nav-dropdown').classList.remove('open'); });
    });

    // Mobile menu
    const mt = document.getElementById('mobile-toggle');
    const nl = document.getElementById('nav-links');
    if (mt && nl) mt.addEventListener('click', () => nl.classList.toggle('open'));

    // FAQ
    document.querySelectorAll('.faq-question').forEach(q => {
      q.addEventListener('click', () => q.closest('.faq-item').classList.toggle('open'));
    });

    // Command tabs
    document.querySelectorAll('.command-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.command-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.command-panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        const panel = document.getElementById(tab.dataset.panel);
        if (panel) panel.classList.add('active');
      });
    });
  });
})();
