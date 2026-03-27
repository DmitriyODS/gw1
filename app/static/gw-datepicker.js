/**
 * GW DatePicker — кастомные компоненты выбора даты/времени
 * GWDatePicker  — одиночный пикер (date / datetime)
 * GWRangePicker — выбор диапазона дат
 *
 * Автоматически инициализируется на input[type="date"] и input[type="datetime-local"].
 * Для отключения добавьте data-no-datepicker на input или обёртку.
 */

/* ─────────────────────────── CSS ─────────────────────────── */
(function injectCSS() {
  if (document.getElementById('gw-dp-styles')) return;
  const style = document.createElement('style');
  style.id = 'gw-dp-styles';
  style.textContent = `
/* ── GW DatePicker ── */
.gw-dp-wrap { position: relative; display: block; }
.gw-dp-field {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; min-height: 42px;
  border: 1.5px solid var(--color-base-300);
  border-radius: 10px;
  background: var(--color-base-100);
  cursor: pointer; user-select: none;
  transition: border-color .15s, box-shadow .15s;
  font-size: .875rem; color: var(--color-base-content);
}
.gw-dp-field:hover { border-color: var(--color-primary); }
.gw-dp-field.open  { border-color: var(--color-primary); box-shadow: 0 0 0 3px color-mix(in oklch, var(--color-primary) 18%, transparent); }
.gw-dp-field-icon  { color: color-mix(in oklch, var(--color-base-content) 40%, transparent); font-size: 1rem; flex-shrink: 0; }
.gw-dp-field-val   { flex: 1; }
.gw-dp-field-placeholder { color: color-mix(in oklch, var(--color-base-content) 35%, transparent); }
.gw-dp-field-clear {
  opacity: 0; pointer-events: none; transition: opacity .15s;
  background: none; border: none; cursor: pointer; padding: 0 2px;
  color: color-mix(in oklch, var(--color-base-content) 40%, transparent);
  display: flex; align-items: center; font-size: .85rem;
}
.gw-dp-field:hover .gw-dp-field-clear.visible,
.gw-dp-field-clear.visible { opacity: 1; pointer-events: auto; }

/* ── Popup ── */
.gw-dp-popup {
  position: fixed; z-index: 9999;
  background: var(--color-base-100);
  border: 1px solid var(--color-base-300);
  border-radius: 14px;
  box-shadow: 0 8px 32px rgba(0,0,0,.14);
  padding: 12px; min-width: 280px;
  box-sizing: border-box;
  opacity: 0; transform: translateY(6px) scale(.98);
  transition: opacity .15s, transform .15s;
  pointer-events: none;
}
.gw-dp-popup.visible { opacity: 1; transform: none; pointer-events: auto; }
@media (max-width: 579px) {
  .gw-rp-months { flex-direction: column !important; }
  .gw-rp-divider { display: none !important; }
}

/* ── Calendar header ── */
.gw-dp-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.gw-dp-nav-btn {
  width: 28px; height: 28px; border: none; border-radius: 7px;
  background: color-mix(in oklch, var(--color-base-content) 6%, transparent);
  color: var(--color-base-content); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: .85rem; transition: background .12s;
}
.gw-dp-nav-btn:hover { background: color-mix(in oklch, var(--color-primary) 12%, var(--color-base-100)); color: var(--color-primary); }
.gw-dp-month-label {
  font-size: .875rem; font-weight: 700; cursor: pointer;
  padding: 3px 8px; border-radius: 7px;
  transition: background .12s;
}
.gw-dp-month-label:hover { background: color-mix(in oklch, var(--color-base-content) 6%, transparent); }

/* ── Weekday row ── */
.gw-dp-weekdays {
  display: grid; grid-template-columns: repeat(7, 1fr);
  gap: 2px; margin-bottom: 4px;
}
.gw-dp-wd {
  text-align: center; font-size: .68rem; font-weight: 700;
  color: color-mix(in oklch, var(--color-base-content) 40%, transparent);
  padding: 3px 0;
}

/* ── Day grid ── */
.gw-dp-days {
  display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px;
}
.gw-dp-day {
  aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  border-radius: 7px; font-size: .82rem; cursor: pointer;
  border: none; background: none; color: var(--color-base-content);
  transition: background .12s, color .12s;
}
.gw-dp-day:hover:not(.empty):not(.selected) { background: color-mix(in oklch, var(--color-primary) 10%, var(--color-base-100)); color: var(--color-primary); }
.gw-dp-day.other-month { color: color-mix(in oklch, var(--color-base-content) 25%, transparent); }
.gw-dp-day.today:not(.selected) {
  background: color-mix(in oklch, var(--color-primary) 10%, var(--color-base-100));
  color: var(--color-primary); font-weight: 700;
  box-shadow: inset 0 0 0 1.5px color-mix(in oklch, var(--color-primary) 40%, transparent);
}
.gw-dp-day.selected {
  background: var(--color-primary); color: var(--color-primary-content);
  font-weight: 700;
}
.gw-dp-day.in-range {
  background: color-mix(in oklch, var(--color-primary) 12%, var(--color-base-100));
  border-radius: 0;
}
.gw-dp-day.range-start { border-radius: 7px 0 0 7px; }
.gw-dp-day.range-end   { border-radius: 0 7px 7px 0; }
.gw-dp-day.range-start.range-end { border-radius: 7px; }
.gw-dp-day.disabled { opacity: .35; cursor: default; pointer-events: none; }

/* ── Time picker ── */
.gw-dp-time {
  display: flex; align-items: center; justify-content: center; gap: 6px;
  margin-top: 10px; padding-top: 10px;
  border-top: 1px solid var(--color-base-200);
}
.gw-dp-time-label { font-size: .75rem; color: color-mix(in oklch, var(--color-base-content) 50%, transparent); font-weight: 600; }
.gw-dp-time-unit {
  display: flex; flex-direction: column; align-items: center; gap: 2px;
}
.gw-dp-time-spin {
  width: 32px; height: 22px; border: none; border-radius: 5px;
  background: color-mix(in oklch, var(--color-base-content) 5%, var(--color-base-100));
  color: var(--color-base-content); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: .7rem; transition: background .12s;
}
.gw-dp-time-spin:hover { background: color-mix(in oklch, var(--color-primary) 12%, var(--color-base-100)); color: var(--color-primary); }
.gw-dp-time-val {
  font-size: .92rem; font-weight: 700; width: 36px; text-align: center;
  border: 1.5px solid var(--color-base-300); border-radius: 6px;
  padding: 3px 2px; background: var(--color-base-100);
  color: var(--color-base-content); outline: none;
  transition: border-color .12s;
  -moz-appearance: textfield;
}
.gw-dp-time-val:focus { border-color: var(--color-primary); box-shadow: 0 0 0 2px color-mix(in oklch, var(--color-primary) 15%, transparent); }
.gw-dp-time-val::-webkit-inner-spin-button,
.gw-dp-time-val::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
.gw-dp-sep { font-size: 1rem; font-weight: 700; opacity: .5; }

/* ── Footer ── */
.gw-dp-footer {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 10px; padding-top: 8px;
  border-top: 1px solid var(--color-base-200);
}
.gw-dp-today-btn, .gw-dp-clear-btn {
  border: none; background: none; cursor: pointer; padding: 4px 8px; border-radius: 6px;
  font-size: .78rem; font-weight: 600; transition: background .12s, color .12s;
}
.gw-dp-today-btn { color: var(--color-primary); }
.gw-dp-today-btn:hover { background: color-mix(in oklch, var(--color-primary) 10%, var(--color-base-100)); }
.gw-dp-clear-btn { color: color-mix(in oklch, var(--color-base-content) 50%, transparent); }
.gw-dp-clear-btn:hover { background: color-mix(in oklch, var(--color-base-content) 8%, transparent); color: var(--color-base-content); }

/* ── Range two-column layout ── */
.gw-rp-months { display: flex; gap: 16px; }
.gw-rp-month  { flex: 1; }
.gw-rp-divider { width: 1px; background: var(--color-base-200); flex-shrink: 0; }
.gw-rp-footer {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 10px; padding-top: 8px;
  border-top: 1px solid var(--color-base-200);
  font-size: .78rem; color: color-mix(in oklch, var(--color-base-content) 55%, transparent);
}
.gw-rp-selected-range { font-weight: 600; color: var(--color-primary); }
`;
  document.head.appendChild(style);
})();

/* ─────────────────────── Helpers ─────────────────────── */
const MONTHS_RU = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                   'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'];
const WD_RU = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'];

function startOfMonth(y, m) { return new Date(y, m, 1); }
function daysInMonth(y, m)  { return new Date(y, m + 1, 0).getDate(); }
function isSameDay(a, b)    { return a && b && a.getFullYear()===b.getFullYear() && a.getMonth()===b.getMonth() && a.getDate()===b.getDate(); }
function clamp(v, lo, hi)   { return Math.min(hi, Math.max(lo, v)); }
function pad2(n)             { return String(n).padStart(2, '0'); }

function toISO(date, withTime) {
  if (!date) return '';
  const y = date.getFullYear(), mo = pad2(date.getMonth()+1), d = pad2(date.getDate());
  if (!withTime) return `${y}-${mo}-${d}`;
  return `${y}-${mo}-${d}T${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function formatDisplay(date, withTime) {
  if (!date) return '';
  const d = pad2(date.getDate()), mo = pad2(date.getMonth()+1), y = date.getFullYear();
  if (!withTime) return `${d}.${mo}.${y}`;
  return `${d}.${mo}.${y} ${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function parseISO(str) {
  if (!str) return null;
  const d = new Date(str.includes('T') ? str : str + 'T00:00:00');
  return isNaN(d) ? null : d;
}


/* ═══════════════════════ GWDatePicker ═══════════════════════ */
class GWDatePicker {
  constructor(inputEl, opts = {}) {
    if (inputEl._gwDp) return;
    inputEl._gwDp = this;

    this.input    = inputEl;
    this.withTime = opts.withTime ?? (inputEl.type === 'datetime-local');
    this.required = opts.required ?? inputEl.required;
    this.placeholder = opts.placeholder ?? (this.withTime ? 'Выберите дату и время' : 'Выберите дату');
    this.onChange = opts.onChange || null;

    this.value    = parseISO(inputEl.value) || null;
    this.viewYear = (this.value || new Date()).getFullYear();
    this.viewMonth= (this.value || new Date()).getMonth();
    this.hour     = this.value ? this.value.getHours()   : 12;
    this.minute   = this.value ? this.value.getMinutes() : 0;
    this._open    = false;

    this._build();
    this._render();
  }

  _build() {
    const inp = this.input;
    inp.style.display = 'none';

    const wrap = document.createElement('div');
    wrap.className = 'gw-dp-wrap';
    inp.parentNode.insertBefore(wrap, inp);
    wrap.appendChild(inp);
    this.wrap = wrap;

    // Field
    const field = document.createElement('div');
    field.className = 'gw-dp-field';
    field.setAttribute('tabindex', '0');
    field.setAttribute('role', 'button');
    field.innerHTML = `
      <i class="bi bi-calendar3 gw-dp-field-icon"></i>
      <span class="gw-dp-field-val"></span>
      <button type="button" class="gw-dp-field-clear" tabindex="-1">
        <i class="bi bi-x-circle-fill"></i>
      </button>`;
    wrap.appendChild(field);
    this.field    = field;
    this.fieldVal = field.querySelector('.gw-dp-field-val');
    this.clearBtn = field.querySelector('.gw-dp-field-clear');

    // Popup (appended to body to avoid overflow/transform clipping)
    const popup = document.createElement('div');
    popup.className = 'gw-dp-popup below';
    document.body.appendChild(popup);
    this.popup = popup;

    this._buildPopup();
    this._bindEvents();
  }

  _buildPopup() {
    this.popup.innerHTML = `
      <div class="gw-dp-header">
        <button type="button" class="gw-dp-nav-btn" data-dir="-1"><i class="bi bi-chevron-left"></i></button>
        <span class="gw-dp-month-label"></span>
        <button type="button" class="gw-dp-nav-btn" data-dir="1"><i class="bi bi-chevron-right"></i></button>
      </div>
      <div class="gw-dp-weekdays">${WD_RU.map(w=>`<div class="gw-dp-wd">${w}</div>`).join('')}</div>
      <div class="gw-dp-days"></div>
      ${this.withTime ? `
      <div class="gw-dp-time">
        <span class="gw-dp-time-label">Время</span>
        <div class="gw-dp-time-unit">
          <button type="button" class="gw-dp-time-spin" data-field="h" data-d="1"><i class="bi bi-chevron-up"></i></button>
          <input type="text" class="gw-dp-time-val" data-time-field="h" maxlength="2" inputmode="numeric" autocomplete="off">
          <button type="button" class="gw-dp-time-spin" data-field="h" data-d="-1"><i class="bi bi-chevron-down"></i></button>
        </div>
        <span class="gw-dp-sep">:</span>
        <div class="gw-dp-time-unit">
          <button type="button" class="gw-dp-time-spin" data-field="m" data-d="1"><i class="bi bi-chevron-up"></i></button>
          <input type="text" class="gw-dp-time-val" data-time-field="m" maxlength="2" inputmode="numeric" autocomplete="off">
          <button type="button" class="gw-dp-time-spin" data-field="m" data-d="-1"><i class="bi bi-chevron-down"></i></button>
        </div>
      </div>` : ''}
      <div class="gw-dp-footer">
        <button type="button" class="gw-dp-today-btn">Сегодня</button>
        ${!this.required ? '<button type="button" class="gw-dp-clear-btn">Очистить</button>' : ''}
      </div>`;
  }

  _bindEvents() {
    this.field.addEventListener('click', e => {
      if (e.target.closest('.gw-dp-field-clear')) return;
      this._toggle();
    });
    this.field.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this._toggle(); }
      if (e.key === 'Escape') this._close();
    });
    this.clearBtn.addEventListener('click', e => { e.stopPropagation(); this._clear(); });

    // Nav buttons
    this.popup.querySelectorAll('.gw-dp-nav-btn').forEach(btn => {
      btn.addEventListener('click', () => this._navigate(+btn.dataset.dir));
    });

    // Day clicks
    this.popup.querySelector('.gw-dp-days').addEventListener('click', e => {
      const btn = e.target.closest('.gw-dp-day');
      if (!btn || btn.classList.contains('empty')) return;
      const d = new Date(+btn.dataset.ts);
      if (this.withTime) { d.setHours(this.hour); d.setMinutes(this.minute); }
      this._setValue(d);
      if (!this.withTime) this._close();
    });

    // Time spin buttons
    if (this.withTime) {
      this.popup.querySelectorAll('.gw-dp-time-spin').forEach(btn => {
        btn.addEventListener('click', () => {
          const { field, d } = btn.dataset;
          if (field === 'h') this.hour   = (this.hour   + +d + 24) % 24;
          if (field === 'm') this.minute = (this.minute + +d * 5 + 60) % 60;
          this._renderTime();
          this._applyTimeToValue();
        });
      });

      // Manual text input for time fields
      this.popup.querySelectorAll('.gw-dp-time-val').forEach(inp => {
        const field = inp.dataset.timeField;

        // Select all on focus for quick overwrite
        inp.addEventListener('focus', () => inp.select());

        // Allow only digits while typing
        inp.addEventListener('input', () => {
          inp.value = inp.value.replace(/\D/g, '').slice(0, 2);
        });

        // Commit on blur
        inp.addEventListener('blur', () => this._commitTimeInput(inp, field));

        // Enter commits; Escape blurs
        inp.addEventListener('keydown', e => {
          if (e.key === 'Enter') { e.preventDefault(); this._commitTimeInput(inp, field); inp.blur(); }
          if (e.key === 'Escape') { this._renderTime(); inp.blur(); }
          // Arrow up/down to spin
          if (e.key === 'ArrowUp')   { e.preventDefault(); this._spinTime(field, 1); }
          if (e.key === 'ArrowDown') { e.preventDefault(); this._spinTime(field, -1); }
        });

        // Mouse wheel to spin
        inp.addEventListener('wheel', e => {
          e.preventDefault();
          this._spinTime(field, e.deltaY < 0 ? 1 : -1);
        }, { passive: false });
      });
    }

    // Today / Clear
    const todayBtn = this.popup.querySelector('.gw-dp-today-btn');
    if (todayBtn) todayBtn.addEventListener('click', () => {
      const now = new Date();
      if (this.withTime) { now.setHours(this.hour); now.setMinutes(this.minute); }
      this._setValue(now); if (!this.withTime) this._close();
    });
    const clearBtn2 = this.popup.querySelector('.gw-dp-clear-btn');
    if (clearBtn2) clearBtn2.addEventListener('click', () => { this._clear(); this._close(); });

    // Close on outside click (popup is in body, so check both wrap and popup)
    document.addEventListener('mousedown', this._onOutside = e => {
      if (!this.wrap.contains(e.target) && !this.popup.contains(e.target)) this._close();
    }, true);
  }

  _toggle() { this._open ? this._close() : this._openPopup(); }

  _openPopup() {
    this._open = true;
    this.field.classList.add('open');
    this._renderCalendar();
    if (this.withTime) this._renderTime();
    this.popup.classList.add('visible');
    this._positionPopup();
    this._onScrollResize = () => this._positionPopup();
    window.addEventListener('scroll', this._onScrollResize, { passive: true, capture: true });
    window.addEventListener('resize', this._onScrollResize, { passive: true });
  }

  _close() {
    this._open = false;
    this.field.classList.remove('open');
    this.popup.classList.remove('visible');
    if (this._onScrollResize) {
      window.removeEventListener('scroll', this._onScrollResize, { capture: true });
      window.removeEventListener('resize', this._onScrollResize);
      this._onScrollResize = null;
    }
  }

  _positionPopup() {
    const MARGIN = 8, GAP = 6;
    const rect = this.wrap.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;

    // Horizontal: align left, clamp to viewport
    const pw = Math.min(this.popup.offsetWidth || 280, vw - MARGIN * 2);
    let left = rect.left;
    if (left + pw > vw - MARGIN) left = vw - MARGIN - pw;
    if (left < MARGIN) left = MARGIN;
    this.popup.style.left = left + 'px';
    this.popup.style.maxWidth = (vw - MARGIN * 2) + 'px';

    // Vertical: start below anchor, shift up if popup goes off bottom of viewport
    const ph = this.popup.offsetHeight;
    let top = rect.bottom + GAP;
    const overflow = top + ph - (vh - MARGIN);
    if (overflow > 0) top -= overflow;
    if (top < MARGIN) top = MARGIN;
    this.popup.style.top = top + 'px';
    this.popup.style.bottom = 'auto';
  }

  _navigate(dir) {
    this.viewMonth += dir;
    if (this.viewMonth > 11) { this.viewMonth = 0;  this.viewYear++; }
    if (this.viewMonth < 0)  { this.viewMonth = 11; this.viewYear--; }
    this._renderCalendar();
  }

  _renderCalendar() {
    const y = this.viewYear, m = this.viewMonth;
    this.popup.querySelector('.gw-dp-month-label').textContent = `${MONTHS_RU[m]} ${y}`;

    const first = startOfMonth(y, m);
    const firstDow = (first.getDay() + 6) % 7; // 0=Mon
    const days = daysInMonth(y, m);
    const today = new Date();

    let html = '';
    // Empty cells before first day
    for (let i = 0; i < firstDow; i++) {
      const prevDays = daysInMonth(y, m - 1 < 0 ? 11 : m - 1);
      const d = prevDays - firstDow + i + 1;
      const date = new Date(m === 0 ? y - 1 : y, m === 0 ? 11 : m - 1, d);
      html += `<button type="button" class="gw-dp-day other-month" data-ts="${date.getTime()}">${d}</button>`;
    }
    for (let d = 1; d <= days; d++) {
      const date = new Date(y, m, d);
      const sel  = isSameDay(date, this.value);
      const tod  = isSameDay(date, today);
      html += `<button type="button" class="gw-dp-day${sel?' selected':''}${tod&&!sel?' today':''}" data-ts="${date.getTime()}">${d}</button>`;
    }
    // Fill remainder
    const total = firstDow + days;
    const nextCells = (7 - (total % 7)) % 7;
    for (let d = 1; d <= nextCells; d++) {
      const date = new Date(m === 11 ? y + 1 : y, m === 11 ? 0 : m + 1, d);
      html += `<button type="button" class="gw-dp-day other-month" data-ts="${date.getTime()}">${d}</button>`;
    }
    this.popup.querySelector('.gw-dp-days').innerHTML = html;
  }

  _renderTime() {
    if (!this.withTime) return;
    const h  = this.popup.querySelector('[data-time-field="h"]');
    const mi = this.popup.querySelector('[data-time-field="m"]');
    // Don't overwrite a focused input — user is typing
    if (h  && document.activeElement !== h)  h.value  = pad2(this.hour);
    if (mi && document.activeElement !== mi) mi.value = pad2(this.minute);
  }

  _commitTimeInput(inp, field) {
    const raw = parseInt(inp.value, 10);
    if (!isNaN(raw)) {
      if (field === 'h') this.hour   = clamp(raw, 0, 23);
      if (field === 'm') this.minute = clamp(raw, 0, 59);
    }
    this._renderTime();
    this._applyTimeToValue();
  }

  _spinTime(field, dir) {
    if (field === 'h') this.hour   = (this.hour   + dir + 24) % 24;
    if (field === 'm') this.minute = (this.minute + dir * 5 + 60) % 60;
    this._renderTime();
    this._applyTimeToValue();
  }

  _applyTimeToValue() {
    if (this.value) {
      this.value.setHours(this.hour);
      this.value.setMinutes(this.minute);
      this._commit();
    }
  }

  _setValue(date) {
    this.value = date;
    if (date) {
      this.viewYear  = date.getFullYear();
      this.viewMonth = date.getMonth();
      this.hour   = date.getHours();
      this.minute = date.getMinutes();
    }
    this._commit();
    this._render();
    if (this._open) this._renderCalendar();
  }

  _clear() {
    this.value = null;
    this._commit();
    this._render();
    if (this._open) this._renderCalendar();
  }

  _commit() {
    this.input.value = toISO(this.value, this.withTime);
    this.input.dispatchEvent(new Event('change', { bubbles: true }));
    if (this.onChange) this.onChange(this.value, toISO(this.value, this.withTime));
  }

  _render() {
    const hasVal = !!this.value;
    if (hasVal) {
      this.fieldVal.textContent = formatDisplay(this.value, this.withTime);
      this.fieldVal.classList.remove('gw-dp-field-placeholder');
    } else {
      this.fieldVal.textContent = this.placeholder;
      this.fieldVal.classList.add('gw-dp-field-placeholder');
    }
    this.clearBtn.classList.toggle('visible', hasVal && !this.required);
  }

  destroy() {
    document.removeEventListener('mousedown', this._onOutside, true);
    this.popup.remove();
    this.input.style.display = '';
    this.wrap.replaceWith(this.input);
  }
}


/* ═══════════════════════ GWRangePicker ═══════════════════════ */
class GWRangePicker {
  /**
   * @param {HTMLInputElement} startInput  — скрытый input для start date
   * @param {HTMLInputElement} endInput    — скрытый input для end date
   * @param {object} opts
   *   opts.placeholder  — плейсхолдер поля (string)
   *   opts.onChange     — callback(startDate, endDate, startISO, endISO)
   */
  constructor(startInput, endInput, opts = {}) {
    if (startInput._gwRp) return;
    startInput._gwRp = this;

    this.startInput = startInput;
    this.endInput   = endInput;
    this.placeholder = opts.placeholder || 'Выберите период';
    this.onChange    = opts.onChange || null;

    this.startDate = parseISO(startInput.value) || null;
    this.endDate   = parseISO(endInput.value)   || null;
    this.hoverDate = null;
    this.selecting = this.startDate ? (this.endDate ? null : 'end') : 'start';

    const base = this.startDate || new Date();
    this.viewYear  = [base.getFullYear(), base.getFullYear()];
    this.viewMonth = [base.getMonth(), (base.getMonth() + 1) % 12];
    if (base.getMonth() === 11) this.viewYear[1]++;

    this._open = false;
    this._build();
    this._render();
  }

  _build() {
    [this.startInput, this.endInput].forEach(inp => inp.style.display = 'none');

    const wrap = document.createElement('div');
    wrap.className = 'gw-dp-wrap';
    this.startInput.parentNode.insertBefore(wrap, this.startInput);
    wrap.appendChild(this.startInput);
    wrap.appendChild(this.endInput);
    this.wrap = wrap;

    // Field
    const field = document.createElement('div');
    field.className = 'gw-dp-field';
    field.setAttribute('tabindex', '0');
    field.setAttribute('role', 'button');
    field.innerHTML = `
      <i class="bi bi-calendar-range gw-dp-field-icon"></i>
      <span class="gw-dp-field-val"></span>
      <button type="button" class="gw-dp-field-clear" tabindex="-1">
        <i class="bi bi-x-circle-fill"></i>
      </button>`;
    wrap.appendChild(field);
    this.field    = field;
    this.fieldVal = field.querySelector('.gw-dp-field-val');
    this.clearBtn = field.querySelector('.gw-dp-field-clear');

    // Popup (appended to body to avoid overflow/transform clipping)
    const popup = document.createElement('div');
    popup.className = 'gw-dp-popup below';
    popup.style.minWidth = '580px';
    document.body.appendChild(popup);
    this.popup = popup;

    this._buildPopup();
    this._bindEvents();
  }

  _buildPopup() {
    this.popup.innerHTML = `
      <div class="gw-rp-months">
        <div class="gw-rp-month" data-idx="0">
          <div class="gw-dp-header">
            <button type="button" class="gw-dp-nav-btn" data-side="0" data-dir="-1"><i class="bi bi-chevron-left"></i></button>
            <span class="gw-dp-month-label"></span>
            <button type="button" class="gw-dp-nav-btn" data-side="0" data-dir="1"><i class="bi bi-chevron-right"></i></button>
          </div>
          <div class="gw-dp-weekdays">${WD_RU.map(w=>`<div class="gw-dp-wd">${w}</div>`).join('')}</div>
          <div class="gw-dp-days"></div>
        </div>
        <div class="gw-rp-divider"></div>
        <div class="gw-rp-month" data-idx="1">
          <div class="gw-dp-header">
            <button type="button" class="gw-dp-nav-btn" data-side="1" data-dir="-1"><i class="bi bi-chevron-left"></i></button>
            <span class="gw-dp-month-label"></span>
            <button type="button" class="gw-dp-nav-btn" data-side="1" data-dir="1"><i class="bi bi-chevron-right"></i></button>
          </div>
          <div class="gw-dp-weekdays">${WD_RU.map(w=>`<div class="gw-dp-wd">${w}</div>`).join('')}</div>
          <div class="gw-dp-days"></div>
        </div>
      </div>
      <div class="gw-rp-footer">
        <span class="gw-rp-selected-range" id="gw-rp-label">Выберите начальную дату</span>
        <button type="button" class="gw-dp-clear-btn">Очистить</button>
      </div>`;
  }

  _bindEvents() {
    this.field.addEventListener('click', e => {
      if (e.target.closest('.gw-dp-field-clear')) return;
      this._toggle();
    });
    this.field.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); this._toggle(); }
      if (e.key === 'Escape') this._close();
    });
    this.clearBtn.addEventListener('click', e => { e.stopPropagation(); this._clear(); });

    // Nav
    this.popup.querySelectorAll('.gw-dp-nav-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const side = +btn.dataset.side, dir = +btn.dataset.dir;
        this.viewMonth[side] += dir;
        if (this.viewMonth[side] > 11) { this.viewMonth[side] = 0;  this.viewYear[side]++; }
        if (this.viewMonth[side] < 0)  { this.viewMonth[side] = 11; this.viewYear[side]--; }
        this._renderCalendars();
      });
    });

    // Day clicks
    this.popup.querySelectorAll('.gw-dp-days').forEach(grid => {
      grid.addEventListener('click', e => {
        const btn = e.target.closest('.gw-dp-day');
        if (!btn) return;
        const d = new Date(+btn.dataset.ts);
        d.setHours(0, 0, 0, 0);
        this._selectDay(d);
      });
      grid.addEventListener('mouseover', e => {
        const btn = e.target.closest('.gw-dp-day');
        if (!btn) return;
        this.hoverDate = new Date(+btn.dataset.ts);
        this.hoverDate.setHours(0, 0, 0, 0);
        this._renderCalendars();
      });
      grid.addEventListener('mouseleave', () => {
        this.hoverDate = null;
        this._renderCalendars();
      });
    });

    // Clear
    this.popup.querySelector('.gw-dp-clear-btn').addEventListener('click', () => {
      this._clear(); this._close();
    });

    document.addEventListener('mousedown', this._onOutside = e => {
      if (!this.wrap.contains(e.target) && !this.popup.contains(e.target)) this._close();
    }, true);
  }

  _selectDay(date) {
    if (this.selecting === 'start' || !this.startDate || (this.endDate && date < this.startDate)) {
      this.startDate = date;
      this.endDate   = null;
      this.selecting = 'end';
    } else {
      if (date < this.startDate) {
        this.endDate   = this.startDate;
        this.startDate = date;
      } else {
        this.endDate = date;
      }
      this.selecting = null;
    }
    this._commit();
    this._render();
    this._renderCalendars();
    this._updateLabel();
    if (this.endDate) this._close();
  }

  _toggle() { this._open ? this._close() : this._openPopup(); }

  _openPopup() {
    this._open = true;
    this.field.classList.add('open');
    this.popup.classList.add('visible');
    this._positionPopup();
    this._renderCalendars();
    this._updateLabel();
    this._onScrollResize = () => this._positionPopup();
    window.addEventListener('scroll', this._onScrollResize, { passive: true, capture: true });
    window.addEventListener('resize', this._onScrollResize, { passive: true });
  }

  _close() {
    this._open = false;
    this.field.classList.remove('open');
    this.popup.classList.remove('visible');
    if (this._onScrollResize) {
      window.removeEventListener('scroll', this._onScrollResize, { capture: true });
      window.removeEventListener('resize', this._onScrollResize);
      this._onScrollResize = null;
    }
  }

  _positionPopup() {
    const rect = this.wrap.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const MARGIN = 8;
    const isMobile = vw < 580;

    // Popup natural width
    const naturalW = isMobile ? 300 : 580;
    const popupW = Math.min(naturalW, vw - MARGIN * 2);
    this.popup.style.maxWidth = (vw - MARGIN * 2) + 'px';

    // Horizontal: align with anchor left edge, clamp to viewport
    let left = rect.left;
    if (left + popupW > vw - MARGIN) left = vw - MARGIN - popupW;
    if (left < MARGIN) left = MARGIN;
    this.popup.style.left = left + 'px';

    // Vertical: prefer below, flip above if not enough space
    const spaceBelow = vh - rect.bottom - MARGIN;
    const spaceAbove = rect.top - MARGIN;
    if (spaceBelow >= 320 || spaceBelow >= spaceAbove) {
      this.popup.style.top = (rect.bottom + 6) + 'px';
      this.popup.style.bottom = 'auto';
    } else {
      this.popup.style.top = 'auto';
      this.popup.style.bottom = (vh - rect.top + 6) + 'px';
    }
  }

  _renderCalendars() {
    [0, 1].forEach(idx => {
      const y = this.viewYear[idx], m = this.viewMonth[idx];
      const col = this.popup.querySelectorAll('.gw-rp-month')[idx];
      col.querySelector('.gw-dp-month-label').textContent = `${MONTHS_RU[m]} ${y}`;

      const first    = startOfMonth(y, m);
      const firstDow = (first.getDay() + 6) % 7;
      const days     = daysInMonth(y, m);
      const today    = new Date(); today.setHours(0,0,0,0);

      // effective range for hover preview
      const rangeEnd = this.selecting === 'end' && this.hoverDate
        ? (this.hoverDate < this.startDate ? this.startDate : this.hoverDate)
        : this.endDate;
      const rangeStart = this.selecting === 'end' && this.hoverDate && this.hoverDate < this.startDate
        ? this.hoverDate : this.startDate;

      let html = '';
      for (let i = 0; i < firstDow; i++) {
        const prevDays = daysInMonth(y, m - 1 < 0 ? 11 : m - 1);
        const d = prevDays - firstDow + i + 1;
        const date = new Date(m === 0 ? y - 1 : y, m === 0 ? 11 : m - 1, d);
        html += this._dayHTML(date, rangeStart, rangeEnd, today, true);
      }
      for (let d = 1; d <= days; d++) {
        const date = new Date(y, m, d);
        html += this._dayHTML(date, rangeStart, rangeEnd, today, false);
      }
      const total = firstDow + days;
      const nextCells = (7 - (total % 7)) % 7;
      for (let d = 1; d <= nextCells; d++) {
        const date = new Date(m === 11 ? y + 1 : y, m === 11 ? 0 : m + 1, d);
        html += this._dayHTML(date, rangeStart, rangeEnd, today, true);
      }
      col.querySelector('.gw-dp-days').innerHTML = html;
    });
  }

  _dayHTML(date, rangeStart, rangeEnd, today, otherMonth) {
    const isStart = isSameDay(date, rangeStart);
    const isEnd   = isSameDay(date, rangeEnd);
    const inRange = rangeStart && rangeEnd && date > rangeStart && date < rangeEnd;
    const isTod   = isSameDay(date, today);
    let cls = 'gw-dp-day';
    if (otherMonth) cls += ' other-month';
    if (isStart)    cls += ' selected range-start';
    if (isEnd)      cls += ' selected range-end';
    if (inRange)    cls += ' in-range';
    if (isTod && !isStart && !isEnd) cls += ' today';
    return `<button type="button" class="${cls}" data-ts="${date.getTime()}">${date.getDate()}</button>`;
  }

  _updateLabel() {
    const lbl = this.popup.querySelector('#gw-rp-label');
    if (!lbl) return;
    if (!this.startDate) { lbl.textContent = 'Выберите начальную дату'; return; }
    if (!this.endDate)   { lbl.textContent = `С ${formatDisplay(this.startDate, false)} → выберите конец`; return; }
    lbl.textContent = `${formatDisplay(this.startDate, false)} — ${formatDisplay(this.endDate, false)}`;
  }

  _clear() {
    this.startDate = null; this.endDate = null; this.selecting = 'start';
    this._commit(); this._render();
    if (this._open) { this._renderCalendars(); this._updateLabel(); }
  }

  _commit() {
    this.startInput.value = toISO(this.startDate, false);
    this.endInput.value   = toISO(this.endDate, false);
    this.startInput.dispatchEvent(new Event('change', { bubbles: true }));
    this.endInput.dispatchEvent(new Event('change', { bubbles: true }));
    if (this.onChange) this.onChange(this.startDate, this.endDate,
      toISO(this.startDate, false), toISO(this.endDate, false));
  }

  _render() {
    const hasVal = !!(this.startDate && this.endDate);
    const hasStart = !!this.startDate;
    if (hasVal) {
      this.fieldVal.textContent = `${formatDisplay(this.startDate, false)} — ${formatDisplay(this.endDate, false)}`;
      this.fieldVal.classList.remove('gw-dp-field-placeholder');
    } else if (hasStart) {
      this.fieldVal.textContent = `С ${formatDisplay(this.startDate, false)}...`;
      this.fieldVal.classList.remove('gw-dp-field-placeholder');
    } else {
      this.fieldVal.textContent = this.placeholder;
      this.fieldVal.classList.add('gw-dp-field-placeholder');
    }
    this.clearBtn.classList.toggle('visible', hasStart);
  }

  destroy() {
    document.removeEventListener('mousedown', this._onOutside, true);
    this.popup.remove();
    [this.startInput, this.endInput].forEach(inp => inp.style.display = '');
    this.wrap.replaceWith(this.startInput);
  }
}


/* ═══════════════════ Авто-инициализация ═══════════════════ */
function initGWDatePickers(root = document) {
  root.querySelectorAll('input[type="datetime-local"], input[type="date"]').forEach(el => {
    if (el._gwDp || el._gwRp || el.closest('[data-no-datepicker]') || el.dataset.noDatepicker !== undefined) return;
    new GWDatePicker(el);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => initGWDatePickers());
} else {
  initGWDatePickers();
}

// Expose globally for manual use
window.GWDatePicker  = GWDatePicker;
window.GWRangePicker = GWRangePicker;
window.initGWDatePickers = initGWDatePickers;
