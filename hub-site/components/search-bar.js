/**
 * @file components/search-bar.js
 * @description <search-bar> - searches Plex library via Tautulli API
 * @deploy ./deploy.sh
 */

class SearchBar extends HTMLElement {
  constructor() {
    super();
    this.results = [];
    this.timeout = null;
    this.tautulli = 'https://tautulli.akplex.tv';
  }

  connectedCallback() {
    this.render();
    const input = this.querySelector('input');
    input.addEventListener('input', (e) => this.handleInput(e.target.value));
    input.addEventListener('focus', () => this.showDropdown());
    input.addEventListener('blur', () => setTimeout(() => this.hideDropdown(), 200));
  }

  handleInput(q) {
    const query = q.trim();
    this.querySelector('.clear').classList.toggle('hidden', !query);
    if (!query) { this.results = []; this.updateDropdown(); return; }
    clearTimeout(this.timeout);
    this.timeout = setTimeout(() => this.search(query), 300);
  }

  async search(query) {
    this.showLoading();
    try {
      const res = await fetch(`${window.location.origin}/api/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      this.results = data.results || [];
    } catch {
      this.results = [];
    }
    this.updateDropdown();
  }

  showLoading() {
    const dd = this.querySelector('.dropdown');
    dd.innerHTML = '<div style="padding:1.5rem; text-align:center; color:rgba(255,255,255,0.5);">Searching...</div>';
    dd.classList.remove('hidden');
  }

  showDropdown() {
    if (this.results.length) this.querySelector('.dropdown').classList.remove('hidden');
  }

  hideDropdown() {
    this.querySelector('.dropdown').classList.add('hidden');
  }

  clear() {
    this.querySelector('input').value = '';
    this.results = [];
    this.updateDropdown();
    this.querySelector('.clear').classList.add('hidden');
  }

  updateDropdown() {
    const dd = this.querySelector('.dropdown');
    const input = this.querySelector('input');
    
    if (!this.results.length && input.value.trim()) {
      dd.innerHTML = '<div style="padding:1.5rem; text-align:center; color:rgba(255,255,255,0.5);">No results</div>';
      dd.classList.remove('hidden');
      return;
    }
    
    if (!this.results.length) { dd.classList.add('hidden'); return; }

    dd.innerHTML = this.results.map(r => {
      const thumb = r.thumb ? `${this.tautulli}/pms_image_proxy?img=${encodeURIComponent(r.thumb)}&rating_key=${r.ratingKey}&fallback=poster` : '';
      const url = `${this.tautulli}/info?rating_key=${r.ratingKey}`;
      return `
        <a href="${url}" target="_blank" style="display:flex; gap:0.75rem; padding:0.75rem; text-decoration:none; color:white; border-bottom:1px solid rgba(255,255,255,0.06);">
          ${thumb ? `<img src="${thumb}" style="width:40px; height:60px; object-fit:cover; border-radius:0.375rem;">` : '<div style="width:40px; height:60px; background:rgba(255,255,255,0.05); border-radius:0.375rem; display:flex; align-items:center; justify-content:center;">🎬</div>'}
          <div style="flex:1; min-width:0;">
            <div style="font-weight:600; font-size:0.875rem;">${r.title} ${r.year ? `<span style="color:rgba(255,255,255,0.3);">(${r.year})</span>` : ''}</div>
            <div style="font-size:0.75rem; color:#a855f7;">${r.type === 'movie' ? '🎬 Movie' : '📺 TV Show'}</div>
          </div>
        </a>
      `;
    }).join('');
    dd.classList.remove('hidden');
  }

  render() {
    this.innerHTML = `
      <div style="position:relative; width:100%; max-width:400px;">
        <div style="position:relative;">
          <svg style="position:absolute; left:0.875rem; top:50%; transform:translateY(-50%); width:1rem; height:1rem; color:rgba(255,255,255,0.3);" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
          </svg>
          <input type="text" placeholder="Search movies & shows..." style="width:100%; padding:0.625rem 2rem 0.625rem 2.5rem; background:#12121a; border:1px solid rgba(255,255,255,0.06); border-radius:0.75rem; color:white; font-size:0.875rem; outline:none;">
          <button class="clear hidden" onclick="this.closest('search-bar').clear()" style="position:absolute; right:0.5rem; top:50%; transform:translateY(-50%); background:none; border:none; color:rgba(255,255,255,0.3); cursor:pointer; font-size:1.25rem;">×</button>
        </div>
        <div class="dropdown hidden" style="position:absolute; top:calc(100% + 0.5rem); width:100%; background:#12121a; border:1px solid rgba(255,255,255,0.06); border-radius:0.75rem; max-height:400px; overflow-y:auto; z-index:100; box-shadow:0 12px 32px rgba(0,0,0,0.5);"></div>
      </div>
    `;
  }
}

customElements.define('search-bar', SearchBar);
