<template>
  <Tag :value="label" :severity="severity" />
</template>

<script setup>
import { computed } from 'vue'
import Tag from 'primevue/tag'

const props = defineProps({ status: { type: String, required: true } })

const map = {
  new:         { label: 'Новая',    severity: 'secondary' },
  in_progress: { label: 'В работе', severity: 'info' },
  paused:      { label: 'Пауза',    severity: 'warn' },
  done:        { label: 'Готово',   severity: 'success' },
}

const label    = computed(() => map[props.status]?.label    ?? props.status)
const severity = computed(() => map[props.status]?.severity ?? 'secondary')
</script>
