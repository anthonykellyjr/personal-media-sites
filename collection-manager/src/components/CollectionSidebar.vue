<script setup>
import { ref, watch } from 'vue'
import { useApi } from '../composables/useApi.js'

const props = defineProps({
  libraryKey: { type: String, default: '' },
  activeCollectionKey: { type: String, default: '' },
})

const emit = defineEmits(['select', 'new'])

const { apiFetch } = useApi()

const collections = ref([])
const isLoading = ref(false)
const filterText = ref('')

const fetchCollections = async () => {
  if (!props.libraryKey) {
    collections.value = []
    return
  }
  isLoading.value = true
  try {
    const data = await apiFetch(`/capi/libraries/${props.libraryKey}/collections`)
    collections.value = data.collections || []
  } catch (err) {
    console.error('Error fetching collections:', err)
  } finally {
    isLoading.value = false
  }
}

watch(() => props.libraryKey, fetchCollections, { immediate: true })

const filteredCollections = ref([])
watch([collections, filterText], () => {
  const q = filterText.value.toLowerCase()
  filteredCollections.value = q
    ? collections.value.filter(c => c.title.toLowerCase().includes(q))
    : collections.value
}, { immediate: true })

// Expose refresh for parent to call after save/delete
const refresh = () => fetchCollections()
defineExpose({ refresh })
</script>

<template>
  <div class="flex flex-col h-full">
    <!-- New Collection button -->
    <button @click="$emit('new')"
            class="w-full py-2.5 mb-3 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
      </svg>
      New Collection
    </button>

    <!-- Filter -->
    <input v-if="collections.length > 5"
           v-model="filterText"
           type="text"
           placeholder="Filter..."
           class="w-full px-3 py-2 mb-2 bg-dark-900 border border-white/10 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/40 transition-colors" />

    <!-- Collection list -->
    <div class="flex-1 overflow-y-auto thin-scrollbar space-y-1">
      <div v-if="isLoading" class="space-y-2 py-2">
        <div v-for="i in 5" :key="i" class="h-10 bg-slate-800 animate-pulse rounded-lg"></div>
      </div>

      <div v-else-if="filteredCollections.length === 0 && !isLoading"
           class="text-center py-8 text-slate-600 text-xs">
        {{ collections.length === 0 ? 'No collections yet' : 'No matches' }}
      </div>

      <button
        v-for="col in filteredCollections"
        :key="col.ratingKey"
        @click="$emit('select', col.ratingKey)"
        class="w-full text-left px-3 py-2.5 rounded-lg transition-all text-sm flex items-center gap-2"
        :class="activeCollectionKey === col.ratingKey
          ? 'bg-purple-600/20 border border-purple-500/40 text-white'
          : 'hover:bg-slate-800/60 text-slate-300 hover:text-white border border-transparent'">
        <span class="flex-1 truncate">{{ col.title }}</span>
        <span v-if="col.kometaManaged"
              class="flex-shrink-0 text-[9px] font-bold px-1.5 py-0.5 bg-amber-600/20 text-amber-400 border border-amber-500/30 rounded-md uppercase tracking-wider"
              title="Managed by Kometa — changes may be overwritten at 3 AM">
          Kometa
        </span>
        <span v-if="col.smart"
              class="flex-shrink-0 text-[9px] font-bold px-1.5 py-0.5 bg-blue-600/20 text-blue-400 border border-blue-500/30 rounded-md uppercase tracking-wider">
          Smart
        </span>
        <span class="flex-shrink-0 text-[10px] text-slate-500">{{ col.childCount }}</span>
      </button>
    </div>
  </div>
</template>
