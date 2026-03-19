<template>
  <div class="h-full flex flex-col gap-3">
    <!-- Top toolbar -->
    <div class="flex flex-wrap gap-2 items-center">
      <!-- Create button -->
      <Button
        v-if="authStore.isManager"
        label="Создать"
        icon="pi pi-plus"
        size="small"
        @click="router.push('/tasks/create')"
      />

      <!-- Status filter -->
      <Select
        v-model="filters.status"
        :options="statusOptions"
        optionLabel="label"
        optionValue="value"
        placeholder="Все статусы"
        class="w-36"
        @change="fetchData"
      />

      <!-- Assignee filter -->
      <Select
        v-model="filters.assignee_id"
        :options="[{ label: 'Все', value: '' }, ...assigneeOptions]"
        optionLabel="label"
        optionValue="value"
        placeholder="Исполнитель"
        class="w-36"
        @change="fetchData"
      />

      <!-- Free/Mine toggle -->
      <div class="flex rounded-lg overflow-hidden border border-surface-300 dark:border-surface-600 text-sm">
        <button
          v-for="opt in ownershipOptions"
          :key="opt.value"
          class="px-3 py-1.5 transition-colors"
          :class="filters.ownership === opt.value
            ? 'bg-primary-500 text-white'
            : 'bg-surface-0 dark:bg-surface-800 text-surface-600 dark:text-surface-400 hover:bg-surface-100 dark:hover:bg-surface-700'"
          @click="setOwnership(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>

    <!-- Tag filters -->
    <div class="flex flex-wrap gap-1.5">
      <button
        v-for="tag in TAGS"
        :key="tag.value"
        class="px-2.5 py-1 rounded-full text-xs font-medium border transition-colors"
        :class="filters.tags.includes(tag.value)
          ? 'bg-primary-500 text-white border-primary-500'
          : 'bg-surface-0 dark:bg-surface-800 border-surface-200 dark:border-surface-700 text-surface-600 dark:text-surface-400 hover:border-primary-400'"
        @click="toggleTag(tag.value)"
      >
        {{ tag.label }}
      </button>
      <button
        v-if="filters.tags.length"
        class="px-2.5 py-1 rounded-full text-xs border border-surface-200 dark:border-surface-700 text-surface-400 hover:text-red-400 transition-colors"
        @click="filters.tags = []; fetchData()"
      >
        ✕ Сбросить
      </button>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '../stores/tasks.js'
import { useAuthStore } from '../stores/auth.js'
import { useUserStore } from '../stores/users.js'
import Select from 'primevue/select'
import Button from 'primevue/button'
import KanbanColumn from '../components/KanbanColumn.vue'
import { useToast } from 'primevue/usetoast'
import { friendlyError } from '../api/errors.js'

const router = useRouter()
const taskStore = useTaskStore()
const authStore = useAuthStore()
const userStore = useUserStore()
const toast = useToast()

const TAGS = [
  { value: 'design',      label: 'Дизайн' },
  { value: 'text',        label: 'Текст' },
  { value: 'publication', label: 'Публикация' },
  { value: 'photo_video', label: 'Фото/Видео' },
  { value: 'internal',    label: 'Внутреннее' },
  { value: 'external',    label: 'Внешнее' },
]

const ownershipOptions = [
  { label: 'Все', value: 'all' },
  { label: 'Свободные', value: 'free' },
  { label: 'Мои', value: 'mine' },
]

const filters = ref({
  status: '',
  assignee_id: '',
  ownership: 'all',
  tags: [],
})

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

function setOwnership(val) {
  filters.value.ownership = val
  fetchData()
}

function toggleTag(tag) {
  const idx = filters.value.tags.indexOf(tag)
  if (idx === -1) filters.value.tags.push(tag)
  else filters.value.tags.splice(idx, 1)
  fetchData()
}

async function fetchData() {
  const params = {}
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.assignee_id) params.assigned_to_id = filters.value.assignee_id
  if (filters.value.ownership === 'free') params.free = true
  if (filters.value.ownership === 'mine' && authStore.user?.id) params.assigned_to_id = authStore.user.id
  if (filters.value.tags.length) params.tags = filters.value.tags.join(',')
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

// Auto-refresh every 20s
let pollInterval = null

onMounted(async () => {
  await Promise.all([fetchData(), userStore.fetchUsers()])
  pollInterval = setInterval(fetchData, 20_000)
})

onUnmounted(() => {
  clearInterval(pollInterval)
})
</script>
