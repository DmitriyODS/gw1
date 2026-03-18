<template>
  <div
    class="bg-surface-0 dark:bg-surface-800 rounded-lg p-3 shadow-sm border border-surface-200 dark:border-surface-700 cursor-grab active:cursor-grabbing select-none hover:shadow-md transition-shadow"
    draggable="true"
    @dragstart="onDragStart"
  >
    <div class="flex items-start justify-between gap-2 mb-2">
      <router-link
        :to="`/tasks/${task.id}`"
        class="text-sm font-medium text-surface-800 dark:text-surface-200 hover:text-primary-600 line-clamp-2 leading-tight"
        @click.stop
      >
        {{ task.title }}
      </router-link>
      <UrgencyBadge :urgency="task.urgency" />
    </div>

    <div class="text-xs text-surface-500 dark:text-surface-400 mb-2" v-if="task.deadline">
      📅 {{ formatDate(task.deadline) }}
    </div>

    <div class="flex items-center justify-between">
      <div class="flex items-center gap-1">
        <UserAvatar v-if="task.assigned_to" :user="task.assigned_to" size="sm" />
        <span v-if="task.assigned_to" class="text-xs text-surface-500 dark:text-surface-400 truncate max-w-[80px]">
          {{ task.assigned_to.full_name }}
        </span>
        <span v-else class="text-xs text-surface-400 italic">Не назначено</span>
      </div>
      <span v-if="task.total_seconds" class="text-xs font-mono text-surface-400">
        {{ formatTime(task.total_seconds) }}
      </span>
    </div>
  </div>
</template>

<script setup>
import UserAvatar from './UserAvatar.vue'
import UrgencyBadge from './UrgencyBadge.vue'

const props = defineProps({ task: { type: Object, required: true } })
const emit = defineEmits(['drag-start'])

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
