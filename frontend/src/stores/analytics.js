import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/index.js'

export const useAnalyticsStore = defineStore('analytics', () => {
  const dashboard = ref(null)
  const timeReport = ref(null)
  const tvData = ref(null)
  const loading = ref(false)

  async function fetchDashboard(params) {
    loading.value = true
    try {
      const { data } = await api.analytics.dashboard(params)
      dashboard.value = data
    } finally {
      loading.value = false
    }
  }

  async function fetchTime(params) {
    loading.value = true
    try {
      const { data } = await api.analytics.time(params)
      timeReport.value = data
    } finally {
      loading.value = false
    }
  }

  async function fetchTV(params) {
    const { data } = await api.analytics.tv(params)
    tvData.value = data
    return data
  }

  async function exportExcel(params) {
    const response = await api.analytics.exportExcel(params)
    const url = URL.createObjectURL(new Blob([response.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = 'analytics.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  }

  return { dashboard, timeReport, tvData, loading, fetchDashboard, fetchTime, fetchTV, exportExcel }
})
