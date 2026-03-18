import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/index.js'

export const useDepartmentStore = defineStore('departments', () => {
  const departments = ref([])

  async function fetchDepartments() {
    const { data } = await api.departments.list()
    departments.value = data.data || []
  }

  async function createDepartment(payload) {
    const { data } = await api.departments.create(payload)
    departments.value.push(data)
    return data
  }

  async function updateDepartment(id, payload) {
    const { data } = await api.departments.update(id, payload)
    const idx = departments.value.findIndex((d) => d.id === id)
    if (idx !== -1) departments.value[idx] = data
    return data
  }

  async function deleteDepartment(id) {
    await api.departments.delete(id)
    departments.value = departments.value.filter((d) => d.id !== id)
  }

  return { departments, fetchDepartments, createDepartment, updateDepartment, deleteDepartment }
})
