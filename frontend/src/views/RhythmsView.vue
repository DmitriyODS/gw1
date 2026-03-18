<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Ритмы</h1>
      <Button label="Добавить ритм" icon="pi pi-plus" size="small" @click="openCreate" />
    </div>

    <div v-if="rhythmStore.rhythms.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="rhythm in rhythmStore.rhythms"
        :key="rhythm.id"
        class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700"
      >
        <div class="flex items-start justify-between mb-2">
          <div class="flex-1">
            <h3 class="font-semibold text-sm">{{ rhythm.title }}</h3>
            <p class="text-xs text-surface-500 mt-0.5">{{ rhythm.cron_expr }}</p>
          </div>
          <div class="flex items-center gap-1">
            <Button icon="pi pi-play" text size="small" @click="runRhythm(rhythm.id)" title="Запустить сейчас" />
            <Button icon="pi pi-pencil" text size="small" @click="openEdit(rhythm)" />
            <Button icon="pi pi-trash" text size="small" severity="danger" @click="deleteRhythm(rhythm.id)" />
          </div>
        </div>
        <p v-if="rhythm.description" class="text-xs text-surface-500 mb-3 line-clamp-2">{{ rhythm.description }}</p>
        <div class="flex items-center justify-between">
          <Tag :value="rhythm.is_active ? 'Активен' : 'Выключен'" :severity="rhythm.is_active ? 'success' : 'secondary'" />
          <Button
            :label="rhythm.is_active ? 'Выключить' : 'Включить'"
            :severity="rhythm.is_active ? 'secondary' : 'success'"
            size="small"
            outlined
            @click="toggleRhythm(rhythm.id)"
          />
        </div>
      </div>
    </div>
    <div v-else class="text-center text-surface-400 py-12">Ритмы не настроены</div>

    <Dialog v-model:visible="showDialog" :header="editing ? 'Редактировать ритм' : 'Новый ритм'" modal :style="{ width: '450px' }">
      <div class="space-y-3">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Название *</label>
          <InputText v-model="form.title" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Расписание (cron)</label>
          <InputText v-model="form.cron_expr" placeholder="0 9 * * 1 (каждый пн в 9:00)" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Описание задачи</label>
          <Textarea v-model="form.description" rows="3" class="w-full" />
        </div>
        <div class="flex gap-2 pt-2">
          <Button :label="editing ? 'Сохранить' : 'Создать'" :loading="loading" @click="submit" />
          <Button label="Отмена" text @click="showDialog = false" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRhythmStore } from '../stores/rhythms.js'
import { useToast } from 'primevue/usetoast'
import { friendlyError } from '../api/errors.js'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Tag from 'primevue/tag'

const rhythmStore = useRhythmStore()
const toast = useToast()
const showDialog = ref(false)
const editing = ref(null)
const loading = ref(false)
const form = ref({ title: '', cron_expr: '', description: '' })

function openCreate() {
  editing.value = null
  form.value = { title: '', cron_expr: '', description: '' }
  showDialog.value = true
}

function openEdit(r) {
  editing.value = r
  form.value = { title: r.title, cron_expr: r.cron_expr, description: r.description || '' }
  showDialog.value = true
}

async function submit() {
  loading.value = true
  try {
    if (editing.value) {
      await rhythmStore.updateRhythm(editing.value.id, form.value)
    } else {
      await rhythmStore.createRhythm(form.value)
    }
    showDialog.value = false
    toast.add({ severity: 'success', summary: 'Сохранено', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    loading.value = false
  }
}

async function deleteRhythm(id) {
  await rhythmStore.deleteRhythm(id)
}

async function toggleRhythm(id) {
  await rhythmStore.toggleRhythm(id)
}

async function runRhythm(id) {
  try {
    await rhythmStore.runRhythm(id)
    toast.add({ severity: 'info', summary: 'Ритм запущен', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  }
}

onMounted(() => rhythmStore.fetchRhythms())
</script>
