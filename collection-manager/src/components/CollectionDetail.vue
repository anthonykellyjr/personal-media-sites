<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { useApi } from '../composables/useApi.js'
import PosterCard from './PosterCard.vue'

const props = defineProps({
  collectionKey: { type: String, required: true },
  libraryKey: { type: String, required: true },
})

const emit = defineEmits(['back', 'saved', 'deleted', 'toast'])

const { apiFetch } = useApi()

// ── Collection data ──
const collection = ref(null)
const items = ref([])
const originalKeys = ref(new Set())
const title = ref('')
const summary = ref('')
const isLoading = ref(true)
const isSaving = ref(false)
const hasChanges = ref(false)

// ── Save progress ──
const saveOverlay = ref(false)
const saveElapsed = ref(0)
const saveResult = ref(null)
let elapsedTimer = null

// ── Search ──
const searchQuery = ref('')
const searchResults = ref([])
const isSearching = ref(false)

// ── State ──
const itemKeys = computed(() => new Set(items.value.map(i => i.ratingKey)))
const isKometa = computed(() => collection.value?.kometaManaged || false)
const isSmart = computed(() => collection.value?.smart || false)
const canSave = computed(() => title.value.trim() && items.value.length > 0 && hasChanges.value && !isSmart.value)

const adminKey = computed(() => localStorage.getItem('collection_manager_admin_key') || '')

// ── Pending changes summary ──
const pendingChanges = computed(() => {
  const currentKeys = new Set(items.value.map(i => i.ratingKey))
  const adding = items.value.filter(i => !originalKeys.value.has(i.ratingKey)).length
  const removing = [...originalKeys.value].filter(k => !currentKeys.has(k)).length
  const totalItems = items.value.length
  return { adding, removing, totalItems }
})

// ── Load collection ──
const loadCollection = async () => {
  isLoading.value = true
  try {
    const data = await apiFetch(`/capi/collections/${props.collectionKey}/items`)
    collection.value = data.collection
    items.value = data.items || []
    originalKeys.value = new Set((data.items || []).map(i => i.ratingKey))
    title.value = data.collection.title || ''
    summary.value = data.collection.summary || ''
    hasChanges.value = false
  } catch (err) {
    emit('toast', 'Failed to load collection', 'error')
  } finally {
    isLoading.value = false
  }
}

onMounted(loadCollection)

onUnmounted(() => {
  if (elapsedTimer) clearInterval(elapsedTimer)
})

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
  hasChanges.value = true
}

const removeItem = (item) => {
  items.value = items.value.filter(i => i.ratingKey !== item.ratingKey)
  hasChanges.value = true
}

const onDragEnd = () => {
  hasChanges.value = true
}

const save = async () => {
  if (!canSave.value) return
  isSaving.value = true
  saveOverlay.value = true
  saveElapsed.value = 0
  saveResult.value = null

  const startTime = Date.now()
  elapsedTimer = setInterval(() => {
    saveElapsed.value = ((Date.now() - startTime) / 1000).toFixed(1)
  }, 100)

  try {
    const res = await apiFetch(`/capi/collections/${props.collectionKey}`, {
      method: 'PUT',
      body: JSON.stringify({
        title: title.value.trim(),
        summary: summary.value.trim(),
        itemKeys: items.value.map(i => i.ratingKey),
      }),
    })
    clearInterval(elapsedTimer)
    saveElapsed.value = ((Date.now() - startTime) / 1000).toFixed(1)

    saveResult.value = {
      success: true,
      stats: res.stats || {},
    }

    hasChanges.value = false
    originalKeys.value = new Set(items.value.map(i => i.ratingKey))
    emit('saved')
  } catch (err) {
    clearInterval(elapsedTimer)
    saveElapsed.value = ((Date.now() - startTime) / 1000).toFixed(1)
    saveResult.value = {
      success: false,
      error: err.message || 'Failed to save',
    }
  } finally {
    isSaving.value = false
  }
}

const closeSaveOverlay = () => {
  saveOverlay.value = false
  saveResult.value = null
}

const deleteCollection = async () => {
  try {
    await apiFetch(`/capi/collections/${props.collectionKey}`, { method: 'DELETE' })
    emit('toast', 'Collection deleted', 'success')
    emit('deleted')
  } catch (err) {
    emit('toast', err.message || 'Failed to delete', 'error')
  }
}

watch(title, () => { hasChanges.value = true })
watch(summary, () => { hasChanges.value = true })
</script>

<template>
  <div>
    <!-- Save progress overlay -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="saveOverlay"
             class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div class="bg-slate-900 border border-white/15 rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl">

            <!-- In progress -->
            <div v-if="!saveResult" class="text-center">
              <svg class="w-10 h-10 animate-spin text-purple-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
              <h3 class="text-white font-bold mb-2">Syncing to Plex</h3>
              <div class="text-xs text-slate-400 space-y-1 mb-3">
                <p v-if="pendingChanges.adding > 0">Adding {{ pendingChanges.adding }} item{{ pendingChanges.adding !== 1 ? 's' : '' }}</p>
                <p v-if="pendingChanges.removing > 0">Removing {{ pendingChanges.removing }} item{{ pendingChanges.removing !== 1 ? 's' : '' }}</p>
                <p>Reordering {{ pendingChanges.totalItems }} items</p>
              </div>
              <div class="text-lg font-mono text-purple-400">{{ saveElapsed }}s</div>
              <p class="text-[10px] text-slate-600 mt-2">All operations run locally on 10.0.0.222</p>
            </div>

            <!-- Success -->
            <div v-else-if="saveResult.success" class="text-center">
              <div class="w-12 h-12 bg-emerald-600/20 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg class="w-7 h-7 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
                </svg>
              </div>
              <h3 class="text-white font-bold mb-3">Collection Saved</h3>
              <div class="bg-slate-800/60 rounded-xl p-3 text-xs text-slate-300 space-y-1.5 text-left mb-4">
                <div class="flex justify-between">
                  <span class="text-slate-500">Total items</span>
                  <span>{{ saveResult.stats.totalItems || 0 }}</span>
                </div>
                <div v-if="saveResult.stats.added" class="flex justify-between">
                  <span class="text-slate-500">Added</span>
                  <span class="text-emerald-400">+{{ saveResult.stats.added }}</span>
                </div>
                <div v-if="saveResult.stats.removed" class="flex justify-between">
                  <span class="text-slate-500">Removed</span>
                  <span class="text-red-400">-{{ saveResult.stats.removed }}</span>
                </div>
                <div v-if="saveResult.stats.reordered" class="flex justify-between">
                  <span class="text-slate-500">Reorder ops</span>
                  <span>{{ saveResult.stats.reordered }}</span>
                </div>
                <div class="flex justify-between border-t border-white/10 pt-1.5">
                  <span class="text-slate-500">Plex API calls</span>
                  <span>{{ saveResult.stats.plexCalls || 0 }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-slate-500">Time</span>
                  <span class="font-mono">{{ saveResult.stats.elapsed || saveElapsed }}s</span>
                </div>
              </div>
              <button @click="closeSaveOverlay"
                      class="w-full py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-xl transition-colors">
                Done
              </button>
            </div>

            <!-- Error -->
            <div v-else class="text-center">
              <div class="w-12 h-12 bg-red-600/20 rounded-full flex items-center justify-center mx-auto mb-3">
                <svg class="w-7 h-7 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </div>
              <h3 class="text-white font-bold mb-2">Save Failed</h3>
              <p class="text-sm text-red-300 mb-1">{{ saveResult.error }}</p>
              <p class="text-[10px] text-slate-600 mb-4">after {{ saveElapsed }}s</p>
              <button @click="closeSaveOverlay"
                      class="w-full py-2.5 bg-slate-700 hover:bg-slate-600 text-white text-sm font-medium rounded-xl transition-colors">
                Close
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Top bar: Back + Title + Actions -->
    <div class="flex items-center gap-3 mb-6">
      <button @click="$emit('back')"
              class="p-2 text-slate-400 hover:text-white transition-colors rounded-lg hover:bg-slate-800/50">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
        </svg>
      </button>

      <!-- Editable title -->
      <input v-model="title"
             :disabled="isSmart"
             type="text"
             placeholder="Collection name..."
             class="flex-1 text-xl font-bold bg-transparent text-white placeholder-slate-600 focus:outline-none border-b border-transparent focus:border-purple-500/40 transition-colors pb-1 disabled:opacity-50" />

      <div class="flex items-center gap-2 flex-shrink-0">
        <!-- Unsaved indicator -->
        <span v-if="hasChanges" class="text-[10px] text-amber-400 uppercase tracking-wider">Unsaved</span>

        <!-- Save -->
        <button v-if="!isSmart"
                @click="save"
                :disabled="!canSave || isSaving"
                class="px-5 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-xl transition-all flex items-center gap-2">
          Save
        </button>

        <!-- Delete -->
        <button @click="deleteCollection"
                class="p-2 text-slate-500 hover:text-red-400 transition-colors rounded-lg hover:bg-red-950/30"
                title="Delete collection">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Kometa warning -->
    <div v-if="isKometa"
         class="flex items-center gap-2 p-3 mb-4 bg-amber-950/30 border border-amber-500/30 rounded-xl text-xs text-amber-300">
      <svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>
      </svg>
      Managed by <strong class="mx-1">Kometa</strong> — changes may be overwritten at 3:00 AM
    </div>

    <!-- Summary -->
    <div class="mb-4">
      <textarea v-model="summary"
                :disabled="isSmart"
                rows="2"
                placeholder="Add a description..."
                class="w-full px-3 py-2 bg-dark-900/50 border border-white/10 rounded-xl text-sm text-slate-300 placeholder-slate-600 focus:outline-none focus:border-purple-500/30 transition-colors resize-none disabled:opacity-50"></textarea>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="py-20 flex justify-center">
      <div class="flex gap-2">
        <span class="w-3 h-3 rounded-full bg-purple-500 animate-bounce" style="animation-delay: 0s"></span>
        <span class="w-3 h-3 rounded-full bg-fuchsia-500 animate-bounce" style="animation-delay: 0.15s"></span>
        <span class="w-3 h-3 rounded-full bg-pink-500 animate-bounce" style="animation-delay: 0.3s"></span>
      </div>
    </div>

    <template v-else>
      <!-- Two-column layout: items + search sidebar -->
      <div class="flex gap-6" :class="isSmart ? '' : 'flex-col lg:flex-row'">

        <!-- Items (main area) -->
        <div class="flex-1 min-w-0">
          <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">
            {{ items.length }} Item{{ items.length !== 1 ? 's' : '' }}
          </h3>

          <div v-if="items.length === 0" class="text-center py-12 text-slate-600">
            <p class="text-sm">No items in this collection</p>
            <p class="text-xs mt-1">Search to start adding items</p>
          </div>

          <VueDraggable
            v-else
            v-model="items"
            :animation="200"
            :disabled="isSmart"
            ghost-class="sortable-ghost"
            @end="onDragEnd"
            class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
            <PosterCard
              v-for="(item, idx) in items"
              :key="item.ratingKey"
              :item="item"
              :position="idx + 1"
              :removable="!isSmart"
              @remove="removeItem"
            />
          </VueDraggable>
        </div>

        <!-- Always-visible search panel (Letterboxd-style) -->
        <div v-if="!isSmart" class="w-full lg:w-72 flex-shrink-0">
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
    </template>
  </div>
</template>

<style scoped>
.fade-enter-active { transition: opacity 0.2s ease-out; }
.fade-leave-active { transition: opacity 0.15s ease-in; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
