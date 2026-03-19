<template>
  <div
    class="bg-surface-0 dark:bg-surface-800 rounded-lg p-3 shadow-sm border cursor-grab active:cursor-grabbing select-none hover:shadow-md transition-all"
    :class="[
      isOthersBusy
        ? 'border-surface-200 dark:border-surface-700 opacity-60 grayscale'
        : 'border-surface-200 dark:border-surface-700',
    ]"
    draggable="true"
    @dragstart="onDragStart"
  >
    <!-- Title row -->
    <div class="flex items-start justify-between gap-2 mb-2">
      <router-link
        :to="`/tasks/${task.id}`"
        class="text-sm font-medium text-surface-800 dark:text-surface-200 hover:text-primary-600 line-clamp-2 leading-tight flex-1"
        @click.stop
      >
        {{ task.title }}
      </router-link>
      <div class="flex items-center gap-1 flex-shrink-0">
        <!-- Subtask indicator -->
        <span
          v-if="hasSubtasks"
          class="w-2 h-2 rounded-full bg-violet-500 flex-shrink-0"
          title="Есть подзадачи"
        />
        <UrgencyBadge :urgency="task.urgency" />
      </div>
    </div>

    <!-- Tags -->
    <div v-if="task.tags?.length" class="flex flex-wrap gap-1 mb-2">
      <span
        v-for="tag in task.tags"
        :key="tag"
        class="px-1.5 py-0.5 rounded text-[10px] font-medium"
        :class="tagClass(tag)"
      >{{ tagLabel(tag) }}</span>
    </div>

    <!-- Deadline -->
    <div
      v-if="task.deadline"
      class="text-xs mb-2 font-medium"
      :class="isOverdue ? 'text-red-500' : 'text-surface-500 dark:text-surface-400'"
    >
      📅 {{ formatDate(task.deadline) }}
      <span v-if="isOverdue" class="ml-1">⚠️ Просрочено</span>
    </div>

    <!-- Footer: assignee + ownership badge + time -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-1.5">
        <UserAvatar v-if="task.assigned_to" :user="task.assigned_to" size="sm" />
        <span v-if="task.assigned_to" class="text-xs text-surface-500 dark:text-surface-400 truncate max-w-[80px]">
          {{ task.assigned_to.full_name }}
        </span>
        <span v-else class="text-xs text-surface-400 italic">Не назначено</span>
      </div>
      <div class="flex items-center gap-1.5">
        <!-- Ownership status badge -->
        <span v-if="ownershipLabel" class="text-[10px] px-1.5 py-0.5 rounded-full font-medium" :class="ownershipClass">
          {{ ownershipLabel }}
        </span>
        <span v-if="task.total_seconds" class="text-xs font-mono text-surface-400">
          {{ formatTime(task.total_seconds) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import UserAvatar from './UserAvatar.vue'
import UrgencyBadge from './UrgencyBadge.vue'

const props = defineProps({ task: { type: Object, required: true } })
const emit = defineEmits(['drag-start'])
const authStore = useAuthStore()

const hasSubtasks = computed(() => props.task.subtasks?.length > 0)

const isOthersBusy = computed(() =>
  props.task.assigned_to_id != null &&
  props.task.assigned_to_id !== authStore.user?.id &&
  props.task.status === 'in_progress'
)

const isOverdue = computed(() => {
  if (!props.task.deadline || props.task.status === 'done') return false
  return new Date(props.task.deadline) < new Date()
})

const ownershipLabel = computed(() => {
  const myId = authStore.user?.id
  if (!props.task.assigned_to_id) return null
  if (props.task.assigned_to_id === myId) {
    return props.task.status === 'in_progress' ? 'В работе' : 'Моя'
  }
  return 'Занята'
})

const ownershipClass = computed(() => {
  const myId = authStore.user?.id
  if (props.task.assigned_to_id === myId) {
    return props.task.status === 'in_progress'
      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
      : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
  }
  return 'bg-surface-100 text-surface-500 dark:bg-surface-700 dark:text-surface-400'
})

const TAG_LABELS = {
  design: 'Дизайн',
  text: 'Текст',
  publication: 'Публикация',
  photo_video: 'Фото/Видео',
  internal: 'Внутреннее',
  external: 'Внешнее',
}

const TAG_CLASSES = {
  design:      'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300',
  text:        'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
  publication: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  photo_video: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
  internal:    'bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-300',
  external:    'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
}

function tagLabel(tag) { return TAG_LABELS[tag] || tag }
function tagClass(tag) { return TAG_CLASSES[tag] || 'bg-surface-100 text-surface-600' }

function onDragStart(e) {
  e.dataTransfer.setData('task_id', props.task.id)
  emit('drag-start', props.task)
}

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}ч ${m}м`
}
</script>
