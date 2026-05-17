<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { HubButton } from '@webhead/shared'
import garfieldImg from '../garfield.webp'

const PLEX_MACHINE_ID = 'b1260353b00ff078b4c700023867f78a4a15aa53'
const PAGE_SIZE = 20
const activeTab = ref('movies')
const movies = ref([])
const episodes = ref([])
const fulfilledRequests = ref([])
const isLoading = ref(false)
const error = ref(null)

// Lazy-load caps per tab. Each starts at PAGE_SIZE; an IntersectionObserver
// watching a sentinel at the bottom bumps the active tab's cap by PAGE_SIZE
// when scrolled into view.
const movieCap = ref(PAGE_SIZE)
const episodeCap = ref(PAGE_SIZE)
const requestCap = ref(PAGE_SIZE)
const sentinel = ref(null)

// Pull to refresh
const touchStartY = ref(0)
const touchCurrentY = ref(0)
const isPulling = ref(false)
const isRefreshing = ref(false)

// Group episodes by series, showing latest episode info + count
const groupedEpisodes = computed(() => {
  const groups = {}
  for (const ep of episodes.value) {
    const key = ep.seriesTitle
    if (!groups[key]) {
      groups[key] = { ...ep, episodes: [ep] }
    } else {
      groups[key].episodes.push(ep)
      // Keep the most recent addedAt
      if (ep.addedAt > groups[key].addedAt) {
        groups[key].addedAt = ep.addedAt
      }
    }
  }
  // Build display data
  return Object.values(groups).map(g => {
    const eps = g.episodes.sort((a, b) => {
      if (a.seasonNumber !== b.seasonNumber) return a.seasonNumber - b.seasonNumber
      return a.episodeNumber - b.episodeNumber
    })
    const first = eps[0]
    const last = eps[eps.length - 1]
    let epLabel
    if (eps.length === 1) {
      epLabel = `S${first.seasonNumber}E${first.episodeNumber}`
    } else if (first.seasonNumber === last.seasonNumber) {
      epLabel = `S${first.seasonNumber}E${first.episodeNumber}-E${last.episodeNumber}`
    } else {
      epLabel = `${eps.length} episodes`
    }
    return {
      id: g.seriesTitle,
      seriesTitle: g.seriesTitle,
      thumb: g.thumb,
      url: g.url,
      addedAt: g.addedAt,
      epLabel,
      count: eps.length,
    }
  }).sort((a, b) => b.addedAt - a.addedAt)
})

const fetchMovies = async () => {
  try {
    const res = await fetch('/api/recently-added-movies')
    if (!res.ok) throw new Error('Failed to fetch movies')
    const data = await res.json()
    movies.value = data.movies || []
  } catch (err) {
    console.error('Error fetching movies:', err)
    error.value = err.message
  }
}

const fetchEpisodes = async () => {
  try {
    const res = await fetch('/api/recently-added-episodes')
    if (!res.ok) throw new Error('Failed to fetch episodes')
    const data = await res.json()
    episodes.value = data.episodes || []
  } catch (err) {
    console.error('Error fetching episodes:', err)
    error.value = err.message
  }
}

const fetchFulfilled = async () => {
  try {
    const res = await fetch('/api/recently-fulfilled')
    if (!res.ok) throw new Error('Failed to fetch requests')
    const data = await res.json()
    fulfilledRequests.value = data.requests || []
  } catch (err) {
    console.error('Error fetching fulfilled requests:', err)
    error.value = err.message
  }
}

const fetchAll = async (showLoader = false) => {
  if (isRefreshing.value) return
  isRefreshing.value = true
  if (showLoader) isLoading.value = true
  error.value = null
  await Promise.all([fetchMovies(), fetchEpisodes(), fetchFulfilled()])
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

// Group movies by week, capped at movieCap (lazy load). Newer items come
// first from the API, so slicing then grouping keeps the most-recent groups.
const groupedMovies = computed(() => {
  const now = Date.now() / 1000
  const weekS = 7 * 86400
  const groups = [
    { label: 'This Week', items: [] },
    { label: 'Last Week', items: [] },
    { label: '2 Weeks Ago', items: [] },
    { label: '3 Weeks Ago', items: [] },
    { label: 'Earlier', items: [] },
  ]
  for (const m of movies.value.slice(0, movieCap.value)) {
    const age = now - (m.addedAt || 0)
    if (age < weekS) groups[0].items.push(m)
    else if (age < 2 * weekS) groups[1].items.push(m)
    else if (age < 3 * weekS) groups[2].items.push(m)
    else if (age < 4 * weekS) groups[3].items.push(m)
    else groups[4].items.push(m)
  }
  return groups.filter(g => g.items.length > 0)
})

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

// Reset caps when switching tabs so users always start at the top of each tab.
function switchTab(t) {
  if (activeTab.value === t) return
  activeTab.value = t
  movieCap.value = PAGE_SIZE
  episodeCap.value = PAGE_SIZE
  requestCap.value = PAGE_SIZE
  window.scrollTo({ top: 0 })
}

// Pull to refresh handlers
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
  // Lazy-load: bump the active tab's cap when the sentinel comes into view.
  // rootMargin pre-loads slightly before the user hits the bottom.
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
    <!-- Loading overlay -->
    <div v-if="isLoading" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
      <div class="flex gap-3">
        <span class="w-4 h-4 rounded-full bg-blue-500 animate-bounce" style="animation-delay: 0s"></span>
        <span class="w-4 h-4 rounded-full bg-purple-500 animate-bounce" style="animation-delay: 0.15s"></span>
        <span class="w-4 h-4 rounded-full bg-pink-500 animate-bounce" style="animation-delay: 0.3s"></span>
      </div>
    </div>

    <!-- Pull indicator -->
    <div v-if="isPulling && (touchCurrentY - touchStartY > 20)"
         class="fixed top-0 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-lg px-5 py-3 rounded-b-2xl text-sm text-white flex items-center gap-2 z-10 pointer-events-none"
         :style="{ transform: `translateX(-50%) translateY(${Math.min((touchCurrentY - touchStartY) / 2, 40)}px)` }">
      <svg class="w-5 h-5 animate-bounce" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3"/>
      </svg>
      <span>Release to refresh</span>
    </div>

    <!-- Refresh button (desktop) -->
    <button @click="fetchAll(true)"
            class="hidden md:flex fixed top-5 right-5 w-12 h-12 px-3 bg-black/50 backdrop-blur-lg border border-white/20 rounded-full items-center justify-center hover:bg-black/70 hover:border-white/40 hover:scale-110 transition z-10"
            :class="{ 'animate-spin': isRefreshing }">
      <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
      </svg>
    </button>

    <div class="min-h-screen p-4 max-w-[1200px] mx-auto">
      <!-- Header -->
      <header class="text-center mb-5 relative">
        <HubButton class="absolute left-0 top-1/2 -translate-y-1/2" />
        <img :src="garfieldImg" alt="WebHead Media" class="w-14 h-14 rounded-2xl mx-auto mb-2 shadow-2xl">
        <h1 class="text-xl font-bold text-white">Recently Added</h1>
        <p class="text-sm text-white/50">in WebheadPlex</p>
      </header>

      <!-- Tabs -->
      <div class="flex justify-center gap-1 mb-5">
        <button @click="switchTab('movies')"
                class="px-5 py-2 rounded-xl text-sm font-bold transition-all duration-200"
                :class="activeTab === 'movies' ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/30' : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'">
          Movies
          <span class="ml-1.5 text-xs opacity-70">{{ movies.length }}</span>
        </button>
        <button @click="switchTab('episodes')"
                class="px-5 py-2 rounded-xl text-sm font-bold transition-all duration-200"
                :class="activeTab === 'episodes' ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/30' : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'">
          Episodes
          <span class="ml-1.5 text-xs opacity-70">{{ groupedEpisodes.length }}</span>
        </button>
        <button @click="switchTab('requests')"
                class="px-5 py-2 rounded-xl text-sm font-bold transition-all duration-200"
                :class="activeTab === 'requests' ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/30' : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'">
          Requests
          <span class="ml-1.5 text-xs opacity-70">{{ fulfilledRequests.length }}</span>
        </button>
      </div>

      <!-- Error -->
      <div v-if="error" class="text-center p-6 text-red-300 bg-red-900/10 border border-red-500/30 rounded-xl mb-4">
        Failed to load: {{ error }}
      </div>

      <!-- Movies Tab (grouped by time) -->
      <div v-if="activeTab === 'movies'" class="space-y-8">
        <section v-for="group in groupedMovies" :key="group.label" class="bg-white/[0.02] border border-white/5 rounded-2xl p-3">
          <h2 class="text-sm font-bold text-slate-300 uppercase tracking-widest mb-3 px-1 flex items-center gap-2">
            <span class="w-1.5 h-1.5 rounded-full bg-purple-400 inline-block"></span>
            {{ group.label }}
            <span class="text-xs font-normal text-slate-500">({{ group.items.length }})</span>
          </h2>
          <div class="grid grid-cols-2 gap-10 sm:grid-cols-2 md:grid-cols-2 lg:grid-cols-4">
            <a v-for="movie in group.items" :key="movie.id" :href="movie.url" target="_blank"
               class="group relative bg-slate-950/60 border border-white/10 rounded-xl overflow-hidden transition-all duration-200 hover:scale-105 hover:-translate-y-1 hover:shadow-[0_12px_30px_-8px_rgba(0,0,0,0.6),0_0_20px_rgba(168,85,247,0.2)] hover:border-purple-500/40 hover:z-10">
              <div class="relative w-full aspect-[2/3] overflow-hidden">
                <img v-if="movie.thumb" :src="movie.thumb" :alt="movie.title" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110" loading="lazy">
                <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
                  <span class="text-slate-600 text-lg">?</span>
                </div>
              </div>
              <div class="p-1.5">
                <div class="text-[10px] font-bold text-white truncate leading-tight">{{ movie.title }}</div>
                <div class="flex items-center justify-between">
                  <span class="text-[9px] text-slate-400">{{ movie.year }}</span>
                  <span class="text-[9px] font-bold text-fuchsia-400">{{ formatTime(movie.addedAt) }}</span>
                </div>
              </div>
            </a>
          </div>
        </section>
      </div>

      <!-- Episodes Tab -->
      <div v-if="activeTab === 'episodes'" class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        <a v-for="ep in visibleEpisodes" :key="ep.id" :href="ep.url" target="_blank"
           class="group relative bg-slate-950/60 border border-white/10 rounded-xl overflow-hidden transition-all duration-200 hover:scale-105 hover:-translate-y-1 hover:shadow-[0_12px_30px_-8px_rgba(0,0,0,0.6),0_0_20px_rgba(168,85,247,0.2)] hover:border-purple-500/40 hover:z-10">
          <div class="relative w-full aspect-[2/3] overflow-hidden">
            <img v-if="ep.thumb" :src="ep.thumb" :alt="ep.seriesTitle" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110" loading="lazy">
            <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
              <span class="text-slate-600 text-lg">?</span>
            </div>
            <div v-if="ep.count > 1"
                 class="absolute top-1.5 right-1.5 min-w-[22px] h-[22px] px-1.5 bg-purple-600/90 rounded-full flex items-center justify-center shadow-lg">
              <span class="text-[10px] font-bold text-white leading-none">{{ ep.count }}</span>
            </div>
          </div>
          <div class="p-2">
            <div class="text-[11px] font-bold text-white truncate leading-tight">{{ ep.seriesTitle }}</div>
            <div class="flex items-center justify-between mt-0.5">
              <span class="text-[10px] text-slate-400 font-medium">{{ ep.epLabel }}</span>
              <span class="text-[10px] font-bold text-fuchsia-400">{{ formatTime(ep.addedAt) }}</span>
            </div>
          </div>
        </a>
      </div>

      <!-- Requests Tab -->
      <div v-if="activeTab === 'requests'" class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        <component v-for="req in visibleRequests" :key="req.title + req.type" :is="req.plexUrl ? 'a' : 'div'" :href="req.plexUrl" :target="req.plexUrl ? '_blank' : undefined"
           class="group relative bg-slate-950/60 border border-white/10 rounded-xl overflow-hidden transition-all duration-200 hover:scale-105 hover:-translate-y-1 hover:shadow-[0_12px_30px_-8px_rgba(0,0,0,0.6),0_0_20px_rgba(168,85,247,0.2)] hover:border-purple-500/40 hover:z-10">
          <div class="relative w-full aspect-[2/3] overflow-hidden">
            <img v-if="req.posterUrl" :src="req.posterUrl" :alt="req.title" class="w-full h-full object-cover transition-transform duration-300 group-hover:scale-110" loading="lazy">
            <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
              <span class="text-slate-600 text-lg">?</span>
            </div>
            <div class="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded-md text-[9px] font-bold uppercase tracking-wide shadow-lg"
                 :class="req.type === 'movie' ? 'bg-blue-600/90 text-blue-100' : 'bg-emerald-600/90 text-emerald-100'">
              {{ req.type === 'movie' ? 'Movie' : 'TV' }}
            </div>
          </div>
          <div class="p-1.5">
            <div class="text-[10px] font-bold text-white truncate leading-tight">{{ req.title }}</div>
            <div class="flex items-center justify-between">
              <span class="text-[9px] text-slate-400">{{ req.year }}</span>
              <span class="text-[9px] font-bold text-fuchsia-400">{{ formatTime(req.addedAt) }}</span>
            </div>
          </div>
        </component>
      </div>

      <!-- Empty states -->
      <div v-if="activeTab === 'movies' && movies.length === 0 && !isLoading && !error" class="text-center p-10 text-slate-400">No movies found</div>
      <div v-if="activeTab === 'episodes' && episodes.length === 0 && !isLoading && !error" class="text-center p-10 text-slate-400">No episodes found</div>
      <div v-if="activeTab === 'requests' && fulfilledRequests.length === 0 && !isLoading && !error" class="text-center p-10 text-slate-400">No fulfilled requests found</div>

      <!-- Lazy-load sentinel + footer hint -->
      <div ref="sentinel" class="h-px"></div>
      <div v-if="hasMore" class="text-center text-xs text-slate-500 py-6">Loading more…</div>
      <div v-else-if="totalForActiveTab > 0" class="text-center text-xs text-slate-600 py-6">
        Showing all {{ totalForActiveTab }}.
      </div>
    </div>
  </div>
</template>
