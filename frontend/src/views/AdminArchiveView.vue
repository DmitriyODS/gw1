<template>
  <div class="space-y-4 max-w-2xl">
    <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Архив</h1>

    <!-- Stats -->
    <div v-if="stats" class="grid grid-cols-2 md:grid-cols-3 gap-3">
      <div v-for="(val, key) in stats" :key="key" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
        <div class="text-2xl font-bold text-primary-600">{{ val }}</div>
        <div class="text-xs text-surface-500 mt-1">{{ key }}</div>
      </div>
    </div>

    <!-- Actions -->
    <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 space-y-3">
      <h3 class="font-semibold text-sm">Действия</h3>
      <div class="flex flex-wrap gap-2">
        <Button
          label="Перенести на проверку"
          outlined
          size="small"
          :loading="actionLoading === 'review'"
          @click="migrateReview"
        />
        <Button
          label="Архивировать старые"
          outlined
          size="small"
          severity="warn"
          :loading="actionLoading === 'archive'"
          @click="archiveOld"
        />
        <Button
          label="Экспорт"
          outlined
          size="small"
          icon="pi pi-download"
          :loading="actionLoading === 'export'"
          @click="exportArchive"
        />
        <Button
          v-if="authStore.isSuperAdmin"
          label="Импорт"
          outlined
          size="small"
          icon="pi pi-upload"
          severity="danger"
          @click="triggerImport"
        />
      </div>
      <input ref="importInput" type="file" accept=".json" class="hidden" @change="importArchive" />
    </div>

    <!-- Preview -->
    <div v-if="preview?.length" class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700">
      <h3 class="font-semibold text-sm mb-3">Предпросмотр архивируемых задач ({{ preview.length }})</h3>
      <div class="space-y-1 max-h-60 overflow-y-auto">
        <div v-for="t in preview" :key="t.id" class="flex items-center justify-between text-sm py-1 border-b border-surface-100 dark:border-surface-700">
          <span>{{ t.title }}</span>
          <span class="text-surface-400 text-xs">{{ t.status }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { api } from '../api/index.js'
import { friendlyError } from '../api/errors.js'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'

const authStore = useAuthStore()
const toast = useToast()

const stats = ref(null)
const preview = ref([])
const actionLoading = ref('')
const importInput = ref(null)

async function load() {
  const { data } = await api.admin.archiveStats()
  stats.value = data
  const prev = await api.admin.archivePreview()
  preview.value = prev.data || []
}

async function migrateReview() {
  actionLoading.value = 'review'
  try {
    await api.admin.migrateReview()
    toast.add({ severity: 'success', summary: 'Перенесено на проверку', life: 2000 })
    load()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    actionLoading.value = ''
  }
}

async function archiveOld() {
  actionLoading.value = 'archive'
  try {
    await api.admin.archiveOld()
    toast.add({ severity: 'success', summary: 'Архивирование выполнено', life: 2000 })
    load()
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    actionLoading.value = ''
  }
}

async function exportArchive() {
  actionLoading.value = 'export'
  try {
    const response = await api.admin.export()
    const url = URL.createObjectURL(new Blob([response.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = 'archive_export.json'
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка экспорта', life: 3000 })
  } finally {
    actionLoading.value = ''
  }
}

function triggerImport() {
  importInput.value?.click()
}

async function importArchive(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    await api.admin.import(formData)
    toast.add({ severity: 'success', summary: 'Импорт выполнен', life: 2000 })
    load()
  } catch (err) {
    toast.add({ severity: 'error', summary: 'Ошибка импорта', life: 3000 })
  }
  e.target.value = ''
}

onMounted(load)
</script>
