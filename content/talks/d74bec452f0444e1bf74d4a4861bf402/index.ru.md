---
title: Айсберг kotlin.coroutines
format: talk
speakers:
- 1ba623dda7574fe8a15e9ace297077b7
- 9053a39cad9f488795b5f3e7df45826d
language: ru
day: 2
start: '2026-02-28T14:00:00+07:00'
end: '2026-02-28T15:00:00+07:00'
track: 3
hall: Конференц-зал №2
order: 50
summary: <p>Пройдемся по всем составным частям корутин в Kotlin, не залезая в kotlnx.coroutines.</p>
season: 2026
---
<p>О чем вы думаете, когда слышите слово «корутина»? Может быть, launch, withContext, coroutineScope? Может быть, по вашему мнению, это «легковесный поток»? Более продвинутые пользователи могут подумать про стейт-машину.</p><p>Пройдемся по всем составным частям корутин в Kotlin, не залезая в kotlinx.coroutines, и поймем, что абсолютно никакой магии в корутинах нет и все механизмы реализованы достаточно просто. В частности, мы рассмотрим, как устроены coroutineContext, Continuation, ContinuationInterceptor, Cancellation и много другого интересного.</p>
