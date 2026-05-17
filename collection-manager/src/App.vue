<script setup>
import { ref, watch } from 'vue'
import { useApi } from './composables/useApi.js'

import AuthGate from './components/AuthGate.vue'
import LibrarySelector from './components/LibrarySelector.vue'
import CollectionsGrid from './components/CollectionsGrid.vue'
import CollectionDetail from './components/CollectionDetail.vue'
import NewCollection from './components/NewCollection.vue'
import Toast from './components/Toast.vue'

const { apiFetch, clearAdminKey } = useApi()

// ── Auth ──
const isAuthenticated = ref(false)

// ── Libraries ──
const libraries = ref([])
const selectedLibrary = ref('')

// ── Navigation: 'grid' or 'detail' or 'new' ──
const view = ref('grid')
const activeCollectionKey = ref('')
const gridRef = ref(null)

// ── Toast ──
const toast = ref({ show: false, message: '', type: 'success' })

const showToast = (message, type = 'success') => {
  toast.value = { show: true, message, type }
}

// ── Auth ──
const onAuthenticated = async () => {
  isAuthenticated.value = true
  try {
    const data = await apiFetch('/capi/libraries')
    console.debug('Fetched libraries:', JSON.stringify(data, null, 2));
    libraries.value = data.libraries || []
    if (libraries.value.length > 0) {
      const preferred = libraries.value.find(l => l.title.toLowerCase() === 'movies')
      selectedLibrary.value = (preferred || libraries.value[0]).key
    }
  } catch (err) {
    showToast('Failed to load libraries', 'error')
  }
}

const logout = () => {
  clearAdminKey()
  isAuthenticated.value = false
  libraries.value = []
  selectedLibrary.value = ''
  view.value = 'grid'
}

// ── Navigation ──
const openCollection = (ratingKey) => {
  activeCollectionKey.value = ratingKey
  view.value = 'detail'
}

const startNewCollection = () => {
  activeCollectionKey.value = ''
  view.value = 'new'
}

const backToGrid = () => {
  view.value = 'grid'
  activeCollectionKey.value = ''
  gridRef.value?.refresh()
}

const onCollectionSaved = () => {
  // Stay on detail view, grid will refresh when user goes back
}

const onCollectionDeleted = () => {
  backToGrid()
}

const onCollectionCreated = (newKey) => {
  // After creating, jump to editing the new collection
  activeCollectionKey.value = newKey
  view.value = 'detail'
  gridRef.value?.refresh()
}

// ── Library change resets view ──
watch(selectedLibrary, () => {
  view.value = 'grid'
  activeCollectionKey.value = ''
})
</script>

<template>
  <!-- Auth Gate -->
  <AuthGate v-if="!isAuthenticated" @authenticated="onAuthenticated" />

  <!-- Main App -->
  <div v-else class="min-h-screen bg-gradient-to-br from-dark-900 via-dark-800 to-dark-900">
    <!-- Header -->
    <header class="sticky top-0 z-30 bg-dark-900/80 backdrop-blur-xl border-b border-white/10">
      <div class="max-w-6xl mx-auto px-4 py-3 flex items-center gap-4">
        <!-- Title -->
        <h1 class="text-lg font-bold text-white flex-shrink-0 cursor-pointer" @click="backToGrid">
          <span class="bg-gradient-to-r from-purple-400 to-fuchsia-400 bg-clip-text text-transparent">Collection Manager</span>
        </h1>

        <!-- Library selector -->
        <div class="flex-1 flex justify-center">
          <LibrarySelector
            v-model="selectedLibrary"
            :libraries="libraries"
          />
        </div>

        <!-- Logout -->
        <button @click="logout"
                class="flex-shrink-0 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                title="Logout">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
          </svg>
        </button>
      </div>
    </header>

    <!-- Content -->
    <main class="max-w-6xl mx-auto p-4">
      <!-- Grid view (default) -->
      <CollectionsGrid
        v-if="view === 'grid'"
        ref="gridRef"
        :library-key="selectedLibrary"
        @select="openCollection"
        @new="startNewCollection"
        @toast="showToast"
      />

      <!-- Detail view (editing existing collection) -->
      <CollectionDetail
        v-if="view === 'detail' && activeCollectionKey"
        :key="activeCollectionKey"
        :collection-key="activeCollectionKey"
        :library-key="selectedLibrary"
        @back="backToGrid"
        @saved="onCollectionSaved"
        @deleted="onCollectionDeleted"
        @toast="showToast"
      />

      <!-- New collection view -->
      <NewCollection
        v-if="view === 'new'"
        :library-key="selectedLibrary"
        @back="backToGrid"
        @created="onCollectionCreated"
        @toast="showToast"
      />
    </main>

    <!-- Toast -->
    <Toast
      :show="toast.show"
      :message="toast.message"
      :type="toast.type"
      @close="toast.show = false"
    />
  </div>
</template>
