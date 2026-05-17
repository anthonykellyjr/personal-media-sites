<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useApi } from '../composables/useApi.js'
import PosterCard from './PosterCard.vue'

const props = defineProps({
  libraryKey: { type: String, default: '' },
  searchQuery: { type: String, default: '' },
  canvasKeys: { type: Set, default: () => new Set() },
})

const emit = defineEmits(['addItem'])

const { apiFetch } = useApi()

const items = ref([])
const page = ref(1)
const totalSize = ref(0)
const isLoading = ref(false)
const hasMore = ref(true)
const sentinel = ref(null)

const PAGE_SIZE = 50

const fetchItems = async (reset = false) => {
  if (!props.libraryKey || isLoading.value) return
  if (!reset && !hasMore.value) return

  isLoading.value = true
  if (reset) {
    items.value = []
    page.value = 1
    hasMore.value = true
  }

  try {
    const params = new URLSearchParams({
      page: page.value,
      size: PAGE_SIZE,
    })
    if (props.searchQuery) params.set('search', props.searchQuery)

    const data = await apiFetch(`/capi/libraries/${props.libraryKey}/items?${params}`)
    const newItems = data.items || []

    if (reset) {
      items.value = newItems
    } else {
      items.value = [...items.value, ...newItems]
    }

    totalSize.value = data.totalSize || 0
    hasMore.value = items.value.length < totalSize.value && newItems.length === PAGE_SIZE
    page.value++
  } catch (err) {
    console.error('Error fetching library items:', err)
  } finally {
    isLoading.value = false
  }
}

// Infinite scroll via IntersectionObserver
let observer = null

const setupObserver = () => {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && hasMore.value && !isLoading.value) {
      fetchItems()
    }
  }, { rootMargin: '200px' })

  nextTick(() => {
    if (sentinel.value) observer.observe(sentinel.value)
  })
}

// Watch for library or search changes
watch(() => props.libraryKey, () => {
  fetchItems(true)
  setupObserver()
})

watch(() => props.searchQuery, () => {
  fetchItems(true)
})

onMounted(() => {
  if (props.libraryKey) {
    fetchItems(true)
    setupObserver()
  }
})

onUnmounted(() => {
  if (observer) observer.disconnect()
})

const isInCanvas = (item) => props.canvasKeys.has(item.ratingKey)
</script>

<template>
  <div>
    <!-- Header -->
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-xs font-bold text-slate-300 uppercase tracking-widest flex items-center gap-2">
        <span class="w-1.5 h-1.5 rounded-full bg-slate-400 inline-block"></span>
        Library
        <span v-if="totalSize" class="text-slate-500 font-normal normal-case">({{ totalSize }} items)</span>
      </h2>
    </div>

    <!-- Empty state -->
    <div v-if="!libraryKey" class="text-center py-12 text-slate-500 text-sm">
      Select a library above to browse
    </div>

    <!-- Grid -->
    <div v-else class="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8">
      <PosterCard
        v-for="item in items"
        :key="item.ratingKey"
        :item="item"
        :selected="isInCanvas(item)"
        @click="$emit('addItem', item)"
      />

      <!-- Skeleton placeholders while loading -->
      <div v-if="isLoading" v-for="i in (items.length === 0 ? 24 : 8)" :key="'skeleton-' + i"
           class="bg-slate-800 animate-pulse rounded-xl aspect-[2/3]"></div>
    </div>

    <!-- Infinite scroll sentinel -->
    <div ref="sentinel" class="h-4"></div>

    <!-- Loading more indicator -->
    <div v-if="isLoading && items.length > 0" class="flex items-center justify-center gap-2 py-4 text-sm text-slate-500">
      <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
      </svg>
      Loading more...
    </div>

    <!-- End of results -->
    <div v-if="!hasMore && items.length > 0 && !isLoading" class="text-center py-4 text-xs text-slate-600">
      All {{ totalSize }} items loaded
    </div>
  </div>
</template>
