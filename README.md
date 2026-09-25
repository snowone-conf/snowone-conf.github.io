# snowone.ru

Сайт конференции [SnowOne](https://snowone.ru/) — Content-First Java-конференции из Сибири (JUGNsk).

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
| `make test` | тесты служебных скриптов |

## Где что лежит

| Путь | Что это |
|---|---|
| `data/conference.yaml` | **данные сезона**: название, даты, площадка, статистика, текст «О конференции», дни и треки (залы), контакты, соцсети |
| `data/committee.yaml` | программный комитет: список id персон |
| `content/talks/<id>/index.ru.md` | доклады: название, докладчики, время, зал, слайды; текст — описание |
| `content/persons/<id>/index.ru.md` + `photo.*` | докладчики, ведущие, члены ПК; текст — биография |
| `content/partners/<slug>/index.ru.md` + `logo.*` | партнёры: уровень (`tier`), порядок (`weight`), ссылки |
| `content/<страница>/index.ru.md` | текстовые страницы: CoC, правила, юридические документы, CFP, «О нас» |
| `hugo.yaml` | настройки сайта: меню, билеты, CFP, подписка, аналитика |
| `layouts/` | шаблоны страниц (разметка и классы прежнего сайта) |
| `assets/css/platform/` | стили прежнего сайта; свои правки — в `assets/css/site.css` |
| `assets/js/site.js` | меню, «Еще», баннер cookies |
| `static/archive/` | **замороженный архив прошлых лет** (готовый HTML прежнего сайта, не редактируется) |
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

**Добавить партнёра:** создайте `content/partners/<slug>/index.ru.md` по образцу существующих и положите рядом `logo.svg`. `tier` — `general` | `gold` | `regular`.

**Слайды:** PDF хранятся в GitHub Releases, по релизу на год (`slides-2026`, …). Загрузите файл в релиз и укажите ссылку в поле `slides` доклада.

**Билеты (Timepad):** в `hugo.yaml` укажите `params.tickets.mode: link` и `params.tickets.url` — в шапке и на главной появится кнопка «Купить билет».

**CFP:** `params.cfp.open` включает и выключает кнопки «Стать спикером» и «Подать заявку», а `params.cfp.url` задаёт ссылку на форму.

**Своя аналитика:** номер счётчика Яндекс Метрики — в `params.yandexMetrikaId`. Счётчик подключится на всех страницах, включая архив, и появится баннер согласия на cookies.

**Статус сезона:** `status` в `data/conference.yaml` (`announced` | `open` | `finished`). При `finished` на главной показывается плашка «Мероприятие завершилось».

## Служебное (переезд со старой платформы)

| Путь | Что это |
|---|---|
| `tools/mirror.py`, `tools/postprocess.py` | снятие копии и отвязка от инфраструктуры прежней системы |
| `tools/import_nextdata.py` | разовый перенос данных сезона 2026 из копии в `content/` и `data/` |
| `tools/freeze_archive.py` | копирует архив из `snapshot/` в `static/` |
| `tools/check_refs.py` | проверка целостности контента (запускается в CI) |
| `tools/import_cfp.py`, `tools/cfp_mapping.yaml` | импорт заявок CFP из Яндекс Форм |
| `docs/slides.json`, workflow `Slides to Releases` | перенос слайдов в GitHub Releases |

Полная копия старого сайта (`snapshot/`) из `main` удалена: для сборки она не нужна. Она сохранена в ветке [`source-snapshot`](../../tree/source-snapshot). Скрипты переноса читают её из папки `snapshot/`: чтобы запустить их снова, достаньте копию из ветки (`git archive origin/source-snapshot snapshot | tar -x` — так файлы не попадут в индекс) или снимите заново (`make snapshot`).

## Публикация

Workflow `.github/workflows/pages.yml`:
- на каждый PR проверяет контент и собирает сайт;
- на пуш в `main` дополнительно публикует сайт в GitHub Pages (Settings → Pages → Source: GitHub Actions).

Сайт доступен по адресу https://snowone-conf.github.io/. Чтобы подключить домен `snowone.ru`, положите файл `static/CNAME` с текстом `snowone.ru`, поменяйте `baseURL` в `hugo.yaml` и настройте DNS.
