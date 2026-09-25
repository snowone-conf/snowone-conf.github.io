# snowone.ru

Сайт конференции [SnowOne](https://snowone.ru/) — Content-First Java-конференции из Сибири (JUGNsk).

Сейчас в репозитории лежит **статическая копия** текущего сайта: он сгенерирован платформой JUG Ru Group (Next.js), а здесь снят без смысловых изменений. Следующий шаг — пересборка на [Hugo](https://gohugo.io/): докладчики, доклады, расписание и партнёры будут храниться как Markdown/YAML.

## Структура
| Путь | Что это |
|---|---|
| `snapshot/` | копия сайта, публикуется в GitHub Pages как есть |
| `tools/mirror.py` | скрипт, который снимает копию (только стандартная библиотека Python; Pillow — по желанию, для сжатия фото) |
| `docs/audit.md` | что на сайте зависело от старой системы и что с этим делать |
| `docs/snapshot-manifest.json` | список страниц, редиректов и ошибок последнего снятия |
| `.github/workflows/pages.yml` | деплой `snapshot/` в GitHub Pages при пуше в `main` |

## Посмотреть локально
```sh
cd snapshot && python3 -m http.server 8080
# открыть http://localhost:8080/
```

## Снять копию заново
```sh
pip install pillow        # по желанию: без него фото не будут уменьшены
rm -rf snapshot && python3 tools/mirror.py snapshot
```

## Публикация в GitHub Pages
1. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. Смержить в `main` — workflow `Deploy to GitHub Pages` опубликует `snapshot/`.

Снапшот использует корневые пути (`/_next/…`), поэтому работает **только из корня домена**:
- `https://<org>.github.io/` — для этого репозиторий должен называться `<org>.github.io`;
- или свой домен (`snowone.ru`) через `CNAME`.

Адрес проектного сайта вида `https://<org>.github.io/<repo>/` снапшоту не подходит. Hugo-версия этого ограничения иметь не будет: там будет `baseURL`.
