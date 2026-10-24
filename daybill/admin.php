<?php
// Admin: manage employees and shop/printer settings.

require __DIR__ . '/lib.php';
require __DIR__ . '/printer.php';
$admin = require_admin();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $action = (string)($_POST['action'] ?? '');
    $pdo = db();
    $uid = (int)($_POST['user_id'] ?? 0);

    if ($action === 'create_user') {
        $username = trim((string)($_POST['username'] ?? ''));
        $pass = (string)($_POST['password'] ?? '');
        $role = ($_POST['role'] ?? '') === 'admin' ? 'admin' : 'employee';
        if (!preg_match('/^[A-Za-z0-9_.-]{3,50}$/', $username)) {
            flash('Username: 3–50 letters, numbers, dot, dash or underscore.', 'err');
        } elseif (strlen($pass) < 6) {
            flash('Password must be at least 6 characters.', 'err');
        } else {
            try {
                $pdo->prepare('INSERT INTO users (username, full_name, password_hash, role) VALUES (?, ?, ?, ?)')
                    ->execute([$username, mb_substr(trim((string)($_POST['full_name'] ?? '')), 0, 100),
                        password_hash($pass, PASSWORD_DEFAULT), $role]);
                flash("User \"$username\" created.");
            } catch (PDOException $e) {
                flash($e->errorInfo[1] == 1062 ? 'That username already exists.' : 'Could not create user.', 'err');
            }
        }
    } elseif ($action === 'reset_password') {
        $pass = (string)($_POST['password'] ?? '');
        if (strlen($pass) < 6) {
            flash('Password must be at least 6 characters.', 'err');
        } else {
            $pdo->prepare('UPDATE users SET password_hash = ? WHERE id = ?')->execute([password_hash($pass, PASSWORD_DEFAULT), $uid]);
            flash('Password changed.');
        }
    } elseif ($action === 'toggle_active' && $uid !== (int)$admin['id']) {
        $pdo->prepare('UPDATE users SET active = 1 - active WHERE id = ?')->execute([$uid]);
        flash('User updated.');
    } elseif ($action === 'delete_user' && $uid !== (int)$admin['id']) {
        $pdo->prepare('DELETE FROM users WHERE id = ?')->execute([$uid]);
        flash('User deleted.');
    } elseif ($action === 'settings') {
        save_setting('shop_name', mb_substr(trim((string)($_POST['shop_name'] ?? '')), 0, 100) ?: 'Daybill Print');
        save_setting('printer_bw', mb_substr(trim((string)($_POST['printer_bw'] ?? '')), 0, 200));
        save_setting('printer_color', mb_substr(trim((string)($_POST['printer_color'] ?? '')), 0, 200));
        save_setting('price_bw', (string)max(0, (float)($_POST['price_bw'] ?? 0)));
        save_setting('price_color', (string)max(0, (float)($_POST['price_color'] ?? 0)));
        save_setting('currency', mb_substr(trim((string)($_POST['currency'] ?? '')), 0, 5));
        save_setting('retention_days', (string)max(0, (int)($_POST['retention_days'] ?? 2)));
        flash('Settings saved.');
    }
    redirect('admin.php');
}

$users = db()->query('SELECT id, username, full_name, role, active, created_at FROM users ORDER BY role, username')->fetchAll();
$printers = list_printers();

page_header('Admin', true);
echo flash();
?>
<div class="card">
  <h2>Employees</h2>
  <table class="tbl">
    <tr><th>User</th><th>Role</th><th>Status</th><th></th></tr>
    <?php foreach ($users as $u): ?>
      <tr>
        <td><b><?= h($u['username']) ?></b><br><small class="muted"><?= h($u['full_name']) ?></small></td>
        <td><?= h($u['role']) ?></td>
        <td><?= $u['active'] ? 'Active' : '<span class="muted">Disabled</span>' ?></td>
        <td class="actions">
          <form method="post" class="inline">
            <?= csrf_field() ?><input type="hidden" name="user_id" value="<?= (int)$u['id'] ?>">
            <input type="password" name="password" placeholder="New password" minlength="6" required>
            <button class="btn small" name="action" value="reset_password">Set</button>
          </form>
          <?php if ((int)$u['id'] !== (int)$admin['id']): ?>
            <form method="post" class="inline">
              <?= csrf_field() ?><input type="hidden" name="user_id" value="<?= (int)$u['id'] ?>">
              <button class="btn small" name="action" value="toggle_active"><?= $u['active'] ? 'Disable' : 'Enable' ?></button>
              <button class="btn small danger" name="action" value="delete_user" onclick="return confirm('Delete user?')">Delete</button>
            </form>
          <?php endif; ?>
        </td>
      </tr>
    <?php endforeach; ?>
  </table>

  <h3>Add new employee</h3>
  <form method="post" class="opts">
    <?= csrf_field() ?>
    <label>Username<input name="username" required pattern="[A-Za-z0-9_.\-]{3,50}"></label>
    <label>Full name<input name="full_name"></label>
    <label>Password<input name="password" type="password" required minlength="6"></label>
    <label>Role<select name="role"><option value="employee">Employee</option><option value="admin">Admin</option></select></label>
    <div class="actions wide"><button class="btn primary" name="action" value="create_user">Create employee</button></div>
  </form>
</div>

<div class="card">
  <h2>Shop &amp; printer settings</h2>
  <form method="post" class="opts">
    <?= csrf_field() ?>
    <label>Shop name<input name="shop_name" value="<?= h(setting('shop_name')) ?>"></label>
    <label>B/W printer
      <input name="printer_bw" list="printers" value="<?= h(setting('printer_bw')) ?>" placeholder="(Windows default printer)">
    </label>
    <label>Colour printer
      <input name="printer_color" list="printers" value="<?= h(setting('printer_color')) ?>" placeholder="(same as B/W)">
    </label>
    <datalist id="printers"><?php foreach ($printers as $p): ?><option value="<?= h($p) ?>"><?php endforeach; ?></datalist>
    <label>Price per page B/W<input name="price_bw" inputmode="decimal" value="<?= h(setting('price_bw')) ?>"></label>
    <label>Price per page colour<input name="price_color" inputmode="decimal" value="<?= h(setting('price_color')) ?>"></label>
    <label>Currency symbol<input name="currency" value="<?= h(setting('currency')) ?>"></label>
    <label>Delete files after (days, 0 = never)<input name="retention_days" type="number" min="0" value="<?= h(setting('retention_days', '2')) ?>"></label>
    <div class="actions wide"><button class="btn primary" name="action" value="settings">Save settings</button></div>
  </form>
  <p class="muted">Printers found on this PC: <?= $printers ? h(implode(', ', $printers)) : 'none detected (type the exact printer name)' ?></p>
</div>
<?php page_footer(); ?>
