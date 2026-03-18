import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/index.js'

export const useTimerStore = defineStore('timer', () => {
  const activeTimer = ref(null)
  const elapsedSeconds = ref(0)

  let pollInterval = null
  let tickInterval = null

  function startTick() {
    if (tickInterval) return
    tickInterval = setInterval(() => {
      if (activeTimer.value) elapsedSeconds.value++
    }, 1000)
  }

  function stopTick() {
    clearInterval(tickInterval)
    tickInterval = null
  }

  async function fetchTimer() {
    try {
      const { data } = await api.tasks.myTimer()
      if (data && data.active) {
        activeTimer.value = { ...data.active, task: data.task }
        elapsedSeconds.value = data.elapsed_sec || 0
        startTick()
      } else {
        activeTimer.value = null
        elapsedSeconds.value = 0
        stopTick()
      }
    } catch {
      activeTimer.value = null
    }
  }

  function startPolling() {
    fetchTimer()
    pollInterval = setInterval(fetchTimer, 20_000)
  }

  function stopPolling() {
    clearInterval(pollInterval)
    pollInterval = null
    stopTick()
  }

  function clear() {
    activeTimer.value = null
    elapsedSeconds.value = 0
    stopTick()
  }

  return { activeTimer, elapsedSeconds, fetchTimer, startPolling, stopPolling, clear }
})
