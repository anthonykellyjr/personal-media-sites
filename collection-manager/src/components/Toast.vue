<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  message: { type: String, default: '' },
  type: { type: String, default: 'success' }, // success | error
  show: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])

watch(() => props.show, (val) => {
  if (val) {
    setTimeout(() => emit('close'), 3000)
  }
})
</script>

<template>
  <Transition name="toast">
    <div v-if="show"
         class="fixed top-4 right-4 z-[100] px-4 py-3 rounded-xl backdrop-blur-xl border shadow-2xl flex items-center gap-2 max-w-sm"
         :class="type === 'error'
           ? 'bg-red-950/80 border-red-500/40 text-red-200'
           : 'bg-emerald-950/80 border-emerald-500/40 text-emerald-200'">
      <svg v-if="type === 'success'" class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
      </svg>
      <svg v-else class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <span class="text-sm">{{ message }}</span>
    </div>
  </Transition>
</template>

<style scoped>
.toast-enter-active { transition: all 0.3s ease-out; }
.toast-leave-active { transition: all 0.3s ease-in; }
.toast-enter-from { opacity: 0; transform: translateX(100%); }
.toast-leave-to { opacity: 0; transform: translateX(100%); }
</style>
