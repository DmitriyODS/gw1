<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between flex-wrap gap-2">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Отчёт по времени</h1>
      <div class="flex items-center gap-2 flex-wrap">
        <DatePicker v-model="dateFrom" dateFormat="dd.mm.yy" placeholder="С" class="w-32" showIcon />
        <DatePicker v-model="dateTo" dateFormat="dd.mm.yy" placeholder="По" class="w-32" showIcon />
        <Button label="Применить" size="small" @click="load" />
        <Button label="Excel" icon="pi pi-download" outlined size="small" @click="exportExcel" />
      </div>
    </div>

    <div v-if="analyticsStore.loading" class="flex justify-center py-12">
      <ProgressSpinner />
    </div>

    <DataTable
      v-else-if="rows.length"
      :value="rows"
      class="text-sm"
      stripedRows
      paginator
      :rows="25"
    >
      <Column field="user" header="Сотрудник" />
      <Column field="task" header="Задача" />
      <Column field="department" header="Отдел" />
      <Column field="hours" header="Часы" style="width: 100px" />
      <Column field="date" header="Дата" style="width: 120px" />
    </DataTable>
    <div v-else class="text-center text-surface-400 py-12">Нет данных</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAnalyticsStore } from '../stores/analytics.js'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import DatePicker from 'primevue/datepicker'

const analyticsStore = useAnalyticsStore()

const now = new Date()
const dateFrom = ref(new Date(now.getFullYear(), now.getMonth(), 1))
const dateTo = ref(new Date(now.getFullYear(), now.getMonth() + 1, 0))

const rows = computed(() => {
  const data = analyticsStore.timeReport
  if (!Array.isArray(data)) return []
  return data.map((r) => ({
    user: r.user_name,
    task: r.task_title,
    department: r.department_name,
    hours: (r.seconds / 3600).toFixed(1),
    date: r.date ? new Date(r.date).toLocaleDateString('ru-RU') : '—',
  }))
})

function toISO(d) {
  return d instanceof Date ? d.toISOString().split('T')[0] : undefined
}

async function load() {
  await analyticsStore.fetchTime({ from: toISO(dateFrom.value), to: toISO(dateTo.value) })
}

async function exportExcel() {
  await analyticsStore.exportExcel({ from: toISO(dateFrom.value), to: toISO(dateTo.value) })
}

onMounted(load)
</script>
