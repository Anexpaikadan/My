<?php
// Public home page (what visitors see at the site address): photo, programs, fees, timings, rules,
// shop and contact. Texts, photo and sections are set by the admin in "Public page".

require_once __DIR__ . '/includes/init.php';

$plans = pub_on('fees') ? q('SELECT * FROM plans WHERE active = 1 ORDER BY sort_order, id')->fetchAll() : [];
$products = pub_on('shop') ? q('SELECT * FROM products WHERE active = 1 ORDER BY sort_order, id DESC LIMIT 4')->fetchAll() : [];
$wa = pub_wa_phone();
$joinWa = wa_link($wa, t('wa_join_enquiry', gym_title()));
$phones = array_filter([setting('phone1'), setting('phone2')]);
$icons = ['bi-fire', 'bi-trophy-fill', 'bi-lightning-charge-fill', 'bi-heart-pulse-fill', 'bi-shield-fill-check', 'bi-people-fill'];

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
    <div class="d-flex gap-2 justify-content-center flex-wrap">
      <a href="<?= e($joinWa) ?>" class="btn btn-primary btn-lg px-4" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(pub('pub_join_text')) ?></a>
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

<?php if (pub_on('programs') && pub_lines('pub_programs')): ?>
  <section class="pub-sec">
    <h2 class="pub-h"><?= e(pub('pub_programs_title')) ?></h2>
    <div class="pub-grid">
      <?php foreach (pub_lines('pub_programs') as $i => [$name, $text]): ?>
        <div class="pub-card"><i class="bi <?= $icons[$i % count($icons)] ?> pub-card-ico"></i><h3><?= e($name) ?></h3><?php if ($text !== ''): ?><p><?= e($text) ?></p><?php endif; ?></div>
      <?php endforeach; ?>
    </div>
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
    <a href="<?= e($joinWa) ?>" class="btn btn-primary w-100 mt-2" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(pub('pub_join_text')) ?></a>
  </section>
<?php endif; ?>

<?php if (pub_on('timings') && pub_lines('pub_timings')): ?>
  <section class="pub-sec">
    <h2 class="pub-h"><?= e(pub('pub_timings_title')) ?></h2>
    <div class="pub-times">
      <?php foreach (pub_lines('pub_timings') as [$day, $time]): ?>
        <div><span><?= e($day) ?></span><b><?= e($time) ?></b></div>
      <?php endforeach; ?>
    </div>
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
<?php require __DIR__ . '/includes/footer.php';
