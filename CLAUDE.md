# Design system rules (for turning Figma designs into code here)

This repo has **three separate apps**. None of them uses React, Vue, Tailwind, a bundler or a build step:
every page is plain **PHP that prints HTML, with CSS and JavaScript written straight into the page**.
Code from Figma (`get_design_context`) usually comes back as React + Tailwind. **Use it only as a
reference.** Rewrite it as plain HTML and CSS that follow the app's own tokens and classes below.

| App | Folder | What it is | Look |
|---|---|---|---|
| Aishwarya Arts & Sports Club | `Av/mynamec_/` | Club members' portal and public site (PHP 7.3+ / MySQL) | Royal blue, gold and crimson; Bebas Neue + DM Sans / Playfair + Inter |
| Daybill Print | `daybill/` | Print-shop app (PHP 8 / MySQL), English and Arabic (RTL) | Theme colours chosen per shop; system fonts; rounded "app" UI |
| Sales POS | `sales-pos.html` | One self-contained page | Dark (`#0a0a0f`) with mint accent |

**Before you edit, check which app the file belongs to.** The apps do not share any tokens or classes.

---

## 1. Tokens

### Club app (`Av/mynamec_/`)
There are **no token files and no token pipeline**. Tokens are CSS custom properties on `:root`,
written inside a `<style>` block in each page shell:

- **Member pages:** `includes/header.php` (used by every member page). New palette (dark ink frame + glass,
  teal primary, coral accent). Old token names (`--blue --navy --gold --t2 --t3 --bg --border --radius`) still
  exist and point at the new colours, so older module code keeps working:
  ```css
  :root{
    --ink:#0A1A1F; --ink-2:#0E2A31; --primary:#0F766E; --primary-dark:#115E59; --primary-light:#5EEAD4; --primary-soft:#E6F4F2;
    --accent:#F26B5B; --accent-ink:#B23A2A; --accent-light:#FFB4A8;
    --surface:#F3F6F5; --card:#fff; --line:#E2E8E7; --text:#10201F; --text-2:#3A4C4B; --text-3:#566866;
    --glass:rgba(255,255,255,.07); --glass-line:rgba(255,255,255,.12); --r-lg:22px; --r:16px; --r-sm:12px;
    --font:'Plus Jakarta Sans',system-ui,sans-serif;
  }
  ```
  App tiles: `<span class="tile tone-teal|coral|violet|amber|rose|sky|lime|slate"><?= ic('users') ?></span>`.
- **Public homepage:** `index.php` has its own `:root` (`--p --p2 --p-soft --a --a-light --a-tx --ink --surface --tx --t2 --t3`).
  `--p`, `--a` and the font come from **Club Settings → Homepage** (`home_primary_color`, `home_accent_color`, `home_font`).
  Every homepage section can be switched off there (`home_*_show` = '0'); texts: `hero_*`, `home_about_*`, `home_join_*`, `footer_text`.
  Do not use the class name `.grid` on the homepage: `av-splash.php` defines a global `.grid` overlay.
- **Contact page:** `contact.php` has `--primary --accent --text --text2 --text3`.
- Many modules also use hard-coded hex values in inline `style=""` attributes. When you add new
  code, use the `var(--…)` tokens instead.
- `assets/css/style.css` is an **old stylesheet that no page loads**. Do not add to it or rely on it.

### Daybill (`daybill/`)
Tokens live in `daybill/assets/style.css` `:root` (`--primary --accent --on-primary --p-50…--p-dark
--a-50…--a-dark --bg --card --soft --text --muted --line --ok/--danger/--warn(+-bg) --radius:18px
--r-md:14px --r-sm:10px --shadow --font --mono`).
**This is the only app that transforms tokens:** `theme_css()` in `daybill/lib.php` takes the shop's two
chosen colours (`app_colors()`) and works out the tint and shade steps and `--on-primary` from their
brightness, then prints them in the page `<style>`. **Map Figma brand colours to `--primary` and
`--accent`. Never hard-code the shop colour.**

### Colour rules (checked with axe across all club pages, keep them passing)
- Body text must reach 4.5:1 contrast. On light backgrounds, do not use `#94a3b8`, `#8a93a8`, `#9e9e9e`,
  `#999`, `#aaa`, `#b0bec5` or the gold `#c8922a` for small text. Use `--t3`, `#5d6b80`, `#666`,
  `#546e7a` or `--a-tx` instead.
- On dark sections, faint text uses `rgba(255,255,255,.62)` or higher, never `.25` to `.5`.
- White text on orange needs `#bf360c`. On green it needs `#157a3f` or darker.

## 2. Components

There is **no component library, no Storybook and no docs**. Reusable UI comes from four places:

1. **Page shells (PHP includes).** Club: `require 'includes/header.php'` at the top and
   `require 'includes/footer.php'` at the end. The header prints `<head>`, the top navbar, the mobile
   drawer and `<main class="page-wrap" id="main">`. The footer prints the footer, the bottom tab bar
   (`#bnav`), the push-notification prompt and an **accessibility helper**. That helper connects each
   `<label>` to the field right after it and makes `div[onclick]` work with the keyboard.
   Daybill: `page_header($title, $staff, $lang, $back)` / `page_footer()` in `daybill/lib.php`.
2. **Shared CSS classes** defined in the shell:
   - Club (`includes/header.php`): `.card .card-header .card-body`, `.btn` + `.btn-blue|green|red|gold|outline`
     + `.btn-sm .btn-block`, `.inp` (text box), `.lbl` (label), `.fg` (field group), `.g2 .g3` (grids),
     `.alert .alert-ok|err|warn|info`, `.popup-ov > .popup-box > .popup-head/.popup-body` (pop-up, used with
     `openPopup(id)`/`closePopup(id)`), `.hero`, `.section` (960px), `.section-lg` (1180px), `.stats-row .stat`.
   - Daybill (`assets/style.css`): `.card .btn(.primary|.ok|.danger|.block|.big|.small) .chip .badge .tbl
     .tabs .tabbar .sheet-* .menu-item .stepper .alert .i` (icon size).
3. **PHP helper functions:** `h()` (escape every output), `url('modules/x.php')`, `setting('CLUB_NAME', default)`,
   `csrfField()`, `getLogoB64()`, `photoUrl()` in `includes/config.php` and `modules/upload_helper.php`.
4. **Module-only styles:** most `modules/*.php` add their own `<style>` block with short, module-specific
   prefixes (`.bh-` blood, `.cf-` crowdfund, `.fd-` feed, `.mk-` market, `.nsg-` name slip,
   `.gf-` ground fund, `.bc-` broadcast, `.cs-` creative studio). **Copy this pattern:** a new screen
   gets a new 2–3 letter prefix, and its CSS goes in that module's `<style>`.

Example of a new club module that follows the conventions:
```php
<?php
require_once __DIR__ . '/../includes/config.php';
requireLogin();
$pageTitle = 'Awards';
require_once __DIR__ . '/../includes/header.php';
?>
<style>
.aw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.8rem}
.aw-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);padding:1rem}
.aw-sub{font-size:.8rem;color:var(--t3)}
</style>
<section class="section">
  <div class="card"><div class="card-body">
    <label class="lbl" for="awName">Award name</label>
    <input class="inp" id="awName" name="name">
    <button type="submit" class="btn btn-blue btn-block">Save</button>
  </div></div>
</section>
<?php require_once __DIR__ . '/../includes/footer.php'; ?>
```

## 3. Frameworks and libraries

- **Server:** plain PHP with PDO MySQL (`db()`). No framework and no Composer.
- **Front end:** vanilla JS, written inline (ES5 style). jQuery 3.7.1 is loaded **only on the club
  homepage** (`index.php`, from code.jquery.com). Bootstrap 5.3 CSS is loaded **only on `contact.php`**.
  Elsewhere, Bootstrap class names (`row`, `col-md-4`) do nothing unless you add your own CSS.
- **Libraries from a CDN, per page as needed** (exact versions): Font Awesome 6.5.0 CSS, html2canvas 1.4.1,
  jsPDF 2.5.1, fabric.js 5.3.0, cropperjs 1.6.2, gif.js 0.2.0, qrcodejs 1.0.0, jsQR 1.4.0.
  Daybill keeps its libraries **in the repo** (`daybill/assets/pdf-lib.min.js`, `qrcode.js`) and serves no CDN code.
- **No build system or bundler.** Daybill busts the browser cache by hand with `?v=` (`style.css?v=21`,
  `app.js?v=8`): **bump the number** whenever you edit those files. The club PWA cache is named in `sw.js`
  (`const CACHE = 'aasc-v2'`): bump it when you change cached files.
- PWA: `manifest.php` + `sw.js` in both apps.

## 4. Assets

- **Club:** `Av/mynamec_/assets/logo.jpg` is the logo. Pages usually inline it as base64 with `getLogoB64()`;
  the public URL `LOGO_URL` is used for OG and share tags. Uploaded files go to
  `assets/uploads/<subdir>/` through `handlePhotoUpload($field, $subdir)` (jpg/png/webp/gif, 5 MB or less),
  and pages show them with `photoUrl()`. Images are not compressed or converted. Use
  `loading="lazy"` and set `width` and `height` on new `<img>` tags.
- **Daybill:** `daybill/assets/logo.png`, PWA icons in `daybill/assets/icons/` (favicon, apple-touch, 192, 512, maskable).
- **CDNs:** only cdnjs.cloudflare.com, cdn.jsdelivr.net, code.jquery.com and Google Fonts. There is no
  CDN of your own. Put images exported from Figma in the app's `assets/` folder, not on a CDN.

## 5. Icons

- **Club:** one SVG line-icon set in `includes/icons.php` (24×24, stroke 2, `currentColor`). The header prints the
  sprite once; use `<?= ic('calendar') ?>` / `ic('users','ic-sm')`. Names: home users calendar droplet store star image
  user idcard award card trophy ball masks flower vote heart coins megaphone shield settings logout menu x back chevron
  next bell bolt wallet palette tent file plus search globe qr sparkle chart whatsapp clipboard check download scan login
  phone map mail eye edit layout install. **To add one,** add its `<path>` to `icon_paths()`.
  The module list for the menu, desktop nav and dashboard lives in `app_modules()` / `admin_modules()` — add new modules there.
  Font Awesome 6.5 CSS is still loaded for older module markup and brand logos (`fab fa-whatsapp`).
- **Daybill:** inline SVG line icons from `icon($name)` in `daybill/lib.php` (24×24 viewBox,
  `stroke="currentColor"`, stroke width 1.9, class `.i`). Names are short and lowercase (`jobs`, `qr`,
  `settings`, `back`, `doc`, `photo`, `tag`, `user`, `shop`). **To add an icon from Figma,** export it as
  a 24px outline and paste its `<path>` into the `$paths` array under a new name.

## 6. Styling approach

- **Global CSS + page `<style>` blocks + inline `style=""`.** No CSS Modules, CSS-in-JS or Sass.
- Classes use plain, short names. Modules use prefixes (see §2). Some JS sets styles directly too.
- **Responsive design is mobile-first.** Most users are on phones:
  - Club breakpoints: `880px` (desktop nav shows, hamburger hides), `500px` (`.g2/.g3` stack, stats 2×2),
    `576px`/`768px` on the homepage. Fixed **bottom tab bar** with `env(safe-area-inset-bottom)` padding;
    the body gets matching bottom padding.
  - Daybill: `600px`, `700px` and `900px` breakpoints; `.tabbar` at the bottom on phones.
  - Viewport: `width=device-width,initial-scale=1,viewport-fit=cover`. **Never add `maximum-scale` or `user-scalable=no`.**
- Accessibility rules that the current code already meets. Keep meeting them:
  - Tap targets are at least 44px (`@media (pointer:coarse)` in the header).
  - Text boxes are at least 16px, so iPhones don't zoom in.
  - Every `<label>` has `for=` matching an `id`.
  - Icon-only controls have an `aria-label`.
  - Use `<button type="button">`, not `<div onclick>`.
  - Show a `:focus-visible` ring.
  - Respect `@media (prefers-reduced-motion: reduce)`.
  - Pop-ups get `role="dialog" aria-modal="true"`, close with Escape and return focus.
  - Anything layered over the bottom bar needs `z-index` above `9999` (homepage) or `990` (member pages).
- Daybill is **RTL-aware**: `<html dir="rtl">` for Arabic. Use logical properties
  (`margin-inline-start`, `inset-inline-end`), not left and right.

## 7. Project structure

```
/                      README.md, CLAUDE.md, sales-pos.html
daybill/               print-shop app
  lib.php              helpers, page_header/page_footer, icon(), theme_css()
  api.php job.php …    one PHP file per screen or endpoint
  assets/              style.css, app.js, layout.js, photo-studio.js, vendor JS, icons/
  agent/               Windows print agent (.bat/.vbs + PHP)
  schema.sql           database
Av/mynamec_/           club app
  includes/            config.php (DB, auth, helpers), header.php, footer.php, whatsapp_otp.php
  index.php            public homepage (standalone shell, jQuery)
  contact.php          public contact (standalone shell, Bootstrap)
  dashboard.php admin.php
  modules/<feature>.php  one file per feature: PHP logic at the top, then HTML, then <style> and <script>
  assets/              logo, uploads/ (made at runtime); css/style.css and js/main.js are old and unused
  sw.js manifest.php   PWA
```

Feature pattern: each `modules/x.php` handles its own AJAX first (`if(!empty($_POST['ajax']))` →
`echo json_encode([...]); exit;`), creates or changes its own tables with `CREATE TABLE IF NOT EXISTS`
/ `ALTER TABLE` inside `try{}`, then prints the page. Escape all output with `h()`, and use prepared
statements for queries.

## Figma → code checklist

1. Call `get_design_context` and `get_screenshot` for the node. Treat the React/Tailwind output as a picture of the layout only.
2. Choose the app. Match Figma colours, radii and shadows to the existing `var(--…)` tokens. Only add a new token, in the shell's `:root`, when nothing is close.
3. Build with plain HTML plus the shared classes (`.card`, `.btn`, `.inp`, `.lbl`, …). Put new styles in the module's `<style>` under its prefix.
4. Icons: club uses Font Awesome or an emoji with `aria-hidden`. Daybill uses `icon()`, adding a 24px path if needed.
5. Images: save them to `assets/`, give `<img>` `width` and `height`, add `loading="lazy"`, and write an `alt`.
6. Check at 390px wide: no sideways scrolling, nothing hidden behind the bottom bar, 44px tap targets, 4.5:1 contrast.
7. Daybill: bump `?v=`. Club: bump the `sw.js` cache name if cached files changed.
