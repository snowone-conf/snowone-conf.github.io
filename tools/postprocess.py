#!/usr/bin/env python3
"""Постобработка снапшота snowone.ru: отвязывает копию от инфраструктуры JUG Ru.

Шаг идемпотентный: его можно запускать повторно на уже обработанном снапшоте.
mirror.py вызывает его автоматически; вручную: python3 tools/postprocess.py [snapshot]

Что делает:
  1. Отключает аналитику JUG Ru: GTM и Яндекс Метрику (патч _app + чистка
     marketingTools в данных страниц) и трекер ringostar.jugru.team.
  2. Подключает к каждой странице /analytics.js и /overrides.css из overrides/.
     analytics.js — место для своей аналитики, overrides.css — косметика.
  3. Заменяет ссылки на сервисы JUG Ru: бот поддержки → t.me/jugnsk,
     CFP JUG Ru → письмо организаторам.
  4. Переносит слайды (PDF) в GitHub Releases: один релиз на год
     (slides-<год>). Ссылки переписываются на release-ассеты, а список
     файлов пишется в docs/slides.json — по нему workflow slides-release.yml
     загружает файлы в релизы.
"""
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "snapshot"))
OVERRIDES = os.path.join(ROOT, "overrides")
SLIDES_JSON = os.path.join(ROOT, "docs", "slides.json")

REPO = "snowone-conf/snowone-conf.github.io"
CURRENT_YEAR = "2026"   # сезон, к которому относятся страницы вне /archive/<год>/
CONTACT_EMAIL = "support@snowone.ru"

TEXT_EXT = (".html", ".json", ".js")

# --- 3. Ссылки JUG Ru (простая замена строк во всех текстовых файлах) ---------
CFP_MAILTO = f"mailto:{CONTACT_EMAIL}?subject=SnowOne%20CFP"
REPLACEMENTS = [
    ("https://t.me/JUGConfSupport_bot/", "https://t.me/jugnsk"),
    ("https://t.me/JUGConfSupport_bot", "https://t.me/jugnsk"),
    ("@JUGConfSupport_bot", "@jugnsk"),
    ("https://t.me/JUGruSupport/", "https://t.me/jugnsk"),
    ("https://callforpapers.jugru.org/jug-ru-group/snowone-2026#step1", CFP_MAILTO),
]

# --- 1. Патчи JS-бандла (регулярки; каждая должна сработать ровно один раз) ---
JS_PATCHES = [
    # (название, регулярка, замена, маркер уже применённого патча)
    # _app: скрипты GTM и Метрики грузятся при флаге t (согласие на cookies).
    # Делаем его всегда ложным — внешние скрипты не загружаются.
    ("gtm+metrika scripts",
     re.compile(r"(let \w=\(\)=>\{let\{marketingTools:\w\}=\(0,\w\.Mq\)\(\),\w=)\(0,\w\.Z\)\(\);"),
     r"\1!1;", re.compile(r"let \w=\(\)=>\{let\{marketingTools:\w\}=\(0,\w\.Mq\)\(\),\w=!1;")),
    # _app: <noscript><iframe GTM> — компонент возвращает null.
    ("gtm noscript",
     re.compile(r"(?<![\w$])(\w)=\(\)=>\{(let\{marketingTools:\w\}=\(0,\w\.Mq\)\(\);return\(0,\w\.jsx\)\(\"noscript\")"),
     r"\1=()=>null,_gtmNoscript=()=>{\2", re.compile(r"=\(\)=>null,_gtmNoscript=")),
    # AnalyticsProvider: не загружаем трекер ringostar (и fingerprintjs).
    ("ringostar tracker",
     re.compile(r"\(async\(\)=>\{let (\w)=await (\w)\.e\(4346\)"),
     r"(async()=>{return;let \1=await \2.e(4346)", re.compile(r"\(async\(\)=>\{return;let \w=await \w\.e\(4346\)")),
]

# Серверно отрендеренные куски аналитики в HTML.
HTML_REMOVE = [
    re.compile(r'<script id="google-analytics"[^>]*>.*?</script>', re.S),
    re.compile(r'<script id="yandex-analytics"[^>]*>.*?</script>', re.S),
    re.compile(r'<noscript><iframe src="https://www\.googletagmanager\.com/[^"]*"[^>]*></iframe></noscript>'),
]
INJECT_MARK = "<!-- snowone-overrides -->"
INJECT = (INJECT_MARK + '<link rel="stylesheet" href="/overrides.css">'
          '<script src="/analytics.js" defer></script>')

RE_NEXTDATA = re.compile(r'(<script id="__NEXT_DATA__" type="application/json">)(.*?)(</script>)', re.S)
RE_PDF = re.compile(r"https://(?:squidex\.jugru\.team/api/assets|cdn\.jugru\.org)/[^\"'?\\\s<>]+\.pdf")
RE_YEAR = re.compile(r"^archive/(\d{4})/")


def walk(ext=TEXT_EXT):
    for root, _, files in os.walk(OUT):
        for name in files:
            if name.endswith(ext):
                yield os.path.join(root, name)


def rel(f):
    return os.path.relpath(f, OUT).replace(os.sep, "/")


def read(f):
    with open(f, encoding="utf-8") as fh:
        return fh.read()


def write(f, s):
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(s)


def clean_data(obj):
    """Убирает из данных страницы счётчики и список конференций JUG Ru."""
    if isinstance(obj, dict):
        mt = obj.get("marketingTools")
        if isinstance(mt, dict):
            for k in ("gtmId", "ymId", "subscriptionId"):
                if k in mt:
                    mt[k] = None
        if isinstance(obj.get("projects"), list):
            obj["projects"] = []
        for v in obj.values():
            clean_data(v)
    elif isinstance(obj, list):
        for v in obj:
            clean_data(v)
    return obj


def patch_js():
    applied = {name: 0 for name, *_ in JS_PATCHES}
    present = dict(applied)
    for f in walk((".js",)):
        s = read(f)
        s2 = s
        for name, rx, repl, done in JS_PATCHES:
            s2, n = rx.subn(repl, s2)
            applied[name] += n
            present[name] += bool(done.search(s2))
        if s2 != s:
            write(f, s2)
    for name in applied:
        if not present[name]:
            sys.exit(f"JS-патч «{name}» не применился — бандл изменился, проверьте tools/postprocess.py")
    print("js patches applied:", applied)


def slide_year(page):
    m = RE_YEAR.match(page)
    return m.group(1) if m else CURRENT_YEAR


def collect_slides():
    """URL слайда -> год. Страницы докладов важнее персон: на странице
    докладчика бывают доклады разных лет."""
    found = {}
    for f in walk((".html",)):
        page = rel(f)
        prio = 0 if "/talks/" in "/" + page else 1
        for url in RE_PDF.findall(read(f)):
            cand = (prio, slide_year(page))
            if url not in found or cand < found[url]:
                found[url] = cand
    return {u: y for u, (_, y) in found.items()}


def asset_name(url, taken):
    base = re.sub(r"[^A-Za-z0-9._-]", "-", url.rsplit("/", 1)[1])
    name = base
    if name in taken:
        uid = url.rstrip("/").split("/")[-2][:8]
        name = f"{uid}-{base}"
    taken.add(name)
    return name


def load_slides():
    if os.path.exists(SLIDES_JSON):
        with open(SLIDES_JSON, encoding="utf-8") as fh:
            return json.load(fh)
    return []


def slides_manifest():
    slides = load_slides()
    known = {s["source"] for s in slides}
    taken = {}
    for s in slides:
        taken.setdefault(s["year"], set()).add(s["name"])
    for url, year in sorted(collect_slides().items()):
        if url in known:
            continue
        name = asset_name(url, taken.setdefault(year, set()))
        slides.append({"year": year, "name": name, "source": url,
                       "url": f"https://github.com/{REPO}/releases/download/slides-{year}/{name}"})
    slides.sort(key=lambda s: (s["year"], s["name"]))
    os.makedirs(os.path.dirname(SLIDES_JSON), exist_ok=True)
    with open(SLIDES_JSON, "w", encoding="utf-8") as fh:
        json.dump(slides, fh, ensure_ascii=False, indent=1)
    print(f"slides: {len(slides)} файлов, релизы: {sorted({s['year'] for s in slides})}")
    return {s["source"]: s["url"] for s in slides}


def rewrite_text(slide_map):
    n = 0
    for f in walk():
        s = read(f)
        s2 = s
        for old, new in REPLACEMENTS:
            s2 = s2.replace(old, new)
        s2 = RE_PDF.sub(lambda m: slide_map.get(m.group(0), m.group(0)), s2)
        if f.endswith(".html"):
            for rx in HTML_REMOVE:
                s2 = rx.sub("", s2)
            s2 = RE_NEXTDATA.sub(lambda m: m.group(1) + json.dumps(
                clean_data(json.loads(m.group(2))), ensure_ascii=False, separators=(",", ":")) + m.group(3), s2)
            if INJECT_MARK not in s2:
                s2 = s2.replace("</head>", INJECT + "</head>", 1)
        elif f.endswith(".json") and "/_next/data/" in "/" + rel(f):
            s2 = json.dumps(clean_data(json.loads(s2)), ensure_ascii=False, separators=(",", ":"))
        if s2 != s:
            n += 1
            write(f, s2)
    print(f"rewrote {n} files")


def copy_overrides():
    for name in os.listdir(OVERRIDES):
        shutil.copy(os.path.join(OVERRIDES, name), os.path.join(OUT, name))


def main():
    patch_js()
    rewrite_text(slides_manifest())
    copy_overrides()


if __name__ == "__main__":
    main()
