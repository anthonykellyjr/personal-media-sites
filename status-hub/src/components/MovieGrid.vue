<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  limit: {
    type: Number,
    default: 10
  },
  layout: {
    type: String,
    default: 'horizontal', // 'horizontal' or 'grid'
    validator: (val) => ['horizontal', 'grid'].includes(val)
  },
  refreshInterval: {
    type: Number,
    default: 600000 // 10 minutes default
  },
  enablePullRefresh: {
    type: Boolean,
    default: false
  },
  showHeader: {
    type: Boolean,
    default: true
  }
})

const movies = ref([])
const isLoading = ref(false)
const error = ref(null)
const scrollContainer = ref(null)
const canScrollLeft = ref(false)
const canScrollRight = ref(false)

const checkScroll = () => {
  const el = scrollContainer.value
  if (!el) return
  canScrollLeft.value = el.scrollLeft > 4
  canScrollRight.value = el.scrollLeft + el.clientWidth < el.scrollWidth - 4
}

const scrollLeft = () => {
  const el = scrollContainer.value
  if (!el) return
  el.scrollBy({ left: -el.clientWidth * 0.75, behavior: 'smooth' })
}

const scrollRight = () => {
  const el = scrollContainer.value
  if (!el) return
  el.scrollBy({ left: el.clientWidth * 0.75, behavior: 'smooth' })
}

const fetchMovies = async () => {
  try {
    error.value = null
    const res = await fetch('/api/trending-movies')
    if (!res.ok) throw new Error('Failed to fetch movies')
    const data = await res.json()
    movies.value = data.movies || []
  } catch (err) {
    console.error('Error fetching movies:', err)
    error.value = err.message
  }
}

const displayedMovies = computed(() => movies.value.slice(0, props.limit))

const formatDateAdded = (dateStr) => {
  if (!dateStr) return ''
  const date = typeof dateStr === 'number' ? new Date(dateStr * 1000) : new Date(dateStr)
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

const smallPoster = (url) => {
  if (!url) return url
  return url.replace('/original/', '/w300/')
}

const containerClasses = computed(() => {
  if (props.layout === 'grid') {
    return 'grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8'
  }
  return 'flex gap-2 pb-2 overflow-x-auto scrollbar-hide'
})

const cardClasses = computed(() => {
  if (props.layout === 'grid') {
    return 'group relative bg-slate-950/60 backdrop-blur-xl border border-white/15 rounded-xl overflow-hidden transition-all duration-300 ease-out hover:scale-[1.05] hover:-translate-y-2 hover:shadow-[0_20px_50px_-10px_rgba(0,0,0,0.7),0_0_30px_rgba(168,85,247,0.3)] hover:border-purple-500/50 hover:z-10'
  }
  return 'group flex-shrink-0 min-w-[130px] max-w-[180px] bg-slate-950/60 backdrop-blur-xl border border-white/15 rounded-xl overflow-hidden transition-all duration-300 ease-out hover:scale-[1.03] hover:-translate-y-1 hover:shadow-[0_15px_40px_-10px_rgba(0,0,0,0.6),0_0_20px_rgba(168,85,247,0.2)] hover:border-purple-500/50 hover:z-10'
})

let interval = null

onMounted(() => {
  fetchMovies().then(() => nextTick(checkScroll))
  if (props.refreshInterval > 0) {
    interval = setInterval(fetchMovies, props.refreshInterval)
  }
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
})

defineExpose({ fetchMovies })

</script>

<template>
  <section :class="layout === 'grid' ? '' : 'mb-5'">
    <h2 v-if="showHeader" class="text-sm font-bold text-slate-300 uppercase tracking-widest mb-2 flex items-center gap-2 px-1">
      <span class="w-1.5 h-1.5 rounded-full bg-slate-400 inline-block"></span> Trending Movies
    </h2>

    <div v-if="error" class="text-red-400 text-sm p-4 bg-red-900/20 border border-red-500/30 rounded-lg">
      Failed to load movies: {{ error }}
    </div>

    <div v-else-if="movies.length === 0 && !isLoading" class="text-slate-400 text-sm p-4">
      No movies found
    </div>

    <div v-else class="relative">
      <button v-if="canScrollLeft && layout === 'horizontal'" @click="scrollLeft" class="absolute left-0 top-0 bottom-0 w-12 flex items-center justify-center bg-gradient-to-r from-black/70 via-black/40 to-transparent rounded-l-xl z-10">
        <svg class="w-6 h-6 text-white drop-shadow-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15 19l-7-7 7-7"/></svg>
      </button>
      <div ref="scrollContainer" :class="containerClasses" @scroll="checkScroll">
        <component :is="movie.url ? 'a' : 'div'" v-for="movie in displayedMovies" :key="movie.id" :href="movie.url || undefined" :target="movie.url ? '_blank' : undefined" :class="cardClasses" class="cursor-pointer">
          <div class="w-full aspect-[3/4] overflow-hidden">
            <img
              v-if="movie.thumb || movie.poster"
              :src="smallPoster(movie.thumb || movie.poster)"
              :alt="movie.title"
              class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
              loading="lazy"
            >
            <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
              <span class="text-slate-600 text-lg">?</span>
            </div>
          </div>
          <div class="px-2 py-1.5">
            <div class="text-sm font-semibold text-white truncate leading-tight">{{ movie.title }}</div>
            <div class="text-xs text-fuchsia-400 font-medium">{{ movie.year || '' }}</div>
          </div>
        </component>
      </div>
      <button v-if="canScrollRight && layout === 'horizontal'" @click="scrollRight" class="absolute right-0 top-0 bottom-0 w-12 flex items-center justify-center bg-gradient-to-l from-black/70 via-black/40 to-transparent rounded-r-xl z-10">
        <svg class="w-6 h-6 text-white drop-shadow-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7"/></svg>
      </button>
    </div>
  </section>
</template>
