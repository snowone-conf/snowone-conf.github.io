#!/usr/bin/env python3
"""Страницы спикера и выступления из карточки Trello — для workflow cfp-accept.

    python3 tools/cfp_from_trello.py build --card <ссылка или короткий код> --summary out.json
    python3 tools/cfp_from_trello.py comment --card <код> --text "…"

Карточку заполняет сервис cfp-function по шаблону, а программный комитет правит её во время
обсуждения. Шаблон и правила разбора — docs/schema.md репозитория cfp-function (§3, §4).
Создаются:
  content/persons/<имя-фамилия>/index.ru.md и photo.jpg (если спикера ещё нет на сайте)
  content/talks/<спикер>---<название>/index.ru.md — без draft и без расписания

Ключ и токен Trello — из переменных окружения TRELLO_KEY и TRELLO_TOKEN.
Итог (номер заявки, ветка, заметки для ревьюера или текст ошибки) пишется в --summary в JSON.
"""
import argparse
import glob
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import yaml

from import_cfp import ROOT, paragraphs, slugify, write_md

CONTENT = os.path.join(ROOT, "content")
API = "https://api.trello.com/1"

FORMATS = {"доклад": "talk", "talk": "talk", "воркшоп": "workshop", "workshop": "workshop",
           "обсуждение": "conversation", "conversation": "conversation",
           "ключевой доклад": "keynote", "keynote": "keynote"}
FORMAT_CHOICES = "Доклад, Воркшоп, Обсуждение, Ключевой доклад"
LANGUAGES = {"русский": "ru", "ru": "ru", "english": "en", "en": "en"}
PHOTO = re.compile(r"^speaker-(\d)\.([a-z0-9]+)$", re.IGNORECASE)


class CardError(Exception):
    """Ошибка разбора карточки; текст уходит комментарием в карточку и в чат ПК."""


# --- разбор описания карточки ---

def unescape(text):
    """Редактор Trello экранирует знаки Markdown обратной косой чертой: «C\\#» → «C#»."""
    return re.sub(r"\\([\\`*_{}\[\]()#+\-.!>~|<])", r"\1", text)


def sections(desc):
    """Разделы «## …» → {заголовок: (поля «Ключ: значение», подразделы «### …»)}; всё после «---» отбрасывается."""
    body = re.split(r"^-{3,}\s*$", desc, maxsplit=1, flags=re.M)[0]
    out = {}
    for block in re.split(r"^##(?!#)\s*", body, flags=re.M)[1:]:
        head, _, rest = block.partition("\n")
        parts = re.split(r"^###\s*(.+?)\s*$", rest, flags=re.M)
        fields = {}
        for line in parts[0].splitlines():
            key, sep, value = line.partition(":")
            if sep and key.strip():
                fields[key.strip().lower()] = value.strip()
        subs = {parts[i].strip().lower(): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
        out[head.strip().lower()] = (fields, subs)
    return out


def required(value, field, section):
    if not value:
        raise CardError(f"Не заполнено поле «{field}» в разделе «{section}».")
    return value


def parse_card(desc):
    """Описание карточки → {talk: {...}, speakers: [{...}], cfp_id}. Ошибки — CardError с текстом из схемы."""
    desc = unescape(desc.replace("\r\n", "\n"))
    secs = sections(desc)
    if "выступление" not in secs or "спикер" not in secs:
        missing = "## Выступление" if "выступление" not in secs else "## Спикер"
        raise CardError(f"Не нашёл раздел «{missing}» в описании карточки. Верните заголовок из шаблона.")

    fields, subs = secs["выступление"]
    raw_format = required(fields.get("формат", ""), "Формат", "Выступление")
    fmt = raw_format.lower()
    if fmt in ("другое", "other"):
        raise CardError(f"Формат «Другое» нужно заменить на один из: {FORMAT_CHOICES}.")
    if fmt not in FORMATS:
        raise CardError(f"Формат «{raw_format}» не распознан. Допустимо: {FORMAT_CHOICES}.")
    raw_lang = required(fields.get("язык", ""), "Язык", "Выступление")
    if raw_lang.lower() not in LANGUAGES:
        raise CardError(f"Язык «{raw_lang}» не распознан. Допустимо: Русский, English.")
    talk = {
        "title": required(fields.get("название", ""), "Название", "Выступление"),
        "format": FORMATS[fmt],
        "language": LANGUAGES[raw_lang.lower()],
        "summary": " ".join(required(subs.get("кратко", ""), "Кратко", "Выступление").split()),
        "description": paragraphs(required(subs.get("подробно", ""), "Подробно", "Выступление")),
    }

    speakers = []
    for number, name in ((1, "спикер"), (2, "спикер 2")):
        if name not in secs:
            continue
        fields, subs = secs[name]
        title = "Спикер" if number == 1 else "Спикер 2"
        speakers.append({
            "number": number,
            "name": " ".join(required(fields.get("имя", ""), "Имя", title).split()),
            "company": fields.get("компания", ""),
            "position": required(fields.get("должность или род деятельности", ""),
                                 "Должность или род деятельности", title),
            "bio": paragraphs(required(subs.get("о спикере", ""), "О спикере", title)),
            "website": fields.get("сайт", ""),
            "github": fields.get("github", ""),
        })
    m = re.search(r"^Заявка\s+(\d{8}-[a-z0-9]{4})", desc, flags=re.M)
    return {"talk": talk, "speakers": speakers, "cfp_id": m.group(1) if m else ""}


# --- страницы сайта ---

def front(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return yaml.safe_load(text.split("---", 2)[1]) or {} if text.startswith("---") else {}


def known_persons(content):
    """Имя → папка персоны: у спикеров прошлых лет папки — хеши, искать можно только по имени."""
    out = {}
    for f in sorted(glob.glob(os.path.join(content, "persons", "*", "index.*.md"))):
        title = str(front(f).get("title", "")).strip().lower()
        if title:
            out.setdefault(title, os.path.basename(os.path.dirname(f)))
    return out


def free_dir(section_dir, slug):
    """Свободная папка: slug, затем slug-2, slug-3…"""
    candidate, n = slug, 1
    while os.path.exists(os.path.join(section_dir, candidate)):
        n += 1
        candidate = f"{slug}-{n}"
    return candidate


def site_contacts(sp):
    out = []
    if sp["website"]:
        out.append({"type": "website", "url": sp["website"] if re.match(r"https?://", sp["website"])
                    else "https://" + sp["website"]})
    if sp["github"]:
        g = sp["github"]
        out.append({"type": "github", "url": g if g.startswith("http") else "https://github.com/" + g.lstrip("@")})
    return out


def build(card, photos, content, season):
    """Создаёт страницы; photos — {номер спикера: (байты, расширение)}. Возвращает (папки, заметки)."""
    notes, created = [], []
    persons_dir = os.path.join(content, "persons")
    talks_dir = os.path.join(content, "talks")
    known = known_persons(content)
    speaker_ids = []
    for sp in card["speakers"]:
        existing = known.get(sp["name"].lower())
        if existing:
            speaker_ids.append(existing)
            notes.append(f"Спикер «{sp['name']}» уже есть на сайте (content/persons/{existing}/): проверьте, "
                         "тот ли это человек, и при необходимости обновите биографию и фото вручную.")
            continue
        if sp["number"] not in photos:
            raise CardError(f"У спикера «{sp['name']}» нет фото: приложите вложение speaker-{sp['number']}.jpg.")
        slug = slugify(sp["name"])
        pid = free_dir(persons_dir, slug)
        if pid != slug:
            notes.append(f"Папка content/persons/{slug}/ занята другим человеком, спикер записан в {pid}/.")
        data, ext = photos[sp["number"]]
        bundle = os.path.join(persons_dir, pid)
        os.makedirs(bundle, exist_ok=True)
        with open(os.path.join(bundle, "photo." + ext), "wb") as fh:
            fh.write(data)
        write_md(os.path.join(bundle, "index.ru.md"), {
            "title": sp["name"],
            "company": sp["company"],
            "position": sp["position"],
            "photo": "photo." + ext,
            "weight": 100,
            "contacts": site_contacts(sp),
        }, sp["bio"], False)
        speaker_ids.append(pid)
        created.append(f"content/persons/{pid}/")

    t = card["talk"]
    slug = f"{speaker_ids[0]}---{slugify(t['title'])}"
    tid = free_dir(talks_dir, slug)
    if tid != slug:
        notes.append(f"Папка content/talks/{slug}/ уже занята, выступление записано в {tid}/.")
    write_md(os.path.join(talks_dir, tid, "index.ru.md"), {
        "title": t["title"],
        "format": t["format"],
        "speakers": speaker_ids,
        "language": t["language"],
        "summary": t["summary"],
        "season": season,
        "cfp_id": card["cfp_id"],
    }, t["description"], False)
    created.append(f"content/talks/{tid}/")
    return created, notes


# --- Trello ---

def auth_header():
    key, token = os.environ.get("TRELLO_KEY"), os.environ.get("TRELLO_TOKEN")
    if not key or not token:
        raise CardError("Не заданы TRELLO_KEY и TRELLO_TOKEN в секретах репозитория.")
    return {"Authorization": f'OAuth oauth_consumer_key="{key}", oauth_token="{token}"'}


def http(url, data=None, method=None):
    req = urllib.request.Request(url, data=data, method=method, headers=auth_header())
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def card_code(card):
    """Ссылка trello.com/c/<код>/… или сам код."""
    m = re.search(r"trello\.com/c/([A-Za-z0-9]+)", card)
    return m.group(1) if m else card.strip()


def fetch_card(code):
    query = urllib.parse.urlencode({"fields": "name,desc,shortUrl,shortLink", "attachments": "true",
                                    "attachment_fields": "name,url,date"})
    return json.loads(http(f"{API}/cards/{code}?{query}"))


def fetch_photos(card):
    """Последнее по дате вложение speaker-N.* для каждого N; JPEG или PNG по содержимому."""
    latest = {}
    for a in sorted(card.get("attachments", []), key=lambda a: a.get("date", "")):
        m = PHOTO.match(a.get("name", ""))
        if m:
            latest[int(m.group(1))] = a
    photos = {}
    for number, a in latest.items():
        data = http(a["url"])
        if data[:3] == b"\xff\xd8\xff":
            photos[number] = (data, "jpg")
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            photos[number] = (data, "png")
        else:
            raise CardError(f"Вложение {a['name']} — не JPEG и не PNG.")
    return photos


def comment(code, text):
    http(f"{API}/cards/{code}/actions/comments", data=urllib.parse.urlencode({"text": text}).encode(), method="POST")


# --- запуск ---

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="создать страницы по карточке")
    b.add_argument("--card", required=True)
    b.add_argument("--summary", required=True, help="куда записать итог в JSON")
    c = sub.add_parser("comment", help="комментарий в карточку")
    c.add_argument("--card", required=True)
    c.add_argument("--text", required=True)
    args = ap.parse_args()

    code = card_code(args.card)
    if args.cmd == "comment":
        comment(code, args.text)
        return

    summary = {"card": code, "cardUrl": f"https://trello.com/c/{code}", "title": code}
    try:
        card = fetch_card(code)
        summary.update(cardUrl=card.get("shortUrl", summary["cardUrl"]), title=card.get("name", code))
        parsed = parse_card(card.get("desc", ""))
        summary["title"] = parsed["talk"]["title"]
        summary["cfp_id"] = parsed["cfp_id"] or code
        with open(os.path.join(ROOT, "data", "conference.yaml"), encoding="utf-8") as fh:
            season = yaml.safe_load(fh)["season"]
        created, notes = build(parsed, fetch_photos(card), CONTENT, season)
        summary.update(ok=True, branch=f"cfp/{summary['cfp_id']}", created=created, notes=notes,
                       speakers=[s["name"] for s in parsed["speakers"]])
    except CardError as e:
        summary.update(ok=False, error=str(e))
    except Exception as e:  # сеть, Trello, диск — тоже в карточку и в чат
        summary.update(ok=False, error=f"сбой сборки: {e}")
    with open(args.summary, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.exit(0 if summary["ok"] else 2)


if __name__ == "__main__":
    main()
