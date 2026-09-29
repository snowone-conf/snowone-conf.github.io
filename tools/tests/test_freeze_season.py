"""Тесты переписывания ссылок в tools/freeze_season.py: python3 -m unittest discover tools/tests"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import freeze_season  # noqa: E402

SECTIONS = ["speakers", "talks", "css", "img/site"]


def rewrite(html):
    return freeze_season.rewrite(html, SECTIONS, "/archive/2026")


class RewriteTest(unittest.TestCase):
    def test_sections_and_home(self):
        self.assertIn('<a href="/archive/2026/speakers/">', rewrite('<a href="/speakers/">'))
        self.assertIn('<a href="/archive/2026/">', rewrite('<a href="/">'))
        self.assertIn('href="/archive/2026/#about"', rewrite('<a href="/#about">'))
        self.assertIn('href="/archive/2026/css/main.css"', rewrite('<link href="/css/main.css">'))

    def test_absolute_urls(self):
        html = rewrite('<link rel="canonical" href="https://snowone.ru/talks/x/"><meta content="https://snowone.ru/">')
        self.assertIn('href="https://snowone.ru/archive/2026/talks/x/"', html)
        self.assertIn('content="https://snowone.ru/archive/2026/"', html)

    def test_srcset_style_and_refresh(self):
        html = rewrite('<img srcset="/speakers/a.jpg 1x, /speakers/b.jpg 2x">'
                       '<div style="--bgImage:url(&quot;/img/site/bg.svg&quot;)"></div>')
        self.assertIn('srcset="/archive/2026/speakers/a.jpg 1x, /archive/2026/speakers/b.jpg 2x"', html)
        self.assertIn('url(&quot;/archive/2026/img/site/bg.svg&quot;)', html)
        self.assertIn('url=/archive/2026/talks/"', rewrite('<meta http-equiv="refresh" content="0; url=/talks/">'))

    def test_untouched(self):
        html = ('<a href="/archive/2025/talks/x/"></a><use href="/img/sprite.svg#info"></use>'
                '<a href="/speakersclub/"></a><a href="/fonts/a.woff2"></a><br /> 1 / 2')
        self.assertEqual(rewrite(html), html)

    def test_analytics(self):
        html = rewrite('<head><script>ym(1);k.src="https://mc.yandex.ru/metrika/tag.js"</script>'
                       '<noscript><img src="https://mc.yandex.ru/watch/1"></noscript></head>')
        self.assertEqual(html, '<head><script src="/analytics.js" defer></script>\n</head>')


if __name__ == "__main__":
    unittest.main()
