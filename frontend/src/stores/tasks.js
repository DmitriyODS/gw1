import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/index.js'

export const useTaskStore = defineStore('tasks', () => {
  const tasks = ref([])
  const currentTask = ref(null)
  const loading = ref(false)

  async function fetchTasks(params) {
    loading.value = true
    try {
      const { data } = await api.tasks.list(params)
      tasks.value = data.data || []
    } finally {
      loading.value = false
    }
  }

  async function fetchTask(id) {
    const { data } = await api.tasks.get(id)
    currentTask.value = data
    return data
  }

  async function createTask(payload) {
    const { data } = await api.tasks.create(payload)
    return data
  }

  async function updateTask(id, payload) {
    const { data } = await api.tasks.update(id, payload)
    if (currentTask.value?.id === id) currentTask.value = data
    const idx = tasks.value.findIndex((t) => t.id === id)
    if (idx !== -1) tasks.value[idx] = data
    return data
  }

  async function deleteTask(id) {
    await api.tasks.delete(id)
    tasks.value = tasks.value.filter((t) => t.id !== id)
  }

  async function moveTask(id, status) {
    const { data } = await api.tasks.move(id, { status })
    const idx = tasks.value.findIndex((t) => t.id === id)
    if (idx !== -1) tasks.value[idx] = { ...tasks.value[idx], ...data }
    return data
  }

  return {
    tasks,
    currentTask,
    loading,
    fetchTasks,
    fetchTask,
    createTask,
    updateTask,
    deleteTask,
    moveTask,
  }
})
