---
# Новый докладчик: hugo new persons/<имя-фамилия>/index.ru.md, фото положить рядом как photo.jpg
title: "{{ replace .File.ContentBaseName "-" " " | title }}"
company: ""
position: ""
photo: photo.jpg
weight: 100             # порядок в списках спикеров
contacts: []            # - {type: telegram|github|website, url: https://...}
draft: true
---
Биография (Markdown).
