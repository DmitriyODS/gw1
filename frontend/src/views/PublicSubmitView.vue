<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <div class="w-full max-w-lg">
      <div class="text-center mb-8">
        <h1 class="text-3xl font-bold text-primary-600">Подать заявку</h1>
        <p class="text-surface-500 mt-1">Заполните форму и мы вам поможем</p>
      </div>

      <div v-if="submitted" class="bg-green-50 border border-green-200 rounded-2xl p-8 text-center">
        <div class="text-4xl mb-3">✅</div>
        <h2 class="text-xl font-semibold text-green-700">Заявка отправлена!</h2>
        <p class="text-green-600 mt-2">Мы свяжемся с вами в ближайшее время.</p>
        <Button label="Подать ещё" class="mt-4" outlined @click="reset" />
      </div>

      <div v-else class="bg-surface-0 dark:bg-surface-800 rounded-2xl shadow-lg p-6 space-y-4">
        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Тема *</label>
          <InputText v-model="form.title" placeholder="Кратко опишите задачу" class="w-full" />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Описание</label>
          <Textarea v-model="form.description" placeholder="Подробное описание..." rows="4" class="w-full" />
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

        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Тип задачи</label>
          <Select
            v-model="form.task_type"
            :options="taskTypes"
            optionLabel="name"
            optionValue="value"
            placeholder="Выберите тип"
            class="w-full"
          />
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-sm font-medium">Контакт</label>
          <InputText v-model="form.contact" placeholder="Email или телефон" class="w-full" />
        </div>

        <Button label="Отправить" icon="pi pi-send" class="w-full" :loading="loading" @click="submit" />
        <p v-if="error" class="text-sm text-red-500 text-center">{{ error }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api/index.js'
import { friendlyError } from '../api/errors.js'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'

const form = ref({ title: '', description: '', department_id: null, task_type: '', contact: '' })
const departments = ref([])
const taskTypes = ref([])
const loading = ref(false)
const submitted = ref(false)
const error = ref('')

async function submit() {
  if (!form.value.title.trim()) {
    error.value = 'Укажите тему'
    return
  }
  error.value = ''
  loading.value = true
  try {
    await api.public.submit(form.value)
    submitted.value = true
  } catch (e) {
    error.value = friendlyError(e) || 'Ошибка отправки'
  } finally {
    loading.value = false
  }
}

function reset() {
  form.value = { title: '', description: '', department_id: null, task_type: '', contact: '' }
  submitted.value = false
}

onMounted(async () => {
  const [d, t] = await Promise.all([api.public.departments(), api.public.taskTypes()])
  departments.value = d.data || []
  taskTypes.value = (t.data || []).map((v) => ({ name: v, value: v }))
})
</script>
