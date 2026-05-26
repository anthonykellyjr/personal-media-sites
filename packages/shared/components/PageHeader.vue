<script setup>
// Shared page header: back-link + logo + title/subtitle on the left, a free
// slot on the right for page-specific actions (tabs, buttons, search, etc.).
//
// API:
//   props:
//     - title     (required)   — h1 text
//     - subtitle  (optional)   — small text under the title
//     - logo      (optional)   — image src; omit to show no logo
//     - logoAlt   (optional)   — alt text for the logo
//     - hideBack  (optional)   — set true to suppress the default HubButton
//     - variant   (optional)   — 'card' (default, free-standing rounded card,
//                                stacks on mobile — use on landing-style pages
//                                like recently-added and tutorials) or 'bar'
//                                (sticky top bar, single horizontal row —
//                                use on app pages with persistent controls
//                                like collection-manager and kelly-collection).
//   slots:
//     - default                — right-hand content (tabs, buttons, anything)
//     - #back                  — overrides the default HubButton entirely
//     - #title                 — overrides the entire title block (rich titles)
//
// Example:
//   <PageHeader title="Recently Added" subtitle="in WebheadPlex" :logo="garfieldImg">
//     <div role="tablist">…tabs…</div>
//     <button>Refresh</button>
//   </PageHeader>
import HubButton from './HubButton.vue'

defineProps({
  title:    { type: String, required: true },
  subtitle: { type: String, default: '' },
  logo:     { type: String, default: '' },
  logoAlt:  { type: String, default: '' },
  hideBack: { type: Boolean, default: false },
  variant:  { type: String, default: 'card', validator: v => ['card', 'bar'].includes(v) },
})
</script>

<template>
  <!-- Card variant: free-standing rounded header, stacks on mobile. -->
  <header
    v-if="variant === 'card'"
    class="flex flex-col md:flex-row items-center justify-between gap-4 mb-8 bg-white/5 p-4 rounded-2xl border border-white/10"
  >
    <div class="flex items-center gap-4 w-full md:w-auto">
      <slot name="back">
        <HubButton v-if="!hideBack" class="relative" />
      </slot>
      <img v-if="logo" :src="logo" :alt="logoAlt" class="w-12 h-12 rounded-xl shadow-lg">
      <slot name="title">
        <div class="text-left">
          <h1 class="text-xl font-bold text-white leading-none mb-1">{{ title }}</h1>
          <p v-if="subtitle" class="text-xs text-white/50">{{ subtitle }}</p>
        </div>
      </slot>
    </div>

    <div class="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-2 md:pb-0">
      <slot />
    </div>
  </header>

  <!-- Bar variant: sticky top bar for app pages with persistent controls. -->
  <header
    v-else
    class="sticky top-0 z-30 bg-slate-900/80 backdrop-blur-xl border-b border-white/10"
  >
    <div class="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3 sm:gap-4">
      <slot name="back">
        <HubButton v-if="!hideBack" />
      </slot>
      <img v-if="logo" :src="logo" :alt="logoAlt" class="w-8 h-8 rounded-lg shadow flex-shrink-0">
      <slot name="title">
        <h1 class="text-base sm:text-lg font-bold text-white flex-shrink-0">{{ title }}</h1>
      </slot>
      <div class="flex-1 flex items-center justify-end gap-2 min-w-0">
        <slot />
      </div>
    </div>
  </header>
</template>
