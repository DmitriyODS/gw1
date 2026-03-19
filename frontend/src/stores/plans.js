import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/index.js'

export const usePlanStore = defineStore('plans', () => {
  const plans = ref([])
  const groups = ref([])
  const autoConverted = ref(0)

  async function fetchPlans(params) {
    const { data } = await api.plans.list(params)
    plans.value = data.data || []
    if (data.groups) groups.value = data.groups
    autoConverted.value = data.auto_converted || 0
  }

  async function createPlan(payload) {
    const { data } = await api.plans.create(payload)
    plans.value.push(data)
    return data
  }

  async function updatePlan(id, payload) {
    const { data } = await api.plans.update(id, payload)
    const idx = plans.value.findIndex((p) => p.id === id)
    if (idx !== -1) plans.value[idx] = data
    return data
  }

  async function deletePlan(id) {
    await api.plans.delete(id)
    plans.value = plans.value.filter((p) => p.id !== id)
  }

  async function pushPlan(id) {
    return api.plans.push(id)
  }

  async function fetchGroups() {
    const { data } = await api.plans.groups.list()
    groups.value = data.data || []
  }

  async function createGroup(payload) {
    const { data } = await api.plans.groups.create(payload)
    groups.value.push(data)
    return data
  }

  async function deleteGroup(id) {
    await api.plans.groups.delete(id)
    groups.value = groups.value.filter((g) => g.id !== id)
  }

  return {
    plans, groups, autoConverted,
    fetchPlans, createPlan, updatePlan, deletePlan, pushPlan,
    fetchGroups, createGroup, deleteGroup,
  }
})
