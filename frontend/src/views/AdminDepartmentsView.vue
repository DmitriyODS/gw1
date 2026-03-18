<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Отделы</h1>
      <Button label="Добавить" icon="pi pi-plus" size="small" @click="openCreate" />
    </div>

    <DataTable :value="deptStore.departments" stripedRows class="text-sm">
      <Column field="name" header="Название" />
      <Column field="description" header="Описание">
        <template #body="{ data }">{{ data.description || '—' }}</template>
      </Column>
      <Column header="" style="width: 100px">
        <template #body="{ data }">
          <div class="flex gap-1">
            <Button icon="pi pi-pencil" text size="small" @click="openEdit(data)" />
            <Button icon="pi pi-trash" text size="small" severity="danger" @click="deleteDept(data.id)" />
          </div>
        </template>
      </Column>
    </DataTable>

    <Dialog v-model:visible="showDialog" :header="editing ? 'Редактировать отдел' : 'Новый отдел'" modal :style="{ width: '400px' }">
      <div class="space-y-3">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Название *</label>
          <InputText v-model="form.name" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Описание</label>
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
import { useDepartmentStore } from '../stores/departments.js'
import { useToast } from 'primevue/usetoast'
import { friendlyError } from '../api/errors.js'
import { useConfirm } from 'primevue/useconfirm'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

const deptStore = useDepartmentStore()
const toast = useToast()
const confirm = useConfirm()

const showDialog = ref(false)
const editing = ref(null)
const loading = ref(false)
const form = ref({ name: '', description: '' })

function openCreate() {
  editing.value = null
  form.value = { name: '', description: '' }
  showDialog.value = true
}

function openEdit(d) {
  editing.value = d
  form.value = { name: d.name, description: d.description || '' }
  showDialog.value = true
}

async function submit() {
  loading.value = true
  try {
    if (editing.value) {
      await deptStore.updateDepartment(editing.value.id, form.value)
    } else {
      await deptStore.createDepartment(form.value)
    }
    showDialog.value = false
    toast.add({ severity: 'success', summary: 'Сохранено', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    loading.value = false
  }
}

function deleteDept(id) {
  confirm.require({
    message: 'Удалить отдел?',
    header: 'Подтверждение',
    accept: () => deptStore.deleteDepartment(id),
  })
}

onMounted(() => deptStore.fetchDepartments())
</script>
