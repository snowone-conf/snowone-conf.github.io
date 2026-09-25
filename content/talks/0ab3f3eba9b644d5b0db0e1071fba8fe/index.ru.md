---
title: 'Deep Dive into JVM JDI: Capturing Live Execution for Automatic JUnit Test Generation'
format: talk
speakers:
- e6d2f30de02643beb583279cd9d68bcb
language: ru
day: 2
start: '2026-02-28T14:00:00+07:00'
end: '2026-02-28T15:00:00+07:00'
track: 1
hall: Большой конференц-зал
order: 50
summary: <p>Глубокий технический разбор архитектуры инструмента, который использует Java Debug Interface (JDI) для захвата состояния работающей JVM и автоматического синтеза валидных unit-тестов.</p>
slides: https://github.com/snowone-conf/snowone-conf.github.io/releases/download/slides-2026/14-00-daniil-stepanov.pdf
season: 2026
---
<p>Глубокий технический разбор архитектуры инструмента, который использует Java Debug Interface (JDI) для захвата состояния работающей JVM и автоматического синтеза валидных unit-тестов.</p>
<p>Что будет в докладе:</p>
<ul>
<li>Deep Dive в JDI. Подробный рассказ про JDI, преимущества и недостатки, а также как его использовать в нестандартных сценариях для безопасного захвата Heap и Stack Frame в реальном времени.</li>
<li>Реконструкция объектов. Reverse Engineering JVM-состояния для воссоздания сложных графов объектов.</li>
<li>Синтез Java-кода. Как превратить сырой дамп памяти в чистый, валидный JUnit-тест.</li>
<li>Роль LLM. Для решения каких проблем мы используем искусственный интеллект?</li>
</ul>
<p>Доклад будет полезен Java-разработчикам, интересующимся внутренним устройством JVM, и всем, кто хочет автоматизировать написание тестов.</p>
<p>Технологии: Java, JVM, JDI (Java Debug Interface), Mockito, JUnit, LLM.</p>
