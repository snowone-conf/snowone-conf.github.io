#!/usr/bin/env python3
"""Замораживает архивные страницы из снапшота в static/ сайта Hugo.

Архив прошлых лет (/archive/, /archive/2025/...) не переносится в данные Hugo,
а публикуется как есть — страницами старой платформы (Next.js) со всеми нужными
ресурсами. Скрипт копирует:
  snapshot/archive/**                  -> static/archive/**
  snapshot/_next/static/**             -> static/_next/static/**   (JS/CSS платформы)
  snapshot/_next/data/*/(ru/)archive*  -> static/_next/data/...     (клиентская навигация по архиву)
  snapshot/squidex/<файлы архива>      -> static/squidex/...        (только используемые архивом)
  overrides/overrides.css              -> static/overrides.css

Данные для текущих страниц (/speakers/ и т.п.) не копируются: если со страницы
архива перейти в текущий сезон, Next.js не найдёт JSON и загрузит страницу Hugo
обычным переходом.

Запуск: python3 tools/freeze_archive.py  (после tools/mirror.py)
"""
import glob
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "snapshot")
STATIC = os.path.join(ROOT, "static")
RE_SQUIDEX = re.compile(r"/squidex/[A-Za-z0-9._/-]+")


def copytree(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def main():
    copytree(os.path.join(SNAP, "archive"), os.path.join(STATIC, "archive"))
    copytree(os.path.join(SNAP, "_next", "static"), os.path.join(STATIC, "_next", "static"))

    data_dst = os.path.join(STATIC, "_next", "data")
    if os.path.exists(data_dst):
        shutil.rmtree(data_dst)
    data_files = []
    for build in glob.glob(os.path.join(SNAP, "_next", "data", "*")):
        for prefix in ("", "ru"):
            base = os.path.join(build, prefix)
            data_files += glob.glob(os.path.join(base, "archive.json"))
            data_files += glob.glob(os.path.join(base, "archive", "**", "*.json"), recursive=True)
    for f in data_files:
        dst = os.path.join(data_dst, os.path.relpath(f, os.path.join(SNAP, "_next", "data")))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(f, dst)

    used = set()
    for f in glob.glob(os.path.join(STATIC, "archive", "**", "*.html"), recursive=True) + data_files:
        with open(f, encoding="utf-8") as fh:
            used |= set(RE_SQUIDEX.findall(fh.read()))
    sq_dst = os.path.join(STATIC, "squidex")
    if os.path.exists(sq_dst):
        shutil.rmtree(sq_dst)
    copied = 0
    for u in sorted(used):
        src = os.path.join(SNAP, u.lstrip("/"))
        if os.path.isfile(src):
            dst = os.path.join(STATIC, u.lstrip("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)
            copied += 1

    shutil.copy(os.path.join(ROOT, "overrides", "overrides.css"), os.path.join(STATIC, "overrides.css"))
    pages = len(glob.glob(os.path.join(STATIC, "archive", "**", "index.html"), recursive=True))
    print(f"архив: {pages} страниц, {len(data_files)} JSON, {copied} картинок")


if __name__ == "__main__":
    main()
