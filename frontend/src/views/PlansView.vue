<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Планы</h1>
      <div class="flex gap-2">
        <Button label="Группа" icon="pi pi-folder-plus" outlined size="small" @click="showGroupDialog = true" />
        <Button label="Добавить план" icon="pi pi-plus" size="small" @click="openCreate" />
      </div>
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
        class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 hover:shadow-md transition-shadow"
      >
        <div class="flex items-start justify-between gap-2 mb-2">
          <h3 class="font-semibold text-surface-800 dark:text-surface-200 text-sm line-clamp-2">{{ plan.title }}</h3>
          <div class="flex gap-1 flex-shrink-0">
            <Button icon="pi pi-send" text size="small" @click="pushPlan(plan.id)" title="Преобразовать в задачу" />
            <Button icon="pi pi-pencil" text size="small" @click="openEdit(plan)" />
            <Button icon="pi pi-trash" text size="small" severity="danger" @click="deletePlan(plan.id)" />
          </div>
        </div>
        <p v-if="plan.description" class="text-xs text-surface-500 line-clamp-2 mb-2">{{ plan.description }}</p>
        <div class="flex items-center gap-2 text-xs text-surface-400">
          <span v-if="plan.group">📁 {{ plan.group.name }}</span>
          <span v-if="plan.due_date">📅 {{ formatDate(plan.due_date) }}</span>
        </div>
      </div>
    </div>
    <div v-else class="text-center text-surface-400 py-12">Планы не найдены</div>

    <!-- Plan dialog -->
    <Dialog v-model:visible="showPlanDialog" :header="editingPlan ? 'Редактировать план' : 'Новый план'" modal :style="{ width: '450px' }">
      <div class="space-y-3">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Название *</label>
          <InputText v-model="planForm.title" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Описание</label>
          <Textarea v-model="planForm.description" rows="3" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Группа</label>
          <Select v-model="planForm.group_id" :options="[{ name: 'Без группы', id: null }, ...planStore.groups]" optionLabel="name" optionValue="id" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Срок</label>
          <DatePicker v-model="planForm.due_date" dateFormat="dd.mm.yy" class="w-full" showIcon />
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
          <div v-for="g in planStore.groups" :key="g.id" class="flex items-center justify-between py-1 border-b border-surface-100 dark:border-surface-700">
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

const planForm = ref({ title: '', description: '', group_id: null, due_date: null })

const filteredPlans = computed(() => {
  if (activeGroup.value === null) return planStore.plans
  return planStore.plans.filter((p) => p.group_id === activeGroup.value)
})

function openCreate() {
  editingPlan.value = null
  planForm.value = { title: '', description: '', group_id: null, due_date: null }
  showPlanDialog.value = true
}

function openEdit(plan) {
  editingPlan.value = plan
  planForm.value = {
    title: plan.title,
    description: plan.description || '',
    group_id: plan.group_id || null,
    due_date: plan.due_date ? new Date(plan.due_date) : null,
  }
  showPlanDialog.value = true
}

async function submitPlan() {
  if (!planForm.value.title.trim()) return
  loading.value = true
  try {
    const payload = { ...planForm.value }
    if (payload.due_date instanceof Date) payload.due_date = payload.due_date.toISOString()
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

onMounted(() => {
  planStore.fetchPlans()
  planStore.fetchGroups()
})
</script>
