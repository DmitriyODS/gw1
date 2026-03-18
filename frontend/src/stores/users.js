import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/index.js'

export const useUserStore = defineStore('users', () => {
  const users = ref([])
  const loading = ref(false)

  async function fetchUsers(params) {
    loading.value = true
    try {
      const { data } = await api.users.list(params)
      users.value = data.data || []
    } finally {
      loading.value = false
    }
  }

  async function createUser(payload) {
    const { data } = await api.users.create(payload)
    users.value.push(data)
    return data
  }

  async function updateUser(id, payload) {
    const { data } = await api.users.update(id, payload)
    const idx = users.value.findIndex((u) => u.id === id)
    if (idx !== -1) users.value[idx] = data
    return data
  }

  async function deleteUser(id) {
    await api.users.delete(id)
    users.value = users.value.filter((u) => u.id !== id)
  }

  return { users, loading, fetchUsers, createUser, updateUser, deleteUser }
})
