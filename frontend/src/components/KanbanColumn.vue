<template>
  <div
    class="flex flex-col bg-surface-100 dark:bg-surface-850 rounded-xl min-w-[260px] max-w-[300px] flex-1"
    :class="{ 'ring-2 ring-primary-400': isDragOver }"
    @dragover.prevent="onDragOver"
    @dragleave="isDragOver = false"
    @drop="onDrop"
  >
    <div class="flex items-center justify-between px-3 py-2 border-b border-surface-200 dark:border-surface-700">
      <span class="font-semibold text-sm text-surface-700 dark:text-surface-300">{{ title }}</span>
      <Badge :value="tasks.length" severity="secondary" />
    </div>
    <div class="flex-1 overflow-y-auto p-2 space-y-2 min-h-[100px]">
      <TaskCard
        v-for="task in tasks"
        :key="task.id"
        :task="task"
        @drag-start="$emit('drag-start', $event)"
      />
      <div v-if="tasks.length === 0" class="text-center text-xs text-surface-400 py-4">
        Пусто
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import Badge from 'primevue/badge'
import TaskCard from './TaskCard.vue'

const props = defineProps({
  title: { type: String, required: true },
  status: { type: String, required: true },
  tasks: { type: Array, default: () => [] },
  canDrop: { type: Boolean, default: true },
})
const emit = defineEmits(['drop', 'drag-start'])

const isDragOver = ref(false)

function onDragOver() {
  if (props.canDrop) isDragOver.value = true
}

function onDrop(e) {
  isDragOver.value = false
  if (!props.canDrop) return
  const taskId = parseInt(e.dataTransfer.getData('task_id'))
  if (taskId) emit('drop', { taskId, status: props.status })
}
</script>
