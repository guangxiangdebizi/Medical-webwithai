// theme-manager.js - 主题管理器
class ThemeManager {
    constructor() {
        this.currentTheme = null;
        this.THEME_KEY = 'app-theme-preference';
        this.THEMES = {
            LIGHT: 'light',
            DARK: 'dark',
            AUTO: 'auto'
        };
    }

    /**
     * 初始化主题
     */
    init() {
        // 读取用户偏好
        const savedTheme = this.getSavedTheme();
        
        // 应用主题
        if (savedTheme === this.THEMES.AUTO) {
            this.applySystemTheme();
            // 监听系统主题变化
            this.watchSystemTheme();
        } else {
            this.applyTheme(savedTheme || this.THEMES.LIGHT);
        }
        
        console.log('✅ Theme Manager initialized, current theme:', this.currentTheme);
    }

    /**
     * 获取保存的主题偏好
     */
    getSavedTheme() {
        try {
            return localStorage.getItem(this.THEME_KEY) || null;
        } catch (e) {
            console.warn('Failed to read theme preference from localStorage:', e);
            return null;
        }
    }

    /**
     * 保存主题偏好
     */
    saveTheme(theme) {
        try {
            localStorage.setItem(this.THEME_KEY, theme);
        } catch (e) {
            console.warn('Failed to save theme preference to localStorage:', e);
        }
    }

    /**
     * 应用主题
     */
    applyTheme(theme) {
        const root = document.documentElement;
        
        // 移除所有主题类
        root.classList.remove('theme-light', 'theme-dark');
        
        // 添加新主题类
        if (theme === this.THEMES.DARK) {
            root.classList.add('theme-dark');
            this.currentTheme = this.THEMES.DARK;
        } else {
            root.classList.add('theme-light');
            this.currentTheme = this.THEMES.LIGHT;
        }
        
        // 更新meta标签（移动端地址栏颜色）
        this.updateMetaThemeColor();
        
        console.log('🎨 Theme applied:', this.currentTheme);
    }

    /**
     * 应用系统主题
     */
    applySystemTheme() {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        this.applyTheme(prefersDark ? this.THEMES.DARK : this.THEMES.LIGHT);
    }

    /**
     * 监听系统主题变化
     */
    watchSystemTheme() {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        
        // 使用 addEventListener 替代已废弃的 addListener
        mediaQuery.addEventListener('change', (e) => {
            const savedTheme = this.getSavedTheme();
            if (savedTheme === this.THEMES.AUTO) {
                this.applyTheme(e.matches ? this.THEMES.DARK : this.THEMES.LIGHT);
            }
        });
    }

    /**
     * 切换主题
     */
    toggleTheme() {
        const newTheme = this.currentTheme === this.THEMES.LIGHT 
            ? this.THEMES.DARK 
            : this.THEMES.LIGHT;
        
        this.setTheme(newTheme);
    }

    /**
     * 设置主题（保存偏好）
     */
    setTheme(theme) {
        this.saveTheme(theme);
        
        if (theme === this.THEMES.AUTO) {
            this.applySystemTheme();
        } else {
            this.applyTheme(theme);
        }
    }

    /**
     * 获取当前主题
     */
    getCurrentTheme() {
        return this.currentTheme;
    }

    /**
     * 更新meta主题颜色（移动端）
     */
    updateMetaThemeColor() {
        let metaTheme = document.querySelector('meta[name="theme-color"]');
        
        if (!metaTheme) {
            metaTheme = document.createElement('meta');
            metaTheme.name = 'theme-color';
            document.head.appendChild(metaTheme);
        }
        
        // 根据主题设置颜色
        const color = this.currentTheme === this.THEMES.DARK ? '#1a202c' : '#ffffff';
        metaTheme.content = color;
    }

    /**
     * 创建主题切换按钮
     */
    createThemeToggleButton() {
        const button = document.createElement('button');
        button.id = 'themeToggleBtn';
        button.className = 'btn btn-secondary theme-toggle-btn';
        button.title = 'Toggle theme';
        button.setAttribute('aria-label', 'Toggle dark mode');
        
        this.updateButtonIcon(button);
        
        button.addEventListener('click', () => {
            this.toggleTheme();
            this.updateButtonIcon(button);
        });
        
        return button;
    }

    /**
     * 更新按钮图标
     */
    updateButtonIcon(button) {
        if (!button) return;
        
        if (this.currentTheme === this.THEMES.DARK) {
            button.innerHTML = '🌙';
            button.title = 'Switch to light mode';
        } else {
            button.innerHTML = '☀️';
            button.title = 'Switch to dark mode';
        }
    }

    /**
     * 添加主题切换按钮到页面
     */
    addToggleButtonToPage() {
        // 查找header-actions容器
        const headerActions = document.querySelector('.header-actions');
        
        if (!headerActions) {
            console.warn('Header actions container not found');
            return;
        }
        
        // 检查是否已存在
        if (document.getElementById('themeToggleBtn')) {
            return;
        }
        
        // 创建并添加按钮
        const button = this.createThemeToggleButton();
        
        // 插入到第一个位置（最左边）
        headerActions.insertBefore(button, headerActions.firstChild);
        
        console.log('✅ Theme toggle button added to page');
    }
}

// 创建全局主题管理器实例
window.themeManager = new ThemeManager();

// DOM加载完成后初始化
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.themeManager.init();
        window.themeManager.addToggleButtonToPage();
    });
} else {
    // 如果DOM已经加载完成
    window.themeManager.init();
    window.themeManager.addToggleButtonToPage();
}

