import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/login',          component: () => import('../views/LoginView.vue'),                  meta: { layout: 'blank', public: true } },
  { path: '/public/submit',  component: () => import('../views/PublicSubmitView.vue'),           meta: { layout: 'blank', public: true } },

  { path: '/',               component: () => import('../views/TasksView.vue'),                  meta: { layout: 'app' } },
  { path: '/tasks/create',   component: () => import('../views/TaskFormView.vue'),               meta: { layout: 'app', role: 'manager' } },
  { path: '/tasks/:id',      component: () => import('../views/TaskDetailView.vue'),             meta: { layout: 'app' } },
  { path: '/tasks/:id/edit', component: () => import('../views/TaskFormView.vue'),               meta: { layout: 'app', role: 'manager' } },

  { path: '/plans',          component: () => import('../views/PlansView.vue'),                  meta: { layout: 'app', role: 'manager' } },
  { path: '/media-plan',     component: () => import('../views/MediaPlanView.vue'),              meta: { layout: 'app' } },
  { path: '/rhythms',        component: () => import('../views/RhythmsView.vue'),                meta: { layout: 'app', role: 'manager' } },

  { path: '/analytics',      component: () => import('../views/AnalyticsDashboardView.vue'),    meta: { layout: 'app' } },
  { path: '/analytics/time', component: () => import('../views/AnalyticsTimeView.vue'),         meta: { layout: 'app' } },
  { path: '/analytics/tv',   component: () => import('../views/AnalyticsTVView.vue'),           meta: { layout: 'blank' } },

  { path: '/profile',        component: () => import('../views/ProfileView.vue'),               meta: { layout: 'app' } },

  { path: '/admin/users',       component: () => import('../views/AdminUsersView.vue'),         meta: { layout: 'app', role: 'admin' } },
  { path: '/admin/departments', component: () => import('../views/AdminDepartmentsView.vue'),   meta: { layout: 'app', role: 'admin' } },
  { path: '/admin/archive',     component: () => import('../views/AdminArchiveView.vue'),       meta: { layout: 'app', role: 'admin' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // ── Already logged in → don't show login page again ───────────────────────
  if (to.path === '/login' && auth.isLoggedIn) {
    // Ensure user is loaded before redirecting
    if (!auth.user) {
      try { await auth.fetchMe() } catch { /* token invalid — show login */ return true }
    }
    return '/'
  }

  // ── Public routes (login, public submit) ───────────────────────────────────
  if (to.meta.public) return true

  // ── Not logged in → go to login ────────────────────────────────────────────
  if (!auth.isLoggedIn) return '/login'

  // ── Load user profile if missing (e.g. after page refresh) ────────────────
  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      // fetchMe failed — token is invalid/expired and refresh already failed
      // (interceptor already cleared the tokens via onSessionExpired)
      return '/login'
    }
  }

  // ── Role-based access ──────────────────────────────────────────────────────
  const role = to.meta.role
  if (role === 'manager' && !auth.isManager) return '/'
  if (role === 'admin'   && !auth.isAdmin)   return '/'

  return true
})

export default router
