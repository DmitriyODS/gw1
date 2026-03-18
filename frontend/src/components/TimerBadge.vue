<template>
  <router-link
    v-if="timerStore.activeTimer"
    :to="`/tasks/${timerStore.activeTimer.task_id || timerStore.activeTimer.task?.id}`"
    class="flex items-center gap-1.5 px-2 py-1 rounded bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 text-sm font-mono hover:opacity-80 transition-opacity"
  >
    <span class="inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
    {{ formatted }}
  </router-link>
</template>

<script setup>
import { computed } from 'vue'
import { useTimerStore } from '../stores/timer.js'

const timerStore = useTimerStore()

const formatted = computed(() => {
  const s = timerStore.elapsedSeconds
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
})
</script>
