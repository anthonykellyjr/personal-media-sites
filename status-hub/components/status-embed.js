/**
 * @file components/status-embed.js
 * @description <status-embed> - embeds Uptime Kuma status page
 * @deploy ./deploy.sh
 */

class StatusEmbed extends HTMLElement {
  static get observedAttributes() { return ['src', 'title']; }
  attributeChangedCallback() { this.render(); }
  connectedCallback() { this.render(); }

  render() {
    const src = this.getAttribute('src') || '';
    const title = this.getAttribute('title') || 'Status';

    this.innerHTML = `
      <section style="margin-bottom:1.5rem;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.5rem;">
          <h2 style="font-size:0.75rem; font-weight:600; color:rgba(255,255,255,0.3); text-transform:uppercase; letter-spacing:0.05em;">${title}</h2>
          <a href="${src}" target="_blank" style="display:flex; align-items:center; gap:0.375rem; font-size:0.75rem; color:rgba(255,255,255,0.3); text-decoration:none;">
            Open full page
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/>
            </svg>
          </a>
        </div>
        <div style="background:#12121a; border:1px solid rgba(255,255,255,0.06); border-radius:0.75rem; overflow:hidden; height:350px;">
          <iframe src="${src}" title="${title}" style="width:100%; height:100%; border:none;"></iframe>
        </div>
      </section>
    `;
  }
}

customElements.define('status-embed', StatusEmbed);
