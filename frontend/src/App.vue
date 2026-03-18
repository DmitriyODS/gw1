<template>
  <component :is="layoutComponent">
    <router-view />
  </component>
  <Toast />
  <ConfirmDialog />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import AppLayout from './layouts/AppLayout.vue'
import BlankLayout from './layouts/BlankLayout.vue'

const route = useRoute()
const layoutComponent = computed(() =>
  route.meta.layout === 'blank' ? BlankLayout : AppLayout
)
</script>
