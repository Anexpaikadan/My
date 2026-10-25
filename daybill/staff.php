<?php
// Employee dashboard: list of incoming print orders.

require __DIR__ . '/lib.php';
$user = require_login();

// Lightweight polling endpoint used to detect new orders.
if (isset($_GET['poll'])) {
    header('Content-Type: application/json');
    // "latest" = newest order (beep), "stamp" changes whenever any order changes status.
    $st = db()->prepare("SELECT COALESCE(MAX(id), 0) AS latest, CONCAT(COALESCE(MAX(updated_at), ''), '/', COUNT(*)) AS stamp
                         FROM jobs WHERE shop_id = ?");
    $st->execute([shop_id()]);
    echo json_encode($st->fetch());
    exit;
}

cleanup_old_files();

$tab = in_array($_GET['tab'] ?? '', ['new', 'done', 'all'], true) ? $_GET['tab'] : 'new';
$q = strtoupper(trim((string)($_GET['q'] ?? '')));

$where = ['j.shop_id = ?'];
$args = [shop_id()];
if ($q !== '') {
    $where[] = '(j.code = ? OR j.customer_name LIKE ? OR j.phone LIKE ?)';
    array_push($args, $q, "%$q%", "%$q%");
} elseif ($tab === 'new') {
    $where[] = "j.status IN ('new','printing')";
} elseif ($tab === 'done') {
    $where[] = "j.status IN ('done','cancelled') AND j.updated_at >= CURDATE()";
} else {
    $where[] = 'j.created_at >= (CURDATE() - INTERVAL 7 DAY)';
}
$sql = 'SELECT j.*, COUNT(f.id) AS nfiles, SUM(f.status = \'printed\') AS nprinted, u.username AS handler
        FROM jobs j LEFT JOIN job_files f ON f.job_id = j.id LEFT JOIN users u ON u.id = j.handled_by
        WHERE ' . implode(' AND ', $where) . '
        GROUP BY j.id ORDER BY j.id ' . ($tab === 'new' && $q === '' ? 'ASC' : 'DESC') . ' LIMIT 200';
$st = db()->prepare($sql);
$st->execute($args);
$jobs = $st->fetchAll();

$st = db()->prepare("SELECT COUNT(*) AS n, COALESCE(SUM(amount), 0) AS total FROM jobs
                     WHERE shop_id = ? AND status = 'done' AND updated_at >= CURDATE()");
$st->execute([shop_id()]);
$today = $st->fetch();
$st = db()->prepare("SELECT COALESCE(MAX(id), 0) AS latest, CONCAT(COALESCE(MAX(updated_at), ''), '/', COUNT(*)) AS stamp
                     FROM jobs WHERE shop_id = ?");
$st->execute([shop_id()]);
$poll = $st->fetch();
$latest = (int)$poll['latest'];

page_header('Print jobs', true);
echo flash();
?>
<div class="stats">
  <div><b><?= (int)$today['n'] ?></b><span>done today</span></div>
  <div><b><?= h(money((float)$today['total'])) ?></b><span>today's bill</span></div>
</div>

<form class="search" method="get">
  <input name="q" value="<?= h($q) ?>" placeholder="Search code / name / phone" autocapitalize="characters">
  <button class="btn">Search</button>
</form>

<nav class="tabs">
  <a href="?tab=new" class="<?= $tab === 'new' && $q === '' ? 'on' : '' ?>">Waiting</a>
  <a href="?tab=done" class="<?= $tab === 'done' && $q === '' ? 'on' : '' ?>">Done today</a>
  <a href="?tab=all" class="<?= $tab === 'all' && $q === '' ? 'on' : '' ?>">Last 7 days</a>
</nav>

<?php if (!$jobs): ?>
  <p class="muted center">No orders here yet. New orders appear automatically.</p>
<?php endif; ?>

<div class="jobs">
<?php foreach ($jobs as $j): ?>
  <a class="job status-<?= h($j['status']) ?>" href="job.php?id=<?= (int)$j['id'] ?>">
    <span class="code"><?= h($j['code']) ?></span>
    <span class="info">
      <b><?= h($j['customer_name'] ?: 'Walk-in customer') ?></b>
      <small><?= (int)$j['nfiles'] ?> file(s) · <?= (int)$j['nprinted'] ?> printed · <?= h(date('d M, h:i A', strtotime($j['created_at']))) ?><?= $j['status'] === 'done' ? ' · ' . h(money((float)$j['amount'])) : '' ?></small>
      <?php if ($j['note']): ?><small class="note">📝 <?= h($j['note']) ?></small><?php endif; ?>
    </span>
    <span class="badge"><?= !$j['verified'] ? '🔒 PIN' : h($j['status']) ?></span>
  </a>
<?php endforeach; ?>
</div>

<script>
(function () {
  var latest = <?= $latest ?>, stamp = <?= json_encode($poll['stamp']) ?>;
  function beep() {
    try {
      var c = new (window.AudioContext || window.webkitAudioContext)(), o = c.createOscillator();
      o.connect(c.destination); o.frequency.value = 880; o.start(); o.stop(c.currentTime + 0.3);
    } catch (e) {}
  }
  setInterval(function () {
    fetch('staff.php?poll=1', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
      if (+d.latest > latest) { beep(); setTimeout(function () { location.reload(); }, 400); }
      else if (d.stamp !== stamp) { location.reload(); } // an order was printed / completed
    }).catch(function () {});
  }, 5000);
})();
</script>
<?php page_footer(); ?>
