/**
 * @file components/service-card.js
 * @description <service-card> - compact card with icon and title
 * @deploy ./deploy.sh
 */

class ServiceCard extends HTMLElement {
  static get observedAttributes() { return ['name', 'href', 'icon']; }
  attributeChangedCallback() { this.render(); }
  connectedCallback() { this.render(); }

  render() {
    const name = this.getAttribute('name') || '';
    const href = this.getAttribute('href') || '#';
    const icon = this.getAttribute('icon') || '';

    this.innerHTML = `
      <a href="${href}" target="_blank" style="display:flex; flex-direction:column; align-items:center; gap:0.625rem; padding:1rem; background:#12121a; border:1px solid rgba(255,255,255,0.06); border-radius:0.75rem; text-decoration:none; color:white; transition:all 0.2s;">
        <img src="${icon}" alt="${name}" style="width:48px; height:48px; border-radius:0.5rem; object-fit:cover;">
        <span style="font-size:0.875rem; font-weight:600; text-align:center;">${name}</span>
      </a>
      <style>
        service-card a:hover {
          border-color: rgba(255,255,255,0.12);
          background: #1a1a24;
        }
      </style>
    `;
  }
}

customElements.define('service-card', ServiceCard);
