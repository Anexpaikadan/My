# CLAUDE.md — design system rules (for Figma → code work)

This repo has **three separate apps**. They are plain **PHP + MySQL + hand-written CSS/JS**.
There is **no React/Vue, no npm, no bundler, no build step, no Storybook, no token pipeline**.
When you turn a Figma design into code, write PHP templates + plain CSS + plain JS that match the app you
are in. Do not bring in a framework, Tailwind, or a build tool.

| App | Folder | Styling | Icons | Languages |
|---|---|---|---|---|
| Daybill Print (print shop) | `daybill/` | one file `daybill/assets/style.css` | inline SVG via `icon()` in `daybill/lib.php` | English / Arabic (RTL) |
| Aishwarya Club (club site) | `aishwarya-club/` | Bootstrap 5.3 (local) + `aishwarya-club/assets/css/club.css` | `ic()` SVG sprite, Bootstrap Icons, 3D WebP tiles | Malayalam / English |
| QuickSale POS | `sales-pos.html` | one self-contained HTML file with a `<style>` block | none | English |

First decide which app the design is for, then follow only that app's section below.

---

## 1. Token definitions

Tokens are **CSS custom properties on `:root`**. No JSON tokens, no Style Dictionary.
Map Figma variables to these existing names before adding new ones.

### Daybill — `daybill/assets/style.css` (top of file)
```css
:root {
  --primary: #360dd9; --accent: #7ed957; --on-primary: #fff;
  --p-50 … --p-300, --p-dark;  --a-50, --a-200, --a-dark;     /* tints of primary / accent */
  --bg: #f4f5fa; --card: #fff; --soft: #f1f3f8; --text: #141925; --muted: #687387; --line: #e4e8f0;
  --ok / --ok-bg, --danger / --danger-bg, --warn / --warn-bg, --info-bg;
  --radius: 18px; --r-md: 14px; --r-sm: 10px;
  --shadow; --shadow-lg;
  --font: system-ui, …, "Noto Sans Arabic", sans-serif;  --mono: ui-monospace, …;
}
```
**The only token transformation in the repo:** each shop picks its own colours (Settings → App colour), and
`theme_css()` in `daybill/lib.php` writes a `:root{}` override with the tints worked out from them
(`mix_hex()` lightens or darkens a colour; `luminance()` picks `--on-primary` black or white).
So **never hard-code the brand purple/green**. Always use `var(--primary)`, `var(--p-100)`, `var(--a-dark)` and so on.

### Aishwarya Club — `aishwarya-club/assets/css/club.css` (top of file)
```css
:root{
  --brand:#E30613; --brand-dark:#B80F0A; --accent:#0A14E0;          /* logo red + blue */
  --dark:#141A3A; --page-dark:#0B1033; --dark-2:#1C2350;            /* dark public surfaces */
  --brand-text:#FF5A52; --accent-text:#8F97FF; --muted:#b5b1b1;     /* text on dark */
  --light:#F4F6FB; --line:#E3E7F5; --text:#0B1033; --text-2; --text-3;
  --gold; --wa:#25D366; --ok;
  --r-card:1rem; --r-btn:.6rem; --r-pill:2rem;  --sh-soft; --sh-dark;
  --font:system-ui,…,"Noto Sans Malayalam",…;
  --bs-primary:#E30613; --bs-border-radius:.6rem; …                 /* Bootstrap hooks */
  --primary, --blue, --red, --radius, --shadow, …                   /* aliases for older module code */
}
:root{--dur-fast:140ms;--dur:260ms;--dur-slow:520ms;--ease-out:cubic-bezier(.22,1,.36,1);--ease-spring:…}
```
- Use the main names (`--brand`, `--accent`, `--r-card`, `--sh-soft`) in new code. The alias block is
  only there so old module code keeps working.
- **Dark / light theme (public pages only):** `<html data-theme="dark|light">` is set before the page
  draws by `theme_head()` in `aishwarya-club/includes/theme.php`. The default comes from the `pub_theme`
  setting and a visitor's choice is saved in localStorage `pubTheme`. The light theme **redefines the
  same tokens** under `html[data-theme=light] body.pub{…}` near the end of `club.css`, then fixes
  hard-coded whites one selector at a time.
  When you add a public component, use tokens (`var(--on)`, `var(--hair)`, `var(--page-dark)`) and add a
  `html[data-theme=light]` rule for anything that is still hard-coded.
- `aishwarya-club/assets/css/style.css` (Royal Blue / Bebas Neue) is an **old, unused** theme. No page
  links to it. Do not use or extend it.

### POS — `sales-pos.html`
Dark-only tokens in its inline `<style>`: `--bg --surface --panel --border --accent(#00e5a0) --accent2 --warn --text --muted`.
Fonts: Syne + JetBrains Mono from Google Fonts.

---

## 2. Component library

No component framework. "Components" are **CSS classes + PHP helper functions that return HTML strings**.

### Daybill
- Page shell: `page_header($title, $staff, $lang, $back)` / `page_footer()` in `daybill/lib.php`. These print
  `<head>`, the sticky glass app bar `.top`, the stylesheet and `app.js`.
- Bottom sheet: `sheet_start($id, $title)` … `sheet_end()`, plus `sheet_field()`.
- CSS components in `style.css`: `.top`, `.tabbar` (fixed bottom; becomes a floating pill at ≥900px),
  `.card`, `.menu.card > .menu-item`, `.menu-title`, `.btn` (pill, min-height 44px) with modifiers
  `.btn.primary | .ok | …`, `.shop-chip`, `.install-chip`, `.wrap` (max 980px) and `.narrow` (max 440px).
```php
<?php page_header(t('settings'), true, $lang, 'admin.php'); ?>
<div class="card">
  <a class="menu-item" href="printer.php"><?= icon('settings') ?><span>…</span></a>
</div>
<button class="btn primary"><?= icon('qr') ?> <?= h(t('save')) ?></button>
<?php page_footer(); ?>
```

### Aishwarya Club
- Member/admin shell: `include 'includes/header.php'` … `include 'includes/footer.php'`. Put
  `<body class="app">` on these pages: light content, dark top bar, 5-tab bottom bar on phones, and a 260px
  dark sidebar at ≥992px.
- Public pages (`index.php`, `contact.php`) build their own `<head>` and use `<body class="pub">`
  (dark by default, can switch to light).
- Bootstrap 5.3 classes (grid, `.modal`, `.form-control`, utilities) plus the custom classes in `club.css`:
  `.btn-brand` (red, glow), `.btn-line`, `.btn-wa`, `.chip` (`aria-pressed="true"` / `.on` = selected),
  `.h-sec` (uppercase section title with a red bar under it), `.h-big`, `.tiles > .tile-l` (app grid:
  3 / 4 / 6 columns), `.pgrid`, `.sl-card` (slider), `.bnav3` (public bottom nav), `.modal-dark`,
  `.popup-ov/.popup-box`, `.rv` + `.in` (reveal on scroll, driven by `assets/js/motion.js`; use `--i` to
  stagger items).
- Module registry: `app_modules()`, `admin_modules()` and `app_meta()` in `includes/icons.php` set each
  module's label, colour (`c-navy`, `c-red`, `c-blue`, …) and icon. Register any new screen there.
- Modules in `modules/*.php` often carry a page-local `<style>` block. Put new shared styles in `club.css`;
  keep only one-off rules local.

---

## 3. Frameworks & libraries

| | Daybill | Club | POS |
|---|---|---|---|
| Server | PHP 8 (typed functions, arrow fns), MySQL via PDO, `schema.sql` | PHP (older-style `array()`), MySQL via `db()` PDO | none (static) |
| UI | plain HTML from PHP | Bootstrap 5.3 CSS + JS (local copy in `assets/vendor/bootstrap`) | plain |
| JS | plain JS: `assets/app.js`, `layout.js`, `photo-studio.js`, `qrcode.js`, `pdf-lib.min.js` | plain JS: `assets/js/main.js`, `mini.js`, `motion.js` | inline `<script>` |
| Build | **none**. Cache-busting with `?v=N` on the URL | **none**. `?v=N` | none |
| PWA | `manifest.php`, `sw.js`, `offline.html` | `manifest.php`, `manifest.json`, `sw.js` | — |

**When you change a CSS/JS file, bump its `?v=` number** where it is linked (Daybill: `page_header()` in
`lib.php`, e.g. `style.css?v=22`, and the `CACHE` name in `daybill/sw.js`; Club: `index.php` and `includes/header.php`, e.g. `club.css?v=6`).
Otherwise the service workers keep serving the old file.

---

## 4. Asset management

- Assets are files in the repo, served as-is. **No CDN, no image pipeline, no bundler.** The only outside
  resource is Google Fonts (Club's unused `style.css`, POS).
- Daybill: `daybill/assets/` (JS/CSS) and `daybill/assets/icons/` (favicon + PWA icons). Customer uploads
  go to `daybill/uploads/`, which `.htaccess` keeps from being reached directly.
- Club: `aishwarya-club/assets/` with `logo.jpg`, `icons/app/` (PWA/favicons), `icons/3d/` (128×128
  WebP), `vendor/` (Bootstrap, Bootstrap Icons, Font Awesome, all local). Club logos and member photos are
  often inlined as base64 (`getLogoB64()`, `getMemberPhoto()`). Uploads are handled by
  `modules/upload_helper.php`.
- Build URLs with `url('assets/…')` in Club. In Daybill, use paths relative to the app folder.
- What little optimisation exists: WebP icons, `loading="lazy" decoding="async"` on `<img>`, explicit
  `width`/`height`.
- Export Figma images as **WebP** (photos/illustrations) or **inline SVG** (icons). Size them to the
  displayed size ×2.

---

## 5. Icon system

All line icons are **24×24 SVG with stroke ≈2 and `currentColor`**, so they take on the text colour.
Export Figma icons in that form (no fill, round caps and joins).

- **Daybill:** `icon('name')` in `daybill/lib.php` returns
  `<svg class="i" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" …>`.
  The `.i` class is 22px. To add an icon, add `'name' => '<path …/>'` to the `$paths` array. Names are
  short lowercase words (`jobs`, `qr`, `settings`, `back`, `doc`, `photo`, `tag`, `user`). In RTL,
  `.back-btn .i` is mirrored.
- **Club, three kinds:**
  1. `ic('users', 'ic-lg')` takes a path from `icon_paths()` in `includes/icons.php` and draws it through a
     sprite that `icon_sprite()` prints once per page. Sizes: `.ic` 22px, `.ic-sm` 18px, `.ic-lg` 28px.
     Names are short lowercase words (`home`, `calendar`, `whatsapp`, …).
  2. Bootstrap Icons, `<i class="bi bi-sun-fill">`. Used in `app_meta()` and in the theme toggle.
     Font Awesome is also loaded, but treat it as legacy.
  3. 3D tile pictures: `app_img('events', 40)` → `assets/icons/3d/events.webp` (Fluent Emoji, MIT). The
     file name is the module key. To change one, replace the file and keep its name (see
     `assets/icons/3d/README.md`).
- Decorative icons get `aria-hidden="true"`. Buttons that show only an icon need an `aria-label`.

---

## 6. Styling approach

- **Global, hand-written CSS with short semantic class names.** No BEM, CSS Modules or CSS-in-JS. One main
  stylesheet per app. Inline `style.cssText` appears only for JS-made toasts and overlays.
- Club CSS is compact (minified, one rule per line, grouped under `/* ── Section ── */` headers).
  Daybill CSS is readable and grouped under `/* ---------- section ---------- */`. Match the style of the
  file you edit.
- **Mobile-first**, then `min-width` breakpoints:
  - Daybill: 700px, 900px (tab bar turns into a floating pill); `max-width:600px` for small tweaks;
    `@media print`.
  - Club: Bootstrap's 576 / 768 / 992 / 1200. At 992px the app sidebar appears and
    `body.app{padding-left:260px}`.
  - Fluid type with `clamp()` (e.g. `.h-sec{font-size:clamp(1.35rem,5.5vw,1.9rem)}`).
- Phone-app details to keep: `env(safe-area-inset-*)` padding on fixed bars, `backdrop-filter` glass
  bars, tap targets of at least 44px (`.btn{min-height:44px}`, `@media(pointer:coarse)`),
  `-webkit-tap-highlight-color:transparent`.
- Accessibility rules already in place (both apps): `:focus-visible` outline rings (never remove them), `.skip-link`, `.sr-only`,
  `prefers-reduced-motion` blocks that turn off animations, contrast notes on tokens (e.g.
  `--brand-text … (5.5:1)`). New colours must reach WCAG AA.
- RTL (Daybill Arabic): use logical properties (`margin-inline-start/end`) and `[dir=rtl]` overrides,
  never `left`/`right` margins.

---

## 7. Project structure

```
/                     README.md, CLAUDE.md, sales-pos.html
daybill/              one PHP file per screen (index = customer, staff, admin, settings, shops, job, printer, qr…)
  lib.php             all shared helpers: DB, auth, t() lang, theme_css(), icon(), page_header/footer, sheets
  lang.php            EN/AR strings     config.php / schema.sql / install.php
  assets/             style.css, app.js, layout.js, photo-studio.js, vendor JS, icons/
  agent/              Windows print agent (PHP CLI + .bat)      uploads/  (protected)
aishwarya-club/
  index.php contact.php          public site (body.pub, dark/light)
  dashboard.php admin.php more.php login.php …   member/admin shell
  includes/           header.php, footer.php, theme.php, icons.php (icons + module registry), lang.php, og.php,
                      wa_gateway.php …  (config.php is NOT in git — it is on the server)
  modules/            one feature per file (events, members, blood, market, election, donation, …)
  assets/             css/club.css, js/, icons/{app,3d}/, vendor/{bootstrap,bootstrap-icons,fontawesome}
```
Patterns:
- **One feature = one PHP file** that handles its own GET (render) and POST/AJAX (actions), using the shared
  shell. Add new features the same way and register them (Club: `app_modules()` / `admin_modules()`).
- All text goes through the translation helper (`t('key')` in both apps). Add the key to every language in
  `lang.php`. Never hard-code visible English.
- Escape output with `h()` (both apps). Use prepared statements for SQL.

---

## Figma → code checklist

1. Pick the app, then map Figma colours, radii, shadows and type to the **existing tokens** above. Add a
   token to `:root` only when nothing fits, and (Club public) also add its `data-theme=light` value.
2. Build with the existing shell and classes (`page_header` / `.card` / `.btn` in Daybill; `header.php` /
   Bootstrap + `club.css` classes in Club) before writing new CSS.
3. Icons: inline SVG paths added to `icon()` / `icon_paths()`; 3D tiles as 128×128 WebP in `icons/3d/`.
4. Mobile first; check at phone width, at 992px (Club) or 900px (Daybill), in dark and light (Club public),
   and in RTL (Daybill).
5. Text through `t()`, output through `h()`, and bump `?v=` on every CSS/JS file you changed.
