<?php
// Customer upload page – this is the page the shop QR code opens.

require __DIR__ . '/lib.php';

// Which shop? The QR code link has ?shop=<slug> (remembered in a cookie); with only one shop it is used directly.
$slug = (string)($_GET['shop'] ?? $_POST['shop'] ?? $_COOKIE['daybill_shop'] ?? '');
$shopRow = $slug !== '' ? shop_by_slug($slug) : null;
if (!$shopRow) {
    $active = all_shops(true);
    $shopRow = count($active) === 1 ? $active[0] : null;
}
if (!$shopRow) {
    page_header('Choose shop');
    echo '<div class="card"><h1>Choose your shop · اختر المحل</h1><div class="menu">';
    foreach ($active as $sh) {
        echo '<a class="menu-item" href="index.php?shop=' . h(rawurlencode($sh['slug'])) . '"><span class="ic">🖨️</span>'
            . '<span class="txt"><b>' . h($sh['name']) . '</b></span><span class="chev">›</span></a>';
    }
    echo $active ? '' : '<p class="muted">No shop is open at the moment.</p>';
    echo '</div></div>';
    page_footer();
    exit;
}
shop_id((int)$shopRow['id']);
if (($_COOKIE['daybill_shop'] ?? '') !== $shopRow['slug']) {
    setcookie('daybill_shop', $shopRow['slug'], ['expires' => time() + 31536000, 'path' => '/', 'secure' => true, 'samesite' => 'Lax']);
}
$self = 'index.php?shop=' . rawurlencode($shopRow['slug']);

function make_code(): string
{
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no 0/O/1/I
    $code = '';
    for ($i = 0; $i < 4; $i++) {
        $code .= $chars[random_int(0, strlen($chars) - 1)];
    }
    return $code;
}

function handle_upload(): array
{
    if (empty($_FILES['files']) || !is_array($_FILES['files']['name'])) {
        return ['ok' => false, 'error' => t('err_none')];
    }
    $files = $_FILES['files'];
    if (count($files['name']) > cfg('max_files')) {
        return ['ok' => false, 'error' => t('err_max', cfg('max_files'))];
    }
    $maxBytes = cfg('max_file_mb') * 1048576;
    $dir = cfg('upload_dir');
    if (!is_dir($dir)) {
        mkdir($dir, 0770, true);
    }

    $accepted = [];
    foreach ($files['name'] as $i => $name) {
        if ($files['error'][$i] === UPLOAD_ERR_NO_FILE) {
            continue;
        }
        if ($files['error'][$i] === UPLOAD_ERR_INI_SIZE || $files['error'][$i] === UPLOAD_ERR_FORM_SIZE
            || $files['size'][$i] > $maxBytes) {
            return ['ok' => false, 'error' => t('err_big', $name, cfg('max_file_mb'))];
        }
        if ($files['error'][$i] !== UPLOAD_ERR_OK) {
            return ['ok' => false, 'error' => t('err_fail', $name)];
        }
        $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
        if (!in_array($ext, ALLOWED_EXT, true)) {
            return ['ok' => false, 'error' => t('err_type', $name)];
        }
        $tmp = $files['tmp_name'][$i];
        $head = (string)file_get_contents($tmp, false, null, 0, 8);
        if ($ext === 'pdf' && strncmp($head, '%PDF', 4) !== 0) {
            return ['ok' => false, 'error' => t('err_pdf', $name)];
        }
        if (in_array($ext, ['jpg', 'jpeg', 'png'], true) && @getimagesize($tmp) === false) {
            return ['ok' => false, 'error' => t('err_img', $name)];
        }
        $accepted[] = ['i' => $i, 'name' => $name, 'ext' => $ext, 'tmp' => $tmp, 'size' => (int)$files['size'][$i]];
    }
    if (!$accepted) {
        return ['ok' => false, 'error' => t('err_none')];
    }

    $pdo = db();
    // Order check "pin": the customer gets a 4-digit PIN that staff must type before printing.
    $pin = verify_mode() === 'pin' ? str_pad((string)random_int(0, 9999), 4, '0', STR_PAD_LEFT) : '';
    $pdo->beginTransaction();
    $saved = [];
    $total = 0.0;
    $unknown = false;
    try {
        $jobId = 0;
        for ($try = 0; $try < 20 && !$jobId; $try++) {
            $code = make_code();
            try {
                $st = $pdo->prepare('INSERT INTO jobs (shop_id, code, customer_name, phone, note, pin, verified) VALUES (?, ?, ?, ?, ?, ?, ?)');
                $st->execute([
                    shop_id(),
                    $code,
                    mb_substr(trim((string)($_POST['customer_name'] ?? '')), 0, 100),
                    mb_substr(trim((string)($_POST['phone'] ?? '')), 0, 30),
                    mb_substr(trim((string)($_POST['note'] ?? '')), 0, 500),
                    $pin,
                    $pin === '' ? 1 : 0,
                ]);
                $jobId = (int)$pdo->lastInsertId();
            } catch (PDOException $e) {
                if ($e->errorInfo[1] != 1062) { // not a duplicate code
                    throw $e;
                }
            }
        }
        if (!$jobId) {
            throw new RuntimeException('Could not create order code');
        }

        $ins = $pdo->prepare('INSERT INTO job_files
            (job_id, original_name, stored_name, orig_name, orig_ext, ext, size_bytes, pages_total,
             copies, paper, color, sides, orientation, page_range, layout, kind, previews)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
        $opts = $_POST['opt'] ?? [];
        $prints = $_FILES['print'] ?? null;
        foreach ($accepted as $f) {
            $stored = bin2hex(random_bytes(16)) . '.' . $f['ext'];
            if (!move_uploaded_file($f['tmp'], $dir . '/' . $stored)) {
                throw new RuntimeException('Could not save file');
            }
            $saved[] = $dir . '/' . $stored;
            $ext = $f['ext'];
            $origName = $origExt = '';
            $o = clean_options(is_array($opts[$f['i']] ?? null) ? $opts[$f['i']] : []);
            // Layout (pages per sheet, photo sheet) or Photo print tool: the browser sent a print-ready PDF as print[i].
            $kind = ($opts[$f['i']]['kind'] ?? '') === 'photo' && photo_enabled() ? 'photo' : '';
            $layout = $kind === 'photo' ? clean_photo_layout((string)($opts[$f['i']]['layout'] ?? ''))
                : clean_layout((string)($opts[$f['i']]['layout'] ?? ''));
            if ($kind === 'photo') {
                $o = ['copies' => 1, 'paper' => photo_paper(), 'color' => 'color', 'sides' => 'single',
                      'orientation' => 'portrait', 'page_range' => ''];
            }
            $ptmp = $prints['tmp_name'][$f['i']] ?? '';
            if ($layout !== '' && $ptmp !== '' && ($prints['error'][$f['i']] ?? 1) === UPLOAD_ERR_OK
                && $prints['size'][$f['i']] <= cfg('max_file_mb') * 1048576 * 2
                && strncmp((string)file_get_contents($ptmp, false, null, 0, 4), '%PDF', 4) === 0) {
                $printName = bin2hex(random_bytes(16)) . '.pdf';
                if (!move_uploaded_file($ptmp, $dir . '/' . $printName)) {
                    throw new RuntimeException('Could not save file');
                }
                $saved[] = $dir . '/' . $printName;
                [$origName, $origExt, $stored, $ext] = [$stored, $f['ext'], $printName, 'pdf'];
                $o['page_range'] = ''; // already applied in the layout
            } else {
                $layout = $kind = '';
            }
            // Photo items: pictures of the sheets for the shop staff (JPEG only).
            $previews = 0;
            if ($kind === 'photo') {
                $pv = $_FILES['preview'] ?? null;
                foreach ((array)($pv['tmp_name'][$f['i']] ?? []) as $k => $ptmp2) {
                    if ($previews < 6 && ($pv['error'][$f['i']][$k] ?? 1) === UPLOAD_ERR_OK && $pv['size'][$f['i']][$k] < 5242880
                        && (@getimagesize($ptmp2)[2] ?? 0) === IMAGETYPE_JPEG
                        && move_uploaded_file($ptmp2, $dir . '/' . $stored . '.p' . $previews . '.jpg')) {
                        $saved[] = $dir . '/' . $stored . '.p' . $previews . '.jpg';
                        $previews++;
                    }
                }
            }
            $pages = $ext === 'pdf' ? pdf_page_count($dir . '/' . $stored)
                : (in_array($ext, ['jpg', 'jpeg', 'png'], true) ? 1 : 0);
            $ins->execute([$jobId, mb_substr(basename($f['name']), 0, 255), $stored, $origName, $origExt, $ext, $f['size'], $pages,
                $o['copies'], $o['paper'], $o['color'], $o['sides'], $o['orientation'], $o['page_range'], $layout, $kind, $previews]);
            $total += auto_price($o + ['pages_total' => $pages, 'layout' => $layout, 'kind' => $kind]);
            $unknown = $unknown || $pages === 0;
        }
        $pdo->commit();
    } catch (Throwable $e) {
        $pdo->rollBack();
        array_map('unlink', $saved);
        error_log('Daybill upload error: ' . $e->getMessage());
        return ['ok' => false, 'error' => t('err_server')];
    }
    if (verify_mode() === 'auto') {
        auto_print_job($jobId); // no check: print straight away
    }
    return ['ok' => true, 'code' => $code, 'files' => count($accepted), 'pin' => $pin,
        'auto' => verify_mode() === 'auto' && setting('print_mode', 'local') !== 'browser',
        'price' => $unknown ? '' : money($total)];
}

$lang = lang();
$result = null;

// Page count only (nothing is stored) – fallback for phones that cannot read the PDF themselves.
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['ajax'] ?? '') === 'count') {
    $tmp = $_FILES['pdf']['tmp_name'] ?? '';
    $ok = $tmp !== '' && ($_FILES['pdf']['error'] ?? 1) === UPLOAD_ERR_OK
        && strncmp((string)file_get_contents($tmp, false, null, 0, 4), '%PDF', 4) === 0;
    header('Content-Type: application/json');
    echo json_encode(['pages' => $ok ? pdf_page_count($tmp) : 0]);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $result = empty($_POST) && empty($_FILES)
        ? ['ok' => false, 'error' => t('err_post', cfg('max_file_mb'))]
        : handle_upload();
    if (($_POST['ajax'] ?? '') === '1' || empty($_POST)) {
        header('Content-Type: application/json');
        echo json_encode($result);
        exit;
    }
}

$papers = enabled_papers();
$colors = enabled_colors();
$sides = enabled_sides();

// Rules for every offered combination, for the live price estimate.
$rules = [];
foreach ($papers as $p) {
    foreach ($colors as $c) {
        foreach ($sides as $s) {
            $rules[$p][$c][$s] = price_rule($p, $c, $s);
        }
    }
}

// Layouts this shop offers, with names in the customer's language; optional fixed sheet prices.
$layoutsJs = [];
$layoutPrices = [];
foreach (enabled_layouts() as $id => $L) {
    $layoutsJs[] = $L + ['id' => $id, 'name' => t('L_' . $id) !== 'L_' . $id ? t('L_' . $id) : $L['label']];
    if (($lp = layout_price($id)) !== null) {
        $layoutPrices[$id] = $lp;
    }
}

// Photo print tool: sizes, paper and prices of this shop.
$photoJs = null;
if (photo_enabled()) {
    $photoJs = ['paper' => photo_paper(), 'price' => setting('photo_price', ''), 'mode' => setting('photo_price_mode', 'photo'),
        'rule' => price_rule(photo_paper(), 'color', 'single'), 'sizes' => []];
    foreach (photo_sizes() as $id => $L) {
        $photoJs['sizes'][] = ['id' => $id, 'w' => $L['w'], 'h' => $L['h'], 'type' => 'size',
            'name' => t('L_' . $id) !== 'L_' . $id ? t('L_' . $id) : $L['label']];
    }
}

// A select, or a fixed label when only one choice is offered.
function choice(string $key, string $label, array $values, bool $translate): string
{
    $text = fn($v) => $translate ? t($v) : $v;
    if (count($values) === 1) {
        return '<label>' . h(t($label)) . '<span class="fixed">' . h($text($values[0])) . '</span>'
            . '<input type="hidden" data-k="' . $key . '" value="' . h($values[0]) . '"></label>';
    }
    $s = '<label>' . h(t($label)) . '<select data-k="' . $key . '">';
    foreach ($values as $v) {
        $s .= '<option value="' . h($v) . '">' . h($text($v)) . '</option>';
    }
    return $s . '</select></label>';
}

function rule_text(array $r): string
{
    [$n, $base, $extra] = $r;
    if ($n <= 1 && abs($base - $extra) < 0.001) {
        return t('rule_flat', money($extra));
    }
    return t('rule', $n, money($base), money($extra));
}

page_header(t('title'), false, $lang);
$accept = '.' . implode(',.', ALLOWED_EXT);
?>
<?php if ($result && $result['ok']): ?>
  <div class="card center">
    <h1><?= h(t('sent')) ?></h1>
    <p><?= h(t('show_code')) ?></p>
    <div class="bigcode"><?= h($result['code']) ?></div>
    <?php if ($result['pin'] !== ''): ?>
      <div class="pin-box"><span><?= h(t('pin_title')) ?></span><b><?= h($result['pin']) ?></b><small><?= h(t('pin_tell')) ?></small></div>
    <?php elseif ($result['auto']): ?>
      <div class="alert ok">🖨 <?= h(t('auto_printing')) ?></div>
    <?php endif; ?>
    <p class="pay-box"><?= h($result['price'] !== '' ? t('estimate') : t('estimate_ph')) ?><?php if ($result['price'] !== ''): ?><b><?= h($result['price']) ?></b><?php endif; ?></p>
    <p class="muted"><?= h(t('final_note')) ?></p>
    <a class="btn block" href="<?= h($self) ?>"><?= h(t('send_more')) ?></a>
  </div>
<?php else: ?>
  <?php if ($result): ?><div class="alert err"><?= h($result['error']) ?></div><?php endif; ?>

  <div id="done" class="card center hidden">
    <h1><?= h(t('sent')) ?></h1>
    <p><?= h(t('show_code')) ?></p>
    <div class="bigcode" id="doneCode"></div>
    <div class="pin-box hidden" id="donePin"><span><?= h(t('pin_title')) ?></span><b></b><small><?= h(t('pin_tell')) ?></small></div>
    <div class="alert ok hidden" id="doneAuto">🖨 <?= h(t('auto_printing')) ?></div>
    <p id="donePrice" class="pay-box"></p>
    <p class="muted"><?= h(t('final_note')) ?></p>
    <a class="btn block" href="<?= h($self) ?>"><?= h(t('send_more')) ?></a>
  </div>

  <form id="upForm" method="post" enctype="multipart/form-data" class="card">
    <h1><?= h(t('title')) ?></h1>
    <p class="muted"><?= h(t('hint', cfg('max_file_mb'))) ?></p>

    <label class="drop" id="drop">
      <input type="file" id="picker" name="files[]" multiple accept="<?= h($accept) ?>">
      <span><?= h(t('choose')) ?></span>
    </label>
    <?php if ($photoJs): ?>
      <button type="button" class="photo-entry" id="photoBtn">
        <span class="pe-ic">📷</span><span><b><?= h(t('photo_print')) ?></b><small><?= h(t('photo_print_sub')) ?></small></span><span class="chev">›</span>
      </button>
    <?php endif; ?>

    <div id="list"></div>
    <div id="total" class="pay-box hidden"></div>

    <!-- Used when JavaScript is off: options of the first file -->
    <noscript>
      <div class="opts">
        <label><?= h(t('copies')) ?><input type="number" name="opt[0][copies]" value="1" min="1" max="999"></label>
        <label><?= h(t('paper')) ?><select name="opt[0][paper]"><?php foreach ($papers as $p): ?><option><?= h($p) ?></option><?php endforeach; ?></select></label>
      </div>
    </noscript>

    <div class="icon-btns">
      <button type="button" class="btn" data-sheet="#pricesSheet">💰 <?= h(t('prices')) ?></button>
      <button type="button" class="btn" data-sheet="#meSheet" id="meBtn">👤 <?= h(t('details')) ?></button>
    </div>
    <?= sheet_start('pricesSheet', t('prices')) ?>
      <table class="tbl prices">
        <?php foreach ($rules as $p => $byColor): foreach ($byColor as $c => $bySides): foreach ($bySides as $s => $r): ?>
          <tr><td><b><?= h($p) ?></b> · <?= h(t($c)) ?> · <?= h(t($s)) ?></td><td><?= h(rule_text($r)) ?></td></tr>
        <?php endforeach; endforeach; endforeach; ?>
        <?php foreach ($layoutsJs as $L): if (isset($layoutPrices[$L['id']])): ?>
          <tr><td><b><?= h($L['name']) ?></b></td><td><?= h(money($layoutPrices[$L['id']])) ?></td></tr>
        <?php endif; endforeach; ?>
      </table>
    <?= sheet_end() ?>
    <?= sheet_start('meSheet', t('optional')) ?>
      <label><?= h(t('name')) ?><input name="customer_name" maxlength="100" autocomplete="name"></label>
      <label><?= h(t('phone')) ?><input name="phone" maxlength="30" inputmode="tel" autocomplete="tel"></label>
      <label><?= h(t('note')) ?><input name="note" maxlength="500" placeholder="<?= h(t('note_ph')) ?>"></label>
      <button type="button" class="btn primary block" data-sheet-close><?= h(t('done')) ?></button>
    <?= sheet_end() ?>

    <div id="err" class="alert err hidden"></div>
    <div id="progress" class="progress hidden"><div></div></div>
    <button class="btn primary block big" id="sendBtn"><?= h(t('send')) ?></button>
  </form>
  <div class="card install-card hidden"><?= install_box(false) ?></div>

  <?php if ($photoJs): ?>
  <!-- Photo print tool (full screen) – logic in assets/photo-tool.js -->
  <dialog class="sheet full" id="photoTool">
    <div class="sheet-head"><span class="grip"></span><b>📷 <?= h(t('photo_print')) ?></b><button type="button" class="sheet-x" aria-label="Close">✕</button></div>
    <div class="sheet-body">
      <label class="drop pt-pick" id="ptPick">
        <input type="file" id="ptFile" accept="image/*">
        <span>🖼️ <?= h(t('photo_choose')) ?><small><?= h(t('photo_any')) ?></small></span>
      </label>
      <div class="pt-main hidden" id="ptMain">
        <div class="pt-sizes" id="ptSizes"></div>
        <div class="pt-editor">
          <div class="pt-frame">
            <canvas id="ptStage"></canvas>
            <svg id="ptGuide" class="pt-guide hidden" viewBox="0 0 100 128" preserveAspectRatio="none" aria-hidden="true">
              <ellipse cx="50" cy="52" rx="27" ry="34"/><line x1="0" y1="14" x2="100" y2="14"/><line x1="0" y1="96" x2="100" y2="96"/>
            </svg>
          </div>
          <p class="muted center pt-tip">✋ <?= h(t('photo_move')) ?></p>
          <div class="pt-tools">
            <button type="button" class="btn" id="ptRotate">⟳ <?= h(t('photo_rotate')) ?></button>
            <label class="btn pt-change"><input type="file" id="ptFile2" accept="image/*" hidden>🔄 <?= h(t('photo_change')) ?></label>
            <button type="button" class="btn" id="ptReset">↺ <?= h(t('photo_reset')) ?></button>
          </div>
          <div class="pt-sliders">
            <label>🔍 <?= h(t('photo_zoom')) ?><input type="range" id="ptZoom" min="1" max="5" step="0.01" value="1"></label>
            <label>☀️ <?= h(t('photo_bright')) ?><input type="range" id="ptBright" min="50" max="160" step="1" value="100"></label>
            <label>◐ <?= h(t('photo_contrast')) ?><input type="range" id="ptContrast" min="50" max="160" step="1" value="100"></label>
          </div>
        </div>
        <h4><?= h(t('photo_count')) ?></h4>
        <div class="pt-count">
          <span class="stepper"><button type="button" data-pt-step="-1">−</button><input type="number" id="ptCount" value="4" min="1" max="500"><button type="button" data-pt-step="1">+</button></span>
          <div class="pt-quick" id="ptQuick"></div>
        </div>
        <div class="pt-info" id="ptInfo"></div>
        <div class="pt-sheets" id="ptSheets" role="button" tabindex="0"></div>
        <button type="button" class="btn block big" id="ptPreviewBtn">👁 <?= h(t('photo_preview')) ?></button>
        <div class="pay-box" id="ptPay"></div>
        <button type="button" class="btn primary block big" id="ptAdd">✓ <?= h(t('photo_add')) ?></button>
      </div>
    </div>
  </dialog>
  <dialog class="sheet full" id="ptPreview">
    <div class="sheet-head"><span class="grip"></span><b>👁 <?= h(t('photo_preview')) ?></b><button type="button" class="sheet-x" aria-label="Close">✕</button></div>
    <div class="sheet-body pt-big" id="ptBig"></div>
  </dialog>
  <?php endif; ?>

  <template id="tpl">
    <div class="file">
      <div class="file-head"><span class="fname"></span><button type="button" class="x" aria-label="<?= h(t('remove')) ?>">✕</button></div>
      <div class="chips"></div>
      <div class="price muted"></div>
      <button type="button" class="btn block opt-open">⚙️ <?= h(t('options')) ?></button>
      <dialog class="sheet file-sheet">
        <div class="sheet-head"><span class="grip"></span><b class="sheet-fname"></b><button type="button" class="sheet-x" aria-label="Close">✕</button></div>
        <div class="sheet-body">
          <div class="opts">
            <label><?= h(t('copies')) ?>
              <span class="stepper"><button type="button" data-step="-1">−</button><input type="number" data-k="copies" value="1" min="1" max="999"><button type="button" data-step="1">+</button></span>
            </label>
            <?= choice('paper', 'paper', $papers, false) ?>
            <?= choice('color', 'colour', $colors, true) ?>
            <?= choice('sides', 'sides', $sides, true) ?>
            <?= choice('orientation', 'layout', ['portrait', 'landscape'], true) ?>
            <label><?= h(t('pages')) ?>
              <input data-k="page_range" placeholder="<?= h(t('pages_ph')) ?>" inputmode="numeric" pattern="[0-9,\- ]*">
            </label>
            <label class="layout-pick wide hidden"><?= h(t('print_layout')) ?>
              <select data-l="id"><option value=""><?= h(t('layout_normal')) ?></option></select>
            </label>
            <label class="pieces-pick hidden"><?= h(t('pieces')) ?>
              <select data-l="pieces"></select>
            </label>
          </div>
          <div class="pay-box sheet-pay"></div>
          <button type="button" class="btn primary block big" data-sheet-close><?= h(t('done')) ?></button>
        </div>
      </dialog>
    </div>
  </template>

  <?php if ($layoutsJs || $photoJs): ?>
    <script src="assets/pdf-lib.min.js" defer></script>
    <script src="assets/layout.js?v=3" defer></script>
  <?php endif; ?>
  <?php if ($photoJs): ?><script src="assets/photo-tool.js?v=1" defer></script><?php endif; ?>
  <script>
  (function () {
    var maxFiles = <?= (int)cfg('max_files') ?>, maxMb = <?= (int)cfg('max_file_mb') ?>, SELF = <?= json_encode($self) ?>;
    var rules = <?= json_encode($rules) ?>, currency = <?= json_encode(setting('currency', 'SR')) ?>;
    var LAYOUTS = <?= json_encode($layoutsJs, JSON_UNESCAPED_UNICODE) ?>, LPRICE = <?= json_encode((object)$layoutPrices) ?>, LDEFS = {};
    LAYOUTS.forEach(function (L) { LDEFS[L.id] = L; });
    var T = <?php $keys = ['err_none', 'err_server', 'err_net', 'estimate', 'estimate_ph', 'pages_count', 'counting',
                'full_sheet', 'preparing', 'layout_fail', 'sheets_count', 'send', 'pieces', 'pages'];
                echo json_encode(array_combine($keys, array_map('t', $keys))); ?>;
    var Terr = { max: <?= json_encode(t('err_max', cfg('max_files'))) ?>, big: <?= json_encode(t('err_big', '%s', cfg('max_file_mb'))) ?> };
    var picker = document.getElementById('picker'), list = document.getElementById('list'),
        tpl = document.getElementById('tpl'), form = document.getElementById('upForm'),
        err = document.getElementById('err'), prog = document.getElementById('progress'),
        btn = document.getElementById('sendBtn'), totalEl = document.getElementById('total');
    var items = [];
    var PHOTO = <?= json_encode($photoJs, JSON_UNESCAPED_UNICODE) ?>, PDEFS = {};
    if (PHOTO) PHOTO.sizes.forEach(function (L) { PDEFS[L.id] = L; });
    var TP = <?php $pk = ['photo_info', 'photo_sheet_of', 'full_sheet', 'photo_edit', 'photo_bad', 'estimate'];
                echo json_encode(array_combine($pk, array_map('t', $pk))); ?>;

    function photoSheets(it) {
      var L = PDEFS[it.photo.id];
      return Math.ceil(it.photo.pieces / window.DaybillLayout.sizeFit(L.w, L.h, PHOTO.paper).max);
    }
    function photoPrice(it) {
      var sheets = photoSheets(it);
      if (PHOTO.price !== '') return (PHOTO.mode === 'sheet' ? sheets : it.photo.pieces) * parseFloat(PHOTO.price);
      var r = PHOTO.rule;
      return r[1] + Math.max(0, sheets - r[0]) * r[2];
    }


    picker.removeAttribute('name'); // files are sent by JavaScript instead
    picker.addEventListener('change', function () {
      var n = picker.files.length;
      for (var i = 0; i < n; i++) addFile(picker.files[i]);
      picker.value = '';
      // One file chosen: show its options right away, like an app.
      if (n === 1 && items.length && window.DaybillSheet) DaybillSheet.open(items[items.length - 1].node.querySelector('.file-sheet'));
    });

    function showErr(m) { err.textContent = m; err.classList.toggle('hidden', !m); }
    function money(v) { var s = v.toFixed(2); return (s.slice(-3) === '.00' ? s.slice(0, -3) : s) + ' ' + currency; }
    function val(node, k) { return node.querySelector('[data-k=' + k + ']').value; }

    // Same logic as pages_selected() in lib.php.
    function selected(total, range) {
      range = range.replace(/\s+/g, '');
      if (!/^(\d+(-\d+)?)(,\d+(-\d+)?)*$/.test(range)) return Math.max(1, total);
      var pages = {};
      range.split(',').forEach(function (part) {
        var ab = part.split('-'), a = +ab[0], b = ab.length > 1 ? +ab[1] : a;
        if (b < a) { var t = a; a = b; b = t; }
        if (total > 0) b = Math.min(b, total);
        for (var i = a; i <= b && i - a < 10000; i++) pages[i] = 1;
      });
      return Math.max(1, Object.keys(pages).length);
    }

    // Layout code of a file: "" (normal), "nup4", "passport:8" …
    function layoutCode(it) {
      var id = it.node.querySelector('[data-l=id]').value, L = LDEFS[id];
      if (!L) return '';
      return L.type === 'size' ? id + ':' + it.node.querySelector('[data-l=pieces]').value : id;
    }

    function price(it) {
      if (it.photo) return photoPrice(it);
      if (!it.pages) return null;
      var r = ((rules[val(it.node, 'paper')] || {})[val(it.node, 'color')] || {})[val(it.node, 'sides')];
      var copies = Math.max(1, parseInt(val(it.node, 'copies'), 10) || 1), code = layoutCode(it);
      var sheets = code ? window.DaybillLayout.sheets(code, LDEFS, it.pages, val(it.node, 'page_range'), val(it.node, 'paper')) : null;
      if (code && LPRICE[code.split(':')[0]] !== undefined) return sheets * copies * LPRICE[code.split(':')[0]];
      if (!r) return null;
      var n = (code ? sheets : selected(it.pages, val(it.node, 'page_range'))) * copies;
      return r[1] + Math.max(0, n - r[0]) * r[2];
    }

    // Offers the layouts that fit this file: pages per sheet for PDFs, photo sheets for photos (and PDFs).
    function setupLayout(it) {
      var ext = it.file.name.split('.').pop().toLowerCase(), isPdf = ext === 'pdf';
      var isImg = ['jpg', 'jpeg', 'png'].indexOf(ext) >= 0;
      var sel = it.node.querySelector('[data-l=id]'), pick = it.node.querySelector('.layout-pick');
      var pcs = it.node.querySelector('[data-l=pieces]'), pcsPick = it.node.querySelector('.pieces-pick');
      if (!window.DaybillLayout || !window.PDFLib || !(isPdf || isImg)) return;
      LAYOUTS.forEach(function (L) {
        if (L.type === 'nup' && !isPdf) return;
        var o = document.createElement('option'); o.value = L.id; o.textContent = L.name; sel.appendChild(o);
      });
      if (sel.options.length < 2) return;
      pick.classList.remove('hidden');
      function pieces() {
        var L = LDEFS[sel.value];
        pcsPick.classList.toggle('hidden', !L || L.type !== 'size');
        if (!L || L.type !== 'size') return;
        var max = window.DaybillLayout.sizeFit(L.w, L.h, val(it.node, 'paper')).max, keep = pcs.value;
        pcs.innerHTML = '';
        [1, 2, 4, 6, 8, 10, 12, 16, 20].filter(function (n) { return n < max; }).concat([0]).forEach(function (n) {
          var o = document.createElement('option');
          o.value = n; o.textContent = n ? n : T.full_sheet + ' (' + max + ')'; pcs.appendChild(o);
        });
        pcs.value = keep && pcs.querySelector('option[value="' + keep + '"]') ? keep : (max > 8 ? '8' : '0');
      }
      sel.addEventListener('change', pieces);
      it.node.querySelector('[data-k=paper]').addEventListener('change', pieces);
    }

    // Short summary on the card: "2 × · A4 · Black & white · One side · 4 pages on one sheet"
    function chips(it) {
      var box = it.node.querySelector('.chips'), parts = [];
      if (it.photo) {
        var L = PDEFS[it.photo.id];
        parts = [L.name, it.photo.pieces + ' ' + T.pieces, PHOTO.paper, T.sheets_count.replace('%d', photoSheets(it))];
        box.innerHTML = '';
        parts.forEach(function (t) { var c = document.createElement('span'); c.className = 'chip'; c.textContent = t; box.appendChild(c); });
        return;
      }
      var copies = Math.max(1, parseInt(val(it.node, 'copies'), 10) || 1);
      parts.push(copies + ' ×');
      ['paper', 'color', 'sides'].forEach(function (k) {
        var el = it.node.querySelector('[data-k=' + k + ']');
        parts.push(el.tagName === 'SELECT' ? el.selectedOptions[0].textContent : el.parentNode.querySelector('.fixed').textContent);
      });
      var ls = it.node.querySelector('[data-l=id]');
      if (ls.value) {
        var pc = it.node.querySelector('[data-l=pieces]');
        parts.push('🗂️ ' + ls.selectedOptions[0].textContent + (LDEFS[ls.value].type === 'size' && pc.value !== '' ? ' · ' + pc.selectedOptions[0].textContent + ' ' + T.pieces : ''));
      }
      var pr = val(it.node, 'page_range');
      if (pr) parts.push(T.pages + ' ' + pr);
      box.innerHTML = '';
      parts.forEach(function (t) { var c = document.createElement('span'); c.className = 'chip'; c.textContent = t; box.appendChild(c); });
    }

    function refresh() {
      var sum = 0, known = items.length > 0;
      items.forEach(function (it) {
        var p = price(it), el = it.node.querySelector('.price'), pay = it.node.querySelector('.sheet-pay');
        el.textContent = it.counting ? T.counting
          : (it.pages && !it.photo ? T.pages_count.replace('%d', it.pages) + ' · ' : '')
            + (p === null ? T.estimate_ph : T.estimate + ': ' + money(p));
        if (pay) {
          pay.innerHTML = '';
          pay.appendChild(document.createTextNode(p === null ? T.estimate_ph : T.estimate));
          if (p !== null) { var pb = document.createElement('b'); pb.textContent = money(p); pay.appendChild(pb); }
        }
        chips(it);
        if (p === null) known = false; else sum += p;
      });
      totalEl.innerHTML = '';
      if (known) {
        totalEl.appendChild(document.createTextNode(T.estimate));
        var b = document.createElement('b'); b.textContent = money(sum); totalEl.appendChild(b);
      }
      totalEl.classList.toggle('hidden', !known);
    }

    function latin1(buf) { return new TextDecoder('latin1').decode(buf); }

    // Same logic as pdf_tree_count() in lib.php.
    function treeCount(s) {
      var m, max = 0, re = /<<[^<>]*\/Type\s*\/Pages\b[^<>]*>>/g;
      while ((m = re.exec(s))) { var c = /\/Count\s+(\d+)/.exec(m[0]); if (c) max = Math.max(max, +c[1]); }
      if (!max) { re = /\/Type\s*\/Pages\b[^>]*?\/Count\s+(\d+)/g; while ((m = re.exec(s))) max = Math.max(max, +m[1]); }
      return max;
    }

    function inflate(bytes) {
      var ds = new DecompressionStream('deflate');
      return new Response(new Blob([bytes]).stream().pipeThrough(ds)).arrayBuffer().then(latin1, function () { return ''; });
    }

    // Same approach as pdf_page_count() in lib.php: plain text plus compressed object streams.
    function pdfPages(buf) {
      var s = latin1(buf), parts = [], re = /stream\r?\n/g, m;
      while (window.DecompressionStream && (m = re.exec(s))) {
        var start = m.index + m[0].length, end = s.indexOf('endstream', start);
        if (end < 0) break;
        var dict = s.slice(Math.max(0, m.index - 400), m.index);
        dict = dict.slice(Math.max(0, dict.lastIndexOf('obj')));
        if (dict.indexOf('/ObjStm') >= 0 && dict.indexOf('/FlateDecode') >= 0) {
          while (end > start && (s[end - 1] === '\n' || s[end - 1] === '\r')) end--;
          parts.push(inflate(new Uint8Array(buf, start, end - start)));
        }
        re.lastIndex = end;
      }
      return Promise.all(parts).then(function (texts) {
        var all = s + '\n' + texts.join('\n');
        return treeCount(all) || (all.match(/\/Type\s*\/Page\b(?!s)/g) || []).length;
      });
    }

    // Asks the server to count pages when the phone could not (old browser or unusual PDF).
    function serverPages(file) {
      var fd = new FormData(); fd.append('ajax', 'count'); fd.append('pdf', file, file.name);
      return fetch(SELF, { method: 'POST', body: fd }).then(function (r) { return r.json(); })
        .then(function (d) { return d.pages || 0; }, function () { return 0; });
    }

    function countPages(it) {
      var ext = it.file.name.split('.').pop().toLowerCase();
      if (['jpg', 'jpeg', 'png'].indexOf(ext) >= 0) { it.pages = 1; return refresh(); }
      if (ext !== 'pdf') return refresh();
      it.counting = true; refresh();
      var local = it.file.arrayBuffer && window.TextDecoder
        ? it.file.arrayBuffer().then(pdfPages).catch(function () { return 0; }) : Promise.resolve(0);
      local.then(function (n) { return n || serverPages(it.file); }).then(function (n) {
        it.pages = n; it.counting = false; refresh();
      });
    }

    function addFile(file) {
      if (items.length >= maxFiles) return showErr(Terr.max);
      if (file.size > maxMb * 1048576) return showErr(Terr.big.replace('%s', file.name));
      showErr('');
      var node = tpl.content.firstElementChild.cloneNode(true);
      node.querySelector('.fname').textContent = '📄 ' + file.name;
      node.querySelector('.sheet-fname').textContent = file.name;
      var sheet = node.querySelector('.file-sheet');
      node.querySelector('.opt-open').onclick = function () { window.DaybillSheet ? DaybillSheet.open(sheet) : sheet.show(); };
      sheet.addEventListener('sheetclosed', refresh);
      var item = { file: file, node: node, pages: 0 };
      node.querySelector('.x').onclick = function () {
        items.splice(items.indexOf(item), 1); node.remove(); refresh();
      };
      node.querySelectorAll('[data-step]').forEach(function (b) {
        b.onclick = function () {
          var inp = node.querySelector('[data-k=copies]');
          inp.value = Math.max(1, Math.min(999, (parseInt(inp.value, 10) || 1) + parseInt(b.dataset.step, 10)));
          refresh();
        };
      });
      node.addEventListener('input', refresh);
      node.addEventListener('change', refresh);
      items.push(item);
      list.appendChild(node);
      setupLayout(item);
      countPages(item);
    }

    // Used by assets/photo-tool.js
    window.DaybillOrder = { items: items, list: list, refresh: refresh, showErr: showErr, money: money,
      maxFiles: maxFiles, maxMb: maxMb, PHOTO: PHOTO, PDEFS: PDEFS, photoPrice: photoPrice,
      T: Object.assign({}, TP, { err_max: Terr.max, err_big: Terr.big }) };

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!items.length) return showErr(T.err_none);
      showErr('');
      var fd = new FormData();
      fd.append('ajax', '1');
      ['customer_name', 'phone', 'note'].forEach(function (n) { fd.append(n, form.elements[n].value); });
      btn.disabled = true;
      for (var i = 0; i < items.length; i++) {
        var it = items[i];
        if (it.photo) { // photo print tool: sheets with the photos at exact size
          fd.append('files[]', it.file, it.file.name);
          btn.textContent = T.preparing;
          try {
            var pc = it.photo.id + ':' + it.photo.pieces;
            var pr = await window.DaybillLayout.build(it.file, pc, PDEFS, PHOTO.paper, '');
            fd.append('print[' + i + ']', pr.blob, 'photo.pdf');
            fd.append('opt[' + i + '][layout]', pc);
            fd.append('opt[' + i + '][kind]', 'photo');
            (it.previews || []).forEach(function (pv, k) { fd.append('preview[' + i + '][' + k + ']', pv, 'sheet' + k + '.jpg'); });
          } catch (x) {
            btn.disabled = false; btn.textContent = T.send;
            return showErr(T.layout_fail.replace('%s', it.file.name) + ' (' + x.message + ')');
          }
          continue;
        }
        var code = layoutCode(it);
        fd.append('files[]', it.file, it.file.name);
        it.node.querySelectorAll('[data-k]').forEach(function (el) {
          fd.append('opt[' + i + '][' + el.dataset.k + ']', el.value);
        });
        if (code) {
          // Build the print-ready sheet(s) on the phone, sent next to the original.
          btn.textContent = T.preparing;
          try {
            var res = await window.DaybillLayout.build(it.file, code, LDEFS, val(it.node, 'paper'), val(it.node, 'page_range'));
            fd.append('print[' + i + ']', res.blob, 'layout.pdf');
            fd.append('opt[' + i + '][layout]', code);
            fd.set('opt[' + i + '][orientation]', res.landscape ? 'landscape' : 'portrait');
          } catch (x) {
            btn.disabled = false; btn.textContent = T.send;
            return showErr(T.layout_fail.replace('%s', it.file.name) + ' (' + x.message + ')');
          }
        }
      }
      btn.textContent = T.send;
      var xhr = new XMLHttpRequest();
      xhr.open('POST', SELF);
      btn.disabled = true; prog.classList.remove('hidden');
      xhr.upload.onprogress = function (ev) {
        if (ev.lengthComputable) prog.firstElementChild.style.width = (ev.loaded / ev.total * 100) + '%';
      };
      xhr.onload = function () {
        btn.disabled = false; prog.classList.add('hidden');
        var r; try { r = JSON.parse(xhr.responseText); } catch (x) { r = { ok: false, error: T.err_server }; }
        if (!r.ok) return showErr(r.error);
        form.classList.add('hidden');
        document.getElementById('doneCode').textContent = r.code;
        var dpin = document.getElementById('donePin');
        if (r.pin) { dpin.querySelector('b').textContent = r.pin; dpin.classList.remove('hidden'); }
        document.getElementById('doneAuto').classList.toggle('hidden', !r.auto);
        var dp = document.getElementById('donePrice');
        dp.textContent = r.price ? T.estimate : T.estimate_ph;
        if (r.price) { var b = document.createElement('b'); b.textContent = r.price; dp.appendChild(b); }
        document.getElementById('done').classList.remove('hidden');
        window.scrollTo(0, 0);
      };
      xhr.onerror = function () { btn.disabled = false; prog.classList.add('hidden'); showErr(T.err_net); };
      xhr.send(fd);
    });
  })();
  </script>
<?php endif; ?>
<?php page_footer(); ?>
