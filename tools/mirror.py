#!/usr/bin/env python3
"""Снимает статическую копию snowone.ru (Next.js-сборка) в каталог snapshot/.

Что делает:
  * обходит все страницы сайта (sitemap + ссылки со страниц), сохраняет HTML
    в виде <path>/index.html, для редиректов пишет HTML-заглушки;
  * скачивает ассеты Next.js (включая лениво подгружаемые чанки из webpack
    runtime и _buildManifest), шрифты, картинки;
  * скачивает JSON-данные страниц (/_next/data/<buildId>/...), чтобы работала
    клиентская навигация;
  * скачивает картинки с CDN squidex.jugru.team в snapshot/squidex/ и
    переписывает ссылки на локальные.

Только стандартная библиотека. Запуск: python3 tools/mirror.py [out_dir]
"""
import concurrent.futures as cf
import hashlib
import json
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ORIGIN = "https://snowone.ru"
SQUIDEX = "https://squidex.jugru.team/api/assets/"
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "snapshot")
UA = "Mozilla/5.0 (X11; Linux x86_64) snowone-mirror/1.0"

ASSET_PREFIXES = ("/_next/", "/img/", "/fonts/", "/favicon")
ASSET_EXT = re.compile(r"\.(js|css|woff2?|ttf|otf|eot|png|jpe?g|gif|svg|webp|avif|ico|webmanifest|json|xml|txt|pdf|mp4)$", re.I)
SKIP_PREFIXES = ("/api/", "/api", "/subscription_thanks")

RE_ATTR = re.compile(r'(?:href|src|content|poster|data-src)\s*=\s*"([^"]+)"', re.I)
RE_SRCSET = re.compile(r'(?:srcset|imagesrcset)\s*=\s*"([^"]+)"', re.I)
RE_CSSURL = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")
RE_SQUIDEX = re.compile(r"https://squidex\.jugru\.team/api/assets/([A-Za-z0-9._~%/+-]+)")
RE_JS_LOCAL = re.compile(r"[\"'`](/(?:img|fonts)/[^\"'`\s]+)[\"'`]")
RE_STATIC = re.compile(r"[\"'](static/(?:chunks|css|media)/[^\"']+)[\"']")
RE_NEXTDATA = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)

lock = threading.Lock()
pages_seen, assets_seen, squidex_seen = set(), set(), set()
redirects = {}      # path -> target
build_ids = set()
failures = []


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **kw):
        return None


opener = urllib.request.build_opener(NoRedirect)


def fetch(url, follow=False):
    """Возвращает (status, headers, body, location)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            op = urllib.request.build_opener() if follow else opener
            with op.open(req, timeout=60) as r:
                return r.status, r.headers, r.read(), None
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                return e.code, e.headers, b"", e.headers.get("Location")
            if e.code >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return e.code, e.headers, (e.read() if e.code == 404 else b""), None
        except Exception as e:  # сеть
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return 0, {}, b"", str(e)


def local_file(path):
    """URL-путь -> файл в OUT."""
    path = urllib.parse.unquote(path)
    if path.endswith("/"):
        path += "index.html"
    elif not ASSET_EXT.search(path) and not path.startswith("/_next/"):
        path += "/index.html"
    return os.path.join(OUT, path.lstrip("/"))


def save(path, body):
    f = local_file(path) if not isinstance(path, tuple) else path[0]
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "wb") as fh:
        fh.write(body)


def norm(ref, base):
    """Абсолютный URL -> внутренний путь сайта или None."""
    # Сайт использует только корневые ссылки; относительные значения атрибутов
    # (meta content, тексты и т.п.) ссылками не являются.
    if not (ref.startswith("/") and not ref.startswith("//")) and not re.match(r"https?://(www\.)?snowone\.ru(/|$)", ref):
        return None
    u = urllib.parse.urljoin(ORIGIN + base, ref.replace("&amp;", "&"))
    p = urllib.parse.urlsplit(u)
    if p.netloc not in ("snowone.ru", "www.snowone.ru"):
        return None
    return p.path or "/"


def is_asset(path):
    return path.startswith(ASSET_PREFIXES) or bool(ASSET_EXT.search(path))


def collect_text_refs(text, base, queue_pages, queue_assets):
    for m in RE_SQUIDEX.finditer(text):
        with lock:
            squidex_seen.add(m.group(1))
    refs = [m.group(1) for m in RE_ATTR.finditer(text)]
    for m in RE_SRCSET.finditer(text):
        refs += [c.strip().split(" ")[0] for c in m.group(1).split(",") if c.strip()]
    refs += [m.group(1) for m in RE_CSSURL.finditer(text)]
    refs += [m.group(1) for m in RE_JS_LOCAL.finditer(text)]
    for r in refs:
        p = norm(r, base)
        if not p or p.startswith(SKIP_PREFIXES):
            continue
        (queue_assets if is_asset(p) else queue_pages).append(p)


def get_asset(path):
    status, headers, body, loc = fetch(ORIGIN + urllib.parse.quote(path, safe="/%[]:@!$&'()*+,;=-._~"), follow=True)
    if status != 200:
        failures.append((path, status))
        return [], []
    save(path, body)
    pages, assets = [], []
    if path.endswith((".css", ".js", ".webmanifest", ".json", ".svg")):
        text = body.decode("utf-8", "replace")
        collect_text_refs(text, path, pages, assets)
        if path.endswith(".js"):
            assets += ["/_next/" + s for s in RE_STATIC.findall(text)]
            assets += webpack_chunks(text)
    return [], assets  # страницы из ассетов не берём — только ассеты


def webpack_chunks(js):
    """Разбирает карты чанков из webpack runtime: "static/chunks/"+e+"."+{id:"hash"}[e]+".js"."""
    out = []
    for kind, ext in (("chunks", "js"), ("css", "css")):
        for m in re.finditer(r'"static/%s/"\+(?:e\+"\."\+)?\(?\{([^}]*)\}' % kind, js):
            prefix_id = '"+e+"."+' in js[m.start():m.start() + 40]
            for cid, h in re.findall(r'(\d+):"([0-9a-f]{8,})"', m.group(1)):
                name = f"{cid}.{h}" if prefix_id else h
                out.append(f"/_next/static/{kind}/{name}.{ext}")
    return out


def get_page(path):
    status, headers, body, loc = fetch(ORIGIN + urllib.parse.quote(path, safe="/%"))
    if status in (301, 302, 303, 307, 308):
        target = norm(loc, path)
        with lock:
            redirects[path] = target or loc
        return ([target] if target else []), []
    if status != 200:
        failures.append((path, status))
        return [], []
    ctype = headers.get("Content-Type", "")
    if "html" not in ctype:
        save(path if is_asset(path) else path, body)
        return [], []
    save(path, body)
    text = body.decode("utf-8", "replace")
    pages, assets = [], []
    collect_text_refs(text, path, pages, assets)
    m = RE_NEXTDATA.search(text)
    if m:
        nd = json.loads(m.group(1))
        bid = nd.get("buildId")
        with lock:
            build_ids.add(bid)
        collect_text_refs(m.group(1), path, pages, assets)
        if nd.get("gsp") or nd.get("gssp"):
            slug = path.strip("/") or "index"
            for variant in (slug, "ru/" + slug if slug != "index" else "ru"):
                assets.append(f"/_next/data/{bid}/{variant}.json")
    return pages, assets


def crawl():
    status, _, body, _ = fetch(ORIGIN + "/sitemap.xml", follow=True)
    start = ["/"] + [urllib.parse.urlsplit(u).path for u in re.findall(r"<loc>([^<]+)</loc>", body.decode())]
    for extra in ("/robots.txt", "/sitemap.xml", "/favicon.ico", "/img/sprite.svg"):
        start.append(extra)
    pq, aq = [], []
    for p in start:
        (aq if is_asset(p) else pq).append(p)

    with cf.ThreadPoolExecutor(8) as ex:
        while pq or aq:
            futs = []
            for p in set(pq):
                if p not in pages_seen:
                    pages_seen.add(p)
                    futs.append(ex.submit(get_page, p))
            for a in set(aq):
                if a not in assets_seen:
                    assets_seen.add(a)
                    futs.append(ex.submit(get_asset, a))
            pq, aq = [], []
            for f in cf.as_completed(futs):
                np_, na = f.result()
                pq += np_
                aq += na
            print(f"pages={len(pages_seen)} assets={len(assets_seen)} squidex={len(squidex_seen)}", flush=True)
        # build manifests для всех buildId
        extra = []
        for bid in build_ids:
            extra += [f"/_next/static/{bid}/_buildManifest.js", f"/_next/static/{bid}/_ssgManifest.js"]
        aq = extra
        while aq:
            futs = [ex.submit(get_asset, a) for a in set(aq) if a not in assets_seen]
            assets_seen.update(aq)
            aq = []
            for f in cf.as_completed(futs):
                aq += f.result()[1]


def squidex_local(key):
    """Ключ squidex (путь после /api/assets/) -> локальный путь /squidex/..."""
    key = urllib.parse.unquote(key)
    safe = re.sub(r"[^A-Za-z0-9._/-]", "_", key)
    return "/squidex/" + safe


squidex_map = {}
SQUIDEX_EXTERNAL = (".pdf", ".pptx", ".zip", ".mp4")


def get_squidex(key):
    local = squidex_local(key)
    if key.lower().endswith(SQUIDEX_EXTERNAL):
        return  # слайды оставляем ссылками на CDN (см. docs/audit.md)
    status, headers, body, _ = fetch(SQUIDEX + key + "?cache=3600", follow=True)
    if status != 200:
        failures.append(("squidex:" + key, status))
        return
    if not ASSET_EXT.search(local):
        ext = mimetypes.guess_extension((headers.get("Content-Type") or "").split(";")[0].strip()) or ".bin"
        local += ext
    f = os.path.join(OUT, local.lstrip("/"))
    os.makedirs(os.path.dirname(f), exist_ok=True)
    with open(f, "wb") as fh:
        fh.write(body)
    with lock:
        squidex_map[key] = local


def rewrite_squidex():
    """Заменяет https://squidex.jugru.team/api/assets/<key> на локальный путь во всех текстовых файлах."""
    def repl(m):
        return squidex_map.get(m.group(1), m.group(0))
    n = 0
    for root, _, files in os.walk(OUT):
        for name in files:
            if not name.endswith((".html", ".json", ".css", ".js", ".webmanifest", ".svg", ".xml")):
                continue
            f = os.path.join(root, name)
            with open(f, encoding="utf-8", errors="surrogateescape") as fh:
                s = fh.read()
            s2 = RE_SQUIDEX.sub(repl, s)
            if s2 != s:
                n += 1
                with open(f, "w", encoding="utf-8", errors="surrogateescape") as fh:
                    fh.write(s2)
    print(f"rewrote squidex refs in {n} files")


# Точечные правки JS платформы, без которых копия не работает вне snowone.ru.
JS_PATCHES = [
    # Хелпер картинок делает new URL(src) и добавляет ?cache=3600&width=...;
    # с локальными путями /squidex/... это падает и роняет гидратацию React.
    # Даём базовый URL текущей страницы.
    (re.compile(r"(\w)=new URL\((\w)\),(\w)=new URLSearchParams\(\1\.search\)"),
     r"\1=new URL(\2,location.href),\3=new URLSearchParams(\1.search)"),
]


def patch_js():
    n = 0
    for root, _, files in os.walk(os.path.join(OUT, "_next")):
        for name in files:
            if not name.endswith(".js"):
                continue
            f = os.path.join(root, name)
            with open(f, encoding="utf-8") as fh:
                s = fh.read()
            s2 = s
            for rx, repl in JS_PATCHES:
                s2 = rx.sub(repl, s2)
            if s2 != s:
                n += 1
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(s2)
    print(f"patched {n} js files")


def optimize_images(max_side=800, min_bytes=300_000):
    """Фото докладчиков на CDN лежат в оригинале (до 17 МБ), а на сайте
    показываются аватарками. Уменьшаем крупные JPEG/PNG до max_side по длинной
    стороне. Требует Pillow; без него шаг пропускается."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        print("Pillow не установлен — оптимизация картинок пропущена")
        return
    saved = 0
    for root, _, files in os.walk(os.path.join(OUT, "squidex")):
        for name in files:
            f = os.path.join(root, name)
            if not name.lower().endswith((".jpg", ".jpeg", ".png")) or os.path.getsize(f) < min_bytes:
                continue
            before = os.path.getsize(f)
            with Image.open(f) as im:
                im = ImageOps.exif_transpose(im)
                im.thumbnail((max_side, max_side))
                if name.lower().endswith(".png"):
                    im.save(f, optimize=True)
                else:
                    im.convert("RGB").save(f, quality=85, optimize=True, progressive=True)
            saved += before - os.path.getsize(f)
    print(f"images optimized, saved {saved // 1024 // 1024} MB")


def write_redirects():
    tpl = ('<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Redirect</title>'
           '<link rel="canonical" href="{t}"><meta name="robots" content="noindex">'
           '<meta http-equiv="refresh" content="0; url={t}">'
           '<script>location.replace("{t}"+location.search+location.hash)</script>'
           '</head><body><a href="{t}">{t}</a></body></html>')
    for src, target in redirects.items():
        f = local_file(src)
        if os.path.exists(f):
            continue  # тот же каталог уже содержит страницу (/foo -> /foo/)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w") as fh:
            fh.write(tpl.format(t=target))


def get_404_page():
    """Страница 404 отдаётся с кодом 404 — сохраняем её тело как 404.html для GitHub Pages."""
    _, _, body, _ = fetch(ORIGIN + "/404/")
    if body:
        save((os.path.join(OUT, "404.html"),), body)
        pages, assets = [], []
        collect_text_refs(body.decode("utf-8", "replace"), "/404/", pages, assets)
        for a in set(assets) - assets_seen:
            assets_seen.add(a)
            get_asset(a)


def main():
    os.makedirs(OUT, exist_ok=True)
    crawl()
    get_404_page()
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    print(f"downloading {len(squidex_seen)} squidex assets")
    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(get_squidex, sorted(squidex_seen)))
    rewrite_squidex()
    patch_js()
    optimize_images()
    write_redirects()
    import postprocess  # отвязка от инфраструктуры JUG Ru, см. tools/postprocess.py
    postprocess.OUT = OUT
    postprocess.main()
    manifest = {
        "origin": ORIGIN,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "build_ids": sorted(build_ids),
        "pages": sorted(pages_seen - set(redirects)),
        "redirects": dict(sorted(redirects.items())),
        "failures": sorted(map(list, failures)),
    }
    with open(os.path.join(OUT, "..", "docs", "snapshot-manifest.json") if os.path.isdir(os.path.join(OUT, "..", "docs")) else os.path.join(OUT, "snapshot-manifest.json"), "w") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    print(f"done: pages={len(manifest['pages'])} redirects={len(redirects)} failures={len(failures)}")


if __name__ == "__main__":
    main()
