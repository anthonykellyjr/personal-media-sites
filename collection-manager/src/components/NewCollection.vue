<script setup>
import { ref, watch, computed } from 'vue'
import { useApi } from '../composables/useApi.js'
import { VueDraggable } from 'vue-draggable-plus'
import PosterCard from './PosterCard.vue'

const props = defineProps({
  libraryKey: { type: String, required: true },
})

const emit = defineEmits(['back', 'created', 'toast'])

const { apiFetch } = useApi()

// ── Form ──
const title = ref('')
const summary = ref('')
const items = ref([])
const isSaving = ref(false)

// ── Search ──
const searchQuery = ref('')
const searchResults = ref([])
const isSearching = ref(false)

const adminKey = computed(() => localStorage.getItem('collection_manager_admin_key') || '')
const itemKeys = computed(() => new Set(items.value.map(i => i.ratingKey)))
const canSave = computed(() => title.value.trim() && items.value.length > 0)

// ── Search library ──
let searchTimer = null
watch(searchQuery, (q) => {
  clearTimeout(searchTimer)
  if (!q.trim()) {
    searchResults.value = []
    return
  }
  searchTimer = setTimeout(async () => {
    isSearching.value = true
    try {
      const data = await apiFetch(`/capi/libraries/${props.libraryKey}/items?search=${encodeURIComponent(q)}&size=20`)
      searchResults.value = data.items || []
    } catch {
      searchResults.value = []
    } finally {
      isSearching.value = false
    }
  }, 300)
})

// ── Actions ──
const addItem = (item) => {
  if (itemKeys.value.has(item.ratingKey)) return
  items.value = [...items.value, item]
}

const removeItem = (item) => {
  items.value = items.value.filter(i => i.ratingKey !== item.ratingKey)
}

const save = async () => {
  if (!canSave.value || isSaving.value) return
  isSaving.value = true
  try {
    const data = await apiFetch('/capi/collections', {
      method: 'POST',
      body: JSON.stringify({
        libraryKey: props.libraryKey,
        title: title.value.trim(),
        summary: summary.value.trim(),
        itemKeys: items.value.map(i => i.ratingKey),
      }),
    })
    emit('toast', 'Collection created', 'success')
    emit('created', data.collection?.ratingKey || '')
  } catch (err) {
    emit('toast', err.message || 'Failed to create', 'error')
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div>
    <!-- Top bar -->
    <div class="flex items-center gap-3 mb-6">
      <button @click="$emit('back')"
              class="p-2 text-slate-400 hover:text-white transition-colors rounded-lg hover:bg-slate-800/50">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
      </button>

      <input v-model="title"
             type="text"
             placeholder="New collection name..."
             class="flex-1 text-xl font-bold bg-transparent text-white placeholder-slate-600 focus:outline-none border-b border-transparent focus:border-purple-500/40 transition-colors pb-1"
             autofocus />

      <button @click="save"
              :disabled="!canSave || isSaving"
              class="px-5 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-xl transition-all flex items-center gap-2">
        <svg v-if="isSaving" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        {{ isSaving ? 'Creating...' : 'Create' }}
      </button>
    </div>

    <!-- Summary -->
    <div class="mb-4">
      <textarea v-model="summary"
                rows="2"
                placeholder="Add a description..."
                class="w-full px-3 py-2 bg-dark-900/50 border border-white/10 rounded-xl text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-purple-500/30 transition-colors resize-none"></textarea>
    </div>

    <!-- Two-column: items + search -->
    <div class="flex gap-6 flex-col lg:flex-row">

      <!-- Items (main area) -->
      <div class="flex-1 min-w-0">
        <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">
          {{ items.length }} Item{{ items.length !== 1 ? 's' : '' }} Added
        </h3>

        <div v-if="items.length === 0" class="text-center py-12 text-slate-600">
          <p class="text-sm">Search to start adding items</p>
        </div>

        <VueDraggable
          v-else
          v-model="items"
          :animation="200"
          ghost-class="sortable-ghost"
          class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
          <PosterCard
            v-for="item in items"
            :key="item.ratingKey"
            :item="item"
            :removable="true"
            @remove="removeItem"
          />
        </VueDraggable>
      </div>

      <!-- Always-visible search (Letterboxd-style) -->
      <div class="w-full lg:w-72 flex-shrink-0">
        <div class="lg:sticky lg:top-20">
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Add a Film</h3>
          <div class="p-3 bg-slate-900/50 border border-white/10 rounded-2xl">
            <div class="relative mb-2">
              <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
              <input v-model="searchQuery"
                     type="text"
                     placeholder="Search library..."
                     class="w-full pl-10 pr-4 py-2 bg-dark-900 border border-white/15 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/60 transition-colors" />
            </div>

            <div v-if="isSearching" class="flex justify-center py-3">
              <svg class="w-5 h-5 animate-spin text-slate-500" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
            </div>

            <div v-else-if="searchResults.length > 0" class="max-h-[400px] overflow-y-auto thin-scrollbar space-y-0.5">
              <button v-for="result in searchResults"
                      :key="result.ratingKey"
                      @click="addItem(result)"
                      :disabled="itemKeys.has(result.ratingKey)"
                      class="w-full flex items-center gap-2.5 p-2 rounded-lg text-left transition-colors"
                      :class="itemKeys.has(result.ratingKey)
                        ? 'opacity-40 cursor-not-allowed'
                        : 'hover:bg-slate-800/60 cursor-pointer'">
                <div class="w-8 h-12 flex-shrink-0 rounded-md overflow-hidden bg-slate-800">
                  <img v-if="result.thumb"
                       :src="`${result.thumb}?k=${encodeURIComponent(adminKey)}`"
                       :alt="result.title"
                       class="w-full h-full object-cover"
                       loading="lazy" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="text-xs text-white truncate">{{ result.title }}</div>
                  <div class="text-[10px] text-slate-500">{{ result.year }}</div>
                </div>
                <svg v-if="itemKeys.has(result.ratingKey)" class="w-4 h-4 text-purple-500 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                <svg v-else class="w-4 h-4 text-slate-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                </svg>
              </button>
            </div>

            <div v-else-if="searchQuery && !isSearching" class="text-center py-3 text-xs text-slate-600">
              No results for "{{ searchQuery }}"
            </div>

            <div v-else class="text-center py-3 text-xs text-slate-600">
              Type to search
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
