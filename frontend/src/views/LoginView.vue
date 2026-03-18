<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-primary-600">GW1</h1>
        <p class="text-surface-500 mt-1">Система управления задачами</p>
      </div>
      <div class="bg-surface-0 dark:bg-surface-800 rounded-2xl shadow-lg p-6">
        <form @submit.prevent="handleLogin" class="space-y-4">
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium text-surface-700 dark:text-surface-300">Логин</label>
            <InputText v-model="form.username" placeholder="username" class="w-full" autofocus />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium text-surface-700 dark:text-surface-300">Пароль</label>
            <Password v-model="form.password" :feedback="false" toggleMask class="w-full" inputClass="w-full" />
          </div>
          <Button
            type="submit"
            label="Войти"
            class="w-full"
            :loading="loading"
          />
          <p v-if="error" class="text-sm text-red-500 text-center">{{ error }}</p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { friendlyError } from '../api/errors.js'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(form.value)
    router.push('/')
  } catch (e) {
    error.value = friendlyError(e, 'Неверный логин или пароль')
  } finally {
    loading.value = false
  }
}
</script>
