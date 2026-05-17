<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: 'Search library...' },
})

const emit = defineEmits(['update:modelValue'])

const localValue = ref(props.modelValue)
let debounceTimer = null

watch(localValue, (val) => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('update:modelValue', val)
  }, 300)
})

watch(() => props.modelValue, (val) => {
  if (val !== localValue.value) localValue.value = val
})

const clear = () => {
  localValue.value = ''
  emit('update:modelValue', '')
}
</script>

<template>
  <div class="relative">
    <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
    </svg>
    <input
      v-model="localValue"
      type="text"
      :placeholder="placeholder"
      class="w-full pl-10 pr-8 py-2.5 bg-dark-900 border border-white/15 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/60 transition-colors"
    />
    <button v-if="localValue"
            @click="clear"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  </div>
</template>
