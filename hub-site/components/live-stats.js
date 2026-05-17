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
    
    if (el('.streams')) el('.streams').textContent = streams;
    if (el('.bw')) el('.bw').textContent = bandwidth.toFixed(1);
    if (el('.pct')) el('.pct').textContent = `(${pct}%)`;
    
    const bar = el('.bar-fill');
    if (bar) {
      bar.style.width = `${pct}%`;
      bar.style.background = pct > 80 ? '#ef4444' : pct > 50 ? '#eab308' : '#22c55e';
    }
  }

  render() {
    this.innerHTML = `
      <div style="display:flex; align-items:center; gap:1rem; padding:0.5rem 0.75rem; background:#12121a; border:1px solid rgba(255,255,255,0.06); border-radius:0.75rem; font-size:0.875rem;">
        <div style="display:flex; align-items:baseline; gap:0.375rem;">
          <span class="streams" style="font-size:1.25rem; font-weight:700; color:#22c55e;">0</span>
          <span style="color:rgba(255,255,255,0.5); font-size:0.75rem;">STREAMS</span>
        </div>
        <div style="width:1px; height:24px; background:rgba(255,255,255,0.06);"></div>
        <div style="display:flex; flex-direction:column; gap:0.25rem;">
          <div style="display:flex; align-items:baseline; gap:0.25rem;">
            <span class="bw" style="font-weight:600;">0.0</span>
            <span style="color:rgba(255,255,255,0.3); font-size:0.75rem;">/ ${this.maxBandwidth} Mbps</span>
            <span class="pct" style="color:rgba(255,255,255,0.5); font-size:0.75rem;">(0%)</span>
          </div>
          <div style="width:80px; height:4px; background:rgba(255,255,255,0.1); border-radius:2px; overflow:hidden;">
            <div class="bar-fill" style="height:100%; width:0%; background:#22c55e; transition:width 0.5s, background 0.3s;"></div>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('live-stats', LiveStats);
