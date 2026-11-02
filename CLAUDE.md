# Design system rules (for turning Figma designs into code here)

This repo has **three separate apps**. None of them uses React, Vue, Tailwind, a bundler or a build step:
every page is plain **PHP that prints HTML, with CSS and JavaScript written straight into the page**.
Code from Figma (`get_design_context`) usually comes back as React + Tailwind. **Use it only as a
reference.** Rewrite it as plain HTML and CSS that follow the app's own tokens and classes below.

| App | Folder | What it is | Look |
|---|---|---|---|
| Aishwarya Arts & Sports Club | `Av/mynamec_/` | Club members' portal and public site (PHP 7.3+ / MySQL), English + Malayalam | Logo red + blue. Public site dark, member/admin app light. Bootstrap 5.3 (local), system fonts |
| Daybill Print | `daybill/` | Print-shop app (PHP 8 / MySQL), English and Arabic (RTL) | Theme colours chosen per shop; system fonts; rounded "app" UI |
| Sales POS | `sales-pos.html` | One self-contained page | Dark (`#0a0a0f`) with mint accent |

**Before you edit, check which app the file belongs to.** The apps do not share any tokens or classes.

---

## 1. Tokens

### Club app (`Av/mynamec_/`)
**One stylesheet: `assets/css/club.css`** (loaded after the local Bootstrap 5.3 CSS by every page). Its `:root` holds the tokens:
```css
:root{
  --brand:#E30613; --brand-dark:#B80F0A;          /* logo red: buttons, active states, heading bar */
  --accent:#0A14E0;                                 /* logo blue */
  --dark:#141A3A; --page-dark:#0B1033; --dark-2:#1C2350;   /* public page background, cards, top bar */
  --brand-text:#FF5A52; --accent-text:#8F97FF;      /* red / blue TEXT on dark backgrounds (pass 4.5:1) */
  --muted:#b5b1b1;                                  /* secondary text on dark */
  --gold:#E8B923; --wa:#25D366; --ok:#15803D;
  --light:#F4F6FB; --line:#E3E7F5; --text:#0B1033; --text-2:#3B4266; --text-3:#565D82;   /* light app */
  --r-card:1rem; --r-btn:.6rem; --r-pill:2rem;
  --font:system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans Malayalam","Noto Sans",sans-serif;
}
```
Old names (`--primary --blue --navy --t2 --t3 --bg --border --radius --brand-grad …`) are kept as aliases so older module code works.
Headings: `.h-sec` (900 weight, UPPERCASE, 3rem×4px red bar under it), `.h-big` (big italic title).
- **Two looks:** `<body class="pub">` = dark public pages (`index.php`, `contact.php`); `<body class="app">` = light
  member/admin pages (`includes/header.php`). Scope public-only styles under `.pub` so they don't leak into the app.
- **Public page content is data, not code.** Admin → **Public Website** (`modules/site.php`) saves to `club_settings`
  (`hero_photo`, `hero_title`, `hero_subtitle`, `about_points`, `join_options`, `footer_text`, `pub_title_<section>`,
  `pub_show_<section>` on/off, `site_whatsapp`, `site_phone`, `site_address`, `site_map`, `social_instagram`, `og_on/og_title/og_desc/og_image`).
  A Malayalam version of any text is the same key + `_ml`. Programs, fee cards, timings and rules are tables made by
  `includes/site_schema.php` (`club_activities`, `site_packages`, `site_timings`, `site_rules`, `enquiries`).
- Do not use the class name `.grid` on the homepage: `av-splash.php` defines a global `.grid` overlay.
- Many modules still use hard-coded hex values in inline `style=""`. New code uses the `var(--…)` tokens.
- `assets/css/style.css` and `assets/js/main.js` are **old files no page loads**. Do not use them.

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
- On dark sections, faint text uses `--muted` or `rgba(255,255,255,.62)` or higher, never `.25` to `.5`.
  Red or blue text on dark uses `--brand-text` / `--accent-text`, not `--brand` / `--accent`.
- White text on `--wa` green fails: WhatsApp buttons (`.btn-wa`) use dark text `#0B1033`.
- White text on orange needs `#bf360c`. On green it needs `#157a3f` or darker.

## 2. Components

There is **no component library, no Storybook and no docs**. Reusable UI comes from four places:

1. **Page shells (PHP includes).** Club: `require 'includes/header.php'` at the top and
   `require 'includes/footer.php'` at the end. The header prints `<head>` (local Bootstrap, Bootstrap Icons, Font Awesome,
   `club.css?v=N`, OG tags), the dark **sidebar** (desktop ≥992px), the dark **top bar** (back button, title, language
   switch, admin shield, profile) and `<main class="page-wrap" id="main">`. The footer prints the 5-tab bottom bar
   (`.tabbar#bnav`: admins Home/Members/**Admin**/Events/More, members Home/Events/**Market**/Feed/More), Bootstrap JS,
   the **accessibility helper** (connects each `<label>` to the next field, makes `div[onclick]` keyboard-usable,
   makes scrolling tables focusable), the module banner script and the **passkey pop-up** (`#mSudo`).
   `more.php` is the "More" page (all modules as icon tiles). Public pages (`index.php`, `contact.php`) have their own
   shell with `.pub-top` and the 3-button bottom bar `.bnav3` (Home / Market / Login-Dashboard-My account).
   Daybill: `page_header($title, $staff, $lang, $back)` / `page_footer()` in `daybill/lib.php`.
2. **Shared CSS classes** (`assets/css/club.css`, plus all Bootstrap 5.3 classes):
   - Both: `.btn-brand` (`.btn-glow`), `.btn-line` (outline on dark), `.btn-wa`, `.chip[aria-pressed]`, `.h-sec`, `.h-big`, `.thanks`, `.hp` (honeypot).
   - Public (`.pub`): `.hero-pub .hero-photo .hero-btns`, `.pt-list/.pt-box`, `.pgrid/.pcard`, sliders
     `.sl .sl-track .sl-card .sl-ctrl .sl-arrow .sl-dots` (`.sl.gold`), `.fgrid .fee(.pop)`, `.tm .tm-row`, `.rule-box`,
     `.shop-grid .prod .tag-offer`, `.ct-box .ct-row .map`, `.people .person`, `.modal-dark` (dark Bootstrap modal), `.mrow`, `.m-photo`.
   - App (`.app`): `.topbar`, `.side`, `.tabbar`, `.tiles .tile-l .ico` (More page), `.dgrid .dtile` + colour classes
     `.c-red .c-blue .c-green .c-amber .c-violet .c-teal .c-rose .c-slate .c-navy .c-pink`, `.h-app`.
   - Kept for older modules (restyled): `.card .card-header .card-body`, `.btn-blue|green|red|gold|outline`, `.btn-sm .btn-block`,
     `.inp`, `.lbl`, `.fg`, `.g2 .g3`, `.alert-ok|err|warn|info`, `.popup-ov > .popup-box` (`openPopup(id)`/`closePopup(id)`),
     `.hero` (module banner: icon from `data-mod-icon`), `.section`, `.stats-row .stat`, `.table-wrap`.
3. **PHP helper functions:** `h()` (escape every output), `url('modules/x.php')`, `setting('CLUB_NAME', default)`,
   `csrfField()`/`verifyCsrf()`, `getLogoB64()` (`includes/config.php`), `img_optimize()`, `ensure_user_columns()` (`includes/extras.php` — **never add functions to config.php**: the server keeps its own copy with the real DB password, so new helpers go in extras.php and pages require it), `photoUrl()`,
   `handlePhotoUpload()` (`modules/upload_helper.php`), `t('key')`/`tset($en,$ml)`/`lang_current()` (`includes/lang.php`),
   `site_cfg()`/`og_tags()` (`includes/og.php`), `sudo_require()` (`includes/sudo.php`), `app_meta()`/`app_modules()` (`includes/icons.php`).
   **Language:** every fixed text comes from `includes/lang.php` (`en` and `ml` arrays with the same keys); `?setlang=ml` sets a cookie.
   **Passkey check:** before any admin delete or money change, call `sudo_require()` on the server and add `data-sudo`
   (+ optional `data-confirm="…"`) to the form, `data-sudo-fields="a,b"` to ask only when those fields change, or wrap
   fetch calls in `sudoThen(fn)`. Confirmation lasts 5 minutes.
4. **Module-only styles:** most `modules/*.php` add their own `<style>` block with short, module-specific
   prefixes (`.bh-` blood, `.cf-` crowdfund, `.fd-` feed, `.mk-` market,
   `.gf-` ground fund, `.bc-` broadcast, `.cs-` creative studio, `.ws-` public website, `.eq-` enquiries). **Copy this pattern:** a new screen
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
.aw-card{background:#fff;border:1px solid var(--line);border-radius:var(--r-card);padding:1rem}
.aw-sub{font-size:.8rem;color:var(--text-3)}
</style>
<section class="section">
  <div class="card"><div class="card-body">
    <label class="form-label" for="awName">Award name</label>
    <input class="form-control" id="awName" name="name">
    <button type="submit" class="btn btn-brand w-100 mt-2">Save</button>
  </div></div>
</section>
<?php require_once __DIR__ . '/../includes/footer.php'; ?>
```

## 3. Frameworks and libraries

- **Server:** plain PHP with PDO MySQL (`db()`). No framework and no Composer.
- **Front end:** vanilla JS, written inline (ES5 style). **Bootstrap 5.3.3 CSS + JS, Bootstrap Icons 1.11.3 and Font Awesome 6.5.0
  are stored in the repo** under `Av/mynamec_/assets/vendor/` (MIT) and loaded on every club page — no CDN for these.
  Use Bootstrap Icons (`<i class="bi bi-…" aria-hidden="true">`) for new UI. There is **no jQuery**: the public login code uses
  `assets/js/mini.js`, a tiny jQuery-like helper; pages that load it set `<body data-bs-no-jquery>`.
- **Libraries from a CDN, per page as needed** (exact versions): html2canvas 1.4.1,
  jsPDF 2.5.1, fabric.js 5.3.0, cropperjs 1.6.2, gif.js 0.2.0, qrcodejs 1.0.0, jsQR 1.4.0.
  Daybill keeps its libraries **in the repo** (`daybill/assets/pdf-lib.min.js`, `qrcode.js`) and serves no CDN code.
- **No build system or bundler.** Bust the browser cache by hand: club `club.css?v=N` (in `includes/header.php`,
  `index.php`, `contact.php`), Daybill `style.css?v=21`, `app.js?v=8`: **bump the number** whenever you edit those files.
  The club PWA cache is named in `sw.js` (`const CACHE = 'aasc-v4'`): bump it when you change cached files.
- PWA: `manifest.php` + `sw.js` in both apps.

## 4. Assets

- **Club:** `Av/mynamec_/assets/logo.jpg` is the logo. Pages usually inline it as base64 with `getLogoB64()`;
  the public URL `LOGO_URL` is used for OG and share tags. Uploaded files go to
  `assets/uploads/<subdir>/` through `handlePhotoUpload($field, $subdir)` (jpg/png/webp/gif, 5 MB or less),
  and pages show them with `photoUrl()`. Every upload goes through `img_optimize()` (max 1200px, JPG 80%). PWA / app icons
  are in `assets/icons/app/` (made from the logo). Use
  `loading="lazy"` and set `width` and `height` on new `<img>` tags.
- **Daybill:** `daybill/assets/logo.png`, PWA icons in `daybill/assets/icons/` (favicon, apple-touch, 192, 512, maskable).
- **CDNs:** only cdnjs.cloudflare.com and cdn.jsdelivr.net (for the per-page libraries above). There is no
  CDN of your own. Put images exported from Figma in the app's `assets/` folder, not on a CDN.

## 5. Icons

- **Club:** **Bootstrap Icons** for all new UI. `app_meta($file)` in `includes/icons.php` gives each page its icon name,
  tile colour class and Malayalam label (used by the sidebar, dashboard tiles, More page and module banners).
  An older SVG line-icon set is also in `includes/icons.php` (24×24, stroke 2, `currentColor`). The header prints the
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
  - Club: Bootstrap breakpoints. `992px`: sidebar shows on app pages (`body.app` gets 260px left padding);
    below it the 5-tab bar is the navigation. Public pages: programs/shop 2 per row on phones, 4 on desktop; slider
    cards 78% wide on phones, 3 per row on desktop. Fixed bottom bars use `env(safe-area-inset-bottom)` padding;
    on desktop the public bar is centred, 480px wide, rounded on top.
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
  - Anything layered over the bottom bar needs a higher `z-index` (Bootstrap modals already are).
  - Pop-ups: use Bootstrap `.modal` (dark: add `.modal-dark`). The public login pop-up uses its own `.overlay > .lgn` classes.
  - Forms people fill in from the public site get a hidden honeypot field (`.hp`, name `website`) and a per-IP limit.
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
  includes/            config.php (DB, auth, helpers), header.php, footer.php, lang.php, og.php, sudo.php,
                       site_schema.php, icons.php, wa_gateway.php
  index.php            public homepage (dark, own shell)      contact.php  public contact (dark, own shell)
  dashboard.php admin.php more.php sudo.php (passkey check endpoint)
  modules/site.php     Admin → Public Website                  modules/enquiries.php  Join the Club requests
  modules/<feature>.php  one file per feature: PHP logic at the top, then HTML, then <style> and <script>
  assets/              logo, css/club.css, js/mini.js, vendor/ (Bootstrap, icons, Font Awesome), icons/app/,
                       uploads/ (made at runtime); css/style.css and js/main.js are old and unused
  sw.js manifest.php   PWA
```

WhatsApp: send through `includes/wa_gateway.php` only — `wa_queue($phone,$text,$kind)` / `wa_queue_many($rows,…)` for
notices (sent by `modules/wa_worker.php`), `wa_otp_send()` / `wa_otp_check()` for codes, and check `wa_feature_on('events'|…)` first.
Never return a code to the browser.

Feature pattern: each `modules/x.php` handles its own AJAX first (`if(!empty($_POST['ajax']))` →
`echo json_encode([...]); exit;`), creates or changes its own tables with `CREATE TABLE IF NOT EXISTS`
/ `ALTER TABLE` inside `try{}`, then prints the page. Escape all output with `h()`, and use prepared
statements for queries.

## Figma → code checklist

1. Call `get_design_context` and `get_screenshot` for the node. Treat the React/Tailwind output as a picture of the layout only.
2. Choose the app. Match Figma colours, radii and shadows to the existing `var(--…)` tokens. Only add a new token, in the shell's `:root`, when nothing is close.
3. Build with plain HTML plus Bootstrap and the shared classes (`.btn-brand`, `.h-sec`, `.form-control`, `.card`, …). Put new styles in the module's `<style>` under its prefix. Put fixed texts in `includes/lang.php` (English + Malayalam).
4. Icons: club uses Bootstrap Icons with `aria-hidden="true"`. Daybill uses `icon()`, adding a 24px path if needed.
5. Images: save them to `assets/`, give `<img>` `width` and `height`, add `loading="lazy"`, and write an `alt`.
6. Check at 390px wide: no sideways scrolling, nothing hidden behind the bottom bar, 44px tap targets, 4.5:1 contrast.
7. Daybill: bump `?v=`. Club: bump `club.css?v=` and the `sw.js` cache name if cached files changed. Admin deletes and money changes: `sudo_require()` + `data-sudo`.
