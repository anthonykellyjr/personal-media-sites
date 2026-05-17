/**
 * @file components/service-card.js
 * @description <service-card> - horizontal card with image left, title right
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
      <div class="service-card">
        <a href="${href}" target="_blank" class="card-link">
          <img src="${icon}" alt="${name}" class="card-icon">
          <span class="card-name">${name}</span>
        </a>
        <a href="${href}" target="_blank" class="card-popout" title="Open in new tab">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/>
          </svg>
        </a>
      </div>
      <style>
        service-card .service-card {
          display: flex;
          align-items: center;
          background: #12121a;
          border: 1px solid rgba(255,255,255,0.06);
          border-radius: 0.75rem;
          overflow: hidden;
          transition: all 0.2s;
          position: relative;
        }
        service-card .service-card:hover {
          border-color: rgba(255,255,255,0.12);
          background: #1a1a24;
        }
        service-card .card-link {
          display: flex;
          align-items: center;
          gap: 1rem;
          padding: 0.75rem 1rem;
          text-decoration: none;
          color: white;
          flex: 1;
        }
        service-card .card-icon {
          width: 64px;
          height: 64px;
          border-radius: 0.5rem;
          object-fit: cover;
          flex-shrink: 0;
        }
        service-card .card-name {
          font-size: 1rem;
          font-weight: 600;
          flex: 1;
        }
        service-card .card-popout {
          position: absolute;
          top: 0.5rem;
          right: 0.5rem;
          padding: 0.375rem;
          color: rgba(255,255,255,0.3);
          border-radius: 0.25rem;
          transition: all 0.2s;
        }
        service-card .card-popout:hover {
          color: rgba(255,255,255,0.7);
          background: rgba(255,255,255,0.1);
        }
      </style>
    `;
  }
}

customElements.define('service-card', ServiceCard);
