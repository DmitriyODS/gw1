<template>
  <div class="h-full flex flex-col gap-4">
    <!-- Filters -->
    <div class="flex flex-wrap gap-2 items-center">
      <InputText v-model="filters.search" placeholder="Поиск..." class="w-48" @input="debounceFetch" />
      <Select
        v-model="filters.status"
        :options="statusOptions"
        optionLabel="label"
        optionValue="value"
        placeholder="Все статусы"
        class="w-40"
        @change="fetchData"
      />
      <Select
        v-model="filters.assignee_id"
        :options="[{ label: 'Все', value: '' }, ...assigneeOptions]"
        optionLabel="label"
        optionValue="value"
        placeholder="Исполнитель"
        class="w-40"
        @change="fetchData"
      />
      <Button
        v-if="authStore.isManager"
        label="Создать"
        icon="pi pi-plus"
        size="small"
        @click="router.push('/tasks/create')"
      />
    </div>

    <!-- Kanban board -->
    <div class="flex-1 flex gap-3 overflow-x-auto pb-2">
      <KanbanColumn
        v-for="col in columns"
        :key="col.status"
        :title="col.title"
        :status="col.status"
        :tasks="tasksByStatus[col.status] || []"
        :can-drop="col.status !== 'in_progress' && col.status !== 'done'"
        @drop="handleDrop"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '../stores/tasks.js'
import { useAuthStore } from '../stores/auth.js'
import { useUserStore } from '../stores/users.js'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import KanbanColumn from '../components/KanbanColumn.vue'
import { useToast } from 'primevue/usetoast'
import { api } from '../api/index.js'
import { friendlyError } from '../api/errors.js'

const router = useRouter()
const taskStore = useTaskStore()
const authStore = useAuthStore()
const userStore = useUserStore()
const toast = useToast()

const filters = ref({ search: '', status: '', assignee_id: '' })

const statusOptions = [
  { label: 'Все', value: '' },
  { label: 'Новые', value: 'new' },
  { label: 'В работе', value: 'in_progress' },
  { label: 'Пауза', value: 'paused' },
  { label: 'Готово', value: 'done' },
]

const columns = [
  { status: 'new',         title: 'Новые' },
  { status: 'in_progress', title: 'В работе' },
  { status: 'paused',      title: 'Пауза' },
  { status: 'done',        title: 'Готово' },
]

const assigneeOptions = computed(() =>
  userStore.users.map((u) => ({ label: u.full_name || u.username, value: u.id }))
)

const tasksByStatus = computed(() => {
  const map = {}
  for (const t of taskStore.tasks) {
    if (!map[t.status]) map[t.status] = []
    map[t.status].push(t)
  }
  return map
})

let debounceTimer = null
function debounceFetch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fetchData, 300)
}

async function fetchData() {
  const params = {}
  if (filters.value.search) params.search = filters.value.search
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.assignee_id) params.assignee_id = filters.value.assignee_id
  await taskStore.fetchTasks(params)
}

async function handleDrop({ taskId, status }) {
  try {
    await taskStore.moveTask(taskId, status)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e) || 'Не удалось переместить', life: 3000 })
    fetchData()
  }
}

onMounted(async () => {
  await Promise.all([fetchData(), userStore.fetchUsers()])
})
</script>
