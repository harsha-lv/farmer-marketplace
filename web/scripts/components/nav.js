/* =====================================================================
   MittiMandi Shared Component: Navigation (Header & Bottom Dock)
   CSP-Safe: uses declarative data-action and data-screen attributes
   ===================================================================== */

export function renderHeaderNav({
  title = 'MittiMandi',
  subtitle = 'Direct Agri Network',
  showBack = false,
  isOnline = true
} = {}) {
  return `
    <div class="header-left">
      ${showBack ? `
        <button type="button" class="icon-btn header-back-btn" data-action="back" aria-label="Go Back" title="Go Back">
          <span>←</span>
        </button>
      ` : ''}
      <div class="header-title-box">
        <span class="header-screen-title" id="header-title">${title}</span>
        <span class="header-subtitle" id="header-subtitle">${subtitle}</span>
      </div>
    </div>
    <div class="header-right">
      <button type="button" class="icon-btn" data-action="nav" data-screen="offline-sync" aria-label="Network & Sync Status" title="Network & Sync Status">
        <span class="net-icon" id="header-net-icon">${isOnline ? '📶' : '✈️'}</span>
      </button>
      <button type="button" class="icon-btn" data-action="nav" data-screen="dashboard" aria-label="Go to Home Dashboard" title="Home">
        <span>🏠</span>
      </button>
    </div>
  `;
}

export function renderBottomDock({
  activeTab = 'home'
} = {}) {
  const dockItems = [
    { id: 'home', icon: '🏠', label: 'Home', screen: 'dashboard' },
    { id: 'lots', icon: '🌾', label: 'Produce', screen: 'lots-list' },
    { id: 'market', icon: '📈', label: 'Mandi AI', screen: 'market-intel' },
    { id: 'trades', icon: '🤝', label: 'Trades', screen: 'trades-negotiate' },
    { id: 'logistics', icon: '🚚', label: 'Transit', screen: 'transport' }
  ];

  return dockItems.map(item => `
    <button type="button" class="dock-item ${item.id === activeTab ? 'active' : ''}" data-action="nav" data-screen="${item.screen}" aria-label="${item.label}">
      <span class="dock-icon" aria-hidden="true">${item.icon}</span>
      <span class="dock-label">${item.label}</span>
    </button>
  `).join('');
}
