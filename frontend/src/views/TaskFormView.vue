<template>
  <div class="max-w-2xl mx-auto">
    <div class="flex items-center gap-3 mb-6">
      <Button icon="pi pi-arrow-left" text @click="router.back()" />
      <h1 class="text-xl font-bold text-surface-800 dark:text-surface-200">
        {{ isEdit ? 'Редактировать задачу' : 'Новая задача' }}
      </h1>
    </div>

    <div class="bg-surface-0 dark:bg-surface-800 rounded-2xl p-6 border border-surface-200 dark:border-surface-700 space-y-4">
      <!-- Название -->
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium">Название *</label>
        <InputText v-model="form.title" placeholder="Название задачи" class="w-full" />
      </div>

      <!-- Тип и срочность -->
      <div class="grid grid-cols-2 gap-4">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Тип задачи</label>
          <Select
            v-model="form.task_type"
            :options="taskTypeOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Выберите тип"
            class="w-full"
            showClear
            @change="onTypeChange"
          />
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Срочность</label>
          <Select v-model="form.urgency" :options="urgencyOptions" optionLabel="label" optionValue="value" class="w-full" />
        </div>
      </div>

      <!-- Исполнитель и отдел -->
      <div class="grid grid-cols-2 gap-4">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Исполнитель</label>
          <Select
            v-model="form.assigned_to_id"
            :options="users"
            optionLabel="full_name"
            optionValue="id"
            placeholder="Не назначено"
            class="w-full"
            showClear
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
            showClear
          />
        </div>
      </div>

      <!-- Срок -->
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium">Срок выполнения</label>
        <DatePicker v-model="form.deadline" dateFormat="dd.mm.yy" class="w-full" showIcon showTime hourFormat="24" />
      </div>

      <!-- Теги -->
      <div class="flex flex-col gap-2">
        <label class="text-sm font-medium">Теги</label>
        <div class="flex flex-wrap gap-2">
          <div v-for="tag in TAGS" :key="tag.value" class="flex items-center gap-1.5">
            <Checkbox :inputId="'tag_' + tag.value" v-model="form.tags" :value="tag.value" />
            <label :for="'tag_' + tag.value" class="text-sm cursor-pointer">{{ tag.label }}</label>
          </div>
        </div>
      </div>

      <!-- Динамические поля по типу задачи -->
      <template v-if="form.task_type === 'publication'">
        <div class="bg-primary-50 dark:bg-primary-900/20 rounded-xl p-4 space-y-3 border border-primary-200 dark:border-primary-800">
          <p class="text-xs font-semibold text-primary-600 uppercase tracking-wide">Параметры публикации</p>
          <div class="grid grid-cols-2 gap-3">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Подтип</label>
              <Select
                v-model="form.dynamic_fields.pub_subtype"
                :options="pubSubtypeOptions"
                optionLabel="label"
                optionValue="value"
                placeholder="Выберите подтип"
                class="w-full"
              />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Дата публикации</label>
              <DatePicker v-model="pubDate" dateFormat="dd.mm.yy" class="w-full" showIcon showTime hourFormat="24" />
            </div>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Площадки</label>
            <div class="flex flex-wrap gap-3">
              <div v-for="p in platformOptions" :key="p" class="flex items-center gap-1.5">
                <Checkbox :inputId="'pl_' + p" v-model="form.dynamic_fields.platforms" :value="p" />
                <label :for="'pl_' + p" class="text-sm cursor-pointer">{{ p }}</label>
              </div>
            </div>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Ссылка</label>
            <InputText v-model="form.dynamic_fields.link" placeholder="https://..." class="w-full" />
          </div>
        </div>
      </template>

      <template v-else-if="form.task_type === 'photo_video'">
        <div class="bg-orange-50 dark:bg-orange-900/20 rounded-xl p-4 space-y-3 border border-orange-200 dark:border-orange-800">
          <p class="text-xs font-semibold text-orange-600 uppercase tracking-wide">Параметры фото/видео</p>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Дата мероприятия</label>
            <DatePicker v-model="eventDate" dateFormat="dd.mm.yy" class="w-full" showIcon showTime hourFormat="24" />
          </div>
        </div>
      </template>

      <template v-else-if="form.task_type === 'edits'">
        <div class="bg-purple-50 dark:bg-purple-900/20 rounded-xl p-4 space-y-3 border border-purple-200 dark:border-purple-800">
          <p class="text-xs font-semibold text-purple-600 uppercase tracking-wide">Параметры правок</p>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Ссылка на задачу</label>
            <InputText v-model="form.dynamic_fields.task_link" placeholder="ID или ссылка на оригинальную задачу" class="w-full" />
          </div>
        </div>
      </template>

      <template v-else-if="form.task_type && form.task_type !== 'publication' && form.task_type !== 'photo_video' && form.task_type !== 'edits'">
        <div class="bg-surface-50 dark:bg-surface-900/50 rounded-xl p-4 space-y-3 border border-surface-200 dark:border-surface-700">
          <p class="text-xs font-semibold text-surface-500 uppercase tracking-wide">Уточнение</p>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Дополнительная информация</label>
            <Textarea v-model="form.dynamic_fields.clarification" rows="3" placeholder="Уточните детали задачи..." class="w-full" />
          </div>
        </div>
      </template>

      <!-- Описание -->
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium">Описание</label>
        <Textarea v-model="form.description" placeholder="Подробное описание задачи" rows="4" class="w-full" />
      </div>

      <!-- Данные заказчика -->
      <div class="border-t border-surface-200 dark:border-surface-700 pt-4">
        <p class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-3">Заказчик</p>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">ФИО</label>
            <InputText v-model="form.customer_name" placeholder="Иванов Иван Иванович" class="w-full" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Телефон</label>
            <InputText v-model="form.customer_phone" placeholder="+7 (999) 000-00-00" class="w-full" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Email</label>
            <InputText v-model="form.customer_email" type="email" placeholder="email@example.com" class="w-full" />
          </div>
        </div>
      </div>

      <!-- Кнопки -->
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
import { ref, computed, watch, onMounted } from 'vue'
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
import Checkbox from 'primevue/checkbox'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const deptStore = useDepartmentStore()
const toast = useToast()

const isEdit = computed(() => !!route.params.id && route.path.includes('/edit'))
const loading = ref(false)
const users = ref([])
const departments = computed(() => deptStore.departments)

const TAGS = [
  { value: 'design',    label: 'Дизайн' },
  { value: 'text',      label: 'Текст' },
  { value: 'publication', label: 'Публикация' },
  { value: 'photo_video', label: 'Фото/Видео' },
  { value: 'internal',  label: 'Внутреннее' },
  { value: 'external',  label: 'Внешнее' },
]

// Auto-tags per task type
const AUTO_TAGS = {
  publication: ['publication'],
  design_image: ['design'],
  design_handout: ['design'],
  design_banner: ['design'],
  design_poster: ['design'],
  verify_presentation: ['design'],
  design_presentation: ['design'],
  verify_design: ['design'],
  design_merch: ['design'],
  design_cards: ['design'],
  mailing: ['external'],
  photo_video: ['photo_video'],
  mail_check: ['internal'],
  edits: ['internal'],
  video_edit: ['photo_video'],
  photo_edit: ['photo_video'],
  internal_work: ['internal'],
  external_work: ['external'],
}

const pubSubtypeOptions = [
  { label: 'Новость', value: 'news' },
  { label: 'Мероприятие', value: 'event' },
]

const platformOptions = ['ВКонтакте', 'Telegram', 'Instagram', 'Сайт', 'YouTube', 'Email-рассылка']

const urgencyOptions = [
  { label: 'Не срочно', value: 'slow' },
  { label: 'Обычный', value: 'normal' },
  { label: 'Важный', value: 'important' },
  { label: 'Срочно', value: 'urgent' },
]

const taskTypeOptions = ref([])

// Separate date refs for dynamic fields (DatePicker needs Date objects)
const pubDate = ref(null)
const eventDate = ref(null)

const form = ref({
  title: '',
  description: '',
  urgency: 'normal',
  task_type: '',
  assigned_to_id: null,
  department_id: null,
  deadline: null,
  tags: [],
  customer_name: '',
  customer_phone: '',
  customer_email: '',
  dynamic_fields: { platforms: [] },
})

// Sync pubDate / eventDate into dynamic_fields
watch(pubDate, (v) => {
  form.value.dynamic_fields.pub_date = v ? v.toISOString() : null
})
watch(eventDate, (v) => {
  form.value.dynamic_fields.event_date = v ? v.toISOString() : null
})

function onTypeChange() {
  if (!isEdit.value) {
    const autoTags = AUTO_TAGS[form.value.task_type] || []
    form.value.tags = [...autoTags]
  }
  // Reset dynamic fields on type change
  form.value.dynamic_fields = { platforms: [] }
  pubDate.value = null
  eventDate.value = null
}

async function submit() {
  if (!form.value.title.trim()) {
    toast.add({ severity: 'warn', summary: 'Укажите название', life: 2000 })
    return
  }
  loading.value = true
  try {
    const payload = {
      ...form.value,
      task_type: form.value.task_type || null,
      customer_name: form.value.customer_name || null,
      customer_phone: form.value.customer_phone || null,
      customer_email: form.value.customer_email || null,
    }
    if (payload.deadline instanceof Date) {
      payload.deadline = payload.deadline.toISOString()
    }
    if (isEdit.value) {
      await taskStore.updateTask(route.params.id, payload)
      toast.add({ severity: 'success', summary: 'Задача обновлена', life: 2000 })
      router.push(`/tasks/${route.params.id}`)
    } else {
      const task = await taskStore.createTask(payload)
      toast.add({ severity: 'success', summary: 'Задача создана', life: 2000 })
      router.push(`/tasks/${task.id}`)
    }
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Ошибка', detail: friendlyError(e), life: 3000 })
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  const [, typesRes] = await Promise.all([
    deptStore.fetchDepartments(),
    api.tasks.types(),
  ])
  taskTypeOptions.value = typesRes.data.data || []
  const { data } = await api.users.list()
  users.value = data.data || []

  if (isEdit.value) {
    const task = await taskStore.fetchTask(route.params.id)
    const df = task.dynamic_fields || {}
    form.value = {
      title: task.title || '',
      description: task.description || '',
      urgency: task.urgency || 'normal',
      task_type: task.task_type || '',
      assigned_to_id: task.assigned_to_id || null,
      department_id: task.department_id || null,
      deadline: task.deadline ? new Date(task.deadline) : null,
      tags: task.tags || [],
      customer_name: task.customer_name || '',
      customer_phone: task.customer_phone || '',
      customer_email: task.customer_email || '',
      dynamic_fields: { platforms: [], ...df },
    }
    if (df.pub_date) pubDate.value = new Date(df.pub_date)
    if (df.event_date) eventDate.value = new Date(df.event_date)
  }
})
</script>
