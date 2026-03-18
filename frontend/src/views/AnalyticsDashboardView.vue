<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Аналитика</h1>
      <div class="flex gap-2">
        <Button label="TV режим" icon="pi pi-desktop" outlined size="small" @click="$router.push('/analytics/tv')" />
        <Button label="Excel" icon="pi pi-download" outlined size="small" @click="exportExcel" />
      </div>
    </div>

    <div v-if="analyticsStore.loading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <template v-else-if="analyticsStore.dashboard">
      <!-- Stats cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div v-for="stat in stats" :key="stat.label" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
          <div class="text-2xl font-bold text-primary-600">{{ stat.value }}</div>
          <div class="text-xs text-surface-500 mt-1">{{ stat.label }}</div>
        </div>
      </div>

      <!-- Charts row -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold mb-3">Задачи по статусам</h3>
          <Chart v-if="statusChartData.labels.length" type="doughnut" :data="statusChartData" :options="donutOptions" style="height: 250px" />
          <p v-else class="text-sm text-surface-400 text-center py-8">Нет данных</p>
        </div>
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold mb-3">По отделам</h3>
          <Chart v-if="deptChartData.labels.length" type="bar" :data="deptChartData" :options="barOptions" style="height: 250px" />
          <p v-else class="text-sm text-surface-400 text-center py-8">Нет данных</p>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useAnalyticsStore } from '../stores/analytics.js'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import Chart from 'primevue/chart'

const analyticsStore = useAnalyticsStore()

const STATUS_LABELS = {
  new: 'Новые',
  in_progress: 'В работе',
  paused: 'Пауза',
  done: 'Готово',
}

const stats = computed(() => {
  const d = analyticsStore.dashboard
  if (!d) return []
  const s = d.by_status || {}
  const total = Object.values(s).reduce((a, b) => a + b, 0)
  return [
    { label: 'Всего задач',  value: total },
    { label: 'В работе',     value: s.in_progress ?? 0 },
    { label: 'Завершено',    value: s.done ?? 0 },
    { label: 'Просрочено',   value: d.overdue_count ?? 0 },
  ]
})

const statusChartData = computed(() => {
  const s = analyticsStore.dashboard?.by_status || {}
  const keys = Object.keys(s)
  return {
    labels: keys.map((k) => STATUS_LABELS[k] || k),
    datasets: [{
      data: keys.map((k) => s[k]),
      backgroundColor: ['#60a5fa', '#34d399', '#fbbf24', '#a78bfa'],
    }],
  }
})

const deptChartData = computed(() => {
  const arr = analyticsStore.dashboard?.by_department || []
  return {
    labels: arr.map((d) => d.name),
    datasets: [{
      label: 'Задачи',
      data: arr.map((d) => d.count),
      backgroundColor: '#60a5fa',
    }],
  }
})

const donutOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
const barOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }

async function exportExcel() {
  await analyticsStore.exportExcel()
}

onMounted(() => analyticsStore.fetchDashboard())
</script>
