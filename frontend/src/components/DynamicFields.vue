<template>
  <div v-if="fields.length" class="space-y-3">
    <h3 class="text-sm font-semibold text-surface-600 dark:text-surface-400">Дополнительные поля</h3>
    <div v-for="field in fields" :key="field.key" class="flex flex-col gap-1">
      <label class="text-xs font-medium text-surface-600 dark:text-surface-400">{{ field.label }}</label>
      <Textarea
        v-if="field.type === 'textarea'"
        v-model="modelValue[field.key]"
        :placeholder="field.placeholder"
        rows="3"
        class="w-full"
      />
      <InputText
        v-else
        v-model="modelValue[field.key]"
        :placeholder="field.placeholder"
        class="w-full"
      />
    </div>
  </div>
</template>

<script setup>
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'

defineProps({
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
})
defineEmits(['update:modelValue'])
</script>
