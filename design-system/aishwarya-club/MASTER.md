# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/aishwarya-club/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Aishwarya Arts & Sports Club (members portal + public website)
**Code:** `Av/mynamec_/` — plain PHP pages, CSS and JS inside each page (no React, no Tailwind, no build step)
**Category:** Sports Team/Club · Community membership
**Source of truth in code:** `:root` in `Av/mynamec_/includes/header.php` (member pages)

This file describes the design **as it is built and tested** (axe WCAG 2 AA: 0 issues on all pages).
The skill's generated suggestion for "sports club" (red + Bebas Neue) is **not** used — the club uses its logo colours.

---

## Global Rules

### Color Palette (from the club logo: red `#FA0500`, blue `#000AFC`, white)

| Role | Hex | CSS Variable | Notes |
|------|-----|--------------|-------|
| Primary (logo blue) | `#0A14E0` | `--primary` | Buttons, links, active tab |
| Primary dark | `#070FA8` | `--primary-dark` | Hover, text on soft blue |
| Primary light | `#A9B0FF` | `--primary-light` | Only on dark backgrounds |
| Primary soft | `#ECEEFF` | `--primary-soft` | Chips, selected rows |
| On Primary | `#FFFFFF` | — | 9.6:1 on primary |
| Accent (logo red) | `#E30613` | `--accent` | Badges, highlights, counters |
| Accent ink | `#B80F0A` | `--accent-ink` | Red text on white |
| Accent soft | `#FFECEC` | `--accent-soft` | Error / logout backgrounds |
| Brand gradient | `linear-gradient(105deg,#D9050F 0%,#8A0A8E 50%,#0A14E0 100%)` | `--brand-grad` | Top bar, page banners, member card, main CTA |
| Background | `#F5F7FF` | `--surface` | Page background |
| Card | `#FFFFFF` | `--card` | Cards, sheets, tab bar |
| Border | `#E3E7F5` | `--line` | Card and input borders |
| Text | `#0B1033` | `--text` / `--ink` | Body text, dark footer |
| Text 2 | `#3B4266` | `--text-2` | Secondary text |
| Text 3 (muted) | `#565D82` | `--text-3` | Hints, captions (5.6:1) |
| Success | `#15803D` | `--ok` | |
| Danger | `#C0392B` | `--danger` | |

**Color rules**
- Raw logo red `#FA0500` fails contrast with white text — always use `--accent` `#E30613` or darker.
- Never use `#94a3b8`, `#8a93a8`, `#999`, `#aaa`, `#b0bec5` for text on light backgrounds.
- On dark/gradient areas, faint text is `rgba(255,255,255,.62)` or higher.
- Old token names still exist and point to these colours: `--blue --navy --gold --t2 --t3 --bg --border --radius`.

### Typography

- **Font:** Plus Jakarta Sans (400–800) for everything. Headings: weight 800, often UPPERCASE.
- **Section heading pattern:** bold uppercase + a 40–56px wide, 4px tall bar in `--brand-grad` underneath.
- **Body:** 16px base, line-height 1.6. Inputs are 16px+ (no iPhone zoom).
- Bebas Neue is kept only in the ID card and Poster Studio (they export images/PDFs).
- Homepage font can be changed in Club Settings → Homepage (Plus Jakarta Sans, Poppins, Manrope, Outfit).

### Radius, shadow, spacing

| Token | Value | Usage |
|-------|-------|-------|
| `--r-lg` | `22px` | Cards, panels |
| `--r` | `16px` | Inner cards, inputs groups |
| `--r-sm` | `12px` | Inputs, small buttons |
| Buttons | `14px` radius, min-height 44px (52px for main CTAs) | |
| `--sh-1` | `0 1px 2px rgba(10,26,31,.05),0 4px 16px rgba(10,26,31,.06)` | Cards |
| `--sh-2` | `0 12px 40px rgba(10,26,31,.16)` | Popups, drawer |
| Spacing | 4 / 8 / 12 / 16 / 24 / 32 px rhythm; page side padding 16px | |

---

## Component Specs (classes in `includes/header.php`)

| Component | Class / helper | Rule |
|-----------|----------------|------|
| Top app bar | `.appbar` | Brand gradient, 60px, back button on sub-pages, round club logo |
| Side menu | `.drawer` | White, 3-column app grid with 3D icons |
| Bottom tab bar | `#bnav` (footer.php) | White glass, 5 items max, centre round gradient button |
| App tile / launcher card | `.appic` + `app_img('name')` | White tile, 3D picture (`assets/icons/3d/*.webp`); dashboard uses big 2-column cards with title + one-line description (`app_desc()`) |
| Page banner | `.hero` (and module banners) | Brand gradient, rounded bottom 30px, big 3D icon, bold uppercase title with white bar |
| Card | `.card .card-header .card-body` | White, 22px radius, `--line` border, `--sh-1` |
| Buttons | `.btn` + `.btn-blue` / `.btn-gold` (red) / `.btn-green` / `.btn-outline` | One main action per screen |
| Inputs | `.lbl` + `.inp` | Visible label with `for=`; 46px tall; blue focus ring |
| Popup | `.popup-ov > .popup-box` | Bottom sheet on phones, dialog on desktop, Escape closes |
| Alerts | `.alert-ok/err/warn/info` | Text + colour (never colour only) |

### Icons
- **App / module icons:** 3D pictures (Microsoft Fluent Emoji 3D, MIT) via `app_img()`. To change one, replace the `.webp` file.
- **UI controls:** SVG line icons via `ic('name')` (24×24, stroke 2). No emoji as icons in new code.
- Decorative icons get `aria-hidden="true"`; icon-only buttons need `aria-label`.

---

## Style Guidelines

**Style:** Clean app-like white surfaces + bold logo gradient accents (sports-club energy, but readable).

**Key effects:** gradient top bar and banners · white cards with soft shadow · 3D icons · bold uppercase headings with gradient bar · bottom sheets · subtle press scale (0.97). Respect `prefers-reduced-motion`.

### Page pattern (member pages)
1. Gradient top bar (back + title)
2. Gradient banner with 3D module icon + uppercase title
3. White cards / big app cards on `--surface`
4. Floating white bottom tab bar

---

## Anti-Patterns (do NOT use)

- ❌ New colours outside this palette, or raw logo red for text
- ❌ Emoji as structural icons in new code
- ❌ `maximum-scale` / `user-scalable=no` in the viewport
- ❌ Tap targets under 44px, inputs under 16px
- ❌ `<div onclick>` for actions (use `<button type="button">`)
- ❌ Class `.grid` on the homepage (clashes with `av-splash.php`)
- ❌ Tailwind/React output pasted as-is — rewrite as plain HTML + these classes

---

## Pre-Delivery Checklist

- [ ] Uses `var(--…)` tokens above, no new hex colours
- [ ] Text contrast ≥ 4.5:1 (run axe), focus ring visible
- [ ] Every `<label>` has `for=`; icon-only controls have `aria-label`
- [ ] Works at 390px wide: no sideways scroll, nothing hidden behind the bottom bar
- [ ] Tap targets ≥ 44px; inputs ≥ 16px
- [ ] `prefers-reduced-motion` respected
- [ ] New module added to `app_modules()` in `includes/icons.php` (menu + dashboard + banner icon)
