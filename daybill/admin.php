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
        save_setting('currency', mb_substr(trim((string)($_POST['currency'] ?? '')), 0, 5));
        save_setting('default_lang', ($_POST['default_lang'] ?? '') === 'ar' ? 'ar' : 'en');
        save_setting('retention_days', (string)max(0, (int)($_POST['retention_days'] ?? 2)));
        flash('Settings saved.');
    } elseif ($action === 'printing') {
        $mode = (string)($_POST['print_mode'] ?? '');
        save_setting('print_mode', in_array($mode, ['local', 'agent', 'browser'], true) ? $mode : 'local');
        $name = fn($v) => mb_substr(trim((string)$v), 0, 200);
        save_setting('printer_bw', $name($_POST['printer_bw'] ?? ''));
        save_setting('printer_color', $name($_POST['printer_color'] ?? ''));
        save_setting('sumatra_path', $name($_POST['sumatra_path'] ?? ''));
        $map = [];
        foreach ((array)($_POST['map'] ?? []) as $paper => $byColor) {
            foreach (COLORS as $c) {
                $n = $name(((array)$byColor)[$c] ?? '');
                if ($n !== '' && in_array($paper, all_papers(), true)) {
                    $map[$paper][$c] = $n;
                }
            }
        }
        save_setting('printer_map', json_encode($map));
        if ($mode === 'agent' && setting('agent_key') === '') {
            save_setting('agent_key', bin2hex(random_bytes(20)));
        }
        flash('Printing settings saved.');
    } elseif ($action === 'new_agent_key') {
        save_setting('agent_key', bin2hex(random_bytes(20)));
        flash('New agent key created – update agent-config.php on the shop PC.');
    } elseif ($action === 'options') {
        $custom = array_filter(array_map(fn($p) => mb_substr(preg_replace('/[^\p{L}\p{N} ._x×-]/u', '', trim($p)), 0, 30),
            explode(',', (string)($_POST['papers_custom'] ?? ''))), 'strlen');
        save_setting('papers_custom', implode(',', array_unique($custom)));
        $pick = fn(string $k, array $all) => implode(',', array_intersect($all, (array)($_POST[$k] ?? [])));
        save_setting('papers_enabled', $pick('papers', all_papers()) ?: 'A4');
        save_setting('colors_enabled', $pick('colors', COLORS) ?: 'bw');
        save_setting('sides_enabled', $pick('sides', SIDES) ?: 'single');
        flash('Customer options saved – set prices for any new combination below.');
    } elseif ($action === 'prices') {
        $table = pricing_table();
        foreach ((array)($_POST['rule'] ?? []) as $paper => $byColor) {
            if (!in_array($paper, all_papers(), true)) {
                continue;
            }
            foreach ((array)$byColor as $color => $bySides) {
                foreach ((array)$bySides as $side => $r) {
                    if (in_array($color, COLORS, true) && in_array($side, SIDES, true) && is_array($r)) {
                        $num = fn($v) => max(0, (float)str_replace(',', '.', (string)$v));
                        $table[$paper][$color][$side] = [(int)$num($r[0] ?? 1), $num($r[1] ?? 0), $num($r[2] ?? 0)];
                    }
                }
            }
        }
        save_setting('pricing', json_encode($table));
        flash('Prices saved.');
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

<?php
$mode = setting('print_mode', 'local');
$labels = ['bw' => 'Black & white', 'color' => 'Colour', 'single' => 'One side', 'double' => 'Both sides'];
$seen = (int)setting('agent_seen', '0');
?>
<div class="card">
  <h2>Customer options</h2>
  <p class="muted">Only ticked options are shown to customers. If only one is ticked (e.g. only A4), customers see just that.</p>
  <form method="post">
    <?= csrf_field() ?>
    <h3>Paper sizes</h3>
    <div class="checks">
      <?php foreach (all_papers() as $p): ?>
        <label class="check"><input type="checkbox" name="papers[]" value="<?= h($p) ?>" <?= in_array($p, enabled_papers(), true) ? 'checked' : '' ?>> <?= h($p) ?></label>
      <?php endforeach; ?>
    </div>
    <label>Add your own paper sizes (comma separated, e.g. <code>Photo 4x6, B5</code>)
      <input name="papers_custom" value="<?= h(setting('papers_custom')) ?>">
      <small>Custom sizes are printed on the printer's current paper – load the right paper first.</small>
    </label>
    <h3>Colour</h3>
    <div class="checks">
      <?php foreach (COLORS as $c): ?>
        <label class="check"><input type="checkbox" name="colors[]" value="<?= $c ?>" <?= in_array($c, enabled_colors(), true) ? 'checked' : '' ?>> <?= $labels[$c] ?></label>
      <?php endforeach; ?>
    </div>
    <h3>Sides</h3>
    <div class="checks">
      <?php foreach (SIDES as $sd): ?>
        <label class="check"><input type="checkbox" name="sides[]" value="<?= $sd ?>" <?= in_array($sd, enabled_sides(), true) ? 'checked' : '' ?>> <?= $labels[$sd] ?></label>
      <?php endforeach; ?>
    </div>
    <div class="actions"><button class="btn primary" name="action" value="options">Save options</button></div>
  </form>
</div>

<div class="card">
  <h2>Prices</h2>
  <p class="muted">Per order file: the first <b>N pages</b> cost the <b>fixed price</b>, each page after that costs the <b>extra page</b> price
    (pages × copies). Example: N = 2, fixed = 2, extra = 1 → 1–2 pages = 2 <?= h(setting('currency', 'SR')) ?>, 5 pages = 5 <?= h(setting('currency', 'SR')) ?>.
    Staff can still change the price of any order.</p>
  <form method="post">
    <?= csrf_field() ?>
    <div class="tbl-wrap">
    <table class="tbl price-tbl">
      <tr><th>Paper</th><th>Colour</th><th>Sides</th><th>First N pages</th><th>Fixed price</th><th>Each extra page</th><th>Example 10 pages</th></tr>
      <?php foreach (enabled_papers() as $p): foreach (enabled_colors() as $c): foreach (enabled_sides() as $sd): $r = price_rule($p, $c, $sd); ?>
        <tr>
          <td><b><?= h($p) ?></b></td><td><?= $labels[$c] ?></td><td><?= $labels[$sd] ?></td>
          <td data-label="First N pages"><input name="rule[<?= h($p) ?>][<?= $c ?>][<?= $sd ?>][0]" type="number" min="0" value="<?= (int)$r[0] ?>"></td>
          <td data-label="Fixed price"><input name="rule[<?= h($p) ?>][<?= $c ?>][<?= $sd ?>][1]" inputmode="decimal" value="<?= h((string)$r[1]) ?>"></td>
          <td data-label="Each extra page"><input name="rule[<?= h($p) ?>][<?= $c ?>][<?= $sd ?>][2]" inputmode="decimal" value="<?= h((string)$r[2]) ?>"></td>
          <td class="muted" data-label="10 pages">= <?= h(money(rule_price($r, 10))) ?></td>
        </tr>
      <?php endforeach; endforeach; endforeach; ?>
    </table>
    </div>
    <div class="actions"><button class="btn primary" name="action" value="prices">Save prices</button></div>
  </form>
</div>

<div class="card">
  <h2>Printing</h2>
  <form method="post" class="opts">
    <?= csrf_field() ?>
    <label class="wide">Print mode
      <select name="print_mode">
        <option value="local" <?= $mode === 'local' ? 'selected' : '' ?>>Local – app runs on the shop PC (XAMPP), prints directly</option>
        <option value="agent" <?= $mode === 'agent' ? 'selected' : '' ?>>Cloud + print agent – hosted online (e.g. Hostinger), agent on shop PC prints</option>
        <option value="browser" <?= $mode === 'browser' ? 'selected' : '' ?>>Browser – staff open the file and print from the browser</option>
      </select>
    </label>
    <label>Default B/W printer
      <input name="printer_bw" list="printers" value="<?= h(setting('printer_bw')) ?>" placeholder="(Windows default printer)">
    </label>
    <label>Default colour printer
      <input name="printer_color" list="printers" value="<?= h(setting('printer_color')) ?>" placeholder="(same as B/W)">
    </label>
    <div class="wide">
      <h3>Printer for each paper size</h3>
      <p class="muted">e.g. A4 → your A4 laser printer, A3 → your A3 printer. Leave empty to use the default printer above.
        Staff can still pick another printer on each order.</p>
      <div class="tbl-wrap">
      <table class="tbl map-tbl">
        <tr><th>Paper</th><?php foreach (enabled_colors() as $c): ?><th><?= $labels[$c] ?> printer</th><?php endforeach; ?></tr>
        <?php $map = printer_map(); foreach (enabled_papers() as $p): ?>
          <tr>
            <td><b><?= h($p) ?></b></td>
            <?php foreach (enabled_colors() as $c): ?>
              <td data-label="<?= $labels[$c] ?>"><input name="map[<?= h($p) ?>][<?= $c ?>]" list="printers" value="<?= h($map[$p][$c] ?? '') ?>" placeholder="(default)"></td>
            <?php endforeach; ?>
          </tr>
        <?php endforeach; ?>
      </table>
      </div>
    </div>
    <datalist id="printers"><?php foreach (known_printers() as $p): ?><option value="<?= h($p) ?>"><?php endforeach; ?></datalist>
    <?php if ($mode === 'local' && core_is_windows()): ?>
      <label class="wide">SumatraPDF.exe location (leave empty to find it automatically)
        <input name="sumatra_path" value="<?= h(setting('sumatra_path')) ?>" placeholder="C:\Program Files\SumatraPDF\SumatraPDF.exe">
      </label>
    <?php endif; ?>
    <div class="actions wide"><button class="btn primary" name="action" value="printing">Save printing</button></div>
  </form>
  <?php if ($mode === 'local'): ?>
    <p class="muted">Printers found on this computer: <?= $printers ? h(implode(', ', $printers)) : 'none detected (type the exact printer name as shown in Windows Settings → Printers)' ?></p>
    <?php if (core_is_windows()): $sp = sumatra_path(); ?>
      <?php if ($sp !== ''): ?>
        <div class="alert ok">✅ SumatraPDF found: <?= h($sp) ?></div>
      <?php else: ?>
        <div class="alert err">❌ SumatraPDF not found – one-tap printing will not work yet. Either:
          <ol>
            <li>Install it from <a href="https://www.sumatrapdfreader.org/download-free-pdf-viewer" target="_blank" rel="noopener">sumatrapdfreader.org</a> (choose "Install for all users" if asked), or</li>
            <li>Download the <b>portable</b> version and put the .exe in <code><?= h(__DIR__ . DIRECTORY_SEPARATOR . 'tools') ?></code></li>
          </ol>
          Then reload this page.</div>
      <?php endif; ?>
    <?php endif; ?>
  <?php elseif ($mode === 'agent'): ?>
    <div class="alert <?= time() - $seen < 60 ? 'ok' : 'err' ?>">
      Print agent: <?= $seen ? (time() - $seen < 60 ? 'connected' : 'last seen ' . h(date('d M, h:i A', $seen))) : 'never connected' ?>
    </div>
    <p>Agent key (put in <code>agent/agent-config.php</code> on the shop PC):</p>
    <p><code class="key"><?= h(setting('agent_key')) ?></code></p>
    <p class="muted">Server URL for the agent: <code><?= h(base_url()) ?></code></p>
    <form method="post"><?= csrf_field() ?>
      <button class="btn small danger" name="action" value="new_agent_key" onclick="return confirm('The old key stops working. Continue?')">Create new key</button>
    </form>
  <?php endif; ?>
</div>

<div class="card">
  <h2>Shop settings</h2>
  <form method="post" class="opts">
    <?= csrf_field() ?>
    <label>Shop name<input name="shop_name" value="<?= h(setting('shop_name')) ?>"></label>
    <label>Currency<input name="currency" value="<?= h(setting('currency', 'SR')) ?>"></label>
    <label>Customer page language
      <select name="default_lang">
        <option value="en" <?= setting('default_lang', 'en') === 'en' ? 'selected' : '' ?>>English</option>
        <option value="ar" <?= setting('default_lang', 'en') === 'ar' ? 'selected' : '' ?>>العربية (Arabic)</option>
      </select>
    </label>
    <label>Delete files after (days, 0 = never)<input name="retention_days" type="number" min="0" value="<?= h(setting('retention_days', '2')) ?>"></label>
    <div class="actions wide"><button class="btn primary" name="action" value="settings">Save settings</button></div>
  </form>
</div>
<?php page_footer(); ?>
