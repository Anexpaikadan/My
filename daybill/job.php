<?php
// One order: preview files, adjust copies/size/etc., print, mark done.

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

function load_file(int $jobId, int $fileId): ?array
{
    $st = db()->prepare('SELECT * FROM job_files WHERE id = ? AND job_id = ?');
    $st->execute([$fileId, $jobId]);
    return $st->fetch() ?: null;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $action = (string)($_POST['action'] ?? '');
    $pdo = db();

    if ($action === 'print' || $action === 'save') {
        $f = load_file($id, (int)($_POST['file_id'] ?? 0));
        if ($f) {
            $o = clean_options($_POST);
            $pdo->prepare('UPDATE job_files SET copies = ?, paper = ?, color = ?, sides = ?, orientation = ?, page_range = ? WHERE id = ?')
                ->execute([$o['copies'], $o['paper'], $o['color'], $o['sides'], $o['orientation'], $o['page_range'], $f['id']]);
            $f = array_merge($f, $o);
            if ($action === 'print') {
                $pdo->prepare("UPDATE jobs SET status = IF(status = 'new', 'printing', status), handled_by = ? WHERE id = ?")
                    ->execute([$user['id'], $id]);
                try {
                    $used = print_file($f);
                    $pdo->prepare("UPDATE job_files SET status = 'printed', print_count = print_count + 1, last_error = '',
                                   printed_at = NOW(), printed_by = ? WHERE id = ?")->execute([$user['id'], $f['id']]);
                    flash('Sent "' . $f['original_name'] . '" to ' . $used . ' – ' . $f['copies'] . ' cop' . ($f['copies'] > 1 ? 'ies' : 'y') . '.');
                } catch (Throwable $e) {
                    $pdo->prepare("UPDATE job_files SET status = 'failed', last_error = ? WHERE id = ?")
                        ->execute([mb_substr($e->getMessage(), 0, 500), $f['id']]);
                    flash($e->getMessage(), 'err');
                }
            } else {
                flash('Options saved.');
            }
        }
    } elseif ($action === 'print_all') {
        $files = $pdo->prepare("SELECT * FROM job_files WHERE job_id = ? AND status <> 'printed' ORDER BY id");
        $files->execute([$id]);
        $ok = 0;
        $errors = [];
        foreach ($files->fetchAll() as $f) {
            try {
                print_file($f);
                $pdo->prepare("UPDATE job_files SET status = 'printed', print_count = print_count + 1, last_error = '',
                               printed_at = NOW(), printed_by = ? WHERE id = ?")->execute([$user['id'], $f['id']]);
                $ok++;
            } catch (Throwable $e) {
                $pdo->prepare("UPDATE job_files SET status = 'failed', last_error = ? WHERE id = ?")
                    ->execute([mb_substr($e->getMessage(), 0, 500), $f['id']]);
                $errors[] = $f['original_name'] . ': ' . $e->getMessage();
            }
        }
        $pdo->prepare("UPDATE jobs SET status = IF(status = 'new', 'printing', status), handled_by = ? WHERE id = ?")
            ->execute([$user['id'], $id]);
        flash($errors ? "Printed $ok file(s). Problems: " . implode(' | ', $errors) : "Printed $ok file(s).", $errors ? 'err' : 'ok');
    } elseif ($action === 'mark_printed') {
        $pdo->prepare("UPDATE job_files SET status = 'printed', print_count = print_count + 1, last_error = '',
                       printed_at = NOW(), printed_by = ? WHERE id = ? AND job_id = ?")
            ->execute([$user['id'], (int)($_POST['file_id'] ?? 0), $id]);
    } elseif ($action === 'done') {
        $amount = max(0, (float)str_replace(',', '', (string)($_POST['amount'] ?? '0')));
        $pdo->prepare("UPDATE jobs SET status = 'done', amount = ?, handled_by = ? WHERE id = ?")
            ->execute([$amount, $user['id'], $id]);
        flash('Order ' . $job['code'] . ' completed.');
        redirect('staff.php');
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
foreach ($files as $f) {
    $total += estimate_price($f);
}
$cur = setting('currency', '₹');
$closed = in_array($job['status'], ['done', 'cancelled'], true);

function sel(string $name, array $opts, string $val): string
{
    $s = '<select name="' . $name . '">';
    foreach ($opts as $k => $label) {
        $s .= '<option value="' . h($k) . '"' . ((string)$k === $val ? ' selected' : '') . '>' . h($label) . '</option>';
    }
    return $s . '</select>';
}

page_header('Order ' . $job['code'], true);
echo flash();
?>
<a href="staff.php" class="back">← All orders</a>
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
</div>

<?php foreach ($files as $f): ?>
  <?php $gone = $f['stored_name'] === ''; ?>
  <div class="card file-card fstatus-<?= h($f['status']) ?>">
    <div class="file-head">
      <span class="fname">📄 <?= h($f['original_name']) ?></span>
      <span class="badge"><?= h($f['status']) ?><?= $f['print_count'] > 1 ? ' ×' . (int)$f['print_count'] : '' ?></span>
    </div>
    <div class="muted">
      <?= strtoupper(h($f['ext'])) ?> · <?= format_bytes((int)$f['size_bytes']) ?>
      <?= $f['pages_total'] ? ' · ' . (int)$f['pages_total'] . ' page(s)' : '' ?>
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
        <label>Paper size<?= sel('paper', array_combine(PAPER_SIZES, PAPER_SIZES), $f['paper']) ?></label>
        <label>Colour<?= sel('color', ['bw' => 'Black & white', 'color' => 'Colour'], $f['color']) ?></label>
        <label>Sides<?= sel('sides', ['single' => 'One side', 'double' => 'Both sides'], $f['sides']) ?></label>
        <label>Layout<?= sel('orientation', ['portrait' => 'Portrait', 'landscape' => 'Landscape'], $f['orientation']) ?></label>
        <label>Pages<input name="page_range" value="<?= h($f['page_range']) ?>" placeholder="All"></label>
        <div class="price muted">≈ <?= h($cur) . number_format(estimate_price($f), 2) ?></div>
        <div class="actions wide">
          <button class="btn primary big" name="action" value="print">🖨 OK – Print</button>
          <button class="btn" name="action" value="save">Save</button>
          <button class="btn" name="action" value="mark_printed" title="Use after printing manually from the preview">Mark printed</button>
        </div>
      </form>
    <?php endif; ?>
  </div>
<?php endforeach; ?>

<div class="card">
  <?php if (!$closed): ?>
    <form method="post" class="actions">
      <?= csrf_field() ?>
      <input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
      <?php if (count($files) > 1): ?>
        <button class="btn primary" name="action" value="print_all">🖨 Print all remaining</button>
      <?php endif; ?>
    </form>
    <form method="post" class="done-row">
      <?= csrf_field() ?>
      <input type="hidden" name="id" value="<?= (int)$job['id'] ?>">
      <label>Bill amount (<?= h($cur) ?>)<input name="amount" inputmode="decimal" value="<?= h(number_format($total, 2, '.', '')) ?>"></label>
      <button class="btn ok big" name="action" value="done">✔ Complete order</button>
      <button class="btn danger" name="action" value="cancel" onclick="return confirm('Cancel this order?')">Cancel order</button>
    </form>
  <?php else: ?>
    <p>Order is <b><?= h($job['status']) ?></b><?= $job['status'] === 'done' ? ' · bill ' . h($cur) . number_format((float)$job['amount'], 2) : '' ?>.</p>
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
</script>
<?php page_footer(); ?>
