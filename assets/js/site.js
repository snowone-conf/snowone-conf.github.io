// Поведение шапки и мелкие интерактивные элементы (замена клиентского кода Next.js).

const MENU_OPENED = 'HeaderNavigation_headerNavigation__menu_opened__G8_7a';
const BUTTON_OPENED = 'MenuButton_menuButton_opened__ldIuw';
const MORE_HIDDEN = 'HeaderNavigation_headerNavigation__more_hidden__9wtfY';
const MORE_ITEM = 'HeaderExpandMenu_headerExpandMenu__item__bOXDI';
const MORE_LINK = 'HeaderExpandMenu_headerExpandMenu__link__Mu9C3';
const DESKTOP = window.matchMedia('(min-width: 1024px)');

function setupMobileMenu(nav) {
  const toggle = nav.querySelector('[data-menu-toggle]');
  const menu = nav.querySelector('#headerNavigation__menu');
  if (!toggle || !menu) return;
  const set = (open) => {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.classList.toggle(BUTTON_OPENED, open);
    menu.classList.toggle(MENU_OPENED, open);
    document.body.classList.toggle('page_withoutScroll', open);
  };
  toggle.addEventListener('click', () => set(toggle.getAttribute('aria-expanded') !== 'true'));
  DESKTOP.addEventListener('change', () => set(false));
}

// Пункты меню, которые не помещаются в строку, переезжают в выпадающее «Еще».
function setupOverflowMenu(nav) {
  const list = nav.querySelector('[data-main-list]');
  const measure = nav.querySelector('[data-measure-list]');
  const more = nav.querySelector('[data-more]');
  const moreToggle = nav.querySelector('[data-more-toggle]');
  const moreList = nav.querySelector('[data-more-list]');
  if (!list || !measure || !more || !moreList) return;
  const items = [...list.children];
  const widths = [...measure.children].map((li) => li.getBoundingClientRect().width);

  const layout = () => {
    items.forEach((li) => list.appendChild(li));
    moreList.replaceChildren();
    if (!DESKTOP.matches) {
      more.classList.add(MORE_HIDDEN);
      more.setAttribute('aria-hidden', 'true');
      return;
    }
    const available = list.parentElement.getBoundingClientRect().width;
    const moreWidth = 90;
    const total = widths.reduce((a, b) => a + b, 0);
    let visible = items.length;
    if (total > available) {
      let used = moreWidth;
      visible = 0;
      while (visible < items.length && used + widths[visible] <= available) used += widths[visible++];
    }
    items.slice(visible).forEach((li) => {
      const a = li.querySelector('a');
      const item = document.createElement('li');
      item.className = MORE_ITEM;
      const link = document.createElement('a');
      link.className = MORE_LINK;
      link.href = a.getAttribute('href');
      link.textContent = a.textContent;
      item.appendChild(link);
      moreList.appendChild(item);
      li.remove();
    });
    const hasMore = visible < items.length;
    more.classList.toggle(MORE_HIDDEN, !hasMore);
    more.setAttribute('aria-hidden', String(!hasMore));
  };

  const close = () => {
    moreToggle.setAttribute('aria-expanded', 'false');
    moreList.hidden = true;
  };
  moreToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = moreToggle.getAttribute('aria-expanded') !== 'true';
    moreToggle.setAttribute('aria-expanded', String(open));
    moreList.hidden = !open;
  });
  document.addEventListener('click', (e) => { if (!more.contains(e.target)) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });

  layout();
  let raf;
  window.addEventListener('resize', () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(layout); });
  document.fonts?.ready.then(layout);
}

// Баннер согласия на cookies (показывается, только если подключена аналитика).
function setupCookieBanner() {
  const banner = document.querySelector('[data-cookie-banner]');
  if (!banner) return;
  const KEY = 'snowone-cookie-consent';
  let accepted = false;
  try { accepted = localStorage.getItem(KEY) === '1'; } catch { /* приватный режим */ }
  if (accepted) return;
  banner.hidden = false;
  banner.querySelector('button').addEventListener('click', () => {
    try { localStorage.setItem(KEY, '1'); } catch { /* ignore */ }
    banner.hidden = true;
  });
}

// Переключатели вкладок (дни расписания и т.п.): [data-tabs] > [data-tab] + [data-tab-panel].
function setupTabs() {
  document.querySelectorAll('[data-tabs]').forEach((root) => {
    const tabs = root.querySelectorAll('[data-tab]');
    const panels = root.querySelectorAll('[data-tab-panel]');
    const activeClass = root.dataset.activeClass;
    const show = (id) => {
      tabs.forEach((t) => {
        const on = t.dataset.tab === id;
        t.setAttribute('aria-selected', String(on));
        if (activeClass) t.classList.toggle(activeClass, on);
      });
      panels.forEach((p) => { p.hidden = p.dataset.tabPanel !== id; });
    };
    tabs.forEach((t) => t.addEventListener('click', (e) => {
      e.preventDefault();
      show(t.dataset.tab);
      history.replaceState(null, '', t.getAttribute('href'));
    }));
    const fromHash = [...tabs].find((t) => t.getAttribute('href') === location.hash);
    if (fromHash) show(fromHash.dataset.tab);
  });
}

document.querySelectorAll('[data-header-nav]').forEach((nav) => {
  setupMobileMenu(nav);
  setupOverflowMenu(nav);
});
setupCookieBanner();
setupTabs();
