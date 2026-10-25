<?php
// Super admin: all shops (create, open, rename, enable/disable) and the super admin accounts.

require __DIR__ . '/lib.php';
$me = require_super();

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_check();
    $action = (string)($_POST['action'] ?? '');
    $pdo = db();
    $sid = (int)($_POST['shop'] ?? 0);
    $uid = (int)($_POST['user_id'] ?? 0);
    $text = fn(string $k, int $len = 100) => mb_substr(trim((string)($_POST[$k] ?? '')), 0, $len);

    if ($action === 'open') {
        $_SESSION['shop_id'] = $sid;
        redirect('staff.php');
    } elseif ($action === 'create_shop') {
        $name = $text('name');
        $slug = strtolower($text('slug', 40));
        $user = $text('username', 50);
        $pass = (string)($_POST['password'] ?? '');
        if ($name === '' || !valid_slug($slug)) {
            flash('Enter a shop name and a link name: 3–40 small letters, numbers or dashes (e.g. riyadh-1).', 'err');
        } elseif (!valid_username($user) || strlen($pass) < 6) {
            flash('Shop admin: username 3–50 letters/numbers, password at least 6 characters.', 'err');
        } else {
            try {
                $pdo->beginTransaction();
                $new = create_shop($name, $slug, $user, $pass, $text('full_name'));
                $pdo->commit();
                $_SESSION['shop_id'] = $new;
                flash("Shop \"$name\" created with admin \"$user\". You are now working in this shop.");
            } catch (PDOException $e) {
                $pdo->rollBack();
                flash($e->errorInfo[1] == 1062 ? 'That link name or username is already used.' : 'Could not create the shop.', 'err');
            }
        }
    } elseif ($action === 'edit_shop') {
        $name = $text('name');
        $slug = strtolower($text('slug', 40));
        if ($name === '' || !valid_slug($slug)) {
            flash('Enter a shop name and a valid link name.', 'err');
        } else {
            try {
                $pdo->prepare('UPDATE shops SET name = ?, slug = ? WHERE id = ?')->execute([$name, $slug, $sid]);
                $pdo->prepare("UPDATE settings SET v = ? WHERE shop_id = ? AND k = 'shop_name'")->execute([$name, $sid]);
                flash('Shop saved. If the link name changed, print a new QR code for that shop.');
            } catch (PDOException $e) {
                flash('That link name is already used.', 'err');
            }
        }
    } elseif ($action === 'toggle_photo') {
        // Right of the shop to use photo print (the shop admin then switches it on in Settings → Photo print).
        $cur = $pdo->prepare("SELECT v FROM settings WHERE shop_id = ? AND k = 'photo_allowed'");
        $cur->execute([$sid]);
        $v = $cur->fetchColumn();
        $allowed = $v === false || $v === '1'; // not set yet = allowed
        $pdo->prepare("INSERT INTO settings (shop_id, k, v) VALUES (?, 'photo_allowed', ?) ON DUPLICATE KEY UPDATE v = VALUES(v)")
            ->execute([$sid, $allowed ? '0' : '1']);
        flash($allowed ? 'Photo print blocked for this shop.' : 'Photo print allowed – the shop admin can switch it on in Settings → Photo print.');
    } elseif ($action === 'toggle_shop') {
        $pdo->prepare('UPDATE shops SET active = 1 - active WHERE id = ?')->execute([$sid]);
        flash('Shop updated. A disabled shop takes no orders and its staff cannot log in.');
    } elseif ($action === 'create_super') {
        $user = $text('username', 50);
        $pass = (string)($_POST['password'] ?? '');
        if (!valid_username($user) || strlen($pass) < 6) {
            flash('Username 3–50 letters/numbers, password at least 6 characters.', 'err');
        } else {
            try {
                $pdo->prepare("INSERT INTO users (shop_id, username, full_name, password_hash, role) VALUES (NULL, ?, ?, ?, 'super')")
                    ->execute([$user, $text('full_name'), password_hash($pass, PASSWORD_DEFAULT)]);
                flash("Super admin \"$user\" created.");
            } catch (PDOException $e) {
                flash('That username already exists.', 'err');
            }
        }
    } elseif ($action === 'super_password') {
        $pass = (string)($_POST['password'] ?? '');
        if (strlen($pass) < 6) {
            flash('Password must be at least 6 characters.', 'err');
        } else {
            $pdo->prepare("UPDATE users SET password_hash = ? WHERE id = ? AND role = 'super'")
                ->execute([password_hash($pass, PASSWORD_DEFAULT), $uid]);
            flash('Password changed.');
        }
    } elseif ($action === 'toggle_super' && $uid !== (int)$me['id']) {
        $pdo->prepare("UPDATE users SET active = 1 - active WHERE id = ? AND role = 'super'")->execute([$uid]);
        flash('Super admin updated.');
    }
    redirect('shops.php');
}

$shops = db()->query("SELECT s.*,
        (SELECT COUNT(*) FROM users u WHERE u.shop_id = s.id) AS staff,
        (SELECT COUNT(*) FROM jobs j WHERE j.shop_id = s.id AND j.created_at >= CURDATE()) AS today,
        (SELECT COALESCE(SUM(j.amount), 0) FROM jobs j WHERE j.shop_id = s.id AND j.status = 'done' AND j.updated_at >= CURDATE()) AS bill,
        (SELECT v FROM settings t WHERE t.shop_id = s.id AND t.k = 'agent_seen') AS seen,
        COALESCE((SELECT v FROM settings t WHERE t.shop_id = s.id AND t.k = 'photo_allowed'), '1') AS photo_allowed,
        COALESCE((SELECT v FROM settings t WHERE t.shop_id = s.id AND t.k = 'photo_enabled'), '0') AS photo_on
    FROM shops s ORDER BY s.name")->fetchAll();
$supers = db()->query("SELECT id, username, full_name, active FROM users WHERE role = 'super' ORDER BY username")->fetchAll();

page_header('Shops', true, 'en', 'settings.php');
echo flash();
?>
<p class="muted">You are a <b>super admin</b>: open any shop to see its orders and settings. Working in:
  <b><?= h(shop()['name'] ?? '–') ?></b></p>

<?php foreach ($shops as $s): $on = (int)$s['id'] === shop_id(); $agentOk = time() - (int)$s['seen'] < 60; ?>
  <div class="card shop-card<?= $s['active'] ? '' : ' disabled' ?><?= $on ? ' current' : '' ?>">
    <div class="user-head">
      <span class="avatar">🏪</span>
      <div class="grow"><b><?= h($s['name']) ?></b><?= $on ? ' <span class="badge">current</span>' : '' ?><?= $s['active'] ? '' : ' <span class="badge">disabled</span>' ?>
        <div class="muted"><?= (int)$s['staff'] ?> staff · <?= (int)$s['today'] ?> orders today · <?= h(money((float)$s['bill'])) ?> ·
          printer <?= $agentOk ? '🟢 connected' : '⚪ offline' ?></div>
        <div class="muted">📷 Photo print: <?= $s['photo_allowed'] !== '1' ? '⛔ blocked' : ($s['photo_on'] === '1' ? '🟢 on' : 'allowed, off') ?></div>
        <div class="muted small-link"><?= h(base_url()) ?>index.php?shop=<?= h($s['slug']) ?></div>
      </div>
    </div>
    <div class="actions">
      <form method="post"><?= csrf_field() ?><input type="hidden" name="shop" value="<?= (int)$s['id'] ?>">
        <button class="btn primary" name="action" value="open">Open shop</button></form>
      <form method="post"><?= csrf_field() ?><input type="hidden" name="shop" value="<?= (int)$s['id'] ?>">
        <button class="btn" name="action" value="toggle_photo"><?= $s['photo_allowed'] !== '1' ? '📷 Allow photo print' : '📷 Block photo print' ?></button></form>
      <a class="btn" href="pctool.php?shop=<?= (int)$s['id'] ?>" title="One file that sets up this shop's PC for printing">⬇ PC tool</a>
      <form method="post"><?= csrf_field() ?><input type="hidden" name="shop" value="<?= (int)$s['id'] ?>">
        <button class="btn" name="action" value="toggle_shop"><?= $s['active'] ? 'Disable' : 'Enable' ?></button></form>
    </div>
    <details>
      <summary>Rename / link name</summary>
      <form method="post" class="opts">
        <?= csrf_field() ?><input type="hidden" name="shop" value="<?= (int)$s['id'] ?>">
        <label>Shop name<input name="name" value="<?= h($s['name']) ?>" required></label>
        <label>Link name<input name="slug" value="<?= h($s['slug']) ?>" required pattern="[a-z0-9][a-z0-9\-]{1,38}[a-z0-9]"></label>
        <div class="actions wide"><button class="btn" name="action" value="edit_shop">Save</button></div>
      </form>
    </details>
  </div>
<?php endforeach; ?>

<div class="card">
  <h2>Add a new shop</h2>
  <p class="muted">The new shop gets its own orders, prices, printers, QR code and PC tool, and its own admin.</p>
  <form method="post" class="opts" id="newShop">
    <?= csrf_field() ?>
    <label>Shop name<input name="name" required maxlength="100" placeholder="e.g. DAYbill Riyadh"></label>
    <label>Link name<input name="slug" required pattern="[a-z0-9][a-z0-9\-]{1,38}[a-z0-9]" placeholder="e.g. riyadh" autocapitalize="none"></label>
    <label>Shop admin username<input name="username" required pattern="[A-Za-z0-9_.\-]{3,50}" autocapitalize="none"></label>
    <label>Shop admin full name<input name="full_name"></label>
    <label>Shop admin password<input name="password" type="password" required minlength="6" autocomplete="new-password"></label>
    <div class="actions wide"><button class="btn primary block" name="action" value="create_shop">Create shop</button></div>
  </form>
</div>

<h3 class="menu-title">Super admins (full access to all shops)</h3>
<?php foreach ($supers as $u): ?>
  <div class="card user-card<?= $u['active'] ? '' : ' disabled' ?>">
    <div class="user-head">
      <span class="avatar"><?= h(mb_strtoupper(mb_substr($u['full_name'] ?: $u['username'], 0, 1))) ?></span>
      <div class="grow"><b><?= h($u['full_name'] ?: $u['username']) ?></b>
        <div class="muted">@<?= h($u['username']) ?><?= (int)$u['id'] === (int)$me['id'] ? ' · you' : '' ?><?= $u['active'] ? '' : ' · disabled' ?></div></div>
    </div>
    <details>
      <summary>Manage</summary>
      <form method="post" class="row-form">
        <?= csrf_field() ?><input type="hidden" name="user_id" value="<?= (int)$u['id'] ?>">
        <input type="password" name="password" placeholder="New password (min 6)" minlength="6" required autocomplete="new-password">
        <button class="btn" name="action" value="super_password">Set password</button>
      </form>
      <?php if ((int)$u['id'] !== (int)$me['id']): ?>
        <form method="post" class="actions"><?= csrf_field() ?><input type="hidden" name="user_id" value="<?= (int)$u['id'] ?>">
          <button class="btn" name="action" value="toggle_super"><?= $u['active'] ? 'Disable login' : 'Enable login' ?></button></form>
      <?php endif; ?>
    </details>
  </div>
<?php endforeach; ?>
<div class="card">
  <h2>Add super admin</h2>
  <form method="post" class="opts">
    <?= csrf_field() ?>
    <label>Username<input name="username" required pattern="[A-Za-z0-9_.\-]{3,50}" autocapitalize="none"></label>
    <label>Full name<input name="full_name"></label>
    <label>Password<input name="password" type="password" required minlength="6" autocomplete="new-password"></label>
    <div class="actions wide"><button class="btn primary" name="action" value="create_super">Create super admin</button></div>
  </form>
</div>

<script>
// Suggest a link name from the shop name.
(function () {
  var f = document.getElementById('newShop'), touched = false;
  f.slug.addEventListener('input', function () { touched = true; });
  f.name.addEventListener('input', function () {
    if (!touched) f.slug.value = f.name.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
  });
})();
</script>
<?php page_footer(); ?>
