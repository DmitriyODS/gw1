// Карта английских сообщений бэкенда → русский текст для пользователя
const ERROR_MAP = {
  'invalid credentials':           'Неверный логин или пароль',
  'user not found':                'Пользователь не найден',
  'unauthorized':                  'Необходима авторизация',
  'forbidden':                     'Недостаточно прав',
  'not found':                     'Запись не найдена',
  'already exists':                'Такая запись уже существует',
  'username already taken':        'Этот логин уже занят',
  'you already have an active timer': 'У вас уже запущен таймер на другой задаче',
  'task already in progress':      'Задача уже выполняется другим сотрудником',
  'internal server error':         'Внутренняя ошибка сервера',
  'bad request':                   'Некорректный запрос',
  'no refresh token':              'Сессия истекла, войдите снова',
}

/**
 * Возвращает понятное пользователю сообщение об ошибке на русском языке.
 * @param {unknown} err — объект ошибки axios или строка
 * @param {string} [fallback] — текст по умолчанию
 */
export function friendlyError(err, fallback = 'Что-то пошло не так. Попробуйте ещё раз.') {
  const raw = err?.response?.data?.error || err?.message || ''
  const lower = raw.toLowerCase()

  for (const [key, ru] of Object.entries(ERROR_MAP)) {
    if (lower.includes(key)) return ru
  }

  // Если бэкенд вернул уже русский текст — показываем как есть
  if (raw && /[а-яА-Я]/.test(raw)) return raw

  return fallback
}
