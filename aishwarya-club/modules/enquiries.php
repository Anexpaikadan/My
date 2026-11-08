<?php
// ================================================================
// Admin → Enquiries: "Join the Club" requests from the public website
// ================================================================
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/lang.php';
require_once __DIR__ . '/../includes/site_schema.php';
require_once __DIR__ . '/../includes/sudo.php';
requireLogin();
if (!isFullAdmin()) { header('Location: ' . url('dashboard.php') . '?err=access'); exit; }
site_tables();

$STATUS = array('new'=>array('New','c-red'), 'contacted'=>array('Contacted','c-blue'), 'joined'=>array('Joined','c-green'), 'closed'=>array('Closed','c-slate'));
$flash = '';
if ($_SERVER['REQUEST_METHOD'] === 'POST' && verifyCsrf()) {
    $id = (int)($_POST['id'] ?? 0);
    $do = $_POST['do'] ?? '';
    if ($do === 'status' && isset($STATUS[$_POST['status'] ?? ''])) {
        db()->prepare("UPDATE enquiries SET status=?, note=? WHERE id=?")->execute(array($_POST['status'], mb_substr(trim($_POST['note'] ?? ''), 0, 250), $id));
        $flash = 'Saved.';
    } elseif ($do === 'delete') {
        sudo_require();
        db()->prepare("DELETE FROM enquiries WHERE id=?")->execute(array($id));
        $flash = 'Deleted.';
    }
    header('Location: ' . url('modules/enquiries.php') . '?f=' . rawurlencode($_GET['f'] ?? 'new') . '&ok=' . rawurlencode($flash)); exit;
}

$f = isset($STATUS[$_GET['f'] ?? '']) || ($_GET['f'] ?? '') === 'all' ? $_GET['f'] : 'new';
$counts = array('all'=>0); foreach ($STATUS as $k => $v) $counts[$k] = 0;
foreach (db()->query("SELECT status, COUNT(*) c FROM enquiries GROUP BY status")->fetchAll() as $r) { $counts[$r['status']] = (int)$r['c']; $counts['all'] += (int)$r['c']; }
if ($f === 'all') $rows = db()->query("SELECT * FROM enquiries ORDER BY created_at DESC LIMIT 300")->fetchAll();
else { $st = db()->prepare("SELECT * FROM enquiries WHERE status=? ORDER BY created_at DESC LIMIT 300"); $st->execute(array($f)); $rows = $st->fetchAll(); }
$club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');

$pageTitle = 'Enquiries';
require_once __DIR__ . '/../includes/header.php';
?>
<style>
.eq-tabs{display:flex;gap:.4rem;overflow-x:auto;margin-bottom:1rem;scrollbar-width:none}
.eq-tabs::-webkit-scrollbar{display:none}
.eq-tabs a{flex:0 0 auto;display:inline-flex;align-items:center;gap:.4rem;min-height:44px;padding:.4rem .95rem;border-radius:2rem;background:#fff;border:1px solid var(--line);color:var(--text-2);font-weight:700;font-size:.88rem;text-decoration:none}
.eq-tabs a.on{background:var(--dark);border-color:var(--dark);color:#fff}
.eq-tabs .n{background:var(--light);color:var(--text);border-radius:1rem;padding:0 .45rem;font-size:.78rem}
.eq-tabs a.on .n{background:rgba(255,255,255,.18);color:#fff}
.eq-list{display:grid;gap:.8rem}
@media(min-width:900px){.eq-list{grid-template-columns:1fr 1fr}}
.eq-card{background:#fff;border:1px solid var(--line);border-radius:1rem;padding:1rem;box-shadow:0 4px 16px -10px rgba(11,16,51,.25)}
.eq-top{display:flex;justify-content:space-between;gap:.6rem;align-items:flex-start}
.eq-top b{font-size:1.05rem}
.eq-meta{font-size:.85rem;color:var(--text-3)}
.eq-int{display:flex;flex-wrap:wrap;gap:.3rem;margin:.5rem 0}
.eq-int span{background:var(--light);border-radius:1rem;padding:.15rem .6rem;font-size:.8rem;font-weight:600;color:var(--text-2)}
.eq-st{font-size:.75rem;font-weight:800;text-transform:uppercase;padding:.2rem .6rem;border-radius:1rem;color:#fff;white-space:nowrap}
.eq-st.c-red{background:var(--brand)}.eq-st.c-blue{background:var(--accent)}.eq-st.c-green{background:#157a3f}.eq-st.c-slate{background:#475569}
.eq-acts{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.6rem}
.eq-acts .btn{flex:1 1 auto}
.eq-form{display:grid;grid-template-columns:1fr auto;gap:.4rem;margin-top:.6rem}
.eq-form .form-select,.eq-form .form-control{min-height:44px;font-size:1rem}
.eq-form .form-control{grid-column:1 / -1}
</style>
<section class="section">
  <h1 class="h-app mb-2"><i class="bi bi-envelope-paper" aria-hidden="true"></i> Enquiries</h1>
  <p class="eq-meta mb-3">People who tapped "Join the Club" on the website. Message them on WhatsApp, then mark them.</p>
  <?php if(!empty($_GET['ok'])): ?><div class="alert alert-ok" role="status"><?= h(mb_substr($_GET['ok'], 0, 60)) ?></div><?php endif; ?>
  <nav class="eq-tabs" aria-label="Filter">
    <?php foreach(array_merge($STATUS, array('all'=>array('All',''))) as $k => $v): ?>
    <a href="?f=<?= $k ?>" class="<?= $f === $k ? 'on' : '' ?>"<?= $f === $k ? ' aria-current="page"' : '' ?>><?= h($v[0]) ?> <span class="n"><?= (int)$counts[$k] ?></span></a>
    <?php endforeach; ?>
  </nav>
  <?php if(!$rows): ?>
    <div class="card"><div class="card-body text-center py-5"><i class="bi bi-inbox fs-1 text-secondary" aria-hidden="true"></i><p class="mt-2 mb-0">No enquiries here.</p></div></div>
  <?php else: ?>
  <div class="eq-list">
    <?php foreach($rows as $r): $digits = preg_replace('/\D/', '', $r['phone']); $st = $STATUS[$r['status']] ?? $STATUS['new'];
      $msg = "Hello {$r['name']}, thank you for your interest in {$club}. "; ?>
    <article class="eq-card">
      <div class="eq-top">
        <div><b><?= h($r['name']) ?></b><div class="eq-meta"><?= h($r['place'] ?: '—') ?> · <?= h($r['phone']) ?></div><div class="eq-meta"><?= date('d M Y, g:i a', strtotime($r['created_at'])) ?></div></div>
        <span class="eq-st <?= $st[1] ?>"><?= h($st[0]) ?></span>
      </div>
      <?php if($r['interest']): ?><div class="eq-int"><?php foreach(array_filter(array_map('trim', explode(',', $r['interest']))) as $it): ?><span><?= h($it) ?></span><?php endforeach; ?></div><?php endif; ?>
      <div class="eq-acts">
        <a class="btn btn-wa btn-sm" href="https://wa.me/<?= h($digits) ?>?text=<?= rawurlencode($msg) ?>" target="_blank" rel="noopener"><i class="bi bi-whatsapp" aria-hidden="true"></i> WhatsApp</a>
        <a class="btn btn-outline-dark btn-sm" href="tel:<?= h($r['phone']) ?>"><i class="bi bi-telephone" aria-hidden="true"></i> Call</a>
        <a class="btn btn-outline-dark btn-sm" href="<?= url('admin.php') ?>?tab=add&name=<?= rawurlencode($r['name']) ?>&phone=<?= rawurlencode(substr($digits, -10)) ?>"><i class="bi bi-person-plus" aria-hidden="true"></i> Add member</a>
      </div>
      <form method="post" class="eq-form">
        <?= csrfField() ?><input type="hidden" name="do" value="status"><input type="hidden" name="id" value="<?= (int)$r['id'] ?>">
        <label class="visually-hidden" for="st<?= (int)$r['id'] ?>">Status for <?= h($r['name']) ?></label>
        <select class="form-select" name="status" id="st<?= (int)$r['id'] ?>"><?php foreach($STATUS as $k => $v): ?><option value="<?= $k ?>"<?= $r['status'] === $k ? ' selected' : '' ?>><?= h($v[0]) ?></option><?php endforeach; ?></select>
        <button type="submit" class="btn btn-brand">Save</button>
        <label class="visually-hidden" for="nt<?= (int)$r['id'] ?>">Note for <?= h($r['name']) ?></label>
        <input class="form-control" name="note" id="nt<?= (int)$r['id'] ?>" value="<?= h($r['note'] ?? '') ?>" placeholder="Note (optional)">
      </form>
      <form method="post" class="mt-2 text-end" data-sudo data-confirm="Delete the enquiry from <?= h($r['name']) ?>?">
        <?= csrfField() ?><input type="hidden" name="do" value="delete"><input type="hidden" name="id" value="<?= (int)$r['id'] ?>">
        <button type="submit" class="btn btn-link text-danger btn-sm"><i class="bi bi-trash" aria-hidden="true"></i> Delete</button>
      </form>
    </article>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>
</section>
<?php require_once __DIR__ . '/../includes/footer.php'; ?>
