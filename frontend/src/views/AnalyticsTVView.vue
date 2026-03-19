<template>
  <div
    class="min-h-screen bg-gray-950 text-white flex flex-col select-none"
    tabindex="0"
    @keydown="onKey"
    ref="tvEl"
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-8 py-4 border-b border-gray-800 flex-shrink-0">
      <div class="text-2xl font-bold text-primary-400">Groove Work</div>
      <div class="flex items-center gap-6">
        <!-- Period selector -->
        <div class="flex rounded-lg overflow-hidden border border-gray-700 text-sm">
          <button
            v-for="p in periods"
            :key="p.value"
            class="px-3 py-1.5 transition-colors"
            :class="period === p.value
              ? 'bg-primary-500 text-white'
              : 'bg-gray-900 text-gray-400 hover:bg-gray-800'"
            @click="setPeriod(p.value)"
          >{{ p.label }}</button>
        </div>
        <!-- Slide dots -->
        <div class="flex gap-1.5">
          <button
            v-for="(_, i) in slides"
            :key="i"
            class="w-2.5 h-2.5 rounded-full transition-colors"
            :class="currentSlide === i ? 'bg-primary-400' : 'bg-gray-700'"
            @click="goTo(i)"
          />
        </div>
      </div>
      <div class="flex items-center gap-4">
        <div class="text-xl font-mono text-gray-300">{{ currentTime }}</div>
        <button
          class="text-gray-600 hover:text-gray-400 transition-colors"
          @click="$router.push('/analytics')"
        >✕</button>
      </div>
    </div>

    <!-- Slide container -->
    <div class="flex-1 overflow-hidden relative">

      <!-- Slide 0: Обзор -->
      <div v-show="currentSlide === 0" class="h-full flex flex-col p-8 gap-6">
        <h2 class="text-3xl font-bold text-gray-100">Обзор задач</h2>
        <div class="grid grid-cols-3 gap-4">
          <div
            v-for="stat in overviewStats"
            :key="stat.label"
            class="rounded-2xl p-6 text-center border"
            :class="stat.bg"
          >
            <div class="text-5xl font-bold" :class="stat.color">{{ stat.value }}</div>
            <div class="text-gray-400 mt-2 text-sm">{{ stat.label }}</div>
          </div>
        </div>
        <div class="flex-1 overflow-hidden">
          <h3 class="text-lg font-semibold text-gray-300 mb-3">Сейчас в работе</h3>
          <div v-if="tvData?.active_tasks?.length" class="grid grid-cols-2 gap-3 overflow-y-auto" style="max-height: calc(100% - 2rem)">
            <div
              v-for="task in tvData.active_tasks"
              :key="task.id"
              class="bg-gray-900 rounded-xl p-4 border border-gray-800 flex items-center gap-3"
            >
              <div class="w-2 h-12 rounded-full bg-green-500 flex-shrink-0"></div>
              <div class="flex-1 min-w-0">
                <p class="font-medium text-white truncate">{{ task.title }}</p>
                <p class="text-sm text-gray-400">{{ task.assigned_to?.full_name || 'Без исполнителя' }}</p>
              </div>
            </div>
          </div>
          <p v-else class="text-gray-600 text-center py-8">Нет задач в работе</p>
        </div>
      </div>

      <!-- Slide 1: Сегодня + Просрочено -->
      <div v-show="currentSlide === 1" class="h-full flex flex-col p-8 gap-6">
        <h2 class="text-3xl font-bold text-gray-100">Сегодня</h2>
        <div class="grid grid-cols-4 gap-4">
          <div class="bg-gray-900 rounded-2xl p-5 text-center border border-gray-800">
            <div class="text-4xl font-bold text-blue-400">{{ tvData?.today?.created ?? 0 }}</div>
            <div class="text-gray-400 mt-2 text-sm">Создано</div>
          </div>
          <div class="bg-gray-900 rounded-2xl p-5 text-center border border-gray-800">
            <div class="text-4xl font-bold text-green-400">{{ tvData?.today?.done ?? 0 }}</div>
            <div class="text-gray-400 mt-2 text-sm">Завершено</div>
          </div>
          <div class="bg-gray-900 rounded-2xl p-5 text-center border border-gray-800">
            <div class="text-4xl font-bold text-yellow-400">{{ tvData?.today?.in_progress ?? 0 }}</div>
            <div class="text-gray-400 mt-2 text-sm">В работе</div>
          </div>
          <div class="bg-gray-900 rounded-2xl p-5 text-center border border-red-900">
            <div class="text-4xl font-bold text-red-400">{{ tvData?.today?.overdue ?? 0 }}</div>
            <div class="text-gray-400 mt-2 text-sm">Просрочено</div>
          </div>
        </div>

        <div class="flex-1 overflow-hidden">
          <h3 class="text-lg font-semibold text-red-400 mb-3">Просроченные задачи</h3>
          <div v-if="tvData?.overdue_tasks?.length" class="space-y-2 overflow-y-auto" style="max-height: calc(100% - 2rem)">
            <div
              v-for="task in tvData.overdue_tasks"
              :key="task.id"
              class="bg-gray-900 rounded-xl p-4 border border-red-900/50 flex items-center gap-4"
            >
              <div class="w-1.5 h-10 rounded-full bg-red-500 flex-shrink-0"></div>
              <div class="flex-1 min-w-0">
                <p class="font-medium text-white truncate">{{ task.title }}</p>
                <p class="text-sm text-gray-500">{{ task.assigned_to?.full_name || 'Без исполнителя' }}</p>
              </div>
              <div class="text-sm text-red-400 font-mono flex-shrink-0">
                {{ formatDeadline(task.deadline) }}
              </div>
            </div>
          </div>
          <p v-else class="text-gray-600 text-center py-8">Нет просроченных задач</p>
        </div>
      </div>

      <!-- Slide 2: По отделам -->
      <div v-show="currentSlide === 2" class="h-full flex flex-col p-8 gap-6">
        <h2 class="text-3xl font-bold text-gray-100">По отделам</h2>
        <div v-if="tvData?.by_department?.length" class="flex-1 space-y-4 overflow-y-auto">
          <div
            v-for="dept in tvData.by_department.slice(0, 8)"
            :key="dept.name"
            class="flex items-center gap-4"
          >
            <span class="text-gray-300 w-48 text-right truncate text-sm flex-shrink-0">{{ dept.name }}</span>
            <div class="flex-1 bg-gray-900 rounded-full h-10 overflow-hidden border border-gray-800">
              <div
                class="h-full bg-primary-600 rounded-full flex items-center justify-end pr-4 text-sm font-bold text-white transition-all"
                :style="{ width: deptBarWidth(dept.count) }"
              >
                {{ dept.count }}
              </div>
            </div>
          </div>
        </div>
        <p v-else class="text-gray-600 text-center py-8">Нет данных</p>
      </div>

      <!-- Slide 3: Топ сотрудников -->
      <div v-show="currentSlide === 3" class="h-full flex flex-col p-8 gap-6">
        <h2 class="text-3xl font-bold text-gray-100">Топ сотрудников</h2>
        <div class="grid grid-cols-2 gap-6 flex-1">
          <div>
            <h3 class="text-lg font-semibold text-gray-400 mb-3">По задачам</h3>
            <div class="space-y-3">
              <div
                v-for="(u, idx) in (tvData?.top_performers || [])"
                :key="u.id"
                class="flex items-center gap-4 bg-gray-900 rounded-xl p-4 border border-gray-800"
              >
                <div class="text-3xl font-bold w-8 flex-shrink-0" :class="medalColor(idx)">{{ idx + 1 }}</div>
                <div class="flex-1 min-w-0">
                  <p class="font-semibold text-white truncate">{{ u.full_name }}</p>
                </div>
                <div class="text-lg font-bold text-primary-400 flex-shrink-0">{{ u.count }}</div>
              </div>
              <p v-if="!tvData?.top_performers?.length" class="text-gray-600 text-center py-4">Нет данных</p>
            </div>
          </div>
          <div>
            <h3 class="text-lg font-semibold text-gray-400 mb-3">По времени</h3>
            <div class="space-y-3">
              <div
                v-for="(u, idx) in (tvData?.top_by_time || [])"
                :key="u.id"
                class="flex items-center gap-4 bg-gray-900 rounded-xl p-4 border border-gray-800"
              >
                <div class="text-3xl font-bold w-8 flex-shrink-0" :class="medalColor(idx)">{{ idx + 1 }}</div>
                <div class="flex-1 min-w-0">
                  <p class="font-semibold text-white truncate">{{ u.full_name }}</p>
                </div>
                <div class="text-sm font-mono text-primary-400 flex-shrink-0">{{ formatTime(u.seconds) }}</div>
              </div>
              <p v-if="!tvData?.top_by_time?.length" class="text-gray-600 text-center py-4">Нет данных</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Slide 4: Burn-up + Рекорд концентрации -->
      <div v-show="currentSlide === 4" class="h-full flex flex-col p-8 gap-6">
        <h2 class="text-3xl font-bold text-gray-100">Динамика</h2>
        <div class="flex-1 bg-gray-900 rounded-2xl p-6 border border-gray-800">
          <h3 class="text-lg font-semibold text-gray-400 mb-4">Создано vs Завершено</h3>
          <Chart
            v-if="burnupChartData.labels.length"
            type="line"
            :data="burnupChartData"
            :options="burnupOptions"
            style="height: 280px"
          />
          <p v-else class="text-gray-600 text-center py-12">Нет данных за период</p>
        </div>
        <!-- Concentration record -->
        <div
          v-if="tvData?.concentration_record?.seconds > 0"
          class="bg-gradient-to-r from-primary-900/40 to-gray-900 rounded-2xl p-5 border border-primary-800/50 flex items-center gap-4"
        >
          <div class="text-4xl">🏆</div>
          <div class="flex-1">
            <p class="text-primary-300 font-semibold">Рекорд концентрации</p>
            <p class="text-white text-sm">{{ tvData.concentration_record.user_name }} — {{ tvData.concentration_record.task_title }}</p>
          </div>
          <div class="text-2xl font-mono font-bold text-primary-400">
            {{ formatTime(tvData.concentration_record.seconds) }}
          </div>
        </div>
      </div>

    </div>

    <!-- Footer nav hints -->
    <div class="px-8 py-2 text-center text-xs text-gray-700 flex-shrink-0">
      ← → навигация · Пробел — пауза · автообновление через {{ refreshCountdown }}с
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAnalyticsStore } from '../stores/analytics.js'
import Chart from 'primevue/chart'

const analyticsStore = useAnalyticsStore()
const tvEl = ref(null)
const currentSlide = ref(0)
const slides = [0, 1, 2, 3, 4]
const tvData = computed(() => analyticsStore.tvData)
const period = ref('week')

const periods = [
  { label: 'Неделя', value: 'week' },
  { label: 'Месяц',  value: 'month' },
  { label: 'Год',    value: 'year' },
]

const currentTime = ref('')
const refreshCountdown = ref(60)
let timeInterval = null
let autoSlideInterval = null
let refreshInterval = null
let countdownInterval = null
let paused = false

function updateTime() {
  currentTime.value = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function goTo(i) {
  currentSlide.value = i
}

function startAutoSlide() {
  clearInterval(autoSlideInterval)
  autoSlideInterval = setInterval(() => {
    if (!paused) currentSlide.value = (currentSlide.value + 1) % slides.length
  }, 10_000)
}

function startRefresh() {
  clearInterval(refreshInterval)
  clearInterval(countdownInterval)
  refreshCountdown.value = 60
  refreshInterval = setInterval(() => {
    loadData()
    refreshCountdown.value = 60
  }, 60_000)
  countdownInterval = setInterval(() => {
    if (refreshCountdown.value > 0) refreshCountdown.value--
  }, 1_000)
}

function onKey(e) {
  if (e.key === 'ArrowRight') currentSlide.value = (currentSlide.value + 1) % slides.length
  if (e.key === 'ArrowLeft') currentSlide.value = (currentSlide.value - 1 + slides.length) % slides.length
  if (e.key === ' ') { e.preventDefault(); paused = !paused }
}

async function setPeriod(p) {
  period.value = p
  await loadData()
}

async function loadData() {
  await analyticsStore.fetchTV({ period: period.value })
}

const overviewStats = computed(() => {
  const d = tvData.value
  if (!d) return []
  return [
    { label: 'В работе',  value: d.stats?.active  ?? 0, color: 'text-yellow-400', bg: 'bg-gray-900 border-gray-800' },
    { label: 'Завершено', value: d.stats?.done     ?? 0, color: 'text-green-400',  bg: 'bg-gray-900 border-gray-800' },
    { label: 'Просрочено',value: d.stats?.overdue  ?? 0, color: 'text-red-400',    bg: 'bg-gray-900 border-red-900' },
  ]
})

function deptBarWidth(count) {
  const items = tvData.value?.by_department || []
  const max = Math.max(...items.map(d => d.count), 1)
  return `${Math.max(4, (count / max) * 100)}%`
}

function medalColor(idx) {
  return ['text-yellow-400', 'text-gray-300', 'text-yellow-700', 'text-gray-600', 'text-gray-600'][idx] || 'text-gray-600'
}

const burnupChartData = computed(() => {
  const created = tvData.value?.burnup_created || []
  const done = tvData.value?.burnup_done || []
  const allDates = [...new Set([...created.map(d => d.date), ...done.map(d => d.date)])].sort()
  if (!allDates.length) return { labels: [], datasets: [] }

  const createdMap = Object.fromEntries(created.map(d => [d.date, d.count]))
  const doneMap = Object.fromEntries(done.map(d => [d.date, d.count]))
  let cumCreated = 0, cumDone = 0
  const cumCreatedArr = []
  const cumDoneArr = []
  for (const date of allDates) {
    cumCreated += createdMap[date] || 0
    cumDone += doneMap[date] || 0
    cumCreatedArr.push(cumCreated)
    cumDoneArr.push(cumDone)
  }

  return {
    labels: allDates,
    datasets: [
      { label: 'Создано',   data: cumCreatedArr, borderColor: '#60a5fa', backgroundColor: '#60a5fa20', fill: true, tension: 0.3 },
      { label: 'Завершено', data: cumDoneArr,     borderColor: '#34d399', backgroundColor: '#34d39920', fill: true, tension: 0.3 },
    ],
  }
})

const burnupOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { position: 'bottom', labels: { color: '#9ca3af' } },
  },
  scales: {
    y: { beginAtZero: true, ticks: { color: '#6b7280' }, grid: { color: '#1f2937' } },
    x: { ticks: { color: '#6b7280' }, grid: { color: '#1f2937' } },
  },
}

function formatTime(s) {
  if (!s) return '0ч 0м'
  return `${Math.floor(s / 3600)}ч ${Math.floor((s % 3600) / 60)}м`
}

function formatDeadline(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffDays = Math.floor((now - d) / 86400000)
  if (diffDays === 0) return 'Сегодня'
  if (diffDays === 1) return 'Вчера'
  return `${diffDays} дн. назад`
}

onMounted(async () => {
  tvEl.value?.focus()
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
  startAutoSlide()
  startRefresh()
  await loadData()
})

onUnmounted(() => {
  clearInterval(timeInterval)
  clearInterval(autoSlideInterval)
  clearInterval(refreshInterval)
  clearInterval(countdownInterval)
})
</script>
