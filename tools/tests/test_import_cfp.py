"""Тесты tools/import_cfp.py на вымышленной выгрузке: python3 -m unittest discover tools/tests"""
import contextlib
import glob
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import import_cfp  # noqa: E402

FIXTURE = os.path.join(HERE, "cfp_export.csv")


class ImportCfpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._content = import_cfp.CONTENT
        import_cfp.CONTENT = self.tmp

    def tearDown(self):
        import_cfp.CONTENT = self._content
        shutil.rmtree(self.tmp)

    def run_import(self, path, *extra):
        argv = sys.argv
        sys.argv = ["import_cfp.py", path, "--no-photos", "--season", "2027", *extra]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                import_cfp.main()
        finally:
            sys.argv = argv

    def files(self):
        out = {}
        for f in sorted(glob.glob(os.path.join(self.tmp, "**", "*.md"), recursive=True)):
            with open(f, encoding="utf-8") as fh:
                out[os.path.relpath(f, self.tmp)] = fh.read()
        return out

    def test_creates_drafts(self):
        self.run_import(FIXTURE)
        files = self.files()
        self.assertIn("persons/testovyi-dokladchik/index.ru.md", files)
        self.assertIn("persons/vtoroi-primer/index.ru.md", files)
        self.assertIn("persons/jane-example/index.ru.md", files)
        talk = files["talks/101-virtualnye-potoki-na-praktike/index.ru.md"]
        self.assertIn("draft: true", talk)
        self.assertIn("season: 2027", talk)
        self.assertIn("- testovyi-dokladchik\n- vtoroi-primer", talk)
        self.assertIn("Первый абзац.\n\nВторой абзац.", talk)
        en = files["talks/102-graalvm-native-image/index.ru.md"]
        self.assertIn("language: en", en)
        self.assertIn("format: workshop", en)
        person = files["persons/testovyi-dokladchik/index.ru.md"]
        self.assertIn("url: https://t.me/test_speaker", person)

    def test_private_fields_not_exported(self):
        self.run_import(FIXTURE)
        everything = "\n".join(self.files().values())
        for secret in ("secret@example.com", "jane@example.com", "+79990000000", "слабый доклад"):
            self.assertNotIn(secret, everything)

    def test_idempotent(self):
        self.run_import(FIXTURE)
        first = self.files()
        path = os.path.join(self.tmp, "talks/101-virtualnye-potoki-na-praktike/index.ru.md")
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("правка редактора\n")
        self.run_import(FIXTURE)
        second = self.files()
        self.assertEqual(set(first), set(second))
        self.assertIn("правка редактора", second["talks/101-virtualnye-potoki-na-praktike/index.ru.md"])

    def test_only(self):
        self.run_import(FIXTURE, "--only", "102")
        self.assertEqual([f for f in self.files() if f.startswith("talks/")], ["talks/102-graalvm-native-image/index.ru.md"])

    def test_xlsx(self):
        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl не установлен")
        rows = import_cfp.read_rows(FIXTURE)
        wb = Workbook()
        ws = wb.active
        ws.append(list(rows[0].keys()))
        for r in rows:
            ws.append(list(r.values()))
        path = os.path.join(self.tmp, "export.xlsx")
        wb.save(path)
        self.run_import(path)
        self.assertIn("talks/101-virtualnye-potoki-na-praktike/index.ru.md", self.files())


if __name__ == "__main__":
    unittest.main()
