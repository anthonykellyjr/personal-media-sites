/**
 * @file components/announcement-banner.js
 * @description <announcement-banner> - displays dismissible status announcements
 * @deploy ./deploy.sh
 */

class AnnouncementBanner extends HTMLElement {
  connectedCallback() {
    this.fetchAnnouncement();
    setInterval(() => this.fetchAnnouncement(), 60000);
  }

  async fetchAnnouncement() {
    try {
      const res = await fetch(`${window.location.origin}/api/announcement`);
      if (!res.ok) { this.innerHTML = ''; return; }
      const data = await res.json();
      if (data.enabled && data.message) {
        this.render(data);
      } else {
        this.innerHTML = '';
      }
    } catch {
      this.innerHTML = '';
    }
  }

  render(data) {
    const colors = {
      red: 'background: linear-gradient(135deg, #7f1d1d, #991b1b); border-color: #dc2626;',
      yellow: 'background: linear-gradient(135deg, #78350f, #92400e); border-color: #f59e0b;',
      green: 'background: linear-gradient(135deg, #14532d, #166534); border-color: #22c55e;',
      info: 'background: linear-gradient(135deg, #1e3a8a, #1e40af); border-color: #3b82f6;'
    };
    const icons = { red: '⚠️', yellow: '⚡', green: '✅', info: 'ℹ️' };
    const style = colors[data.severity] || colors.info;
    const icon = icons[data.severity] || icons.info;

    this.innerHTML = `
      <div style="${style} display:flex; align-items:center; justify-content:space-between; padding:0.75rem 1rem; border:1px solid; border-radius:0.75rem; margin-bottom:1rem;">
        <div style="display:flex; align-items:center; gap:0.75rem;">
          <span>${icon}</span>
          <p style="margin:0; font-size:0.875rem;">${data.message}</p>
        </div>
        ${data.dismissible ? '<button onclick="this.parentElement.remove()" style="background:rgba(255,255,255,0.1); border:none; color:white; width:28px; height:28px; border-radius:50%; cursor:pointer;">✕</button>' : ''}
      </div>
    `;
  }
}

customElements.define('announcement-banner', AnnouncementBanner);
