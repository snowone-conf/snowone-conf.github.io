#!/usr/bin/env python3
"""Разовый перенос данных сезона из снапшота (JSON Next.js) в контент Hugo.

Читает snapshot/_next/data/<buildId>/ru/*.json и создаёт:
  content/persons/<id>/index.{ru,en}.md  — докладчики, ведущие, программный комитет (+ фото)
  content/talks/<id>/index.{ru,en}.md    — доклады
  content/partners/<slug>/index.{ru,en}.md — партнёры (+ логотип)
  content/<page>/index.ru.md             — текстовые страницы (CoC, правила, юр. документы)
  data/conference.yaml, data/committee.yaml

Идентификаторы (hex-id) сохраняются как имена бандлов, чтобы не менялись URL.
Английские версии создаются только там, где в данных есть перевод.

Запуск: python3 tools/import_nextdata.py [--force]
"""
import glob
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "snapshot")
DATA = glob.glob(os.path.join(SNAP, "_next", "data", "*", "ru"))[0]
CONTENT = os.path.join(ROOT, "content")
FORCE = "--force" in sys.argv
SEASON = 2026
TZ = timezone(timedelta(hours=7))  # Новосибирск: время в контенте храним местное


def local(iso):
    """'2026-02-28T08:25:00Z' -> '2026-02-28T15:25:00+07:00'"""
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ).isoformat()


def page(name):
    with open(os.path.join(DATA, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)["pageProps"]


def tr(d, lang="ru"):
    """Локализованное значение {ru, en} -> строка; '-' и пустые считаются отсутствующими."""
    if not isinstance(d, dict):
        return d
    v = d.get(lang)
    if isinstance(v, str) and v.strip() in ("", "-", "<p>-</p>"):
        return None
    return v


def clean(d):
    """Выбрасывает пустые значения из frontmatter."""
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


class Dumper(yaml.SafeDumper):
    pass


def _str(dumper, s):
    style = "|" if "\n" in s else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", s, style=style)


Dumper.add_representer(str, _str)


def dump_yaml(obj):
    return yaml.dump(obj, Dumper=Dumper, allow_unicode=True, sort_keys=False, width=1000)


def write_md(path, front, body=""):
    if os.path.exists(path) and not FORCE:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("---\n" + dump_yaml(clean(front)) + "---\n")
        if body:
            fh.write(body.strip() + "\n")


def write_data(name, obj):
    path = os.path.join(ROOT, "data", name + ".yaml")
    if os.path.exists(path) and not FORCE:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(dump_yaml(obj))


def copy_asset(url, bundle, basename):
    """/squidex/... -> файл внутри бандла. Возвращает имя файла."""
    if not url:
        return None
    src = os.path.join(SNAP, url.split("?")[0].lstrip("/"))
    if not os.path.exists(src):
        print("  нет файла", url)
        return None
    name = basename + os.path.splitext(src)[1].lower()
    os.makedirs(bundle, exist_ok=True)
    shutil.copy(src, os.path.join(bundle, name))
    return name


TYPES = {"talk": "talk", "conversation": "conversation", "workshop": "workshop"}


# --- персоны ----------------------------------------------------------------
def import_persons(committee_ids):
    order = {sp["id"]: (i + 1) * 10 for i, sp in enumerate(page("speakers")["speakers"])}
    for f in sorted(glob.glob(os.path.join(DATA, "persons", "*.json"))):
        pp = json.load(open(f, encoding="utf-8"))["pageProps"]
        p = pp["person"]
        bundle = os.path.join(CONTENT, "persons", p["id"])
        photo = copy_asset((p.get("photo") or {}).get("url"), bundle, "photo")
        past = []
        for year, groups in pp.get("pastActivities") or []:
            for g in groups:
                for t in (g.get("talks") or []) + (g.get("activities") or []):
                    past.append({"year": int(year), "title": tr(t["name"]),
                                 "format": TYPES.get(t.get("type"), "talk"),
                                 "language": "ru" if t.get("isRussianLanguage", True) else "en",
                                 "url": f"/archive/{year}/talks/{t['id']}/"})
        contacts = [{"type": c["type"], "url": c["value"]} for c in p.get("contacts") or []]
        for lang in ("ru", "en"):
            name = tr(p["name"], lang)
            if not name:
                continue
            front = {
                "title": name,
                "weight": order.get(p["id"]),
                "company": tr(p.get("company"), lang),
                "position": tr(p.get("position"), lang),
                "photo": photo,
                "contacts": contacts,
                "committee": p["id"] in committee_ids or None,
                "past_talks": past if lang == "ru" else None,
            }
            bio = tr(p.get("bio"), lang)
            if lang == "en" and not bio and not tr(p.get("company"), "en"):
                continue
            write_md(os.path.join(bundle, f"index.{lang}.md"), front, bio or "")


# --- доклады ----------------------------------------------------------------
def import_talks():
    for f in sorted(glob.glob(os.path.join(DATA, "talks", "*.json"))):
        t = json.load(open(f, encoding="utf-8"))["pageProps"]["talk"]
        bundle = os.path.join(CONTENT, "talks", t["id"])
        slides = [m["url"] for m in t.get("materials") or [] if m.get("materialType") == "presentation"]
        for lang in ("ru", "en"):
            title = tr(t["name"], lang)
            if not title:
                continue
            if lang == "en" and title == tr(t["name"], "ru"):
                continue  # «перевода» нет — название совпадает
            front = {
                "title": title,
                "format": TYPES.get(t.get("type"), t.get("type")),
                "speakers": [s["id"] for s in t.get("speakers") or []],
                "hosts": [s["id"] for s in t.get("hosts") or []],
                "language": "ru" if t.get("isRussianLanguage") else "en",
                "day": t.get("talkDay"),
                "start": local(t.get("talkStartTime")),
                "end": local(t.get("talkEndTime")),
                "track": t.get("trackNumber"),
                "hall": tr(t.get("hall"), lang) or tr(t.get("hall")),
                "order": t.get("talkOrder"),
                "summary": tr(t.get("shortDescription"), lang),
                "slides": slides[0] if slides else None,
                "video": [v if isinstance(v, str) else v.get("url") for v in t.get("videoLinks") or []],
                "season": SEASON,
            }
            write_md(os.path.join(bundle, f"index.{lang}.md"), front, tr(t.get("longDescription"), lang) or "")


# --- партнёры ---------------------------------------------------------------
def import_partners():
    pp = page("partners")
    order = {p["slug"]: (i + 1) * 10 for i, p in enumerate(
        pp.get("mainPartners", []) + pp.get("infoPartners", []) + pp.get("venuePartners", []))}
    for f in sorted(glob.glob(os.path.join(DATA, "partners", "*.json"))):
        p = json.load(open(f, encoding="utf-8"))["pageProps"]["partner"]
        bundle = os.path.join(CONTENT, "partners", p["slug"])
        logo = copy_asset((p.get("logo") or {}).get("url"), bundle, "logo")
        for lang in ("ru", "en"):
            buttons = []
            for kind, items in (p.get("buttons") or {}).items():
                for b in items or []:
                    title, href = tr(b.get("title"), lang), tr(b.get("href"), lang)
                    if title and href:
                        buttons.append({"title": title, "url": href})
            desc = tr(p.get("descriptions"), lang)
            if lang == "en" and not desc:
                continue
            front = {
                "title": tr(p["name"], lang),
                "tier": p.get("type"),
                "weight": order.get(p["slug"], p.get("order")),
                "link": p.get("link"),
                "logo": logo,
                "buttons": buttons,
                "season": SEASON,
            }
            write_md(os.path.join(bundle, f"index.{lang}.md"), front, desc or "")


# --- текстовые страницы -----------------------------------------------------
TEXT_PAGES = {
    # страница: (ключ в pageProps, заголовок, порядок в списке «Правовые документы» или None)
    "privacy_policy": ("privacyPolicy", "Политика конфиденциальности", 10),
    "data_processing_consent": ("dataProcessingConsent", "Согласие на обработку персональных данных", 20),
    "publish_content_consent": ("publishContentConsent", "Согласие на обработку персональных данных, разрешенных субъектом персональных данных для распространения", 30),
    "coc": ("cocContent", "Code of Conduct", 40),
    "public_policy": ("publicPolicy", "Политика в области фото и видеосъемки", 50),
    "author_agreement": ("authorAgreement", "Лицензионный договор с Автором", 60),
    "advertising_agreement": ("advertisingAgreement", "Согласие на получение рекламной информации", 70),
    "rules": ("rulesContent", "Правила участия", None),
}


def import_text_pages():
    for slug, (key, title, legal) in TEXT_PAGES.items():
        v = page(slug).get(key)
        html = tr(v) if isinstance(v, dict) else v
        if isinstance(html, dict):  # иногда контент вложен ещё на уровень
            html = tr(html.get("content") or html.get("text") or html)
        if not isinstance(html, str):
            print("  пропущена страница", slug, type(html))
            continue
        write_md(os.path.join(CONTENT, slug, "index.ru.md"),
                 {"title": title, "layout": "text", "legal": legal is not None or None, "weight": legal}, html)
    write_md(os.path.join(CONTENT, "legal", "index.ru.md"), {"title": "Правовые документы", "layout": "legal"})


# --- страницы с собственной структурой --------------------------------------
def import_special_pages():
    cfp = page("callforpapers")["cfp"]
    topics = []
    for cat, items in cfp.get("topicsByCategory") or []:
        topics.append({"title": tr(cat), "items": [tr(i["title"]) for i in items]})
    links = cfp.get("banner", {}).get("links") or []
    write_md(os.path.join(CONTENT, "callforpapers", "index.ru.md"), {
        "title": "Подать заявку на доклад",
        "layout": "callforpapers",
        "seoTitle": "SnowOne 2026 | Подача заявки на доклад",
        "ogImage": "/img/site/snowone-cfp.jpg",
        "subtitle": tr(cfp["banner"]["title"]),
        "ask": {"title": tr(links[0]["text"]), "url": tr(links[0]["href"])} if links else None,
        "topics_note": tr(cfp.get("topicsText")),
        "topics": topics,
    })
    write_md(os.path.join(CONTENT, "organizers", "index.ru.md"), {
        "title": "Организаторы",
        "layout": "organizers",
        "seoTitle": "SnowOne 2026 | Организаторы | JUGNsk",
        "organizer": "JUGNsk",
        "logo": "/img/site/jugnsk-logo.jpg",
        "link": "https://t.me/jugnsk",
    }, "Независимое сообщество Java-разработчиков в Новосибирске. Постим новости, делаем объявления о митапах "
       "и других мероприятиях. Обсуждения глобальных тем Java/JVM категорически приветствуются.")
    write_md(os.path.join(CONTENT, "speakers", "index.ru.md"), {"title": "Спикеры", "layout": "speakers"})
    write_md(os.path.join(CONTENT, "schedule", "days", "index.ru.md"), {"title": "Расписание", "layout": "schedule"})
    # Корни разделов: как на старом сайте — редиректы или списки
    write_md(os.path.join(CONTENT, "schedule", "_index.ru.md"), {"title": "Расписание", "layout": "redirect", "redirect": "/schedule/days/", "sitemap": {"disable": True}})
    write_md(os.path.join(CONTENT, "talks", "_index.ru.md"), {"title": "Доклады", "layout": "redirect", "redirect": "/schedule/days/", "sitemap": {"disable": True}})
    write_md(os.path.join(CONTENT, "persons", "_index.ru.md"), {"title": "Спикеры", "layout": "redirect", "redirect": "/speakers/", "sitemap": {"disable": True}})
    write_md(os.path.join(CONTENT, "partners", "_index.ru.md"), {"title": "Партнеры"})


# --- данные сезона ----------------------------------------------------------
def import_conference():
    home = page("../index") if os.path.exists(os.path.join(DATA, "..", "index.json")) else page("index")
    ci = home["conferenceInfo"]
    v, pr = ci["version"], ci["project"]
    venue = v.get("venue", {}).get("ru", {})
    sched = page("schedule/days")
    conf = {
        "season": int(v["version"]),
        "title": tr(v["title"]),
        "description": tr(v["description"]),
        "meta_description": ci["marketingTools"].get("metaDescription"),
        "start": local(v["dates"]["startDate"]),
        "end": local(v["dates"]["endDate"]),
        "status": "finished",  # announced | open | finished — управляет плашками и кнопками
        "venue": {"city": venue.get("city"), "title": venue.get("title"),
                  "address": venue.get("address"), "map": venue.get("geolocationLink")},
        "organizer": "JUGNsk",
        "since": int(pr.get("since", 2020)),
        "contacts": {"support": pr["contactUs"]["supportEmail"], "partners": pr["contactUs"]["partnersEmail"],
                     "telegram": "https://t.me/jugnsk"},
        "social": [{"name": s["name"], "url": s["url"]} for s in pr.get("social", [])],
        "statistics": [{"value": tr(s["value"]), "label": tr(s["label"])} for s in home.get("statistic", [])],
        "about": tr(home["common"]["aboutMain"]),
        "community_day": {"title": tr(home["communityDay"]["title"]),
                          "description": tr(home["communityDay"]["description"])},
        "program_pdf": tr((sched.get("eventProgram") or {}).get("link")),
        "days": [{"date": d["date"][:10],
                  "tracks": [{"number": t["trackNumber"], "title": tr(t["trackTitle"])} for t in d.get("tracks", [])]}
                 for d in sched["talksByDay"]],
    }
    write_data("conference", conf)
    committee = [p["id"] for p in page("organizers")["programCommittee"]]
    write_data("committee", {"season": conf["season"], "members": committee})
    return set(committee)


def main():
    committee = import_conference()
    import_persons(committee)
    import_talks()
    import_partners()
    import_text_pages()
    import_special_pages()
    print("готово:", {d: len(os.listdir(os.path.join(CONTENT, d)))
                      for d in ("persons", "talks", "partners") if os.path.isdir(os.path.join(CONTENT, d))})


if __name__ == "__main__":
    main()
