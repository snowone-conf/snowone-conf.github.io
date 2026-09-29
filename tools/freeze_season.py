#!/usr/bin/env python3
"""Замораживает текущий сезон в архив: static/archive/<год>/.

Собирает сайт Hugo во временную папку и копирует готовые страницы сезона
(главная, расписание, доклады, спикеры, партнёры, текстовые страницы и т.п.)
вместе с их CSS, JS и картинками в static/archive/<год>/. Ссылки между ними
переписываются: /speakers/ -> /archive/<год>/speakers/, / -> /archive/<год>/.
После этого архив — обычные статические файлы, которые больше не зависят от
шаблонов и данных Hugo, и основной сайт можно готовить к следующему сезону.

Не копируются и не переписываются:
  * общие статические файлы из static/ (шрифты, спрайт, /_next/, /squidex/ и т.п.),
    кроме картинок сезона /img/site/…: они копируются, чтобы архив не поменялся
    вместе с оформлением нового сезона;
  * архивы сезонов (/archive/<год>/…) — ссылки на них остаются как есть.
    Список сезонов /archive/ замораживается вместе с сезоном в
    /archive/<год>/archive/ (как в архиве 2025), и меню архивной копии ведёт туда;
  * 404.html, robots.txt, sitemap.xml.

Аналитика: встроенный счётчик убирается, вместо него подключается общий
/analytics.js (как на страницах архива 2025) — счётчик берётся из hugo.yaml.

Запуск: python3 tools/freeze_season.py [ГОД] [--force]
  ГОД — по умолчанию season из data/conference.yaml;
  --force — перезаписать уже существующий static/archive/<год>/.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")
# Адрес, с которым собираются абсолютные ссылки (canonical, og:url, og:image).
BASE_URL = "https://snowone.ru"
# Картинки оформления сезона, которые замораживаются вместе с архивом.
SEASON_IMAGES = "img/site"
SKIP = {"archive", "404.html", "robots.txt", "sitemap.xml", "analytics.js"}

RE_METRIKA = re.compile(r"<script>(?:(?!</script>).)*mc\.yandex\.ru(?:(?!</script>).)*</script>\s*"
                        r"|<noscript>(?:(?!</noscript>).)*mc\.yandex\.ru(?:(?!</noscript>).)*</noscript>\s*", re.S)
ANALYTICS_TAG = '<script src="/analytics.js" defer></script>'


def url_pattern(sections):
    """Корневые ссылки на разделы сезона и на главную (относительные и с BASE_URL)."""
    names = "|".join(re.escape(s) for s in sorted(sections, key=len, reverse=True))
    return re.compile(
        r"(?P<pre>[\s\"'(=,;])(?P<base>%s)?/(?=(?:(?:%s)(?=[/\"'?#)\s,&])|[\"'#?&]))"
        % (re.escape(BASE_URL), names))


RE_ARCHIVE_INDEX = re.compile(r"(?P<pre>[\s\"'(=,;])(?P<base>%s)?/archive/(?=[\"'#?&])" % re.escape(BASE_URL))


def rewrite(html, sections, prefix):
    """Переписывает ссылки на разделы sections, главную и список архива под префикс архива."""
    html = url_pattern(sections).sub(lambda m: "%s%s%s/" % (m["pre"], m["base"] or "", prefix), html)
    html = RE_ARCHIVE_INDEX.sub(lambda m: "%s%s%s/archive/" % (m["pre"], m["base"] or "", prefix), html)
    html = RE_METRIKA.sub("", html)
    if ANALYTICS_TAG not in html and 'http-equiv="refresh"' not in html:
        html = html.replace("</head>", "%s\n</head>" % ANALYTICS_TAG, 1)
    return html


def season_images(html):
    return set(re.findall(r"(?:%s)?/(%s/[A-Za-z0-9._/-]+)" % (re.escape(BASE_URL), re.escape(SEASON_IMAGES)), html))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("year", nargs="?", type=int)
    ap.add_argument("--force", action="store_true", help="перезаписать существующий архив сезона")
    args = ap.parse_args()

    year = args.year
    if not year:
        with open(os.path.join(ROOT, "data", "conference.yaml"), encoding="utf-8") as fh:
            year = int(yaml.safe_load(fh)["season"])
    prefix = "/archive/%d" % year
    dest = os.path.join(STATIC, "archive", str(year))
    if os.path.exists(dest):
        if not args.force:
            sys.exit("%s уже существует (перезаписать: --force)" % os.path.relpath(dest, ROOT))
        shutil.rmtree(dest)

    with tempfile.TemporaryDirectory() as build:
        subprocess.run(["hugo", "--gc", "--quiet", "--source", ROOT, "--destination", build,
                        "--baseURL", BASE_URL + "/"], check=True)
        skip = SKIP | set(os.listdir(STATIC))
        entries = sorted(e for e in os.listdir(build) if e not in skip)
        os.makedirs(dest)
        for e in entries:
            src = os.path.join(build, e)
            (shutil.copytree if os.path.isdir(src) else shutil.copy)(src, os.path.join(dest, e))
        os.makedirs(os.path.join(dest, "archive"))
        shutil.copy(os.path.join(build, "archive", "index.html"), os.path.join(dest, "archive", "index.html"))

    sections = [e for e in entries if os.path.isdir(os.path.join(dest, e))] + [SEASON_IMAGES]
    pages = images = 0
    refs = set()
    for d, _, files in os.walk(dest):
        for f in files:
            if not f.endswith(".html"):
                continue
            path = os.path.join(d, f)
            with open(path, encoding="utf-8") as fh:
                html = fh.read()
            for img in season_images(html):
                src, dst = os.path.join(STATIC, img), os.path.join(dest, img)
                if os.path.isfile(src) and not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy(src, dst)
                    images += 1
            html = rewrite(html, sections, prefix)
            refs |= set(re.findall(re.escape(prefix) + r"/[^\s\"'#?)&,]+", html))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(html)
            pages += 1
    # Hugo публикует и исходные файлы бандлов (photo.jpg), хотя страницы ссылаются
    # только на уменьшенные копии: неиспользуемое в архив не кладём.
    unused = 0
    for d, _, files in os.walk(dest):
        for f in files:
            path = os.path.join(d, f)
            if not f.endswith(".html") and "%s/%s" % (prefix, os.path.relpath(path, dest)) not in refs:
                os.remove(path)
                unused += 1
    print("%s: %d страниц, %d картинок оформления, удалено неиспользуемых файлов: %d; разделы: %s"
          % (os.path.relpath(dest, ROOT), pages, images, unused, ", ".join(sections)))


if __name__ == "__main__":
    main()
