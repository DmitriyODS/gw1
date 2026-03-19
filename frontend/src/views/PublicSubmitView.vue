<template>
  <div class="min-h-screen bg-surface-50 dark:bg-surface-900 flex items-center justify-center p-4">
    <div class="w-full max-w-xl">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-primary-600">Подать заявку</h1>
        <p class="text-surface-500 mt-1">Заполните форму — мы свяжемся с вами</p>
      </div>

      <!-- Success -->
      <div v-if="submitted" class="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-2xl p-8 text-center">
        <div class="text-5xl mb-3">✅</div>
        <h2 class="text-xl font-semibold text-green-700 dark:text-green-400">Заявка отправлена!</h2>
        <p class="text-green-600 dark:text-green-500 mt-2">Мы свяжемся с вами в ближайшее время.</p>
        <Button label="Подать ещё одну" class="mt-4" outlined @click="reset" />
      </div>

      <div v-else class="bg-surface-0 dark:bg-surface-800 rounded-2xl shadow-lg p-6 space-y-4 border border-surface-200 dark:border-surface-700">
        <!-- Title -->
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Тема заявки *</label>
          <InputText v-model="form.title" placeholder="Кратко опишите задачу" class="w-full" />
        </div>

        <!-- Type + Dept -->
        <div class="grid grid-cols-2 gap-3">
          <div class="flex flex-col gap-1">
            <label class="text-sm font-medium">Тип задачи</label>
            <Select
              v-model="form.task_type"
              :options="taskTypes"
              optionLabel="label"
              optionValue="value"
              placeholder="Выберите тип"
              class="w-full"
              showClear
              @change="onTypeChange"
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

        <!-- Description -->
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Описание</label>
          <Textarea v-model="form.description" placeholder="Подробное описание задачи..." rows="4" class="w-full" />
        </div>

        <!-- Dynamic fields for publication -->
        <template v-if="form.task_type === 'publication'">
          <div class="bg-primary-50 dark:bg-primary-900/20 rounded-xl p-4 space-y-3 border border-primary-200 dark:border-primary-800">
            <p class="text-xs font-semibold text-primary-600 uppercase tracking-wide">Параметры публикации</p>
            <div class="grid grid-cols-2 gap-3">
              <div class="flex flex-col gap-1">
                <label class="text-sm font-medium">Подтип</label>
                <Select
                  v-model="dynFields.pub_subtype"
                  :options="pubSubtypeOptions"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="Подтип"
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
                  <Checkbox :inputId="'pl_' + p" v-model="dynFields.platforms" :value="p" />
                  <label :for="'pl_' + p" class="text-sm cursor-pointer">{{ p }}</label>
                </div>
              </div>
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">Ссылка</label>
              <InputText v-model="dynFields.link" placeholder="https://..." class="w-full" />
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

        <!-- Customer fields -->
        <div class="border-t border-surface-200 dark:border-surface-700 pt-4">
          <p class="text-sm font-semibold text-surface-600 dark:text-surface-400 mb-3">Ваши контакты</p>
          <div class="grid grid-cols-1 gap-3">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-medium">ФИО *</label>
              <InputText v-model="form.customer_name" placeholder="Иванов Иван Иванович" class="w-full" />
            </div>
            <div class="grid grid-cols-2 gap-3">
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
        </div>

        <!-- File upload -->
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Файлы (необязательно)</label>
          <FileUpload
            ref="fileUploadRef"
            mode="basic"
            chooseLabel="Прикрепить файлы"
            multiple
            :maxFileSize="10000000"
            :auto="false"
            @select="onFilesSelect"
          />
          <div v-if="selectedFiles.length" class="flex flex-wrap gap-1 mt-1">
            <span
              v-for="f in selectedFiles"
              :key="f.name"
              class="text-xs px-2 py-0.5 bg-surface-100 dark:bg-surface-700 rounded-full text-surface-600 dark:text-surface-300"
            >{{ f.name }}</span>
          </div>
        </div>

        <Button label="Отправить заявку" icon="pi pi-send" class="w-full" :loading="loading" @click="submit" />
        <p v-if="error" class="text-sm text-red-500 text-center">{{ error }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { api } from '../api/index.js'
import { friendlyError } from '../api/errors.js'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import DatePicker from 'primevue/datepicker'
import Checkbox from 'primevue/checkbox'
import FileUpload from 'primevue/fileupload'

const form = ref({
  title: '',
  description: '',
  department_id: null,
  task_type: '',
  customer_name: '',
  customer_phone: '',
  customer_email: '',
})

const dynFields = ref({ platforms: [], pub_subtype: '', link: '', pub_date: null, event_date: null })
const pubDate = ref(null)
const eventDate = ref(null)
const selectedFiles = ref([])
const fileUploadRef = ref(null)

const departments = ref([])
const taskTypes = ref([])
const loading = ref(false)
const submitted = ref(false)
const error = ref('')

const pubSubtypeOptions = [
  { label: 'Новость', value: 'news' },
  { label: 'Мероприятие', value: 'event' },
]

const platformOptions = ['ВКонтакте', 'Telegram', 'Instagram', 'Сайт', 'YouTube', 'Email-рассылка']

watch(pubDate, (v) => { dynFields.value.pub_date = v ? v.toISOString() : null })
watch(eventDate, (v) => { dynFields.value.event_date = v ? v.toISOString() : null })

function onTypeChange() {
  dynFields.value = { platforms: [], pub_subtype: '', link: '', pub_date: null, event_date: null }
  pubDate.value = null
  eventDate.value = null
}

function onFilesSelect(event) {
  selectedFiles.value = event.files || []
}

async function submit() {
  if (!form.value.title.trim()) {
    error.value = 'Укажите тему заявки'
    return
  }
  if (!form.value.customer_name.trim()) {
    error.value = 'Укажите ваше имя'
    return
  }
  error.value = ''
  loading.value = true

  try {
    const fd = new FormData()
    fd.append('title', form.value.title)
    fd.append('description', form.value.description || '')
    if (form.value.task_type) fd.append('task_type', form.value.task_type)
    if (form.value.department_id) fd.append('department_id', String(form.value.department_id))
    if (form.value.customer_name) fd.append('customer_name', form.value.customer_name)
    if (form.value.customer_phone) fd.append('customer_phone', form.value.customer_phone)
    if (form.value.customer_email) fd.append('customer_email', form.value.customer_email)

    const df = { ...dynFields.value }
    if (Object.keys(df).some(k => df[k] !== null && df[k] !== '' && !(Array.isArray(df[k]) && !df[k].length))) {
      fd.append('dynamic_fields', JSON.stringify(df))
    }

    for (const file of selectedFiles.value) {
      fd.append('files', file)
    }

    await api.public.submit(fd)
    submitted.value = true
  } catch (e) {
    error.value = friendlyError(e) || 'Ошибка отправки'
  } finally {
    loading.value = false
  }
}

function reset() {
  form.value = { title: '', description: '', department_id: null, task_type: '', customer_name: '', customer_phone: '', customer_email: '' }
  dynFields.value = { platforms: [], pub_subtype: '', link: '', pub_date: null, event_date: null }
  selectedFiles.value = []
  submitted.value = false
  error.value = ''
}

onMounted(async () => {
  const [d, t] = await Promise.all([api.public.departments(), api.public.taskTypes()])
  departments.value = d.data.data || d.data || []
  taskTypes.value = t.data.data || t.data || []
})
</script>
