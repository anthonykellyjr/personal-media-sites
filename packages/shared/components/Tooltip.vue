<script setup>
// Generic Teleported tooltip wrapper. Wraps any element (slot) with a tooltip
// that appears on hover (desktop) and tap (mobile/touch). Renders the tooltip
// to <body> so it can never be clipped by parent overflow or stacking contexts.
//
// API:
//   tip        — string, the text shown
//   placement  — 'top' | 'bottom' (default 'bottom')
//   maxWidth   — number px for tooltip text width (default 260)
//
// Usage:
//   <Tooltip tip="CPU usage"><div class="pill">CPU 42%</div></Tooltip>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  tip:       { type: String, required: true },
  placement: { type: String, default: 'bottom' },
  maxWidth:  { type: Number, default: 260 },
})

const triggerEl = ref(null)
const open = ref(false)
const style = ref({})

// Compute fixed-position coordinates from the trigger's bounding box. Clamps
// horizontally so the tooltip never overflows the viewport — important for
// pills near the right edge of the header where centered tooltips would clip.
function position() {
  const el = triggerEl.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const margin = 8
  const half = props.maxWidth / 2
  let left = r.left + r.width / 2
  // Clamp center so left edge >= margin and right edge <= viewport - margin
  left = Math.max(margin + half, Math.min(window.innerWidth - margin - half, left))

  if (props.placement === 'top') {
    style.value = {
      bottom: `${window.innerHeight - r.top + 6}px`,
      left:   `${left}px`,
      transform: 'translateX(-50%)',
      maxWidth: `${props.maxWidth}px`,
    }
  } else {
    style.value = {
      top:  `${r.bottom + 6}px`,
      left: `${left}px`,
      transform: 'translateX(-50%)',
      maxWidth: `${props.maxWidth}px`,
    }
  }
}

function show() { open.value = true; position() }
function hide() { open.value = false }
function toggle(e) {
  e?.stopPropagation()
  open.value = !open.value
  if (open.value) position()
}

function onScroll() { if (open.value) position() }
function onClickOutside(e) {
  if (open.value && triggerEl.value && !triggerEl.value.contains(e.target)) hide()
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true, capture: true })
  window.addEventListener('resize', onScroll)
  document.addEventListener('click', onClickOutside)
})
onUnmounted(() => {
  window.removeEventListener('scroll', onScroll, { capture: true })
  window.removeEventListener('resize', onScroll)
  document.removeEventListener('click', onClickOutside)
})
</script>

<template>
  <span ref="triggerEl"
        class="inline-flex"
        @mouseenter="show"
        @mouseleave="hide"
        @focusin="show"
        @focusout="hide"
        @click="toggle">
    <slot />
  </span>
  <Teleport to="body">
    <Transition name="tooltip-fade">
      <div v-if="open"
           role="tooltip"
           class="fixed z-[9999] px-3 py-2 rounded-lg text-sm font-medium leading-snug bg-slate-900 text-slate-100 border border-white/20 shadow-xl pointer-events-none whitespace-normal"
           :style="style">
        {{ tip }}
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.tooltip-fade-enter-active,
.tooltip-fade-leave-active { transition: opacity 0.15s ease; }
.tooltip-fade-enter-from,
.tooltip-fade-leave-to { opacity: 0; }
</style>
