<?php
// Admin settings pages: admin.php?s=employees | options | prices | printing | shop

require __DIR__ . '/lib.php';
require __DIR__ . '/printer.php';
$admin = require_admin();

$sections = ['employees' => 'Employees', 'options' => 'Customer options', 'prices' => 'Prices',
    'printing' => 'Printing', 'shop' => 'Shop settings', 'colors' => 'App colour'];
$themes = [
    'DAYbill' => ['#360dd9', '#7ed957'], 'Ocean' => ['#1f6feb', '#14b8a6'], 'Emerald' => ['#047857', '#f59e0b'],
    'Royal' => ['#6d28d9', '#ec4899'], 'Rose' => ['#be123c', '#0ea5e9'], 'Sunset' => ['#c2410c', '#2563eb'],
    'Midnight' => ['#12233f', '#22c55e'], 'Charcoal' => ['#27272a', '#eab308'],
];
$sec = (string)($_GET['s'] ?? '');
if (!isset($sections[$sec])) {
    redirect('settings.php');
}

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
    } elseif ($action === 'colors') {
        foreach (['color_primary' => 0, 'color_accent' => 1] as $k => $i) {
            $c = strtolower(trim((string)($_POST[$k] ?? '')));
            save_setting($k, valid_hex($c) && empty($_POST['reset_flag']) ? $c : DEFAULT_COLORS[$i]);
        }
        flash(!empty($_POST['reset_flag']) ? 'Colours reset to the DAYbill logo colours.' : 'App colours saved.');
    } elseif ($action === 'settings') {
        save_setting('shop_name', mb_substr(trim((string)($_POST['shop_name'] ?? '')), 0, 100) ?: 'Daybill Print');
        save_setting('currency', mb_substr(trim((string)($_POST['currency'] ?? '')), 0, 5));
        save_setting('default_lang', ($_POST['default_lang'] ?? '') === 'ar' ? 'ar' : 'en');
        save_setting('retention_days', (string)max(0, (int)($_POST['retention_days'] ?? 2)));
        save_setting('auto_complete', isset($_POST['auto_complete']) ? '1' : '0');
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
    redirect('admin.php?s=' . $sec);
}

$users = db()->query('SELECT id, username, full_name, role, active, created_at FROM users ORDER BY role, username')->fetchAll();
$printers = $sec === 'printing' ? list_printers() : [];
$mode = setting('print_mode', 'local');
$labels = ['bw' => 'Black & white', 'color' => 'Colour', 'single' => 'One side', 'double' => 'Both sides'];
$seen = (int)setting('agent_seen', '0');

page_header($sections[$sec], true, 'en', 'settings.php');
echo flash();
?>
<?php if ($sec === 'employees'): ?>
<?php foreach ($users as $u): ?>
  <div class="card user-card<?= $u['active'] ? '' : ' disabled' ?>">
    <div class="user-head">
      <span class="avatar"><?= h(mb_strtoupper(mb_substr($u['full_name'] ?: $u['username'], 0, 1))) ?></span>
      <div class="grow"><b><?= h($u['full_name'] ?: $u['username']) ?></b>
        <div class="muted">@<?= h($u['username']) ?> · <?= h($u['role']) ?><?= $u['active'] ? '' : ' · disabled' ?><?= (int)$u['id'] === (int)$admin['id'] ? ' · you' : '' ?></div></div>
    </div>
    <details>
      <summary>Manage</summary>
      <form method="post" class="row-form">
        <?= csrf_field() ?><input type="hidden" name="user_id" value="<?= (int)$u['id'] ?>">
        <input type="password" name="password" placeholder="New password (min 6)" minlength="6" required autocomplete="new-password">
        <button class="btn" name="action" value="reset_password">Set password</button>
      </form>
      <?php if ((int)$u['id'] !== (int)$admin['id']): ?>
        <form method="post" class="actions">
          <?= csrf_field() ?><input type="hidden" name="user_id" value="<?= (int)$u['id'] ?>">
          <button class="btn" name="action" value="toggle_active"><?= $u['active'] ? 'Disable login' : 'Enable login' ?></button>
          <button class="btn danger" name="action" value="delete_user" onclick="return confirm('Delete user?')">Delete</button>
        </form>
      <?php endif; ?>
    </details>
  </div>
<?php endforeach; ?>

<div class="card">
  <h2>Add new employee</h2>
  <form method="post" class="opts">
    <?= csrf_field() ?>
    <label>Username<input name="username" required pattern="[A-Za-z0-9_.\-]{3,50}" autocapitalize="none"></label>
    <label>Full name<input name="full_name"></label>
    <label>Password<input name="password" type="password" required minlength="6" autocomplete="new-password"></label>
    <label>Role<select name="role"><option value="employee">Employee</option><option value="admin">Admin</option></select></label>
    <div class="actions wide"><button class="btn primary block" name="action" value="create_user">Create employee</button></div>
  </form>
</div>

<?php elseif ($sec === 'options'): ?>
<div class="card">
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

<?php elseif ($sec === 'prices'): ?>
<div class="card">
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

<?php elseif ($sec === 'printing'): ?>
<div class="card">
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

<?php elseif ($sec === 'colors'): [$cp, $ca] = app_colors(); ?>
<div class="card">
  <p class="muted">Choose the colours of the app for customers and staff. <b>Main colour</b>: buttons, tabs, order codes.
    <b>Second colour</b>: amount to pay, success messages and the line under the logo.</p>
  <h3>Ready themes</h3>
  <div class="swatches">
    <?php foreach ($themes as $name => [$tp, $ta]): ?>
      <button type="button" class="swatch<?= [$tp, $ta] === [$cp, $ca] ? ' on' : '' ?>" data-p="<?= $tp ?>" data-a="<?= $ta ?>">
        <i><b style="background:<?= $tp ?>"></b><b style="background:<?= $ta ?>"></b></i><?= h($name) ?>
      </button>
    <?php endforeach; ?>
  </div>
  <form method="post" id="colorForm">
    <?= csrf_field() ?>
    <h3>Your own colours</h3>
    <div class="color-row">
      <label>Main colour<input type="color" name="color_primary" value="<?= h($cp) ?>"></label>
      <label>Second colour<input type="color" name="color_accent" value="<?= h($ca) ?>"></label>
    </div>
    <div class="preview">
      <div class="pv-bar"></div>
      <div class="pv-body">
        <span class="pv-btn">OK – Print</span>
        <span class="pv-pay">Amount to pay: 6 SR</span>
      </div>
    </div>
    <div class="actions">
      <button class="btn primary" name="action" value="colors">Save colours</button>
      <button class="btn" name="action" value="colors" formnovalidate onclick="this.form.reset_flag.value=1">Reset to logo colours</button>
      <input type="hidden" name="reset_flag" value="">
    </div>
  </form>
</div>
<script>
(function () {
  var f = document.getElementById('colorForm'), p = f.color_primary, a = f.color_accent;
  function mix(hex, k) { // toward white
    var n = parseInt(hex.slice(1), 16), c = [n >> 16, n >> 8 & 255, n & 255];
    return 'rgb(' + c.map(function (v) { return Math.round(v + (255 - v) * k); }).join(',') + ')';
  }
  function lum(hex) {
    var n = parseInt(hex.slice(1), 16);
    return [n >> 16, n >> 8 & 255, n & 255].map(function (v) { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); })
      .reduce(function (s, v, i) { return s + v * [.2126, .7152, .0722][i]; }, 0);
  }
  function paint() {
    var bar = f.querySelector('.pv-bar'), btn = f.querySelector('.pv-btn'), pay = f.querySelector('.pv-pay');
    bar.style.background = 'linear-gradient(90deg,' + p.value + ' 0 62%,' + a.value + ' 62% 100%)';
    btn.style.background = p.value; btn.style.color = lum(p.value) > .45 ? '#111' : '#fff';
    pay.style.background = mix(a.value, .88); pay.style.border = '1px solid ' + mix(a.value, .6);
    document.querySelectorAll('.swatch').forEach(function (s) { s.classList.toggle('on', s.dataset.p === p.value && s.dataset.a === a.value); });
  }
  document.querySelectorAll('.swatch').forEach(function (s) {
    s.onclick = function () { p.value = s.dataset.p; a.value = s.dataset.a; paint(); };
  });
  p.oninput = a.oninput = paint;
  paint();
})();
</script>

<?php else: ?>
<div class="card">
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
    <label class="check wide"><input type="checkbox" name="auto_complete" value="1" <?= setting('auto_complete', '1') === '1' ? 'checked' : '' ?>>
      Complete orders automatically when all files are printed (bill = calculated price)</label>
    <div class="actions wide"><button class="btn primary" name="action" value="settings">Save settings</button></div>
  </form>
</div>
<?php endif; ?>
<?php page_footer(); ?>
