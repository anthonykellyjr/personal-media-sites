<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { PageHeader } from '@webhead/shared'
import garfieldImg from '../garfield.webp'

const PLEX_MACHINE_ID = 'b1260353b00ff078b4c700023867f78a4a15aa53'
const PAGE_SIZE = 20
const activeTab = ref('movies')
const movies = ref([])
const episodes = ref([])
const fulfilledRequests = ref([])
const isLoading = ref(false)
const error = ref(null)

// Derive string value for subtitle binding
const tabLabel = computed(() => ({
  movies: 'Movies',
  episodes: 'Episodes',
  requests: 'Media Requests',
}[activeTab.value] || ''))

// normalize subtitle string
const pageSubtitle = computed(() => `in ${tabLabel.value} · WebheadPlex`)

// Shared with /requests-admin/ via localStorage. When present, the hide-on-hover
// button appears on Requests cards; when missing, public visitors see nothing.
const adminKey = ref(localStorage.getItem('requests_admin_key') || '')

async function hideRequest(req) {
  if (!req.tmdbId) {
    alert("Can't hide — this entry has no tmdbId.")
    return
  }
  try {
    const res = await fetch('/api/recently-fulfilled/hide', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Key': adminKey.value },
      body: JSON.stringify({ tmdbId: req.tmdbId, type: req.type }),
    })
    if (res.status === 401) {
      alert('Admin key rejected. Sign back in at /requests-admin/ to refresh it.')
      localStorage.removeItem('requests_admin_key')
      adminKey.value = ''
      return
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    // Optimistic local removal so the user doesn't have to wait for a refetch.
    fulfilledRequests.value = fulfilledRequests.value.filter(
      r => !(r.tmdbId === req.tmdbId && r.type === req.type)
    )
  } catch (err) {
    alert('Hide failed: ' + err.message)
  }
}

// Lazy-load caps per tab.
const movieCap = ref(PAGE_SIZE)
const episodeCap = ref(PAGE_SIZE)
const requestCap = ref(PAGE_SIZE)
const sentinel = ref(null)

// Pull to refresh
const touchStartY = ref(0)
const touchCurrentY = ref(0)
const isPulling = ref(false)
const isRefreshing = ref(false)

// Group episodes by series. Each entry shows the most-recently-added episode
// of that series, and the click target is that episode's season (the backend
// builds the url from parentRatingKey, so a click lands in the right season).
const groupedEpisodes = computed(() => {
  const groups = {}
  for (const ep of episodes.value) {
    const key = ep.seriesTitle
    if (!groups[key]) groups[key] = []
    groups[key].push(ep)
  }
  return Object.values(groups).map(eps => {
    const latest = eps.reduce((a, b) => (a.addedAt >= b.addedAt ? a : b))
    return {
      id: latest.seriesTitle,
      seriesTitle: latest.seriesTitle,
      thumb: latest.thumb,
      url: latest.url,               // season URL of the most-recent episode
      addedAt: latest.addedAt,
      epLabel: `S${latest.seasonNumber}E${latest.episodeNumber}`,
      // Backend now pre-dedupes by series and sends `count`; fall back to the
      // per-page group size if an older backend response is in flight.
      count: latest.count ?? eps.length,
    }
  }).sort((a, b) => b.addedAt - a.addedAt)
})

async function fetchJson(label, url) {
  let res
  try {
    res = await fetch(url)
  } catch (netErr) {
    throw new Error(`${label} — network error (${netErr.message})`)
  }
  if (!res.ok) {
    const snippet = await res.text().catch(() => '')
    console.error(`${label} API responded`, res.status, res.statusText, snippet.slice(0, 500))
    const detail = snippet.trim().slice(0, 80).replace(/\s+/g, ' ')
    throw new Error(`${label} — HTTP ${res.status}${detail ? ': ' + detail : ''}`)
  }
  try {
    return await res.json()
  } catch (parseErr) {
    throw new Error(`${label} — bad JSON (${parseErr.message})`)
  }
}

const fetchMovies = async () => {
  const data = await fetchJson('movies', '/api/recently-added-movies')
  movies.value = data.movies || []
}

const fetchEpisodes = async () => {
  const data = await fetchJson('episodes', '/api/recently-added-episodes')
  episodes.value = data.episodes || []
}

const fetchFulfilled = async () => {
  const data = await fetchJson('requests', '/api/recently-fulfilled')
  fulfilledRequests.value = data.requests || []
}

const fetchAll = async (showLoader = false) => {
  if (isRefreshing.value) return
  isRefreshing.value = true
  if (showLoader) isLoading.value = true
  error.value = null
  const failures = []
  await Promise.all([
    fetchMovies().catch(e => failures.push(e.message)),
    fetchEpisodes().catch(e => failures.push(e.message)),
    fetchFulfilled().catch(e => failures.push(e.message)),
  ])
  if (failures.length) error.value = failures.join(' · ')
  setTimeout(() => { isLoading.value = false; isRefreshing.value = false }, 300)
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp * 1000)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const visibleMovies = computed(() => movies.value.slice(0, movieCap.value))
const visibleEpisodes = computed(() => groupedEpisodes.value.slice(0, episodeCap.value))
const visibleRequests = computed(() => fulfilledRequests.value.slice(0, requestCap.value))

const totalForActiveTab = computed(() => ({
  movies: movies.value.length,
  episodes: groupedEpisodes.value.length,
  requests: fulfilledRequests.value.length,
}[activeTab.value] || 0))

const visibleForActiveTab = computed(() => ({
  movies: Math.min(movieCap.value, movies.value.length),
  episodes: Math.min(episodeCap.value, groupedEpisodes.value.length),
  requests: Math.min(requestCap.value, fulfilledRequests.value.length),
}[activeTab.value] || 0))

const hasMore = computed(() => visibleForActiveTab.value < totalForActiveTab.value)

function loadMore() {
  if (!hasMore.value) return
  if (activeTab.value === 'movies') movieCap.value += PAGE_SIZE
  else if (activeTab.value === 'episodes') episodeCap.value += PAGE_SIZE
  else if (activeTab.value === 'requests') requestCap.value += PAGE_SIZE
}

function switchTab(t) {
  if (activeTab.value === t) return
  activeTab.value = t
  movieCap.value = PAGE_SIZE
  episodeCap.value = PAGE_SIZE
  requestCap.value = PAGE_SIZE
  window.scrollTo({ top: 0 })
}

const handleTouchStart = (e) => {
  if (window.scrollY === 0 && !isRefreshing.value) {
    touchStartY.value = e.touches[0].clientY
    isPulling.value = true
  }
}
const handleTouchMove = (e) => {
  if (!isPulling.value || isRefreshing.value) return
  touchCurrentY.value = e.touches[0].clientY
  if (touchCurrentY.value - touchStartY.value > 40 && window.scrollY === 0) e.preventDefault()
}
const handleTouchEnd = () => {
  if (isPulling.value && touchCurrentY.value - touchStartY.value > 80) fetchAll(true)
  isPulling.value = false
  touchStartY.value = 0
  touchCurrentY.value = 0
}

let observer = null
onMounted(() => {
  fetchAll(true)
  const interval = setInterval(() => fetchAll(false), 60000)
  observer = new IntersectionObserver(
    entries => { if (entries[0].isIntersecting) loadMore() },
    { rootMargin: '300px' }
  )
  if (sentinel.value) observer.observe(sentinel.value)
  onUnmounted(() => { clearInterval(interval); observer?.disconnect() })
})
</script>

<template>
  <div @touchstart="handleTouchStart" @touchmove="handleTouchMove" @touchend="handleTouchEnd">
    
    <div v-if="isLoading" role="status" aria-live="polite"
         class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
      <div class="flex gap-3" aria-hidden="true">
        <span class="w-4 h-4 rounded-full bg-blue-500 animate-bounce" style="animation-delay: 0s"></span>
        <span class="w-4 h-4 rounded-full bg-purple-500 animate-bounce" style="animation-delay: 0.15s"></span>
        <span class="w-4 h-4 rounded-full bg-pink-500 animate-bounce" style="animation-delay: 0.3s"></span>
      </div>
      <span class="sr-only">Loading recently added media…</span>
    </div>

    <div v-if="isPulling && (touchCurrentY - touchStartY > 20)"
         class="fixed top-0 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-lg px-5 py-3 rounded-b-2xl text-sm text-white flex items-center gap-2 z-10 pointer-events-none"
         :style="{ transform: `translateX(-50%) translateY(${Math.min((touchCurrentY - touchStartY) / 2, 40)}px)` }">
      <svg class="w-5 h-5 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/>
      </svg>
      <span>Release to refresh</span>
    </div>

    <div class="min-h-screen p-4 max-w-[1200px] mx-auto">
      
      <PageHeader title="Recently Added" :subtitle="pageSubtitle" :logo="garfieldImg" logo-alt="WebHead Media">
        <div role="tablist" aria-label="Recently added categories" class="flex items-center gap-2">
          <button @click="switchTab('movies')" role="tab" :aria-selected="activeTab === 'movies'" :tabindex="activeTab === 'movies' ? 0 : -1"
                  class="px-4 py-2 rounded-lg text-sm font-bold transition-all duration-200 whitespace-nowrap"
                  :class="activeTab === 'movies' ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/30' : 'bg-transparent text-slate-400 hover:bg-white/10 hover:text-white'">
            Movies <span class="ml-1.5 text-xs opacity-70">{{ movies.length }}</span>
          </button>
          <button @click="switchTab('episodes')" role="tab" :aria-selected="activeTab === 'episodes'" :tabindex="activeTab === 'episodes' ? 0 : -1"
                  class="px-4 py-2 rounded-lg text-sm font-bold transition-all duration-200 whitespace-nowrap"
                  :class="activeTab === 'episodes' ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/30' : 'bg-transparent text-slate-400 hover:bg-white/10 hover:text-white'">
            Episodes <span class="ml-1.5 text-xs opacity-70">{{ groupedEpisodes.length }}</span>
          </button>
          <button @click="switchTab('requests')" role="tab" :aria-selected="activeTab === 'requests'" :tabindex="activeTab === 'requests' ? 0 : -1"
                  class="px-4 py-2 rounded-lg text-sm font-bold transition-all duration-200 whitespace-nowrap"
                  :class="activeTab === 'requests' ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/30' : 'bg-transparent text-slate-400 hover:bg-white/10 hover:text-white'">
            Requests <span class="ml-1.5 text-xs opacity-70">{{ fulfilledRequests.length }}</span>
          </button>
        </div>
        <button @click="fetchAll(true)"
                class="ml-2 w-10 h-10 flex-shrink-0 bg-white/5 border border-white/10 rounded-lg flex items-center justify-center hover:bg-white/20 transition-all"
                :class="{ 'animate-spin': isRefreshing }"
                :aria-busy="isRefreshing"
                aria-label="Refresh data"
                title="Refresh Data">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
          </svg>
        </button>
      </PageHeader>

      <!-- aria-live="polite" so screen readers announce new errors without
           interrupting; break-words keeps long HTML snippets from overflowing. -->
      <div v-if="error" role="alert" aria-live="polite"
           class="text-left p-4 md:p-6 text-red-300 bg-red-900/10 border border-red-500/30 rounded-xl mb-4 break-words text-sm">
        <span class="font-bold mr-1">Failed to load:</span>{{ error }}
      </div>

      <div v-if="activeTab === 'movies'">
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-5 gap-4 md:gap-6">
          <a v-for="movie in visibleMovies" :key="movie.id" :href="movie.url" target="_blank"
             class="group relative bg-slate-950/60 border border-white/10 rounded-xl overflow-hidden transition-all duration-200 hover:scale-105 hover:-translate-y-1 hover:shadow-[0_12px_30px_-8px_rgba(0,0,0,0.6),0_0_20px_rgba(168,85,247,0.2)] hover:border-purple-500/40 hover:z-10">
            <div class="relative w-full aspect-[2/3] overflow-hidden">
              <img v-if="movie.thumb" :src="movie.thumb" :alt="movie.title" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110" loading="lazy">
              <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
                <span class="text-slate-600 text-lg">?</span>
              </div>
            </div>
            <div class="p-3">
              <div class="text-sm font-bold text-white truncate leading-tight mb-1">{{ movie.title }}</div>
              <div class="flex items-center justify-between mt-1">
                <span class="text-xs text-slate-400">{{ movie.year }}</span>
                <span class="text-xs font-semibold text-purple-300 bg-purple-900/40 px-2 py-0.5 rounded-md">{{ formatTime(movie.addedAt) }}</span>
              </div>
            </div>
          </a>
        </div>
      </div>

      <div v-if="activeTab === 'episodes'">
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 md:gap-6">
          <a v-for="ep in visibleEpisodes" :key="ep.id" :href="ep.url" target="_blank"
             class="group relative bg-slate-950/60 border border-white/10 rounded-xl overflow-hidden transition-all duration-200 hover:scale-105 hover:-translate-y-1 hover:shadow-[0_12px_30px_-8px_rgba(0,0,0,0.6),0_0_20px_rgba(168,85,247,0.2)] hover:border-purple-500/40 hover:z-10">
            <div class="relative w-full aspect-[2/3] overflow-hidden">
              <img v-if="ep.thumb" :src="ep.thumb" :alt="ep.seriesTitle" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110" loading="lazy">
              <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
                <span class="text-slate-600 text-lg">?</span>
              </div>
              <div v-if="ep.count > 1"
                   class="absolute top-2 right-2 min-w-[24px] h-[24px] px-2 bg-purple-600/90 rounded-full flex items-center justify-center shadow-lg">
                <span class="text-xs font-bold text-white leading-none">{{ ep.count }}</span>
              </div>
            </div>
            <div class="p-3">
              <div class="text-sm font-bold text-white truncate leading-tight mb-1">{{ ep.seriesTitle }}</div>
              <div class="flex items-center justify-between mt-1">
                <span class="text-xs text-slate-400 font-medium">{{ ep.epLabel }}</span>
                <span class="text-xs font-semibold text-purple-300 bg-purple-900/40 px-2 py-0.5 rounded-md">{{ formatTime(ep.addedAt) }}</span>
              </div>
            </div>
          </a>
        </div>
      </div>

      <div v-if="activeTab === 'requests'">
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 md:gap-6">
          <component v-for="req in visibleRequests" :key="req.title + req.type" :is="req.plexUrl ? 'a' : 'div'" :href="req.plexUrl" :target="req.plexUrl ? '_blank' : undefined"
             class="group relative bg-slate-950/60 border border-white/10 rounded-xl overflow-hidden transition-all duration-200 hover:scale-105 hover:-translate-y-1 hover:shadow-[0_12px_30px_-8px_rgba(0,0,0,0.6),0_0_20px_rgba(168,85,247,0.2)] hover:border-purple-500/40 hover:z-10">
            <div class="relative w-full aspect-[2/3] overflow-hidden">
              <img v-if="req.posterUrl" :src="req.posterUrl" :alt="req.title" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110" loading="lazy">
              <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
                <span class="text-slate-600 text-lg">?</span>
              </div>
              <div class="absolute top-2 right-2 px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wide shadow-lg"
                   :class="req.type === 'movie' ? 'bg-blue-600/90 text-blue-100' : 'bg-emerald-600/90 text-emerald-100'">
                {{ req.type === 'movie' ? 'Movie' : 'TV' }}
              </div>
              <!-- Admin-only hide button: opacity-0 → opacity-100 on card hover.
                   .stop.prevent so clicking it doesn't navigate to Plex. -->
              <button v-if="adminKey"
                      @click.stop.prevent="hideRequest(req)"
                      class="absolute top-2 left-2 w-7 h-7 rounded-full bg-red-600/90 hover:bg-red-700 text-white text-base font-bold leading-none shadow-lg opacity-0 group-hover:opacity-100 focus:opacity-100 transition flex items-center justify-center"
                      :aria-label="`Hide ${req.title} from this feed`"
                      title="Hide from feed">
                ×
              </button>
            </div>
            <div class="p-3">
              <div class="text-sm font-bold text-white truncate leading-tight mb-1">{{ req.title }}</div>
              <div class="flex items-center justify-between mt-1">
                <span class="text-xs text-slate-400">{{ req.year }}</span>
                <span class="text-xs font-semibold text-purple-300 bg-purple-900/40 px-2 py-0.5 rounded-md">{{ formatTime(req.addedAt) }}</span>
              </div>
            </div>
          </component>
        </div>
      </div>

      <div v-if="activeTab === 'movies' && movies.length === 0 && !isLoading && !error" class="text-center p-10 text-slate-400">No movies found</div>
      <div v-if="activeTab === 'episodes' && episodes.length === 0 && !isLoading && !error" class="text-center p-10 text-slate-400">No episodes found</div>
      <div v-if="activeTab === 'requests' && fulfilledRequests.length === 0 && !isLoading && !error" class="text-center p-10 text-slate-400">No fulfilled requests found</div>

      <div ref="sentinel" class="h-px"></div>
      <div v-if="hasMore" class="text-center text-sm text-slate-500 py-8">Loading more…</div>
      <div v-else-if="totalForActiveTab > 0" class="text-center text-sm text-slate-600 py-8">
        Showing all {{ totalForActiveTab }}.
      </div>
    </div>
  </div>
</template>