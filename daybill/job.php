<?php
// One order: preview files, adjust copies/size/price, print, complete with bill amount.

require __DIR__ . '/lib.php';
require __DIR__ . '/printer.php';
$user = require_login();

$id = (int)($_GET['id'] ?? $_POST['id'] ?? 0);
$st = db()->prepare('SELECT * FROM jobs WHERE id = ?');
$st->execute([$id]);
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
    db()->prepare("UPDATE job_files SET status = 'printed', print_count = print_count + 1, last_error = '',
                   printed_at = NOW(), printed_by = ? WHERE id = ?")->execute([$userId, $fileId]);
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

    if ($action === 'print' || $action === 'save') {
        $f = load_file($id, (int)($_POST['file_id'] ?? 0));
        if ($f) {
            $o = clean_options($_POST);
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
    } elseif ($action === 'delete' && $user['role'] === 'admin') {
        $files = $pdo->prepare('SELECT stored_name FROM job_files WHERE job_id = ?');
        $files->execute([$id]);
        foreach ($files->fetchAll(PDO::FETCH_COLUMN) as $name) {
            if ($name !== '') {
                @unlink(cfg('upload_dir') . '/' . $name);
                @unlink(cfg('upload_dir') . '/' . $name . '.pdf');
            }
        }
        $pdo->prepare('DELETE FROM jobs WHERE id = ?')->execute([$id]);
        flash('Order deleted.');
        redirect('staff.php');
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
  <?php if ($mode === 'agent' && time() - (int)setting('agent_seen', '0') > 60): ?>
    <div class="alert err">⚠ The shop print agent has not connected in the last minute. Is it running on the shop PC?</div>
  <?php endif; ?>
</div>

<?php foreach ($files as $f): ?>
  <?php $gone = $f['stored_name'] === ''; $auto = auto_price($f); ?>
  <div class="card file-card fstatus-<?= h($f['status']) ?>">
    <div class="file-head">
      <span class="fname">📄 <?= h($f['original_name']) ?></span>
      <span class="badge"><?= h($f['status']) ?><?= $f['print_count'] > 1 ? ' ×' . (int)$f['print_count'] : '' ?></span>
    </div>
    <div class="muted">
      <?= strtoupper(h($f['ext'])) ?> · <?= format_bytes((int)$f['size_bytes']) ?>
      · <?= $f['pages_total'] ? (int)$f['pages_total'] . ' page(s)' : '<b class="warn">pages unknown – check price</b>' ?>
      <?php if ($f['printed_at']): ?> · printed <?= h(date('h:i A', strtotime($f['printed_at']))) ?> by <?= h($f['printer_user'] ?? '?') ?><?php endif; ?>
    </div>
    <?php if ($f['last_error'] && $f['status'] === 'failed'): ?><div class="alert err"><?= h($f['last_error']) ?></div><?php endif; ?>

    <?php if ($gone): ?>
      <p class="muted">File removed from server (older than retention period).</p>
    <?php else: ?>
      <div class="actions">
        <a class="btn" href="file.php?id=<?= (int)$f['id'] ?>" target="_blank">👁 Open / preview</a>
        <a class="btn" href="file.php?id=<?= (int)$f['id'] ?>&amp;dl=1">⬇ Download</a>
      </div>
      <form method="post" class="opts">
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
  <?php if ($user['role'] === 'admin'): ?>
    <form method="post" class="actions">
      <?= csrf_field() ?>
      <input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
      <button class="btn danger" name="action" value="delete" onclick="return confirm('Delete this order and its files?')">Delete order &amp; files</button>
    </form>
  <?php endif; ?>
</div>

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
setTimeout(function () { location.reload(); }, 4000);
<?php endif; ?>
</script>
<?php page_footer(); ?>
