<template>
  <div class="max-w-2xl mx-auto space-y-4">
    <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">Профиль</h1>

    <!-- Stats cards -->
    <div v-if="stats" class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
        <div class="text-2xl font-bold text-primary-600">{{ stats.created_tasks }}</div>
        <div class="text-xs text-surface-500 mt-1">Создано задач</div>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
        <div class="text-2xl font-bold text-green-600">{{ stats.completed_tasks }}</div>
        <div class="text-xs text-surface-500 mt-1">Завершено</div>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
        <div class="text-2xl font-bold text-blue-600">{{ formatTime(stats.week_seconds) }}</div>
        <div class="text-xs text-surface-500 mt-1">За неделю</div>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-xl p-4 border border-surface-200 dark:border-surface-700 text-center">
        <div class="text-2xl font-bold text-violet-600">{{ formatTime(stats.month_seconds) }}</div>
        <div class="text-xs text-surface-500 mt-1">За месяц</div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- Profile edit -->
      <div class="bg-surface-0 dark:bg-surface-800 rounded-2xl p-6 border border-surface-200 dark:border-surface-700 space-y-4">
        <div class="flex items-center gap-4">
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
            <label class="text-sm font-medium">Текущий пароль</label>
            <Password v-model="form.old_password" :feedback="false" toggleMask class="w-full" inputClass="w-full" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Новый пароль</label>
            <Password v-model="form.new_password" :feedback="false" toggleMask class="w-full" inputClass="w-full" />
          </div>
          <Button label="Сохранить" :loading="loading" @click="save" />
        </div>
      </div>

      <!-- Avatar -->
      <div class="bg-surface-0 dark:bg-surface-800 rounded-2xl p-6 border border-surface-200 dark:border-surface-700 space-y-4">
        <h3 class="text-sm font-semibold">Аватар</h3>
        <div class="flex justify-center">
          <UserAvatar :user="authStore.user" size="lg" />
        </div>
        <FileUpload
          mode="basic"
          auto
          chooseLabel="Загрузить фото"
          accept="image/*"
          :maxFileSize="2000000"
          @uploader="uploadAvatar"
        />
        <Button
          v-if="authStore.user?.avatar_path"
          label="Сбросить аватар"
          icon="pi pi-times"
          severity="secondary"
          outlined
          size="small"
          class="w-full"
          @click="resetAvatar"
        />
      </div>
    </div>

    <!-- Recent tasks -->
    <div v-if="stats?.recent_tasks?.length" class="bg-surface-0 dark:bg-surface-800 rounded-2xl p-5 border border-surface-200 dark:border-surface-700">
      <h3 class="text-sm font-semibold mb-3">Последние задачи</h3>
      <div class="space-y-2">
        <div
          v-for="task in stats.recent_tasks"
          :key="task.id"
          class="flex items-center gap-3 text-sm py-2 border-b border-surface-100 dark:border-surface-700 last:border-0"
        >
          <div class="w-2 h-2 rounded-full flex-shrink-0" :class="statusDot(task.status)" />
          <router-link
            :to="`/tasks/${task.id}`"
            class="flex-1 truncate hover:text-primary-600 font-medium"
          >{{ task.title }}</router-link>
          <span class="text-xs text-surface-400 flex-shrink-0">
            {{ new Date(task.last_work).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) }}
          </span>
        </div>
      </div>
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
const stats = ref(null)

const form = ref({ full_name: '', old_password: '', new_password: '' })

const roleMap = {
  staff: 'Сотрудник',
  tv: 'TV',
  manager: 'Менеджер',
  admin: 'Администратор',
  super_admin: 'Суперадмин',
}
const roleLabel = computed(() => roleMap[authStore.user?.role] || authStore.user?.role)

async function loadStats() {
  try {
    const { data } = await api.profile.get()
    stats.value = data
  } catch {}
}

async function save() {
  loading.value = true
  try {
    const payload = { full_name: form.value.full_name }
    if (form.value.new_password) {
      payload.old_password = form.value.old_password
      payload.new_password = form.value.new_password
    }
    await api.profile.update(payload)
    await authStore.fetchMe()
    form.value.old_password = ''
    form.value.new_password = ''
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

async function resetAvatar() {
  try {
    await api.profile.resetAvatar()
    await authStore.fetchMe()
    toast.add({ severity: 'success', summary: 'Аватар сброшен', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  }
}

function formatTime(s) {
  if (!s) return '0ч 0м'
  return `${Math.floor(s / 3600)}ч ${Math.floor((s % 3600) / 60)}м`
}

function statusDot(status) {
  return {
    new:         'bg-surface-400',
    in_progress: 'bg-green-500',
    paused:      'bg-yellow-500',
    done:        'bg-blue-500',
  }[status] || 'bg-surface-300'
}

onMounted(async () => {
  form.value.full_name = authStore.user?.full_name || ''
  await loadStats()
})
</script>
