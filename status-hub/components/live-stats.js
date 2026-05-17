/**
 * @file components/live-stats.js
 * @description <live-stats> - displays streams and bandwidth with progress bar
 * @deploy ./deploy.sh
 */

class LiveStats extends HTMLElement {
  constructor() {
    super();
    this.maxBandwidth = 40;
  }

  connectedCallback() {
    this.render();
    this.fetchStats();
    setInterval(() => this.fetchStats(), 10000);
  }

  async fetchStats() {
    try {
      const res = await fetch(`${window.location.origin}/api/tautulli-stats`);
      if (!res.ok) return;
      const data = await res.json();
      this.update(data.activeStreams || 0, data.bandwidth || 0);
    } catch {
      // Silent fail
    }
  }

  update(streams, bandwidth) {
    const el = (sel) => this.querySelector(sel);
    const pct = Math.min(100, Math.round((bandwidth / this.maxBandwidth) * 100));
    
    if (el('.streams-value')) el('.streams-value').textContent = streams;
    if (el('.bw-value')) el('.bw-value').textContent = bandwidth.toFixed(1);
    if (el('.bw-pct')) el('.bw-pct').textContent = `${pct}%`;
    
    const bar = el('.bw-bar-fill');
    if (bar) {
      bar.style.width = `${pct}%`;
      bar.style.background = pct > 80 ? '#ef4444' : pct > 50 ? '#eab308' : '#22c55e';
    }
  }

  render() {
    this.innerHTML = `
      <div class="live-stats">
        <div class="stat-block">
          <span class="streams-value">0</span>
          <span class="stat-label">Streams</span>
        </div>
        <div class="stat-divider"></div>
        <div class="stat-block bw-block">
          <div class="bw-row">
            <span class="bw-value">0.0</span>
            <span class="bw-unit">/ ${this.maxBandwidth} Mbps</span>
          </div>
          <div class="bw-bar">
            <div class="bw-bar-fill"></div>
          </div>
          <span class="bw-pct">0%</span>
        </div>
      </div>
      <style>
        .live-stats {
          display: flex;
          align-items: center;
          gap: 1rem;
          background: #12121a;
          border: 1px solid rgba(255,255,255,0.08);
          border-radius: 0.5rem;
          padding: 0.75rem 1rem;
        }
        .stat-block {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.25rem;
        }
        .streams-value {
          font-size: 1.75rem;
          font-weight: 700;
          color: #22c55e;
          line-height: 1;
        }
        .stat-label {
          font-size: 0.65rem;
          color: rgba(255,255,255,0.5);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .stat-divider {
          width: 1px;
          height: 40px;
          background: rgba(255,255,255,0.1);
        }
        .bw-block {
          align-items: flex-start;
          min-width: 120px;
        }
        .bw-row {
          display: flex;
          align-items: baseline;
          gap: 0.25rem;
        }
        .bw-value {
          font-size: 1.25rem;
          font-weight: 600;
          color: white;
        }
        .bw-unit {
          font-size: 0.7rem;
          color: rgba(255,255,255,0.4);
        }
        .bw-bar {
          width: 100%;
          height: 6px;
          background: rgba(255,255,255,0.1);
          border-radius: 3px;
          overflow: hidden;
          margin-top: 0.35rem;
        }
        .bw-bar-fill {
          height: 100%;
          width: 0%;
          background: #22c55e;
          border-radius: 3px;
          transition: width 0.5s ease, background 0.3s ease;
        }
        .bw-pct {
          font-size: 0.65rem;
          color: rgba(255,255,255,0.5);
          margin-top: 0.2rem;
        }
      </style>
    `;
  }
}

customElements.define('live-stats', LiveStats);
