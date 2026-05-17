<script setup>
defineProps({
  href: { type: String, required: true },
  label: { type: String, required: true },
  subtitle: { type: String, default: '' },
  color: { type: String, default: 'purple', validator: v => ['orange', 'blue', 'red', 'purple'].includes(v) },
  compactSmall: { type: Boolean, default: false }
})

const colorMap = {
  orange: 'hover:shadow-[0_20px_50px_-10px_rgba(0,0,0,0.6),0_0_30px_rgba(251,146,60,0.2)] hover:border-orange-500/40',
  blue:   'hover:shadow-[0_20px_50px_-10px_rgba(0,0,0,0.6),0_0_30px_rgba(59,130,246,0.2)] hover:border-blue-500/40',
  red:    'hover:shadow-[0_20px_50px_-10px_rgba(0,0,0,0.6),0_0_30px_rgba(239,68,68,0.2)] hover:border-red-500/40',
  purple: 'hover:shadow-[0_20px_50px_-10px_rgba(0,0,0,0.6),0_0_30px_rgba(168,85,247,0.2)] hover:border-purple-500/40'
}

const chevronColorMap = {
  orange: 'group-hover:text-orange-400',
  blue:   'group-hover:text-blue-400',
  red:    'group-hover:text-red-400',
  purple: 'group-hover:text-purple-400'
}
</script>

<template>
  <a :href="href" target="_blank"
     class="group relative flex items-center bg-slate-950/60 backdrop-blur-xl border border-white/15 rounded-2xl transition-all duration-300 ease-out hover:scale-[1.02] hover:-translate-y-0.5 hover:bg-slate-900/80"
     :class="[colorMap[color], compactSmall ? 'gap-2 p-2.5 sm:gap-3 sm:p-4' : 'gap-3 p-4']">
    <slot name="icon" />
    <div class="min-w-0 flex-1" :class="{ 'hidden sm:block': compactSmall }">
      <span class="text-sm sm:text-base font-semibold text-white tracking-wide">{{ label }}<template v-if="subtitle">&nbsp;{{ subtitle }}</template></span>
    </div>
    <svg class="w-4 h-4 sm:w-5 sm:h-5 text-white/20 flex-shrink-0 group-hover:translate-x-1 transition-all"
         :class="[chevronColorMap[color], { 'hidden sm:block': compactSmall }]"
         fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
    </svg>
  </a>
</template>
