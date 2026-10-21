"""Тесты tools/cfp_from_trello.py: разбор карточки по шаблону и страницы сайта (без обращения к Trello)."""
import glob
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import cfp_from_trello as cft  # noqa: E402

# Пример карточки из docs/schema.md (cfp-function), §3
CARD = """## Выступление
Название: Виртуальные потоки в продакшене
Формат: Доклад
Пояснение к формату:
Язык: Русский

### Кратко
Как мы перевели сервисы на виртуальные потоки
и что сломалось по дороге.

### Подробно
Подробное описание…

Второй абзац…

## Спикер
Имя: Иван Иванов
Компания: Компания
Должность или род деятельности: Ведущий разработчик
Город: Новосибирск
Сайт: https://ivanov.pro/
GitHub: https://github.com/ivanov

### О спикере
О себе…

### Прошлые выступления
- https://example.com/talks/loom

## Комментарий для ПК
Могу сделать и воркшоп.

---
Заявка 20261013-k7q2 · подана 13.10.2026"""

SECOND = """
## Спикер 2
Имя: Пётр Петров
Компания:
Должность или род деятельности: Архитектор
Город: Томск
Сайт:
GitHub: petrov

### О спикере
Био Петра.
"""

JPEG = b"\xff\xd8\xff\xe0 photo"


def with_second(card=CARD):
    head, tail = card.split("## Комментарий для ПК")
    return head + SECOND.lstrip("\n") + "\n## Комментарий для ПК" + tail


class ParseTest(unittest.TestCase):
    def test_schema_example(self):
        card = cft.parse_card(CARD)
        self.assertEqual(card["cfp_id"], "20261013-k7q2")
        self.assertEqual(card["talk"], {
            "title": "Виртуальные потоки в продакшене",
            "format": "talk",
            "language": "ru",
            "summary": "Как мы перевели сервисы на виртуальные потоки и что сломалось по дороге.",
            "description": "Подробное описание…\n\nВторой абзац…",
        })
        sp = card["speakers"][0]
        self.assertEqual(sp["name"], "Иван Иванов")
        self.assertEqual(sp["position"], "Ведущий разработчик")
        self.assertEqual(sp["bio"], "О себе…")
        self.assertEqual(len(card["speakers"]), 1)

    def test_edits_of_program_committee(self):
        card = cft.parse_card(with_second(CARD.replace("Формат: Доклад", "формат:  Ключевой доклад")
                                          .replace("Язык: Русский", "Язык: English")
                                          .replace("Название: Виртуальные", "Название: C\\# и виртуальные")))
        self.assertEqual(card["talk"]["format"], "keynote")
        self.assertEqual(card["talk"]["language"], "en")
        self.assertEqual(card["talk"]["title"], "C# и виртуальные потоки в продакшене")
        self.assertEqual([s["name"] for s in card["speakers"]], ["Иван Иванов", "Пётр Петров"])
        self.assertEqual(card["speakers"][1]["number"], 2)

    def assertCardError(self, card, text):
        with self.assertRaises(cft.CardError) as ctx:
            cft.parse_card(card)
        self.assertEqual(str(ctx.exception), text)

    def test_errors_from_schema(self):
        self.assertCardError(CARD.replace("## Выступление", "## Доклад"),
                             "Не нашёл раздел «## Выступление» в описании карточки. Верните заголовок из шаблона.")
        self.assertCardError(CARD.replace("## Спикер\n", "## Автор\n"),
                             "Не нашёл раздел «## Спикер» в описании карточки. Верните заголовок из шаблона.")
        self.assertCardError(CARD.replace("Название: Виртуальные потоки в продакшене", "Название:"),
                             "Не заполнено поле «Название» в разделе «Выступление».")
        self.assertCardError(CARD.replace("Формат: Доклад", "Формат: Другое"),
                             "Формат «Другое» нужно заменить на один из: Доклад, Воркшоп, Обсуждение, Ключевой доклад.")
        self.assertCardError(CARD.replace("Формат: Доклад", "Формат: Мастер-класс"),
                             "Формат «Мастер-класс» не распознан. Допустимо: Доклад, Воркшоп, Обсуждение, Ключевой доклад.")
        self.assertCardError(CARD.replace("Язык: Русский", "Язык: Немецкий"),
                             "Язык «Немецкий» не распознан. Допустимо: Русский, English.")
        self.assertCardError(CARD.replace("Должность или род деятельности: Ведущий разработчик\n", ""),
                             "Не заполнено поле «Должность или род деятельности» в разделе «Спикер».")
        self.assertCardError(CARD.replace("О себе…", ""), "Не заполнено поле «О спикере» в разделе «Спикер».")

    def test_text_after_separator_is_ignored(self):
        card = cft.parse_card(CARD + "\n## Спикер 2\nИмя: Не читается")
        self.assertEqual(len(card["speakers"]), 1)

    def test_speaker_mode_does_not_need_talk(self):
        without_talk = CARD.split("## Спикер\n", 1)[1]
        card = cft.parse_card("## Спикер\n" + without_talk, "speaker")
        self.assertIsNone(card["talk"])
        self.assertEqual(card["speakers"][0]["name"], "Иван Иванов")
        self.assertEqual(card["cfp_id"], "20261013-k7q2")
        self.assertCardError(CARD.replace("Формат: Доклад", "Формат: Другое"),
                             "Формат «Другое» нужно заменить на один из: Доклад, Воркшоп, Обсуждение, Ключевой доклад.")
        cft.parse_card(CARD.replace("Формат: Доклад", "Формат: Другое"), "speaker")  # в режиме speaker не важно
        with self.assertRaises(cft.CardError):
            cft.parse_card(without_talk, "speaker")

    def test_card_code(self):
        self.assertEqual(cft.card_code("https://trello.com/c/AbCd1234/12-i-ivanov"), "AbCd1234")
        self.assertEqual(cft.card_code(" AbCd1234 "), "AbCd1234")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "persons"))
        os.makedirs(os.path.join(self.tmp, "talks"))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def read(self, rel):
        with open(os.path.join(self.tmp, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_pages_without_schedule_and_contacts(self):
        created, notes = cft.build(cft.parse_card(CARD), {1: (JPEG, "jpg")}, self.tmp, 2027)
        self.assertEqual(created, ["content/persons/ivan-ivanov/",
                                   "content/talks/ivan-ivanov---virtualnye-potoki-v-prodakshene/"])
        self.assertEqual(notes, [])
        talk = self.read("talks/ivan-ivanov---virtualnye-potoki-v-prodakshene/index.ru.md")
        self.assertIn("speakers:\n- ivan-ivanov\n", talk)
        self.assertIn("season: 2027\ncfp_id: 20261013-k7q2\n", talk)
        self.assertIn("Подробное описание…\n\nВторой абзац…", talk)
        for absent in ("draft", "day:", "start:", "track:", "hall:", "воркшоп"):
            self.assertNotIn(absent, talk)
        person = self.read("persons/ivan-ivanov/index.ru.md")
        self.assertIn("title: Иван Иванов\ncompany: Компания\nposition: Ведущий разработчик\nphoto: photo.jpg\n"
                      "weight: 100\nseason: 2027\n", person)
        self.assertIn("url: https://ivanov.pro/", person)
        self.assertIn("url: https://github.com/ivanov", person)
        self.assertNotIn("Новосибирск", person)
        self.assertNotIn("loom", person)
        with open(os.path.join(self.tmp, "persons/ivan-ivanov/photo.jpg"), "rb") as fh:
            self.assertEqual(fh.read(), JPEG)

    def test_returning_speaker_and_busy_talk_folder(self):
        old = os.path.join(self.tmp, "persons", "e6d2f30de02643beb583279cd9d68bcb")
        os.makedirs(old)
        with open(os.path.join(old, "index.ru.md"), "w", encoding="utf-8") as fh:
            fh.write("---\ntitle: Иван Иванов\n---\nСтарая биография\n")
        os.makedirs(os.path.join(self.tmp, "talks", "e6d2f30de02643beb583279cd9d68bcb---virtualnye-potoki-v-prodakshene"))
        created, notes = cft.build(cft.parse_card(CARD), {}, self.tmp, 2027)
        self.assertEqual(created, ["content/persons/e6d2f30de02643beb583279cd9d68bcb/",
                                   "content/talks/e6d2f30de02643beb583279cd9d68bcb---virtualnye-potoki-v-prodakshene-2/"])
        self.assertEqual(len(notes), 2)
        self.assertIn("уже есть на сайте", notes[0])
        self.assertIn("из карточки дополнено: компания, должность.", notes[0])
        self.assertIn("-2/", notes[1])
        self.assertEqual(self.read("persons/e6d2f30de02643beb583279cd9d68bcb/index.ru.md"),
                         "---\ntitle: Иван Иванов\ncompany: Компания\nposition: Ведущий разработчик\n---\nСтарая биография\n")

    def test_second_speaker_and_missing_photo(self):
        card = cft.parse_card(with_second())
        with self.assertRaises(cft.CardError) as ctx:
            cft.build(card, {1: (JPEG, "jpg")}, self.tmp, 2027)
        self.assertEqual(str(ctx.exception), "У спикера «Пётр Петров» нет фото: приложите вложение speaker-2.jpg.")
        shutil.rmtree(os.path.join(self.tmp, "persons"))
        os.makedirs(os.path.join(self.tmp, "persons"))
        created, _ = cft.build(card, {1: (JPEG, "jpg"), 2: (b"\x89PNG\r\n\x1a\n", "png")}, self.tmp, 2027)
        self.assertIn("content/persons/petr-petrov/", created)
        talk = glob.glob(os.path.join(self.tmp, "talks", "*", "index.ru.md"))[0]
        with open(talk, encoding="utf-8") as fh:
            self.assertIn("speakers:\n- ivan-ivanov\n- petr-petrov\n", fh.read())
        self.assertIn("photo: photo.png", self.read("persons/petr-petrov/index.ru.md"))
        self.assertIn("url: https://github.com/petrov", self.read("persons/petr-petrov/index.ru.md"))


class SpeakerModeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "persons"))
        os.makedirs(os.path.join(self.tmp, "talks"))
        self.card = cft.parse_card(CARD, "speaker")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_new_speaker_only(self):
        changed, notes = cft.build(self.card, {1: (JPEG, "jpg")}, self.tmp, 2027, "speaker")
        self.assertEqual(changed, ["content/persons/ivan-ivanov/"])
        self.assertEqual(notes, [])
        self.assertEqual(os.listdir(os.path.join(self.tmp, "talks")), [])
        self.assertTrue(cft.speakers_published(self.card, self.tmp, 2027))
        self.assertFalse(cft.speakers_published(self.card, self.tmp, 2028))

    def test_returning_speaker_gets_season_and_missing_fields(self):
        old = os.path.join(self.tmp, "persons", "e6d2f30de02643beb583279cd9d68bcb")
        os.makedirs(old)
        original = "---\ntitle: Иван Иванов\nweight: 200\nseason: 2026\nphoto: photo.png\n---\n<p>Старая биография</p>\n"
        with open(os.path.join(old, "index.ru.md"), "w", encoding="utf-8") as fh:
            fh.write(original)
        changed, notes = cft.build(self.card, {}, self.tmp, 2027, "speaker")
        self.assertEqual(changed, ["content/persons/e6d2f30de02643beb583279cd9d68bcb/"])
        self.assertIn("уже есть на сайте", notes[0])
        with open(os.path.join(old, "index.ru.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), original.replace("season: 2026\n", "").replace(
                "photo: photo.png\n", "photo: photo.png\ncompany: Компания\nposition: Ведущий разработчик\nseason: 2027\n"))
        self.assertTrue(cft.speakers_published(self.card, self.tmp, 2027))

    def test_filled_fields_are_kept_and_empty_bio_is_added(self):
        old = os.path.join(self.tmp, "persons", "e6d2f30de02643beb583279cd9d68bcb")
        os.makedirs(old)
        with open(os.path.join(old, "index.ru.md"), "w", encoding="utf-8") as fh:
            fh.write("---\ntitle: Иван Иванов\ncompany: Старая компания\nposition: ''\n---\n")
        changed, notes = cft.build(self.card, {}, self.tmp, 2027, "speaker")
        self.assertIn("из карточки дополнено: должность, «О себе».", notes[0])
        text = self.read_person(old)
        self.assertTrue(text.startswith("---\ntitle: Иван Иванов\ncompany: Старая компания\n"
                                        "position: Ведущий разработчик\nseason: 2027\n---\n\n"), text)
        self.assertIn(self.card["speakers"][0]["bio"].strip(), text)
        self.assertEqual(cft.front(os.path.join(old, "index.ru.md"))["company"], "Старая компания")

    @staticmethod
    def read_person(folder):
        with open(os.path.join(folder, "index.ru.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_published_talks_by_cfp_id(self):
        cft.build(cft.parse_card(CARD), {1: (JPEG, "jpg")}, self.tmp, 2027)
        self.assertEqual(cft.published_talks(self.tmp, "20261013-k7q2"),
                         ["content/talks/ivan-ivanov---virtualnye-potoki-v-prodakshene/"])
        self.assertEqual(cft.published_talks(self.tmp, "20261013-zzzz"), [])
        self.assertEqual(cft.published_talks(self.tmp, ""), [])


class DecideTest(unittest.TestCase):
    PR_S, PR_T = "https://github.com/x/pull/1", "https://github.com/x/pull/2"

    def check(self, expected, mode, update=False, recreate=False, talk_paths=(), done=False, spr="", tpr=""):
        v = cft.decide(mode, update, recreate, list(talk_paths), done, spr, tpr)
        self.assertEqual((v["action"], v["kind"], v["reason"], v["pr_url"]), expected)

    def test_speaker_mode(self):
        self.check(("build", "pr-ready", "", ""), "speaker")
        self.check(("skip", "warning", "speaker-published", ""), "speaker", done=True)
        self.check(("skip", "pr-exists", "", self.PR_S), "speaker", spr=self.PR_S)
        self.check(("build", "pr-ready", "", self.PR_S), "speaker", recreate=True, spr=self.PR_S)
        self.check(("skip", "warning", "talk-pr-open", self.PR_T), "speaker", tpr=self.PR_T)
        self.check(("skip", "warning", "talk-published", ""), "speaker", talk_paths=["content/talks/x/"], done=True)

    def test_talk_mode(self):
        self.check(("build", "pr-ready", "", ""), "talk")
        self.check(("build", "pr-ready", "", ""), "talk", spr=self.PR_S, done=True)  # PR со спикером заменится
        self.check(("skip", "pr-exists", "", self.PR_T), "talk", tpr=self.PR_T)
        self.check(("build", "pr-ready", "", self.PR_T), "talk", recreate=True, tpr=self.PR_T)
        self.check(("skip", "warning", "talk-already", ""), "talk", talk_paths=["content/talks/x/"])

    def test_card_edits(self):
        self.check(("build", "pr-updated", "", self.PR_T), "talk", update=True, tpr=self.PR_T)
        self.check(("build", "pr-updated", "", self.PR_S), "speaker", update=True, spr=self.PR_S)
        self.check(("skip", "warning", "update-no-pr", ""), "talk", update=True)
        self.check(("skip", "warning", "update-no-pr", ""), "talk", update=True, talk_paths=["content/talks/x/"])
        self.check(("skip", "warning", "update-no-pr", ""), "speaker", update=True, done=True)
        self.check(("skip", "warning", "update-no-pr", ""), "speaker", update=True, spr=self.PR_S, tpr=self.PR_T)


if __name__ == "__main__":
    unittest.main()
