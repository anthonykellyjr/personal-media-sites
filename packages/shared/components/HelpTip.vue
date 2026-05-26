<script setup>
// Standalone "?" help icon with tooltip. Built on top of Tooltip so it inherits
// the Teleport + viewport-clamp behavior. Hover on desktop, tap on mobile.
//
// API:
//   tip   — string, text shown in the tooltip
//   size  — 'sm' | 'md' | 'lg' (default 'sm')
//
// Usage:
//   <HelpTip tip="Green = uploaded. Amber = waiting. Gray = not yet aired." />
import { computed } from 'vue'
import Tooltip from './Tooltip.vue'

const props = defineProps({
  tip:  { type: String, required: true },
  size: { type: String, default: 'sm' },
})

const sizeClass = computed(() => ({
  sm: 'w-4 h-4',
  md: 'w-5 h-5',
  lg: 'w-6 h-6',
}[props.size] || 'w-4 h-4'))
</script>

<template>
  <Tooltip :tip="tip">
    <button type="button"
            aria-label="Help"
            class="inline-flex items-center justify-center text-slate-400 hover:text-white transition cursor-help rounded-full"
            @click.prevent>
      <svg :class="sizeClass" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10"/>
        <path stroke-linecap="round" stroke-linejoin="round" d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 17h.01"/>
      </svg>
    </button>
  </Tooltip>
</template>
