<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Ритмы</h1>
      <Button label="Добавить ритм" icon="pi pi-plus" size="small" @click="openCreate" />
    </div>

    <div v-if="rhythmStore.rhythms.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="rhythm in rhythmStore.rhythms"
        :key="rhythm.id"
        class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700"
      >
        <div class="flex items-start justify-between mb-2">
          <div class="flex-1 min-w-0">
            <h3 class="font-semibold text-sm truncate">{{ rhythm.name }}</h3>
            <p class="text-xs text-surface-500 mt-0.5">{{ freqLabel(rhythm) }}</p>
          </div>
          <div class="flex items-center gap-1 flex-shrink-0">
            <Button icon="pi pi-play" text size="small" @click="confirmRun(rhythm)" title="Запустить сейчас" />
            <Button icon="pi pi-pencil" text size="small" @click="openEdit(rhythm)" />
            <Button icon="pi pi-trash" text size="small" severity="danger" @click="deleteRhythm(rhythm.id)" />
          </div>
        </div>

        <p v-if="rhythm.description" class="text-xs text-surface-500 mb-2 line-clamp-2">{{ rhythm.description }}</p>

        <!-- Task info -->
        <div class="bg-surface-50 dark:bg-surface-900/50 rounded-lg p-2 mb-3 space-y-1">
          <p class="text-xs font-medium text-surface-700 dark:text-surface-300 truncate">📋 {{ rhythm.task_title }}</p>
          <div class="flex flex-wrap gap-1">
            <span
              v-if="rhythm.task_urgency && rhythm.task_urgency !== 'normal'"
              class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
              :class="urgencyClass(rhythm.task_urgency)"
            >{{ urgencyLabel(rhythm.task_urgency) }}</span>
            <span v-if="rhythm.task_type" class="text-[10px] px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400 font-medium">
              {{ rhythm.task_type }}
            </span>
          </div>
        </div>

        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span
              class="text-[10px] px-2 py-0.5 rounded-full font-medium"
              :class="rhythm.is_active
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-surface-100 text-surface-500 dark:bg-surface-700'"
            >{{ rhythm.is_active ? 'Активен' : 'Выключен' }}</span>
            <span v-if="rhythm.last_run_at" class="text-[10px] text-surface-400">
              {{ formatDate(rhythm.last_run_at) }}
            </span>
          </div>
          <Button
            :label="rhythm.is_active ? 'Выключить' : 'Включить'"
            :severity="rhythm.is_active ? 'secondary' : 'success'"
            size="small"
            outlined
            @click="toggleRhythm(rhythm)"
          />
        </div>
      </div>
    </div>
    <div v-else class="text-center text-surface-400 py-12">Ритмы не настроены</div>

    <!-- Edit/Create dialog -->
    <Dialog v-model:visible="showDialog" :header="editing ? 'Редактировать ритм' : 'Новый ритм'" modal :style="{ width: '520px' }">
      <div class="space-y-4">
        <!-- Rhythm name -->
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Название ритма *</label>
          <InputText v-model="form.name" class="w-full" placeholder="Например: Еженедельный отчёт" />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Описание</label>
          <Textarea v-model="form.description" rows="2" class="w-full" placeholder="Описание ритма" />
        </div>

        <!-- Frequency -->
        <div class="grid grid-cols-3 gap-3">
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Частота *</label>
            <Select
              v-model="form.frequency"
              :options="frequencyOptions"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>
          <div v-if="form.frequency === 'weekly'" class="flex flex-col gap-1">
            <label class="text-sm font-medium">День недели</label>
            <Select
              v-model="form.day_of_week"
              :options="weekdayOptions"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>
          <div v-if="form.frequency === 'monthly'" class="flex flex-col gap-1">
            <label class="text-sm font-medium">День месяца</label>
            <Select
              v-model="form.day_of_month"
              :options="dayOfMonthOptions"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>
        </div>

        <!-- Task fields -->
        <div class="border-t border-surface-200 dark:border-surface-700 pt-3">
          <p class="text-xs font-semibold text-surface-500 uppercase tracking-wide mb-3">Параметры задачи</p>
          <div class="space-y-3">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Название задачи *</label>
              <InputText v-model="form.task_title" class="w-full" placeholder="Название создаваемой задачи" />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Описание задачи</label>
              <Textarea v-model="form.task_description" rows="2" class="w-full" placeholder="Описание" />
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium">Срочность</label>
                <Select
                  v-model="form.task_urgency"
                  :options="urgencyOptions"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                />
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium">Тип задачи</label>
                <Select
                  v-model="form.task_type"
                  :options="taskTypeOptions"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="Без типа"
                  class="w-full"
                  showClear
                />
              </div>
            </div>
          </div>
        </div>

        <div class="flex gap-2 pt-2">
          <Button :label="editing ? 'Сохранить' : 'Создать'" :loading="loading" @click="submit" />
          <Button label="Отмена" text @click="showDialog = false" />
        </div>
      </div>
    </Dialog>

    <!-- Run confirmation dialog -->
    <Dialog v-model:visible="showRunConfirm" header="Запустить ритм?" modal :style="{ width: '380px' }">
      <div class="space-y-3">
        <p class="text-sm text-surface-600 dark:text-surface-400">
          Будет создана задача «<strong>{{ runTarget?.task_title }}</strong>» прямо сейчас.
        </p>
        <p class="text-xs text-surface-500">Это действие не отменяется.</p>
        <div class="flex gap-2 pt-2">
          <Button label="Запустить" icon="pi pi-play" severity="success" :loading="runLoading" @click="executeRun" />
          <Button label="Отмена" text @click="showRunConfirm = false" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRhythmStore } from '../stores/rhythms.js'
import { useToast } from 'primevue/usetoast'
import { friendlyError } from '../api/errors.js'
import { api } from '../api/index.js'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'

const rhythmStore = useRhythmStore()
const toast = useToast()
const showDialog = ref(false)
const showRunConfirm = ref(false)
const editing = ref(null)
const runTarget = ref(null)
const loading = ref(false)
const runLoading = ref(false)
const taskTypeOptions = ref([])

const emptyForm = () => ({
  name: '',
  description: '',
  frequency: 'weekly',
  day_of_week: 1,
  day_of_month: 1,
  task_title: '',
  task_description: '',
  task_urgency: 'normal',
  task_type: null,
})

const form = ref(emptyForm())

const frequencyOptions = [
  { label: 'Ежедневно', value: 'daily' },
  { label: 'Еженедельно', value: 'weekly' },
  { label: 'Ежемесячно', value: 'monthly' },
]

const weekdayOptions = [
  { label: 'Понедельник', value: 1 },
  { label: 'Вторник', value: 2 },
  { label: 'Среда', value: 3 },
  { label: 'Четверг', value: 4 },
  { label: 'Пятница', value: 5 },
  { label: 'Суббота', value: 6 },
  { label: 'Воскресенье', value: 0 },
]

const dayOfMonthOptions = Array.from({ length: 31 }, (_, i) => ({ label: `${i + 1}`, value: i + 1 }))

const urgencyOptions = [
  { label: 'Не срочно', value: 'slow' },
  { label: 'Обычный',   value: 'normal' },
  { label: 'Важный',    value: 'important' },
  { label: 'Срочно',    value: 'urgent' },
]

function freqLabel(r) {
  if (r.frequency === 'daily') return 'Ежедневно'
  if (r.frequency === 'weekly') {
    const wd = weekdayOptions.find(w => w.value === r.day_of_week)
    return `Еженедельно · ${wd?.label ?? ''}`
  }
  if (r.frequency === 'monthly') return `Ежемесячно · ${r.day_of_month} числа`
  return r.frequency
}

function urgencyClass(urgency) {
  const map = {
    slow:      'bg-surface-100 text-surface-500',
    normal:    'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    important: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    urgent:    'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  }
  return map[urgency] || ''
}

function urgencyLabel(urgency) {
  return { slow: 'Не срочно', normal: 'Обычный', important: 'Важный', urgent: 'Срочно' }[urgency] || urgency
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function openCreate() {
  editing.value = null
  form.value = emptyForm()
  showDialog.value = true
}

function openEdit(r) {
  editing.value = r
  form.value = {
    name: r.name,
    description: r.description || '',
    frequency: r.frequency || 'weekly',
    day_of_week: r.day_of_week ?? 1,
    day_of_month: r.day_of_month ?? 1,
    task_title: r.task_title || '',
    task_description: r.task_description || '',
    task_urgency: r.task_urgency || 'normal',
    task_type: r.task_type || null,
  }
  showDialog.value = true
}

async function submit() {
  if (!form.value.name.trim() || !form.value.task_title.trim()) {
    toast.add({ severity: 'warn', summary: 'Укажите название ритма и задачи', life: 2000 })
    return
  }
  loading.value = true
  try {
    const payload = { ...form.value }
    if (payload.frequency !== 'weekly') delete payload.day_of_week
    if (payload.frequency !== 'monthly') delete payload.day_of_month
    if (!payload.task_type) payload.task_type = null

    if (editing.value) {
      await rhythmStore.updateRhythm(editing.value.id, payload)
    } else {
      await rhythmStore.createRhythm(payload)
    }
    showDialog.value = false
    toast.add({ severity: 'success', summary: 'Сохранено', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    loading.value = false
  }
}

async function deleteRhythm(id) {
  await rhythmStore.deleteRhythm(id)
}

async function toggleRhythm(r) {
  await rhythmStore.toggleRhythm(r.id)
}

function confirmRun(rhythm) {
  runTarget.value = rhythm
  showRunConfirm.value = true
}

async function executeRun() {
  if (!runTarget.value) return
  runLoading.value = true
  try {
    await rhythmStore.runRhythm(runTarget.value.id)
    showRunConfirm.value = false
    toast.add({ severity: 'success', summary: 'Задача создана', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    runLoading.value = false
  }
}

onMounted(async () => {
  const [, typesRes] = await Promise.all([rhythmStore.fetchRhythms(), api.tasks.types()])
  taskTypeOptions.value = typesRes.data.data || []
})
</script>
