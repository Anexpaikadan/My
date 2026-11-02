<?php
// ================================================================
// Admin → Public Website: everything on the public home page.
//   Texts & photo · Sections on/off · Programs · Fees · Timings · Rules
//   Contact · Link preview (WhatsApp / Facebook sharing)
// Malayalam texts are saved under the same key + "_ml".
// ================================================================
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/lang.php';
require_once __DIR__ . '/../includes/og.php';
require_once __DIR__ . '/../includes/site_schema.php';
require_once __DIR__ . '/../includes/sudo.php';
require_once __DIR__ . '/upload_helper.php';
requireLogin();
if (!isFullAdmin()) { header('Location: ' . url('dashboard.php') . '?err=access'); exit; }
site_tables();

function ss_save($key, $value) {
    db()->prepare("INSERT INTO club_settings(setting_key,setting_value,setting_group,label,type) VALUES(?,?,'website',?,'text')
                   ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value)")->execute(array($key, $value, $key));
}
function ss_get($key, $default = '') {
    $s = db()->prepare("SELECT setting_value FROM club_settings WHERE setting_key=?"); $s->execute(array($key));
    $v = $s->fetchColumn(); return ($v === false || $v === null) ? $default : $v;
}
function ss_photo($field, $sub = 'site') {
    $p = handlePhotoUpload($field, $sub);
    return $p ? 'assets/uploads/' . $p : null;
}

$SECTIONS = array('about'=>'About', 'programs'=>'Programs', 'achievements'=>'Achievements', 'gallery'=>'Gallery', 'events'=>'Events',
                  'fees'=>'Fees', 'timings'=>'Timings', 'rules'=>'Rules', 'shop'=>'Shop', 'notices'=>'Notice board', 'committee'=>'Committee', 'contact'=>'Contact');
$TABS = array('texts'=>array('Texts & photo','fonts'), 'sections'=>array('Sections','toggles'), 'programs'=>array('Programs','trophy'),
              'fees'=>array('Fees','currency-rupee'), 'timings'=>array('Timings','clock'), 'rules'=>array('Rules','list-ol'),
              'contact'=>array('Contact','telephone'), 'share'=>array('Link preview','share'));
$tab = isset($TABS[$_GET['tab'] ?? '']) ? $_GET['tab'] : 'texts';
$flash = ''; $flashType = 'ok';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!verifyCsrf()) { $flash = 'Page expired. Please try again.'; $flashType = 'err'; }
    else {
        $do = $_POST['do'] ?? '';
        $T = function($k) { return trim($_POST[$k] ?? ''); };
        try {
            switch ($do) {
            case 'texts':
                foreach (array('hero_title','hero_subtitle','about_points','join_options','footer_text') as $k) { ss_save($k, $T($k)); ss_save($k . '_ml', $T($k . '_ml')); }
                foreach ($SECTIONS as $k => $l) { ss_save('pub_title_' . $k, $T('pub_title_' . $k)); ss_save('pub_title_' . $k . '_ml', $T('pub_title_' . $k . '_ml')); }
                if ($p = ss_photo('hero_photo')) ss_save('hero_photo', $p);
                if (!empty($_POST['hero_photo_clear'])) ss_save('hero_photo', '');
                $flash = 'Texts saved.'; break;
            case 'sections':
                foreach ($SECTIONS as $k => $l) ss_save('pub_show_' . $k, !empty($_POST['show'][$k]) ? '1' : '0');
                $flash = 'Sections saved.'; break;
            case 'contact':
                foreach (array('site_whatsapp','site_phone','site_map','social_instagram') as $k) ss_save($k, $T($k));
                ss_save('site_address', $T('site_address')); ss_save('site_address_ml', $T('site_address_ml'));
                $flash = 'Contact details saved.'; break;
            case 'share':
                ss_save('og_on', !empty($_POST['og_on']) ? '1' : '0');
                ss_save('og_title', $T('og_title')); ss_save('og_desc', $T('og_desc'));
                if ($p = ss_photo('og_image')) ss_save('og_image', $p);
                if (!empty($_POST['og_image_clear'])) ss_save('og_image', '');
                $flash = 'Link preview saved.'; break;

            case 'prog_save':
                $id = (int)($_POST['id'] ?? 0);
                $f = array($T('name'), $T('name_ml'), mb_substr($T('emoji'), 0, 4) ?: '🏆', $T('description'), $T('description_ml'), $T('suitable_for'),
                           $T('time_text'), $T('contact_person'), $T('reg_link'), !empty($_POST['is_active']) ? 1 : 0, (int)$T('sort_order'));
                if ($f[0] === '') { $flash = 'Please enter a name.'; $flashType = 'err'; break; }
                if ($id) db()->prepare("UPDATE club_activities SET name=?,name_ml=?,emoji=?,description=?,description_ml=?,suitable_for=?,time_text=?,contact_person=?,reg_link=?,is_active=?,sort_order=? WHERE id=?")->execute(array_merge($f, array($id)));
                else { db()->prepare("INSERT INTO club_activities(name,name_ml,emoji,description,description_ml,suitable_for,time_text,contact_person,reg_link,is_active,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?,?)")->execute($f); $id = (int)db()->lastInsertId(); }
                if ($p = ss_photo('photo', 'programs')) db()->prepare("UPDATE club_activities SET photo=? WHERE id=?")->execute(array($p, $id));
                if (!empty($_POST['photo_clear'])) db()->prepare("UPDATE club_activities SET photo=NULL WHERE id=?")->execute(array($id));
                $flash = 'Program saved.'; break;
            case 'prog_del':
                sudo_require();
                db()->prepare("DELETE FROM club_activities WHERE id=?")->execute(array((int)$_POST['id'])); $flash = 'Program deleted.'; break;

            case 'fee_save':
                sudo_require();   // money
                $id = (int)($_POST['id'] ?? 0);
                $f = array($T('name'), $T('price'), $T('duration'), $T('note'), !empty($_POST['popular']) ? 1 : 0, (int)$T('sort_order'), !empty($_POST['is_active']) ? 1 : 0);
                if ($f[0] === '' || $f[1] === '') { $flash = 'Please enter a name and a price.'; $flashType = 'err'; break; }
                if ($id) db()->prepare("UPDATE site_packages SET name=?,price=?,duration=?,note=?,popular=?,sort_order=?,is_active=? WHERE id=?")->execute(array_merge($f, array($id)));
                else db()->prepare("INSERT INTO site_packages(name,price,duration,note,popular,sort_order,is_active) VALUES(?,?,?,?,?,?,?)")->execute($f);
                $flash = 'Fee card saved.'; break;
            case 'fee_del':
                sudo_require();
                db()->prepare("DELETE FROM site_packages WHERE id=?")->execute(array((int)$_POST['id'])); $flash = 'Fee card deleted.'; break;

            case 'tm_save':
                $id = (int)($_POST['id'] ?? 0);
                $f = array($T('name'), $T('days'), $T('time_text'), ($_POST['icon'] ?? '') === 'moon' ? 'moon' : 'sun', (int)$T('sort_order'));
                if ($f[0] === '' || $f[2] === '') { $flash = 'Please enter a name and a time.'; $flashType = 'err'; break; }
                if ($id) db()->prepare("UPDATE site_timings SET name=?,days=?,time_text=?,icon=?,sort_order=? WHERE id=?")->execute(array_merge($f, array($id)));
                else db()->prepare("INSERT INTO site_timings(name,days,time_text,icon,sort_order) VALUES(?,?,?,?,?)")->execute($f);
                $flash = 'Timing saved.'; break;
            case 'tm_del':
                sudo_require();
                db()->prepare("DELETE FROM site_timings WHERE id=?")->execute(array((int)$_POST['id'])); $flash = 'Timing deleted.'; break;

            case 'ru_save':
                $id = (int)($_POST['id'] ?? 0);
                $f = array($T('title'), $T('body'), (int)$T('sort_order'));
                if ($f[0] === '' || $f[1] === '') { $flash = 'Please enter a title and at least one rule.'; $flashType = 'err'; break; }
                if ($id) db()->prepare("UPDATE site_rules SET title=?,body=?,sort_order=? WHERE id=?")->execute(array_merge($f, array($id)));
                else db()->prepare("INSERT INTO site_rules(title,body,sort_order) VALUES(?,?,?)")->execute($f);
                $flash = 'Rules saved.'; break;
            case 'ru_del':
                sudo_require();
                db()->prepare("DELETE FROM site_rules WHERE id=?")->execute(array((int)$_POST['id'])); $flash = 'Rules deleted.'; break;
            }
        } catch (Exception $e) { $flash = 'Could not save. Please try again.'; $flashType = 'err'; }
        if ($flashType === 'ok' && $flash !== '') { header('Location: ' . url('modules/site.php') . '?tab=' . $tab . '&ok=' . rawurlencode($flash)); exit; }
    }
}
if (isset($_GET['ok'])) $flash = mb_substr($_GET['ok'], 0, 80);

$pageTitle = 'Public Website';
require_once __DIR__ . '/../includes/header.php';
$V = function($k, $d = '') { return h(ss_get($k, $d)); };
$editId = (int)($_GET['edit'] ?? 0);
?>
<style>
.ws-tabs{display:flex;gap:.4rem;overflow-x:auto;padding-bottom:.3rem;margin-bottom:1rem;scrollbar-width:none}
.ws-tabs::-webkit-scrollbar{display:none}
.ws-tabs a{flex:0 0 auto;display:inline-flex;align-items:center;gap:.4rem;min-height:44px;padding:.4rem .95rem;border-radius:2rem;background:#fff;border:1px solid var(--line);color:var(--text-2);font-weight:700;font-size:.88rem;text-decoration:none}
.ws-tabs a.on{background:var(--dark);border-color:var(--dark);color:#fff}
.ws-card{background:#fff;border:1px solid var(--line);border-radius:1rem;padding:1.1rem;margin-bottom:1rem;box-shadow:0 4px 16px -10px rgba(11,16,51,.25)}
.ws-card h2{font-size:1rem;font-weight:800;text-transform:uppercase;margin:0 0 .8rem}
.ws-card .form-control,.ws-card .form-select{min-height:48px;font-size:1rem;border-radius:.7rem}
.ws-card textarea.form-control{min-height:110px}
.ws-hint{font-size:.82rem;color:var(--text-3)}
.ws-ml{font-family:var(--font)}
.ws-row{display:flex;align-items:center;gap:.8rem;padding:.75rem 0;border-top:1px solid var(--line)}
.ws-row:first-of-type{border-top:0}
.ws-row .ws-th{width:56px;height:56px;border-radius:.8rem;object-fit:cover;flex:0 0 56px;background:var(--light);display:flex;align-items:center;justify-content:center;font-size:1.6rem}
.ws-row .ws-tx{flex:1;min-width:0}
.ws-row .ws-tx b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ws-row .ws-tx small{color:var(--text-3)}
.ws-acts{display:flex;gap:.35rem}
.ws-acts .btn{min-width:44px;padding:.3rem .6rem}
.ws-sw .form-check{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.75rem 0;margin:0;border-top:1px solid var(--line)}
.ws-sw .form-check:first-child{border-top:0}
.ws-sw .form-check-input{width:3rem;height:1.6rem;margin:0;float:none;cursor:pointer}
.ws-sw .form-check-label{font-weight:600}
.ws-off{opacity:.55}
.ws-prev{max-width:240px;border-radius:.8rem;border:1px solid var(--line)}
.ws-og{border:1px solid var(--line);border-radius:.8rem;overflow:hidden;max-width:420px;background:#f7f8fc}
.ws-og img{width:100%;aspect-ratio:1.91/1;object-fit:cover;display:block;background:#0B1033}
.ws-og div{padding:.6rem .8rem}
.ws-og b{display:block}.ws-og small{color:var(--text-3)}
</style>

<section class="section">
  <div class="d-flex align-items-center justify-content-between gap-2 mb-2 flex-wrap">
    <h1 class="h-app m-0"><i class="bi bi-globe2" aria-hidden="true"></i> Public Website</h1>
    <a class="btn btn-outline-dark btn-sm" href="<?= url('index.php') ?>" target="_blank" rel="noopener"><i class="bi bi-box-arrow-up-right" aria-hidden="true"></i> View site</a>
  </div>
  <nav class="ws-tabs" aria-label="Website settings">
    <?php foreach($TABS as $k => $tb): ?><a href="?tab=<?= $k ?>" class="<?= $tab === $k ? 'on' : '' ?>"<?= $tab === $k ? ' aria-current="page"' : '' ?>><i class="bi bi-<?= $tb[1] ?>" aria-hidden="true"></i><?= h($tb[0]) ?></a><?php endforeach; ?>
  </nav>
  <?php if($flash): ?><div class="alert alert-<?= $flashType === 'ok' ? 'ok' : 'err' ?>" role="<?= $flashType === 'ok' ? 'status' : 'alert' ?>"><?= h($flash) ?></div><?php endif; ?>

<?php if($tab === 'texts'): $hp = ss_get('hero_photo'); ?>
  <form method="post" enctype="multipart/form-data">
    <?= csrfField() ?><input type="hidden" name="do" value="texts">
    <div class="ws-card">
      <h2>Top of the page</h2>
      <label class="form-label" for="hero_photo">Main photo</label>
      <?php if($hp): ?><div class="mb-2"><img class="ws-prev" src="<?= h(url($hp)) ?>" alt="Current main photo" width="240" height="150" loading="lazy">
        <div class="form-check mt-1"><input class="form-check-input" type="checkbox" name="hero_photo_clear" value="1" id="hpc"><label class="form-check-label" for="hpc">Remove this photo</label></div></div><?php endif; ?>
      <input class="form-control mb-1" type="file" name="hero_photo" id="hero_photo" accept="image/*">
      <p class="ws-hint mb-3">A wide photo looks best. It is made smaller automatically (max 1200px). Without a photo the first gallery photo, or the logo, is shown.</p>
      <div class="row g-2">
        <div class="col-md-6"><label class="form-label" for="hero_title">Big title (English)</label><input class="form-control" name="hero_title" id="hero_title" value="<?= $V('hero_title') ?>" placeholder="<?= h(setting('CLUB_NAME','')) ?>"></div>
        <div class="col-md-6"><label class="form-label" for="hero_title_ml">Big title (Malayalam)</label><input class="form-control ws-ml" name="hero_title_ml" id="hero_title_ml" lang="ml" value="<?= $V('hero_title_ml') ?>"></div>
        <div class="col-md-6"><label class="form-label" for="hero_subtitle">One line under the title (English)</label><input class="form-control" name="hero_subtitle" id="hero_subtitle" value="<?= $V('hero_subtitle') ?>" placeholder="<?= h(setting('CLUB_TAGLINE','')) ?>"></div>
        <div class="col-md-6"><label class="form-label" for="hero_subtitle_ml">One line (Malayalam)</label><input class="form-control ws-ml" name="hero_subtitle_ml" id="hero_subtitle_ml" lang="ml" value="<?= $V('hero_subtitle_ml') ?>"></div>
      </div>
    </div>
    <div class="ws-card">
      <h2>About the club</h2>
      <p class="ws-hint">One point per line. Each line becomes a box with a tick.</p>
      <div class="row g-2">
        <div class="col-md-6"><label class="form-label" for="about_points">Points (English)</label><textarea class="form-control" name="about_points" id="about_points" rows="5"><?= $V('about_points') ?></textarea></div>
        <div class="col-md-6"><label class="form-label" for="about_points_ml">Points (Malayalam)</label><textarea class="form-control ws-ml" name="about_points_ml" id="about_points_ml" lang="ml" rows="5"><?= $V('about_points_ml') ?></textarea></div>
      </div>
    </div>
    <div class="ws-card">
      <h2>"Join the Club" form</h2>
      <p class="ws-hint">Choices people can tap, separated by commas. Example: Football, Cricket, Arts, Blood donor</p>
      <div class="row g-2">
        <div class="col-md-6"><label class="form-label" for="join_options">Choices (English)</label><input class="form-control" name="join_options" id="join_options" value="<?= $V('join_options') ?>" placeholder="Football,Cricket,Arts,Blood donor,Volunteer"></div>
        <div class="col-md-6"><label class="form-label" for="join_options_ml">Choices (Malayalam)</label><input class="form-control ws-ml" name="join_options_ml" id="join_options_ml" lang="ml" value="<?= $V('join_options_ml') ?>"></div>
      </div>
    </div>
    <div class="ws-card">
      <h2>Section headings</h2>
      <p class="ws-hint">Leave empty to use the standard heading.</p>
      <?php foreach($SECTIONS as $k => $l): ?>
      <div class="row g-2 mb-1">
        <div class="col-6"><label class="form-label small" for="pt_<?= $k ?>"><?= h($l) ?> (English)</label><input class="form-control" name="pub_title_<?= $k ?>" id="pt_<?= $k ?>" value="<?= $V('pub_title_' . $k) ?>" placeholder="<?= h(lang_strings()['en']['sec_' . $k] ?? $l) ?>"></div>
        <div class="col-6"><label class="form-label small" for="ptm_<?= $k ?>"><?= h($l) ?> (Malayalam)</label><input class="form-control ws-ml" name="pub_title_<?= $k ?>_ml" id="ptm_<?= $k ?>" lang="ml" value="<?= $V('pub_title_' . $k . '_ml') ?>" placeholder="<?= h(lang_strings()['ml']['sec_' . $k] ?? '') ?>"></div>
      </div>
      <?php endforeach; ?>
    </div>
    <div class="ws-card">
      <h2>Footer</h2>
      <div class="row g-2">
        <div class="col-md-6"><label class="form-label" for="footer_text">Extra footer text (English)</label><textarea class="form-control" name="footer_text" id="footer_text" rows="2"><?= $V('footer_text') ?></textarea></div>
        <div class="col-md-6"><label class="form-label" for="footer_text_ml">Extra footer text (Malayalam)</label><textarea class="form-control ws-ml" name="footer_text_ml" id="footer_text_ml" lang="ml" rows="2"><?= $V('footer_text_ml') ?></textarea></div>
      </div>
    </div>
    <button type="submit" class="btn btn-brand btn-lg w-100"><i class="bi bi-check2" aria-hidden="true"></i> Save texts</button>
  </form>

<?php elseif($tab === 'sections'):
  $old = array('about'=>'home_about_show','programs'=>'home_activities_show','achievements'=>'home_achievements_show','gallery'=>'home_gallery_show','events'=>'home_events_show','notices'=>'home_notices_show','committee'=>'home_committee_show'); ?>
  <form method="post" class="ws-card ws-sw">
    <?= csrfField() ?><input type="hidden" name="do" value="sections">
    <h2>Show on the public page</h2>
    <?php foreach($SECTIONS as $k => $l): $v = ss_get('pub_show_' . $k, ''); if ($v === '') $v = isset($old[$k]) ? ss_get($old[$k], '1') : '1'; ?>
    <div class="form-check form-switch"><label class="form-check-label" for="sw_<?= $k ?>"><?= h($l) ?></label><input class="form-check-input" type="checkbox" role="switch" name="show[<?= $k ?>]" value="1" id="sw_<?= $k ?>"<?= $v !== '0' ? ' checked' : '' ?>></div>
    <?php endforeach; ?>
    <p class="ws-hint mt-2 mb-3">A section with nothing in it (for example no fee cards) is hidden by itself.</p>
    <button type="submit" class="btn btn-brand btn-lg w-100">Save</button>
  </form>

<?php elseif($tab === 'programs'):
  $rows = db()->query("SELECT * FROM club_activities ORDER BY sort_order,id")->fetchAll();
  $e = array('id'=>0,'name'=>'','name_ml'=>'','emoji'=>'🏆','description'=>'','description_ml'=>'','suitable_for'=>'','time_text'=>'','contact_person'=>'','reg_link'=>'','is_active'=>1,'sort_order'=>count($rows),'photo'=>'');
  foreach ($rows as $r) if ((int)$r['id'] === $editId) $e = $r; ?>
  <div class="ws-card">
    <h2>Programs (<?= count($rows) ?>)</h2>
    <?php if(!$rows): ?><p class="ws-hint">No programs yet. Add one below.</p><?php endif; ?>
    <?php foreach($rows as $r): ?>
    <div class="ws-row<?= $r['is_active'] ? '' : ' ws-off' ?>">
      <?php if(!empty($r['photo'])): ?><img class="ws-th" src="<?= h(url($r['photo'])) ?>" alt="" width="56" height="56" loading="lazy"><?php else: ?><span class="ws-th" aria-hidden="true"><?= h($r['emoji']) ?></span><?php endif; ?>
      <div class="ws-tx"><b><?= h($r['name']) ?></b><small><?= h($r['time_text'] ?: ($r['is_active'] ? 'Shown' : 'Hidden')) ?></small></div>
      <div class="ws-acts">
        <a class="btn btn-outline-dark" href="?tab=programs&edit=<?= (int)$r['id'] ?>#form" aria-label="Edit <?= h($r['name']) ?>"><i class="bi bi-pencil" aria-hidden="true"></i></a>
        <form method="post" data-sudo data-confirm="Delete <?= h($r['name']) ?>?"><?= csrfField() ?><input type="hidden" name="do" value="prog_del"><input type="hidden" name="id" value="<?= (int)$r['id'] ?>"><button type="submit" class="btn btn-outline-danger" aria-label="Delete <?= h($r['name']) ?>"><i class="bi bi-trash" aria-hidden="true"></i></button></form>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
  <form method="post" enctype="multipart/form-data" class="ws-card" id="form">
    <?= csrfField() ?><input type="hidden" name="do" value="prog_save"><input type="hidden" name="id" value="<?= (int)$e['id'] ?>">
    <h2><?= $e['id'] ? 'Edit program' : 'Add a program' ?></h2>
    <div class="row g-2">
      <div class="col-9 col-md-5"><label class="form-label" for="pName">Name (English) *</label><input class="form-control" name="name" id="pName" value="<?= h($e['name']) ?>" required></div>
      <div class="col-3 col-md-2"><label class="form-label" for="pEmoji">Emoji</label><input class="form-control text-center" name="emoji" id="pEmoji" value="<?= h($e['emoji']) ?>" maxlength="4"></div>
      <div class="col-md-5"><label class="form-label" for="pNameMl">Name (Malayalam)</label><input class="form-control ws-ml" name="name_ml" id="pNameMl" lang="ml" value="<?= h($e['name_ml'] ?? '') ?>"></div>
      <div class="col-md-6"><label class="form-label" for="pDesc">Short text (English)</label><textarea class="form-control" name="description" id="pDesc" rows="3"><?= h($e['description']) ?></textarea></div>
      <div class="col-md-6"><label class="form-label" for="pDescMl">Short text (Malayalam)</label><textarea class="form-control ws-ml" name="description_ml" id="pDescMl" lang="ml" rows="3"><?= h($e['description_ml'] ?? '') ?></textarea></div>
      <div class="col-md-4"><label class="form-label" for="pSuit">Suitable for</label><input class="form-control" name="suitable_for" id="pSuit" value="<?= h($e['suitable_for'] ?? '') ?>" placeholder="Ages 8–18"></div>
      <div class="col-md-4"><label class="form-label" for="pTime">Time</label><input class="form-control" name="time_text" id="pTime" value="<?= h($e['time_text'] ?? '') ?>" placeholder="Sat & Sun, 6–8 am"></div>
      <div class="col-md-4"><label class="form-label" for="pCont">Trainer / contact</label><input class="form-control" name="contact_person" id="pCont" value="<?= h($e['contact_person'] ?? '') ?>" placeholder="Name, phone"></div>
      <div class="col-md-8"><label class="form-label" for="pLink">Booking link (optional)</label><input class="form-control" name="reg_link" id="pLink" type="url" value="<?= h($e['reg_link'] ?? '') ?>" placeholder="Empty = opens the Join the Club form"></div>
      <div class="col-md-4"><label class="form-label" for="pSort">Order</label><input class="form-control" name="sort_order" id="pSort" type="number" inputmode="numeric" value="<?= (int)$e['sort_order'] ?>"></div>
      <div class="col-12"><label class="form-label" for="pPhoto">Square photo</label>
        <?php if(!empty($e['photo'])): ?><div class="mb-2"><img class="ws-prev" src="<?= h(url($e['photo'])) ?>" alt="Current photo" width="120" height="120" loading="lazy" style="max-width:120px"><div class="form-check mt-1"><input class="form-check-input" type="checkbox" name="photo_clear" value="1" id="pPc"><label class="form-check-label" for="pPc">Remove photo</label></div></div><?php endif; ?>
        <input class="form-control" type="file" name="photo" id="pPhoto" accept="image/*"></div>
      <div class="col-12 ws-sw"><div class="form-check form-switch"><label class="form-check-label" for="pAct">Show on website</label><input class="form-check-input" type="checkbox" role="switch" name="is_active" value="1" id="pAct"<?= $e['is_active'] ? ' checked' : '' ?>></div></div>
    </div>
    <div class="d-grid gap-2 mt-2"><button type="submit" class="btn btn-brand btn-lg"><?= $e['id'] ? 'Save changes' : 'Add program' ?></button>
      <?php if($e['id']): ?><a class="btn btn-outline-secondary" href="?tab=programs">Cancel</a><?php endif; ?></div>
  </form>

<?php elseif($tab === 'fees'):
  $rows = db()->query("SELECT * FROM site_packages ORDER BY sort_order,id")->fetchAll();
  $e = array('id'=>0,'name'=>'','price'=>'','duration'=>'','note'=>'','popular'=>0,'sort_order'=>count($rows),'is_active'=>1);
  foreach ($rows as $r) if ((int)$r['id'] === $editId) $e = $r; ?>
  <div class="ws-card">
    <h2>Fee cards (<?= count($rows) ?>)</h2>
    <?php if(!$rows): ?><p class="ws-hint">No fee cards yet. Until you add one, the site shows Monthly ₹<?= h(setting('FEE_MONTHLY',100)) ?> and Annual ₹<?= h(setting('FEE_ANNUAL',1000)) ?> from Club Settings.</p><?php endif; ?>
    <?php foreach($rows as $r): ?>
    <div class="ws-row<?= $r['is_active'] ? '' : ' ws-off' ?>">
      <span class="ws-th" aria-hidden="true"><i class="bi bi-<?= $r['popular'] ? 'star-fill' : 'tag' ?>" style="color:var(--brand)"></i></span>
      <div class="ws-tx"><b><?= h($r['name']) ?> · <?= h($r['price']) ?></b><small><?= h($r['duration']) ?><?= $r['popular'] ? ' · Most popular' : '' ?></small></div>
      <div class="ws-acts">
        <a class="btn btn-outline-dark" href="?tab=fees&edit=<?= (int)$r['id'] ?>#form" aria-label="Edit <?= h($r['name']) ?>"><i class="bi bi-pencil" aria-hidden="true"></i></a>
        <form method="post" data-sudo data-confirm="Delete <?= h($r['name']) ?>?"><?= csrfField() ?><input type="hidden" name="do" value="fee_del"><input type="hidden" name="id" value="<?= (int)$r['id'] ?>"><button type="submit" class="btn btn-outline-danger" aria-label="Delete <?= h($r['name']) ?>"><i class="bi bi-trash" aria-hidden="true"></i></button></form>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
  <form method="post" class="ws-card" id="form" data-sudo>
    <?= csrfField() ?><input type="hidden" name="do" value="fee_save"><input type="hidden" name="id" value="<?= (int)$e['id'] ?>">
    <h2><?= $e['id'] ? 'Edit fee card' : 'Add a fee card' ?></h2>
    <p class="ws-hint">Price changes ask for your passkey.</p>
    <div class="row g-2">
      <div class="col-md-6"><label class="form-label" for="fName">Name *</label><input class="form-control" name="name" id="fName" value="<?= h($e['name']) ?>" placeholder="Monthly" required></div>
      <div class="col-6 col-md-3"><label class="form-label" for="fPrice">Price *</label><input class="form-control" name="price" id="fPrice" value="<?= h($e['price']) ?>" placeholder="₹150" required></div>
      <div class="col-6 col-md-3"><label class="form-label" for="fDur">Duration</label><input class="form-control" name="duration" id="fDur" value="<?= h($e['duration']) ?>" placeholder="per month"></div>
      <div class="col-md-9"><label class="form-label" for="fNote">Note</label><input class="form-control" name="note" id="fNote" value="<?= h($e['note']) ?>" placeholder="Full club access"></div>
      <div class="col-md-3"><label class="form-label" for="fSort">Order</label><input class="form-control" name="sort_order" id="fSort" type="number" inputmode="numeric" value="<?= (int)$e['sort_order'] ?>"></div>
      <div class="col-12 ws-sw">
        <div class="form-check form-switch"><label class="form-check-label" for="fPop">"Most popular" (red border)</label><input class="form-check-input" type="checkbox" role="switch" name="popular" value="1" id="fPop"<?= $e['popular'] ? ' checked' : '' ?>></div>
        <div class="form-check form-switch"><label class="form-check-label" for="fAct">Show on website</label><input class="form-check-input" type="checkbox" role="switch" name="is_active" value="1" id="fAct"<?= $e['is_active'] ? ' checked' : '' ?>></div>
      </div>
    </div>
    <div class="d-grid gap-2 mt-2"><button type="submit" class="btn btn-brand btn-lg"><?= $e['id'] ? 'Save changes' : 'Add fee card' ?></button>
      <?php if($e['id']): ?><a class="btn btn-outline-secondary" href="?tab=fees">Cancel</a><?php endif; ?></div>
  </form>

<?php elseif($tab === 'timings'):
  $rows = db()->query("SELECT * FROM site_timings ORDER BY sort_order,id")->fetchAll();
  $e = array('id'=>0,'name'=>'','days'=>'','time_text'=>'','icon'=>'sun','sort_order'=>count($rows));
  foreach ($rows as $r) if ((int)$r['id'] === $editId) $e = $r; ?>
  <div class="ws-card">
    <h2>Timings (<?= count($rows) ?>)</h2>
    <?php if(!$rows): ?><p class="ws-hint">No timings yet.</p><?php endif; ?>
    <?php foreach($rows as $r): ?>
    <div class="ws-row">
      <span class="ws-th" aria-hidden="true"><i class="bi bi-<?= $r['icon'] === 'moon' ? 'moon-stars-fill' : 'sun-fill' ?>" style="color:<?= $r['icon'] === 'moon' ? 'var(--accent)' : '#B45309' ?>"></i></span>
      <div class="ws-tx"><b><?= h($r['name']) ?> · <?= h($r['time_text']) ?></b><small><?= h($r['days']) ?></small></div>
      <div class="ws-acts">
        <a class="btn btn-outline-dark" href="?tab=timings&edit=<?= (int)$r['id'] ?>#form" aria-label="Edit <?= h($r['name']) ?>"><i class="bi bi-pencil" aria-hidden="true"></i></a>
        <form method="post" data-sudo data-confirm="Delete <?= h($r['name']) ?>?"><?= csrfField() ?><input type="hidden" name="do" value="tm_del"><input type="hidden" name="id" value="<?= (int)$r['id'] ?>"><button type="submit" class="btn btn-outline-danger" aria-label="Delete <?= h($r['name']) ?>"><i class="bi bi-trash" aria-hidden="true"></i></button></form>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
  <form method="post" class="ws-card" id="form">
    <?= csrfField() ?><input type="hidden" name="do" value="tm_save"><input type="hidden" name="id" value="<?= (int)$e['id'] ?>">
    <h2><?= $e['id'] ? 'Edit timing' : 'Add a timing' ?></h2>
    <div class="row g-2">
      <div class="col-md-6"><label class="form-label" for="tName">Name *</label><input class="form-control" name="name" id="tName" value="<?= h($e['name']) ?>" placeholder="Morning football" required></div>
      <div class="col-md-6"><label class="form-label" for="tDays">Days</label><input class="form-control" name="days" id="tDays" value="<?= h($e['days']) ?>" placeholder="Mon – Sat"></div>
      <div class="col-6 col-md-4"><label class="form-label" for="tTime">Time *</label><input class="form-control" name="time_text" id="tTime" value="<?= h($e['time_text']) ?>" placeholder="6:00 – 8:00 am" required></div>
      <div class="col-6 col-md-4"><label class="form-label" for="tIcon">Icon</label><select class="form-select" name="icon" id="tIcon"><option value="sun"<?= $e['icon'] !== 'moon' ? ' selected' : '' ?>>☀️ Day</option><option value="moon"<?= $e['icon'] === 'moon' ? ' selected' : '' ?>>🌙 Evening</option></select></div>
      <div class="col-md-4"><label class="form-label" for="tSort">Order</label><input class="form-control" name="sort_order" id="tSort" type="number" inputmode="numeric" value="<?= (int)$e['sort_order'] ?>"></div>
    </div>
    <div class="d-grid gap-2 mt-3"><button type="submit" class="btn btn-brand btn-lg"><?= $e['id'] ? 'Save changes' : 'Add timing' ?></button>
      <?php if($e['id']): ?><a class="btn btn-outline-secondary" href="?tab=timings">Cancel</a><?php endif; ?></div>
  </form>

<?php elseif($tab === 'rules'):
  $rows = db()->query("SELECT * FROM site_rules ORDER BY sort_order,id")->fetchAll();
  $e = array('id'=>0,'title'=>'','body'=>'','sort_order'=>count($rows));
  foreach ($rows as $r) if ((int)$r['id'] === $editId) $e = $r; ?>
  <div class="ws-card">
    <h2>Rule boxes (<?= count($rows) ?>)</h2>
    <?php if(!$rows): ?><p class="ws-hint">No rules yet.</p><?php endif; ?>
    <?php foreach($rows as $r): $n = count(array_filter(array_map('trim', explode("\n", $r['body'])))); ?>
    <div class="ws-row">
      <span class="ws-th" aria-hidden="true"><i class="bi bi-list-ol"></i></span>
      <div class="ws-tx"><b><?= h($r['title']) ?></b><small><?= $n ?> rule<?= $n === 1 ? '' : 's' ?></small></div>
      <div class="ws-acts">
        <a class="btn btn-outline-dark" href="?tab=rules&edit=<?= (int)$r['id'] ?>#form" aria-label="Edit <?= h($r['title']) ?>"><i class="bi bi-pencil" aria-hidden="true"></i></a>
        <form method="post" data-sudo data-confirm="Delete <?= h($r['title']) ?>?"><?= csrfField() ?><input type="hidden" name="do" value="ru_del"><input type="hidden" name="id" value="<?= (int)$r['id'] ?>"><button type="submit" class="btn btn-outline-danger" aria-label="Delete <?= h($r['title']) ?>"><i class="bi bi-trash" aria-hidden="true"></i></button></form>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
  <form method="post" class="ws-card" id="form">
    <?= csrfField() ?><input type="hidden" name="do" value="ru_save"><input type="hidden" name="id" value="<?= (int)$e['id'] ?>">
    <h2><?= $e['id'] ? 'Edit rules' : 'Add a rule box' ?></h2>
    <div class="row g-2">
      <div class="col-md-9"><label class="form-label" for="rTitle">Title *</label><input class="form-control" name="title" id="rTitle" value="<?= h($e['title']) ?>" placeholder="Ground rules" required></div>
      <div class="col-md-3"><label class="form-label" for="rSort">Order</label><input class="form-control" name="sort_order" id="rSort" type="number" inputmode="numeric" value="<?= (int)$e['sort_order'] ?>"></div>
      <div class="col-12"><label class="form-label" for="rBody">Rules * <span class="ws-hint">(one per line — they are numbered 01, 02 …)</span></label><textarea class="form-control" name="body" id="rBody" rows="6" required><?= h($e['body']) ?></textarea></div>
    </div>
    <div class="d-grid gap-2 mt-3"><button type="submit" class="btn btn-brand btn-lg"><?= $e['id'] ? 'Save changes' : 'Add rule box' ?></button>
      <?php if($e['id']): ?><a class="btn btn-outline-secondary" href="?tab=rules">Cancel</a><?php endif; ?></div>
  </form>

<?php elseif($tab === 'contact'): ?>
  <form method="post" class="ws-card">
    <?= csrfField() ?><input type="hidden" name="do" value="contact">
    <h2>Contact details</h2>
    <div class="row g-2">
      <div class="col-md-6"><label class="form-label" for="cWa">WhatsApp number</label><input class="form-control" name="site_whatsapp" id="cWa" type="tel" inputmode="tel" value="<?= $V('site_whatsapp') ?>" placeholder="<?= h(setting('CLUB_PHONE','')) ?>">
        <p class="ws-hint mb-0">Used by the WhatsApp buttons and the Join form. Empty = club phone.</p></div>
      <div class="col-md-6"><label class="form-label" for="cPh">Phone number for "Call"</label><input class="form-control" name="site_phone" id="cPh" type="tel" inputmode="tel" value="<?= $V('site_phone') ?>" placeholder="<?= h(setting('CLUB_PHONE','')) ?>"></div>
      <div class="col-md-6"><label class="form-label" for="cAd">Address (English)</label><textarea class="form-control" name="site_address" id="cAd" rows="3"><?= $V('site_address') ?></textarea></div>
      <div class="col-md-6"><label class="form-label" for="cAdM">Address (Malayalam)</label><textarea class="form-control ws-ml" name="site_address_ml" id="cAdM" lang="ml" rows="3"><?= $V('site_address_ml') ?></textarea></div>
      <div class="col-12"><label class="form-label" for="cMap">Google Maps link</label><input class="form-control" name="site_map" id="cMap" type="url" value="<?= $V('site_map') ?>" placeholder="https://maps.app.goo.gl/…  or  https://www.google.com/maps/embed?pb=…">
        <p class="ws-hint mb-0">A normal link shows an "Open in Google Maps" button. An <b>embed</b> link (Google Maps → Share → Embed a map → copy only the src address) shows the map on the page.</p></div>
      <div class="col-12"><label class="form-label" for="cIg">Instagram link</label><input class="form-control" name="social_instagram" id="cIg" type="url" value="<?= $V('social_instagram') ?>" placeholder="https://instagram.com/yourclub"></div>
    </div>
    <button type="submit" class="btn btn-brand btn-lg w-100 mt-3">Save contact details</button>
  </form>

<?php elseif($tab === 'share'): $ogi = ss_get('og_image'); $ogOn = ss_get('og_on', '1') === '1'; ?>
  <form method="post" enctype="multipart/form-data" class="ws-card">
    <?= csrfField() ?><input type="hidden" name="do" value="share">
    <h2>Link preview (WhatsApp, Facebook)</h2>
    <p class="ws-hint">When someone shares the website link, WhatsApp shows this photo, title and text.</p>
    <div class="ws-sw mb-2"><div class="form-check form-switch"><label class="form-check-label" for="ogOn">Show link preview</label><input class="form-check-input" type="checkbox" role="switch" name="og_on" value="1" id="ogOn"<?= $ogOn ? ' checked' : '' ?>></div></div>
    <div class="row g-2">
      <div class="col-12"><label class="form-label" for="ogT">Title</label><input class="form-control" name="og_title" id="ogT" maxlength="90" value="<?= $V('og_title') ?>" placeholder="<?= h(setting('CLUB_NAME','') . ' · ' . setting('CLUB_PLACE','')) ?>"></div>
      <div class="col-12"><label class="form-label" for="ogD">Short text</label><textarea class="form-control" name="og_desc" id="ogD" rows="2" maxlength="200" placeholder="<?= h(setting('CLUB_TAGLINE','')) ?>"><?= $V('og_desc') ?></textarea></div>
      <div class="col-12"><label class="form-label" for="ogI">Photo</label>
        <?php if($ogi): ?><div class="form-check mb-1"><input class="form-check-input" type="checkbox" name="og_image_clear" value="1" id="ogIc"><label class="form-check-label" for="ogIc">Remove photo (use the club logo)</label></div><?php endif; ?>
        <input class="form-control" type="file" name="og_image" id="ogI" accept="image/jpeg,image/png"><p class="ws-hint mb-0">Best size: 1200 × 630, JPG.</p></div>
    </div>
    <button type="submit" class="btn btn-brand btn-lg w-100 mt-3">Save link preview</button>
  </form>
  <div class="ws-card"><h2>Preview</h2>
    <div class="ws-og"><img src="<?= h(site_img_url($ogi ?: 'assets/icons/app/icon-512.png')) ?>" alt="" width="420" height="220" loading="lazy">
      <div><b><?= h(ss_get('og_title', setting('CLUB_NAME','') . ' · ' . setting('CLUB_PLACE',''))) ?></b><small><?= h(ss_get('og_desc', setting('CLUB_TAGLINE',''))) ?></small><br><small><?= h(preg_replace('#^https?://#', '', rtrim(SITE_URL, '/'))) ?></small></div></div>
    <?php if(!$ogOn): ?><p class="ws-hint mt-2 mb-0">Link preview is switched off.</p><?php endif; ?>
  </div>
<?php endif; ?>
</section>
<?php require_once __DIR__ . '/../includes/footer.php'; ?>
