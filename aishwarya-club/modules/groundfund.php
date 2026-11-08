<?php
require_once __DIR__ . '/../includes/config.php';
$pageOG = [
  'title' => '🏟️ Ground Fund — Aishwarya Arts & Sports Club',
  'desc'  => 'How our members funded the club ground — AASC, Vettikkattiri, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/groundfund.php',
];
requireLogin();
$me = currentUser();
$isAdmin = isAdminRole($me['role']) || isFinanceAdmin($me['role']) || isModuleAdmin('groundfund', $me);
$uid = (int)$me['id'];
$CLUB  = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$PLACE = setting('CLUB_PLACE','Vettikkattiri');
$LOGO  = defined('LOGO_URL') ? LOGO_URL : '';
$pageTitle = 'Ground Fund — '.$CLUB;
$SELF = url('modules/groundfund.php');

try {
  db()->exec("CREATE TABLE IF NOT EXISTS gf_pledges (id INT AUTO_INCREMENT PRIMARY KEY, member_id INT NOT NULL, pledge_amount DECIMAL(12,2) DEFAULT 0, note VARCHAR(255) DEFAULT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY uq_member (member_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
  db()->exec("CREATE TABLE IF NOT EXISTS gf_payments (id INT AUTO_INCREMENT PRIMARY KEY, member_id INT NOT NULL, amount DECIMAL(12,2) NOT NULL, pay_date DATE DEFAULT NULL, method VARCHAR(40) DEFAULT 'cash', note VARCHAR(255) DEFAULT NULL, added_by INT DEFAULT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, INDEX idx_mem (member_id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
  db()->exec("CREATE TABLE IF NOT EXISTS gf_expenses (id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(255) NOT NULL, amount DECIMAL(12,2) NOT NULL, spent_date DATE DEFAULT NULL, note TEXT DEFAULT NULL, added_by INT DEFAULT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4");
} catch (Exception $e) {}

// ── AJAX (admin) ──
if (isset($_POST['ajax'])) {
  header('Content-Type: application/json');
  if (!$isAdmin) { echo json_encode(['ok'=>false,'msg'=>'Not allowed']); exit; }
  require_once __DIR__ . '/../includes/sudo.php'; sudo_require();   // every action here changes money
  $a = $_POST['ajax'];
  try {
    if ($a==='add_payment') {
      $mid=(int)$_POST['member_id']; $amt=(float)$_POST['amount'];
      $pd=$_POST['pay_date']?:date('Y-m-d'); $mth=trim($_POST['method']??'cash'); $note=trim($_POST['note']??'');
      if(!$mid||$amt<=0){echo json_encode(['ok'=>false,'msg'=>'Enter amount']);exit;}
      db()->prepare("INSERT INTO gf_payments(member_id,amount,pay_date,method,note,added_by) VALUES(?,?,?,?,?,?)")->execute([$mid,$amt,$pd,$mth,$note,$uid]);
      echo json_encode(['ok'=>true,'msg'=>'✅ Payment of ₹'.number_format($amt).' added']); exit;
    }
    if ($a==='set_pledge') {
      $mid=(int)$_POST['member_id']; $amt=(float)$_POST['pledge_amount'];
      db()->prepare("INSERT INTO gf_pledges(member_id,pledge_amount) VALUES(?,?) ON DUPLICATE KEY UPDATE pledge_amount=VALUES(pledge_amount)")->execute([$mid,$amt]);
      echo json_encode(['ok'=>true,'msg'=>'✅ Pledge saved']); exit;
    }
    if ($a==='add_expense') {
      $t=trim($_POST['title']); $amt=(float)$_POST['amount']; $sd=$_POST['spent_date']?:date('Y-m-d'); $note=trim($_POST['note']??'');
      if(!$t||$amt<=0){echo json_encode(['ok'=>false,'msg'=>'Fill title & amount']);exit;}
      db()->prepare("INSERT INTO gf_expenses(title,amount,spent_date,note,added_by) VALUES(?,?,?,?,?)")->execute([$t,$amt,$sd,$note,$uid]);
      echo json_encode(['ok'=>true,'msg'=>'✅ Expense added']); exit;
    }
    if ($a==='del_payment') { db()->prepare("DELETE FROM gf_payments WHERE id=?")->execute([(int)$_POST['pid']]); echo json_encode(['ok'=>true,'msg'=>'Removed']); exit; }
    if ($a==='del_expense') { db()->prepare("DELETE FROM gf_expenses WHERE id=?")->execute([(int)$_POST['eid']]); echo json_encode(['ok'=>true,'msg'=>'Removed']); exit; }
  } catch (Exception $e) { echo json_encode(['ok'=>false,'msg'=>'Error']); exit; }
  echo json_encode(['ok'=>false,'msg'=>'Unknown']); exit;
}

// ── Data ──
$rows = db()->query("
  SELECT u.id,u.name,u.profile_photo,u.role,u.whatsapp_number,u.blood_group,u.profession,u.skill,
         COALESCE(pl.pledge_amount,0) pledge, COALESCE(pp.paid,0) paid
  FROM users u
  LEFT JOIN gf_pledges pl ON pl.member_id=u.id
  LEFT JOIN (SELECT member_id,SUM(amount) paid FROM gf_payments GROUP BY member_id) pp ON pp.member_id=u.id
  WHERE u.status='active' ORDER BY paid DESC, u.name ASC
")->fetchAll();
$totalPledged=0;$totalPaid=0;
foreach($rows as $r){$totalPledged+=$r['pledge'];$totalPaid+=$r['paid'];}
$totalExpense=(float)db()->query("SELECT COALESCE(SUM(amount),0) FROM gf_expenses")->fetchColumn();
$fundBalance=$totalPaid-$totalExpense;
$expenses=db()->query("SELECT * FROM gf_expenses ORDER BY spent_date DESC, id DESC")->fetchAll();
// Expense summary
$expCount = count($expenses);
$expAvg = $expCount ? $totalExpense/$expCount : 0;
$expThisMonth = 0; $expThisYear = 0;
$curMonth = date('Y-m'); $curYear = date('Y');
foreach($expenses as $ex){
  if($ex['spent_date']){
    if(substr($ex['spent_date'],0,7)===$curMonth) $expThisMonth += $ex['amount'];
    if(substr($ex['spent_date'],0,4)===$curYear)  $expThisYear  += $ex['amount'];
  }
}
function gfm($n){return '₹'.number_format($n,2);}

// ── EXCEL (CSV) EXPORTS ──
// CSV opens directly in Excel. UTF-8 BOM added so ₹ and names show correctly.
if (($_GET['view'] ?? '')==='export_members') {
  if (!$isAdmin) { http_response_code(403); exit('Admins only.'); }
  $fname = 'GroundFund_Members_'.date('Y-m-d').'.csv';
  header('Content-Type: text/csv; charset=utf-8');
  header('Content-Disposition: attachment; filename="'.$fname.'"');
  echo "\xEF\xBB\xBF"; // UTF-8 BOM
  $out = fopen('php://output','w');
  fputcsv($out, [strtoupper($CLUB).' — GROUND FUND MEMBER COLLECTION']);
  fputcsv($out, [$PLACE.', Kerala  |  Generated: '.date('d M Y, g:i A')]);
  fputcsv($out, []);
  fputcsv($out, ['#','Member Name','Phone','Role','Pledged (Rs)','Paid (Rs)','Balance (Rs)','Status']);
  $i=0;
  foreach ($rows as $r) {
    $i++; $bal = $r['pledge'] - $r['paid'];
    fputcsv($out, [
      $i, $r['name'], ($r['whatsapp_number']?:'-'), roleLabel($r['role']),
      number_format($r['pledge'],2,'.',''), number_format($r['paid'],2,'.',''),
      number_format(max(0,$bal),2,'.',''), ($bal>0?'Balance Due':($r['pledge']>0?'Fully Paid':'No Pledge'))
    ]);
  }
  fputcsv($out, []);
  fputcsv($out, ['','TOTAL','','', number_format($totalPledged,2,'.',''), number_format($totalPaid,2,'.',''), number_format(max(0,$totalPledged-$totalPaid),2,'.','')]);
  fclose($out); exit;
}

if (($_GET['view'] ?? '')==='export_expenses') {
  if (!$isAdmin) { http_response_code(403); exit('Admins only.'); }
  $fname = 'GroundFund_Expenses_'.date('Y-m-d').'.csv';
  header('Content-Type: text/csv; charset=utf-8');
  header('Content-Disposition: attachment; filename="'.$fname.'"');
  echo "\xEF\xBB\xBF";
  $out = fopen('php://output','w');
  fputcsv($out, [strtoupper($CLUB).' — GROUND FUND EXPENSES']);
  fputcsv($out, [$PLACE.', Kerala  |  Generated: '.date('d M Y, g:i A')]);
  fputcsv($out, []);
  fputcsv($out, ['#','Item / Spent On','Date','Amount (Rs)','Note']);
  $i=0;
  foreach ($expenses as $ex) {
    $i++;
    fputcsv($out, [$i, $ex['title'], ($ex['spent_date']?date('d M Y',strtotime($ex['spent_date'])):'-'), number_format($ex['amount'],2,'.',''), ($ex['note']?:'')]);
  }
  fputcsv($out, []);
  fputcsv($out, ['','TOTAL EXPENSES','', number_format($totalExpense,2,'.','')]);
  fclose($out); exit;
}

// ── REPORT VIEW (built-in) ──
if (($_GET['view'] ?? '')==='report') {
  if (!$isAdmin) { http_response_code(403); exit('Admins only.'); }
  ?>
  <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Ground Fund Report — <?= h($CLUB) ?></title>
  <style>
  *{margin:0;padding:0;box-sizing:border-box}body{font-family:'Segoe UI',Arial,sans-serif;color:#1a2238;background:#e9edf4;padding:18px}
  .sheet{max-width:780px;margin:0 auto;background:#fff;border-radius:10px;box-shadow:0 6px 30px rgba(0,0,0,.15);position:relative;overflow:hidden}
  .wm{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:0;opacity:.06}.wm img{width:60%;max-width:420px;transform:rotate(-18deg)}
  .wm-text{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;z-index:0;opacity:.05;font-size:2.6rem;font-weight:900;color:#0B1033;transform:rotate(-18deg);text-align:center;padding:0 20px}
  .content{position:relative;z-index:1;padding:30px 32px 38px}
  .rhead{display:flex;align-items:center;gap:15px;border-bottom:3px solid #0A14E0;padding-bottom:15px}.rhead img{width:60px;height:60px;border-radius:50%;object-fit:cover;border:2px solid #c8922a}.rhead h1{font-size:1.3rem;color:#0B1033}.rhead .sub{font-size:.8rem;color:#5a6680;margin-top:2px}
  .rtag{display:inline-block;background:#0A14E0;color:#fff;font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:3px 12px;border-radius:20px;margin:14px 0 10px}
  .sumgrid{display:flex;gap:10px;margin-bottom:22px;flex-wrap:wrap}.sumbox{flex:1;min-width:110px;border:1px solid #E3E7F5;border-radius:9px;padding:11px 13px;background:#f8f9ff}.sumbox .l{font-size:.75rem;text-transform:uppercase;color:#5f6880;font-weight:700}.sumbox .v{font-size:1.25rem;font-weight:800;margin-top:3px}.green .v{color:#1b5e20}.blue .v{color:#0A14E0}.red .v{color:#c62828}.gold .v{color:#c8922a}
  h3.sec{font-size:.92rem;color:#0B1033;margin:18px 0 10px;border-left:4px solid #c8922a;padding-left:8px}
  table{width:100%;border-collapse:collapse;font-size:.8rem;margin-bottom:8px}th{background:#0B1033;color:#fff;text-align:left;padding:7px 9px;font-size:.75rem}th.r,td.r{text-align:right}td{padding:7px 9px;border-bottom:1px solid #eef1f6}tr:nth-child(even) td{background:#fafbfe}.due{color:#e65100;font-weight:700}.clear{color:#1b5e20;font-weight:700}tfoot td{font-weight:800;border-top:2px solid #0A14E0;background:#f0f4fc}
  .rfoot{margin-top:24px;border-top:1px solid #E3E7F5;padding-top:13px;font-size:.75rem;color:#5f6880;display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px}.stamp{margin-top:9px;font-size:.75rem;color:#aab2c4;font-style:italic}
  .pbar{max-width:780px;margin:0 auto 14px;display:flex;gap:10px;justify-content:flex-end}.pbtn{background:#0A14E0;color:#fff;border:none;border-radius:8px;padding:10px 18px;font-size:.85rem;font-weight:700;cursor:pointer}.pbtn.alt{background:#5a6680}
  @media print{
    body{background:#fff;padding:0}
    .pbar{display:none}
    .sheet{box-shadow:none;border-radius:0;max-width:100%}
    .wm,.wm-text{display:none}           /* hide stretched watermark on print to avoid overlap */
    table{page-break-inside:auto}
    tr{page-break-inside:avoid;page-break-after:auto}
    thead{display:table-header-group}
    h3.sec{page-break-after:avoid}
    @page{margin:12mm}
  }
  </style></head><body>
  <div class="pbar"><button class="pbtn" onclick="window.print()">📄 Save as PDF / Print</button><button class="pbtn alt" onclick="location.href='<?= $SELF ?>'">← Back</button></div>
  <div class="sheet">
    <?php if($LOGO): ?><div class="wm"><img src="<?= h($LOGO) ?>" alt=""></div><?php endif; ?>
    <div class="wm-text"><?= h($CLUB) ?></div>
    <div class="content">
      <div class="rhead"><?php if($LOGO): ?><img src="<?= h($LOGO) ?>" alt="logo"><?php endif; ?><div><h1><?= h($CLUB) ?></h1><div class="sub"><?= h($PLACE) ?>, Kerala · Ground Fund Ledger</div></div></div>
      <div class="rtag">Ground Fund Report</div>
      <div style="font-size:.8rem;color:#5a6680;margin-bottom:16px">Generated: <?= date('d M Y, g:i A') ?></div>
      <div class="sumgrid">
        <div class="sumbox green"><div class="l">Collected</div><div class="v"><?= gfm($totalPaid) ?></div></div>
        <div class="sumbox blue"><div class="l">Pledged</div><div class="v"><?= gfm($totalPledged) ?></div></div>
        <div class="sumbox red"><div class="l">Expenses</div><div class="v"><?= gfm($totalExpense) ?></div></div>
        <div class="sumbox gold"><div class="l">Fund Balance</div><div class="v"><?= gfm($fundBalance) ?></div></div>
      </div>
      <h3 class="sec">👥 Member Contributions</h3>
      <table><thead><tr><th style="width:30px">#</th><th>Member</th><th>Phone</th><th class="r">Pledged</th><th class="r">Paid</th><th class="r">Balance</th></tr></thead><tbody>
        <?php foreach($rows as $i=>$r): $bal=$r['pledge']-$r['paid']; ?>
        <tr><td><?= $i+1 ?></td><td><?= h($r['name']) ?><br><span style="color:#aab2c4;font-size:.75rem"><?= h(roleLabel($r['role'])) ?></span></td><td style="font-size:.75rem"><?= h($r['whatsapp_number']?:'—') ?></td><td class="r"><?= gfm($r['pledge']) ?></td><td class="r"><?= gfm($r['paid']) ?></td><td class="r <?= $bal>0?'due':'clear' ?>"><?= $bal>0?gfm($bal):'✓ Clear' ?></td></tr>
        <?php endforeach; ?>
      </tbody><tfoot><tr><td colspan="3">TOTAL</td><td class="r"><?= gfm($totalPledged) ?></td><td class="r"><?= gfm($totalPaid) ?></td><td class="r"><?= gfm(max(0,$totalPledged-$totalPaid)) ?></td></tr></tfoot></table>
      <?php if(!empty($expenses)): ?>
      <h3 class="sec">💸 Expenses</h3>
      <table><thead><tr><th>Item</th><th>Date</th><th class="r">Amount</th></tr></thead><tbody>
        <?php foreach($expenses as $ex): ?><tr><td><?= h($ex['title']) ?></td><td><?= $ex['spent_date']?date('d M Y',strtotime($ex['spent_date'])):'—' ?></td><td class="r"><?= gfm($ex['amount']) ?></td></tr><?php endforeach; ?>
      </tbody><tfoot><tr><td colspan="2">TOTAL EXPENSES</td><td class="r"><?= gfm($totalExpense) ?></td></tr></tfoot></table>
      <?php endif; ?>
      <div class="rfoot"><span><?= h($CLUB) ?> · <?= h($PLACE) ?></span><span><?= rtrim(SITE_URL,'/') ?></span></div>
      <div class="stamp">System-generated permanent ledger of member contributions toward the club ground.</div>
    </div>
  </div></body></html>
  <?php
  exit;
}

$filter = $_GET['filter'] ?? 'all';
require_once __DIR__.'/../includes/header.php';
?>
<style>
:root{--gf1:#0A14E0;--gf2:#1A23C9;--gfg:#1b5e20;--gfgold:#c8922a}
.gf-shell{background:#F5F7FF;min-height:100vh;padding-bottom:6rem}
.gf-hero{background:linear-gradient(135deg,#0a1f3d,#121A5C 55%,#1A23C9);padding:1.8rem 1.1rem 1.5rem;text-align:center;color:#fff;position:relative;overflow:hidden}
.gf-hero::before{content:'🏟️';position:absolute;font-size:8rem;opacity:.06;right:-10px;top:-10px}
.gf-hero h1{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.44rem;letter-spacing:.01em;margin-bottom:.2rem;position:relative}
.gf-hero p{font-size:.76rem;color:rgba(255,255,255,.72);position:relative}
.gf-wrap{max-width:760px;margin:0 auto;padding:1rem}
.gf-sum{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem;margin-bottom:1rem}
.gf-sum-box{background:#fff;border-radius:16px;padding:.9rem;box-shadow:0 3px 14px rgba(13,27,62,.06);text-align:center;animation:gfUp .4s both}
.gf-sum-box:nth-child(2){animation-delay:.05s}.gf-sum-box:nth-child(3){animation-delay:.1s}.gf-sum-box:nth-child(4){animation-delay:.15s}
@keyframes gfUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}
.gf-sum-box .l{font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#5f6880;margin-bottom:.2rem}
.gf-sum-box .v{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.24rem}
.v-paid{color:var(--gfg)}.v-pledge{color:var(--gf1)}.v-exp{color:#c62828}.v-bal{color:#8a6116}
.gf-search{display:flex;align-items:center;gap:.5rem;background:#fff;border:1.5px solid #E3E7F5;border-radius:24px;padding:.55rem .9rem;margin-bottom:.7rem;box-shadow:0 2px 8px rgba(0,0,0,.04)}
.gf-search input{border:none;outline:none;flex:1;font-size:.9rem;font-family:inherit;background:none}
.gf-filters{display:flex;gap:.4rem;overflow-x:auto;padding-bottom:.4rem;margin-bottom:.8rem;scrollbar-width:none}.gf-filters::-webkit-scrollbar{display:none}
.gf-chip{flex-shrink:0;padding:.4rem .85rem;border-radius:20px;background:#fff;border:1.5px solid #E3E7F5;font-size:.76rem;font-weight:700;color:#64748b;text-decoration:none;white-space:nowrap}
.gf-chip.on{background:var(--gf1);border-color:var(--gf1);color:#fff}
.gf-card{background:#fff;border-radius:16px;box-shadow:0 3px 14px rgba(13,27,62,.06);margin-bottom:.6rem;overflow:hidden}
.gf-row{display:flex;align-items:center;gap:.7rem;padding:.85rem .9rem;cursor:pointer;transition:background .15s}
.gf-row:active{background:#f6f8fc}
.gf-av{width:44px;height:44px;border-radius:50%;object-fit:cover;flex-shrink:0;background:linear-gradient(135deg,var(--gf1),var(--gf2));color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800}
.gf-name{font-weight:800;font-size:.92rem;color:#0B1033}.gf-role{font-size:.75rem;color:#5f6880}
.gf-amt{text-align:right;flex-shrink:0}.gf-paid{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.0rem;color:var(--gfg);line-height:1}
.gf-bal-pill{display:inline-block;font-size:.75rem;font-weight:800;padding:.12rem .5rem;border-radius:10px;margin-top:.15rem}
.bal-due{background:#fff3e0;color:#e65100}.bal-clear{background:#e8f5e9;color:#1b5e20}.bal-none{background:#eceff1;color:#546e7a}
.gf-chev{color:#cbd5e1;font-size:.9rem;transition:transform .25s}.gf-card.open .gf-chev{transform:rotate(90deg)}
.gf-detail{display:none;border-top:1px solid #F5F7FF;padding:.9rem;background:#fafbff}
.gf-card.open .gf-detail{display:block;animation:gfUp .25s}
.gf-prof{display:flex;gap:.7rem;align-items:center;margin-bottom:.7rem}
.gf-prof-tiles{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.4rem;margin-bottom:.7rem}
.gf-tile{background:#fff;border:1px solid #eef1f6;border-radius:10px;padding:.5rem;text-align:center}
.gf-tile .tl{font-size:.75rem;color:#5f6880;font-weight:800;text-transform:uppercase}.gf-tile .tv{font-size:.82rem;font-weight:800;color:#0B1033;margin-top:.1rem}
.gf-pay-item{display:flex;justify-content:space-between;align-items:center;font-size:.78rem;padding:.4rem 0;border-bottom:1px dashed #E3E7F5}
.gf-mini-btn{background:linear-gradient(135deg,var(--gfg),#2e7d32);color:#fff;border:none;border-radius:10px;padding:.5rem .9rem;font-size:.78rem;font-weight:800;cursor:pointer;font-family:inherit}
.gf-mini-btn.blue{background:linear-gradient(135deg,var(--gf1),var(--gf2))}
.gf-sec-title{font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.96rem;letter-spacing:.01em;color:var(--gf1);margin:1.3rem 0 .6rem;display:flex;align-items:center;justify-content:space-between}
.gf-exp-row{display:flex;justify-content:space-between;align-items:center;background:#fff;border-radius:12px;padding:.7rem .85rem;margin-bottom:.45rem;box-shadow:0 2px 8px rgba(0,0,0,.04)}
.gf-report-btn{display:flex;align-items:center;justify-content:center;gap:.4rem;width:100%;background:linear-gradient(135deg,#1b5e20,#2e7d32);color:#fff;border-radius:12px;padding:.7rem;font-size:.84rem;font-weight:800;text-decoration:none;margin-bottom:1rem}
.gf-ov{display:none;position:fixed;inset:0;background:rgba(13,27,62,.6);z-index:10000;align-items:flex-end;justify-content:center}
.gf-ov.on{display:flex}
.gf-modal{background:#fff;width:100%;max-width:480px;border-radius:22px 22px 0 0;padding:1.2rem 1.2rem 1.6rem;animation:gfSlide .3s ease}
@keyframes gfSlide{from{transform:translateY(100%)}to{transform:translateY(0)}}
.gf-modal h3{font-size:1.05rem;color:#0B1033;margin-bottom:.1rem;display:flex;align-items:center;gap:.4rem}
.gf-modal .who{font-size:.76rem;color:#5f6880;margin-bottom:.9rem}
.inp{width:100%;padding:.7rem .8rem;border:1.5px solid #E3E7F5;border-radius:11px;font-size:.9rem;font-family:inherit;box-sizing:border-box;margin-bottom:.55rem}
.gf-modal-btns{display:flex;gap:.5rem;margin-top:.4rem}
.gf-submit{flex:1;background:linear-gradient(135deg,var(--gf1),var(--gf2));color:#fff;border:none;border-radius:11px;padding:.75rem;font-weight:800;font-size:.9rem;cursor:pointer}
.gf-cancel{background:#eceff1;color:#546e7a;border:none;border-radius:11px;padding:.75rem 1.1rem;font-weight:700;cursor:pointer}
.gf-fab{position:fixed;bottom:calc(74px + env(safe-area-inset-bottom,0px));right:1.1rem;z-index:900;background:linear-gradient(135deg,#c62828,#e53935);color:#fff;height:50px;padding:0 1.2rem;border-radius:26px;display:flex;align-items:center;gap:.4rem;font-size:.85rem;font-weight:800;text-decoration:none;box-shadow:0 8px 24px rgba(198,40,40,.4);border:none;cursor:pointer;font-family:inherit}
.gf-toast{position:fixed;bottom:5.5rem;left:50%;transform:translateX(-50%) translateY(30px);background:#1b5e20;color:#fff;padding:.6rem 1.1rem;border-radius:22px;font-size:.82rem;font-weight:700;z-index:10001;opacity:0;transition:all .3s;white-space:nowrap}
.gf-toast.on{opacity:1;transform:translateX(-50%) translateY(0)}.gf-toast.err{background:#c62828}
</style>

<div class="gf-shell">
  <div class="gf-hero">
    <h1>🏟️ GROUND FUND</h1>
    <p><?= h($CLUB) ?> · <?= h($PLACE) ?> · Member Contributions</p>
  </div>

  <div class="gf-wrap">
    <div class="gf-sum">
      <div class="gf-sum-box"><div class="l">Collected</div><div class="v v-paid">₹<?= number_format($totalPaid) ?></div></div>
      <div class="gf-sum-box"><div class="l">Pledged</div><div class="v v-pledge">₹<?= number_format($totalPledged) ?></div></div>
      <div class="gf-sum-box"><div class="l">Expenses</div><div class="v v-exp">₹<?= number_format($totalExpense) ?></div></div>
      <div class="gf-sum-box"><div class="l">Fund Balance</div><div class="v v-bal">₹<?= number_format($fundBalance) ?></div></div>
    </div>

    <?php if($isAdmin): ?>
    <div style="font-size:.75rem;font-weight:800;color:#556274;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.4rem">📥 Reports & Export</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem;margin-bottom:1rem">
      <a href="?view=report" class="gf-report-btn" style="margin:0;grid-column:1/-1">📄 Full Report (PDF) — Members + Expenses</a>
      <a href="?view=export_members" class="gf-report-btn" style="margin:0;background:linear-gradient(135deg,#1d6f42,#2e7d32)">📊 Member Collection<br><span style="font-size:.75rem;opacity:.85;font-weight:600">Excel</span></a>
      <a href="?view=export_expenses" class="gf-report-btn" style="margin:0;background:linear-gradient(135deg,#b25b00,#e65100)">💸 Expense Report<br><span style="font-size:.75rem;opacity:.85;font-weight:600">Excel</span></a>
    </div>
    <?php endif; ?>

    <div class="gf-search">
      <span>🔍</span>
      <input type="text" id="gfSearch" placeholder="Search member by name…" oninput="gfFilterSearch()">
    </div>

    <div class="gf-filters">
      <?php foreach(['all'=>'👥 All','paid'=>'✅ Fully Paid','balance'=>'⏳ Balance Due','top'=>'🏆 Top Funders'] as $k=>$lbl): ?>
      <a href="?filter=<?= $k ?>" class="gf-chip <?= $filter===$k?'on':'' ?>"><?= $lbl ?></a>
      <?php endforeach; ?>
    </div>

    <div id="gfList">
    <?php
    $list=$rows;
    if($filter==='paid')    $list=array_filter($rows,fn($r)=>$r['pledge']>0&&$r['paid']>=$r['pledge']);
    if($filter==='balance') $list=array_filter($rows,fn($r)=>$r['pledge']>0&&$r['paid']<$r['pledge']);
    if($filter==='top')     $list=array_filter($rows,fn($r)=>$r['paid']>0);
    $list=array_values($list);
    if(empty($list)): ?>
    <div style="text-align:center;padding:2rem;color:#5f6880">No members here.</div>
    <?php else: foreach($list as $i=>$r):
      $bal=$r['pledge']-$r['paid']; $photo=$r['profile_photo']?getMemberPhoto($r['profile_photo']):'';
      if($r['pledge']<=0){$balCls='bal-none';$balTxt='No pledge';}
      elseif($bal<=0){$balCls='bal-clear';$balTxt='✓ Paid';}
      else{$balCls='bal-due';$balTxt='Bal ₹'.number_format($bal);}
      $hist=db()->prepare("SELECT * FROM gf_payments WHERE member_id=? ORDER BY pay_date DESC,id DESC");$hist->execute([$r['id']]);$hist=$hist->fetchAll();
    ?>
    <div class="gf-card" data-name="<?= h(strtolower($r['name'])) ?>" id="gfc-<?= $r['id'] ?>">
      <div class="gf-row" onclick="gfToggle(<?= $r['id'] ?>)">
        <?php if($photo): ?><img src="<?= $photo ?>" class="gf-av" alt=""><?php else: ?><div class="gf-av"><?= strtoupper(substr($r['name'],0,1)) ?></div><?php endif; ?>
        <div style="flex:1;min-width:0">
          <div class="gf-name"><?php if($filter==='top'&&$i<3) echo ['🥇','🥈','🥉'][$i].' '; ?><?= h($r['name']) ?></div>
          <div class="gf-role"><?= h(roleLabel($r['role'])) ?></div>
        </div>
        <div class="gf-amt"><div class="gf-paid">₹<?= number_format($r['paid']) ?></div><span class="gf-bal-pill <?= $balCls ?>"><?= $balTxt ?></span></div>
        <span class="gf-chev">▸</span>
      </div>
      <div class="gf-detail">
        <div class="gf-prof">
          <?php if($photo): ?><img src="<?= $photo ?>" style="width:54px;height:54px;border-radius:50%;object-fit:cover" alt=""><?php else: ?><div class="gf-av" style="width:54px;height:54px;font-size:1.3rem"><?= strtoupper(substr($r['name'],0,1)) ?></div><?php endif; ?>
          <div><div style="font-weight:800;color:#0B1033"><?= h($r['name']) ?></div><div style="font-size:.75rem;color:#5f6880"><?= h(roleLabel($r['role'])) ?> · AV<?= str_pad($r['id'],4,'0',STR_PAD_LEFT) ?></div></div>
        </div>
        <div class="gf-prof-tiles">
          <div class="gf-tile"><div class="tl">Pledged</div><div class="tv">₹<?= number_format($r['pledge']) ?></div></div>
          <div class="gf-tile"><div class="tl">Paid</div><div class="tv" style="color:#1b5e20">₹<?= number_format($r['paid']) ?></div></div>
          <div class="gf-tile"><div class="tl">Balance</div><div class="tv" style="color:<?= $bal>0?'#e65100':'#1b5e20' ?>">₹<?= number_format(max(0,$bal)) ?></div></div>
          <div class="gf-tile"><div class="tl">Blood</div><div class="tv"><?= h($r['blood_group']?:'—') ?></div></div>
          <?php if($r['profession']): ?><div class="gf-tile"><div class="tl">Job</div><div class="tv"><?= h($r['profession']) ?></div></div><?php endif; ?>
          <?php if($r['skill']): ?><div class="gf-tile"><div class="tl">Skill</div><div class="tv"><?= h($r['skill']) ?></div></div><?php endif; ?>
        </div>
        <div style="font-size:.75rem;font-weight:800;color:#64748b;text-transform:uppercase;margin-bottom:.3rem">Payment History</div>
        <?php if(empty($hist)): ?><div style="font-size:.78rem;color:#5f6880;padding:.3rem 0">No payments yet.</div>
        <?php else: foreach($hist as $hp): ?>
        <div class="gf-pay-item">
          <div><span style="font-weight:700">₹<?= number_format($hp['amount']) ?></span><span style="color:#5f6880"> · <?= $hp['pay_date']?date('d M Y',strtotime($hp['pay_date'])):'—' ?> · <?= h(ucfirst($hp['method'])) ?></span><?php if($hp['note']): ?><div style="font-size:.75rem;color:#5f6880"><?= h($hp['note']) ?></div><?php endif; ?></div>
          <?php if($isAdmin): ?><button onclick="gfDelPay(<?= $hp['id'] ?>)" style="background:none;border:none;color:#b71c1c;cursor:pointer;font-size:.9rem">🗑</button><?php endif; ?>
        </div>
        <?php endforeach; endif; ?>
        <?php if($isAdmin): ?>
        <div style="display:flex;gap:.5rem;margin-top:.8rem">
          <button class="gf-mini-btn" onclick="gfOpenPay(<?= $r['id'] ?>,'<?= h(addslashes($r['name'])) ?>')">➕ Add Payment</button>
          <button class="gf-mini-btn blue" onclick="gfOpenPledge(<?= $r['id'] ?>,'<?= h(addslashes($r['name'])) ?>',<?= (int)$r['pledge'] ?>)">🎯 Set Pledge</button>
        </div>
        <?php endif; ?>
      </div>
    </div>
    <?php endforeach; endif; ?>
    </div>
    <div id="gfNoResult" style="display:none;text-align:center;padding:1.5rem;color:#5f6880">No member found.</div>

    <div class="gf-sec-title"><span>💸 Fund Expenses</span><span style="font-family:inherit;font-size:.9rem;color:#c62828;font-weight:800">₹<?= number_format($totalExpense) ?></span></div>

    <?php if(!empty($expenses)): ?>
    <!-- Expense summary -->
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin-bottom:.7rem">
      <div style="background:#fff;border-radius:12px;padding:.6rem;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.04)">
        <div style="font-size:.75rem;font-weight:800;color:#5f6880;text-transform:uppercase">Entries</div>
        <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.04rem;color:#0B1033"><?= $expCount ?></div>
      </div>
      <div style="background:#fff;border-radius:12px;padding:.6rem;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.04)">
        <div style="font-size:.75rem;font-weight:800;color:#5f6880;text-transform:uppercase">This Month</div>
        <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.04rem;color:#c62828">₹<?= number_format($expThisMonth) ?></div>
      </div>
      <div style="background:#fff;border-radius:12px;padding:.6rem;text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.04)">
        <div style="font-size:.75rem;font-weight:800;color:#5f6880;text-transform:uppercase">Average</div>
        <div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:1.04rem;color:#0B1033">₹<?= number_format($expAvg) ?></div>
      </div>
    </div>
    <!-- Expense time filter -->
    <div class="gf-filters" style="margin-bottom:.6rem">
      <button class="gf-chip on" data-exp="all" onclick="gfExpFilter('all',this)">📋 All</button>
      <button class="gf-chip" data-exp="month" onclick="gfExpFilter('month',this)">📅 This Month</button>
      <button class="gf-chip" data-exp="year" onclick="gfExpFilter('year',this)">🗓️ This Year</button>
    </div>
    <?php endif; ?>

    <div id="gfExpList">
    <?php if(empty($expenses)): ?><div style="text-align:center;padding:1rem;color:#5f6880;font-size:.82rem">No expenses recorded yet.</div>
    <?php else: foreach($expenses as $ex):
      $ePeriodM = ($ex['spent_date'] && substr($ex['spent_date'],0,7)===$curMonth) ? '1' : '0';
      $ePeriodY = ($ex['spent_date'] && substr($ex['spent_date'],0,4)===$curYear) ? '1' : '0';
    ?>
    <div class="gf-exp-row" data-month="<?= $ePeriodM ?>" data-year="<?= $ePeriodY ?>">
      <div><div style="font-weight:700;font-size:.86rem;color:#0B1033"><?= h($ex['title']) ?></div><div style="font-size:.75rem;color:#5f6880"><?= $ex['spent_date']?date('d M Y',strtotime($ex['spent_date'])):'' ?><?= $ex['note']?' · '.h($ex['note']):'' ?></div></div>
      <div style="display:flex;align-items:center;gap:.5rem"><div style="font-family:var(--font,'Plus Jakarta Sans'),sans-serif;font-weight:800;text-transform:uppercase;font-size:0.92rem;color:#c62828">₹<?= number_format($ex['amount']) ?></div><?php if($isAdmin): ?><button onclick="gfDelExp(<?= $ex['id'] ?>)" style="background:none;border:none;color:#b71c1c;cursor:pointer">🗑</button><?php endif; ?></div>
    </div>
    <?php endforeach; endif; ?>
    <div id="gfExpNone" style="display:none;text-align:center;padding:1rem;color:#5f6880;font-size:.82rem">No expenses in this period.</div>
    </div>
  </div>
</div>

<?php if($isAdmin): ?>
<button class="gf-fab" onclick="gfOpenExpense()">＋ Add Expense</button>

<div class="gf-ov" id="ovPay" onclick="if(event.target===this)gfClose('ovPay')">
  <div class="gf-modal">
    <h3>➕ Add Payment</h3><div class="who" id="payWho"></div>
    <input type="hidden" id="payMid">
    <input type="number" class="inp" id="payAmt" placeholder="Amount ₹" min="1">
    <div style="display:flex;gap:.5rem"><input type="date" class="inp" id="payDate" value="<?= date('Y-m-d') ?>"><select class="inp" id="payMethod"><option value="cash">Cash</option><option value="upi">UPI</option><option value="bank">Bank</option></select></div>
    <input type="text" class="inp" id="payNote" placeholder="Note (optional)">
    <div class="gf-modal-btns"><button class="gf-submit" style="background:linear-gradient(135deg,#1b5e20,#2e7d32)" onclick="gfSavePay()">Save Payment</button><button class="gf-cancel" onclick="gfClose('ovPay')">Cancel</button></div>
  </div>
</div>
<div class="gf-ov" id="ovPledge" onclick="if(event.target===this)gfClose('ovPledge')">
  <div class="gf-modal">
    <h3>🎯 Set Pledge</h3><div class="who" id="pledgeWho"></div>
    <input type="hidden" id="pledgeMid">
    <input type="number" class="inp" id="pledgeAmt" placeholder="Pledge amount ₹" min="0">
    <div class="gf-modal-btns"><button class="gf-submit" onclick="gfSavePledge()">Save Pledge</button><button class="gf-cancel" onclick="gfClose('ovPledge')">Cancel</button></div>
  </div>
</div>
<div class="gf-ov" id="ovExp" onclick="if(event.target===this)gfClose('ovExp')">
  <div class="gf-modal">
    <h3>💸 Add Expense</h3><div class="who">What was the fund spent on?</div>
    <input type="text" class="inp" id="expTitle" placeholder="e.g. Land registration">
    <div style="display:flex;gap:.5rem"><input type="number" class="inp" id="expAmt" placeholder="Amount ₹" min="1"><input type="date" class="inp" id="expDate" value="<?= date('Y-m-d') ?>"></div>
    <input type="text" class="inp" id="expNote" placeholder="Note (optional)">
    <div class="gf-modal-btns"><button class="gf-submit" style="background:linear-gradient(135deg,#c62828,#e53935)" onclick="gfSaveExp()">Add Expense</button><button class="gf-cancel" onclick="gfClose('ovExp')">Cancel</button></div>
  </div>
</div>
<?php endif; ?>

<div class="gf-toast" id="gfToast"></div>

<script>
var GF_SELF = <?= json_encode($SELF) ?>;
function gfToast(m,e){var t=document.getElementById('gfToast');t.textContent=m;t.className='gf-toast on'+(e?' err':'');setTimeout(function(){t.className='gf-toast';},2600);}
function gfToggle(id){document.getElementById('gfc-'+id).classList.toggle('open');}
function gfExpFilter(period,btn){
  document.querySelectorAll('[data-exp]').forEach(function(b){b.classList.remove('on');});
  btn.classList.add('on');
  var rows=document.querySelectorAll('#gfExpList .gf-exp-row'),shown=0;
  rows.forEach(function(r){
    var ok = period==='all' || (period==='month'&&r.getAttribute('data-month')==='1') || (period==='year'&&r.getAttribute('data-year')==='1');
    r.style.display=ok?'':'none'; if(ok)shown++;
  });
  document.getElementById('gfExpNone').style.display=shown===0?'block':'none';
}
function gfFilterSearch(){
  var q=document.getElementById('gfSearch').value.toLowerCase().trim();
  var cards=document.querySelectorAll('#gfList .gf-card'),shown=0;
  cards.forEach(function(c){var ok=c.getAttribute('data-name').indexOf(q)>-1;c.style.display=ok?'':'none';if(ok)shown++;});
  document.getElementById('gfNoResult').style.display=shown===0?'block':'none';
}
function gfClose(id){document.getElementById(id).classList.remove('on');document.body.style.overflow='';}
function gfOpen(id){document.getElementById(id).classList.add('on');document.body.style.overflow='hidden';}
function gfPost(data,cb){if(window.sudoThen){sudoThen(function(){gfPostGo(data,cb);});}else gfPostGo(data,cb);}
function gfPostGo(data,cb){fetch(GF_SELF,{method:'POST',body:new URLSearchParams(data)}).then(function(r){return r.json();}).then(cb).catch(function(){gfToast('Error',1);});}
<?php if($isAdmin): ?>
function gfOpenPay(mid,name){document.getElementById('payMid').value=mid;document.getElementById('payWho').textContent='For '+name;document.getElementById('payAmt').value='';document.getElementById('payNote').value='';gfOpen('ovPay');}
function gfSavePay(){var amt=document.getElementById('payAmt').value;if(!amt||amt<=0){gfToast('Enter amount',1);return;}gfPost({ajax:'add_payment',member_id:document.getElementById('payMid').value,amount:amt,pay_date:document.getElementById('payDate').value,method:document.getElementById('payMethod').value,note:document.getElementById('payNote').value},function(res){if(res.ok){gfToast(res.msg);gfClose('ovPay');setTimeout(function(){location.reload();},700);}else gfToast(res.msg||'Error',1);});}
function gfOpenPledge(mid,name,cur){document.getElementById('pledgeMid').value=mid;document.getElementById('pledgeWho').textContent='For '+name;document.getElementById('pledgeAmt').value=cur||'';gfOpen('ovPledge');}
function gfSavePledge(){gfPost({ajax:'set_pledge',member_id:document.getElementById('pledgeMid').value,pledge_amount:document.getElementById('pledgeAmt').value||0},function(res){if(res.ok){gfToast(res.msg);gfClose('ovPledge');setTimeout(function(){location.reload();},700);}else gfToast(res.msg||'Error',1);});}
function gfOpenExpense(){document.getElementById('expTitle').value='';document.getElementById('expAmt').value='';document.getElementById('expNote').value='';gfOpen('ovExp');}
function gfSaveExp(){var t=document.getElementById('expTitle').value,a=document.getElementById('expAmt').value;if(!t||!a||a<=0){gfToast('Fill title & amount',1);return;}gfPost({ajax:'add_expense',title:t,amount:a,spent_date:document.getElementById('expDate').value,note:document.getElementById('expNote').value},function(res){if(res.ok){gfToast(res.msg);gfClose('ovExp');setTimeout(function(){location.reload();},700);}else gfToast(res.msg||'Error',1);});}
function gfDelPay(pid){if(!confirm('Remove this payment?'))return;gfPost({ajax:'del_payment',pid:pid},function(res){if(res.ok){gfToast('Removed');setTimeout(function(){location.reload();},500);}});}
function gfDelExp(eid){if(!confirm('Remove this expense?'))return;gfPost({ajax:'del_expense',eid:eid},function(res){if(res.ok){gfToast('Removed');setTimeout(function(){location.reload();},500);}});}
<?php endif; ?>
</script>

<?php require_once __DIR__.'/../includes/footer.php'; ?>
