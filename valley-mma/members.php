<?php
// Member list with search, status filter and delete.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST' && post('action') === 'delete') {
    require_verify('members.php');
    $m = q('SELECT * FROM members WHERE id = ?', [(int)post('id')])->fetch();
    if ($m) {
        q('DELETE FROM members WHERE id = ?', [$m['id']]);
        if ($m['photo'] !== '' && is_file(cfg('photo_dir') . '/' . $m['photo'])) {
            unlink(cfg('photo_dir') . '/' . $m['photo']);
        }
        flash('success', t('member_deleted', $m['name']));
    }
    redirect('members.php');
}

$today = today();
$soon = date('Y-m-d', strtotime('+' . (int)setting('expiry_days', '7') . ' day'));
$s = get('s');
$status = get('status');
$planId = (int)get('plan');

$where = [];
$args = [];
if ($s !== '') {
    $where[] = '(m.name LIKE ? OR m.phone LIKE ? OR m.adm_no LIKE ? OR m.place LIKE ?)';
    array_push($args, "%$s%", "%$s%", "%$s%", "%$s%");
}
if ($status === 'pending' || $status === 'inactive') {
    $where[] = 'm.status = ?';
    $args[] = $status;
} elseif ($status === 'active') {
    $where[] = "m.status = 'active' AND m.expiry_date >= ?";
    $args[] = $today;
} elseif ($status === 'expiring') {
    $where[] = "m.status = 'active' AND m.expiry_date BETWEEN ? AND ?";
    array_push($args, $today, $soon);
} elseif ($status === 'expired') {
    $where[] = "m.status = 'active' AND (m.expiry_date < ? OR m.expiry_date IS NULL)";
    $args[] = $today;
} elseif ($status === 'frozen') {
    $where[] = 'm.id IN (SELECT member_id FROM member_freezes WHERE ? BETWEEN from_date AND to_date)';
    $args[] = $today;
}
if ($planId) {
    $where[] = 'm.plan_id = ?';
    $args[] = $planId;
}
$sqlWhere = $where ? 'WHERE ' . implode(' AND ', $where) : '';
$count = (int)q("SELECT COUNT(*) FROM members m $sqlWhere", $args)->fetchColumn();
$per = 30;
$pages = max(1, (int)ceil($count / $per));
$page = min($pages, max(1, (int)get('page', '1')));
$rows = q("SELECT m.*, p.name plan_name, (SELECT COALESCE(SUM(total - paid), 0) FROM payments WHERE member_id = m.id) balance
           FROM members m LEFT JOIN plans p ON p.id = m.plan_id $sqlWhere
           ORDER BY m.id DESC LIMIT $per OFFSET " . (($page - 1) * $per), $args)->fetchAll();
$plans = q('SELECT id, name FROM plans ORDER BY sort_order, id')->fetchAll();

$title = t('members') . " ($count)";
$active = 'members';
$back = 'index.php';
$actions = '<a href="member_edit.php" class="btn btn-primary"><i class="bi bi-person-plus-fill"></i> ' . e(t('add_member')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<form class="card card-body mb-3 filters" method="get">
  <div class="row g-2">
    <div class="col-12 col-md-5"><input class="form-control" type="search" name="s" value="<?= e($s) ?>" placeholder="<?= e(t('search_ph')) ?>"></div>
    <div class="col-6 col-md-3">
      <select class="form-select" name="status" onchange="this.form.submit()">
        <option value=""><?= e(t('all_status')) ?></option>
        <?php foreach (['active', 'expiring', 'expired', 'frozen', 'pending', 'inactive'] as $st): ?>
          <option value="<?= $st ?>"<?= $status === $st ? ' selected' : '' ?>><?= e(t('st_' . $st)) ?></option>
        <?php endforeach; ?>
      </select>
    </div>
    <div class="col-6 col-md-2">
      <select class="form-select" name="plan" onchange="this.form.submit()">
        <option value=""><?= e(t('all_plans')) ?></option>
        <?php foreach ($plans as $p): ?><option value="<?= $p['id'] ?>"<?= $planId === (int)$p['id'] ? ' selected' : '' ?>><?= e($p['name']) ?></option><?php endforeach; ?>
      </select>
    </div>
    <div class="col-12 col-md-2"><button class="btn btn-dark w-100"><i class="bi bi-search"></i> <?= e(t('search')) ?></button></div>
  </div>
</form>

<div class="card">
  <div class="table-responsive">
    <table class="table table-hover table-cards">
      <thead><tr><th><?= e(t('member')) ?></th><th><?= e(t('phone')) ?></th><th><?= e(t('plan')) ?></th><th><?= e(t('expiry_date')) ?></th><th><?= e(t('status')) ?></th><th><?= e(t('balance')) ?></th><th></th></tr></thead>
      <tbody>
      <?php if (!$rows): ?><tr><td colspan="7" class="text-center text-muted p-4"><?= e(t('no_members')) ?></td></tr><?php endif; ?>
      <?php foreach ($rows as $m): $st = member_status($m['expiry_date'], $m['status']); ?>
        <tr class="<?= $st === 'expired' ? 'row-expired' : ($st === 'expiring' ? 'row-expiring' : '') ?>">
          <td class="td-main"><a href="member_view.php?id=<?= $m['id'] ?>" class="member-row text-decoration-none text-dark">
            <img src="<?= e(photo_url($m)) ?>" class="avatar" alt="" loading="lazy">
            <span><span class="name d-block"><?= e($m['name']) ?></span><span class="small-muted"><?= e($m['adm_no']) ?> · <?= e(t('joined')) ?> <?= e(fdate($m['join_date'])) ?></span></span></a></td>
          <td data-label="<?= e(t('phone')) ?>"><a href="tel:<?= e(clean_phone($m['phone'])) ?>"><?= e($m['phone']) ?></a></td>
          <td data-label="<?= e(t('plan')) ?>"><?= e($m['plan_name'] ?? '–') ?></td>
          <td data-label="<?= e(t('expiry_date')) ?>"><?= e(fdate($m['expiry_date'])) ?></td>
          <td data-label="<?= e(t('status')) ?>"><?= status_badge($m['expiry_date'], $m['status']) ?> <?= level_badge(level_by_id($m['level_id'] !== null ? (int)$m['level_id'] : null)) ?><?= in_array((int)$m['id'], frozen_ids(), true) ? ' <span class="badge bg-info text-dark"><i class="bi bi-snow"></i> ' . e(t('frozen')) . '</span>' : '' ?></td>
          <td data-label="<?= e(t('balance')) ?>" class="<?= $m['balance'] > 0 ? 'text-danger fw-bold' : '' ?>"><?= money($m['balance']) ?></td>
          <td class="td-actions text-end text-nowrap">
            <a class="btn btn-sm btn-accent" href="payment_add.php?member=<?= $m['id'] ?>" title="<?= e(t('record_payment')) ?>"><i class="bi bi-cash-coin"></i></a>
            <a class="btn btn-sm btn-whatsapp" target="_blank" rel="noopener" href="<?= e(wa_link($m['phone'], $st === 'active' ? t('wa_hello', $m['name']) : reminder_text($m))) ?>" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>
            <a class="btn btn-sm btn-outline-primary" href="member_edit.php?id=<?= $m['id'] ?>" title="<?= e(t('edit')) ?>"><i class="bi bi-pencil"></i></a>
            <form method="post" class="d-inline" data-verify="<?= e(t('confirm_delete_member', $m['name'])) ?>">
              <?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= $m['id'] ?>">
              <button class="btn btn-sm btn-outline-danger" title="<?= e(t('delete')) ?>"><i class="bi bi-trash"></i></button>
            </form>
          </td>
        </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
  </div>
</div>
<?php if ($pages > 1): ?>
<nav class="mt-3"><ul class="pagination justify-content-center flex-wrap">
  <?php for ($i = 1; $i <= $pages; $i++): ?>
    <li class="page-item<?= $i === $page ? ' active' : '' ?>"><a class="page-link" href="?<?= e(http_build_query(['s' => $s, 'status' => $status, 'plan' => $planId ?: '', 'page' => $i])) ?>"><?= $i ?></a></li>
  <?php endfor; ?>
</ul></nav>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
