<script setup>
defineProps({
  libraries: { type: Array, default: () => [] },
  modelValue: { type: String, default: '' },
})

defineEmits(['update:modelValue'])
</script>

<template>
  <div class="flex gap-1.5 flex-wrap">
    <button
      v-for="lib in libraries"
      :key="lib.key"
      @click="$emit('update:modelValue', lib.key)"
      class="px-3 py-1.5 text-xs font-medium rounded-lg transition-all"
      :class="modelValue === lib.key
        ? 'bg-purple-600 text-white shadow-lg shadow-purple-500/20'
        : 'bg-slate-800/60 text-slate-400 hover:text-white hover:bg-slate-700/60 border border-white/10'">
      {{ lib.title }}
      <span class="ml-1 opacity-60">{{ lib.count }}</span>
    </button>
  </div>
</template>
