<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  status: { type: String, default: 'checking', validator: v => ['online', 'offline', 'checking'].includes(v) }
})

const dotClass = computed(() => ({
  online:   'bg-emerald-500 text-emerald-500',
  offline:  'bg-rose-500 text-rose-500',
  checking: 'bg-slate-500 text-slate-500'
})[props.status])

const badgeClass = computed(() => ({
  online:   'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
  offline:  'bg-rose-500/10 text-rose-400 border border-rose-500/20',
  checking: 'bg-slate-700/50 text-slate-400'
})[props.status])

const badgeText = computed(() => ({
  online:   'ONLINE',
  offline:  'OFFLINE',
  checking: 'CHECKING'
})[props.status])
</script>

<template>
  <div class="flex items-center gap-3 bg-slate-950/50 backdrop-blur-sm border border-white/10 rounded-xl px-4 sm:px-5 h-12">
    <div class="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-[0_0_8px_currentColor]"
         :class="dotClass"></div>
    <span class="text-sm font-medium text-slate-300 truncate">{{ label }}</span>
    <span class="text-[10px] px-2 py-0.5 rounded-md font-bold ml-auto tracking-wider uppercase flex-shrink-0"
          :class="badgeClass">
      {{ badgeText }}
    </span>
  </div>
</template>
