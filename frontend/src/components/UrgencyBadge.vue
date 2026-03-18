<template>
  <Tag :value="label" :severity="severity" />
</template>

<script setup>
import { computed } from 'vue'
import Tag from 'primevue/tag'

const props = defineProps({ urgency: { type: String, default: 'normal' } })

const map = {
  slow:      { label: 'Не срочно', severity: 'secondary' },
  normal:    { label: 'Обычный',   severity: 'info' },
  important: { label: 'Важный',    severity: 'warn' },
  urgent:    { label: 'Срочно',    severity: 'danger' },
}

const label    = computed(() => map[props.urgency]?.label    ?? props.urgency)
const severity = computed(() => map[props.urgency]?.severity ?? 'secondary')
</script>
