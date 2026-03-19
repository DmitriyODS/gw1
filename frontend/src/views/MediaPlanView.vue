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

    <div v-else class="grid grid-cols-1 xl:grid-cols-4 gap-4">
      <!-- Calendar -->
      <div class="xl:col-span-3 bg-surface-0 dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700 overflow-hidden">
        <div class="grid grid-cols-7 border-b border-surface-200 dark:border-surface-700">
          <div
            v-for="day in weekDays"
            :key="day"
            class="py-2 text-center text-xs font-semibold text-surface-500 bg-surface-50 dark:bg-surface-900"
          >{{ day }}</div>
        </div>
        <div class="grid grid-cols-7">
          <div
            v-for="(cell, idx) in calendarCells"
            :key="idx"
            class="min-h-[90px] border-b border-r border-surface-100 dark:border-surface-700 p-1"
            :class="{ 'bg-surface-50 dark:bg-surface-900/50': !cell.inMonth }"
          >
            <div
              v-if="cell.inMonth"
              class="text-xs font-medium mb-1 w-5 h-5 flex items-center justify-center rounded-full"
              :class="cell.isToday ? 'bg-primary-500 text-white' : 'text-surface-500'"
            >{{ cell.day }}</div>
            <div v-for="task in cell.tasks" :key="task.id" class="mb-0.5">
              <router-link
                :to="`/tasks/${task.id}`"
                class="block text-[10px] px-1 py-0.5 rounded truncate hover:opacity-80 transition-opacity"
                :class="statusTaskClass(task.status)"
              >{{ task.title }}</router-link>
            </div>
          </div>
        </div>
      </div>

      <!-- Without date block -->
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
        <div class="p-4 border-b border-surface-200 dark:border-surface-700">
          <h3 class="text-sm font-semibold text-surface-700 dark:text-surface-300">Без даты публикации</h3>
          <p class="text-xs text-surface-400 mt-0.5">{{ withoutDate.length }} задач</p>
        </div>
        <div class="p-2 space-y-1.5 max-h-[600px] overflow-y-auto">
          <div
            v-for="task in withoutDate"
            :key="task.id"
            class="rounded-lg p-2 border border-surface-100 dark:border-surface-700"
          >
            <router-link
              :to="`/tasks/${task.id}`"
              class="text-xs font-medium text-surface-700 dark:text-surface-300 hover:text-primary-600 block truncate"
            >{{ task.title }}</router-link>
            <span
              class="text-[10px] px-1.5 py-0.5 rounded-full mt-1 inline-block"
              :class="statusTaskClass(task.status)"
            >{{ statusLabel(task.status) }}</span>
          </div>
          <p v-if="!withoutDate.length" class="text-sm text-surface-400 text-center py-4">Все задачи имеют дату</p>
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
const entries = ref([])
const withoutDate = ref([])
const currentDate = ref(new Date())

const weekDays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

const monthLabel = computed(() =>
  currentDate.value.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
)

// Build a date → tasks map from the entries array
const tasksByDate = computed(() => {
  const map = {}
  for (const entry of entries.value) {
    const key = entry.pub_date?.substring(0, 10)
    if (!key) continue
    if (!map[key]) map[key] = []
    map[key].push(entry)
  }
  return map
})

const calendarCells = computed(() => {
  const year = currentDate.value.getFullYear()
  const month = currentDate.value.getMonth()
  const firstDay = new Date(year, month, 1)
  const lastDay = new Date(year, month + 1, 0)
  const today = new Date()

  const startOffset = (firstDay.getDay() + 6) % 7
  const cells = []

  for (let i = 0; i < startOffset; i++) {
    cells.push({ inMonth: false, day: null, tasks: [], isToday: false })
  }

  for (let d = 1; d <= lastDay.getDate(); d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const isToday = today.getFullYear() === year && today.getMonth() === month && today.getDate() === d
    cells.push({
      inMonth: true,
      day: d,
      tasks: tasksByDate.value[dateStr] || [],
      isToday,
    })
  }

  while (cells.length % 7 !== 0) {
    cells.push({ inMonth: false, day: null, tasks: [], isToday: false })
  }

  return cells
})

function statusTaskClass(status) {
  return {
    new:         'bg-surface-100 dark:bg-surface-700 text-surface-600 dark:text-surface-300',
    in_progress: 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300',
    paused:      'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300',
    done:        'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300',
  }[status] || 'bg-primary-100 dark:bg-primary-900/40 text-primary-700 dark:text-primary-300'
}

function statusLabel(status) {
  return { new: 'Новая', in_progress: 'В работе', paused: 'Пауза', done: 'Готово' }[status] || status
}

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
    entries.value = data.entries || []
    withoutDate.value = data.without_date || []
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
