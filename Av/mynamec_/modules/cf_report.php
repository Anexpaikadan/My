<?php
require_once __DIR__ . '/../includes/config.php';
$me = currentUser();

// Not logged in → send to login (new tab may not carry session otherwise)
if (!$me) {
  header('Location: '.url('index.php'));
  exit;
}

// Allow finance admins AND general admins (president/admin/etc. via isAdminRole)
$canReport = isFinanceAdmin($me['role']) || isAdminRole($me['role']);
if (!$canReport) {
  http_response_code(403);
  echo '<div style="font-family:sans-serif;padding:40px;text-align:center;color:#333">'
     . '<h2>🔒 Access Restricted</h2>'
     . '<p>This funding report is only available to club admins.</p>'
     . '<p style="color:#666666;font-size:.85rem">Your role: '.h($me['role']).'</p>'
     . '<a href="'.url('modules/crowdfund.php').'" style="color:#0F766E">← Back to Crowd Funding</a></div>';
  exit;
}

$cid = (int)($_GET['id'] ?? 0);
$camp = db()->prepare("SELECT * FROM cf_campaigns WHERE id=?"); $camp->execute([$cid]); $camp = $camp->fetch();
if (!$camp) { exit('Campaign not found.'); }

$dons = db()->prepare("SELECT * FROM cf_donations WHERE campaign_id=? AND status='verified' ORDER BY amount DESC, donated_at ASC");
$dons->execute([$cid]); $dons = $dons->fetchAll();

$CLUB  = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$PLACE = setting('CLUB_PLACE','Vettikkattiri');
$LOGO  = defined('LOGO_URL') ? LOGO_URL : '';
$total = 0; foreach($dons as $d) $total += $d['amount'];
$pct = $camp['target_amount']>0 ? min(100,round(($total/$camp['target_amount'])*100)) : 0;
function rmoney($n){ return '₹'.number_format($n,2); }
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Funding Report — <?= h($camp['title']) ?></title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Segoe UI',Arial,sans-serif;color:#1a2238;background:#e9edf4;padding:18px}
  .sheet{max-width:760px;margin:0 auto;background:#fff;border-radius:10px;box-shadow:0 6px 30px rgba(0,0,0,.15);position:relative;overflow:hidden}
  /* Watermark */
  .wm{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:0;opacity:.06}
  .wm img{width:62%;max-width:420px;transform:rotate(-18deg)}
  .wm-text{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:0;opacity:.05;font-size:3.2rem;font-weight:900;color:#10201F;transform:rotate(-18deg);letter-spacing:.1em;text-align:center}
  .content{position:relative;z-index:1;padding:30px 34px 40px}
  /* Header */
  .rhead{display:flex;align-items:center;gap:16px;border-bottom:3px solid #0F766E;padding-bottom:16px;margin-bottom:6px}
  .rhead img{width:62px;height:62px;border-radius:50%;object-fit:cover;border:2px solid #c8922a}
  .rhead h1{font-size:1.32rem;color:#10201F;line-height:1.2}
  .rhead .sub{font-size:.8rem;color:#5a6680;margin-top:2px}
  .rtag{display:inline-block;background:#0F766E;color:#fff;font-size:.66rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;padding:3px 12px;border-radius:20px;margin:14px 0 4px}
  .ctitle{font-size:1.5rem;color:#10201F;font-weight:800;margin-bottom:2px}
  .cmeta{font-size:.82rem;color:#5a6680;margin-bottom:18px}
  /* Summary */
  .sumgrid{display:flex;gap:12px;margin-bottom:22px;flex-wrap:wrap}
  .sumbox{flex:1;min-width:120px;border:1px solid #E2E8E7;border-radius:10px;padding:12px 14px;background:#f8f9ff}
  .sumbox .l{font-size:.66rem;text-transform:uppercase;letter-spacing:.06em;color:#5f6880;font-weight:700}
  .sumbox .v{font-size:1.3rem;font-weight:800;color:#10201F;margin-top:3px}
  .sumbox.green .v{color:#1b5e20}.sumbox.blue .v{color:#0F766E}.sumbox.gold .v{color:#c8922a}
  .progress{height:10px;background:#E2E8E7;border-radius:6px;overflow:hidden;margin-bottom:24px}
  .progress span{display:block;height:100%;background:linear-gradient(90deg,#1b5e20,#4caf50);border-radius:6px}
  /* Table */
  h3.sec{font-size:.95rem;color:#10201F;margin-bottom:10px;border-left:4px solid #c8922a;padding-left:8px}
  table{width:100%;border-collapse:collapse;font-size:.82rem}
  th{background:#10201F;color:#fff;text-align:left;padding:8px 10px;font-size:.72rem;letter-spacing:.04em}
  th.r,td.r{text-align:right}
  td{padding:8px 10px;border-bottom:1px solid #eef1f6}
  tr:nth-child(even) td{background:#fafbfe}
  .rank{font-weight:800;color:#c8922a}
  .top1 td{background:#fffaf0 !important}
  tfoot td{font-weight:800;color:#10201F;border-top:2px solid #0F766E;background:#f0f4fc}
  /* Footer */
  .rfoot{margin-top:26px;border-top:1px solid #E2E8E7;padding-top:14px;font-size:.72rem;color:#5f6880;display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px}
  .stamp{margin-top:10px;font-size:.7rem;color:#aab2c4;font-style:italic}
  /* Print button */
  .pbar{max-width:760px;margin:0 auto 14px;display:flex;gap:10px;justify-content:flex-end}
  .pbtn{background:#0F766E;color:#fff;border:none;border-radius:8px;padding:10px 18px;font-size:.85rem;font-weight:700;cursor:pointer}
  .pbtn.alt{background:#5a6680}
  @media print{
    body{background:#fff;padding:0}
    .pbar{display:none}
    .sheet{box-shadow:none;border-radius:0;max-width:100%}
    @page{margin:12mm}
  }
</style>
</head>
<body>
  <div class="pbar">
    <button class="pbtn" onclick="window.print()">📄 Save as PDF / Print</button>
    <button class="pbtn alt" onclick="history.back()">← Back</button>
  </div>

  <div class="sheet">
    <!-- Watermark -->
    <?php if($LOGO): ?><div class="wm"><img src="<?= h($LOGO) ?>" alt=""></div><?php endif; ?>
    <div class="wm-text"><?= h($CLUB) ?></div>

    <div class="content">
      <!-- Header -->
      <div class="rhead">
        <?php if($LOGO): ?><img src="<?= h($LOGO) ?>" alt="logo"><?php endif; ?>
        <div>
          <h1><?= h($CLUB) ?></h1>
          <div class="sub"><?= h($PLACE) ?>, Kerala · Official Funding Report</div>
        </div>
      </div>

      <div class="rtag">Crowd Funding Report</div>
      <div class="ctitle"><?= h($camp['title']) ?></div>
      <div class="cmeta">
        Category: <?= h(ucfirst($camp['category'])) ?> ·
        Status: <?= h(ucfirst($camp['status'])) ?> ·
        Report generated: <?= date('d M Y, g:i A') ?>
      </div>

      <!-- Summary -->
      <div class="sumgrid">
        <div class="sumbox green"><div class="l">Total Raised</div><div class="v"><?= rmoney($total) ?></div></div>
        <div class="sumbox blue"><div class="l">Target</div><div class="v"><?= rmoney($camp['target_amount']) ?></div></div>
        <div class="sumbox gold"><div class="l">Donors</div><div class="v"><?= count($dons) ?></div></div>
        <div class="sumbox"><div class="l">Funded</div><div class="v"><?= $pct ?>%</div></div>
      </div>
      <div class="progress"><span style="width:<?= $pct ?>%"></span></div>

      <!-- Donor table -->
      <h3 class="sec">🏆 Verified Donors (highest first)</h3>
      <?php if(empty($dons)): ?>
      <p style="font-size:.85rem;color:#5f6880">No verified donations yet.</p>
      <?php else: ?>
      <table>
        <thead>
          <tr><th style="width:42px">#</th><th>Donor</th><th>Date</th><th>Method</th><th class="r">Amount</th></tr>
        </thead>
        <tbody>
          <?php foreach($dons as $i=>$d): ?>
          <tr class="<?= $i===0?'top1':'' ?>">
            <td class="rank"><?= $i===0?'🥇':($i===1?'🥈':($i===2?'🥉':($i+1))) ?></td>
            <td><?= h($d['donor_name']) ?><?= $d['donor_phone']?' <span style="color:#aab2c4">· '.h($d['donor_phone']).'</span>':'' ?></td>
            <td><?= date('d M Y', strtotime($d['donated_at'])) ?></td>
            <td><?= h(strtoupper($d['payment_method'])) ?></td>
            <td class="r"><?= rmoney($d['amount']) ?></td>
          </tr>
          <?php endforeach; ?>
        </tbody>
        <tfoot>
          <tr><td colspan="4">TOTAL</td><td class="r"><?= rmoney($total) ?></td></tr>
        </tfoot>
      </table>
      <?php endif; ?>

      <!-- Footer -->
      <div class="rfoot">
        <span><?= h($CLUB) ?> · <?= h($PLACE) ?></span>
        <span><?= rtrim(SITE_URL,'/') ?></span>
      </div>
      <div class="stamp">This is a system-generated report from the <?= h($CLUB) ?> website. Figures reflect admin-verified donations only.</div>
    </div>
  </div>
</body>
</html>
