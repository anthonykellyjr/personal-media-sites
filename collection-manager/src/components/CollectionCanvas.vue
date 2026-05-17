<script setup>
import { computed } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import PosterCard from './PosterCard.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'remove'])

const items = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const removeItem = (item) => {
  emit('remove', item)
}
</script>

<template>
  <div class="border-2 border-dashed rounded-xl transition-colors min-h-[120px]"
       :class="items.length ? 'border-purple-500/30 bg-purple-950/10' : 'border-slate-700/50 bg-slate-900/30'">

    <!-- Empty state -->
    <div v-if="items.length === 0"
         class="flex flex-col items-center justify-center py-10 text-slate-600">
      <svg class="w-10 h-10 mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
      </svg>
      <p class="text-sm">Click posters above to add them here</p>
      <p class="text-xs mt-1 text-slate-700">Then drag to reorder</p>
    </div>

    <!-- Sortable grid -->
    <VueDraggable
      v-else
      v-model="items"
      :animation="200"
      ghost-class="sortable-ghost"
      chosen-class="sortable-chosen"
      drag-class="sortable-drag"
      class="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 gap-2 p-3">
      <PosterCard
        v-for="item in items"
        :key="item.ratingKey"
        :item="item"
        :removable="true"
        :compact="true"
        @remove="removeItem"
      />
    </VueDraggable>

    <!-- Item count -->
    <div v-if="items.length" class="px-3 pb-2 text-right">
      <span class="text-[10px] text-slate-500">{{ items.length }} item{{ items.length !== 1 ? 's' : '' }}</span>
    </div>
  </div>
</template>
