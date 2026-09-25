// Аналитика для замороженных страниц архива (/archive/...). Генерируется Hugo
// из params.yandexMetrikaId в hugo.yaml; страницы Hugo подключают счётчик сами.
{{- with site.Params.yandexMetrikaId }}
(function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};m[i].l=1*new Date();
k=e.createElement(t);a=e.getElementsByTagName(t)[0];k.async=1;k.src=r;a.parentNode.insertBefore(k,a)})
(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");
ym({{ . }},"init",{clickmap:true,trackLinks:true,accurateTrackBounce:true});
{{- end }}
