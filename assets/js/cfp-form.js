// Форма заявки на доклад: проверка полей, уменьшение фото, капча ALTCHA и отправка в сервис cfp-function.
// Поля описаны в docs/schema.md репозитория cfp-function; data-path у поля — его путь в JSON заявки.

const PHOTO_MAX_SIDE = 1200;
const PHOTO_MAX_BYTES = 10 * 1024 * 1024;

const form = document.querySelector('[data-cfp-form]');
if (form) setup(form);

function setup(form) {
  const api = form.dataset.api.replace(/\/$/, '');
  const photos = {}; // путь поля фото → data URL уменьшенного JPEG
  const status = form.querySelector('[data-status]');
  const submit = form.querySelector('[type=submit]');
  const formError = form.querySelector('[data-form-error]');

  // Счётчики символов у длинных полей
  form.querySelectorAll('[data-counter]').forEach((counter) => {
    const input = document.getElementById(counter.dataset.counter);
    const update = () => {
      const n = [...input.value.trim()].length;
      const min = Number(input.getAttribute('minlength') || 0);
      const max = Number(input.getAttribute('maxlength'));
      counter.textContent = min && n < min ? `${n} из ${min}–${max}` : `${n} из ${max}`;
    };
    input.addEventListener('input', update);
    update();
  });

  // «Другое» → обязательное пояснение к формату
  const format = field('talk.format');
  const noteBlock = form.querySelector('[data-format-note]');
  const syncFormat = () => {
    const other = format.value === 'other';
    noteBlock.hidden = !other;
    field('talk.formatNote').required = other;
  };
  format.addEventListener('change', syncFormat);
  syncFormat();

  // Второй спикер
  const second = form.querySelector('[data-speaker="1"]');
  const addSpeaker = form.querySelector('[data-add-speaker]');
  const setSecond = (on) => {
    second.hidden = !on;
    second.disabled = !on;
    addSpeaker.hidden = on;
    if (on) second.querySelector('input').focus();
  };
  addSpeaker.addEventListener('click', () => setSecond(true));
  second.querySelector('[data-remove-speaker]').addEventListener('click', () => {
    setSecond(false);
    addSpeaker.focus();
  });

  // Фото: уменьшаем в браузере и показываем превью
  form.querySelectorAll('input[type=file]').forEach((input) => {
    input.addEventListener('change', async () => {
      const path = input.dataset.path;
      const preview = form.querySelector(`[data-preview="${path}"]`);
      delete photos[path];
      preview.hidden = true;
      clearError(path);
      const file = input.files[0];
      if (!file) return;
      if (!['image/jpeg', 'image/png'].includes(file.type)) {
        showError(path, 'Фото должно быть в формате JPEG или PNG.');
        return;
      }
      if (file.size > PHOTO_MAX_BYTES) {
        showError(path, 'Фото больше 10 МБ.');
        return;
      }
      try {
        photos[path] = await shrink(file);
        preview.src = photos[path];
        preview.hidden = false;
      } catch {
        showError(path, 'Не удалось открыть фото. Попробуйте другой файл.');
      }
    });
  });

  // Ошибка у поля исчезает, как только его начали править
  form.addEventListener('input', (e) => {
    if (e.target.dataset.path) clearError(e.target.dataset.path);
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    formError.hidden = true;
    if (!validate()) return;
    submit.disabled = true;
    try {
      status.textContent = 'Проверяем, что вы не робот… Это займёт несколько секунд.';
      const altcha = await solveAltcha(api);
      status.textContent = 'Отправляем заявку…';
      const resp = await fetch(`${api}/api/applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(collect(altcha)),
      });
      const body = await resp.json().catch(() => ({}));
      if (resp.ok) {
        done(body.id);
        return;
      }
      if (body.errors) {
        showServerErrors(body.errors);
      } else {
        showFormError('Сервис заявок не ответил. Попробуйте ещё раз через несколько минут.');
      }
    } catch {
      showFormError('Не удалось связаться с сервисом заявок. Проверьте интернет и попробуйте ещё раз.');
    } finally {
      submit.disabled = false;
      status.textContent = '';
    }
  });

  function field(path) {
    return form.querySelector(`[data-path="${path}"]`);
  }

  function activeInputs() {
    return [...form.querySelectorAll('[data-path]')].filter((el) => !el.closest('fieldset:disabled') && !el.closest('[hidden]'));
  }

  // Проверки браузера (обязательность, длина, тип) плюс фото; первое неверное поле получает фокус
  function validate() {
    let first = null;
    for (const el of activeInputs()) {
      const path = el.dataset.path;
      let message = '';
      if (el.type === 'file') {
        if (!photos[path]) message = 'Приложите фото.';
      } else if (el.type === 'checkbox') {
        if (!el.checked) message = 'Без этого согласия заявку принять нельзя.';
      } else {
        message = lengthMessage(el) || (el.validity.typeMismatch ? typeMessage(el) : '');
      }
      if (path.endsWith('.pastTalks') && !message) message = pastTalksMessage(el.value);
      if (message) {
        showError(path, message);
        first ??= el;
      }
    }
    if (first) {
      first.focus();
      showFormError('Проверьте поля, отмеченные выше.');
    }
    return !first;
  }

  function lengthMessage(el) {
    const n = [...el.value.trim()].length;
    const min = Number(el.getAttribute('minlength') || 0);
    const max = Number(el.getAttribute('maxlength') || Infinity);
    if (el.required && n === 0) return el.tagName === 'SELECT' ? 'Выберите вариант.' : 'Заполните поле.';
    if (n > 0 && n < min) return `Не короче ${min} символов, сейчас ${n}.`;
    if (n > max) return `Не длиннее ${max} символов, сейчас ${n}.`;
    return '';
  }

  function typeMessage(el) {
    if (el.type === 'email') return 'Проверьте адрес e-mail.';
    if (el.type === 'url') return 'Ссылка должна начинаться с http:// или https://.';
    return 'Проверьте значение.';
  }

  function pastTalksMessage(value) {
    const lines = value.split('\n').map((s) => s.trim()).filter(Boolean);
    if (lines.length > 3) return 'Не больше трёх ссылок.';
    if (lines.some((s) => !/^https?:\/\/\S+$/i.test(s))) return 'Каждая ссылка должна начинаться с http:// или https://.';
    return '';
  }

  // JSON заявки по data-path полей: talk.title → {talk: {title}}, speakers[1].name → {speakers: [, {name}]}
  function collect(altcha) {
    const data = { talk: {}, speakers: [{}], consents: { textVersion: form.dataset.consentVersion } };
    for (const el of activeInputs()) {
      const path = el.dataset.path;
      let value;
      if (el.type === 'file') value = { data: photos[path] };
      else if (el.type === 'checkbox') value = el.checked;
      else value = el.value.trim();
      const m = path.match(/^speakers\[(\d)\]\.(\w+)$/);
      if (m) {
        data.speakers[m[1]] ??= {};
        data.speakers[m[1]][m[2]] = value;
      } else {
        const [group, key] = path.includes('.') ? path.split('.') : [null, path];
        if (group) data[group][key] = value;
        else data[key] = value;
      }
    }
    data.trap = form.querySelector('[data-trap]').value;
    data.altcha = altcha;
    return data;
  }

  function showServerErrors(errors) {
    let first = null;
    for (const [path, message] of Object.entries(errors)) {
      if (path === 'form' || path === 'altcha' || path === 'speakers' || !field(path)) {
        showFormError(message);
      } else {
        showError(path, message);
        first ??= field(path);
      }
    }
    first?.focus();
  }

  function showError(path, message) {
    const box = form.querySelector(`[data-field="${path}"]`);
    const error = box?.querySelector('.CfpForm__error');
    if (!error) return showFormError(message);
    error.textContent = message;
    error.hidden = false;
    box.classList.add('CfpForm__field_invalid');
    field(path)?.setAttribute('aria-invalid', 'true');
  }

  function clearError(path) {
    const box = form.querySelector(`[data-field="${path}"]`);
    if (!box) return;
    box.querySelector('.CfpForm__error').hidden = true;
    box.classList.remove('CfpForm__field_invalid');
    field(path)?.removeAttribute('aria-invalid');
  }

  function showFormError(message) {
    formError.textContent = message;
    formError.hidden = false;
  }

  function done(id) {
    const box = document.querySelector('[data-done]');
    box.querySelector('[data-done-id]').textContent = id;
    form.hidden = true;
    document.querySelector('.CfpForm__intro').hidden = true;
    box.hidden = false;
    box.focus();
    box.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// Уменьшает фото до PHOTO_MAX_SIDE по длинной стороне и перекодирует в JPEG (data URL)
async function shrink(file) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, PHOTO_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#fff'; // прозрачный PNG на белом фоне
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return canvas.toDataURL('image/jpeg', 0.88);
}

// Капча ALTCHA: подбираем число n, при котором SHA-256(salt + n) равен challenge.
// Перебор идёт пачками, чтобы страница не подвисала.
async function solveAltcha(api) {
  const resp = await fetch(`${api}/api/altcha`, { cache: 'no-store' });
  if (!resp.ok) throw new Error('altcha');
  const c = await resp.json();
  const encoder = new TextEncoder();
  const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
  const BATCH = 500;
  for (let start = 0; start <= c.maxnumber; start += BATCH) {
    const numbers = [];
    for (let n = start; n < start + BATCH && n <= c.maxnumber; n++) numbers.push(n);
    const hashes = await Promise.all(numbers.map((n) => crypto.subtle.digest('SHA-256', encoder.encode(c.salt + n))));
    const found = hashes.findIndex((h) => hex(h) === c.challenge);
    if (found >= 0) {
      const payload = { algorithm: c.algorithm, challenge: c.challenge, number: numbers[found], salt: c.salt, signature: c.signature };
      return btoa(JSON.stringify(payload));
    }
  }
  throw new Error('altcha');
}
