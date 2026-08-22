// theme.js - Global Theme Toggle Logic
document.addEventListener('DOMContentLoaded', () => {
    const themeBtn = document.getElementById('theme-toggle');
    if (!themeBtn) return;

    // Set initial icon visibility based on data-theme which is already set by inline script
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    
    // Toggle logic
    themeBtn.addEventListener('click', () => {
        const root = document.documentElement;
        const newTheme = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        
        // Update DOM
        root.setAttribute('data-theme', newTheme);
        
        // Save to localStorage
        localStorage.setItem('rakshak-theme', newTheme);
        
        // Dispatch event in case charts or maps need to redraw based on theme
        window.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: newTheme } }));
    });
});
