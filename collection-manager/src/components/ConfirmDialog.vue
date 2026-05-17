<script setup>
defineProps({
  show: { type: Boolean, default: false },
  title: { type: String, default: 'Confirm' },
  message: { type: String, default: 'Are you sure?' },
  confirmLabel: { type: String, default: 'Confirm' },
  danger: { type: Boolean, default: false },
})

defineEmits(['confirm', 'cancel'])
</script>

<template>
  <Transition name="modal">
    <div v-if="show" class="fixed inset-0 z-[90] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="$emit('cancel')"></div>
      <div class="relative bg-dark-800 border border-white/15 rounded-2xl p-6 max-w-md w-full shadow-2xl">
        <h3 class="text-lg font-bold text-white mb-2">{{ title }}</h3>
        <p class="text-sm text-slate-300 mb-6">{{ message }}</p>
        <div class="flex justify-end gap-3">
          <button @click="$emit('cancel')"
                  class="px-4 py-2 text-sm text-slate-300 hover:text-white transition-colors">
            Cancel
          </button>
          <button @click="$emit('confirm')"
                  class="px-4 py-2 text-sm font-medium rounded-lg transition-all"
                  :class="danger
                    ? 'bg-red-600 hover:bg-red-500 text-white'
                    : 'bg-purple-600 hover:bg-purple-500 text-white'">
            {{ confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-enter-active { transition: all 0.2s ease-out; }
.modal-leave-active { transition: all 0.15s ease-in; }
.modal-enter-from { opacity: 0; }
.modal-leave-to { opacity: 0; }
.modal-enter-from > div:last-child { transform: scale(0.95); }
</style>
