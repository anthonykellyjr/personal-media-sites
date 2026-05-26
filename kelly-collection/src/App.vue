<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { useApi } from './composables/useApi.js'
import { PageHeader } from '@webhead/shared'

const { kellyKey, setKellyKey, clearKellyKey, apiFetch } = useApi()

// ── Auth state ──
const isAuthenticated = ref(false)
const codeInput = ref('')
const authError = ref('')
const isAuthChecking = ref(false)

// ── Collection state ──
const collection = ref(null)
const items = ref([])
const originalKeys = ref(new Set())
const isLoading = ref(true)
const isSaving = ref(false)
const hasChanges = ref(false)

// ── Save overlay ──
const saveOverlay = ref(false)
const saveElapsed = ref(0)
const saveResult = ref(null)
let elapsedTimer = null

// ── Search ──
const searchQuery = ref('')
const searchResults = ref([])
const isSearching = ref(false)

// ── Computed ──
const itemKeys = computed(() => new Set(items.value.map(i => i.ratingKey)))
const canSave = computed(() => items.value.length > 0 && hasChanges.value)

const pendingChanges = computed(() => {
  const adding = items.value.filter(i => !originalKeys.value.has(i.ratingKey)).length
  const removing = [...originalKeys.value].filter(k => !itemKeys.value.has(k)).length
  return { adding, removing, totalItems: items.value.length }
})

// ── Auth ──
const tryAuth = async () => {
  if (!codeInput.value.trim()) return
  isAuthChecking.value = true
  authError.value = ''
  setKellyKey(codeInput.value.trim())

  try {
    await loadCollection()
    isAuthenticated.value = true
  } catch (e) {
    authError.value = e.message === 'Unauthorized' ? 'Invalid code' : 'Could not connect'
    clearKellyKey()
    isLoading.value = true
  } finally {
    isAuthChecking.value = false
  }
}

const autoCheck = async () => {
  if (!kellyKey.value) return
  isAuthChecking.value = true
  try {
    await loadCollection()
    isAuthenticated.value = true
  } catch {
    clearKellyKey()
    isLoading.value = true
  } finally {
    isAuthChecking.value = false
  }
}

const logout = () => {
  clearKellyKey()
  isAuthenticated.value = false
  collection.value = null
  items.value = []
}

// ── Load collection ──
const loadCollection = async () => {
  isLoading.value = true
  const data = await apiFetch('/capi/kelly/collection')
  collection.value = data.collection
  items.value = data.items || []
  originalKeys.value = new Set((data.items || []).map(i => i.ratingKey))
  hasChanges.value = false
  isLoading.value = false
}

// ── Search ──
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
      const data = await apiFetch(`/capi/kelly/search?q=${encodeURIComponent(q)}`)
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
    const res = await apiFetch('/capi/kelly/collection', {
      method: 'PUT',
      body: JSON.stringify({
        itemKeys: items.value.map(i => i.ratingKey),
      }),
    })
    clearInterval(elapsedTimer)
    saveElapsed.value = ((Date.now() - startTime) / 1000).toFixed(1)

    saveResult.value = { success: true, stats: res.stats || {} }
    hasChanges.value = false
    originalKeys.value = new Set(items.value.map(i => i.ratingKey))
  } catch (err) {
    clearInterval(elapsedTimer)
    saveElapsed.value = ((Date.now() - startTime) / 1000).toFixed(1)
    saveResult.value = { success: false, error: err.message || 'Failed to save' }
  } finally {
    isSaving.value = false
  }
}

const closeSaveOverlay = () => {
  saveOverlay.value = false
  saveResult.value = null
}

onMounted(autoCheck)
onUnmounted(() => { if (elapsedTimer) clearInterval(elapsedTimer) })
</script>

<template>
  <!-- ═══ AUTH GATE ═══ -->
  <div v-if="!isAuthenticated" class="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-dark-900 via-dark-800 to-dark-900">
    <div class="bg-slate-950/60 backdrop-blur-xl border border-white/15 rounded-2xl p-8 max-w-sm w-full shadow-2xl">
      <!-- Totoro GIF -->
      <div class="flex justify-center mb-4">
        <img src="https://media1.tenor.com/m/_4v7UZ7EMgAAAAAC/totoro-sleep.gif"
             alt="Totoro"
             class="w-full max-h-[40vh] object-contain rounded-xl" />
      </div>

      <h1 class="text-xl font-bold text-white mb-1">Kelly's Collection</h1>
      <p class="text-sm text-slate-400 mb-6">Enter your access code</p>

      <div v-if="isAuthChecking" class="flex justify-center py-8">
        <div class="flex gap-2">
          <span class="w-3 h-3 rounded-full bg-pink-500 animate-bounce" style="animation-delay: 0s"></span>
          <span class="w-3 h-3 rounded-full bg-rose-500 animate-bounce" style="animation-delay: 0.15s"></span>
          <span class="w-3 h-3 rounded-full bg-pink-400 animate-bounce" style="animation-delay: 0.3s"></span>
        </div>
      </div>

      <form v-else @submit.prevent="tryAuth" class="space-y-4">
        <input
          v-model="codeInput"
          type="password"
          inputmode="numeric"
          placeholder="Access code"
          autocomplete="current-password"
          class="w-full px-4 py-3 bg-dark-900 border border-white/15 rounded-xl text-white text-center text-lg tracking-[0.3em] placeholder-slate-500 focus:outline-none focus:border-pink-500/60 transition-colors"
        />
        <p v-if="authError" class="text-sm text-red-400 text-center">{{ authError }}</p>
        <button type="submit"
                :disabled="!codeInput.trim()"
                class="w-full py-3 bg-pink-600 hover:bg-pink-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-xl transition-all">
          Enter
        </button>
      </form>
    </div>
  </div>

  <!-- ═══ MAIN APP ═══ -->
  <div v-else class="min-h-screen bg-gradient-to-br from-dark-900 via-dark-800 to-dark-900">

    <PageHeader variant="bar" title="Kelly's Collection">
      <template #title>
        <h1 class="text-base sm:text-lg font-bold flex-shrink-0">
          <span class="bg-gradient-to-r from-pink-400 to-rose-400 bg-clip-text text-transparent">Kelly's Collection</span>
        </h1>
      </template>

      <span v-if="hasChanges" class="text-[10px] text-amber-400 uppercase tracking-wider">Unsaved</span>

      <button @click="save"
              :disabled="!canSave || isSaving"
              class="px-5 py-2 bg-pink-600 hover:bg-pink-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-xl transition-all">
        Save
      </button>

      <button @click="logout"
              class="p-2 text-slate-500 hover:text-slate-300 transition-colors"
              title="Logout">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
        </svg>
      </button>
    </PageHeader>

    <!-- Content -->
    <main class="max-w-6xl mx-auto p-4">

      <!-- Loading -->
      <div v-if="isLoading" class="py-20 flex justify-center">
        <div class="flex gap-2">
          <span class="w-3 h-3 rounded-full bg-pink-500 animate-bounce" style="animation-delay: 0s"></span>
          <span class="w-3 h-3 rounded-full bg-rose-500 animate-bounce" style="animation-delay: 0.15s"></span>
          <span class="w-3 h-3 rounded-full bg-pink-400 animate-bounce" style="animation-delay: 0.3s"></span>
        </div>
      </div>

      <!-- Collection editor -->
      <template v-else>
        <div class="flex gap-6 flex-col lg:flex-row">

          <!-- Items grid (main area) -->
          <div class="flex-1 min-w-0">
            <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">
              {{ items.length }} Movie{{ items.length !== 1 ? 's' : '' }}
            </h3>

            <div v-if="items.length === 0" class="text-center py-12 text-slate-600">
              <p class="text-sm">Your collection is empty</p>
              <p class="text-xs mt-1">Search to start adding movies</p>
            </div>

            <VueDraggable
              v-else
              v-model="items"
              :animation="200"
              ghost-class="sortable-ghost"
              @end="onDragEnd"
              class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">

              <!-- Poster card (inline) -->
              <div v-for="(item, idx) in items"
                   :key="item.ratingKey"
                   class="group relative bg-slate-950/60 border border-white/10 rounded-xl overflow-hidden cursor-grab active:cursor-grabbing transition-colors duration-200 hover:border-pink-500/40">

                <div class="relative w-full aspect-[2/3] overflow-hidden">
                  <!-- Poster -->
                  <img v-if="item.thumb"
                       :src="`${item.thumb}?k=${encodeURIComponent(kellyKey)}`"
                       :alt="item.title"
                       class="w-full h-full object-cover"
                       loading="lazy">
                  <div v-else class="w-full h-full bg-slate-800 flex items-center justify-center">
                    <span class="text-slate-600 text-xl">?</span>
                  </div>

                  <!-- Gradient -->
                  <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-60"></div>

                  <!-- Position badge -->
                  <div class="absolute top-1.5 left-1.5 min-w-[22px] h-[22px] px-1 bg-pink-600/90 rounded-full flex items-center justify-center z-10">
                    <span class="text-[10px] font-bold text-white leading-none">#{{ idx + 1 }}</span>
                  </div>

                  <!-- Remove button -->
                  <button @click.stop="removeItem(item)"
                          class="absolute top-1.5 right-1.5 w-6 h-6 bg-red-600/80 hover:bg-red-500 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                  </button>
                </div>

                <!-- Title -->
                <div class="absolute bottom-0 inset-x-0 p-2 bg-gradient-to-t from-slate-950/90 to-transparent">
                  <div class="text-[11px] font-bold text-white truncate drop-shadow-md">{{ item.title }}</div>
                  <div v-if="item.year" class="text-[10px] text-slate-300 mt-0.5">{{ item.year }}</div>
                </div>
              </div>
            </VueDraggable>
          </div>

          <!-- Search sidebar -->
          <div class="w-full lg:w-72 flex-shrink-0">
            <div class="lg:sticky lg:top-20">
              <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Add a Movie</h3>
              <div class="p-3 bg-slate-900/50 border border-white/10 rounded-2xl">
                <div class="relative mb-2">
                  <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                  </svg>
                  <input v-model="searchQuery"
                         type="text"
                         placeholder="Search movies..."
                         class="w-full pl-10 pr-4 py-2 bg-dark-900 border border-white/15 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-pink-500/60 transition-colors" />
                </div>

                <!-- Searching spinner -->
                <div v-if="isSearching" class="flex justify-center py-3">
                  <svg class="w-5 h-5 animate-spin text-slate-500" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                  </svg>
                </div>

                <!-- Results -->
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
                           :src="`${result.thumb}?k=${encodeURIComponent(kellyKey)}`"
                           :alt="result.title"
                           class="w-full h-full object-cover"
                           loading="lazy" />
                    </div>
                    <div class="flex-1 min-w-0">
                      <div class="text-xs text-white truncate">{{ result.title }}</div>
                      <div class="text-[10px] text-slate-500">{{ result.year }}</div>
                    </div>
                    <svg v-if="itemKeys.has(result.ratingKey)" class="w-4 h-4 text-pink-500 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
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
    </main>

    <!-- ═══ SAVE OVERLAY ═══ -->
    <Teleport to="body">
      <Transition name="fade">
        <div v-if="saveOverlay"
             class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div class="bg-slate-900 border border-white/15 rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl">

            <!-- In progress -->
            <div v-if="!saveResult" class="text-center">
              <svg class="w-10 h-10 animate-spin text-pink-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
              </svg>
              <h3 class="text-white font-bold mb-2">Saving to Plex</h3>
              <div class="text-xs text-slate-400 space-y-1 mb-3">
                <p v-if="pendingChanges.adding > 0">Adding {{ pendingChanges.adding }} movie{{ pendingChanges.adding !== 1 ? 's' : '' }}</p>
                <p v-if="pendingChanges.removing > 0">Removing {{ pendingChanges.removing }} movie{{ pendingChanges.removing !== 1 ? 's' : '' }}</p>
                <p>Reordering {{ pendingChanges.totalItems }} movies</p>
              </div>
              <div class="text-lg font-mono text-pink-400">{{ saveElapsed }}s</div>
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
                  <span class="text-slate-500">Total movies</span>
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
                <div class="flex justify-between border-t border-white/10 pt-1.5">
                  <span class="text-slate-500">Time</span>
                  <span class="font-mono">{{ saveResult.stats.elapsed || saveElapsed }}s</span>
                </div>
              </div>
              <button @click="closeSaveOverlay"
                      class="w-full py-2.5 bg-pink-600 hover:bg-pink-500 text-white text-sm font-medium rounded-xl transition-colors">
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
  </div>
</template>

<style scoped>
.fade-enter-active { transition: opacity 0.2s ease-out; }
.fade-leave-active { transition: opacity 0.15s ease-in; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
