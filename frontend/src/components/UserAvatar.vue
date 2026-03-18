<template>
  <img
    v-if="hasAvatar"
    :src="`/avatars/${user.id}`"
    :alt="user?.full_name"
    :class="sizeClass"
    class="rounded-full object-cover bg-surface-200"
    @error="hasAvatar = false"
  />
  <div
    v-else
    :class="[sizeClass, bgColor]"
    class="rounded-full flex items-center justify-center text-white font-semibold select-none"
  >
    {{ initials }}
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  user: { type: Object, default: null },
  size: { type: String, default: 'md' }, // sm | md | lg
})

const hasAvatar = ref(!!props.user?.id)

watch(() => props.user?.id, (id) => {
  hasAvatar.value = !!id
})

const sizeClass = computed(() => ({
  sm: 'w-8 h-8 text-xs',
  md: 'w-10 h-10 text-sm',
  lg: 'w-16 h-16 text-xl',
}[props.size] || 'w-10 h-10 text-sm'))

const initials = computed(() => {
  const name = props.user?.full_name || props.user?.username || '?'
  return name.split(' ').slice(0, 2).map((p) => p[0]).join('').toUpperCase()
})

const colors = ['bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500', 'bg-pink-500', 'bg-teal-500']
const bgColor = computed(() => colors[(props.user?.id || 0) % colors.length])
</script>
