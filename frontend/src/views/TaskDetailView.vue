<template>
  <div v-if="taskStore.loading" class="flex justify-center p-8">
    <ProgressSpinner />
  </div>
  <div v-else-if="task" class="max-w-4xl mx-auto space-y-4">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1">
        <div class="flex items-center gap-2 mb-1">
          <StatusBadge :status="task.status" />
          <UrgencyBadge :urgency="task.urgency" />
        </div>
        <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">{{ task.title }}</h1>
        <p v-if="task.department" class="text-sm text-surface-500 mt-1">{{ task.department?.name }}</p>
      </div>
      <div class="flex gap-2 flex-shrink-0">
        <Button
          v-if="authStore.isManager"
          label="Редактировать"
          icon="pi pi-pencil"
          size="small"
          outlined
          @click="router.push(`/tasks/${task.id}/edit`)"
        />
        <Button
          v-if="authStore.isAdmin"
          icon="pi pi-trash"
          size="small"
          severity="danger"
          outlined
          @click="confirmDelete"
        />
      </div>
    </div>

    <!-- Description -->
    <div v-if="task.description" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-2">Описание</h3>
      <p class="text-sm text-surface-700 dark:text-surface-300 whitespace-pre-wrap">{{ task.description }}</p>
    </div>

    <!-- Meta info -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-3 border border-surface-200 dark:border-surface-700">
        <div class="text-xs text-surface-500 mb-1">Исполнитель</div>
        <div class="flex items-center gap-2">
          <UserAvatar v-if="task.assigned_to" :user="task.assigned_to" size="sm" />
          <span class="text-sm">{{ task.assigned_to?.full_name || 'Не назначено' }}</span>
        </div>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-3 border border-surface-200 dark:border-surface-700">
        <div class="text-xs text-surface-500 mb-1">Срок</div>
        <div class="text-sm">{{ task.deadline ? formatDate(task.deadline) : '—' }}</div>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-3 border border-surface-200 dark:border-surface-700">
        <div class="text-xs text-surface-500 mb-1">Затрачено времени</div>
        <div class="text-sm font-mono">{{ formatTime(task.total_seconds || 0) }}</div>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-3 border border-surface-200 dark:border-surface-700">
        <div class="text-xs text-surface-500 mb-1">Тип</div>
        <div class="text-sm">{{ task.task_type || '—' }}</div>
      </div>
    </div>

    <!-- Timer controls -->
    <div v-if="isAssignee || authStore.isManager" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-3">Таймер</h3>
      <div class="flex gap-2 flex-wrap">
        <Button
          v-if="task.status === 'new' || task.status === 'paused'"
          label="Начать"
          icon="pi pi-play"
          size="small"
          severity="success"
          @click="startTimer"
          :loading="timerLoading"
        />
        <Button
          v-if="task.status === 'in_progress' && isAssignee"
          label="Пауза"
          icon="pi pi-pause"
          size="small"
          severity="warn"
          @click="pauseTimer"
          :loading="timerLoading"
        />
        <Button
          v-if="task.status === 'in_progress' && authStore.isManager && !isAssignee"
          label="Перехватить"
          icon="pi pi-bolt"
          size="small"
          severity="warn"
          @click="forceStart"
          :loading="timerLoading"
        />
        <Button
          v-if="task.status === 'in_progress'"
          label="Завершить"
          icon="pi pi-check"
          size="small"
          severity="success"
          @click="markDone"
          :loading="timerLoading"
        />
        <Button
          v-if="authStore.isAdmin && task.assigned_to_id"
          label="Передать"
          icon="pi pi-send"
          size="small"
          outlined
          @click="showDelegate = true"
        />
        <Button
          v-if="authStore.isAdmin && task.assigned_to_id"
          label="Снять назначение"
          icon="pi pi-user-minus"
          size="small"
          severity="secondary"
          outlined
          @click="unassign"
        />
      </div>
    </div>

    <!-- Attachments -->
    <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400">Файлы</h3>
        <div class="flex gap-2">
          <Button v-if="task.attachments?.length" label="ZIP" icon="pi pi-download" size="small" text @click="downloadZip" />
          <FileUpload
            mode="basic"
            auto
            customUpload
            chooseLabel="Загрузить"
            :maxFileSize="10000000"
            @uploader="uploadFile"
            class="p-button-sm"
          />
        </div>
      </div>
      <div v-if="task.attachments?.length" class="space-y-1">
        <div v-for="att in task.attachments" :key="att.id" class="flex items-center justify-between text-sm py-1 border-b border-surface-100 dark:border-surface-700 last:border-0">
          <a :href="`/uploads/${att.filename}`" target="_blank" class="text-primary-600 hover:underline truncate">
            {{ att.original_name || att.filename }}
          </a>
          <Button icon="pi pi-times" text size="small" severity="danger" @click="deleteAttachment(att.id)" />
        </div>
      </div>
      <p v-else class="text-sm text-surface-400 italic">Нет файлов</p>
    </div>

    <!-- Comments -->
    <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-3">Комментарии</h3>
      <div v-if="task.comments?.length" class="space-y-3 mb-4">
        <div v-for="c in task.comments" :key="c.id" class="flex gap-3">
          <UserAvatar :user="c.user" size="sm" />
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-xs font-medium text-surface-700 dark:text-surface-300">{{ c.user?.full_name }}</span>
              <span class="text-xs text-surface-400">{{ formatDate(c.created_at) }}</span>
              <Button
                v-if="canDeleteComment(c)"
                icon="pi pi-times"
                text size="small"
                severity="danger"
                class="ml-auto"
                @click="deleteComment(c.id)"
              />
            </div>
            <p class="text-sm text-surface-700 dark:text-surface-300 whitespace-pre-wrap">{{ c.text }}</p>
          </div>
        </div>
      </div>
      <div class="flex gap-2">
        <Textarea v-model="newComment" placeholder="Написать комментарий..." rows="2" class="flex-1" />
        <Button icon="pi pi-send" @click="addComment" :disabled="!newComment.trim()" />
      </div>
    </div>

    <!-- Delegate dialog -->
    <Dialog v-model:visible="showDelegate" header="Передать задачу" modal :style="{ width: '350px' }">
      <div class="flex flex-col gap-3">
        <label class="text-sm">Выберите исполнителя</label>
        <Select
          v-model="delegateTo"
          :options="users"
          optionLabel="full_name"
          optionValue="id"
          placeholder="Пользователь"
          class="w-full"
        />
        <Button label="Передать" @click="delegateTask" class="w-full" />
      </div>
    </Dialog>
  </div>
  <div v-else class="text-center text-surface-400 py-16">Задача не найдена</div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '../stores/tasks.js'
import { useAuthStore } from '../stores/auth.js'
import { useTimerStore } from '../stores/timer.js'
import { api } from '../api/index.js'
import { friendlyError } from '../api/errors.js'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import ProgressSpinner from 'primevue/progressspinner'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import FileUpload from 'primevue/fileupload'
import StatusBadge from '../components/StatusBadge.vue'
import UrgencyBadge from '../components/UrgencyBadge.vue'
import UserAvatar from '../components/UserAvatar.vue'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const authStore = useAuthStore()
const timerStore = useTimerStore()
const toast = useToast()
const confirm = useConfirm()

const task = computed(() => taskStore.currentTask)
const isAssignee = computed(() => task.value?.assigned_to_id === authStore.user?.id)
const timerLoading = ref(false)
const newComment = ref('')
const showDelegate = ref(false)
const delegateTo = ref(null)
const users = ref([])

async function reload() {
  await taskStore.fetchTask(route.params.id)
}

async function startTimer() {
  timerLoading.value = true
  try {
    await api.tasks.timerStart(task.value.id)
    await reload()
    timerStore.fetchTimer()
    toast.add({ severity: 'success', summary: 'Таймер запущен', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    timerLoading.value = false
  }
}

async function pauseTimer() {
  timerLoading.value = true
  try {
    await api.tasks.timerPause(task.value.id)
    await reload()
    timerStore.fetchTimer()
    toast.add({ severity: 'info', summary: 'Таймер на паузе', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    timerLoading.value = false
  }
}

async function forceStart() {
  timerLoading.value = true
  try {
    await api.tasks.timerForceStart(task.value.id)
    await reload()
    timerStore.fetchTimer()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    timerLoading.value = false
  }
}

async function markDone() {
  timerLoading.value = true
  try {
    await api.tasks.done(task.value.id)
    await reload()
    timerStore.fetchTimer()
    toast.add({ severity: 'success', summary: 'Задача завершена', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    timerLoading.value = false
  }
}

async function unassign() {
  try {
    await api.tasks.unassign(task.value.id)
    await reload()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  }
}

async function delegateTask() {
  if (!delegateTo.value) return
  try {
    await api.tasks.delegate(task.value.id, { assignee_id: delegateTo.value })
    showDelegate.value = false
    await reload()
    toast.add({ severity: 'success', summary: 'Задача передана', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  }
}

async function uploadFile(event) {
  const formData = new FormData()
  formData.append('file', event.files[0])
  try {
    await api.tasks.uploadAttachment(task.value.id, formData)
    await reload()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка загрузки', life: 3000 })
  }
}

async function deleteAttachment(attId) {
  try {
    await api.tasks.deleteAttachment(task.value.id, attId)
    await reload()
  } catch {}
}

async function downloadZip() {
  const response = await api.tasks.downloadZip(task.value.id)
  const url = URL.createObjectURL(new Blob([response.data]))
  const a = document.createElement('a')
  a.href = url
  a.download = `task_${task.value.id}_files.zip`
  a.click()
  URL.revokeObjectURL(url)
}

async function addComment() {
  if (!newComment.value.trim()) return
  try {
    await api.tasks.addComment(task.value.id, { text: newComment.value })
    newComment.value = ''
    await reload()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', life: 3000 })
  }
}

function canDeleteComment(c) {
  return authStore.isAdmin || c.user?.id === authStore.user?.id
}

async function deleteComment(commentId) {
  try {
    await api.tasks.deleteComment(task.value.id, commentId)
    await reload()
  } catch {}
}

function confirmDelete() {
  confirm.require({
    message: 'Удалить задачу?',
    header: 'Подтверждение',
    accept: async () => {
      await taskStore.deleteTask(task.value.id)
      router.push('/')
    },
  })
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}ч ${m}м`
}

onMounted(async () => {
  taskStore.loading = true
  await reload()
  taskStore.loading = false
  if (authStore.isAdmin) {
    const { data } = await api.users.list()
    users.value = data.data || []
  }
})
</script>
