# How to use UI/UX Pro Max (for the club website)

UI/UX Pro Max is installed in this repo at `.claude/skills/`. It gives Claude Code a design rulebook
(colours, fonts, layouts, accessibility) plus a searchable design database.

## 1. Easiest way — just ask Claude

Open Claude Code on this repo and ask in plain words. The skill turns on by itself for design work.
To force it, start your message with **`/ui-ux-pro-max`**.

Examples you can copy:

| You want | Type this |
|---|---|
| Check a page for problems | `/ui-ux-pro-max review modules/events.php for mobile and accessibility issues` |
| Redesign a page | `/ui-ux-pro-max redesign the Blood Hub page using our design system` |
| A new module | `/ui-ux-pro-max build a new Attendance module for the club, same design as other modules` |
| Fix a look problem | `/ui-ux-pro-max the buttons on the Market page look too small on phones, fix them` |
| Colours / fonts ideas | `/ui-ux-pro-max suggest a festival colour theme for the Onam page` |
| A chart | `/ui-ux-pro-max add a chart of members per blood group to the admin Reports tab` |

Claude will first read **`design-system/aishwarya-club/MASTER.md`** (our real colours, fonts, components)
and, for the homepage, **`design-system/aishwarya-club/pages/homepage.md`**. So new work keeps the logo red-blue look.

Other skills installed with it (use the same way): `/design-system`, `/ui-styling`, `/brand`,
`/banner-design` (posters, social banners), `/slides` (presentations), `/design`.

## 2. The search tool (optional, for more ideas)

Needs Python 3. Run from the repo folder:

```bash
# A full design direction for an idea
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "sports club event registration" --design-system

# One topic only (domains: ux, color, typography, style, landing, chart, icons, google-fonts, gsap)
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "form error message" --domain ux
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "festival vibrant" --domain color
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "bold sports headline" --domain typography
python3 .claude/skills/ui-ux-pro-max/scripts/search.py "bar chart comparison" --domain chart
```

Tips: use 2–5 words about **one** thing. If the result is off-topic, try once more with different words.

## 3. Our rules in short (from MASTER.md)

- Colours: white background, logo blue `#0A14E0`, logo red `#E30613`, red→blue gradient for bars and banners.
- Font: Plus Jakarta Sans, bold uppercase headings with a small gradient bar.
- Icons: 3D pictures for apps/modules, SVG line icons for buttons. No emoji as icons in new code.
- Phones first: 44px tap targets, 16px text boxes, nothing behind the bottom bar, no sideways scroll.
- Readable: text contrast at least 4.5:1, every field has a label.

## 4. Updating the design rules

If you change the look (for example a new colour), ask Claude to update
`design-system/aishwarya-club/MASTER.md` too, so later work follows the new rule.
For one page that should look different, add `design-system/aishwarya-club/pages/<page-name>.md`.
