#!/usr/bin/env python3
"""Проверка целостности контента: ссылки между докладами, персонами и партнёрами.

Проверяет:
  * speakers/hosts докладов ссылаются на существующие content/persons/<id>/
  * члены программного комитета (data/committee.yaml) существуют
  * файлы photo/logo, указанные во frontmatter, лежат в бандле
  * у докладов текущего сезона заполнены day/start/end/track и они согласованы
    с data/conference.yaml (день существует, трек есть в этом дне, начало < конца)

Выход с кодом 1 при ошибках. Запуск: python3 tools/check_refs.py
"""
import glob
import os
import sys
from datetime import datetime

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, "content")
errors = []


def front(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---"):
        return {}
    return yaml.safe_load(text.split("---", 2)[1]) or {}


def bundles(section):
    return {os.path.basename(d): d for d in glob.glob(os.path.join(CONTENT, section, "*")) if os.path.isdir(d)}


def rel(p):
    return os.path.relpath(p, ROOT)


def main():
    persons = bundles("persons")
    conf = yaml.safe_load(open(os.path.join(ROOT, "data", "conference.yaml"), encoding="utf-8"))
    committee = yaml.safe_load(open(os.path.join(ROOT, "data", "committee.yaml"), encoding="utf-8"))

    for pid, d in persons.items():
        for f in glob.glob(os.path.join(d, "index.*.md")):
            photo = front(f).get("photo")
            if photo and not os.path.exists(os.path.join(d, photo)):
                errors.append(f"{rel(f)}: нет файла фото {photo}")

    for pid in committee.get("members", []):
        if pid not in persons:
            errors.append(f"data/committee.yaml: нет персоны {pid}")

    days = conf.get("days", [])
    for tid, d in bundles("talks").items():
        for f in glob.glob(os.path.join(d, "index.*.md")):
            fm = front(f)
            for role in ("speakers", "hosts"):
                for pid in fm.get(role) or []:
                    if pid not in persons:
                        errors.append(f"{rel(f)}: {role} ссылается на несуществующую персону {pid}")
            if fm.get("season") != conf.get("season") or not f.endswith(".ru.md"):
                continue
            missing = [k for k in ("day", "start", "end", "track") if not fm.get(k)]
            if missing:
                errors.append(f"{rel(f)}: не заполнены поля {', '.join(missing)}")
                continue
            day = fm["day"]
            if not 1 <= day <= len(days):
                errors.append(f"{rel(f)}: день {day} отсутствует в data/conference.yaml")
                continue
            tracks = {t["number"] for t in days[day - 1].get("tracks", [])}
            if fm["track"] not in tracks:
                errors.append(f"{rel(f)}: трека {fm['track']} нет в дне {day} (есть: {sorted(tracks)})")
            start, end = (datetime.fromisoformat(str(fm[k])) for k in ("start", "end"))
            if start >= end:
                errors.append(f"{rel(f)}: начало {fm['start']} не раньше конца {fm['end']}")
            if start.date().isoformat() != days[day - 1]["date"]:
                errors.append(f"{rel(f)}: дата начала {start.date()} не совпадает с днём {day} ({days[day - 1]['date']})")

    for sid, d in bundles("partners").items():
        for f in glob.glob(os.path.join(d, "index.*.md")):
            logo = front(f).get("logo")
            if logo and not os.path.exists(os.path.join(d, logo)):
                errors.append(f"{rel(f)}: нет файла логотипа {logo}")

    for e in errors:
        print("ОШИБКА:", e)
    print(f"проверено: {len(persons)} персон, {len(bundles('talks'))} докладов, {len(bundles('partners'))} партнёров; ошибок: {len(errors)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
