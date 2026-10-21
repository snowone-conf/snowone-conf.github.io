#!/usr/bin/env python3
"""Публикация на сайте из карточки Trello — для workflow cfp-accept.

    python3 tools/cfp_from_trello.py run --card <ссылка или код> --mode speaker|talk [--update] [--recreate]
        [--from talk|speaker] [--by "Имя"] --summary out.json
    python3 tools/cfp_from_trello.py comment --card <код> --text "…"

Карточку заполняет сервис cfp-function по шаблону, а программный комитет правит её во время
обсуждения. Шаблон и правила разбора — docs/schema.md репозитория cfp-function (§3, §4).

Режимы (колонки Trello):
  speaker — «Опубликовали спикера»: только страница спикера content/persons/<имя-фамилия>/ с season:
            спикер появляется на главной, на его странице — «описание выступления появится позже»;
  talk    — «Опубликовали доклад»: выступление content/talks/<спикер>---<название>/ (без draft и
            без расписания) и спикер, если его ещё нет на сайте.
Скрипт сначала решает, нужно ли что-то собирать (PR уже открыт, доклад уже на сайте, ошибочный
перенос…), и пишет решение в --summary (JSON): action = build | skip, данные для PR и для
сообщения в чат ПК (kind, reason, …). Тексты сообщений собирает сервис cfp-function.

Ключ и токен Trello — из переменных окружения TRELLO_KEY и TRELLO_TOKEN; открытые PR — через gh.
"""
import argparse
import glob
import json
import os
import re
import subprocess
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


def missing_section(name):
    return CardError(f"Не нашёл раздел «## {name}» в описании карточки. Верните заголовок из шаблона.")


def parse_talk(fields, subs):
    raw_format = required(fields.get("формат", ""), "Формат", "Выступление")
    fmt = raw_format.lower()
    if fmt in ("другое", "other"):
        raise CardError(f"Формат «Другое» нужно заменить на один из: {FORMAT_CHOICES}.")
    if fmt not in FORMATS:
        raise CardError(f"Формат «{raw_format}» не распознан. Допустимо: {FORMAT_CHOICES}.")
    raw_lang = required(fields.get("язык", ""), "Язык", "Выступление")
    if raw_lang.lower() not in LANGUAGES:
        raise CardError(f"Язык «{raw_lang}» не распознан. Допустимо: Русский, English.")
    return {
        "title": required(fields.get("название", ""), "Название", "Выступление"),
        "format": FORMATS[fmt],
        "language": LANGUAGES[raw_lang.lower()],
        "summary": " ".join(required(subs.get("кратко", ""), "Кратко", "Выступление").split()),
        "description": paragraphs(required(subs.get("подробно", ""), "Подробно", "Выступление")),
    }


def parse_card(desc, mode="talk"):
    """Описание карточки → {talk, speakers, cfp_id}. В режиме speaker раздел «Выступление» не проверяется
    (тема может быть ещё не готова), talk = None. Ошибки — CardError с текстом из схемы."""
    desc = unescape(desc.replace("\r\n", "\n"))
    secs = sections(desc)
    if mode == "talk" and "выступление" not in secs:
        raise missing_section("Выступление")
    if "спикер" not in secs:
        raise missing_section("Спикер")
    talk = parse_talk(*secs["выступление"]) if mode == "talk" else None

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


# --- что уже есть на сайте ---

def front(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---"):
        return {}
    return yaml.safe_load(text.split("---", 2)[1]) or {}


def known_persons(content):
    """Имя (в нижнем регистре) → {id, path, season}: у спикеров прошлых лет папки — хеши, искать можно только по имени."""
    out = {}
    for f in sorted(glob.glob(os.path.join(content, "persons", "*", "index.ru.md"))):
        fm = front(f)
        title = str(fm.get("title", "")).strip().lower()
        if title and title not in out:
            out[title] = {"id": os.path.basename(os.path.dirname(f)), "path": f, "season": fm.get("season")}
    return out


def published_talks(content, cfp_id):
    """Папки выступлений с этим номером заявки."""
    if not cfp_id:
        return []
    return [f"content/talks/{os.path.basename(os.path.dirname(f))}/"
            for f in sorted(glob.glob(os.path.join(content, "talks", "*", "index.ru.md")))
            if str(front(f).get("cfp_id", "")) == cfp_id]


def speakers_published(card, content, season):
    """Все спикеры карточки уже на сайте и отмечены в этом сезоне."""
    known = known_persons(content)
    return all((known.get(sp["name"].lower()) or {}).get("season") == season for sp in card["speakers"])


# --- решение ---

def decide(mode, update, recreate, talk_paths, speakers_done, speaker_pr, talk_pr):
    """Что делать с карточкой. Возвращает {action: build|skip, kind, reason, pr_url}.
    speaker_pr / talk_pr — ссылки на открытые PR этой заявки (или пустые строки)."""
    def skip(kind, reason="", pr=""):
        return {"action": "skip", "kind": kind, "reason": reason, "pr_url": pr}

    def build(pr=""):
        return {"action": "build", "kind": "pr-updated" if update else "pr-ready", "reason": "", "pr_url": pr}

    own_pr = speaker_pr if mode == "speaker" else talk_pr
    if update:
        # Правка описания: пересобираем только открытый PR своего режима
        if own_pr and not (mode == "speaker" and (talk_paths or talk_pr)):
            return build(own_pr)
        return skip("warning", "update-no-pr")
    if mode == "speaker":
        if talk_paths:
            return skip("warning", "talk-published")
        if talk_pr:
            return skip("warning", "talk-pr-open", talk_pr)
        if speaker_pr:
            return build(speaker_pr) if recreate else skip("pr-exists", pr=speaker_pr)
        if speakers_done:
            return skip("warning", "speaker-published")
        return build()
    if talk_paths:
        return skip("warning", "talk-already")
    if talk_pr:
        return build(talk_pr) if recreate else skip("pr-exists", pr=talk_pr)
    return build()


# --- страницы ---

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


def mark_season(path, season):
    """Добавляет season в frontmatter существующей персоны, не трогая остальное."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head, sep, rest = text[3:].partition("\n---")
    head = re.sub(r"^season:.*\n?", "", head, flags=re.M).rstrip("\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("---" + head + f"\nseason: {season}" + sep + rest)


FILLABLE = {"company": "компания", "position": "должность"}


def fill_missing(path, sp):
    """Дополняет существующую персону пустыми у неё полями из карточки: компания, должность, текст «О себе».
    Заполненное, фото и остальной файл не меняются. → названия дополненных полей."""
    fm = front(path)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    head, sep, rest = text[3:].partition("\n---")
    filled = []
    for key, label in FILLABLE.items():
        if sp.get(key) and not str(fm.get(key) or "").strip():
            line = yaml.safe_dump({key: sp[key]}, allow_unicode=True, width=10000).strip()
            head = re.sub(rf"^{key}:.*\n?", "", head, flags=re.M).rstrip("\n") + "\n" + line
            filled.append(label)
    body = rest.partition("\n")[2] if rest.startswith("\n") else rest
    if sp.get("bio") and not body.strip():
        rest = "\n\n" + sp["bio"].strip() + "\n"
        filled.append("«О себе»")
    if filled:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("---" + head + sep + rest)
    return filled


def build_persons(card, photos, content, season, mode):
    """Страницы спикеров. Новые персоны получают season; уже известным (выступали раньше) пустые компания,
    должность и «О себе» дополняются из карточки, а в режиме speaker дописывается season; заполненное и фото
    не меняются. → (ids, изменения, заметки)"""
    notes, changed, ids = [], [], []
    persons_dir = os.path.join(content, "persons")
    known = known_persons(content)
    for sp in card["speakers"]:
        existing = known.get(sp["name"].lower())
        if existing:
            ids.append(existing["id"])
            rel = f"content/persons/{existing['id']}/"
            if existing["season"] == season:
                continue
            filled = fill_missing(existing["path"], sp)
            notes.append(f"Спикер «{sp['name']}» уже есть на сайте ({rel}): проверьте, тот ли это человек"
                         + (f"; из карточки дополнено: {', '.join(filled)}" if filled else "")
                         + ". Заполненные раньше поля и фото не менялись — при необходимости обновите вручную.")
            if mode == "speaker":
                mark_season(existing["path"], season)
            if mode == "speaker" or filled:
                changed.append(rel)
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
            "season": season,
            "contacts": site_contacts(sp),
        }, sp["bio"], False)
        ids.append(pid)
        changed.append(f"content/persons/{pid}/")
    return ids, changed, notes


def build(card, photos, content, season, mode="talk"):
    """Создаёт страницы режима; photos — {номер спикера: (байты, расширение)}. → (изменения, заметки)"""
    ids, changed, notes = build_persons(card, photos, content, season, mode)
    if mode == "speaker":
        return changed, notes
    t = card["talk"]
    talks_dir = os.path.join(content, "talks")
    slug = f"{ids[0]}---{slugify(t['title'])}"
    tid = free_dir(talks_dir, slug)
    if tid != slug:
        notes.append(f"Папка content/talks/{slug}/ уже занята, выступление записано в {tid}/.")
    write_md(os.path.join(talks_dir, tid, "index.ru.md"), {
        "title": t["title"],
        "format": t["format"],
        "speakers": ids,
        "language": t["language"],
        "summary": t["summary"],
        "season": season,
        "cfp_id": card["cfp_id"],
    }, t["description"], False)
    changed.append(f"content/talks/{tid}/")
    return changed, notes


# --- Trello и GitHub ---

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


def open_pr(branch):
    """Ссылка на открытый PR из ветки или пустая строка."""
    out = subprocess.run(["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "url",
                          "--jq", ".[0].url // \"\""], capture_output=True, text=True, check=True)
    return out.stdout.strip()


# --- запуск ---

def run(args, content=CONTENT):
    code = card_code(args.card)
    s = {"card": code, "cardUrl": f"https://trello.com/c/{code}", "title": code, "mode": args.mode,
         "from": args.from_list, "by": args.by, "update": args.update, "notes": [], "created": [], "paths": []}
    try:
        card = fetch_card(code)
        s.update(cardUrl=card.get("shortUrl", s["cardUrl"]), title=card.get("name", code))
        parsed = parse_card(card.get("desc", ""), args.mode)
        cfp_id = parsed["cfp_id"] or code
        if parsed["talk"]:
            s["title"] = parsed["talk"]["title"]
        s["speakers"] = [sp["name"] for sp in parsed["speakers"]]
        with open(os.path.join(ROOT, "data", "conference.yaml"), encoding="utf-8") as fh:
            season = yaml.safe_load(fh)["season"]
        branches = {m: f"cfp/{cfp_id}-{m}" for m in ("speaker", "talk")}
        prs = {m: open_pr(b) for m, b in branches.items()}
        talk_paths = published_talks(content, parsed["cfp_id"])
        verdict = decide(args.mode, args.update, args.recreate, talk_paths,
                         speakers_published(parsed, content, season), prs["speaker"], prs["talk"])
        s.update(cfp_id=cfp_id, branch=branches[args.mode], action=verdict["action"], kind=verdict["kind"],
                 reason=verdict["reason"], prUrl=verdict["pr_url"], paths=talk_paths)
        if verdict["reason"] == "update-no-pr" and args.mode == "speaker" and not talk_paths:
            known = known_persons(content)
            s["paths"] = [f"content/persons/{known[n.lower()]['id']}/" for n in s["speakers"] if n.lower() in known]
        if verdict["action"] == "build":
            s["created"], s["notes"] = build(parsed, fetch_photos(card), content, season, args.mode)
            if args.mode == "talk" and prs["speaker"]:
                s["supersede"] = prs["speaker"]
        s["ok"] = True
    except CardError as e:
        s.update(ok=False, kind="error", message=str(e))
    except Exception as e:  # сеть, Trello, gh, диск — тоже в карточку и в чат
        s.update(ok=False, kind="error", message=f"сбой сборки: {e}")
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="решить и при необходимости создать страницы по карточке")
    r.add_argument("--card", required=True)
    r.add_argument("--mode", choices=("speaker", "talk"), required=True)
    r.add_argument("--update", action="store_true", help="запуск по правке описания карточки")
    r.add_argument("--recreate", action="store_true", help="пересобрать открытый PR")
    r.add_argument("--from", dest="from_list", default="", help="колонка до переноса: speaker, talk или пусто")
    r.add_argument("--by", default="", help="кто перенёс или поправил карточку")
    r.add_argument("--summary", required=True, help="куда записать итог в JSON")
    c = sub.add_parser("comment", help="комментарий в карточку")
    c.add_argument("--card", required=True)
    c.add_argument("--text", required=True)
    args = ap.parse_args()

    if args.cmd == "comment":
        comment(card_code(args.card), args.text)
        return
    summary = run(args)
    with open(args.summary, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    sys.exit(0 if summary["ok"] else 2)


if __name__ == "__main__":
    main()
