import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import router from './router/index.js'
import { onSessionExpired } from './api/index.js'
import App from './App.vue'
import './assets/main.css'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: { darkModeSelector: '.dark' },
  },
})
app.use(ToastService)
app.use(ConfirmationService)

// When any protected API call fails to refresh, clear state and go to login
// This runs after pinia is set up so stores are available
onSessionExpired(() => {
  // Lazy import to avoid circular deps
  import('./stores/auth.js').then(({ useAuthStore }) => {
    useAuthStore().logout()
  })
  router.push('/login')
})

app.mount('#app')
