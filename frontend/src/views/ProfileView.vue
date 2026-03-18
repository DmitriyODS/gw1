<template>
  <div class="max-w-lg mx-auto space-y-4">
    <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Профиль</h1>

    <div class="bg-surface-0 dark:bg-surface-800 rounded-2xl p-6 border border-surface-200 dark:border-surface-700">
      <div class="flex items-center gap-4 mb-6">
        <UserAvatar :user="authStore.user" size="lg" />
        <div>
          <p class="font-semibold text-surface-800 dark:text-surface-200">{{ authStore.user?.full_name }}</p>
          <p class="text-sm text-surface-500">@{{ authStore.user?.username }}</p>
          <p class="text-xs text-surface-400 mt-0.5">{{ roleLabel }}</p>
        </div>
      </div>

      <div class="space-y-3">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Имя</label>
          <InputText v-model="form.full_name" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Новый пароль</label>
          <Password v-model="form.password" :feedback="false" toggleMask class="w-full" inputClass="w-full" />
        </div>
        <Button label="Сохранить" :loading="loading" @click="save" />
      </div>
    </div>

    <div class="bg-surface-0 dark:bg-surface-800 rounded-2xl p-6 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold mb-3">Аватар</h3>
      <FileUpload
        mode="basic"
        auto
        chooseLabel="Загрузить фото"
        accept="image/*"
        :maxFileSize="2000000"
        @uploader="uploadAvatar"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import { api } from '../api/index.js'
import { friendlyError } from '../api/errors.js'
import { useToast } from 'primevue/usetoast'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import FileUpload from 'primevue/fileupload'
import UserAvatar from '../components/UserAvatar.vue'

const authStore = useAuthStore()
const toast = useToast()
const loading = ref(false)

const form = ref({ full_name: '', password: '' })

const roleMap = { staff: 'Сотрудник', tv: 'TV', manager: 'Менеджер', admin: 'Администратор', super_admin: 'Суперадмин' }
const roleLabel = computed(() => roleMap[authStore.user?.role] || authStore.user?.role)

async function save() {
  loading.value = true
  try {
    const payload = { full_name: form.value.full_name }
    if (form.value.password) payload.password = form.value.password
    await api.profile.update(payload)
    await authStore.fetchMe()
    form.value.password = ''
    toast.add({ severity: 'success', summary: 'Сохранено', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    loading.value = false
  }
}

async function uploadAvatar(event) {
  const formData = new FormData()
  formData.append('avatar', event.files[0])
  try {
    await api.profile.uploadAvatar(formData)
    await authStore.fetchMe()
    toast.add({ severity: 'success', summary: 'Аватар обновлён', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка загрузки', life: 3000 })
  }
}

onMounted(() => {
  form.value.full_name = authStore.user?.full_name || ''
})
</script>
