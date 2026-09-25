# Локальная работа с сайтом. Нужны: Hugo extended (версия в .hugo-version), Python 3 + PyYAML.

.PHONY: serve build check import archive snapshot clean

serve:            ## локальный сервер с live-reload: http://localhost:1313
	hugo server -D --disableFastRender

build:            ## полная сборка в public/
	hugo --gc --minify

check:            ## то же, что проверяет CI: целостность контента + строгая сборка
	python3 tools/check_refs.py
	hugo --gc --minify --panicOnWarning --destination /tmp/snowone-check >/dev/null && echo "hugo: ok"

import:           ## (разово) перенести данные сезона из snapshot/ в content/ и data/ (не перезаписывает)
	python3 tools/import_nextdata.py

archive:          ## обновить замороженный архив в static/ из snapshot/
	python3 tools/freeze_archive.py

snapshot:         ## заново снять копию старого сайта (нужен доступ к snowone.ru)
	rm -rf snapshot && python3 tools/mirror.py snapshot

clean:
	rm -rf public resources/_gen
