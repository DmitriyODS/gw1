<template>
  <div class="flex h-screen overflow-hidden bg-surface-50 dark:bg-surface-900">
    <!-- Sidebar -->
    <aside class="w-56 flex-shrink-0 bg-surface-0 dark:bg-surface-800 border-r border-surface-200 dark:border-surface-700 flex flex-col">
      <div class="p-4 text-xl font-bold text-primary-600 dark:text-primary-400 border-b border-surface-200 dark:border-surface-700">
        Groove Work v.1
      </div>
      <nav class="flex-1 p-2 space-y-1 overflow-y-auto">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-surface-700 dark:text-surface-300 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
          active-class="bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 font-medium"
        >
          <span class="material-symbols-outlined" style="font-size:18px">{{ item.icon }}</span>
          {{ item.label }}
        </router-link>
      </nav>
      <div class="p-3 border-t border-surface-200 dark:border-surface-700">
        <router-link to="/profile" class="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <UserAvatar :user="authStore.user" size="sm" />
          <span class="text-sm text-surface-700 dark:text-surface-300 truncate">
            {{ authStore.user?.full_name || authStore.user?.username || 'Профиль' }}
          </span>
        </router-link>
      </div>
    </aside>

    <!-- Main area -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- Topbar -->
      <header class="h-14 flex-shrink-0 bg-surface-0 dark:bg-surface-800 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between px-4">
        <h1 class="text-base font-semibold text-surface-800 dark:text-surface-200">
          {{ currentTitle }}
        </h1>
        <div class="flex items-center gap-3">
          <TimerBadge />
          <button
            class="flex items-center justify-center w-8 h-8 rounded-lg text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            :title="isDark ? 'Светлая тема' : 'Тёмная тема'"
            @click="toggleTheme"
          >
            <span class="material-symbols-outlined" style="font-size:20px">{{ isDark ? 'light_mode' : 'dark_mode' }}</span>
          </button>
          <button
            class="flex items-center justify-center w-8 h-8 rounded-lg text-surface-500 hover:bg-surface-100 dark:hover:bg-surface-700 transition-colors"
            title="Выйти"
            @click="handleLogout"
          >
            <span class="material-symbols-outlined" style="font-size:20px">logout</span>
          </button>
        </div>
      </header>

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto p-4">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useTimerStore } from '../stores/timer.js'
import UserAvatar from '../components/UserAvatar.vue'
import TimerBadge from '../components/TimerBadge.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const timerStore = useTimerStore()

// ── Theme toggle ───────────────────────────────────────────────────────────
const isDark = ref(localStorage.getItem('theme') === 'dark')

function applyTheme(dark) {
  document.documentElement.classList.toggle('dark', dark)
  localStorage.setItem('theme', dark ? 'dark' : 'light')
}

function toggleTheme() {
  isDark.value = !isDark.value
  applyTheme(isDark.value)
}

// Start polling only after mount (not during SSR/setup phase)
onMounted(() => {
  applyTheme(isDark.value)
  timerStore.startPolling()
})
onUnmounted(() => timerStore.stopPolling())

const titleMap = {
  '/': 'Задачи',
  '/plans': 'Планы',
  '/media-plan': 'Медиаплан',
  '/rhythms': 'Ритмы',
  '/analytics': 'Аналитика',
  '/analytics/time': 'Время',
  '/analytics/tv': 'TV',
  '/profile': 'Профиль',
  '/admin/users': 'Пользователи',
  '/admin/departments': 'Отделы',
  '/admin/archive': 'Архив',
}

const currentTitle = computed(() => titleMap[route.path] || 'GW1')

const navItems = computed(() => {
  const items = [
    { to: '/',               label: 'Задачи',    icon: 'task' },
    { to: '/analytics',      label: 'Аналитика', icon: 'bar_chart' },
    { to: '/analytics/time', label: 'Время',     icon: 'schedule' },
    { to: '/media-plan',     label: 'Медиаплан', icon: 'calendar_month' },
  ]
  if (authStore.isManager) {
    items.push(
      { to: '/plans',   label: 'Планы', icon: 'folder_open' },
      { to: '/rhythms', label: 'Ритмы', icon: 'autorenew' }
    )
  }
  if (authStore.isAdmin) {
    items.push(
      { to: '/admin/users',       label: 'Пользователи', icon: 'group' },
      { to: '/admin/departments', label: 'Отделы',       icon: 'corporate_fare' },
      { to: '/admin/archive',     label: 'Архив',        icon: 'archive' }
    )
  }
  return items
})

async function handleLogout() {
  timerStore.stopPolling()
  await authStore.logout()
  router.push('/login')
}
</script>
