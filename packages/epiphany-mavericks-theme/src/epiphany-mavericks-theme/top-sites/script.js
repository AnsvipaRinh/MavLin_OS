// Top Sites Page - Safari 7 Style Interactions

(function() {
    'use strict';

    // Default top sites (fallback if no history)
    const DEFAULT_SITES = [
        { title: 'Apple', url: 'https://www.apple.com', icon: 'https://www.apple.com/favicon.ico' },
        { title: 'GitHub', url: 'https://github.com', icon: 'https://github.githubassets.com/favicon.ico' },
        { title: 'Arch Linux', url: 'https://archlinux.org', icon: 'https://archlinux.org/static/favicon.29302f683ff8.ico' },
        { title: 'MDN Web Docs', url: 'https://developer.mozilla.org', icon: 'https://developer.mozilla.org/favicon-32x32.png' },
        { title: 'Wikipedia', url: 'https://wikipedia.org', icon: 'https://wikipedia.org/static/favicon/wikipedia.ico' },
        { title: 'YouTube', url: 'https://youtube.com', icon: 'https://www.youtube.com/s/desktop/9c3b4b6f/img/favicon_32.png' },
        { title: 'Reddit', url: 'https://reddit.com', icon: 'https://www.redditstatic.com/desktop2x/img/favicon/favicon-32x32.png' },
        { title: 'Stack Overflow', url: 'https://stackoverflow.com', icon: 'https://cdn.sstatic.net/Sites/stackoverflow/Img/favicon.ico' }
    ];

    // DOM elements
    const sitesGrid = document.getElementById('sitesGrid');
    const addSiteBtn = document.getElementById('addSiteBtn');
    const urlInput = document.querySelector('.url-input');

    // State
    let sites = [...DEFAULT_SITES];
    let isEditing = false;

    // Initialize
    function init() {
        loadSites();
        renderSites();
        setupEventListeners();
        setupKeyboardNavigation();
    }

    // Load sites from localStorage (simulating history)
    function loadSites() {
        try {
            const stored = localStorage.getItem('mavericks-top-sites');
            if (stored) {
                const parsed = JSON.parse(stored);
                if (Array.isArray(parsed) && parsed.length > 0) {
                    sites = parsed.slice(0, 12); // Max 12 sites
                }
            }
        } catch (e) {
            console.warn('Failed to load top sites:', e);
        }
    }

    // Save sites to localStorage
    function saveSites() {
        try {
            localStorage.setItem('mavericks-top-sites', JSON.stringify(sites));
        } catch (e) {
            console.warn('Failed to save top sites:', e);
        }
    }

    // Render site cards
    function renderSites() {
        sitesGrid.innerHTML = '';
        
        sites.forEach((site, index) => {
            const card = createSiteCard(site, index);
            sitesGrid.appendChild(card);
        });
        
        // Re-append add button at the end
        if (addSiteBtn.parentNode !== sitesGrid) {
            sitesGrid.appendChild(addSiteBtn);
        }
    }

    // Create site card element
    function createSiteCard(site, index) {
        const card = document.createElement('a');
        card.className = 'site-card';
        card.href = site.url;
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');
        card.setAttribute('aria-label', `Open ${site.title}`);
        card.dataset.index = index;

        // Favicon
        const icon = document.createElement('img');
        icon.className = 'site-icon';
        icon.src = site.icon || `https://www.google.com/s2/favicons?domain=${new URL(site.url).hostname}&sz=64`;
        icon.alt = '';
        icon.loading = 'lazy';
        icon.onerror = function() {
            this.src = `https://www.google.com/s2/favicons?domain=${new URL(site.url).hostname}&sz=64`;
        };

        // Title
        const title = document.createElement('div');
        title.className = 'site-title';
        title.textContent = site.title;

        // URL
        const url = document.createElement('div');
        url.className = 'site-url';
        try {
            url.textContent = new URL(site.url).hostname.replace('www.', '');
        } catch {
            url.textContent = site.url;
        }

        // Delete button (shown on hover/focus)
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.innerHTML = '<svg viewBox="0 0 24 24" width="14" height="14"><line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
        deleteBtn.setAttribute('aria-label', `Remove ${site.title}`);
        deleteBtn.tabIndex = -1;
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            removeSite(index);
        });

        card.appendChild(icon);
        card.appendChild(title);
        card.appendChild(url);
        card.appendChild(deleteBtn);

        // Keyboard support
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault();
                removeSite(index);
            }
        });

        return card;
    }

    // Remove site
    function removeSite(index) {
        sites.splice(index, 1);
        saveSites();
        renderSites();
    }

    // Add new site
    function addSite(title, url) {
        if (sites.length >= 12) {
            alert('Maximum 12 top sites allowed. Remove one first.');
            return;
        }
        
        const newSite = {
            title: title || new URL(url).hostname,
            url: url.startsWith('http') ? url : 'https://' + url,
            icon: `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=64`
        };
        
        sites.unshift(newSite); // Add to beginning
        saveSites();
        renderSites();
    }

    // Setup event listeners
    function setupEventListeners() {
        // Add site button
        addSiteBtn.addEventListener('click', showAddSiteDialog);
        addSiteBtn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                showAddSiteDialog();
            }
        });

        // Address bar - navigate on Enter
        urlInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const value = urlInput.value.trim();
                if (value) {
                    const url = value.startsWith('http') ? value : 'https://' + value;
                    window.location.href = url;
                }
            }
        });

        // Click outside to close dialogs
        document.addEventListener('click', (e) => {
            if (isEditing && !e.target.closest('.add-site-dialog')) {
                hideAddSiteDialog();
            }
        });
    }

    // Show add site dialog
    function showAddSiteDialog() {
        if (isEditing) return;
        isEditing = true;

        const dialog = document.createElement('div');
        dialog.className = 'add-site-dialog';
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-modal', 'true');
        dialog.setAttribute('aria-labelledby', 'add-site-title');
        dialog.innerHTML = `
            <div class="dialog-backdrop"></div>
            <div class="dialog-content">
                <h2 id="add-site-title">Add Top Site</h2>
                <div class="form-group">
                    <label for="site-title">Title</label>
                    <input type="text" id="site-title" placeholder="Site name" autocomplete="off">
                </div>
                <div class="form-group">
                    <label for="site-url">URL</label>
                    <input type="url" id="site-url" placeholder="https://example.com" autocomplete="off">
                </div>
                <div class="dialog-actions">
                    <button class="btn-cancel">Cancel</button>
                    <button class="btn-add" id="btn-add-site">Add</button>
                </div>
            </div>
        `;

        // Add dialog styles
        const style = document.createElement('style');
        style.textContent = `
            .add-site-dialog {
                position: fixed;
                inset: 0;
                z-index: 1000;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .dialog-backdrop {
                position: absolute;
                inset: 0;
                background: rgba(0,0,0,0.4);
                backdrop-filter: blur(4px);
            }
            .dialog-content {
                position: relative;
                background: var(--safari-card-bg);
                border-radius: var(--safari-radius);
                padding: 24px;
                width: 90%;
                max-width: 400px;
                box-shadow: var(--safari-shadow-hover);
                animation: dialog-in 0.2s ease-out;
            }
            @keyframes dialog-in {
                from { opacity: 0; transform: scale(0.95) translateY(10px); }
                to { opacity: 1; transform: scale(1) translateY(0); }
            }
            .dialog-content h2 {
                margin: 0 0 20px;
                font-size: 18px;
                font-weight: 600;
            }
            .form-group {
                margin-bottom: 16px;
            }
            .form-group label {
                display: block;
                font-size: 13px;
                font-weight: 500;
                margin-bottom: 6px;
                color: var(--safari-text);
            }
            .form-group input {
                width: 100%;
                padding: 10px 12px;
                border: 1px solid var(--safari-toolbar-border);
                border-radius: var(--safari-radius-sm);
                font-family: inherit;
                font-size: 14px;
                background: var(--safari-card-bg);
                color: var(--safari-text);
                transition: var(--safari-transition);
            }
            .form-group input:focus {
                outline: none;
                border-color: var(--safari-accent);
                box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.2);
            }
            .dialog-actions {
                display: flex;
                justify-content: flex-end;
                gap: 12px;
                margin-top: 24px;
            }
            .btn-cancel,
            .btn-add {
                padding: 8px 16px;
                border-radius: var(--safari-radius-sm);
                font-family: inherit;
                font-size: 13px;
                font-weight: 500;
                cursor: pointer;
                transition: var(--safari-transition);
            }
            .btn-cancel {
                background: none;
                border: 1px solid var(--safari-toolbar-border);
                color: var(--safari-text);
            }
            .btn-cancel:hover {
                background: rgba(0,0,0,0.05);
            }
            .btn-add {
                background: var(--safari-accent);
                border: none;
                color: white;
            }
            .btn-add:hover {
                background: var(--safari-accent-hover);
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(dialog);

        // Focus title input
        setTimeout(() => {
            document.getElementById('site-title').focus();
        }, 50);

        // Event listeners
        dialog.querySelector('.btn-cancel').addEventListener('click', hideAddSiteDialog);
        dialog.querySelector('.dialog-backdrop').addEventListener('click', hideAddSiteDialog);
        dialog.querySelector('.btn-add').addEventListener('click', () => {
            const title = document.getElementById('site-title').value.trim();
            const url = document.getElementById('site-url').value.trim();
            if (url) {
                addSite(title, url);
                hideAddSiteDialog();
            }
        });

        // Enter key in inputs
        dialog.querySelectorAll('input').forEach(input => {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    const title = document.getElementById('site-title').value.trim();
                    const url = document.getElementById('site-url').value.trim();
                    if (url) {
                        addSite(title, url);
                        hideAddSiteDialog();
                    }
                }
                if (e.key === 'Escape') {
                    hideAddSiteDialog();
                }
            });
        });

        // Escape key
        dialog.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                hideAddSiteDialog();
            }
        });

        function hideAddSiteDialog() {
            isEditing = false;
            dialog.remove();
            style.remove();
        }
    }

    // Keyboard navigation for grid
    function setupKeyboardNavigation() {
        let currentIndex = -1;
        const cards = () => Array.from(sitesGrid.querySelectorAll('.site-card'));

        document.addEventListener('keydown', (e) => {
            const cardList = cards();
            if (cardList.length === 0) return;

            // Only handle if focus is in the grid or on add button
            const active = document.activeElement;
            const isInGrid = active.closest('.site-card') || active === addSiteBtn;

            if (!isInGrid) return;

            let newIndex = currentIndex;

            switch (e.key) {
                case 'ArrowRight':
                    e.preventDefault();
                    newIndex = (currentIndex + 1) % (cardList.length + 1); // +1 for add button
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    newIndex = (currentIndex - 1 + cardList.length + 1) % (cardList.length + 1);
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    newIndex = Math.min(currentIndex + 4, cardList.length);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    newIndex = Math.max(currentIndex - 4, -1);
                    break;
                case 'Home':
                    e.preventDefault();
                    newIndex = 0;
                    break;
                case 'End':
                    e.preventDefault();
                    newIndex = cardList.length;
                    break;
                default:
                    return;
            }

            if (newIndex !== currentIndex) {
                currentIndex = newIndex;
                const target = currentIndex === cardList.length ? addSiteBtn : cardList[currentIndex];
                target.focus();
            }
        });

        // Track current index on focus
        sitesGrid.addEventListener('focusin', (e) => {
            const card = e.target.closest('.site-card');
            if (card) {
                currentIndex = Array.from(cards()).indexOf(card);
            } else if (e.target === addSiteBtn) {
                currentIndex = cards().length;
            }
        });
    }

    // Initialize when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();