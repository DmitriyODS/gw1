<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-2">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Отчёт по времени</h1>
      <div class="flex items-center gap-2 flex-wrap">
        <!-- Employee filter (admin+) -->
        <Select
          v-if="authStore.isAdmin"
          v-model="filterUserId"
          :options="[{ label: 'Все сотрудники', value: 0 }, ...userOptions]"
          optionLabel="label"
          optionValue="value"
          placeholder="Сотрудник"
          class="w-44"
          @change="load"
        />
        <DatePicker v-model="dateFrom" dateFormat="dd.mm.yy" placeholder="С" class="w-32" showIcon />
        <DatePicker v-model="dateTo" dateFormat="dd.mm.yy" placeholder="По" class="w-32" showIcon />
        <Button label="Применить" size="small" @click="load" />
        <Button label="Excel" icon="pi pi-download" outlined size="small" @click="exportExcel" />
      </div>
    </div>

    <div v-if="analyticsStore.loading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <template v-else-if="report">
      <!-- Summary cards -->
      <div class="grid grid-cols-3 gap-3">
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
          <div class="text-2xl font-bold text-primary-600">{{ formatTime(report.summary?.week_seconds) }}</div>
          <div class="text-xs text-surface-500 mt-1">За неделю</div>
        </div>
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
          <div class="text-2xl font-bold text-primary-600">{{ formatTime(report.summary?.month_seconds) }}</div>
          <div class="text-xs text-surface-500 mt-1">За месяц</div>
        </div>
        <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
          <div class="text-2xl font-bold text-primary-600">{{ formatTime(report.summary?.all_seconds) }}</div>
          <div class="text-xs text-surface-500 mt-1">За всё время</div>
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- Detailed log grouped by date -->
        <div class="lg:col-span-2 bg-surface-0 dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
          <div class="p-4 border-b border-surface-200 dark:border-surface-700">
            <h3 class="text-sm font-semibold">Детальный журнал</h3>
          </div>
          <div v-if="groupedLogs.length" class="divide-y divide-surface-100 dark:divide-surface-700 max-h-[500px] overflow-y-auto">
            <div v-for="group in groupedLogs" :key="group.date">
              <!-- Date header -->
              <div class="px-4 py-2 bg-surface-50 dark:bg-surface-900/50 flex items-center justify-between">
                <span class="text-xs font-semibold text-surface-500">{{ group.dateLabel }}</span>
                <span class="text-xs font-mono text-primary-600">{{ formatTime(group.totalSeconds) }}</span>
              </div>
              <!-- Log entries -->
              <div
                v-for="log in group.logs"
                :key="log.id"
                class="px-4 py-2.5 flex items-center gap-3 text-sm"
                :class="log.is_active ? 'bg-green-50 dark:bg-green-900/10' : ''"
              >
                <div class="w-1.5 h-1.5 rounded-full flex-shrink-0" :class="log.is_active ? 'bg-green-500' : 'bg-surface-300 dark:bg-surface-600'" />
                <div class="flex-1 min-w-0">
                  <router-link
                    :to="`/tasks/${log.task_id}`"
                    class="font-medium text-surface-800 dark:text-surface-200 hover:text-primary-600 truncate block"
                  >{{ log.task_title }}</router-link>
                  <span class="text-xs text-surface-500">{{ log.user_name }}</span>
                  <span v-if="log.department" class="text-xs text-surface-400 ml-2">· {{ log.department }}</span>
                </div>
                <div class="text-xs font-mono text-surface-500 flex-shrink-0">
                  {{ formatHHMM(log.started_at) }}{{ log.is_active ? ' — сейчас' : '' }}
                </div>
                <div class="text-xs font-mono font-semibold text-primary-600 flex-shrink-0 w-16 text-right">
                  {{ formatTime(log.seconds) }}
                </div>
              </div>
            </div>
          </div>
          <p v-else class="text-sm text-surface-400 text-center py-8">Нет данных за период</p>
        </div>

        <!-- Right column: by user + top tasks -->
        <div class="space-y-4">
          <!-- By user -->
          <div v-if="authStore.isAdmin" class="bg-surface-0 dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
            <div class="p-4 border-b border-surface-200 dark:border-surface-700">
              <h3 class="text-sm font-semibold">По сотрудникам</h3>
            </div>
            <div class="p-3 space-y-2">
              <div
                v-for="u in (report.by_user || [])"
                :key="u.id"
                class="flex items-center gap-2 text-sm"
              >
                <span class="flex-1 truncate">{{ u.full_name || u.username }}</span>
                <span class="font-mono text-xs text-primary-600">{{ formatTime(u.seconds) }}</span>
              </div>
              <p v-if="!report.by_user?.length" class="text-sm text-surface-400 text-center py-2">Нет данных</p>
            </div>
          </div>

          <!-- Top tasks -->
          <div class="bg-surface-0 dark:bg-surface-800 rounded-xl border border-surface-200 dark:border-surface-700">
            <div class="p-4 border-b border-surface-200 dark:border-surface-700">
              <h3 class="text-sm font-semibold">Топ задач по времени</h3>
            </div>
            <div class="p-3 space-y-2">
              <div
                v-for="(t, idx) in (report.by_task || []).slice(0, 10)"
                :key="t.id"
                class="flex items-center gap-2 text-sm"
              >
                <span class="text-surface-400 w-5 text-right flex-shrink-0">{{ idx + 1 }}</span>
                <router-link
                  :to="`/tasks/${t.id}`"
                  class="flex-1 truncate hover:text-primary-600"
                >{{ t.title }}</router-link>
                <span class="font-mono text-xs text-primary-600 flex-shrink-0">{{ formatTime(t.seconds) }}</span>
              </div>
              <p v-if="!report.by_task?.length" class="text-sm text-surface-400 text-center py-2">Нет данных</p>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-else class="text-center text-surface-400 py-12">Нет данных</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAnalyticsStore } from '../stores/analytics.js'
import { useAuthStore } from '../stores/auth.js'
import { useUserStore } from '../stores/users.js'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import DatePicker from 'primevue/datepicker'
import Select from 'primevue/select'

const analyticsStore = useAnalyticsStore()
const authStore = useAuthStore()
const userStore = useUserStore()

const now = new Date()
const dateFrom = ref(new Date(now.getFullYear(), now.getMonth(), 1))
const dateTo = ref(new Date(now.getFullYear(), now.getMonth() + 1, 0))
const filterUserId = ref(0)

const report = computed(() => analyticsStore.timeReport)

const userOptions = computed(() =>
  userStore.users.map(u => ({ label: u.full_name || u.username, value: u.id }))
)

const groupedLogs = computed(() => {
  const logs = report.value?.detail_logs || []
  const byDate = {}
  for (const log of logs) {
    const date = log.started_at ? log.started_at.substring(0, 10) : 'unknown'
    if (!byDate[date]) byDate[date] = { date, logs: [], totalSeconds: 0 }
    byDate[date].logs.push(log)
    byDate[date].totalSeconds += log.seconds || 0
  }
  return Object.values(byDate)
    .sort((a, b) => b.date.localeCompare(a.date))
    .map(g => ({
      ...g,
      dateLabel: g.date !== 'unknown'
        ? new Date(g.date).toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
        : 'Без даты',
    }))
})

function toISO(d) {
  return d instanceof Date ? d.toISOString().split('T')[0] : undefined
}

async function load() {
  const params = { from: toISO(dateFrom.value), to: toISO(dateTo.value) }
  if (filterUserId.value) params.user_id = filterUserId.value
  await analyticsStore.fetchTime(params)
}

async function exportExcel() {
  await analyticsStore.exportExcel({ from: toISO(dateFrom.value), to: toISO(dateTo.value) })
}

function formatTime(s) {
  if (!s) return '0ч 0м'
  return `${Math.floor(s / 3600)}ч ${Math.floor((s % 3600) / 60)}м`
}

function formatHHMM(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

onMounted(async () => {
  if (authStore.isAdmin) await userStore.fetchUsers()
  await load()
})
</script>
