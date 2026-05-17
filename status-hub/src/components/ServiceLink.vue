<script setup>
defineProps({
  href: { type: String, required: true },
  name: { type: String, required: true },
  icon: { type: String, required: true }
})
</script>

<template>
  <a :href="href" target="_blank"
     class="group flex items-center gap-2.5 bg-slate-950/60 backdrop-blur-xl border border-white/15 hover:border-purple-500/50 rounded-xl px-4 py-2.5 transition-all duration-300 ease-out hover:scale-[1.05] hover:-translate-y-1 hover:bg-slate-900/80 hover:shadow-[0_15px_40px_-10px_rgba(0,0,0,0.5),0_0_25px_rgba(168,85,247,0.2)]">
    <img :src="icon" :alt="name" class="w-5 h-5 object-contain filter drop-shadow opacity-90 group-hover:opacity-100 group-hover:scale-110 transition">
    <span class="text-sm font-semibold text-slate-200 group-hover:text-white">{{ name }}</span>
    <svg class="w-3.5 h-3.5 text-slate-500 ml-1 group-hover:text-purple-400 group-hover:translate-x-0.5 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
    </svg>
  </a>
</template>
