# Homepage (`Av/mynamec_/index.php`) — overrides

- Dark public look (`<body class="pub">`). Sections in order: hero, about, programs, achievements, gallery, events,
  fees, timings, rules, shop, notice board, committee, contact, footer ("Developed by anexpaikadan").
- Every text, heading, photo and section switch comes from Admin → Public Website (`modules/site.php`); do not hard-code them.
- Hero: one photo (max 640px wide, centred), big uppercase italic title, one line under it, glowing "Join the Club"
  button + outline WhatsApp and Call buttons.
- Pop-ups are Bootstrap modals with `.modal-dark`. The member login pop-up keeps its own `.overlay > .lgn` markup and logic.
- Do not use the class name `.grid` here: `av-splash.php` defines a global `.grid` overlay.
