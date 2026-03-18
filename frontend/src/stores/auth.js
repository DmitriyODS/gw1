import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '../api/index.js'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token'))

  const isLoggedIn = computed(() => !!accessToken.value)
  const isAdmin = computed(() => ['admin', 'super_admin'].includes(user.value?.role))
  const isSuperAdmin = computed(() => user.value?.role === 'super_admin')
  const isManager = computed(() =>
    ['manager', 'admin', 'super_admin'].includes(user.value?.role)
  )

  async function login(credentials) {
    const { data } = await api.auth.login(credentials)
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    accessToken.value = data.access_token
    user.value = data.user
  }

  async function logout() {
    try { await api.auth.logout() } catch {}
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    accessToken.value = null
    user.value = null
  }

  async function fetchMe() {
    const { data } = await api.profile.get()
    user.value = data.user
  }

  return { user, accessToken, isLoggedIn, isAdmin, isSuperAdmin, isManager, login, logout, fetchMe }
})
