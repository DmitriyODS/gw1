<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Медиаплан</h1>
      <div class="flex items-center gap-2">
        <Button icon="pi pi-chevron-left" text size="small" @click="prevMonth" />
        <span class="text-sm font-medium w-32 text-center">{{ monthLabel }}</span>
        <Button icon="pi pi-chevron-right" text size="small" @click="nextMonth" />
        <Button icon="pi pi-download" outlined size="small" @click="exportExcel" label="Excel" />
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <div v-else class="bg-surface-0 dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
      <!-- Calendar grid -->
      <div class="grid grid-cols-7 border-b border-surface-200 dark:border-surface-700">
        <div v-for="day in weekDays" :key="day" class="py-2 text-center text-xs font-semibold text-surface-500 bg-surface-50 dark:bg-surface-900">
          {{ day }}
        </div>
      </div>
      <div class="grid grid-cols-7">
        <div
          v-for="(cell, idx) in calendarCells"
          :key="idx"
          class="min-h-[80px] border-b border-r border-surface-100 dark:border-surface-700 p-1"
          :class="{ 'bg-surface-50 dark:bg-surface-900/50': !cell.inMonth }"
        >
          <div v-if="cell.date" class="text-xs font-medium mb-1" :class="cell.isToday ? 'text-primary-600' : 'text-surface-500'">
            {{ cell.day }}
          </div>
          <div v-for="task in cell.tasks" :key="task.id" class="mb-0.5">
            <router-link
              :to="`/tasks/${task.id}`"
              class="block text-xs px-1 py-0.5 rounded bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300 truncate hover:bg-primary-200 transition-colors"
            >
              {{ task.title }}
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api/index.js'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'

const loading = ref(false)
const calendarData = ref({})
const currentDate = ref(new Date())

const weekDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

const monthLabel = computed(() => {
  return currentDate.value.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
})

const calendarCells = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const today = new Date()

  // Monday-based offset
  let startOffset = (firstDay.getDay() + 6) % 7
  const cells = []

  // Previous month days
  for (let i = startOffset - 1; i >= 0; i--) {
    cells.push({ inMonth: false, date: null, day: null, tasks: [], isToday: false })
  }

  // Current month days
  for (let d = 1; d <= lastDay.getDate(); d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === d
    cells.push({
      inMonth: true,
      date: dateStr,
      day: d,
      tasks: calendarData.value[dateStr] || [],
      isToday,
    })
  }

  // Fill to complete rows
  while (cells.length % 7 !== 0) {
    cells.push({ inMonth: false, date: null, day: null, tasks: [], isToday: false })
  }

  return cells
})

function prevMonth() {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() - 1)
  currentDate.value = d
  fetchData()
}

function nextMonth() {
  const d = new Date(currentDate.value)
  d.setMonth(d.getMonth() + 1)
  currentDate.value = d
  fetchData()
}

async function fetchData() {
  loading.value = true
  try {
    const year = currentDate.value.getFullYear()
    const month = currentDate.value.getMonth() + 1
    const { data } = await api.mediaPlan.calendar({ year, month })
    calendarData.value = data || {}
  } finally {
    loading.value = false
  }
}

async function exportExcel() {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth() + 1
  const response = await api.mediaPlan.exportExcel({ year, month })
  const url = URL.createObjectURL(new Blob([response.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = `mediaplan_${year}_${month}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(fetchData)
</script>
