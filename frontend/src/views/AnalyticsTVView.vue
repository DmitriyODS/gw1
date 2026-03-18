<template>
  <div
    class="min-h-screen bg-gray-950 text-white flex flex-col"
    :class="{ dark: true }"
    tabindex="0"
    @keydown="onKey"
    ref="tvEl"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-8 py-4 border-b border-gray-800">
      <div class="text-2xl font-bold text-primary-400">GW1</div>
      <div class="text-lg font-mono text-gray-400">{{ currentTime }}</div>
      <div class="flex items-center gap-2">
        <div class="flex gap-1">
          <button
            v-for="(_, i) in slides"
            :key="i"
            class="w-2 h-2 rounded-full transition-colors"
            :class="currentSlide === i ? 'bg-primary-400' : 'bg-gray-600'"
            @click="currentSlide = i"
          />
        </div>
        <Button icon="pi pi-times" text severity="secondary" size="small" @click="$router.push('/analytics')" />
      </div>
    </div>

    <!-- Slides -->
    <div class="flex-1 overflow-hidden">
      <!-- Slide 0: Status overview -->
      <div v-if="currentSlide === 0" class="h-full flex flex-col p-8">
        <h2 class="text-2xl font-bold mb-6 text-gray-200">Обзор задач</h2>
        <div v-if="tvData" class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div v-for="stat in overviewStats" :key="stat.label" class="bg-gray-900 rounded-2xl p-6 text-center border border-gray-800">
            <div class="text-4xl font-bold text-primary-400">{{ stat.value }}</div>
            <div class="text-gray-400 mt-2">{{ stat.label }}</div>
          </div>
        </div>
        <div v-if="tvData?.active_tasks?.length" class="flex-1 overflow-hidden">
          <h3 class="text-lg font-semibold text-gray-300 mb-3">В работе</h3>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 overflow-y-auto">
            <div v-for="task in tvData.active_tasks" :key="task.id" class="bg-gray-900 rounded-xl p-4 border border-gray-800 flex items-center gap-3">
              <div class="w-2 h-12 rounded-full bg-green-500"></div>
              <div class="flex-1 min-w-0">
                <p class="font-medium text-white truncate">{{ task.title }}</p>
                <p class="text-sm text-gray-400">{{ task.assignee?.name }}</p>
              </div>
              <div class="text-sm font-mono text-green-400">{{ formatTime(task.timer_seconds) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Slide 1: By department -->
      <div v-else-if="currentSlide === 1" class="h-full flex flex-col p-8">
        <h2 class="text-2xl font-bold mb-6 text-gray-200">По отделам</h2>
        <div v-if="tvData?.by_department" class="flex-1">
          <div class="space-y-4">
            <div v-for="(count, dept) in tvData.by_department" :key="dept" class="flex items-center gap-4">
              <span class="text-gray-300 w-40 text-right truncate text-sm">{{ dept }}</span>
              <div class="flex-1 bg-gray-900 rounded-full h-8 overflow-hidden">
                <div
                  class="h-full bg-primary-500 rounded-full flex items-center justify-end pr-3 text-sm font-semibold text-white transition-all"
                  :style="{ width: barWidth(count) }"
                >
                  {{ count }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Slide 2: Top performers -->
      <div v-else-if="currentSlide === 2" class="h-full flex flex-col p-8">
        <h2 class="text-2xl font-bold mb-6 text-gray-200">Топ сотрудников</h2>
        <div v-if="tvData?.top_users" class="space-y-3">
          <div v-for="(u, idx) in tvData.top_users" :key="u.user_id" class="flex items-center gap-4 bg-gray-900 rounded-xl p-4 border border-gray-800">
            <div class="text-3xl font-bold text-gray-600 w-8">{{ idx + 1 }}</div>
            <div class="flex-1">
              <p class="font-semibold text-white">{{ u.name }}</p>
              <p class="text-sm text-gray-400">Задач: {{ u.tasks_done }}</p>
            </div>
            <div class="text-right">
              <div class="text-lg font-mono text-primary-400">{{ formatTime(u.total_seconds) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Nav hints -->
    <div class="px-8 py-3 text-center text-xs text-gray-600">
      ← → для навигации | Space для паузы
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAnalyticsStore } from '../stores/analytics.js'
import Button from 'primevue/button'

const analyticsStore = useAnalyticsStore()
const tvEl = ref(null)
const currentSlide = ref(0)
const slides = [0, 1, 2]
const tvData = computed(() => analyticsStore.tvData)

const currentTime = ref('')
let timeInterval = null
let autoInterval = null
let paused = false

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function startAuto() {
  autoInterval = setInterval(() => {
    if (!paused) currentSlide.value = (currentSlide.value + 1) % slides.length
  }, 12_000)
}

function onKey(e) {
  if (e.key === 'ArrowRight') currentSlide.value = (currentSlide.value + 1) % slides.length
  if (e.key === 'ArrowLeft') currentSlide.value = (currentSlide.value - 1 + slides.length) % slides.length
  if (e.key === ' ') { e.preventDefault(); paused = !paused }
}

const overviewStats = computed(() => {
  const d = tvData.value
  if (!d) return []
  return [
    { label: 'Всего', value: d.total ?? 0 },
    { label: 'В работе', value: d.in_progress ?? 0 },
    { label: 'Завершено', value: d.done ?? 0 },
    { label: 'Просрочено', value: d.overdue ?? 0 },
  ]
})

function barWidth(count) {
  const max = Math.max(...Object.values(tvData.value?.by_department || { _: 1 }))
  return `${Math.max(5, (count / max) * 100)}%`
}

function formatTime(s) {
  if (!s) return '0ч 0м'
  return `${Math.floor(s / 3600)}ч ${Math.floor((s % 3600) / 60)}м`
}

onMounted(async () => {
  tvEl.value?.focus()
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  startAuto()
  await analyticsStore.fetchTV()
})

onUnmounted(() => {
  clearInterval(timeInterval)
  clearInterval(autoInterval)
})
</script>
