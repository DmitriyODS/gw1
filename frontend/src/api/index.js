import axios from 'axios'

const http = axios.create({
  baseURL: '/',
  timeout: 30000,
})

// Attach JWT
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Auth-failure callback (set from main.js after router is ready) ──────────
let _onSessionExpired = null
export function onSessionExpired(cb) { _onSessionExpired = cb }

// ── Refresh on 401 ──────────────────────────────────────────────────────────
let refreshing = false
let queue = []

function processQueue(error, token = null) {
  queue.forEach((p) => (error ? p.reject(error) : p.resolve(token)))
  queue = []
}

http.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config

    // Never intercept auth endpoints — would cause an infinite loop
    if (original.url?.includes('/api/auth/')) return Promise.reject(error)

    // Background requests (e.g. timer polling) opt out of the redirect cycle
    if (original._skipRefresh) return Promise.reject(error)

    if (error.response?.status === 401 && !original._retry) {
      if (refreshing) {
        return new Promise((resolve, reject) => {
          queue.push({ resolve, reject })
        }).then((token) => {
          original.headers.Authorization = `Bearer ${token}`
          return http(original)
        })
      }

      original._retry = true
      refreshing = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        if (!refreshToken) throw new Error('no refresh token')

        const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
        localStorage.setItem('access_token', data.access_token)
        // refresh_token rotates only if backend returns a new one
        if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)

        processQueue(null, data.access_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return http(original)
      } catch (err) {
        processQueue(err)
        // Clear tokens but do NOT do window.location.href — let the router guard
        // detect the missing token on the next navigation and redirect to /login
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        if (_onSessionExpired) _onSessionExpired()
        return Promise.reject(err)
      } finally {
        refreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export const api = {
  auth: {
    login: (data) => http.post('/api/auth/login', data),
    refresh: (data) => http.post('/api/auth/refresh', data),
    logout: () => http.post('/api/auth/logout'),
  },

  tasks: {
    list: (params) => http.get('/api/tasks/', { params }),
    get: (id) => http.get(`/api/tasks/${id}`),
    create: (data) => http.post('/api/tasks/', data),
    update: (id, data) => http.put(`/api/tasks/${id}`, data),
    delete: (id) => http.delete(`/api/tasks/${id}`),
    move: (id, data) => http.post(`/api/tasks/${id}/move`, data),
    timerStart: (id) => http.post(`/api/tasks/${id}/timer/start`),
    timerPause: (id) => http.post(`/api/tasks/${id}/timer/pause`),
    timerForceStart: (id) => http.post(`/api/tasks/${id}/timer/force-start`),
    done: (id) => http.post(`/api/tasks/${id}/done`),
    delegate: (id, data) => http.post(`/api/tasks/${id}/delegate`, data),
    unassign: (id) => http.post(`/api/tasks/${id}/unassign`),
    // _skipRefresh: polling request — a 401 here must not trigger a redirect cycle
    myTimer: () => http.get('/api/tasks/my-timer', { _skipRefresh: true }),
    uploadAttachment: (id, formData) =>
      http.post(`/api/tasks/${id}/attachments`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),
    deleteAttachment: (id, attId) => http.delete(`/api/tasks/${id}/attachments/${attId}`),
    downloadZip: (id) => http.get(`/api/tasks/${id}/attachments/zip`, { responseType: 'blob' }),
    addComment: (id, data) => http.post(`/api/tasks/${id}/comments`, data),
    deleteComment: (id, commentId) => http.delete(`/api/tasks/${id}/comments/${commentId}`),
    types: () => http.get('/api/task-types'),
  },

  users: {
    list: (params) => http.get('/api/users/', { params }),
    get: (id) => http.get(`/api/users/${id}`),
    create: (data) => http.post('/api/users/', data),
    update: (id, data) => http.put(`/api/users/${id}`, data),
    delete: (id) => http.delete(`/api/users/${id}`),
  },

  departments: {
    list: () => http.get('/api/departments/'),
    create: (data) => http.post('/api/departments/', data),
    update: (id, data) => http.put(`/api/departments/${id}`, data),
    delete: (id) => http.delete(`/api/departments/${id}`),
  },

  analytics: {
    dashboard: (params) => http.get('/api/analytics/', { params }),
    time: (params) => http.get('/api/analytics/time', { params }),
    tv: (params) => http.get('/api/analytics/tv', { params }),
    exportExcel: (params) =>
      http.get('/api/analytics/export/excel', { params, responseType: 'blob' }),
  },

  rhythms: {
    list: () => http.get('/api/rhythms/'),
    create: (data) => http.post('/api/rhythms/', data),
    update: (id, data) => http.put(`/api/rhythms/${id}`, data),
    delete: (id) => http.delete(`/api/rhythms/${id}`),
    toggle: (id) => http.post(`/api/rhythms/${id}/toggle`),
    run: (id) => http.post(`/api/rhythms/${id}/run`),
  },

  plans: {
    list: (params) => http.get('/api/plans/', { params }),
    create: (data) => http.post('/api/plans/', data),
    update: (id, data) => http.put(`/api/plans/${id}`, data),
    delete: (id) => http.delete(`/api/plans/${id}`),
    push: (id) => http.post(`/api/plans/${id}/push`),
    convertDue: (data) => http.post('/api/plans/convert-due', data),
    groups: {
      list: () => http.get('/api/plan-groups/'),
      create: (data) => http.post('/api/plan-groups/', data),
      delete: (id) => http.delete(`/api/plan-groups/${id}`),
    },
  },

  mediaPlan: {
    calendar: (params) => http.get('/api/media-plan/', { params }),
    exportExcel: (params) =>
      http.get('/api/media-plan/export', { params, responseType: 'blob' }),
  },

  profile: {
    get: () => http.get('/api/profile'),
    update: (data) => http.put('/api/profile', data),
    uploadAvatar: (formData) =>
      http.post('/api/profile/avatar', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),
    resetAvatar: () =>
      http.post('/api/profile/avatar', new URLSearchParams({ reset: 'true' }), {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      }),
  },

  admin: {
    archiveStats: () => http.get('/api/admin/archive'),
    archivePreview: () => http.get('/api/admin/archive/preview'),
    migrateReview: () => http.post('/api/admin/archive/migrate-review'),
    archiveOld: () => http.post('/api/admin/archive/run'),
    export: () => http.post('/api/admin/archive/export', {}, { responseType: 'blob' }),
    import: (formData) =>
      http.post('/api/admin/archive/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),
  },

  public: {
    submit: (data) => http.post('/public/submit', data),
    departments: () => http.get('/public/departments'),
    taskTypes: () => http.get('/public/task-types'),
  },
}

export default http
