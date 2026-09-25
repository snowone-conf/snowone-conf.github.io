# Локальная работа с сайтом. Нужны: Hugo extended (версия в .hugo-version), Python 3 + PyYAML.

.PHONY: serve build check test import-cfp clean

serve:            ## локальный сервер с live-reload: http://localhost:1313
	hugo server -D --disableFastRender

build:            ## полная сборка в public/
	hugo --gc --minify

check:            ## то же, что проверяет CI: целостность контента + строгая сборка
	python3 tools/check_refs.py
	hugo --gc --minify --panicOnWarning --destination /tmp/snowone-check >/dev/null && echo "hugo: ok"

test:             ## тесты служебных скриптов
	python3 -m unittest discover -s tools/tests

import-cfp:       ## черновики докладов из выгрузки Яндекс Форм: make import-cfp FILE=export.xlsx [ARGS="--only 12,15"]
	python3 tools/import_cfp.py "$(FILE)" $(ARGS)

clean:
	rm -rf public resources/_gen
