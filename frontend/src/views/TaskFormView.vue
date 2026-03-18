<template>
  <div class="max-w-2xl mx-auto">
    <div class="flex items-center gap-3 mb-6">
      <Button icon="pi pi-arrow-left" text @click="router.back()" />
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">
        {{ isEdit ? 'Редактировать задачу' : 'Новая задача' }}
      </h1>
    </div>

    <div class="bg-surface-0 dark:bg-surface-800 rounded-2xl p-6 border border-surface-200 dark:border-surface-700 space-y-4">
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium">Название *</label>
        <InputText v-model="form.title" placeholder="Название задачи" class="w-full" />
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium">Описание</label>
        <Textarea v-model="form.description" placeholder="Описание задачи" rows="4" class="w-full" />
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Срочность</label>
          <Select v-model="form.urgency" :options="urgencyOptions" optionLabel="label" optionValue="value" class="w-full" />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Тип задачи</label>
          <Select v-model="form.task_type" :options="taskTypeOptions" optionLabel="label" optionValue="value" placeholder="Выберите тип" class="w-full" showClear />
        </div>
      </div>

      <div class="grid grid-cols-2 gap-4">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Исполнитель</label>
          <Select
            v-model="form.assigned_to_id"
            :options="users"
            optionLabel="full_name"
            optionValue="id"
            placeholder="Выберите пользователя"
            class="w-full"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Отдел</label>
          <Select
            v-model="form.department_id"
            :options="departments"
            optionLabel="name"
            optionValue="id"
            placeholder="Выберите отдел"
            class="w-full"
          />
        </div>
      </div>

      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium">Срок выполнения</label>
        <DatePicker v-model="form.deadline" dateFormat="dd.mm.yy" class="w-full" showIcon />
      </div>

      <div class="flex gap-3 pt-2">
        <Button
          :label="isEdit ? 'Сохранить' : 'Создать'"
          icon="pi pi-check"
          :loading="loading"
          @click="submit"
        />
        <Button label="Отмена" text @click="router.back()" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useTaskStore } from '../stores/tasks.js'
import { useDepartmentStore } from '../stores/departments.js'
import { api } from '../api/index.js'
import { friendlyError } from '../api/errors.js'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const deptStore = useDepartmentStore()
const toast = useToast()

const isEdit = computed(() => !!route.params.id && route.path.includes('/edit'))
const loading = ref(false)
const users = ref([])
const departments = computed(() => deptStore.departments)

const form = ref({
  title: '',
  description: '',
  urgency: 'normal',
  task_type: '',
  assigned_to_id: null,
  department_id: null,
  deadline: null,
})

const urgencyOptions = [
  { label: 'Не срочно', value: 'slow' },
  { label: 'Обычный', value: 'normal' },
  { label: 'Важный', value: 'important' },
  { label: 'Срочно', value: 'urgent' },
]

const TASK_TYPE_LABELS = {
  publication: 'Публикация',
  design: 'Дизайн',
  text: 'Текст',
  photo_video: 'Фото/Видео',
  internal: 'Внутреннее',
  external: 'Внешнее',
}
const taskTypeOptions = ref([])

async function submit() {
  if (!form.value.title.trim()) {
    toast.add({ severity: 'warn', summary: 'Укажите название', life: 2000 })
    return
  }
  loading.value = true
  try {
    const payload = { ...form.value }
    if (payload.deadline instanceof Date) {
      payload.deadline = payload.deadline.toISOString()
    }
    if (isEdit.value) {
      await taskStore.updateTask(route.params.id, payload)
      toast.add({ severity: 'success', summary: 'Задача обновлена', life: 2000 })
    } else {
      const task = await taskStore.createTask(payload)
      toast.add({ severity: 'success', summary: 'Задача создана', life: 2000 })
      router.push(`/tasks/${task.id}`)
      return
    }
    router.push(`/tasks/${route.params.id}`)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const [, typesRes] = await Promise.all([
    deptStore.fetchDepartments(),
    api.public.taskTypes(),
  ])
  taskTypeOptions.value = (typesRes.data.data || []).map((t) => ({
    label: TASK_TYPE_LABELS[t] || t,
    value: t,
  }))
  const { data } = await api.users.list()
  users.value = data.data || []

  if (isEdit.value) {
    const task = await taskStore.fetchTask(route.params.id)
    form.value = {
      title: task.title || '',
      description: task.description || '',
      urgency: task.urgency || 'normal',
      task_type: task.task_type || '',
      assigned_to_id: task.assigned_to_id || null,
      department_id: task.department_id || null,
      deadline: task.deadline ? new Date(task.deadline) : null,
    }
  }
})
</script>
