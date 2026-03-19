<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Планы</h1>
      <div class="flex gap-2">
        <Button label="Группа" icon="pi pi-folder-plus" outlined size="small" @click="showGroupDialog = true" />
        <Button label="Добавить план" icon="pi pi-plus" size="small" @click="openCreate" />
      </div>
    </div>

    <!-- Auto-converted banner -->
    <div
      v-if="planStore.autoConverted > 0"
      class="flex items-center gap-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-xl px-4 py-3 text-sm"
    >
      <span class="text-green-600 dark:text-green-400 font-medium">
        ✅ {{ planStore.autoConverted }} {{ planWord(planStore.autoConverted) }} автоматически преобразован{{ planStore.autoConverted > 1 ? 'ы' : '' }} в задачи
      </span>
    </div>

    <!-- Group filter -->
    <div class="flex gap-2 flex-wrap">
      <Button
        :label="`Все (${planStore.plans.length})`"
        :outlined="activeGroup !== null"
        size="small"
        @click="activeGroup = null"
      />
      <Button
        v-for="g in planStore.groups"
        :key="g.id"
        :label="g.name"
        :outlined="activeGroup !== g.id"
        size="small"
        @click="activeGroup = g.id"
      />
    </div>

    <!-- Plans grid -->
    <div v-if="filteredPlans.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="plan in filteredPlans"
        :key="plan.id"
        class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border hover:shadow-md transition-shadow"
        :class="plan.is_converted
          ? 'border-surface-200 dark:border-surface-700 opacity-60'
          : 'border-surface-200 dark:border-surface-700'"
      >
        <div class="flex items-start justify-between gap-2 mb-2">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-1.5 flex-wrap mb-1">
              <span
                v-if="plan.is_converted"
                class="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 font-medium"
              >Преобразован</span>
              <span
                v-if="plan.urgency && plan.urgency !== 'normal'"
                class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                :class="urgencyClass(plan.urgency)"
              >{{ urgencyLabel(plan.urgency) }}</span>
            </div>
            <h3 class="font-semibold text-surface-800 dark:text-surface-200 text-sm line-clamp-2">{{ plan.title }}</h3>
          </div>
          <div class="flex gap-1 flex-shrink-0">
            <Button
              v-if="!plan.is_converted"
              icon="pi pi-send"
              text
              size="small"
              @click="pushPlan(plan.id)"
              title="Преобразовать в задачу"
            />
            <Button icon="pi pi-pencil" text size="small" @click="openEdit(plan)" />
            <Button icon="pi pi-trash" text size="small" severity="danger" @click="deletePlan(plan.id)" />
          </div>
        </div>

        <p v-if="plan.description" class="text-xs text-surface-500 line-clamp-2 mb-2">{{ plan.description }}</p>

        <div class="flex items-center gap-2 flex-wrap text-xs">
          <span v-if="plan.group" class="text-surface-400">📁 {{ plan.group.name }}</span>
          <span
            v-if="plan.release_date"
            class="px-2 py-0.5 rounded-full font-medium"
            :class="releaseDateClass(plan.release_date)"
          >📅 {{ formatDate(plan.release_date) }}</span>
          <router-link
            v-if="plan.converted_task_id"
            :to="`/tasks/${plan.converted_task_id}`"
            class="text-primary-600 hover:underline"
          >→ Задача #{{ plan.converted_task_id }}</router-link>
        </div>
      </div>
    </div>
    <div v-else class="text-center text-surface-400 py-12">Планы не найдены</div>

    <!-- Plan dialog -->
    <Dialog
      v-model:visible="showPlanDialog"
      :header="editingPlan ? 'Редактировать план' : 'Новый план'"
      modal
      :style="{ width: '500px' }"
    >
      <div class="space-y-3">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Название *</label>
          <InputText v-model="planForm.title" class="w-full" placeholder="Название плана" />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Описание</label>
          <Textarea v-model="planForm.description" rows="3" class="w-full" placeholder="Подробное описание" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Группа</label>
            <Select
              v-model="planForm.group_id"
              :options="[{ name: 'Без группы', id: null }, ...planStore.groups]"
              optionLabel="name"
              optionValue="id"
              class="w-full"
            />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Срочность</label>
            <Select
              v-model="planForm.urgency"
              :options="urgencyOptions"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Тип задачи</label>
          <Select
            v-model="planForm.task_type"
            :options="taskTypeOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Выберите тип"
            class="w-full"
            showClear
          />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Дата релиза (автоконвертация)</label>
          <DatePicker v-model="planForm.release_date" dateFormat="dd.mm.yy" class="w-full" showIcon showTime hourFormat="24" />
        </div>

        <div class="flex gap-2 pt-2">
          <Button :label="editingPlan ? 'Сохранить' : 'Создать'" :loading="loading" @click="submitPlan" />
          <Button label="Отмена" text @click="showPlanDialog = false" />
        </div>
      </div>
    </Dialog>

    <!-- Group dialog -->
    <Dialog v-model:visible="showGroupDialog" header="Управление группами" modal :style="{ width: '400px' }">
      <div class="space-y-3">
        <div class="flex gap-2">
          <InputText v-model="newGroupName" placeholder="Название группы" class="flex-1" />
          <Button icon="pi pi-plus" @click="createGroup" />
        </div>
        <div v-if="planStore.groups.length" class="space-y-1">
          <div
            v-for="g in planStore.groups"
            :key="g.id"
            class="flex items-center justify-between py-1 border-b border-surface-100 dark:border-surface-700"
          >
            <span class="text-sm">{{ g.name }}</span>
            <Button icon="pi pi-trash" text size="small" severity="danger" @click="deleteGroup(g.id)" />
          </div>
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { usePlanStore } from '../stores/plans.js'
import { useToast } from 'primevue/usetoast'
import { friendlyError } from '../api/errors.js'
import { api } from '../api/index.js'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'

const planStore = usePlanStore()
const toast = useToast()

const activeGroup = ref(null)
const showPlanDialog = ref(false)
const showGroupDialog = ref(false)
const editingPlan = ref(null)
const loading = ref(false)
const newGroupName = ref('')
const taskTypeOptions = ref([])

const urgencyOptions = [
  { label: 'Не срочно', value: 'slow' },
  { label: 'Обычный',   value: 'normal' },
  { label: 'Важный',    value: 'important' },
  { label: 'Срочно',    value: 'urgent' },
]

const planForm = ref({
  title: '',
  description: '',
  group_id: null,
  urgency: 'normal',
  task_type: '',
  release_date: null,
})

const filteredPlans = computed(() => {
  if (activeGroup.value === null) return planStore.plans
  return planStore.plans.filter((p) => p.group_id === activeGroup.value)
})

function releaseDateClass(iso) {
  if (!iso) return ''
  const diff = new Date(iso) - new Date()
  if (diff < 0) return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  if (diff < 7 * 86400000) return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
  return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
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

function planWord(n) {
  if (n % 10 === 1 && n % 100 !== 11) return 'план'
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return 'плана'
  return 'планов'
}

function openCreate() {
  editingPlan.value = null
  planForm.value = { title: '', description: '', group_id: null, urgency: 'normal', task_type: '', release_date: null }
  showPlanDialog.value = true
}

function openEdit(plan) {
  editingPlan.value = plan
  planForm.value = {
    title: plan.title,
    description: plan.description || '',
    group_id: plan.group_id || null,
    urgency: plan.urgency || 'normal',
    task_type: plan.task_type || '',
    release_date: plan.release_date ? new Date(plan.release_date) : null,
  }
  showPlanDialog.value = true
}

async function submitPlan() {
  if (!planForm.value.title.trim()) return
  loading.value = true
  try {
    const payload = {
      ...planForm.value,
      task_type: planForm.value.task_type || null,
      release_date: planForm.value.release_date instanceof Date
        ? planForm.value.release_date.toISOString()
        : planForm.value.release_date || null,
    }
    if (editingPlan.value) {
      await planStore.updatePlan(editingPlan.value.id, payload)
    } else {
      await planStore.createPlan(payload)
    }
    showPlanDialog.value = false
    toast.add({ severity: 'success', summary: 'Сохранено', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    loading.value = false
  }
}

async function deletePlan(id) {
  await planStore.deletePlan(id)
}

async function pushPlan(id) {
  try {
    await planStore.pushPlan(id)
    toast.add({ severity: 'success', summary: 'Задача создана из плана', life: 2000 })
    await planStore.fetchPlans()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  }
}

async function createGroup() {
  if (!newGroupName.value.trim()) return
  await planStore.createGroup({ name: newGroupName.value })
  newGroupName.value = ''
}

async function deleteGroup(id) {
  await planStore.deleteGroup(id)
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

onMounted(async () => {
  const [, typesRes] = await Promise.all([planStore.fetchPlans(), api.tasks.types()])
  taskTypeOptions.value = typesRes.data.data || []
  await planStore.fetchGroups()
})
</script>
