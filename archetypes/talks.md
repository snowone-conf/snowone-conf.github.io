---
# Новый доклад: hugo new talks/<короткий-slug>/index.ru.md
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
format: talk            # talk | conversation | workshop | keynote
speakers: []            # имена папок из content/persons/
hosts: []
language: ru            # ru | en
day: 1                  # номер дня из data/conference.yaml
start: 2027-02-27T16:00:00+07:00   # местное (новосибирское) время
end: 2027-02-27T17:00:00+07:00
track: 1                # номер трека (зала) из data/conference.yaml
hall: Большой конференц-зал
summary: ""
slides: ""              # ссылка на PDF в GitHub Releases (slides-<год>)
video: []
season: 2027
draft: true
---
Подробное описание доклада (Markdown).
