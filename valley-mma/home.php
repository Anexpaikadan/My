<?php
// Public home page (what visitors see at the site address): photo, programs, fees, timings, rules,
// shop and contact. Texts, photo and sections are set by the admin in "Public page".

require_once __DIR__ . '/includes/init.php';

$plans = pub_on('fees') ? q('SELECT * FROM plans WHERE active = 1 ORDER BY sort_order, id')->fetchAll() : [];
$products = pub_on('shop') ? q('SELECT * FROM products WHERE active = 1 ORDER BY sort_order, id DESC LIMIT 4')->fetchAll() : [];
$wa = pub_wa_phone();
$joinWa = wa_link($wa, t('wa_join_enquiry', gym_title()));
$phones = array_filter([setting('phone1'), setting('phone2')]);
$programs = programs_list();
$pubBatches = array_values(array_filter(batches(), fn($b) => $b['show_public']));
$achievements = pub_on('achievements') ? achievements_public() : [];
$events = pub_on('events') ? events_upcoming() : [];

$title = pub('pub_hero_title');
$bare = true;
$publicPage = 'home';
require __DIR__ . '/includes/header.php';
?>
<section class="pub-hero">
  <img src="<?= e(hero_url()) ?>" alt="<?= e(gym_title()) ?>" class="pub-hero-img" width="853" height="860">
  <div class="pub-hero-body">
    <h1><?= e(pub('pub_hero_title')) ?></h1>
    <p><?= e(pub('pub_hero_text')) ?></p>
    <button type="button" class="btn btn-primary btn-lg w-100 mb-2 trial-btn" data-bs-toggle="modal" data-bs-target="#trialModal"><i class="bi bi-lightning-charge-fill"></i> <?= e(pub('pub_trial_text')) ?></button>
    <div class="d-flex gap-2 justify-content-center flex-wrap">
      <a href="<?= e($joinWa) ?>" class="btn btn-outline-light btn-lg px-4" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(pub('pub_join_text')) ?></a>
      <?php if ($phones): ?><a href="tel:<?= e(clean_phone(reset($phones))) ?>" class="btn btn-outline-light btn-lg px-4"><i class="bi bi-telephone-fill"></i> <?= e(t('call')) ?></a><?php endif; ?>
    </div>
  </div>
</section>

<div class="pub-wrap">
<?php if (pub_on('about') && trim(pub('pub_about_text')) !== ''): ?>
  <section class="pub-sec">
    <h2 class="pub-h"><?= e(pub('pub_about_title')) ?></h2>
    <ul class="pub-ticks">
      <?php foreach (preg_split('/\R/', trim(pub('pub_about_text'))) as $line): if (trim($line) === '') continue; ?>
        <li><i class="bi bi-check-circle-fill"></i><span><?= e(trim($line)) ?></span></li>
      <?php endforeach; ?>
    </ul>
  </section>
<?php endif; ?>

<?php if (pub_on('programs') && $programs): ?>
  <section class="pub-sec" id="programs">
    <h2 class="pub-h"><?= e(pub('pub_programs_title')) ?></h2>
    <div class="prog-grid">
      <?php foreach ($programs as $p): $img = safe_img($p['image']); ?>
        <button type="button" class="prog-card" data-program="<?= $p['id'] ?>">
          <span class="prog-img"<?= $img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '' ?>><?php if ($img === ''): ?><i class="bi bi-fire"></i><?php endif; ?></span>
          <span class="prog-body"><span class="prog-name"><?= e($p['name']) ?></span>
            <?php if ($p['short_text'] !== ''): ?><span class="prog-short"><?= e($p['short_text']) ?></span><?php endif; ?>
            <span class="prog-more"><?= e(t('more_details')) ?> <i class="bi bi-arrow-right"></i></span></span>
        </button>
      <?php endforeach; ?>
    </div>
  </section>
<?php endif; ?>

<?php if ($events): ?>
  <section class="pub-sec" id="events">
    <h2 class="pub-h"><?= e(pub('pub_events_title')) ?></h2>
    <div class="ev-track">
      <?php foreach ($events as $ev) echo event_card_html($ev, 'event.php?id=' . (int)$ev['id']); ?>
    </div>
  </section>
<?php endif; ?>

<?php if ($achievements): ?>
  <section class="pub-sec" id="champions">
    <h2 class="pub-h d-flex align-items-center"><span class="me-auto"><?= e(pub('pub_achievements_title')) ?></span>
      <span class="ach-arrows"><button type="button" class="btn btn-sm btn-outline-light" data-ach-go="-1" aria-label="Back"><i class="bi bi-chevron-left"></i></button>
        <button type="button" class="btn btn-sm btn-outline-light" data-ach-go="1" aria-label="Next"><i class="bi bi-chevron-right"></i></button></span></h2>
    <div class="ach-track" id="achTrack">
      <?php foreach ($achievements as $a): $img = safe_img($a['image']); ?>
        <button type="button" class="ach-card" data-ach="<?= $a['id'] ?>">
          <span class="ach-img<?= $img === '' ? ' noimg' : '' ?>"<?= $img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '' ?>><?php if ($img === ''): ?><i class="bi bi-trophy-fill"></i><img src="assets/logo.png" alt="" class="ach-logo"><?php endif; ?>
            <span class="ach-badge"><i class="bi bi-trophy-fill"></i></span></span>
          <span class="ach-body"><span class="ach-title"><?= e($a['title']) ?></span><span class="ach-name"><?= e($a['athlete']) ?></span>
            <?php if ($a['event'] !== '' || $a['ach_date']): ?><span class="ach-event"><?= e(trim($a['event'] . ($a['ach_date'] ? ' · ' . date('M Y', strtotime($a['ach_date'])) : ''), ' ·')) ?></span><?php endif; ?></span>
        </button>
      <?php endforeach; ?>
    </div>
    <div class="ach-dots" id="achDots"></div>
  </section>
<?php endif; ?>

<?php if (pub_on('fees') && $plans): ?>
  <section class="pub-sec">
    <h2 class="pub-h"><?= e(pub('pub_fees_title')) ?></h2>
    <div class="pub-grid">
      <?php foreach ($plans as $i => $p): ?>
        <div class="pub-card pub-fee<?= $i === 1 ? ' hot' : '' ?>">
          <div class="pub-fee-name"><?= e($p['name']) ?></div>
          <div class="pub-fee-price"><?= money($p['price']) ?></div>
          <div class="pub-fee-dur"><?= e(plan_duration($p)) ?></div>
          <?php if ($p['description'] !== ''): ?><p><?= e($p['description']) ?></p><?php endif; ?>
        </div>
      <?php endforeach; ?>
    </div>
    <?php if (pub('pub_fees_note') !== ''): ?><p class="pub-note"><i class="bi bi-info-circle"></i> <?= e(pub('pub_fees_note')) ?></p><?php endif; ?>
    <button type="button" class="btn btn-primary btn-lg w-100 mt-2" data-bs-toggle="modal" data-bs-target="#trialModal"><i class="bi bi-lightning-charge-fill"></i> <?= e(pub('pub_trial_text')) ?></button>
  </section>
<?php endif; ?>

<?php if (pub_on('timings') && ($pubBatches || pub_lines('pub_timings'))): ?>
  <section class="pub-sec" id="timings">
    <h2 class="pub-h"><?= e(pub('pub_timings_title')) ?></h2>
    <?php if ($pubBatches): ?>
      <div class="pub-batches">
        <?php foreach ($pubBatches as $b): $h = (int)substr($b['start_time'], 0, 2); ?>
          <div class="pub-batch"><span class="pub-batch-ico"><i class="bi bi-<?= $h < 12 ? 'sunrise' : ($h < 18 ? 'sun' : 'moon-stars') ?>-fill"></i></span>
            <span class="me-auto"><b><?= e($b['name']) ?></b><small><?= e(batch_days($b)) ?><?= $b['trainer'] !== '' ? ' · ' . e($b['trainer']) : '' ?><?= $b['note'] !== '' ? ' · ' . e($b['note']) : '' ?></small></span>
            <span class="pub-batch-time"><?= e(time_text($b['start_time'])) ?><small><?= e(time_text($b['end_time'])) ?></small></span></div>
        <?php endforeach; ?>
      </div>
      <?php foreach (pub_lines('pub_timings') as [$day, $time]): if (stripos($time, 'closed') === false && stripos($day, 'sunday') === false) continue; ?>
        <p class="pub-note"><i class="bi bi-info-circle"></i> <?= e($day . ($time !== '' ? ': ' . $time : '')) ?></p>
      <?php endforeach; ?>
    <?php else: ?>
      <div class="pub-times">
        <?php foreach (pub_lines('pub_timings') as [$day, $time]): ?>
          <div><span><?= e($day) ?></span><b><?= e($time) ?></b></div>
        <?php endforeach; ?>
      </div>
    <?php endif; ?>
  </section>
<?php endif; ?>

<?php if (pub_on('rules')): ?>
  <section class="pub-sec">
    <h2 class="pub-h"><?= e(pub('pub_rules_title')) ?></h2>
    <?= rules_html() ?>
  </section>
<?php endif; ?>

<?php if (pub_on('shop') && $products): ?>
  <section class="pub-sec">
    <h2 class="pub-h d-flex align-items-center"><span class="me-auto"><?= e(pub('pub_shop_title')) ?></span><a href="shop.php" class="btn btn-sm btn-outline-light"><?= e(t('view_all')) ?></a></h2>
    <div class="shop-grid">
      <?php foreach ($products as $p): $imgs = product_images($p); ?>
        <a href="shop.php#p<?= $p['id'] ?>" class="shop-item"><div class="shop-thumb"><?php if ($imgs): ?><img src="<?= e(product_img_url($imgs[0])) ?>" alt="" loading="lazy"><?php else: ?><i class="bi bi-bag"></i><?php endif; ?></div>
          <div class="shop-name"><?= e($p['name']) ?></div><div class="shop-price"><?= product_price_html($p) ?></div></a>
      <?php endforeach; ?>
    </div>
  </section>
<?php endif; ?>

<?php if (pub_on('contact')): ?>
  <section class="pub-sec">
    <h2 class="pub-h"><?= e(pub('pub_contact_title')) ?></h2>
    <div class="pub-card text-start">
      <?php if (pub('pub_address') !== ''): ?><p class="mb-3"><i class="bi bi-geo-alt-fill text-primary"></i> <?= e(pub('pub_address')) ?></p><?php endif; ?>
      <div class="d-grid gap-2">
        <?php foreach ($phones as $ph): ?><a class="btn btn-outline-light" href="tel:<?= e(clean_phone($ph)) ?>"><i class="bi bi-telephone-fill"></i> <?= e($ph) ?></a><?php endforeach; ?>
        <a class="btn btn-whatsapp" href="<?= e(wa_link($wa, t('wa_hello_gym', gym_title()))) ?>" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> WhatsApp</a>
        <?php if (pub('pub_map_url') !== ''): ?><a class="btn btn-outline-light" href="<?= e(pub('pub_map_url')) ?>" target="_blank" rel="noopener"><i class="bi bi-map-fill"></i> <?= e(t('open_map')) ?></a><?php endif; ?>
        <?php if (pub('pub_instagram') !== ''): ?><a class="btn btn-outline-light" href="<?= e(pub('pub_instagram')) ?>" target="_blank" rel="noopener"><i class="bi bi-instagram"></i> Instagram</a><?php endif; ?>
      </div>
    </div>
  </section>
<?php endif; ?>
</div>

<div class="modal fade" id="trialModal" tabindex="-1" aria-labelledby="trialTitle" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered"><form class="modal-content pub-modal" method="post" action="trial.php" id="trial"><?= csrf_field() ?>
    <div class="modal-header"><h2 class="modal-title h5" id="trialTitle"><i class="bi bi-lightning-charge-fill text-primary"></i> <?= e(pub('pub_trial_text')) ?></h2>
      <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button></div>
    <div class="modal-body">
      <p class="small mb-3" style="color:#c9c5c5"><?= e(t('trial_form_help')) ?></p>
      <div class="d-none"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
      <label class="form-label small" for="trName"><?= e(t('name')) ?> *</label>
      <input class="form-control form-control-lg mb-2" id="trName" name="name" maxlength="100" required autocomplete="name">
      <label class="form-label small" for="trPlace"><?= e(t('place')) ?></label>
      <input class="form-control form-control-lg mb-2" id="trPlace" name="place" maxlength="100" autocomplete="address-level2">
      <label class="form-label small" for="trPhone"><?= e(t('whatsapp_number')) ?> *</label>
      <input class="form-control form-control-lg mb-2" id="trPhone" name="phone" type="tel" inputmode="tel" required pattern="[+0-9 ]{10,16}" placeholder="9XXXXXXXXX" autocomplete="tel">
      <?php if ($pubBatches): ?>
        <label class="form-label small" for="trBatch"><?= e(t('preferred_batch')) ?></label>
        <select class="form-select form-select-lg mb-2" id="trBatch" name="batch_id"><option value=""><?= e(t('any_time')) ?></option>
          <?php foreach ($pubBatches as $b): ?><option value="<?= $b['id'] ?>"><?= e($b['name'] . ' · ' . batch_time($b)) ?></option><?php endforeach; ?></select>
      <?php endif; ?>
      <?php if ($programs): ?>
        <label class="form-label small d-block"><?= e(t('interested_in')) ?></label>
        <div class="d-flex flex-wrap gap-1 cat-opt">
          <?php foreach ($programs as $i => $p): ?>
            <input type="radio" class="btn-check" name="program" value="<?= e($p['name']) ?>" id="trp<?= $i ?>"><label class="btn btn-sm btn-outline-light" for="trp<?= $i ?>"><?= e($p['name']) ?></label>
          <?php endforeach; ?>
        </div>
      <?php endif; ?>
    </div>
    <div class="modal-footer"><button class="btn btn-primary btn-lg w-100"><i class="bi bi-send"></i> <?= e(t('submit_request')) ?></button></div>
  </form></div>
</div>

<div class="modal fade" id="infoModal" tabindex="-1" aria-labelledby="infoName" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable"><div class="modal-content pub-modal overflow-hidden">
    <div class="info-img" id="infoImg"><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button></div>
    <div class="modal-body">
      <div class="info-kicker" id="infoKicker"></div>
      <h2 class="h3 fw-bold text-uppercase mb-1" id="infoName"></h2>
      <p class="info-short" id="infoShort"></p>
      <div class="info-rows" id="infoRows"></div>
      <p class="mb-0" id="infoDetails" style="white-space:pre-line"></p>
    </div>
    <div class="modal-footer border-0 pt-0" id="infoFoot">
      <button type="button" class="btn btn-primary btn-lg w-100" id="infoTrial"><i class="bi bi-lightning-charge-fill"></i> <?= e(pub('pub_trial_text')) ?></button>
    </div>
  </div></div>
</div>
<script>window.VM_HOME = <?= json_encode([
    'programs' => array_map('program_json', $programs),
    'ach' => array_map(fn($a) => ['id' => (int)$a['id'], 'title' => $a['title'], 'name' => $a['athlete'], 'event' => $a['event'],
        'date' => $a['ach_date'] ? date('d M Y', strtotime($a['ach_date'])) : '', 'details' => (string)$a['details'], 'img' => safe_img($a['image'])], $achievements),
    't' => ['for' => t('suitable_for'), 'when' => t('class_time'), 'trainer' => t('trainer'), 'program' => pub('pub_programs_title'), 'ach' => pub('pub_achievements_title')],
], JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP) ?>;</script>
<?php
$scripts = ['assets/home.js?v=' . APP_VERSION];
require __DIR__ . '/includes/footer.php';
