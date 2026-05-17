<script setup>
import { ref, watch, computed } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { useApi } from '../composables/useApi.js'

const props = defineProps({
  libraryKey: { type: String, default: '' },
})

const emit = defineEmits(['select', 'new', 'orderChanged', 'toast'])

const { apiFetch } = useApi()

const collections = ref([])
const isLoading = ref(false)
const orderChanged = ref(false)
const isSavingOrder = ref(false)

const adminKey = computed(() => localStorage.getItem('collection_manager_admin_key') || '')

const fetchCollections = async () => {
  if (!props.libraryKey) return
  isLoading.value = true
  try {
    const data = await apiFetch(`/capi/libraries/${props.libraryKey}/collections`)
    collections.value = data.collections || []
    orderChanged.value = false
  } catch (err) {
    console.error('Error fetching collections:', err)
  } finally {
    isLoading.value = false
  }
}

watch(() => props.libraryKey, fetchCollections, { immediate: true })

const onDragEnd = () => {
  orderChanged.value = true
}

const saveOrder = async () => {
  isSavingOrder.value = true
  try {
    const collectionKeys = collections.value.map(c => c.ratingKey)
    await apiFetch(`/capi/libraries/${props.libraryKey}/collections/order`, {
      method: 'PUT',
      body: JSON.stringify({ collectionKeys }),
    })
    orderChanged.value = false
    emit('toast', 'Collection order saved', 'success')
  } catch (err) {
    emit('toast', 'Failed to save order', 'error')
  } finally {
    isSavingOrder.value = false
  }
}

const refresh = () => fetchCollections()
defineExpose({ refresh })
</script>

<template>
  <div>
    <!-- Top bar -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <h2 class="text-sm font-bold text-slate-300 uppercase tracking-widest">Collections</h2>
        <span v-if="collections.length" class="text-xs text-slate-600">({{ collections.length }})</span>
      </div>
      <div class="flex items-center gap-3">
        <!-- Save order button -->
        <button v-if="orderChanged"
                @click="saveOrder"
                :disabled="isSavingOrder"
                class="px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 text-white text-sm font-medium rounded-xl transition-all flex items-center gap-2">
          <svg v-if="isSavingOrder" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
          </svg>
          {{ isSavingOrder ? 'Saving...' : 'Save Order' }}
        </button>
        <!-- New collection -->
        <button @click="$emit('new')"
                class="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-xl transition-all flex items-center gap-2">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
          New Collection
        </button>
      </div>
    </div>

    <!-- Loading skeletons -->
    <div v-if="isLoading" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="bg-slate-800 animate-pulse rounded-2xl h-48"></div>
    </div>

    <!-- Empty state -->
    <div v-else-if="collections.length === 0"
         class="text-center py-20 text-slate-600">
      <svg class="w-16 h-16 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
      </svg>
      <p class="text-lg">No collections yet</p>
      <p class="text-sm mt-1">Create your first collection to get started</p>
    </div>

    <!-- Sortable collection grid -->
    <VueDraggable
      v-else
      v-model="collections"
      :animation="250"
      ghost-class="sortable-ghost"
      handle=".drag-handle"
      @end="onDragEnd"
      class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">

      <div v-for="col in collections"
           :key="col.ratingKey"
           @click="$emit('select', col.ratingKey)"
           class="group relative bg-slate-950/60 backdrop-blur-xl border border-white/15 rounded-2xl overflow-hidden cursor-pointer transition-all duration-300 hover:border-purple-500/50 hover:shadow-[0_20px_50px_-10px_rgba(0,0,0,0.7),0_0_30px_rgba(168,85,247,0.2)]">

        <!-- Drag handle -->
        <div class="drag-handle absolute top-3 left-3 z-10 w-8 h-8 bg-black/40 backdrop-blur-sm rounded-lg flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing"
             @click.stop>
          <svg class="w-4 h-4 text-slate-400" fill="currentColor" viewBox="0 0 24 24">
            <circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/>
            <circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/>
            <circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/>
          </svg>
        </div>

        <!-- Badges -->
        <div class="absolute top-3 right-3 z-10 flex gap-1.5">
          <span v-if="col.kometaManaged"
                class="text-[9px] font-bold px-2 py-1 bg-amber-600/30 backdrop-blur-sm text-amber-300 border border-amber-500/30 rounded-lg uppercase tracking-wider">
            Kometa
          </span>
          <span v-if="col.smart"
                class="text-[9px] font-bold px-2 py-1 bg-blue-600/30 backdrop-blur-sm text-blue-300 border border-blue-500/30 rounded-lg uppercase tracking-wider">
            Smart
          </span>
        </div>

        <!-- Collection poster / gradient -->
        <div class="h-36 relative overflow-hidden">
          <img v-if="col.thumb"
               :src="`${col.thumb}?k=${encodeURIComponent(adminKey)}`"
               :alt="col.title"
               class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
               loading="lazy">
          <div v-else class="w-full h-full bg-gradient-to-br from-purple-900/50 to-slate-900"></div>
          <div class="absolute inset-0 bg-gradient-to-t from-slate-950 via-slate-950/40 to-transparent"></div>
        </div>

        <!-- Info -->
        <div class="p-4 -mt-8 relative">
          <h3 class="text-base font-bold text-white truncate">{{ col.title }}</h3>
          <p class="text-xs text-slate-400 mt-1">{{ col.childCount }} item{{ col.childCount !== 1 ? 's' : '' }}</p>
        </div>
      </div>
    </VueDraggable>

    <!-- Drag hint -->
    <p v-if="collections.length > 1 && !orderChanged" class="text-center text-[10px] text-slate-700 mt-4">
      Drag collections to reorder their prominence in Plex
    </p>
  </div>
</template>
