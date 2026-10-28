<?php
// Membership plans: add, edit, change price/duration, delete, share on WhatsApp.

require __DIR__ . '/includes/init.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)post('id');
    if (post('action') === 'delete') {
        $used = (int)q('SELECT COUNT(*) FROM members WHERE plan_id = ?', [$id])->fetchColumn()
            + (int)q('SELECT COUNT(*) FROM payments WHERE plan_id = ?', [$id])->fetchColumn();
        if ($used) {
            q('UPDATE plans SET active = 0 WHERE id = ?', [$id]);
            flash('warning', t('plan_in_use'));
        } else {
            q('DELETE FROM plans WHERE id = ?', [$id]);
            flash('success', t('plan_deleted'));
        }
        redirect('plans.php');
    }
    $name = mb_substr(post('name'), 0, 100);
    $value = max(1, min(3650, (int)post('duration_value')));
    $unit = post('duration_unit') === 'day' ? 'day' : 'month';
    $price = num(post('price'));
    $desc = mb_substr(post('description'), 0, 500);
    $act = post('active', '0') === '1' ? 1 : 0;
    $sort = (int)post('sort_order');
    if ($name === '') {
        flash('danger', t('err_name'));
    } elseif ($id) {
        q('UPDATE plans SET name = ?, duration_value = ?, duration_unit = ?, price = ?, description = ?, active = ?, sort_order = ? WHERE id = ?',
            [$name, $value, $unit, $price, $desc, $act, $sort, $id]);
        flash('success', t('plan_saved'));
    } else {
        q('INSERT INTO plans (name, duration_value, duration_unit, price, description, active, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [$name, $value, $unit, $price, $desc, $act, $sort]);
        flash('success', t('plan_saved'));
    }
    redirect('plans.php');
}

$plans = q('SELECT p.*, (SELECT COUNT(*) FROM members m WHERE m.plan_id = p.id AND m.expiry_date >= CURDATE()) members
            FROM plans p ORDER BY p.active DESC, p.sort_order, p.id')->fetchAll();
$members = q('SELECT id, name, phone, adm_no FROM members ORDER BY name')->fetchAll();
$allText = '🥊 ' . gym_title() . ' – ' . setting('gym_place') . "\n" . t('membership_plans') . ":\n";
foreach ($plans as $p) {
    if ($p['active']) {
        $allText .= "\n• " . $p['name'] . ' (' . plan_duration($p) . '): ' . money($p['price']);
    }
}
$allText .= "\n\n📞 " . trim(setting('phone1') . ' / ' . setting('phone2'), ' /') . upi_text();

$title = t('membership_plans');
$active = 'plans';
$actions = '<a class="btn btn-whatsapp" target="_blank" rel="noopener" href="' . e(wa_link('', $allText)) . '"><i class="bi bi-whatsapp"></i> ' . e(t('share_all_plans')) . '</a>'
    . '<button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#planModal" data-plan="{}"><i class="bi bi-plus-lg"></i> ' . e(t('add_plan')) . '</button>';
require __DIR__ . '/includes/header.php';
?>
<div class="row g-3">
  <?php foreach ($plans as $p): ?>
    <div class="col-sm-6 col-xl-3">
      <div class="card h-100<?= $p['active'] ? '' : ' opacity-50' ?>">
        <div class="card-body d-flex flex-column">
          <div class="d-flex align-items-start">
            <h2 class="h5 mb-1 me-auto"><?= e($p['name']) ?></h2>
            <?php if (!$p['active']): ?><span class="badge bg-secondary"><?= e(t('hidden')) ?></span><?php endif; ?>
          </div>
          <div class="small-muted mb-2"><i class="bi bi-clock"></i> <?= e(plan_duration($p)) ?></div>
          <div class="display-6 fw-bold text-primary mb-2"><?= money($p['price']) ?></div>
          <p class="small mb-2"><?= e($p['description']) ?></p>
          <div class="small-muted mb-3"><i class="bi bi-people"></i> <?= e(t('n_active_members', (int)$p['members'])) ?></div>
          <div class="mt-auto d-flex flex-wrap gap-2">
            <button class="btn btn-sm btn-outline-primary" data-bs-toggle="modal" data-bs-target="#planModal" data-plan="<?= e(json_encode($p)) ?>"><i class="bi bi-pencil"></i> <?= e(t('edit')) ?></button>
            <button class="btn btn-sm btn-whatsapp" data-bs-toggle="modal" data-bs-target="#shareModal" data-text="<?= e(plan_text($p) . "\n\n📞 " . setting('phone1') . upi_text((float)$p['price'])) ?>"><i class="bi bi-whatsapp"></i> <?= e(t('send')) ?></button>
            <form method="post" class="ms-auto" onsubmit="return confirm(<?= e(json_encode(t('confirm_delete'))) ?>)">
              <?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= $p['id'] ?>">
              <button class="btn btn-sm btn-outline-danger" title="<?= e(t('delete')) ?>"><i class="bi bi-trash"></i></button>
            </form>
          </div>
        </div>
      </div>
    </div>
  <?php endforeach; ?>
</div>

<div class="modal fade" id="planModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered"><form class="modal-content" method="post">
    <?= csrf_field() ?><input type="hidden" name="id">
    <div class="modal-header"><h2 class="modal-title h5"><?= e(t('plan')) ?></h2><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body row g-3">
      <div class="col-12"><label class="form-label"><?= e(t('plan_name')) ?></label><input class="form-control" name="name" required maxlength="100" placeholder="<?= e(t('plan_name_ph')) ?>"></div>
      <div class="col-6"><label class="form-label"><?= e(t('duration')) ?></label><input class="form-control" type="number" name="duration_value" min="1" max="3650" value="1" required></div>
      <div class="col-6"><label class="form-label">&nbsp;</label><select class="form-select" name="duration_unit"><option value="month"><?= e(t('months')) ?></option><option value="day"><?= e(t('days')) ?></option></select></div>
      <div class="col-6"><label class="form-label"><?= e(t('price')) ?> (₹)</label><input class="form-control" type="number" name="price" min="0" step="0.01" required></div>
      <div class="col-6"><label class="form-label"><?= e(t('sort_order')) ?></label><input class="form-control" type="number" name="sort_order" value="0"></div>
      <div class="col-12"><label class="form-label"><?= e(t('description')) ?></label><textarea class="form-control" name="description" rows="2" maxlength="500"></textarea></div>
      <div class="col-12"><div class="form-check form-switch"><input class="form-check-input" type="checkbox" name="active" value="1" id="pa" checked><label class="form-check-label" for="pa"><?= e(t('plan_active')) ?></label></div></div>
    </div>
    <div class="modal-footer"><button class="btn btn-primary btn-lg w-100"><?= e(t('save')) ?></button></div>
  </form></div>
</div>

<div class="modal fade" id="shareModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable"><div class="modal-content">
    <div class="modal-header"><h2 class="modal-title h5"><i class="bi bi-whatsapp text-success"></i> <?= e(t('send_plan_whatsapp')) ?></h2><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
    <div class="modal-body">
      <textarea class="form-control mb-3" id="shareText" rows="6"></textarea>
      <label class="form-label"><?= e(t('send_to_member')) ?></label>
      <input class="form-control mb-2" type="search" id="shareSearch" placeholder="<?= e(t('search_ph')) ?>">
      <div class="list-group" id="shareList" style="max-height:240px;overflow:auto">
        <?php foreach ($members as $mm): ?>
          <a href="#" class="list-group-item list-group-item-action d-flex" data-phone="<?= e(wa_phone($mm['phone'])) ?>" data-name="<?= e(mb_strtolower($mm['name'] . ' ' . $mm['phone'] . ' ' . $mm['adm_no'])) ?>">
            <span class="me-auto"><?= e($mm['name']) ?></span><span class="small-muted"><?= e($mm['phone']) ?></span></a>
        <?php endforeach; ?>
      </div>
      <label class="form-label mt-3"><?= e(t('or_new_number')) ?></label>
      <div class="input-group"><input class="form-control" type="tel" id="sharePhone" placeholder="98XXXXXXXX"><button class="btn btn-whatsapp" type="button" id="shareGo"><i class="bi bi-send"></i></button></div>
      <a class="btn btn-outline-success w-100 mt-2" id="shareAny" href="#" target="_blank" rel="noopener"><?= e(t('choose_in_whatsapp')) ?></a>
    </div>
  </div></div>
</div>
<script>window.VM_CC = <?= json_encode(setting('country_code', '91')) ?>;</script>
<?php require __DIR__ . '/includes/footer.php';
