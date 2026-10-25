<?php
// One order: preview files, adjust copies/size/price, print, complete with bill amount.

require __DIR__ . '/lib.php';
require __DIR__ . '/printer.php';
$user = require_login();

$id = (int)($_GET['id'] ?? $_POST['id'] ?? 0);
$st = db()->prepare('SELECT * FROM jobs WHERE id = ? AND shop_id = ?');
$st->execute([$id, shop_id()]);
$job = $st->fetch();
if (!$job) {
    http_response_code(404);
    exit('Order not found.');
}
$mode = setting('print_mode', 'local'); // local | agent | browser

function load_file(int $jobId, int $fileId): ?array
{
    $st = db()->prepare('SELECT * FROM job_files WHERE id = ? AND job_id = ?');
    $st->execute([$fileId, $jobId]);
    return $st->fetch() ?: null;
}

function mark_printed(int $fileId, int $userId): void
{
    global $id, $autoDone;
    db()->prepare("UPDATE job_files SET status = 'printed', print_count = print_count + 1, last_error = '',
                   printed_at = NOW(), printed_by = ? WHERE id = ?")->execute([$userId, $fileId]);
    $autoDone = update_job_status((int)$id) || !empty($autoDone);
}

// Prints now (local), queues for the shop-PC agent (agent), or just records it (browser).
function send_to_printer(array $f, string $mode, int $userId): string
{
    if ($mode === 'agent') {
        db()->prepare("UPDATE job_files SET status = 'queued', queued_at = NOW(), last_error = '', printed_by = ? WHERE id = ?")
            ->execute([$userId, $f['id']]);
        return 'queued for the shop printer';
    }
    if ($mode === 'browser') {
        mark_printed((int)$f['id'], $userId);
        return 'opened for printing';
    }
    try {
        $used = print_file($f);
    } catch (Throwable $e) {
        db()->prepare("UPDATE job_files SET status = 'failed', last_error = ? WHERE id = ?")
            ->execute([mb_substr($e->getMessage(), 0, 500), $f['id']]);
        throw $e;
    }
    mark_printed((int)$f['id'], $userId);
    return 'sent to ' . $used;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $action = (string)($_POST['action'] ?? '');
    $pdo = db();
    $isAdmin = in_array($user['role'], ['admin', 'super'], true);

    // Order check "pin": nothing can be printed before the customer's PIN was entered.
    if (!$job['verified'] && in_array($action, ['print', 'print_all', 'mark_printed', 'done'], true)) {
        flash('🔒 Enter the shop PIN first.', 'err');
        redirect('job.php?id=' . $id);
    }
    if ($action === 'verify_pin' && !$job['verified']) {
        $r = check_shop_pin(preg_replace('/\D/', '', (string)($_POST['pin'] ?? '')));
        if ($r === 'ok') {
            approve_job($id, (int)$user['id']);
            flash('✅ Shop PIN correct – order approved' . (setting('print_mode', 'local') !== 'browser' ? ' and sent to the printer.' : '.'));
        } else {
            flash($r === 'locked' ? 'Too many wrong PINs – wait 15 minutes.' : 'Wrong shop PIN.', 'err');
        }
        redirect('job.php?id=' . $id);
    }
    if ($action === 'unlock' && $isAdmin && !$job['verified']) {
        $pdo->prepare('UPDATE jobs SET verified = 1, handled_by = ? WHERE id = ?')->execute([$user['id'], $id]);
        flash('Order unlocked by admin without PIN.');
        redirect('job.php?id=' . $id);
    }

    if ($action === 'print' || $action === 'save') {
        $f = load_file($id, (int)($_POST['file_id'] ?? 0));
        if ($f) {
            $o = clean_options($_POST);
            if ($f['kind'] === 'photo') { // photo items stay on the photo paper, in colour
                $o['paper'] = $f['paper'];
            }
            // Price: left as shown -> unchanged (an automatic price follows the new options);
            // empty or equal to the calculated price -> automatic; anything else -> staff override.
            $raw = trim(str_replace(',', '.', (string)($_POST['price'] ?? '')));
            $untouched = abs((float)$raw - (float)($_POST['price_shown'] ?? -1)) < 0.005;
            $auto = auto_price($o + ['pages_total' => $f['pages_total']]);
            if ($raw === '' || abs((float)$raw - $auto) < 0.005 || ($untouched && $f['price'] === null)) {
                $price = null;
            } else {
                $price = max(0, round((float)$raw, 2));
            }
            // Printer: '' = automatic (admin's printer for this paper size and colour).
            $printer = mb_substr(trim((string)($_POST['printer'] ?? '')), 0, 200);
            if ($printer !== '' && !in_array($printer, known_printers(), true)) {
                $printer = '';
            }
            $pdo->prepare('UPDATE job_files SET copies = ?, paper = ?, color = ?, sides = ?, orientation = ?, page_range = ?, price = ?, printer = ? WHERE id = ?')
                ->execute([$o['copies'], $o['paper'], $o['color'], $o['sides'], $o['orientation'], $o['page_range'], $price, $printer, $f['id']]);
            $f = array_merge($f, $o, ['price' => $price, 'printer' => $printer]);
            if ($action === 'print') {
                $pdo->prepare("UPDATE jobs SET status = IF(status = 'new', 'printing', status), handled_by = ? WHERE id = ?")
                    ->execute([$user['id'], $id]);
                try {
                    $what = send_to_printer($f, $mode, (int)$user['id']);
                    if ($mode === 'browser') {
                        redirect('file.php?id=' . (int)$f['id']); // opens in the new tab (formtarget)
                    }
                    flash('"' . $f['original_name'] . '" ' . $what . ' – ' . $f['copies'] . ' cop' . ($f['copies'] > 1 ? 'ies' : 'y') . '.');
                } catch (Throwable $e) {
                    flash($e->getMessage(), 'err');
                }
            } else {
                flash('Saved.');
            }
        }
    } elseif ($action === 'print_all' && $mode !== 'browser') {
        $files = $pdo->prepare("SELECT * FROM job_files WHERE job_id = ? AND status IN ('pending','failed') AND stored_name <> '' ORDER BY id");
        $files->execute([$id]);
        $ok = 0;
        $errors = [];
        foreach ($files->fetchAll() as $f) {
            try {
                send_to_printer($f, $mode, (int)$user['id']);
                $ok++;
            } catch (Throwable $e) {
                $errors[] = $f['original_name'] . ': ' . $e->getMessage();
            }
        }
        $pdo->prepare("UPDATE jobs SET status = IF(status = 'new', 'printing', status), handled_by = ? WHERE id = ?")
            ->execute([$user['id'], $id]);
        $verb = $mode === 'agent' ? 'Queued' : 'Printed';
        flash($errors ? "$verb $ok file(s). Problems: " . implode(' | ', $errors) : "$verb $ok file(s).", $errors ? 'err' : 'ok');
    } elseif ($action === 'relayout') {
        // Staff changed the layout: the browser sent a new print-ready PDF (or '' = print the original again).
        $f = load_file($id, (int)($_POST['file_id'] ?? 0));
        $layout = clean_layout((string)($_POST['layout'] ?? ''));
        $dir = cfg('upload_dir');
        $tmp = $_FILES['print']['tmp_name'] ?? '';
        if ($f && $f['stored_name'] !== '') {
            if ($layout === '' && $f['orig_name'] !== '') {
                @unlink($dir . '/' . $f['stored_name']);
                $pages = $f['orig_ext'] === 'pdf' ? pdf_page_count($dir . '/' . $f['orig_name']) : (int)in_array($f['orig_ext'], ['jpg', 'jpeg', 'png'], true);
                $pdo->prepare("UPDATE job_files SET stored_name = orig_name, ext = orig_ext, orig_name = '', orig_ext = '', layout = '',
                               pages_total = ?, orientation = 'portrait', price = NULL WHERE id = ?")->execute([$pages, $f['id']]);
                flash('Layout removed – the original file will be printed.');
            } elseif ($layout !== '' && $tmp !== '' && ($_FILES['print']['error'] ?? 1) === UPLOAD_ERR_OK
                && strncmp((string)file_get_contents($tmp, false, null, 0, 4), '%PDF', 4) === 0) {
                $new = bin2hex(random_bytes(16)) . '.pdf';
                move_uploaded_file($tmp, $dir . '/' . $new);
                if ($f['orig_name'] === '') {
                    [$origName, $origExt] = [$f['stored_name'], $f['ext']];
                } else {
                    [$origName, $origExt] = [$f['orig_name'], $f['orig_ext']];
                    @unlink($dir . '/' . $f['stored_name']);
                }
                $orient = ($_POST['orientation'] ?? '') === 'landscape' ? 'landscape' : 'portrait';
                $pdo->prepare("UPDATE job_files SET stored_name = ?, ext = 'pdf', orig_name = ?, orig_ext = ?, layout = ?, pages_total = ?,
                               page_range = '', orientation = ?, price = NULL WHERE id = ?")
                    ->execute([$new, $origName, $origExt, $layout, pdf_page_count($dir . '/' . $new), $orient, $f['id']]);
                flash('Layout changed: ' . layout_label($layout) . '.');
            }
        }
    } elseif ($action === 'mark_printed') {
        $f = load_file($id, (int)($_POST['file_id'] ?? 0));
        if ($f) {
            mark_printed((int)$f['id'], (int)$user['id']);
        }
    } elseif ($action === 'save_amount' || $action === 'done') {
        $amount = max(0, round((float)str_replace(',', '.', (string)($_POST['amount'] ?? '0')), 2));
        $status = $action === 'done' ? 'done' : $job['status'];
        $pdo->prepare('UPDATE jobs SET status = ?, amount = ?, handled_by = ? WHERE id = ?')
            ->execute([$status, $amount, $user['id'], $id]);
        if ($action === 'done') {
            flash('Order ' . $job['code'] . ' completed – ' . money($amount) . '.');
            redirect('staff.php');
        }
        flash('Amount saved: ' . money($amount) . '.');
    } elseif ($action === 'cancel') {
        $pdo->prepare("UPDATE jobs SET status = 'cancelled', handled_by = ? WHERE id = ?")->execute([$user['id'], $id]);
        flash('Order ' . $job['code'] . ' cancelled.');
        redirect('staff.php');
    } elseif ($action === 'reopen') {
        $pdo->prepare("UPDATE jobs SET status = 'printing' WHERE id = ?")->execute([$id]);
    } elseif ($action === 'delete' && in_array($user['role'], ['admin', 'super'], true)) {
        $files = $pdo->prepare('SELECT stored_name FROM job_files WHERE job_id = ? UNION ALL SELECT orig_name FROM job_files WHERE job_id = ?');
        $files->execute([$id, $id]);
        foreach ($files->fetchAll(PDO::FETCH_COLUMN) as $name) {
            delete_upload((string)$name);
        }
        $pdo->prepare('DELETE FROM jobs WHERE id = ?')->execute([$id]);
        flash('Order deleted.');
        redirect('staff.php');
    }
    if (!empty($autoDone)) {
        flash('All files printed – order ' . $job['code'] . ' completed automatically (' . money((float)db()->query(
            'SELECT amount FROM jobs WHERE id = ' . (int)$id)->fetchColumn()) . ').');
    }
    redirect('job.php?id=' . $id);
}

$st = db()->prepare('SELECT f.*, u.username AS printer_user FROM job_files f LEFT JOIN users u ON u.id = f.printed_by
                     WHERE f.job_id = ? ORDER BY f.id');
$st->execute([$id]);
$files = $st->fetchAll();
$total = 0.0;
$waiting = false;
foreach ($files as $f) {
    $total += file_price($f);
    $waiting = $waiting || in_array($f['status'], ['queued', 'sending'], true);
}
$amount = (float)$job['amount'] > 0 ? (float)$job['amount'] : $total;
$closed = in_array($job['status'], ['done', 'cancelled'], true);
$labels = ['bw' => 'Black & white', 'color' => 'Colour', 'single' => 'One side', 'double' => 'Both sides',
    'portrait' => 'Portrait', 'landscape' => 'Landscape'];

// Select with the offered choices (plus the file's current value if no longer offered).
function sel(string $name, array $values, string $current, array $labels): string
{
    if (!in_array($current, $values, true)) {
        $values[] = $current;
    }
    $s = '<select name="' . $name . '">';
    foreach ($values as $v) {
        $s .= '<option value="' . h($v) . '"' . ($v === $current ? ' selected' : '') . '>' . h($labels[$v] ?? $v) . '</option>';
    }
    return $s . '</select>';
}

page_header('Order ' . $job['code'], true, 'en', 'staff.php');
echo flash();
?>
<div class="card">
  <div class="job-title">
    <span class="bigcode small"><?= h($job['code']) ?></span>
    <div>
      <b><?= h($job['customer_name'] ?: 'Walk-in customer') ?></b>
      <?php if ($job['phone']): ?> · <a href="tel:<?= h($job['phone']) ?>"><?= h($job['phone']) ?></a><?php endif; ?>
      <div class="muted"><?= h(date('d M Y, h:i A', strtotime($job['created_at']))) ?> · <span class="badge"><?= h($job['status']) ?></span></div>
    </div>
  </div>
  <?php if ($job['note']): ?><div class="alert info">📝 <?= h($job['note']) ?></div><?php endif; ?>
  <?php if (!$job['verified']): ?>
    <form method="post" class="pin-check" autocomplete="off">
      <?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
      <b>🔒 Waiting for approval – enter the shop PIN</b>
      <div class="pin-inputs">
        <input name="pin" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" required placeholder="••••" autofocus>
        <button class="btn primary big" name="action" value="verify_pin">Approve &amp; print</button>
      </div>
      <?php if (in_array($user['role'], ['admin', 'super'], true)): ?>
        <button class="btn small" name="action" value="unlock" formnovalidate onclick="return confirm('Unlock this order without the PIN?')">Admin: unlock without PIN</button>
      <?php endif; ?>
    </form>
    <style>/* locked: no printing until the PIN is checked */
      button[value=print], button[value=print_all], button[value=mark_printed], button[value=done] { display: none !important; }</style>
  <?php endif; ?>
  <?php if ($mode === 'agent' && time() - (int)setting('agent_seen', '0') > 60): ?>
    <div class="alert err">⚠ The shop print agent has not connected in the last minute. Is it running on the shop PC?</div>
  <?php endif; ?>
</div>

<?php foreach ($files as $f): ?>
  <?php $gone = $f['stored_name'] === ''; $auto = auto_price($f); ?>
  <div class="card file-card fstatus-<?= h($f['status']) ?>">
    <div class="file-head">
      <span class="fname"><?= $f['kind'] === 'photo' ? '📷 Photo print' : '📄 ' . h($f['original_name']) ?></span>
      <span class="badge"><?= h($f['status']) ?><?= $f['print_count'] > 1 ? ' ×' . (int)$f['print_count'] : '' ?></span>
    </div>
    <div class="muted">
      <?= strtoupper(h($f['ext'])) ?> · <?= format_bytes((int)$f['size_bytes']) ?>
      · <?= $f['pages_total'] ? (int)$f['pages_total'] . ($f['layout'] !== '' ? ' sheet(s)' : ' page(s)') : '<b class="warn">pages unknown – check price</b>' ?>
      <?php if ($f['layout'] !== ''): ?><div class="layout-info">🗂️ <?= h(layout_label($f['layout'])) ?></div><?php endif; ?>
      <?php if ($f['printed_at']): ?> · printed <?= h(date('h:i A', strtotime($f['printed_at']))) ?> by <?= h($f['printer_user'] ?? '?') ?><?php endif; ?>
    </div>
    <?php if ($f['last_error'] && $f['status'] === 'failed'): ?><div class="alert err"><?= h($f['last_error']) ?></div><?php endif; ?>

    <?php if ($gone): ?>
      <p class="muted">File removed from server (older than retention period).</p>
    <?php else: ?>
      <?php $fid = (int)$f['id']; ?>
      <div class="chips">
        <span class="chip"><?= (int)$f['copies'] ?> ×</span><span class="chip"><?= h($f['paper']) ?></span>
        <span class="chip"><?= h($labels[$f['color']] ?? $f['color']) ?></span><span class="chip"><?= h($labels[$f['sides']] ?? $f['sides']) ?></span>
        <?php if ($f['page_range'] !== ''): ?><span class="chip">pages <?= h($f['page_range']) ?></span><?php endif; ?>
        <?php if ($mode !== 'browser'): ?><span class="chip">🖨 <?= h(printer_for($f) ?: 'default printer') ?></span><?php endif; ?>
        <span class="chip"><?= h(money(file_price($f))) ?></span>
      </div>
      <?php if ((int)$f['previews'] > 0): ?>
        <div class="pv-row" data-sheet="#pv<?= $fid ?>" role="button" title="Preview">
          <?php for ($k = 0; $k < (int)$f['previews']; $k++): ?>
            <img src="file.php?id=<?= $fid ?>&amp;pv=<?= $k ?>" alt="Sheet <?= $k + 1 ?>" loading="lazy">
          <?php endfor; ?>
          <span class="pv-hint">👁 Preview</span>
        </div>
        <?= sheet_start('pv' . $fid, '👁 ' . layout_label($f['layout']) . ' · ' . $f['paper'], 'dark') ?>
          <div class="pt-big">
            <?php for ($k = 0; $k < (int)$f['previews']; $k++): ?>
              <img src="file.php?id=<?= $fid ?>&amp;pv=<?= $k ?>" alt="">
              <p class="pt-cap">Sheet <?= $k + 1 ?> of <?= max((int)$f['pages_total'], (int)$f['previews']) ?></p>
            <?php endfor; ?>
          </div>
        <?= sheet_end() ?>
      <?php endif; ?>
      <div class="card-actions">
        <?php if ($mode === 'browser'): ?>
          <button class="btn primary big" form="f<?= $fid ?>" name="action" value="print" formtarget="_blank" data-reload>🖨 OK – Open &amp; print</button>
        <?php else: ?>
          <button class="btn primary big" form="f<?= $fid ?>" name="action" value="print">🖨 OK – Print</button>
        <?php endif; ?>
        <button type="button" class="btn big" data-sheet="#opt<?= $fid ?>">⚙️ Options</button>
        <a class="btn big" href="file.php?id=<?= $fid ?>" target="_blank">👁 Open</a>
      </div>
      <?= sheet_start('opt' . $fid, $f['original_name']) ?>
      <div class="actions">
        <a class="btn" href="file.php?id=<?= (int)$f['id'] ?>" target="_blank">👁 Open / preview</a>
        <a class="btn" href="file.php?id=<?= (int)$f['id'] ?>&amp;dl=1">⬇ Download</a>
        <?php if ($f['orig_name'] !== ''): ?><a class="btn" href="file.php?id=<?= (int)$f['id'] ?>&amp;orig=1" target="_blank">📄 Original</a><?php endif; ?>
      </div>
      <form method="post" class="opts" id="f<?= $fid ?>">
        <?= csrf_field() ?>
        <input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
        <input type="hidden" name="file_id" value="<?= (int)$f['id'] ?>">
        <label>Copies
          <span class="stepper"><button type="button" data-step="-1">−</button><input type="number" name="copies" value="<?= (int)$f['copies'] ?>" min="1" max="999"><button type="button" data-step="1">+</button></span>
        </label>
        <label>Paper size<?= sel('paper', enabled_papers(), $f['paper'], $labels) ?></label>
        <label>Colour<?= sel('color', enabled_colors(), $f['color'], $labels) ?></label>
        <label>Sides<?= sel('sides', enabled_sides(), $f['sides'], $labels) ?></label>
        <label>Layout<?= sel('orientation', ['portrait', 'landscape'], $f['orientation'], $labels) ?></label>
        <label>Pages<input name="page_range" value="<?= h($f['page_range']) ?>" placeholder="All"></label>
        <?php if ($mode !== 'browser'): ?>
          <label>Printer
            <select name="printer">
              <option value="">Auto – <?= h(auto_printer($f) ?: 'default printer') ?></option>
              <?php foreach (known_printers() as $pn): ?>
                <option value="<?= h($pn) ?>" <?= $f['printer'] === $pn ? 'selected' : '' ?>><?= h($pn) ?></option>
              <?php endforeach; ?>
            </select>
          </label>
        <?php endif; ?>
        <label>Price (<?= h(setting('currency', 'SR')) ?>)
          <input name="price" inputmode="decimal" value="<?= h(number_format(file_price($f), 2, '.', '')) ?>">
          <input type="hidden" name="price_shown" value="<?= h(number_format(file_price($f), 2, '.', '')) ?>">
          <small><?= $f['price'] !== null ? 'Changed by staff · calculated ' . h(money($auto)) : 'Calculated automatically' ?> – Save to update</small>
        </label>
        <?php if ($mode === 'browser'): ?>
          <div class="alert info wide">In the print window choose: <b><?= (int)$f['copies'] ?> cop<?= $f['copies'] > 1 ? 'ies' : 'y' ?></b>,
            <b><?= h($f['paper']) ?></b>, <b><?= h($labels[$f['color']]) ?></b>, <b><?= h($labels[$f['sides']]) ?></b>,
            <b><?= h($labels[$f['orientation']]) ?></b><?= $f['page_range'] !== '' ? ', pages <b>' . h($f['page_range']) . '</b>' : '' ?>.</div>
        <?php endif; ?>
        <div class="actions wide">
          <?php if ($mode === 'browser'): ?>
            <button class="btn primary big" name="action" value="print" formtarget="_blank" data-reload>🖨 OK – Open &amp; print</button>
          <?php else: ?>
            <button class="btn primary big" name="action" value="print">🖨 OK – Print</button>
          <?php endif; ?>
          <button class="btn" name="action" value="save">Save</button>
          <?php if ($mode !== 'browser'): ?>
            <button class="btn" name="action" value="mark_printed" title="Use after printing manually from the preview">Mark printed</button>
          <?php endif; ?>
        </div>
      </form>
      <?php $srcExt = $f['orig_name'] !== '' ? $f['orig_ext'] : $f['ext'];
      if ($f['kind'] !== 'photo' && enabled_layouts() && in_array($srcExt, ['pdf', 'jpg', 'jpeg', 'png'], true)): ?>
        <details class="relayout" data-file="<?= (int)$f['id'] ?>" data-ext="<?= h($srcExt) ?>"
                 data-src="file.php?id=<?= (int)$f['id'] ?><?= $f['orig_name'] !== '' ? '&amp;orig=1' : '' ?>">
          <summary>🗂️ Change layout</summary>
          <div class="opts">
            <label class="wide">Layout
              <select data-l="id">
                <option value="">Normal – 1 page per sheet</option>
                <?php foreach (enabled_layouts() as $lid => $L): if ($L['type'] === 'nup' && $srcExt !== 'pdf') continue; ?>
                  <option value="<?= h($lid) ?>" <?= explode(':', $f['layout'])[0] === $lid ? 'selected' : '' ?>><?= h($L['label']) ?></option>
                <?php endforeach; ?>
              </select>
            </label>
            <label class="pieces-pick hidden">Pieces<select data-l="pieces" data-current="<?= (int)(explode(':', $f['layout'])[1] ?? 0) ?>"></select></label>
            <div class="actions wide"><button type="button" class="btn primary" data-apply>Apply layout</button> <span class="muted" data-msg></span></div>
          </div>
        </details>
      <?php endif; ?>
      <?= sheet_end() ?>
    <?php endif; ?>
  </div>
<?php endforeach; ?>

<div class="card">
  <?php if (!$closed): ?>
    <?php if (count($files) > 1 && $mode !== 'browser'): ?>
      <form method="post" class="actions">
        <?= csrf_field() ?>
        <input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
        <button class="btn primary" name="action" value="print_all">🖨 Print all remaining</button>
      </form>
    <?php endif; ?>
    <p class="muted">Calculated total: <b><?= h(money($total)) ?></b></p>
    <form method="post" class="done-row">
      <?= csrf_field() ?>
      <input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
      <label>Bill amount (<?= h(setting('currency', 'SR')) ?>)<input name="amount" inputmode="decimal" value="<?= h(number_format($amount, 2, '.', '')) ?>"></label>
      <button class="btn" name="action" value="save_amount">Save amount</button>
      <?php $unprinted = count(array_filter($files, fn($f) => $f['status'] !== 'printed')); ?>
      <button class="btn ok big" name="action" value="done"<?= $unprinted ? ' onclick="return confirm(\'' . $unprinted . ' file(s) not printed yet. Complete anyway?\')"' : '' ?>>✔ Complete order</button>
      <button class="btn danger" name="action" value="cancel" onclick="return confirm('Cancel this order?')">Cancel order</button>
    </form>
  <?php else: ?>
    <p>Order is <b><?= h($job['status']) ?></b><?= $job['status'] === 'done' ? ' · bill ' . h(money((float)$job['amount'])) : '' ?>.</p>
    <form method="post" class="actions">
      <?= csrf_field() ?>
      <input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
      <button class="btn" name="action" value="reopen">Reopen</button>
    </form>
  <?php endif; ?>
  <?php if (in_array($user['role'], ['admin', 'super'], true)): ?>
    <form method="post" class="actions">
      <?= csrf_field() ?>
      <input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
      <button class="btn danger" name="action" value="delete" onclick="return confirm('Delete this order and its files?')">Delete order &amp; files</button>
    </form>
  <?php endif; ?>
</div>

<?php if (enabled_layouts()): ?>
<script src="assets/pdf-lib.min.js"></script>
<script src="assets/layout.js?v=3"></script>
<script>
// Staff can change a file's layout: the print-ready PDF is built here in the browser and uploaded.
(function () {
  var LDEFS = <?= json_encode((object)enabled_layouts(), JSON_UNESCAPED_UNICODE) ?>;
  document.querySelectorAll('.relayout').forEach(function (box) {
    var card = box.closest('.file-card'), sel = box.querySelector('[data-l=id]'), pcs = box.querySelector('[data-l=pieces]');
    var pcsPick = box.querySelector('.pieces-pick'), msg = box.querySelector('[data-msg]'), btn = box.querySelector('[data-apply]');
    var paper = function () { return card.querySelector('select[name=paper]').value; };
    function pieces() {
      var L = LDEFS[sel.value];
      pcsPick.classList.toggle('hidden', !L || L.type !== 'size');
      if (!L || L.type !== 'size') return;
      var max = DaybillLayout.sizeFit(L.w, L.h, paper()).max, keep = pcs.value || pcs.dataset.current;
      pcs.innerHTML = '';
      [1, 2, 4, 6, 8, 10, 12, 16, 20].filter(function (n) { return n < max; }).concat([0]).forEach(function (n) {
        var o = document.createElement('option'); o.value = n; o.textContent = n ? n : 'Full sheet (' + max + ')'; pcs.appendChild(o);
      });
      pcs.value = pcs.querySelector('option[value="' + keep + '"]') ? keep : '0';
    }
    sel.addEventListener('change', pieces); pieces();
    btn.addEventListener('click', async function () {
      var L = LDEFS[sel.value], code = L ? (L.type === 'size' ? sel.value + ':' + pcs.value : sel.value) : '';
      var fd = new FormData();
      fd.append('csrf', <?= json_encode(csrf_token()) ?>); fd.append('id', <?= (int)$job['id'] ?>);
      fd.append('file_id', box.dataset.file); fd.append('action', 'relayout'); fd.append('layout', code);
      btn.disabled = true; msg.textContent = code ? 'Preparing…' : 'Saving…';
      try {
        if (code) {
          var blob = await (await fetch(box.dataset.src, { credentials: 'same-origin' })).blob();
          var file = new File([blob], 'source.' + box.dataset.ext, { type: blob.type });
          var res = await DaybillLayout.build(file, code, LDEFS, paper(), '');
          fd.append('print', res.blob, 'layout.pdf'); fd.append('orientation', res.landscape ? 'landscape' : 'portrait');
        }
        await fetch('job.php', { method: 'POST', body: fd, credentials: 'same-origin' });
        location.reload();
      } catch (e) { btn.disabled = false; msg.textContent = 'Could not make this layout: ' + e.message; }
    });
  });
})();
</script>
<?php endif; ?>
<script>
document.querySelectorAll('.stepper [data-step]').forEach(function (b) {
  b.onclick = function () {
    var inp = b.parentNode.querySelector('input');
    inp.value = Math.max(1, Math.min(999, (parseInt(inp.value, 10) || 1) + parseInt(b.dataset.step, 10)));
  };
});
// Browser printing opens the file in a new tab; refresh this page to show it as printed.
document.querySelectorAll('[data-reload]').forEach(function (b) {
  b.addEventListener('click', function () { setTimeout(function () { location.reload(); }, 1500); });
});
<?php if ($waiting): ?>
// Waiting for the print agent: refresh until the files are printed.
setTimeout(function () { location.reload(); }, 1500);
<?php endif; ?>
</script>
<?php page_footer(); ?>
