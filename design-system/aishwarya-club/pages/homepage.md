# Homepage override (`Av/mynamec_/index.php`)

These rules **override** MASTER.md for the public homepage only.

- The homepage has its own `:root` tokens: `--p --p2 --p-soft --a --a-light --a-tx --ink --surface --tx --t2 --t3 --brand`.
- `--p` (main colour), `--a` (accent) and the font come from **Club Settings → Homepage**
  (`home_primary_color`, `home_accent_color`, `home_font`). Defaults: `#0A14E0`, `#E30613`, Plus Jakarta Sans.
- `--brand` = gradient from accent to primary — used for the top bar when scrolled, the login button, the hero CTA and the round centre button.
- Sections (each can be switched off in settings, `home_*_show = '0'`): hero, stats, about, activities, events,
  notice board, committee, achievements, gallery, join box. Dark sections use `--ink` with soft red/blue glows.
- Section titles: bold uppercase + 56px gradient bar (`.sec-title::after`).
- Login popup logic (passkey keypad, register, optional WhatsApp code) must not be changed when restyling.
- Never use the class name `.grid` here; use `.cgrid`.
