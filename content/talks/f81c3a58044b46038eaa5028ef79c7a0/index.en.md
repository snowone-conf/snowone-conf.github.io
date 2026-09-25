---
title: The Valhalla Project, or How to Add Value Types to Java Without Turning It into C++
format: talk
speakers:
- 9cbc880fd47843e29e543fd37f95bbef
language: ru
day: 2
start: '2026-02-28T16:50:00+07:00'
end: '2026-02-28T17:50:00+07:00'
track: 1
hall: Большой конференц-зал
order: 100
summary: |-
  <p>Let's talk about how to change the Java language and its implementation in order to open the way for efficient scalarization and inline of objects into other objects, but not turn Java into C++.</p>
  <p>Let's discuss why it might be more important to invest in the versatile development of the language itself, rather than immediately go ahead and implement a specific (albeit very important) feature in the compiler and runtime.</p>
slides: https://github.com/snowone-conf/snowone-conf.github.io/releases/download/slides-2026/16-50-ivan-uglyanskii-.pdf
season: 2026
---
<p>The Valhalla project is an epic long-term construction project that began back in 2014. Since that time, within the framework of this project, one has been trying to add value classes to Java, which was supposed to open the way for effective scalarization and inline of objects into other objects, but in fact it turned into a huge refactoring of the entire JVM.</p>
<p>Along the way, various approaches to supporting value classes were adopted and rejected, countless prototypes were created, and more and more new JEPs were discovered, but value classes still did not appear. Finally, last year there was a breakthrough, and a new (much simpler!) approach to implementing value classes has given us hope for a speedy completion of the project.</p>
<p>In the talk, we will recall what value classes are in general and why they are needed in Java, in what tasks they will be useful; we will also look at the old and now rejected approaches to their implementation and appreciate the beauty and elegance of the latest solution.</p>
