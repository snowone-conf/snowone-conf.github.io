# Локальная работа с сайтом. Нужны: Hugo extended (версия в .hugo-version), Python 3 + PyYAML.

.PHONY: serve build check test import-cfp import archive snapshot clean

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

import:           ## (разово, нужна папка snapshot/) перенести данные сезона из snapshot/ в content/ и data/ (не перезаписывает)
	python3 tools/import_nextdata.py

archive:          ## (нужна папка snapshot/) обновить замороженный архив в static/
	python3 tools/freeze_archive.py

snapshot:         ## заново снять копию старого сайта (нужен доступ к snowone.ru)
	rm -rf snapshot && python3 tools/mirror.py snapshot

clean:
	rm -rf public resources/_gen
