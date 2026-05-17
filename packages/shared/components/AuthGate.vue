<script setup>
import { ref } from 'vue'
import LoadingDots from './LoadingDots.vue'

const props = defineProps({
  title: { type: String, default: 'Authentication Required' },
  subtitle: { type: String, default: 'Enter your key to continue' },
  apiFetch: { type: Function, required: true },
  setAuthKey: { type: Function, required: true },
  authKey: { type: String, default: '' },
  testEndpoint: { type: String, required: true },
  accentColor: { type: String, default: 'purple' },
})

const emit = defineEmits(['authenticated'])

const keyInput = ref('')
const isChecking = ref(false)
const error = ref('')
const showKey = ref(false)

const tryAuth = async () => {
  if (!keyInput.value.trim()) return
  isChecking.value = true
  error.value = ''

  props.setAuthKey(keyInput.value.trim())

  try {
    await props.apiFetch(props.testEndpoint)
    emit('authenticated')
  } catch (e) {
    error.value = e.message === 'Unauthorized' ? 'Invalid key' : 'Could not connect to API'
    props.setAuthKey('')
  } finally {
    isChecking.value = false
  }
}

const autoCheck = async () => {
  if (!props.authKey) return
  isChecking.value = true
  try {
    await props.apiFetch(props.testEndpoint)
    emit('authenticated')
  } catch {
    props.setAuthKey('')
  } finally {
    isChecking.value = false
  }
}

autoCheck()
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <div class="bg-slate-950/60 backdrop-blur-xl border border-white/15 rounded-2xl p-8 max-w-sm w-full shadow-2xl">
      <h1 class="text-xl font-bold text-white mb-1">{{ title }}</h1>
      <p class="text-sm text-slate-400 mb-6">{{ subtitle }}</p>

      <div v-if="isChecking" class="flex justify-center py-8">
        <LoadingDots />
      </div>

      <form v-else @submit.prevent="tryAuth" class="space-y-4">
        <div class="relative">
          <input
            v-model="keyInput"
            :type="showKey ? 'text' : 'password'"
            placeholder="Access key"
            autocomplete="current-password"
            class="w-full px-4 py-3 pr-11 bg-dark-900 border border-white/15 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/60 transition-colors"
          />
          <button type="button" @click="showKey = !showKey"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors">
            <svg v-if="showKey" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L6.59 6.59m7.532 7.532l3.29 3.29M3 3l18 18"/>
            </svg>
            <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
            </svg>
          </button>
        </div>
        <p v-if="error" class="text-sm text-red-400">{{ error }}</p>
        <button type="submit"
                :disabled="!keyInput.trim()"
                class="w-full py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-xl transition-all">
          Authenticate
        </button>
      </form>
    </div>
  </div>
</template>
