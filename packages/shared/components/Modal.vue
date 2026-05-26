<script setup>
// Shared modal wrapper for the websites workspace.
//
// API:
//   v-model         — boolean, controls open/closed
//   title           — string, header text (optional if you use the #header slot)
//   maxWidth        — CSS max-width for the panel; accepts a number (px) or
//                     string ('md' | 'lg' | 'xl' | '600px'). Default 640.
//   borderClass     — extra Tailwind classes for the panel border (theme accent).
//                     Example: 'border-fuchsia-500/30' for the Quick Request modal.
//   closeOnEsc      — boolean, default true
//   closeOnBackdrop — boolean, default true
//   tabs            — optional array of {id, label, count?, accent?} for a tab
//                     bar rendered below the header. When provided, default-slot
//                     content is replaced by per-tab slots named #tab-<id>.
//   activeTab       — v-model:active-tab; the currently selected tab id.
//                     Defaults to the first tab's id if omitted.
//
// Slots:
//   default        — body content (used when `tabs` is empty)
//   #tab-<id>      — body content for the tab with that id (used when `tabs` set)
//   #header        — overrides the default title row (still gets a close X
//                    on the right unless the slot supplies its own)
//   #footer        — sticky footer (typically a link to a full page or
//                    secondary CTA)
//
// Behavior:
//   - Teleported to <body> so it escapes any local stacking context.
//   - Click on backdrop closes (if closeOnBackdrop).
//   - ESC key closes (if closeOnEsc).
//   - Body scroll is locked while open.
//   - Fade transition on the whole thing.
import { computed, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue:      { type: Boolean, default: false },
  title:           { type: String, default: '' },
  maxWidth:        { type: [String, Number], default: 640 },
  borderClass:     { type: String, default: 'border-white/15' },
  closeOnEsc:      { type: Boolean, default: true },
  closeOnBackdrop: { type: Boolean, default: true },
  tabs:            { type: Array, default: () => [] },
  activeTab:       { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'close', 'update:activeTab'])

function close() {
  emit('update:modelValue', false)
  emit('close')
}

// Resolved active tab id: falls back to the first tab when the parent didn't
// supply one. Emits update:activeTab so v-model:active-tab works in the parent.
const currentTabId = computed(() => {
  if (!props.tabs.length) return ''
  const has = props.tabs.some(t => t.id === props.activeTab)
  return has ? props.activeTab : props.tabs[0].id
})

function selectTab(id) {
  if (id !== props.activeTab) emit('update:activeTab', id)
}

const panelStyle = computed(() => {
  const w = typeof props.maxWidth === 'number' ? `${props.maxWidth}px` : props.maxWidth
  return { maxWidth: w }
})

function onKey(e) {
  if (e.key === 'Escape' && props.modelValue && props.closeOnEsc) close()
}

watch(() => props.modelValue, (open) => {
  if (open) {
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
  } else {
    document.removeEventListener('keydown', onKey)
    document.body.style.overflow = ''
  }
}, { immediate: true })

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="modelValue"
           class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
           role="dialog"
           aria-modal="true"
           :aria-label="title || 'Dialog'"
           @click.self="closeOnBackdrop && close()">
        <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" @click="closeOnBackdrop && close()"></div>

        <div class="relative w-full bg-slate-900/95 backdrop-blur-xl border rounded-2xl shadow-2xl flex flex-col max-h-[90vh]"
             :class="borderClass"
             :style="panelStyle">

          <slot name="header">
            <div class="flex items-center justify-between p-5 sm:p-6 pb-3 sm:pb-4 flex-shrink-0">
              <h3 class="text-lg sm:text-xl font-bold text-white">{{ title }}</h3>
              <button @click="close" aria-label="Close" class="text-slate-400 hover:text-white transition">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </slot>

          <!-- Tab bar (when tabs prop is set). Sits between header and content,
               doesn't scroll. Each tab can show a count chip and an accent color
               (matches the theme of its content — e.g. emerald for Uploaded). -->
          <div v-if="tabs.length" class="flex-shrink-0 flex items-center gap-1 px-5 sm:px-6 pb-3 sm:pb-4 border-b border-white/10 overflow-x-auto scrollbar-hide" role="tablist">
            <button
              v-for="t in tabs"
              :key="t.id"
              role="tab"
              :aria-selected="currentTabId === t.id"
              :tabindex="currentTabId === t.id ? 0 : -1"
              @click="selectTab(t.id)"
              class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-bold uppercase tracking-wider transition-colors border whitespace-nowrap"
              :class="currentTabId === t.id
                ? (t.accent === 'emerald' ? 'bg-emerald-500/15 text-emerald-200 border-emerald-500/40'
                  : t.accent === 'indigo'  ? 'bg-indigo-500/15 text-indigo-200 border-indigo-500/40'
                  : t.accent === 'amber'   ? 'bg-amber-500/15 text-amber-200 border-amber-500/40'
                  : t.accent === 'fuchsia' ? 'bg-fuchsia-500/15 text-fuchsia-200 border-fuchsia-500/40'
                  : 'bg-white/10 text-white border-white/25')
                : 'text-slate-400 hover:text-white hover:bg-white/5 border-transparent'">
              {{ t.label }}
              <span v-if="t.count != null" class="text-[10px] px-1.5 py-0.5 rounded bg-black/40 text-current">{{ t.count }}</span>
            </button>
          </div>

          <div class="flex-1 overflow-y-auto thin-scrollbar px-5 sm:px-6 pb-5 sm:pb-6 space-y-4 pt-4">
            <template v-if="tabs.length">
              <slot :name="`tab-${currentTabId}`" />
            </template>
            <slot v-else />
          </div>

          <div v-if="$slots.footer"
               class="border-t border-white/10 px-5 sm:px-6 py-3 sm:py-4 flex-shrink-0 bg-slate-900/80">
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
