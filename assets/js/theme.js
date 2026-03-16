/**
 * AutoQuest Theme Engine
 * Manages both Light/Dark modes and Emerald/Amethyst color themes
 */
(function() {
    const THEME_KEY = 'aq_theme';
    const COLOR_KEY = 'aq_color';
    const DEFAULT_THEME = 'dark';
    const DEFAULT_COLOR = 'emerald';

    function getSystemTheme() {
        return window.matchMedia('(prefers-color-scheme:light)').matches ? 'light' : 'dark';
    }

    function applyTheme(theme) {
        const actualTheme = theme === 'system' ? getSystemTheme() : theme;
        document.documentElement.setAttribute('data-theme', actualTheme);
        
        // Update UI active states
        document.querySelectorAll('[data-theme-value]').forEach(el => {
            el.classList.toggle('active', el.dataset.themeValue === theme);
        });

        // Update dropdown labels
        const labels = document.querySelectorAll('#settings-btn .dd-label');
        labels.forEach(lb => {
            // Only update if it contains "Theme" or "Mode" in any language
            // Better to rely on the active class for visual feedback in a unified menu
        });
    }

    function applyColor(color) {
        document.documentElement.setAttribute('data-color', color);
        
        // Update UI active states
        document.querySelectorAll('[data-color-value]').forEach(el => {
            el.classList.toggle('active', el.dataset.colorValue === color);
        });
    }

    async function setTheme(theme) {
        localStorage.setItem(THEME_KEY, theme);
        document.body.classList.add('setting-switching');
        await new Promise(r => setTimeout(r, 600));
        applyTheme(theme);
        requestAnimationFrame(() => {
            document.body.classList.remove('setting-switching');
        });
    }

    async function setColor(color) {
        localStorage.setItem(COLOR_KEY, color);
        document.body.classList.add('setting-switching');
        await new Promise(r => setTimeout(r, 600));
        applyColor(color);
        requestAnimationFrame(() => {
            document.body.classList.remove('setting-switching');
        });
    }

    // Initialize
    const savedTheme = localStorage.getItem(THEME_KEY) || DEFAULT_THEME;
    const savedColor = localStorage.getItem(COLOR_KEY) || DEFAULT_COLOR;
    
    applyTheme(savedTheme);
    applyColor(savedColor);

    // System theme listener
    window.matchMedia('(prefers-color-scheme:light)').addEventListener('change', () => {
        if (localStorage.getItem(THEME_KEY) === 'system') {
            applyTheme('system');
        }
    });

    // Exports
    window.setTheme = setTheme;
    window.setColor = setColor;
})();
