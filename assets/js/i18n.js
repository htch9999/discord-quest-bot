/**
 * i18n — Multi-language engine (VI / EN / JA)
 */
(function () {
  const KEY = 'lang';
  const SUPPORTED = ['vi', 'en', 'ja'];
  const FALLBACK = 'en';
  const DEFAULT = 'vi';
  let locales = {};
  let currentLang = DEFAULT;

  function detectLang() {
    const saved = localStorage.getItem(KEY);
    if (saved && SUPPORTED.includes(saved)) return saved;
    const urlParam = new URLSearchParams(window.location.search).get('lang');
    if (urlParam && SUPPORTED.includes(urlParam)) return urlParam;
    const browserLang = navigator.language.slice(0, 2);
    if (SUPPORTED.includes(browserLang)) return browserLang;
    return DEFAULT;
  }

  function get(obj, path) {
    return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : null), obj);
  }

  function t(key) {
    return get(locales[currentLang], key) || get(locales[FALLBACK], key) || key;
  }

  function apply() {
    document.querySelectorAll('[data-i18n]').forEach(el => { el.innerHTML = t(el.dataset.i18n); });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
    document.querySelectorAll('[data-i18n-aria]').forEach(el => { el.setAttribute('aria-label', t(el.dataset.i18nAria)); });
    const desc = t('meta.description');
    if (desc !== 'meta.description') { const m = document.querySelector('meta[name="description"]'); if (m) m.setAttribute('content', desc); }
    document.documentElement.lang = currentLang;
    document.querySelectorAll('[data-lang-value]').forEach(el => { el.classList.toggle('active', el.dataset.langValue === currentLang); });
  }

  async function load(lang) {
    if (locales[lang]) return;
    try { const r = await fetch(`assets/locales/${lang}.json`); locales[lang] = await r.json(); }
    catch (e) { locales[lang] = {}; }
  }

  async function setLang(lang) {
    if (!SUPPORTED.includes(lang)) return;
    currentLang = lang;
    localStorage.setItem(KEY, lang);
    document.body.classList.add('setting-switching');
    await new Promise(r => setTimeout(r, 600));
    await load(lang);
    if (lang !== FALLBACK) await load(FALLBACK);
    apply();
    // Allow DOM to update before removing class so fade-in triggers
    requestAnimationFrame(() => {
        document.body.classList.remove('setting-switching');
    });
  }

  async function init() {
    const lang = detectLang();
    await load(lang);
    if (lang !== FALLBACK) await load(FALLBACK);
    currentLang = lang;
    apply();
  }

  window.setLang = setLang;
  window.i18nInit = init;
  window.t = t;
})();
