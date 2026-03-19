<template>
  <div v-if="taskStore.loading" class="flex justify-center p-8">
    <ProgressSpinner />
  </div>
  <div v-else-if="task" class="max-w-4xl mx-auto space-y-4">
    <!-- Header -->
    <div class="flex items-start justify-between gap-4">
      <div class="flex-1">
        <!-- Parent task indicator -->
        <div v-if="task.parent_task_id" class="flex items-center gap-2 mb-2">
          <span class="px-2 py-0.5 text-xs rounded-full bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 font-medium">
            📎 Подзадача
          </span>
          <router-link :to="`/tasks/${task.parent_task_id}`" class="text-xs text-violet-600 hover:underline">
            Перейти к родительской задаче →
          </router-link>
        </div>
        <div class="flex items-center gap-2 mb-1">
          <StatusBadge :status="task.status" />
          <UrgencyBadge :urgency="task.urgency" />
        </div>
        <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">{{ task.title }}</h1>
        <p v-if="task.department" class="text-sm text-surface-500 mt-1">{{ task.department?.name }}</p>
        <p v-if="task.task_type" class="text-xs text-surface-400 mt-0.5">{{ taskTypeLabel(task.task_type) }}</p>
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

    <!-- Tags -->
    <div v-if="task.tags?.length" class="flex flex-wrap gap-1.5">
      <span
        v-for="tag in task.tags"
        :key="tag"
        class="px-2 py-0.5 rounded-full text-xs font-medium"
        :class="tagClass(tag)"
      >{{ tagLabel(tag) }}</span>
    </div>

    <!-- Description -->
    <div v-if="task.description" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-2">Описание</h3>
      <p class="text-sm text-surface-700 dark:text-surface-300 whitespace-pre-wrap">{{ task.description }}</p>
    </div>

    <!-- Dynamic fields -->
    <div v-if="hasDynamicFields" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-3">Дополнительные параметры</h3>
      <dl class="grid grid-cols-2 gap-2 text-sm">
        <template v-if="df.pub_subtype">
          <dt class="text-surface-500">Подтип</dt>
          <dd>{{ df.pub_subtype === 'news' ? 'Новость' : 'Мероприятие' }}</dd>
        </template>
        <template v-if="df.platforms?.length">
          <dt class="text-surface-500">Площадки</dt>
          <dd>{{ df.platforms.join(', ') }}</dd>
        </template>
        <template v-if="df.pub_date">
          <dt class="text-surface-500">Дата публикации</dt>
          <dd>{{ formatDate(df.pub_date) }}</dd>
        </template>
        <template v-if="df.event_date">
          <dt class="text-surface-500">Дата мероприятия</dt>
          <dd>{{ formatDate(df.event_date) }}</dd>
        </template>
        <template v-if="df.link">
          <dt class="text-surface-500">Ссылка</dt>
          <dd><a :href="df.link" target="_blank" class="text-primary-600 hover:underline truncate">{{ df.link }}</a></dd>
        </template>
        <template v-if="df.task_link">
          <dt class="text-surface-500">Ссылка на задачу</dt>
          <dd>{{ df.task_link }}</dd>
        </template>
        <template v-if="df.clarification">
          <dt class="text-surface-500">Уточнение</dt>
          <dd>{{ df.clarification }}</dd>
        </template>
      </dl>
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
        <div class="text-sm" :class="isOverdue ? 'text-red-500 font-medium' : ''">
          {{ task.deadline ? formatDate(task.deadline) : '—' }}
          <span v-if="isOverdue"> ⚠️</span>
        </div>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-3 border border-surface-200 dark:border-surface-700">
        <div class="text-xs text-surface-500 mb-1">Затрачено</div>
        <div class="text-sm font-mono">{{ formatTime(totalSeconds) }}</div>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-3 border border-surface-200 dark:border-surface-700">
        <div class="text-xs text-surface-500 mb-1">Заказчик</div>
        <div class="text-sm">{{ task.customer_name || '—' }}</div>
        <div v-if="task.customer_phone" class="text-xs text-surface-400">{{ task.customer_phone }}</div>
      </div>
    </div>

    <!-- Subtasks -->
    <div v-if="task.subtasks?.length" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-3">
        Подзадачи
        <span class="ml-1 text-xs text-surface-400">({{ doneSubtasks }}/{{ task.subtasks.length }} завершено)</span>
      </h3>
      <div class="space-y-2">
        <div
          v-for="sub in task.subtasks"
          :key="sub.id"
          class="flex items-center gap-3 text-sm py-1 border-b border-surface-100 dark:border-surface-700 last:border-0"
        >
          <span class="w-2 h-2 rounded-full flex-shrink-0" :class="sub.status === 'done' ? 'bg-green-500' : 'bg-surface-300'" />
          <router-link :to="`/tasks/${sub.id}`" class="flex-1 hover:text-primary-600 truncate">{{ sub.title }}</router-link>
          <StatusBadge :status="sub.status" />
        </div>
      </div>
    </div>

    <!-- Timer controls -->
    <div v-if="isAssignee || authStore.isManager" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-3">
        Таймер
        <span v-if="activeElapsed" class="ml-2 font-mono text-primary-500">{{ formatTime(activeElapsed) }}</span>
      </h3>
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
          v-if="task.status !== 'done'"
          label="Завершить"
          icon="pi pi-check"
          size="small"
          severity="success"
          :disabled="hasOpenSubtasks"
          :title="hasOpenSubtasks ? 'Есть незавершённые подзадачи' : ''"
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
          label="Снять"
          icon="pi pi-user-minus"
          size="small"
          severity="secondary"
          outlined
          @click="unassign"
        />
      </div>
      <p v-if="hasOpenSubtasks" class="text-xs text-orange-500 mt-2">
        ⚠️ Нельзя завершить — есть открытые подзадачи
      </p>
    </div>

    <!-- Time logs history -->
    <div v-if="task.time_logs?.length" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-3">История времени</h3>
      <div class="space-y-1">
        <div
          v-for="log in task.time_logs"
          :key="log.id"
          class="flex items-center gap-3 text-xs py-1.5 border-b border-surface-100 dark:border-surface-700 last:border-0"
          :class="!log.ended_at ? 'bg-green-50 dark:bg-green-900/10 rounded px-2' : ''"
        >
          <UserAvatar v-if="log.user" :user="log.user" size="sm" />
          <span class="text-surface-600 dark:text-surface-400 flex-shrink-0">{{ log.user?.full_name }}</span>
          <span class="text-surface-400">{{ formatDateTime(log.started_at) }}</span>
          <span class="text-surface-400">→</span>
          <span v-if="log.ended_at" class="text-surface-400">{{ formatDateTime(log.ended_at) }}</span>
          <span v-else class="text-green-500 font-medium">активен</span>
          <span class="ml-auto font-mono font-medium">{{ formatTime(logSeconds(log)) }}</span>
        </div>
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
          <Button v-if="authStore.isAdmin" icon="pi pi-times" text size="small" severity="danger" @click="deleteAttachment(att.id)" />
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
            <a v-if="c.filename" :href="`/uploads/${c.filename}`" target="_blank" class="text-xs text-primary-600 hover:underline">
              📎 {{ c.original_name || c.filename }}
            </a>
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

// Computed helpers
const df = computed(() => task.value?.dynamic_fields || {})
const hasDynamicFields = computed(() => {
  const d = df.value
  return d.pub_subtype || d.platforms?.length || d.pub_date || d.event_date || d.link || d.task_link || d.clarification
})

const isOverdue = computed(() => {
  if (!task.value?.deadline || task.value.status === 'done') return false
  return new Date(task.value.deadline) < new Date()
})

const hasOpenSubtasks = computed(() =>
  task.value?.subtasks?.some((s) => s.status !== 'done') ?? false
)

const doneSubtasks = computed(() =>
  task.value?.subtasks?.filter((s) => s.status === 'done').length ?? 0
)

const totalSeconds = computed(() => {
  const logs = task.value?.time_logs || []
  return logs.reduce((acc, log) => {
    if (log.ended_at) {
      return acc + Math.floor((new Date(log.ended_at) - new Date(log.started_at)) / 1000)
    }
    return acc + Math.floor((Date.now() - new Date(log.started_at)) / 1000)
  }, 0)
})

const activeElapsed = computed(() => {
  if (timerStore.activeTimer?.task_id === task.value?.id) {
    return timerStore.elapsedSeconds
  }
  return 0
})

const TASK_TYPE_LABELS = {
  publication: 'Публикация', design_image: 'Разработка картинки',
  design_handout: 'Разработка раздатки', design_banner: 'Разработка баннера',
  design_poster: 'Разработка плаката/афиши', verify_presentation: 'Верификация презентации',
  design_presentation: 'Разработка презентации', verify_design: 'Верификация дизайна',
  design_merch: 'Разработка сувенирной продукции', design_cards: 'Разработка открыток',
  mailing: 'Выполнение корпоративных рассылок', photo_video: 'Фото/видео сопровождение',
  other: 'Другое', mail_check: 'Проверка почты', edits: 'Правки по задаче',
  video_edit: 'Монтаж видео', photo_edit: 'Обработка фото',
  internal_work: 'Внутренняя работа отдела', external_work: 'Внешняя работа отдела',
}

function taskTypeLabel(type) { return TASK_TYPE_LABELS[type] || type }

const TAG_LABELS = { design: 'Дизайн', text: 'Текст', publication: 'Публикация', photo_video: 'Фото/Видео', internal: 'Внутреннее', external: 'Внешнее' }
const TAG_CLASSES = {
  design: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  text: 'bg-blue-100 text-blue-700', publication: 'bg-green-100 text-green-700',
  photo_video: 'bg-orange-100 text-orange-700', internal: 'bg-surface-100 text-surface-600',
  external: 'bg-yellow-100 text-yellow-700',
}
function tagLabel(tag) { return TAG_LABELS[tag] || tag }
function tagClass(tag) { return TAG_CLASSES[tag] || 'bg-surface-100 text-surface-600' }

function logSeconds(log) {
  if (log.ended_at) return Math.floor((new Date(log.ended_at) - new Date(log.started_at)) / 1000)
  return Math.floor((Date.now() - new Date(log.started_at)) / 1000)
}

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
    const msg = friendlyError(e)
    if (msg === 'task already taken') {
      toast.add({ severity: 'warn', summary: 'Задача занята', detail: 'Эту задачу уже выполняет другой сотрудник', life: 4000 })
    } else if (msg === 'you already have an active timer') {
      toast.add({ severity: 'warn', summary: 'Конфликт таймера', detail: 'У вас уже запущен таймер. Сначала поставьте текущую задачу на паузу.', life: 4000 })
    } else {
      toast.add({ severity: 'error', summary: 'Ошибка', detail: msg, life: 3000 })
    }
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
    toast.add({ severity: 'info', summary: 'Задача перехвачена', life: 2000 })
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
    const msg = friendlyError(e)
    if (msg === 'has_open_subtasks') {
      toast.add({ severity: 'warn', summary: 'Нельзя завершить', detail: 'Сначала завершите все подзадачи', life: 4000 })
    } else {
      toast.add({ severity: 'error', summary: 'Ошибка', detail: msg, life: 3000 })
    }
  } finally {
    timerLoading.value = false
  }
}

async function unassign() {
  try {
    await api.tasks.unassign(task.value.id)
    await reload()
    toast.add({ severity: 'info', summary: 'Исполнитель снят', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  }
}

async function delegateTask() {
  if (!delegateTo.value) return
  try {
    await api.tasks.delegate(task.value.id, { user_id: delegateTo.value })
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
    const formData = new FormData()
    formData.append('text', newComment.value)
    await api.tasks.addComment(task.value.id, formData)
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
    message: 'Удалить задачу? Это действие нельзя отменить.',
    header: 'Подтверждение удаления',
    acceptSeverity: 'danger',
    acceptLabel: 'Удалить',
    rejectLabel: 'Отмена',
    accept: async () => {
      await taskStore.deleteTask(task.value.id)
      router.push('/')
    },
  })
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

function formatDateTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function formatTime(seconds) {
  if (!seconds) return '0ч 0м'
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
