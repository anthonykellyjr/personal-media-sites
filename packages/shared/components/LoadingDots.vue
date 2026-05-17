<script setup>
defineProps({
  colors: {
    type: Array,
    default: () => ['bg-purple-500', 'bg-fuchsia-500', 'bg-pink-500']
  }
})
</script>

<template>
  <div class="flex gap-2">
    <span v-for="(color, i) in colors" :key="i"
          class="w-3 h-3 rounded-full animate-bounce"
          :class="color"
          :style="{ animationDelay: `${i * 0.15}s` }"></span>
  </div>
</template>
