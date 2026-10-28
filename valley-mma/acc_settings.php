<?php
// Accounts setup: money accounts (cash, bank, UPI) with opening balance, income/expense categories,
// and which account receives membership payments for each payment method.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/accounts.php';
require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $a = post('action');
    $id = (int)post('id');
    if ($a === 'account') {
        $name = mb_substr(post('name'), 0, 60);
        $kind = in_array(post('kind'), ['cash', 'bank', 'upi'], true) ? post('kind') : 'cash';
        $open = round((float)post('opening_balance'), 2);
        $act = post('active') === '1' ? 1 : 0;
        if ($name === '') {
            flash('danger', t('err_name'));
        } elseif ($id) {
            q('UPDATE acc_accounts SET name = ?, kind = ?, opening_balance = ?, active = ? WHERE id = ?', [$name, $kind, $open, $act, $id]);
            flash('success', t('saved'));
        } else {
            q('INSERT INTO acc_accounts (name, kind, opening_balance, active, sort_order) VALUES (?, ?, ?, 1, 9)', [$name, $kind, $open]);
            flash('success', t('saved'));
        }
    } elseif ($a === 'category') {
        $name = mb_substr(post('name'), 0, 60);
        $type = post('type') === 'income' ? 'income' : 'expense';
        $act = post('active') === '1' ? 1 : 0;
        if ($name === '') {
            flash('danger', t('err_name'));
        } elseif ($id) {
            q('UPDATE acc_categories SET name = ?, active = ? WHERE id = ?', [$name, $act, $id]);
            flash('success', t('saved'));
        } else {
            q('INSERT INTO acc_categories (name, type, sort_order) VALUES (?, ?, 50)', [$name, $type]);
            flash('success', t('saved'));
        }
    } elseif ($a === 'delete_category') {
        $used = (int)q('SELECT COUNT(*) FROM acc_entries WHERE category_id = ?', [$id])->fetchColumn();
        if ($used || $id === acc_fee_category()) {
            q('UPDATE acc_categories SET active = 0 WHERE id = ?', [$id]);
            flash('warning', t('category_hidden'));
        } else {
            q('DELETE FROM acc_categories WHERE id = ?', [$id]);
            flash('success', t('removed'));
        }
    } elseif ($a === 'mapping') {
        $ids = array_map('intval', array_column(acc_accounts(true), 'id'));
        foreach (['cash', 'upi', 'card', 'bank'] as $m) {
            if (in_array((int)post('map_' . $m), $ids, true)) {
                set_setting('acc_map_' . $m, (string)(int)post('map_' . $m));
            }
        }
        if (q("SELECT COUNT(*) FROM acc_categories WHERE id = ? AND type = 'income'", [(int)post('fee_category')])->fetchColumn()) {
            set_setting('acc_fee_category', (string)(int)post('fee_category'));
        }
        flash('success', t('saved'));
    }
    redirect('acc_settings.php#' . ($a === 'delete_category' ? 'category' : $a));
}

$accounts = acc_accounts(true);
$cats = acc_categories(null, true);
$used = q('SELECT category_id, COUNT(*) n FROM acc_entries GROUP BY category_id')->fetchAll(PDO::FETCH_KEY_PAIR);

$title = t('acc_setup');
$active = 'accounts';
$back = 'accounts.php';
require __DIR__ . '/includes/header.php';
?>
<div class="row g-3">
  <div class="col-lg-6">
    <div class="card mb-3" id="account">
      <div class="card-header"><i class="bi bi-wallet2"></i> <?= e(t('money_accounts')) ?></div>
      <div class="list-group list-group-flush">
        <?php foreach ($accounts as $a): ?>
          <form method="post" class="list-group-item row g-2 m-0 align-items-center<?= $a['active'] ? '' : ' opacity-50' ?>"><?= csrf_field() ?>
            <input type="hidden" name="action" value="account"><input type="hidden" name="id" value="<?= $a['id'] ?>">
            <div class="col-12 col-sm-4"><input class="form-control form-control-sm" name="name" value="<?= e($a['name']) ?>" required aria-label="<?= e(t('name')) ?>"></div>
            <div class="col-4 col-sm-3"><select class="form-select form-select-sm" name="kind" aria-label="<?= e(t('type')) ?>">
              <?php foreach (['cash', 'bank', 'upi'] as $k): ?><option value="<?= $k ?>"<?= $a['kind'] === $k ? ' selected' : '' ?>><?= e(t('kind_' . $k)) ?></option><?php endforeach; ?></select></div>
            <div class="col-4 col-sm-3"><input class="form-control form-control-sm" type="number" step="0.01" name="opening_balance" value="<?= e($a['opening_balance']) ?>" title="<?= e(t('opening_balance')) ?>" aria-label="<?= e(t('opening_balance')) ?>"></div>
            <div class="col-4 col-sm-2 d-flex gap-1 align-items-center">
              <input class="form-check-input" type="checkbox" name="active" value="1"<?= $a['active'] ? ' checked' : '' ?> title="<?= e(t('in_use')) ?>" aria-label="<?= e(t('in_use')) ?>">
              <button class="btn btn-sm btn-outline-primary ms-auto"><i class="bi bi-check2"></i></button></div>
          </form>
        <?php endforeach; ?>
      </div>
      <form method="post" class="card-body border-top row g-2 m-0"><?= csrf_field() ?><input type="hidden" name="action" value="account">
        <div class="col-12 small fw-semibold"><?= e(t('add_account')) ?></div>
        <div class="col-12 col-sm-5"><input class="form-control" name="name" placeholder="<?= e(t('account_name_ph')) ?>" required></div>
        <div class="col-6 col-sm-3"><select class="form-select" name="kind"><?php foreach (['cash', 'bank', 'upi'] as $k): ?><option value="<?= $k ?>"><?= e(t('kind_' . $k)) ?></option><?php endforeach; ?></select></div>
        <div class="col-6 col-sm-2"><input class="form-control" type="number" step="0.01" name="opening_balance" placeholder="<?= e(t('opening_balance')) ?>"></div>
        <div class="col-12 col-sm-2"><button class="btn btn-primary w-100"><i class="bi bi-plus-lg"></i></button></div>
      </form>
      <div class="card-footer bg-transparent small-muted"><?= e(t('opening_hint')) ?></div>
    </div>

    <form method="post" class="card mb-3" id="mapping"><?= csrf_field() ?><input type="hidden" name="action" value="mapping">
      <div class="card-header"><i class="bi bi-diagram-3"></i> <?= e(t('fee_mapping')) ?></div>
      <div class="card-body row g-2">
        <?php foreach (['cash', 'upi', 'card', 'bank'] as $m): ?>
          <div class="col-6"><label class="form-label small"><?= e(t('m_' . $m)) ?> →</label>
            <select class="form-select" name="map_<?= $m ?>"><?php foreach ($accounts as $a): ?><option value="<?= $a['id'] ?>"<?= (int)setting('acc_map_' . $m) === (int)$a['id'] ? ' selected' : '' ?>><?= e($a['name']) ?></option><?php endforeach; ?></select></div>
        <?php endforeach; ?>
        <div class="col-12"><label class="form-label small"><?= e(t('fee_category')) ?></label>
          <select class="form-select" name="fee_category"><?php foreach ($cats as $c): if ($c['type'] !== 'income') continue; ?><option value="<?= $c['id'] ?>"<?= acc_fee_category() === (int)$c['id'] ? ' selected' : '' ?>><?= e($c['name']) ?></option><?php endforeach; ?></select></div>
        <div class="col-12 small-muted"><?= e(t('fee_mapping_hint')) ?></div>
      </div>
      <div class="card-footer bg-transparent"><button class="btn btn-primary"><?= e(t('save')) ?></button></div>
    </form>
  </div>

  <div class="col-lg-6" id="category"><span id="categories"></span>
    <?php foreach (['income', 'expense'] as $type): ?>
      <div class="card mb-3" id="categories-<?= $type ?>">
        <div class="card-header"><i class="bi <?= $type === 'income' ? 'bi-arrow-down-left-circle text-success' : 'bi-arrow-up-right-circle text-danger' ?>"></i> <?= e(t($type . '_categories')) ?></div>
        <div class="list-group list-group-flush">
          <?php foreach ($cats as $c): if ($c['type'] !== $type) continue; ?>
            <div class="list-group-item d-flex gap-2 align-items-center<?= $c['active'] ? '' : ' opacity-50' ?>">
              <form method="post" class="d-flex gap-2 align-items-center flex-grow-1"><?= csrf_field() ?>
                <input type="hidden" name="action" value="category"><input type="hidden" name="id" value="<?= $c['id'] ?>">
                <input class="form-control form-control-sm" name="name" value="<?= e($c['name']) ?>" required aria-label="<?= e(t('name')) ?>">
                <?php if ((int)$c['id'] === acc_fee_category()): ?><span class="badge text-bg-light" title="<?= e(t('fee_category')) ?>"><i class="bi bi-link-45deg"></i></span><input type="hidden" name="active" value="1"><?php else: ?>
                <input class="form-check-input flex-shrink-0" type="checkbox" name="active" value="1"<?= $c['active'] ? ' checked' : '' ?> title="<?= e(t('in_use')) ?>" aria-label="<?= e(t('in_use')) ?>"><?php endif; ?>
                <span class="small-muted text-nowrap"><?= (int)($used[$c['id']] ?? 0) ?></span>
                <button class="btn btn-sm btn-outline-primary"><i class="bi bi-check2"></i></button>
              </form>
              <?php if ((int)$c['id'] !== acc_fee_category()): ?>
                <form method="post" onsubmit="return confirm(<?= e(json_encode(t('confirm_delete'))) ?>)"><?= csrf_field() ?>
                  <input type="hidden" name="action" value="delete_category"><input type="hidden" name="id" value="<?= $c['id'] ?>">
                  <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i></button></form>
              <?php endif; ?>
            </div>
          <?php endforeach; ?>
        </div>
        <form method="post" class="card-body border-top d-flex gap-2"><?= csrf_field() ?>
          <input type="hidden" name="action" value="category"><input type="hidden" name="type" value="<?= $type ?>">
          <input class="form-control" name="name" placeholder="<?= e(t('new_category')) ?>" required>
          <button class="btn btn-primary"><i class="bi bi-plus-lg"></i></button>
        </form>
      </div>
    <?php endforeach; ?>
  </div>
</div>
<?php require __DIR__ . '/includes/footer.php';
