<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Пользователи</h1>
      <Button label="Добавить" icon="pi pi-plus" size="small" @click="openCreate" />
    </div>

    <DataTable :value="userStore.users" :loading="userStore.loading" stripedRows class="text-sm">
      <Column header="Пользователь" style="min-width: 200px">
        <template #body="{ data }">
          <div class="flex items-center gap-2">
            <UserAvatar :user="data" size="sm" />
            <div>
              <p class="font-medium">{{ data.full_name }}</p>
              <p class="text-xs text-surface-400">@{{ data.username }}</p>
            </div>
          </div>
        </template>
      </Column>
      <Column field="role" header="Роль">
        <template #body="{ data }">
          <Tag :value="roleLabel(data.role)" :severity="roleSeverity(data.role)" />
        </template>
      </Column>
      <Column header="Отдел">
        <template #body="{ data }">{{ data.department?.name || '—' }}</template>
      </Column>
      <Column header="" style="width: 120px">
        <template #body="{ data }">
          <div class="flex gap-1">
            <Button icon="pi pi-pencil" text size="small" @click="openEdit(data)" />
            <Button
              v-if="authStore.isSuperAdmin"
              icon="pi pi-trash"
              text
              size="small"
              severity="danger"
              @click="deleteUser(data.id)"
            />
          </div>
        </template>
      </Column>
    </DataTable>

    <Dialog v-model:visible="showDialog" :header="editing ? 'Редактировать пользователя' : 'Новый пользователь'" modal :style="{ width: '450px' }">
      <div class="space-y-3">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Имя *</label>
          <InputText v-model="form.full_name" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Логин *</label>
          <InputText v-model="form.username" class="w-full" :disabled="!!editing" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">{{ editing ? 'Новый пароль' : 'Пароль *' }}</label>
          <Password v-model="form.password" :feedback="false" toggleMask class="w-full" inputClass="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Роль</label>
          <Select v-model="form.role" :options="roleOptions" optionLabel="label" optionValue="value" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Отдел</label>
          <Select v-model="form.department_id" :options="[{ name: 'Без отдела', id: null }, ...deptStore.departments]" optionLabel="name" optionValue="id" class="w-full" />
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
import { useUserStore } from '../stores/users.js'
import { useDepartmentStore } from '../stores/departments.js'
import { useAuthStore } from '../stores/auth.js'
import { useToast } from 'primevue/usetoast'
import { friendlyError } from '../api/errors.js'
import { useConfirm } from 'primevue/useconfirm'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Select from 'primevue/select'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import UserAvatar from '../components/UserAvatar.vue'

const userStore = useUserStore()
const deptStore = useDepartmentStore()
const authStore = useAuthStore()
const toast = useToast()
const confirm = useConfirm()

const showDialog = ref(false)
const editing = ref(null)
const loading = ref(false)
const form = ref({ name: '', username: '', password: '', role: 'user', department_id: null })

const roleOptions = [
  { label: 'Сотрудник', value: 'staff' },
  { label: 'TV', value: 'tv' },
  { label: 'Менеджер', value: 'manager' },
  { label: 'Администратор', value: 'admin' },
  { label: 'Суперадмин', value: 'super_admin' },
]

const roleLabel = (r) => roleOptions.find((o) => o.value === r)?.label || r
const roleSeverity = (r) => ({ staff: 'secondary', tv: 'secondary', manager: 'info', admin: 'warn', super_admin: 'danger' }[r] || 'secondary')

function openCreate() {
  editing.value = null
  form.value = { full_name: '', username: '', password: '', role: 'staff', department_id: null }
  showDialog.value = true
}

function openEdit(u) {
  editing.value = u
  form.value = { full_name: u.full_name, username: u.username, password: '', role: u.role, department_id: u.department_id || null }
  showDialog.value = true
}

async function submit() {
  loading.value = true
  try {
    const payload = { ...form.value }
    if (editing.value) {
      if (!payload.password) delete payload.password
      await userStore.updateUser(editing.value.id, payload)
    } else {
      await userStore.createUser(payload)
    }
    showDialog.value = false
    toast.add({ severity: 'success', summary: 'Сохранено', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    loading.value = false
  }
}

function deleteUser(id) {
  confirm.require({
    message: 'Удалить пользователя?',
    header: 'Подтверждение',
    accept: () => userStore.deleteUser(id),
  })
}

onMounted(() => {
  userStore.fetchUsers()
  deptStore.fetchDepartments()
})
</script>
