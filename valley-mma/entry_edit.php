<?php
// Add or edit an income, expense or transfer entry in the accounts ledger.

require __DIR__ . '/includes/init.php';
require __DIR__ . '/includes/accounts.php';
$me = require_admin();

$id = (int)($_GET['id'] ?? $_POST['id'] ?? 0);
$row = $id ? q('SELECT * FROM acc_entries WHERE id = ?', [$id])->fetch() : null;
if ($id && !$row) {
    redirect('ledger.php');
}
$type = $row['type'] ?? (in_array(get('type'), ['income', 'expense', 'transfer'], true) ? get('type') : 'expense');
$accounts = acc_accounts();
$accIds = array_map('intval', array_column(acc_accounts(true), 'id'));
$errors = [];

if ($_SERVER['REQUEST_METHOD'] === 'POST' && post('action') === 'delete' && $row) {
    require_verify('entry_edit.php?id=' . $id);
    q('DELETE FROM acc_entries WHERE id = ?', [$id]);
    flash('success', t('entry_deleted', $row['voucher_no']));
    redirect('ledger.php');
}

$d = $row ?: ['entry_date' => today(), 'category_id' => null, 'account_id' => $accounts[0]['id'] ?? 1,
    'to_account_id' => $accounts[1]['id'] ?? null, 'amount' => '', 'party' => '', 'description' => '', 'ref_no' => ''];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $type = in_array(post('type'), ['income', 'expense', 'transfer'], true) ? post('type') : 'expense';
    $d['entry_date'] = post('entry_date');
    $d['amount'] = num(post('amount'));
    $d['account_id'] = (int)post('account_id');
    $d['to_account_id'] = $type === 'transfer' ? (int)post('to_account_id') : null;
    $d['category_id'] = $type === 'transfer' ? null : (int)post('category_id');
    $d['party'] = mb_substr(post('party'), 0, 100);
    $d['description'] = mb_substr(post('description'), 0, 255);
    $d['ref_no'] = mb_substr(post('ref_no'), 0, 50);
    if (!valid_date($d['entry_date'])) {
        $errors[] = t('err_date');
    }
    if (!verify_ok()) {
        $errors[] = t('verify_wrong');
    }
    if ($d['amount'] <= 0) {
        $errors[] = t('err_amount');
    }
    if (!in_array($d['account_id'], $accIds, true)) {
        $errors[] = t('err_account');
    }
    if ($type === 'transfer' && (!in_array($d['to_account_id'], $accIds, true) || $d['to_account_id'] === $d['account_id'])) {
        $errors[] = t('err_transfer');
    }
    if ($type !== 'transfer' && !q('SELECT COUNT(*) FROM acc_categories WHERE id = ? AND type = ?', [$d['category_id'], $type])->fetchColumn()) {
        $errors[] = t('err_category');
    }
    if (!$errors) {
        $vals = [$d['entry_date'], $type, $d['category_id'] ?: null, $d['account_id'], $d['to_account_id'] ?: null, $d['amount'],
            $d['party'], $d['description'], $d['ref_no']];
        if ($row) {
            q('UPDATE acc_entries SET entry_date = ?, type = ?, category_id = ?, account_id = ?, to_account_id = ?, amount = ?,
               party = ?, description = ?, ref_no = ? WHERE id = ?', array_merge($vals, [$id]));
        } else {
            $no = next_voucher_no();
            q('INSERT INTO acc_entries (entry_date, type, category_id, account_id, to_account_id, amount, party, description, ref_no, voucher_no, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', array_merge($vals, [$no, $me['id']]));
            $id = (int)db()->lastInsertId();
        }
        flash('success', t('entry_saved'));
        redirect(post('again') === '1' ? 'entry_edit.php?type=' . $type : 'voucher.php?id=' . $id);
    }
}

$cats = acc_categories();
$title = $row ? t('edit_entry') : t('add_' . $type);
$active = 'accounts';
$back = $row ? 'ledger.php' : 'accounts.php';
require __DIR__ . '/includes/header.php';
$val = fn($k) => e((string)($d[$k] ?? ''));
?>
<?php if ($errors): ?><div class="alert alert-danger"><?= implode('<br>', array_map('e', array_unique($errors))) ?></div><?php endif; ?>
<form method="post" class="row g-3" id="entryForm" style="max-width:760px" data-verify="<?= e(t('verify_money')) ?>">
  <?= csrf_field() ?><input type="hidden" name="id" value="<?= $row ? $id : '' ?>">
  <div class="col-12">
    <div class="btn-group w-100" role="group">
      <?php foreach (['income' => ['bi-plus-circle', 'success'], 'expense' => ['bi-dash-circle', 'danger'], 'transfer' => ['bi-arrow-left-right', 'dark']] as $k => [$ic, $cl]): ?>
        <input type="radio" class="btn-check" name="type" id="ty_<?= $k ?>" value="<?= $k ?>"<?= $type === $k ? ' checked' : '' ?> data-entry-type data-title="<?= e(t('add_' . $k)) ?>">
        <label class="btn btn-outline-<?= $cl ?> btn-lg" for="ty_<?= $k ?>"><i class="bi <?= $ic ?>"></i> <?= e(t('acc_' . $k)) ?></label>
      <?php endforeach; ?>
    </div>
  </div>
  <div class="col-12"><div class="card"><div class="card-body row g-3">
    <div class="col-6"><label class="form-label" for="entry_date"><?= e(t('date')) ?></label>
      <input class="form-control" type="date" id="entry_date" name="entry_date" value="<?= $val('entry_date') ?>" required></div>
    <div class="col-6"><label class="form-label" for="amount"><?= e(t('amount')) ?> (₹)</label>
      <input class="form-control form-control-lg fw-bold" type="number" min="0.01" step="0.01" id="amount" name="amount" value="<?= $val('amount') ?>" required inputmode="decimal" autofocus></div>

    <div class="col-12 when-cat"><label class="form-label"><?= e(t('category')) ?></label>
      <div class="d-flex flex-wrap gap-2">
        <?php foreach ($cats as $c): ?>
          <span class="cat-opt" data-cat-type="<?= $c['type'] ?>">
            <input type="radio" class="btn-check" name="category_id" id="cat<?= $c['id'] ?>" value="<?= $c['id'] ?>"<?= (int)$d['category_id'] === (int)$c['id'] ? ' checked' : '' ?>>
            <label class="btn btn-sm <?= $c['type'] === 'income' ? 'btn-outline-success' : 'btn-outline-danger' ?>" for="cat<?= $c['id'] ?>"><?= e($c['name']) ?></label>
          </span>
        <?php endforeach; ?>
        <a href="acc_settings.php#categories" class="btn btn-sm btn-light"><i class="bi bi-plus"></i> <?= e(t('new_category')) ?></a>
      </div>
      <?php if (!$row): ?><div class="small-muted mt-1"><?= e(t('fee_auto_note')) ?></div><?php endif; ?>
    </div>

    <div class="col-6"><label class="form-label" for="account_id"><span class="when-cat"><?= e(t('account')) ?></span><span class="when-transfer"><?= e(t('from_account')) ?></span></label>
      <select class="form-select" id="account_id" name="account_id">
        <?php foreach ($accounts as $a): ?><option value="<?= $a['id'] ?>"<?= (int)$d['account_id'] === (int)$a['id'] ? ' selected' : '' ?>><?= e($a['name']) ?></option><?php endforeach; ?>
      </select></div>
    <div class="col-6 when-transfer"><label class="form-label" for="to_account_id"><?= e(t('to_account')) ?></label>
      <select class="form-select" id="to_account_id" name="to_account_id">
        <?php foreach ($accounts as $a): ?><option value="<?= $a['id'] ?>"<?= (int)$d['to_account_id'] === (int)$a['id'] ? ' selected' : '' ?>><?= e($a['name']) ?></option><?php endforeach; ?>
      </select></div>
    <div class="col-6 when-cat"><label class="form-label" for="party"><span class="when-income"><?= e(t('received_from')) ?></span><span class="when-expense"><?= e(t('paid_to')) ?></span></label>
      <input class="form-control" id="party" name="party" value="<?= $val('party') ?>" maxlength="100" list="parties"></div>
    <div class="col-md-8"><label class="form-label" for="description"><?= e(t('description')) ?></label>
      <input class="form-control" id="description" name="description" value="<?= $val('description') ?>" maxlength="255"></div>
    <div class="col-md-4"><label class="form-label" for="ref_no"><?= e(t('ref_no')) ?></label>
      <input class="form-control" id="ref_no" name="ref_no" value="<?= $val('ref_no') ?>" maxlength="50" placeholder="<?= e(t('ref_no_ph')) ?>"></div>
  </div></div></div>
  <div class="col-12 d-flex flex-wrap gap-2 align-items-center mb-4">
    <button class="btn btn-primary btn-lg px-4"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button>
    <?php if (!$row): ?><button class="btn btn-outline-primary btn-lg" name="again" value="1"><?= e(t('save_add_another')) ?></button><?php endif; ?>
    <a href="<?= e($back) ?>" class="btn btn-light btn-lg ms-auto"><?= e(t('cancel')) ?></a>
  </div>
</form>
<?php if ($row): ?>
  <form method="post" data-verify="<?= e(t('confirm_delete')) ?>" class="mb-5"><?= csrf_field() ?>
    <input type="hidden" name="id" value="<?= $id ?>"><input type="hidden" name="action" value="delete">
    <button class="btn btn-outline-danger"><i class="bi bi-trash"></i> <?= e(t('delete')) ?></button></form>
<?php endif; ?>
<datalist id="parties">
  <?php foreach (q("SELECT DISTINCT party FROM acc_entries WHERE party <> '' ORDER BY party LIMIT 200")->fetchAll(PDO::FETCH_COLUMN) as $p): ?><option value="<?= e($p) ?>"><?php endforeach; ?>
</datalist>
<?php require __DIR__ . '/includes/footer.php';
