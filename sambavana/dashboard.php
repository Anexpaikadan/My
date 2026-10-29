<?php require 'config.php';$u=require_login();
if($u['role']==='admin')redirect('admin.php');
if($u['role']==='collector')redirect('fund.php?id='.(int)$u['fund_id']);
$s=$pdo->prepare('SELECT * FROM funds WHERE creator_id=? ORDER BY status=\'closed\',id DESC');$s->execute([$u['id']]);$funds=$s->fetchAll();
// per fund: totals, entries, people with balance
$q=$pdo->prepare('SELECT COUNT(*) n,COALESCE(SUM(c.amount>COALESCE(pp.paid,0)),0) pend FROM contributions c LEFT JOIN (SELECT contribution_id,SUM(amount) paid FROM payments GROUP BY contribution_id) pp ON pp.contribution_id=c.id WHERE c.fund_id=? AND c.cancelled=0');
$T=$P=$N=$PN=0;
foreach($funds as &$f){[$f['t'],$f['p'],$f['b']]=fund_totals($f['id']);$q->execute([$f['id']]);$x=$q->fetch();$f['n']=(int)$x['n'];$f['pend']=(int)$x['pend'];
 $T+=$f['t'];$P+=$f['p'];$N+=$f['n'];$PN+=$f['pend'];}
unset($f);
$r=$pdo->prepare('SELECT c.id,c.serial_no,c.name,c.amount,c.created_at,f.title,(SELECT COALESCE(SUM(amount),0) FROM payments p WHERE p.contribution_id=c.id) paid FROM contributions c JOIN funds f ON f.id=c.fund_id WHERE f.creator_id=? AND c.cancelled=0 ORDER BY c.id DESC LIMIT 5');$r->execute([$u['id']]);$recent=$r->fetchAll();
$pc=fn($p,$t)=>$t>0?(int)min(100,round($p/$t*100)):0;
$h=(int)date('G');$hi=$h<12?'Good morning':($h<17?'Good afternoon':'Good evening');
nav_main('home');head('Home');?>
<style>
.hero{background:linear-gradient(135deg,#3513d6,#6a3df0);color:#fff;border-radius:20px;padding:18px;box-shadow:0 6px 18px #3513d640}
.hero .big{font-size:1.9rem;font-weight:800;line-height:1.1}
.hero .progress{background:#ffffff40;height:8px}
.hero .progress-bar{background:var(--g)}
.hero .k{font-size:.8rem;opacity:.85}
.stat{background:#fff;border-radius:16px;padding:12px 6px;text-align:center;box-shadow:0 1px 4px #3513d614;text-decoration:none;color:#222;display:block}
.stat b{display:block;font-size:1.25rem}
.stat i{font-size:1.2rem;color:var(--p)}
.fund{border-radius:18px;overflow:hidden}
.fund .top{display:block;padding:14px 14px 10px;color:#222;text-decoration:none}
.fund .progress{height:7px}
.chip{font-size:.75rem;border-radius:20px;padding:1px 9px;background:#ece8ff;color:var(--p);font-weight:600}
.chip.closed{background:#eee;color:#666}
.acts{display:flex;border-top:1px solid #f0eef8}
.acts a{flex:1;text-align:center;padding:8px 2px;font-size:11px;color:#555;text-decoration:none}
.acts a i{display:block;font-size:19px;color:var(--p)}
.acts a:active{background:#f3f1ff}
.rec{display:flex;align-items:center;gap:10px;padding:10px 12px;color:#222;text-decoration:none;border-bottom:1px solid #f3f2f8}
.rec:last-child{border-bottom:0}
.rec .dot{width:36px;height:36px;border-radius:12px;background:#ece8ff;color:var(--p);display:flex;align-items:center;justify-content:center;font-weight:700;flex:none;font-size:13px}
</style>
<div class="hero mb-3">
<div class="k"><?=$hi?>, <?=e($u['name'])?> 👋</div>
<div class="k mt-2">Collected / ലഭിച്ചത്</div>
<div class="big">₹<?=money($P)?></div>
<div class="progress my-2"><div class="progress-bar" style="width:<?=$pc($P,$T)?>%"></div></div>
<div class="d-flex justify-content-between small"><span>Promised ₹<?=money($T)?></span><span>Balance ₹<?=money($T-$P)?></span></div>
</div>
<div class="row g-2 mb-3">
<div class="col-4"><div class="stat"><i class="bi bi-collection"></i><b><?=count($funds)?></b><small class="text-muted">Funds</small></div></div>
<div class="col-4"><div class="stat"><i class="bi bi-people"></i><b><?=$N?></b><small class="text-muted">Entries</small></div></div>
<div class="col-4"><div class="stat"><i class="bi bi-hourglass-split"></i><b class="text-danger"><?=$PN?></b><small class="text-muted">Pending</small></div></div>
</div>
<div class="d-flex justify-content-between align-items-center mb-2"><h6 class="m-0 fw-bold">My Funds / എന്റെ ഫണ്ടുകൾ</h6>
<a class="btn btn-sm btn-outline-primary rounded-pill" href="account.php#new"><i class="bi bi-plus"></i> New</a></div>
<?php foreach($funds as $f):$id=$f['id'];?>
<div class="card fund mb-3">
<a class="top" href="fund.php?id=<?=$id?>">
<div class="d-flex justify-content-between align-items-start gap-2"><b style="font-size:1.05rem"><?=e($f['title'])?></b><i class="bi bi-chevron-right text-muted"></i></div>
<div class="d-flex gap-1 my-1"><span class="chip"><?=e(ucfirst($f['type']))?></span><span class="chip <?=$f['status']==='closed'?'closed':''?>"><?=$f['status']==='closed'?'🔒 Closed':'● Open'?></span><small class="text-muted ms-auto"><?=$f['n']?> entries</small></div>
<div class="progress my-2"><div class="progress-bar bg-success" style="width:<?=$pc($f['p'],$f['t'])?>%"></div></div>
<div class="row g-0 text-center small"><div class="col-4"><small class="text-muted d-block">Total</small><b>₹<?=money($f['t'])?></b></div><div class="col-4 border-start"><small class="text-muted d-block">Paid</small><b class="text-success">₹<?=money($f['p'])?></b></div><div class="col-4 border-start"><small class="text-muted d-block">Balance</small><b class="text-danger">₹<?=money($f['b'])?></b></div></div>
</a>
<div class="acts">
<?php if($f['status']==='open'):?><a href="entry.php?id=<?=$id?>"><i class="bi bi-plus-square"></i>Entry</a><?php endif;?>
<a href="reports.php?id=<?=$id?>"><i class="bi bi-bar-chart-line"></i>Reports</a>
<a href="remind.php?id=<?=$id?>"><i class="bi bi-bell"></i>Pending<?=$f['pend']?' ('.$f['pend'].')':''?></a>
<a href="items.php?id=<?=$id?>"><i class="bi bi-bag"></i>Products</a>
</div></div>
<?php endforeach;if(!$funds):?>
<div class="card p-4 text-center mb-3"><div style="font-size:42px">🪙</div><b>No funds yet</b><p class="small text-muted mb-2">Create your first fund, e.g. പായസം ചലഞ്ച്</p>
<a class="btn btn-primary rounded-pill" href="account.php#new">＋ Create fund</a></div>
<?php endif;?>
<?php if($recent):?><h6 class="fw-bold mb-2">Recent entries / പുതിയവ</h6>
<div class="card mb-3"><?php foreach($recent as $x):?><a class="rec" href="contribution.php?id=<?=$x['id']?>"><span class="dot">#<?=$x['serial_no']?></span>
<span class="flex-grow-1 text-truncate"><b><?=nm($x['name'],$x['amount']-$x['paid'])?></b><br><small class="text-muted"><?=e($x['title'])?> · <?=date('d M, g:i a',strtotime($x['created_at']))?></small></span><b>₹<?=money($x['amount'])?></b></a><?php endforeach;?></div>
<?php endif;?>
<?php foot();
