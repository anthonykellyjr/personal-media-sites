<script setup>
defineProps({
  title: { type: String, default: '' },
  summary: { type: String, default: '' },
  isEditing: { type: Boolean, default: false },
  isSaving: { type: Boolean, default: false },
  canSave: { type: Boolean, default: false },
  kometaManaged: { type: Boolean, default: false },
  smart: { type: Boolean, default: false },
})

defineEmits(['update:title', 'update:summary', 'save', 'delete', 'cancel'])
</script>

<template>
  <div class="space-y-3">
    <!-- Kometa warning -->
    <div v-if="kometaManaged"
         class="flex items-start gap-2 p-3 bg-amber-950/30 border border-amber-500/30 rounded-xl text-xs text-amber-300">
      <svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>
      </svg>
      <span>This collection is managed by <strong>Kometa</strong>. Your changes may be overwritten at the next scheduled sync (3:00 AM).</span>
    </div>

    <!-- Smart collection notice -->
    <div v-if="smart"
         class="flex items-start gap-2 p-3 bg-blue-950/30 border border-blue-500/30 rounded-xl text-xs text-blue-300">
      <svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <span>This is a <strong>Smart Collection</strong> — items are automatically populated by Plex filters and cannot be manually edited here.</span>
    </div>

    <!-- Title input -->
    <div>
      <label class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1 block">Title</label>
      <input
        :value="title"
        @input="$emit('update:title', $event.target.value)"
        :disabled="smart"
        type="text"
        placeholder="Collection name..."
        class="w-full px-3 py-2.5 bg-dark-900 border border-white/15 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/60 transition-colors disabled:opacity-50"
      />
    </div>

    <!-- Summary input -->
    <div>
      <label class="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1 block">Summary <span class="font-normal">(optional)</span></label>
      <textarea
        :value="summary"
        @input="$emit('update:summary', $event.target.value)"
        :disabled="smart"
        placeholder="Description..."
        rows="2"
        class="w-full px-3 py-2.5 bg-dark-900 border border-white/15 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/60 transition-colors resize-none disabled:opacity-50"
      ></textarea>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-2 pt-1">
      <button v-if="!smart"
              @click="$emit('save')"
              :disabled="!canSave || isSaving"
              class="flex-1 py-2.5 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-xl transition-all flex items-center justify-center gap-2">
        <svg v-if="isSaving" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
        </svg>
        {{ isSaving ? 'Saving...' : (isEditing ? 'Save Changes' : 'Create Collection') }}
      </button>

      <button @click="$emit('cancel')"
              class="px-4 py-2.5 text-sm text-slate-400 hover:text-white transition-colors">
        Cancel
      </button>

      <button v-if="isEditing"
              @click="$emit('delete')"
              class="px-4 py-2.5 text-sm text-red-400 hover:text-red-300 transition-colors ml-auto">
        Delete
      </button>
    </div>
  </div>
</template>
