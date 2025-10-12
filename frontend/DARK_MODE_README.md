# Dark Mode Implementation

## Overview
The application now supports a beautiful dark mode theme that is easy on the eyes, especially for medical professionals working during night shifts or in low-light environments.

## Features

### 🌓 Theme Toggle
- **Location**: A theme toggle button (☀️/🌙) is automatically added to the header of all pages
- **Quick Switch**: Click the button to instantly toggle between light and dark modes
- **Smooth Transition**: All color changes are animated with smooth transitions

### 💾 User Preference Memory
- Your theme preference is automatically saved to localStorage
- The selected theme persists across page reloads and browser sessions
- Works independently for each browser/device

### 🖥️ System Theme Support
- Optionally follows your operating system's theme preference
- Automatically switches when you change your system theme
- Perfect for users who prefer automatic theme switching

### 📱 Full Coverage
All pages support dark mode:
- Main chat interface (`index.html`)
- Tools page (`tools.html`)
- Shared conversation page (`share.html`)

## Technical Details

### CSS Variables
The implementation uses CSS custom properties (variables) for easy theme management:
- Light theme: Default color scheme with clean whites and grays
- Dark theme: Carefully selected colors with proper contrast ratios
- Smooth transitions between themes (0.3s ease)

### Color Palette

**Light Mode:**
- Primary Background: `#f8fafc`
- Secondary Background: `#ffffff`
- Primary Text: `#2d3748`
- Brand Color: `#4299e1`

**Dark Mode:**
- Primary Background: `#1a202c`
- Secondary Background: `#2d3748`
- Primary Text: `#f7fafc`
- Brand Color: `#63b3ed` (slightly brighter for better visibility)

### Accessibility
- WCAG 2.1 AA compliant color contrast ratios
- Optimized for reduced eye strain during extended use
- Smooth animations that respect user preferences

## Files Modified
- `frontend/js/theme-manager.js` - New theme management system
- `frontend/css/style.css` - CSS variables and dark mode styles
- `frontend/css/tools.css` - Tools page dark mode support
- `frontend/index.html` - Theme manager integration
- `frontend/tools.html` - Theme manager integration
- `frontend/share.html` - Theme manager integration

## Browser Support
- Chrome/Edge 88+
- Firefox 85+
- Safari 14+
- Opera 75+

## Future Enhancements
Potential improvements for future versions:
- Additional theme options (e.g., sepia, high contrast)
- Per-page theme preferences
- Scheduled theme switching (e.g., auto-dark after 8 PM)
- Custom color scheme builder

