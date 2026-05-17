<script setup>
import { ref, onMounted, computed } from 'vue'

const videos = ref([])
const loading = ref(true)
const error = ref(null)
const selectedCategory = ref('All')

const categories = computed(() => {
  const cats = [...new Set(videos.value.map(v => v.category).filter(Boolean))]
  return ['All', ...cats]
})

const filteredVideos = computed(() => {
  if (selectedCategory.value === 'All') return videos.value
  return videos.value.filter(v => v.category === selectedCategory.value)
})

onMounted(async () => {
  try {
    const res = await fetch('/tutorials/videos/videos.json')
    if (!res.ok) throw new Error('Failed to load tutorials')
    videos.value = await res.json()
  } catch (e) {
    error.value = 'Could not load tutorials'
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="min-h-screen p-4 sm:p-6 lg:p-8">
    <div class="max-w-7xl mx-auto">
      <!-- Header -->
      <header class="text-center mb-8">
        <h1 class="text-3xl sm:text-4xl font-bold text-white mb-2">Plex Tutorials</h1>
        <p class="text-slate-400 text-lg">Setup guides and tips for the best experience</p>
      </header>

      <!-- Category Filter -->
      <div v-if="categories.length > 2" class="flex flex-wrap justify-center gap-2 mb-8">
        <button
          v-for="cat in categories"
          :key="cat"
          @click="selectedCategory = cat"
          :class="[
            'px-4 py-1.5 rounded-full text-sm font-medium transition-colors',
            selectedCategory === cat
              ? 'bg-indigo-600 text-white'
              : 'bg-white/10 text-slate-300 hover:bg-white/20'
          ]"
        >
          {{ cat }}
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="text-center py-20">
        <div class="inline-block w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="text-center py-20">
        <p class="text-slate-400">{{ error }}</p>
      </div>

      <!-- Empty State -->
      <div v-else-if="filteredVideos.length === 0" class="text-center py-20">
        <p class="text-slate-400">No tutorials yet — check back soon!</p>
      </div>

      <!-- Video Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        <div
          v-for="video in filteredVideos"
          :key="video.id"
          class="bg-white/5 rounded-xl overflow-hidden border border-white/10 hover:border-indigo-500/50 transition-colors"
        >
          <!-- Video Player -->
          <div class="relative aspect-video bg-black">
            <video
              :src="'/tutorials/videos/' + video.filename"
              :poster="video.thumbnail ? '/tutorials/videos/' + video.thumbnail : undefined"
              controls
              preload="metadata"
              class="w-full h-full object-contain"
            ></video>
          </div>

          <!-- Info -->
          <div class="p-4">
            <div class="flex items-start justify-between gap-2">
              <h2 class="text-white font-semibold text-lg leading-tight">{{ video.title }}</h2>
              <span
                v-if="video.duration"
                class="text-xs text-slate-500 bg-white/5 px-2 py-0.5 rounded shrink-0"
              >{{ video.duration }}</span>
            </div>
            <p v-if="video.description" class="text-slate-400 text-sm mt-2 leading-relaxed">{{ video.description }}</p>
            <span
              v-if="video.category"
              class="inline-block mt-3 text-xs text-indigo-400 bg-indigo-500/10 px-2.5 py-1 rounded-full"
            >{{ video.category }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
