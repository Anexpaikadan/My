# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/aishwarya-club/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.

---

**Project:** Aishwarya Arts & Sports Club (members portal + public website)
**Code:** `Av/mynamec_/` — plain PHP pages, Bootstrap 5.3 (stored locally), one custom stylesheet, plain JavaScript
**Source of truth in code:** `:root` in `Av/mynamec_/assets/css/club.css`

Tested with axe (WCAG 2 AA) on every page at 390px and 1280px wide.

## Two looks

| Where | Body class | Look |
|---|---|---|
| Public site (`index.php`, `contact.php`) | `pub` | Dark: page `#0B1033`, cards `#141A3A`, white text, secondary `#b5b1b1` |
| Member + admin app (all other pages) | `app` | Light: page `#F4F6FB`, white cards, dark sidebar (desktop) and dark top bar |

## Colours (from the club logo)

| Role | Hex | Variable | Notes |
|---|---|---|---|
| Brand (logo red) | `#E30613` | `--brand` | Main buttons (with glow), active states, 4px heading bar |
| Brand dark | `#B80F0A` | `--brand-dark` | Hover |
| Accent (logo blue) | `#0A14E0` | `--accent` | Secondary highlights |
| Dark | `#141A3A` | `--dark` | Cards on the public page, sidebar |
| Page dark | `#0B1033` | `--page-dark` | Public page background, top bar |
| Red text on dark | `#FF5A52` | `--brand-text` | Never use `--brand` for small text on dark |
| Blue text on dark | `#8F97FF` | `--accent-text` | Focus rings on dark |
| Muted on dark | `#b5b1b1` | `--muted` | Secondary text on dark |
| Gold | `#E8B923` | `--gold` | Achievements slider |
| WhatsApp | `#25D366` | `--wa` | Always with dark text `#0B1033` |
| Text (light app) | `#0B1033` / `#3B4266` / `#565D82` | `--text --text-2 --text-3` | |

## Type and shape

- Font: system stack (`system-ui, -apple-system, Segoe UI, Roboto, Noto Sans Malayalam`) — nothing to download, Malayalam supported.
- Headings: weight 900, UPPERCASE. Big titles slightly italic (`.h-big`). Section headings (`.h-sec`) have a 3rem × 4px red bar.
- Radius: cards 1rem, buttons .6rem, pills 2rem. Soft shadows.
- Inputs at least 48–52px tall, 16px text. Tap targets at least 44px.

## Layout

- Mobile-first at 390px. Programs and shop: 2 per row on phones, 4 on desktop. Sliders: 78% cards on phones,
  3 per row on desktop, scroll-snap, arrows, dots, 4s auto-slide that pauses on touch and is off for reduced motion.
- Public bottom bar: Home / raised red Market button / Login (or Dashboard / My account). Desktop: centred, 480px, rounded top.
- App bottom bar (phones): 5 tabs with a raised centre button (Admin for admins, Market for members) and a "More" page.
  Desktop (≥992px): dark sidebar instead.

## Rules

- Escape all output with `h()`. All fixed texts in `includes/lang.php` (English + Malayalam).
- Admin deletes and money changes: `sudo_require()` on the server + `data-sudo` on the form.
- Public forms: honeypot field `.hp` + per-IP limit.
- Images: `loading="lazy"`, `width`/`height`, `alt`. Uploads are resized by `img_optimize()`.
- Icons: Bootstrap Icons (`bi bi-…`) with `aria-hidden="true"`; icon-only buttons need `aria-label`.
