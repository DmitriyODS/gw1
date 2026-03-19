<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-2">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Аналитика</h1>
      <div class="flex gap-2 flex-wrap">
        <!-- Period selector -->
        <div class="flex rounded-lg overflow-hidden border border-surface-300 dark:border-surface-600 text-sm">
          <button
            v-for="p in periods"
            :key="p.value"
            class="px-3 py-1.5 transition-colors"
            :class="period === p.value
              ? 'bg-primary-500 text-white'
              : 'bg-surface-0 dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'"
            @click="setPeriod(p.value)"
          >{{ p.label }}</button>
        </div>
        <Button label="TV" icon="pi pi-desktop" outlined size="small" @click="$router.push('/analytics/tv')" />
        <Button label="Excel" icon="pi pi-download" outlined size="small" @click="exportExcel" />
      </div>
    </div>

    <div v-if="analyticsStore.loading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <template v-else-if="analyticsStore.dashboard">
      <!-- Stats cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div v-for="stat in stats" :key="stat.label" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
          <div class="text-2xl font-bold" :class="stat.color || 'text-primary-600'">{{ stat.value }}</div>
          <div class="text-xs text-surface-500 mt-1">{{ stat.label }}</div>
        </div>
      </div>

      <!-- Charts row 1: status doughnut + dept bar -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold mb-3">Задачи по статусам</h3>
          <Chart v-if="statusChartData.labels.length" type="doughnut" :data="statusChartData" :options="donutOptions" style="height: 220px" />
          <p v-else class="text-sm text-surface-400 text-center py-8">Нет данных</p>
        </div>
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold mb-3">По типам задач</h3>
          <Chart v-if="typeChartData.labels.length" type="doughnut" :data="typeChartData" :options="donutOptions" style="height: 220px" />
          <p v-else class="text-sm text-surface-400 text-center py-8">Нет данных</p>
        </div>
      </div>

      <!-- Burn-up chart -->
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
        <h3 class="text-sm font-semibold mb-3">Burn-up (создано vs завершено)</h3>
        <Chart v-if="burnupChartData.labels.length" type="line" :data="burnupChartData" :options="lineOptions" style="height: 200px" />
        <p v-else class="text-sm text-surface-400 text-center py-8">Нет данных за период</p>
      </div>

      <!-- Dept chart -->
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
        <h3 class="text-sm font-semibold mb-3">По отделам</h3>
        <Chart v-if="deptChartData.labels.length" type="bar" :data="deptChartData" :options="barOptions" style="height: 200px" />
        <p v-else class="text-sm text-surface-400 text-center py-8">Нет данных</p>
      </div>

      <!-- Top tables row -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Top by tasks -->
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold mb-3">Топ по задачам</h3>
          <div v-if="dashboard.top_by_tasks?.length" class="space-y-2">
            <div v-for="(u, idx) in dashboard.top_by_tasks.slice(0,5)" :key="u.id" class="flex items-center gap-2 text-sm">
              <span class="text-surface-400 w-5 text-right">{{ idx + 1 }}</span>
              <span class="flex-1 truncate">{{ u.full_name || u.username }}</span>
              <span class="font-semibold text-primary-600">{{ u.count }}</span>
            </div>
          </div>
          <p v-else class="text-sm text-surface-400">Нет данных</p>
        </div>

        <!-- Top by time -->
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold mb-3">Топ по времени</h3>
          <div v-if="dashboard.top_by_time?.length" class="space-y-2">
            <div v-for="(u, idx) in dashboard.top_by_time.slice(0,5)" :key="u.id" class="flex items-center gap-2 text-sm">
              <span class="text-surface-400 w-5 text-right">{{ idx + 1 }}</span>
              <span class="flex-1 truncate">{{ u.full_name || u.username }}</span>
              <span class="font-mono text-xs text-primary-600">{{ formatTime(u.seconds) }}</span>
            </div>
          </div>
          <p v-else class="text-sm text-surface-400">Нет данных</p>
        </div>

        <!-- Top customers -->
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold mb-3">Топ заказчиков</h3>
          <div v-if="dashboard.top_customers?.length" class="space-y-2">
            <div v-for="(c, idx) in dashboard.top_customers.slice(0,5)" :key="idx" class="flex items-center gap-2 text-sm">
              <span class="text-surface-400 w-5 text-right">{{ idx + 1 }}</span>
              <span class="flex-1 truncate">{{ c.name }}</span>
              <span class="font-semibold text-primary-600">{{ c.count }}</span>
            </div>
          </div>
          <p v-else class="text-sm text-surface-400">Нет данных</p>
        </div>

        <!-- Top departments -->
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold mb-3">Топ отделов по заявкам</h3>
          <div v-if="dashboard.top_departments?.length" class="space-y-2">
            <div v-for="(d, idx) in dashboard.top_departments.slice(0,5)" :key="idx" class="flex items-center gap-2 text-sm">
              <span class="text-surface-400 w-5 text-right">{{ idx + 1 }}</span>
              <span class="flex-1 truncate">{{ d.name }}</span>
              <span class="font-semibold text-primary-600">{{ d.count }}</span>
            </div>
          </div>
          <p v-else class="text-sm text-surface-400">Нет данных</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAnalyticsStore } from '../stores/analytics.js'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import Chart from 'primevue/chart'

const analyticsStore = useAnalyticsStore()
const period = ref('month')

const periods = [
  { label: 'День',   value: 'day' },
  { label: 'Неделя', value: 'week' },
  { label: 'Месяц',  value: 'month' },
  { label: 'Год',    value: 'year' },
]

const STATUS_LABELS = { new: 'Новые', in_progress: 'В работе', paused: 'Пауза', done: 'Готово' }

const dashboard = computed(() => analyticsStore.dashboard || {})

const stats = computed(() => {
  const s = dashboard.value.by_status || {}
  const total = Object.values(s).reduce((a, b) => a + b, 0)
  return [
    { label: 'Всего задач',  value: total },
    { label: 'В работе',     value: s.in_progress ?? 0, color: 'text-blue-600' },
    { label: 'Завершено',    value: s.done ?? 0, color: 'text-green-600' },
    { label: 'Просрочено',   value: dashboard.value.overdue_count ?? 0, color: 'text-red-500' },
  ]
})

const statusChartData = computed(() => {
  const s = dashboard.value.by_status || {}
  const keys = Object.keys(s)
  return {
    labels: keys.map((k) => STATUS_LABELS[k] || k),
    datasets: [{ data: keys.map((k) => s[k]), backgroundColor: ['#60a5fa', '#34d399', '#fbbf24', '#a78bfa'] }],
  }
})

const typeChartData = computed(() => {
  const arr = dashboard.value.by_type || []
  return {
    labels: arr.map((t) => t.name),
    datasets: [{ data: arr.map((t) => t.count), backgroundColor: ['#60a5fa','#34d399','#fbbf24','#a78bfa','#f87171','#fb923c','#4ade80','#38bdf8','#c084fc','#f472b6'] }],
  }
})

const deptChartData = computed(() => {
  const arr = dashboard.value.by_department || []
  return {
    labels: arr.map((d) => d.name),
    datasets: [{ label: 'Задачи', data: arr.map((d) => d.count), backgroundColor: '#60a5fa' }],
  }
})

const burnupChartData = computed(() => {
  const created = dashboard.value.burnup_created || []
  const done = dashboard.value.burnup_done || []
  const allDates = [...new Set([...created.map(d => d.date), ...done.map(d => d.date)])].sort()
  if (!allDates.length) return { labels: [], datasets: [] }

  // Cumulative sums
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
      { label: 'Создано', data: cumCreatedArr, borderColor: '#60a5fa', backgroundColor: '#60a5fa20', fill: true, tension: 0.3 },
      { label: 'Завершено', data: cumDoneArr, borderColor: '#34d399', backgroundColor: '#34d39920', fill: true, tension: 0.3 },
    ],
  }
})

const donutOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
const barOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, indexAxis: 'y' }
const lineOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } }

function setPeriod(p) {
  period.value = p
  analyticsStore.fetchDashboard({ period: p })
}

function exportExcel() {
  analyticsStore.exportExcel()
}

function formatTime(s) {
  if (!s) return '0ч 0м'
  return `${Math.floor(s / 3600)}ч ${Math.floor((s % 3600) / 60)}м`
}

onMounted(() => analyticsStore.fetchDashboard({ period: period.value }))
</script>
