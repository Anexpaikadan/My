<?php
// Join requests: free trial requests from the public home page. Tabs by status; open one to chat on
// WhatsApp, send the join link with password and trial days, change the status.

require __DIR__ . '/includes/init.php';
require_admin();

const REQ_STATUS = ['new' => 'danger', 'following' => 'primary', 'waiting' => 'warning text-dark', 'trial' => 'info text-dark', 'joined' => 'success', 'not_interested' => 'secondary'];

$tab = array_key_exists(get('tab'), REQ_STATUS) || get('tab') === 'all' ? get('tab') : 'open';
$counts = q('SELECT status, COUNT(*) FROM join_requests GROUP BY status')->fetchAll(PDO::FETCH_KEY_PAIR);
$openCount = array_sum(array_intersect_key($counts, array_flip(['new', 'following', 'waiting', 'trial'])));
$s = trim(get('s'));
$where = $tab === 'all' ? '1' : ($tab === 'open' ? "status IN ('new', 'following', 'waiting', 'trial')" : 'status = ?');
$args = $tab === 'all' || $tab === 'open' ? [] : [$tab];
if ($s !== '') {
    $where .= ' AND (name LIKE ? OR phone LIKE ? OR place LIKE ?)';
    array_push($args, "%$s%", "%$s%", "%$s%");
}
$rows = q("SELECT * FROM join_requests WHERE $where ORDER BY status = 'new' DESC, updated_at DESC LIMIT 300", $args)->fetchAll();

$title = t('join_requests');
$active = 'requests';
$back = 'members.php';
require __DIR__ . '/includes/header.php';
?>
<form class="mb-2" method="get"><input type="hidden" name="tab" value="<?= e($tab) ?>">
  <input class="form-control" type="search" name="s" value="<?= e($s) ?>" placeholder="<?= e(t('search_name_phone')) ?>"></form>
<ul class="nav nav-pills mb-3 flex-nowrap overflow-auto pb-1">
  <li class="nav-item"><a class="nav-link text-nowrap<?= $tab === 'open' ? ' active' : '' ?>" href="?tab=open"><?= e(t('rq_open')) ?> <span class="badge text-bg-light border"><?= $openCount ?></span></a></li>
  <?php foreach (REQ_STATUS as $k => $cls): ?>
    <li class="nav-item"><a class="nav-link text-nowrap<?= $tab === $k ? ' active' : '' ?>" href="?tab=<?= $k ?>"><?= e(t('rq_' . $k)) ?> <span class="badge text-bg-light border"><?= (int)($counts[$k] ?? 0) ?></span></a></li>
  <?php endforeach; ?>
  <li class="nav-item"><a class="nav-link text-nowrap<?= $tab === 'all' ? ' active' : '' ?>" href="?tab=all"><?= e(t('all')) ?></a></li>
</ul>
<div class="card"><div class="list-group list-group-flush">
  <?php if (!$rows): ?><div class="list-group-item text-muted p-4 text-center"><?= e(t('no_requests')) ?></div><?php endif; ?>
  <?php foreach ($rows as $r): ?>
    <a href="join_request.php?id=<?= $r['id'] ?>" class="list-group-item list-group-item-action d-flex align-items-center gap-2">
      <span class="req-ava"><?= e(mb_strtoupper(mb_substr($r['name'], 0, 1))) ?></span>
      <span class="me-auto"><span class="fw-semibold"><?= e($r['name']) ?></span><?= $r['program'] !== '' ? ' <span class="small-muted">· ' . e($r['program']) . '</span>' : '' ?>
        <span class="d-block small-muted"><?= e($r['phone']) ?><?= $r['place'] !== '' ? ' · ' . e($r['place']) : '' ?> · <?= e(fdate($r['created_at'])) ?>
          <?= $r['trial_date'] ? ' · <i class="bi bi-calendar-check"></i> ' . e(fdate($r['trial_date'])) : '' ?></span></span>
      <span class="badge bg-<?= REQ_STATUS[$r['status']] ?>"><?= e(t('rq_' . $r['status'])) ?></span>
    </a>
  <?php endforeach; ?>
</div></div>
<?php require __DIR__ . '/includes/footer.php';
