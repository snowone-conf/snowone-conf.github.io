# snowone.ru

Сайт конференции [SnowOne](https://snowone.ru/) — Content-First конференции из Сибири (JUGNsk).

Сайт статический и собирается [Hugo](https://gohugo.io/) из Markdown/YAML-файлов этого репозитория. Он публикуется в GitHub Pages на каждый пуш в `main`. Внешний вид повторяет прежний сайт, который работал на прежней системе: в шаблонах используются её стили.

## Быстрый старт

Нужны:
- **Hugo extended** той версии, что указана в [`.hugo-version`](.hugo-version):
  - macOS: `brew install hugo`;
  - Windows: `winget install Hugo.Hugo.Extended`;
  - Linux: `.deb` со [страницы релизов](https://github.com/gohugoio/hugo/releases) или `pip install hugo`.
- **Python 3 + PyYAML** (`pip install pyyaml`) — только для проверок и служебных скриптов.

```sh
git clone https://github.com/snowone-conf/snowone-conf.github.io.git
cd snowone-conf.github.io
make serve          # или: hugo server -D
# открыть http://localhost:1313 — страница обновляется при сохранении файлов
```

Перед пушем полезно запустить `make check`: он делает те же проверки, что и CI.

| Команда | Что делает |
|---|---|
| `make serve` | локальный сервер с live-reload (черновики `draft: true` тоже видны) |
| `make build` | сборка сайта в `public/` |
| `make check` | проверка ссылок между докладами и персонами и строгая сборка (как в CI) |
| `make import-cfp FILE=…` | черновики докладов из выгрузки Яндекс Форм |
| `make freeze-season` | заморозить текущий сезон в `static/archive/<год>/` |
| `make test` | тесты служебных скриптов |

## Где что лежит

| Путь | Что это |
|---|---|
| `data/conference.yaml` | **данные сезона**: название, даты, площадка, статистика, текст «О конференции», дни и треки (залы), контакты, соцсети |
| `data/committee.yaml` | программный комитет: список id персон |
| `content/talks/<id>/index.ru.md` | доклады: название, докладчики, время, зал, слайды; текст — описание |
| `content/persons/<id>/index.ru.md` + `photo.*` | докладчики, ведущие, члены ПК; текст — биография |
| `content/partners/<slug>/index.ru.md` + `logo.*` | партнёры: уровень (`tier`), порядок (`weight`), ссылки |
| `content/<страница>/index.ru.md` | текстовые страницы: CoC, правила (пока скрыты), CFP, «О нас». Юридические документы сезона 2026 — только в архиве `/archive/2026/` |
| `hugo.yaml` | настройки сайта: меню, билеты, CFP, аналитика |
| `layouts/` | шаблоны страниц (разметка и классы прежнего сайта) |
| `assets/css/platform/` | стили прежнего сайта; свои правки — в `assets/css/site.css` |
| `assets/js/site.js` | меню, «Еще», баннер cookies |
| `static/archive/<год>/` | **замороженный архив прошлых лет** (готовый HTML, не редактируется): 2025 — страницы прежней системы, 2026 и дальше — снимки этого сайта |
| `data/archive.yaml` | список сезонов на странице `/archive/` |
| `index.*.md` рядом с `index.ru.md` | английская версия (`index.en.md`). Пока выключена: `disableLanguages` в `hugo.yaml` |

## Типовые задачи

**Добавить докладчика:**
```sh
hugo new persons/ivan-ivanov/index.ru.md   # положите фото рядом: content/persons/ivan-ivanov/photo.jpg
```

**Добавить доклад:**
```sh
hugo new talks/my-talk/index.ru.md
```
В поле `speakers` перечислите имена папок докладчиков (`ivan-ivanov`). Время указывается новосибирское, с `+07:00`. `day` и `track` — номера дня и зала из `data/conference.yaml`. Пока стоит `draft: true`, доклад виден только в `make serve`.

**Перенести заявки из CFP (Яндекс Формы):** выгрузите ответы формы в `.xlsx` или `.csv` и выполните
```sh
make import-cfp FILE=~/Downloads/export.xlsx              # все ответы
make import-cfp FILE=export.xlsx ARGS="--only 12,15"      # только принятые (номера ответов)
```
Скрипт создаст черновики (`draft: true`) докладов и докладчиков и скачает фото по ссылкам из формы. Уже существующие файлы он не трогает. E-mail, телефоны и комментарии для ПК в контент не попадают. Если вопросы в форме называются иначе, поправьте `tools/cfp_mapping.yaml`. Саму выгрузку в репозиторий не коммитьте: `*.xlsx` и `*.csv` в `.gitignore`. Для `.xlsx` нужен `pip install openpyxl`.

**Публикация из CFP (сезон 2027):** заявки приходят с формы `/callforpapers/apply/` в сервис `cfp-function` и становятся карточками Trello. Публикуют их две колонки, в любом порядке:
- **«Опубликовали спикера ⚡»** — PR только со страницей спикера (поле `season` у персоны): спикер появляется на главной и в «Спикерах», на его странице — «Описание выступления появится здесь позже». Спикеру, который уже выступал, в страницу дописывается только `season`;
- **«Опубликовали доклад ⚡»** — PR со страницей выступления (без `draft` и без расписания) и со спикером, если его ещё нет на сайте. Открытый PR только со спикером при этом закрывается: спикер входит в новый PR.

Колонки запускают workflow **CFP: публикация из карточки** (`.github/workflows/cfp-accept.yml`, скрипт `tools/cfp_from_trello.py`), ветки — `cfp/<номер заявки>-speaker` и `cfp/<номер заявки>-talk`. Ссылка на PR приходит комментарием в карточку и сообщением в чат ПК. Если делать нечего (PR уже есть, доклад уже на сайте, карточку перенесли не туда), workflow ничего не меняет, а объясняет в чате и в карточке, что произошло и как исправить. Пока PR открыт, правка описания карточки пересобирает его; после слияния правки — обычным PR. Новое фото подхватывает только ручной запуск с «пересоздать».
- Ручной запуск: Actions → «CFP: публикация из карточки» → Run workflow (карточка, режим, «пересоздать»).
- Выступление без расписания допустимо; `day`, `start`, `end`, `track` добавляются позже, все вместе.
- Нужны секреты `TRELLO_KEY`, `TRELLO_TOKEN`, `EVENTS_SECRET` и переменная `CFP_SERVICE_URL` (Settings → Secrets and variables → Actions).

**Добавить партнёра:** создайте `content/partners/<slug>/index.ru.md` по образцу существующих и положите рядом `logo.svg`. `tier` — `general` | `gold` | `regular`.

**Слайды:** PDF хранятся в GitHub Releases, по релизу на год (`slides-2026`, …). Загрузите файл в релиз и укажите ссылку в поле `slides` доклада.

**Билеты (Timepad):** в `hugo.yaml` укажите `params.tickets.mode: link` и `params.tickets.url` — в шапке и на главной появится кнопка «Купить билет».

**CFP:** `params.cfp.open` включает и выключает приём заявок целиком: ссылку «Стать спикером» в шапке, кнопку «Подать заявку» и саму форму `/callforpapers/apply/` (при `false` её нет и по прямому адресу — страницу создаёт `content/callforpapers/_content.gotmpl` только при открытом приёме). Текст согласия — `/callforpapers/consent/`; при его правке поднимите `params.cfp.consentVersion`.

**Своя аналитика:** номер счётчика Яндекс Метрики — в `params.yandexMetrikaId`. Счётчик подключится на всех страницах, включая архив, и появится баннер согласия на cookies.

**Статус сезона:** `status` в `data/conference.yaml` (`announced` | `open` | `finished`). При `finished` на главной показывается плашка «Мероприятие завершилось».

## Служебные скрипты

| Путь | Что это |
|---|---|
| `tools/check_refs.py` | проверка целостности контента (запускается в CI) |
| `tools/import_cfp.py`, `tools/cfp_mapping.yaml` | импорт заявок CFP из Яндекс Форм |
| `tools/cfp_from_trello.py`, workflow `CFP: публикация из карточки` | страницы спикера и выступления из карточки Trello, PR к ревью |
| `docs/slides.json`, workflow `Slides to Releases` | загрузка слайдов в GitHub Releases |

Архив прошлых лет в `static/archive/` — готовые страницы прежнего сайта, их не нужно редактировать. Копия прежнего сайта сохранена в ветке [`source-snapshot`](../../tree/source-snapshot).

## Публикация

Workflow `.github/workflows/pages.yml`:
- на каждый PR проверяет контент и собирает сайт;
- на пуш в `main` дополнительно публикует сайт в GitHub Pages (Settings → Pages → Source: GitHub Actions).

Сайт доступен по адресу https://snowone-conf.github.io/. Чтобы подключить домен `snowone.ru`, положите файл `static/CNAME` с текстом `snowone.ru`, поменяйте `baseURL` в `hugo.yaml` и настройте DNS.

**Закрыть сезон и начать следующий:** когда сайт сезона больше не будет меняться, выполните `make freeze-season` — Hugo соберёт сайт, а скрипт скопирует все страницы с CSS, JS и картинками в `static/archive/<год>/` (год — `season` из `data/conference.yaml`) и перепишет ссылки на `/archive/<год>/…`; список сезонов тоже замораживается — в `/archive/<год>/archive/`. Добавьте сезон в начало `data/archive.yaml` — он появится на странице «Архив». После этого основной сайт можно менять под новый сезон: архив от шаблонов и данных уже не зависит.
