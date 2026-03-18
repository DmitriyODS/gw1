import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/index.js'

export const useRhythmStore = defineStore('rhythms', () => {
  const rhythms = ref([])

  async function fetchRhythms() {
    const { data } = await api.rhythms.list()
    rhythms.value = data.data || []
  }

  async function createRhythm(payload) {
    const { data } = await api.rhythms.create(payload)
    rhythms.value.push(data)
    return data
  }

  async function updateRhythm(id, payload) {
    const { data } = await api.rhythms.update(id, payload)
    const idx = rhythms.value.findIndex((r) => r.id === id)
    if (idx !== -1) rhythms.value[idx] = data
    return data
  }

  async function deleteRhythm(id) {
    await api.rhythms.delete(id)
    rhythms.value = rhythms.value.filter((r) => r.id !== id)
  }

  async function toggleRhythm(id) {
    const { data } = await api.rhythms.toggle(id)
    const idx = rhythms.value.findIndex((r) => r.id === id)
    if (idx !== -1) rhythms.value[idx] = data
    return data
  }

  async function runRhythm(id) {
    return api.rhythms.run(id)
  }

  return { rhythms, fetchRhythms, createRhythm, updateRhythm, deleteRhythm, toggleRhythm, runRhythm }
})
