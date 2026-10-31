<?php
// Public page settings: photo, headings and texts of every section on the public home page,
// fees note, class timings, the gym rules, shop name and the WhatsApp numbers for enquiries.

require __DIR__ . '/includes/init.php';
require_admin();

$text = [ // setting => max length
    'pub_hero_title' => 80, 'pub_hero_text' => 250, 'pub_join_text' => 30, 'pub_trial_text' => 40,
    'pub_about_title' => 60, 'pub_about_text' => 1500, 'pub_programs_title' => 60, 'pub_programs' => 2000,
    'pub_fees_title' => 60, 'pub_fees_note' => 300, 'pub_timings_title' => 60, 'pub_timings' => 1000,
    'pub_rules_title' => 60, 'pub_shop_title' => 30, 'pub_shop_text' => 250, 'pub_contact_title' => 60,
    'pub_address' => 300, 'pub_map_url' => 500, 'pub_instagram' => 300, 'pub_whatsapp' => 20, 'shop_whatsapp' => 20,
];
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    foreach ($text as $k => $max) {
        $v = mb_substr(trim(str_replace("\r\n", "\n", (string)($_POST[$k] ?? ''))), 0, $max);
        if (in_array($k, ['pub_map_url', 'pub_instagram'], true) && $v !== '' && !preg_match('#^https?://#i', $v)) {
            $v = 'https://' . $v;
        }
        set_setting($k, $v);
    }
    foreach (PUB_SECTIONS as $s) {
        set_setting('pub_show_' . $s, post('show_' . $s) === '1' ? '1' : '0');
    }
    $rules = rules_from_text((string)($_POST['rules'] ?? ''));
    set_setting('gym_rules', $rules ? json_encode($rules, JSON_UNESCAPED_UNICODE) : '');
    $old = setting('pub_hero_img');
    if (!empty($_FILES['hero']['name'])) {
        $f = save_photo($_FILES['hero'], 1400, __DIR__ . '/media');
        if ($f === null) {
            flash('danger', t('err_photo'));
        } else {
            set_setting('pub_hero_img', $f);
            if ($old !== '') {
                @unlink(__DIR__ . '/media/' . $old);
            }
        }
    } elseif (post('hero_default') === '1' && $old !== '') {
        @unlink(__DIR__ . '/media/' . $old);
        set_setting('pub_hero_img', '');
    }
    flash('success', t('saved'));
    redirect('public_settings.php');
}

$title = t('public_page');
$active = 'public';
$back = 'more.php';
$actions = '<a href="home.php" class="btn btn-outline-primary" target="_blank"><i class="bi bi-box-arrow-up-right"></i> ' . e(t('open_public_page')) . '</a>';
require __DIR__ . '/includes/header.php';
$pv = fn($k) => e(pub($k)); // not $v: header.php uses that name

// A section card: on/off switch, heading and its fields.
$sec = function (string $key, string $titleKey, string $icon, string $fields) use ($pv): void { ?>
  <div class="card mb-3" id="<?= $key ?>"><div class="card-header d-flex align-items-center gap-2">
    <i class="bi <?= $icon ?> text-primary"></i><span class="me-auto fw-bold"><?= e(t('sec_' . $key)) ?></span>
    <div class="form-check form-switch mb-0"><input class="form-check-input" type="checkbox" role="switch" name="show_<?= $key ?>" value="1" id="sw_<?= $key ?>"<?= pub_on($key) ? ' checked' : '' ?>>
      <label class="form-check-label small" for="sw_<?= $key ?>"><?= e(t('show')) ?></label></div></div>
    <div class="card-body">
      <label class="form-label small" for="<?= $titleKey ?>"><?= e(t('heading')) ?></label>
      <input class="form-control mb-3" id="<?= $titleKey ?>" name="<?= $titleKey ?>" value="<?= $pv($titleKey) ?>" maxlength="60">
      <?= $fields ?>
    </div></div>
<?php };
$ta = fn($k, $rows, $help = '') => '<label class="form-label small" for="' . $k . '">' . e(t('content')) . '</label><textarea class="form-control" id="' . $k . '" name="' . $k . '" rows="' . $rows . '">' . $pv($k) . '</textarea>'
    . ($help !== '' ? '<div class="form-text">' . e($help) . '</div>' : '');
?>
<div class="alert alert-light border small"><i class="bi bi-globe2 text-primary"></i> <?= e(t('public_page_help', base_url())) ?></div>
<form method="post" enctype="multipart/form-data"><?= csrf_field() ?>
<div class="row g-3">
  <div class="col-lg-6">
    <div class="card mb-3"><div class="card-header fw-bold"><i class="bi bi-image text-primary"></i> <?= e(t('sec_hero')) ?></div>
      <div class="card-body">
        <img src="<?= e(hero_url()) ?>" alt="" class="img-fluid rounded mb-2 d-block mx-auto" style="max-height:260px">
        <label class="form-label small" for="hero"><?= e(t('change_photo')) ?></label>
        <input class="form-control mb-1" type="file" id="hero" name="hero" accept="image/*">
        <?php if (setting('pub_hero_img') !== ''): ?><div class="form-check small mb-2"><input class="form-check-input" type="checkbox" name="hero_default" value="1" id="hd"><label class="form-check-label" for="hd"><?= e(t('use_default_photo')) ?></label></div><?php endif; ?>
        <label class="form-label small mt-2" for="pub_hero_title"><?= e(t('heading')) ?></label>
        <input class="form-control mb-2" id="pub_hero_title" name="pub_hero_title" value="<?= $pv('pub_hero_title') ?>" maxlength="80">
        <label class="form-label small" for="pub_hero_text"><?= e(t('content')) ?></label>
        <textarea class="form-control mb-2" id="pub_hero_text" name="pub_hero_text" rows="2" maxlength="250"><?= $pv('pub_hero_text') ?></textarea>
        <label class="form-label small" for="pub_join_text"><?= e(t('join_button_text')) ?></label>
        <input class="form-control mb-2" id="pub_join_text" name="pub_join_text" value="<?= $pv('pub_join_text') ?>" maxlength="30">
        <label class="form-label small" for="pub_trial_text"><?= e(t('trial_button_text')) ?></label>
        <input class="form-control" id="pub_trial_text" name="pub_trial_text" value="<?= $pv('pub_trial_text') ?>" maxlength="40">
      </div></div>
    <?php
    $sec('about', 'pub_about_title', 'bi-star-fill', $ta('pub_about_text', 4, t('one_per_line')));
    $sec('programs', 'pub_programs_title', 'bi-fire', $ta('pub_programs', 5, t('title_pipe_text')));
    $sec('fees', 'pub_fees_title', 'bi-cash-coin', '<div class="small mb-2">' . e(t('fees_from_plans')) . ' <a href="plans.php">' . e(t('plans')) . '</a></div>'
        . '<label class="form-label small" for="pub_fees_note">' . e(t('note')) . '</label><input class="form-control" id="pub_fees_note" name="pub_fees_note" value="' . $pv('pub_fees_note') . '" maxlength="300">');
    $sec('timings', 'pub_timings_title', 'bi-clock-fill', $ta('pub_timings', 4, t('day_pipe_time')));
    ?>
  </div>
  <div class="col-lg-6">
    <?php
    $sec('rules', 'pub_rules_title', 'bi-journal-text', '<label class="form-label small" for="rules">' . e(t('content')) . '</label>'
        . '<textarea class="form-control font-monospace small" id="rules" name="rules" rows="16">' . e(rules_to_text(gym_rules())) . '</textarea>'
        . '<div class="form-text">' . e(t('rules_help')) . '</div><a href="rules.php" class="btn btn-sm btn-outline-primary mt-2"><i class="bi bi-eye"></i> ' . e(t('view_and_share')) . '</a>');
    $sec('shop', 'pub_shop_title', 'bi-bag-fill', '<div class="form-text mt-n2 mb-2">' . e(t('shop_title_help')) . '</div>'
        . '<label class="form-label small" for="pub_shop_text">' . e(t('content')) . '</label><input class="form-control mb-2" id="pub_shop_text" name="pub_shop_text" value="' . $pv('pub_shop_text') . '" maxlength="250">'
        . '<label class="form-label small" for="shop_whatsapp">' . e(t('shop_whatsapp')) . '</label><input class="form-control" id="shop_whatsapp" name="shop_whatsapp" value="' . $pv('shop_whatsapp') . '" inputmode="tel" placeholder="' . e(setting('phone1')) . '">'
        . '<a href="products.php" class="btn btn-sm btn-outline-primary mt-2"><i class="bi bi-bag"></i> ' . e(t('products')) . '</a>');
    $sec('contact', 'pub_contact_title', 'bi-geo-alt-fill', '<label class="form-label small" for="pub_address">' . e(t('address')) . '</label><textarea class="form-control mb-2" id="pub_address" name="pub_address" rows="2">' . $pv('pub_address') . '</textarea>'
        . '<label class="form-label small" for="pub_map_url">' . e(t('map_link')) . '</label><input class="form-control mb-2" id="pub_map_url" name="pub_map_url" value="' . $pv('pub_map_url') . '" placeholder="https://maps.app.goo.gl/…">'
        . '<label class="form-label small" for="pub_instagram">Instagram</label><input class="form-control mb-2" id="pub_instagram" name="pub_instagram" value="' . $pv('pub_instagram') . '" placeholder="https://instagram.com/…">'
        . '<label class="form-label small" for="pub_whatsapp">' . e(t('public_whatsapp')) . '</label><input class="form-control" id="pub_whatsapp" name="pub_whatsapp" value="' . $pv('pub_whatsapp') . '" inputmode="tel" placeholder="' . e(setting('phone1')) . '">'
        . '<div class="form-text">' . e(t('public_whatsapp_help')) . '</div>');
    ?>
  </div>
</div>
<div class="mb-4"><button class="btn btn-primary btn-lg w-100"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
</form>
<?php require __DIR__ . '/includes/footer.php';
