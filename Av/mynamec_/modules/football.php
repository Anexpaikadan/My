<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/upload_helper.php';
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '⚽ Football Tournament — Aishwarya Arts & Sports Club',
  'desc'  => 'Football tournament fixtures and results — AASC, Vettikkattiri',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/football.php',
];
requireLogin(); $user = currentUser();
$pageTitle = 'Football Tournament — '.setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$isAdmin   = isSportsAdmin($user['role']);
$uid       = $user['id'];

// ── DB setup ────────────────────────────────────────────────────
try {
  db()->exec("CREATE TABLE IF NOT EXISTS tournaments(
    id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(200),
    sport VARCHAR(50) DEFAULT 'football',description TEXT,
    start_date DATE,end_date DATE,venue VARCHAR(200),prize VARCHAR(100),
    banner_photo VARCHAR(500),
    format ENUM('league','knockout','group_knockout') DEFAULT 'league',
    status ENUM('upcoming','ongoing','completed') DEFAULT 'upcoming',
    registration_open TINYINT(1) DEFAULT 1,
    created_by INT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)");
} catch(Exception $e){}
try { db()->exec("ALTER TABLE tournaments ADD COLUMN banner_photo VARCHAR(500) DEFAULT NULL"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE tournament_registrations ADD UNIQUE uniq_reg (tournament_id, user_id)"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE tournaments ADD COLUMN format ENUM('league','knockout','group_knockout') DEFAULT 'league'"); } catch(Exception $e){}
try { db()->exec("ALTER TABLE tournaments ADD COLUMN registration_open TINYINT(1) DEFAULT 1"); } catch(Exception $e){}
try {
  db()->exec("CREATE TABLE IF NOT EXISTS tournament_teams(
    id INT AUTO_INCREMENT PRIMARY KEY,tournament_id INT,team_name VARCHAR(100),
    captain VARCHAR(100),team_photo VARCHAR(500),
    wins INT DEFAULT 0,losses INT DEFAULT 0,draws INT DEFAULT 0,
    goals_for INT DEFAULT 0,goals_against INT DEFAULT 0)");
} catch(Exception $e){}
try { db()->exec("ALTER TABLE tournament_teams ADD COLUMN team_photo VARCHAR(500) DEFAULT NULL"); } catch(Exception $e){}
try {
  db()->exec("CREATE TABLE IF NOT EXISTS tournament_matches(
    id INT AUTO_INCREMENT PRIMARY KEY,tournament_id INT,
    team1_id INT,team2_id INT,
    team1_goals INT DEFAULT 0,team2_goals INT DEFAULT 0,
    match_date DATE,match_time TIME,venue VARCHAR(200),
    status ENUM('scheduled','live','completed') DEFAULT 'scheduled',
    round VARCHAR(80),stage VARCHAR(50) DEFAULT 'group')");
} catch(Exception $e){}
try { db()->exec("ALTER TABLE tournament_matches ADD COLUMN stage VARCHAR(50) DEFAULT 'group'"); } catch(Exception $e){}
try {
  db()->exec("CREATE TABLE IF NOT EXISTS tournament_registrations(
    id INT AUTO_INCREMENT PRIMARY KEY,tournament_id INT,user_id INT,
    player_name VARCHAR(150),position VARCHAR(60),
    status ENUM('pending','approved','rejected') DEFAULT 'pending',
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uniq_reg (tournament_id, user_id))");
} catch(Exception $e){}

$msg = '';

// ── POST HANDLERS ────────────────────────────────────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

  // Create tournament
  if ($isAdmin && isset($_POST['create_tourney'])) {
    $bp = handlePhotoUpload('banner','tournaments');
    db()->prepare("INSERT INTO tournaments(name,description,start_date,end_date,venue,prize,banner_photo,format,registration_open,created_by)VALUES(?,?,?,?,?,?,?,?,?,?)")
       ->execute([trim($_POST['tname']),trim($_POST['tdesc']??''),$_POST['tstart'],$_POST['tend'],trim($_POST['tvenue']??''),trim($_POST['tprize']??''),$bp,$_POST['tformat']??'league',(int)($_POST['reg_open']??1),$uid]);
    $msg = ['t'=>'ok','m'=>'✅ Tournament created!'];
  }

  // Delete tournament
  if ($isAdmin && isset($_POST['del_tournament'])) {
    $tid = (int)$_POST['del_tid'];
    if ($tid) {
      db()->prepare("DELETE FROM tournament_registrations WHERE tournament_id=?")->execute([$tid]);
      db()->prepare("DELETE FROM tournament_matches WHERE tournament_id=?")->execute([$tid]);
      db()->prepare("DELETE FROM tournament_teams WHERE tournament_id=?")->execute([$tid]);
      db()->prepare("DELETE FROM tournaments WHERE id=?")->execute([$tid]);
      $msg = ['t'=>'ok','m'=>'🗑 Tournament deleted.'];
    }
  }

  // Status change
  if ($isAdmin && isset($_POST['set_status'])) {
    $tid = (int)$_POST['status_tid'];
    $st  = in_array($_POST['new_status'],['upcoming','ongoing','completed']) ? $_POST['new_status'] : 'upcoming';
    db()->prepare("UPDATE tournaments SET status=? WHERE id=?")->execute([$st,$tid]);
    $msg = ['t'=>'ok','m'=>'✅ Status updated!'];
  }

  // Toggle registration
  if ($isAdmin && isset($_POST['toggle_reg'])) {
    $tid = (int)$_POST['reg_tid'];
    db()->prepare("UPDATE tournaments SET registration_open=1-registration_open WHERE id=?")->execute([$tid]);
    $msg = ['t'=>'ok','m'=>'✅ Registration updated!'];
  }

  // Add team manually
  if ($isAdmin && isset($_POST['add_team'])) {
    $tp = handlePhotoUpload('team_photo','teams');
    db()->prepare("INSERT INTO tournament_teams(tournament_id,team_name,captain,team_photo)VALUES(?,?,?,?)")
       ->execute([(int)$_POST['tid'],trim($_POST['team_name']),trim($_POST['captain']??''),$tp]);
    $msg = ['t'=>'ok','m'=>'✅ Team added!'];
  }

  // Auto-generate teams from registrations (random shuffle)
  if ($isAdmin && isset($_POST['auto_teams'])) {
    $tid    = (int)$_POST['auto_tid'];
    $tcount = max(2,(int)($_POST['team_count']??4));
    $regs   = db()->prepare("SELECT r.*,u.name uname FROM tournament_registrations r JOIN users u ON u.id=r.user_id WHERE r.tournament_id=? AND r.status='approved'");
    $regs->execute([$tid]); $regs = $regs->fetchAll();
    if (count($regs) >= $tcount) {
      shuffle($regs);
      $chunks = array_chunk($regs, (int)ceil(count($regs)/$tcount));
      foreach ($chunks as $gi => $group) {
        $tname   = 'Team '.chr(65+$gi);
        $captain = $group[0]['uname'] ?? 'TBD';
        db()->prepare("INSERT INTO tournament_teams(tournament_id,team_name,captain)VALUES(?,?,?)")->execute([$tid,$tname,$captain]);
      }
      $msg = ['t'=>'ok','m'=>'✅ '.count($chunks).' teams auto-generated from registrations!'];
    } else {
      $msg = ['t'=>'err','m'=>'❌ Not enough approved registrations ('.$tcount.' teams needed).'];
    }
  }

  // Delete team
  if ($isAdmin && isset($_POST['del_team'])) {
    db()->prepare("DELETE FROM tournament_teams WHERE id=?")->execute([(int)$_POST['del_team_id']]);
    $msg = ['t'=>'ok','m'=>'🗑 Team deleted.'];
  }

  // Schedule match
  if ($isAdmin && isset($_POST['add_match'])) {
    db()->prepare("INSERT INTO tournament_matches(tournament_id,team1_id,team2_id,match_date,match_time,venue,round,stage)VALUES(?,?,?,?,?,?,?,?)")
       ->execute([(int)$_POST['mid_t'],(int)$_POST['team1'],(int)$_POST['team2'],$_POST['mdate'],$_POST['mtime']??null,trim($_POST['mvenue']??''),trim($_POST['mround']??'Group Stage'),$_POST['mstage']??'group']);
    $msg = ['t'=>'ok','m'=>'✅ Match scheduled!'];
  }

  // Auto-generate league fixtures
  if ($isAdmin && isset($_POST['gen_fixtures'])) {
    $tid   = (int)$_POST['fix_tid'];
    $teams = db()->prepare("SELECT id,team_name FROM tournament_teams WHERE tournament_id=?");
    $teams->execute([$tid]); $teams = $teams->fetchAll();
    $n = count($teams);
    if ($n >= 2) {
      $baseDate = $_POST['fix_start_date'] ?? date('Y-m-d');
      $day = 0;
      for ($i = 0; $i < $n; $i++) {
        for ($j = $i+1; $j < $n; $j++) {
          $matchDate = date('Y-m-d', strtotime($baseDate.' +'.$day.' days'));
          db()->prepare("INSERT INTO tournament_matches(tournament_id,team1_id,team2_id,match_date,round,stage)VALUES(?,?,?,?,'Group Stage','group')")
             ->execute([$tid,$teams[$i]['id'],$teams[$j]['id'],$matchDate]);
          $day++;
        }
      }
      $msg = ['t'=>'ok','m'=>'✅ '.($n*($n-1)/2).' fixtures generated!'];
    }
  }

  // Delete match
  if ($isAdmin && isset($_POST['del_match'])) {
    db()->prepare("DELETE FROM tournament_matches WHERE id=?")->execute([(int)$_POST['del_match_id']]);
    $msg = ['t'=>'ok','m'=>'🗑 Match deleted.'];
  }

  // Update score
  if ($isAdmin && isset($_POST['update_score'])) {
    $rid=(int)$_POST['rid']; $g1=(int)$_POST['g1']; $g2=(int)$_POST['g2'];
    // Reset old result first
    $om = db()->prepare("SELECT * FROM tournament_matches WHERE id=?"); $om->execute([$rid]); $om = $om->fetch();
    if ($om && $om['status']==='completed') {
      // Reverse old scores
      $og1=$om['team1_goals']; $og2=$om['team2_goals'];
      if($og1>$og2){db()->prepare("UPDATE tournament_teams SET wins=wins-1,goals_for=goals_for-?,goals_against=goals_against-? WHERE id=?")->execute([$og1,$og2,$om['team1_id']]);db()->prepare("UPDATE tournament_teams SET losses=losses-1,goals_for=goals_for-?,goals_against=goals_against-? WHERE id=?")->execute([$og2,$og1,$om['team2_id']]);}
      elseif($og2>$og1){db()->prepare("UPDATE tournament_teams SET wins=wins-1,goals_for=goals_for-?,goals_against=goals_against-? WHERE id=?")->execute([$og2,$og1,$om['team2_id']]);db()->prepare("UPDATE tournament_teams SET losses=losses-1,goals_for=goals_for-?,goals_against=goals_against-? WHERE id=?")->execute([$og1,$og2,$om['team1_id']]);}
      else{db()->prepare("UPDATE tournament_teams SET draws=draws-1,goals_for=goals_for-?,goals_against=goals_against-? WHERE id=?")->execute([$og1,$og2,$om['team1_id']]);db()->prepare("UPDATE tournament_teams SET draws=draws-1,goals_for=goals_for-?,goals_against=goals_against-? WHERE id=?")->execute([$og2,$og1,$om['team2_id']]);}
    }
    db()->prepare("UPDATE tournament_matches SET team1_goals=?,team2_goals=?,status='completed' WHERE id=?")->execute([$g1,$g2,$rid]);
    $m = db()->prepare("SELECT * FROM tournament_matches WHERE id=?"); $m->execute([$rid]); $m = $m->fetch();
    if($g1>$g2){db()->prepare("UPDATE tournament_teams SET wins=wins+1,goals_for=goals_for+?,goals_against=goals_against+? WHERE id=?")->execute([$g1,$g2,$m['team1_id']]);db()->prepare("UPDATE tournament_teams SET losses=losses+1,goals_for=goals_for+?,goals_against=goals_against+? WHERE id=?")->execute([$g2,$g1,$m['team2_id']]);}
    elseif($g2>$g1){db()->prepare("UPDATE tournament_teams SET wins=wins+1,goals_for=goals_for+?,goals_against=goals_against+? WHERE id=?")->execute([$g2,$g1,$m['team2_id']]);db()->prepare("UPDATE tournament_teams SET losses=losses+1,goals_for=goals_for+?,goals_against=goals_against+? WHERE id=?")->execute([$g1,$g2,$m['team1_id']]);}
    else{db()->prepare("UPDATE tournament_teams SET draws=draws+1,goals_for=goals_for+?,goals_against=goals_against+? WHERE id=?")->execute([$g1,$g2,$m['team1_id']]);db()->prepare("UPDATE tournament_teams SET draws=draws+1,goals_for=goals_for+?,goals_against=goals_against+? WHERE id=?")->execute([$g2,$g1,$m['team2_id']]);}
    $msg = ['t'=>'ok','m'=>'✅ Score updated!'];
  }

  // Member register for tournament
  if (isset($_POST['join_tournament'])) {
    $tid  = (int)$_POST['reg_tid'];
    $pos  = trim($_POST['position']??'');
    $name = trim($_POST['player_name']??$user['name']);
    $treg = db()->prepare("SELECT * FROM tournaments WHERE id=?"); $treg->execute([$tid]); $treg = $treg->fetch();
    if ($treg && $treg['registration_open']) {
      // Auto-approve if member has a valid active subscription
      $hasSub = false;
      try {
        // Check subscription_requests (approved + not expired)
        $subCheck = db()->prepare("SELECT id FROM subscription_requests WHERE user_id=? AND status='approved' AND valid_until >= CURDATE() LIMIT 1");
        $subCheck->execute([$uid]); $hasSub = (bool)$subCheck->fetch();
        // Also check subscriptions table
        if (!$hasSub) {
          $subCheck2 = db()->prepare("SELECT id FROM subscriptions WHERE user_id=? AND valid_until >= CURDATE() LIMIT 1");
          $subCheck2->execute([$uid]); $hasSub = (bool)$subCheck2->fetch();
        }
      } catch(Exception $e){}

      $autoStatus = $hasSub ? 'approved' : 'pending';
      $autoMsg    = $hasSub
        ? '✅ Registered & auto-approved! Your active subscription qualifies you.'
        : '⏳ Registered! Awaiting admin approval.';

      try {
        db()->prepare("INSERT INTO tournament_registrations(tournament_id,user_id,player_name,position,status)VALUES(?,?,?,?,?)")
           ->execute([$tid,$uid,$name,$pos,$autoStatus]);
        $msg = ['t'=>'ok','m'=>$autoMsg];
      } catch(Exception $e) {
        $msg = ['t'=>'err','m'=>'❌ Already registered for this tournament.'];
      }
    }
  }

  // Admin approve/reject registration
  if ($isAdmin && isset($_POST['reg_action'])) {
    $rid = (int)$_POST['reg_id'];
    $act = $_POST['reg_action'];
    if (in_array($act,['approved','rejected'])) {
      db()->prepare("UPDATE tournament_registrations SET status=? WHERE id=?")->execute([$act,$rid]);
      $msg = ['t'=>'ok','m'=>'✅ Registration '.$act.'!'];
    }
  }

  if ($msg) { header('Location:'.url('modules/football.php').'?msg='.urlencode($msg['m']).'&mt='.$msg['t']); exit; }
}

if (isset($_GET['msg'])) $msg = ['t'=>$_GET['mt']??'ok','m'=>$_GET['msg']];

$tournaments = db()->query("SELECT * FROM tournaments WHERE sport='football' ORDER BY created_at DESC")->fetchAll();
require_once __DIR__ . '/../includes/header.php';
?>
<style>
.ft-hero{background:linear-gradient(135deg,#1B5E20,#2E7D32,#388E3C);padding:2rem 1.2rem 1.8rem;text-align:center}
.ft-hero h1{font-family:'Bebas Neue',sans-serif;font-size:2rem;color:#fff;letter-spacing:.08em}
.ft-hero h1 span{color:#A5D6A7}
.t-card{background:#fff;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,.1);overflow:hidden;margin-bottom:1.5rem}
.t-banner{position:relative;width:100%;min-height:160px;background:linear-gradient(135deg,#1B5E20,#388E3C);overflow:hidden}
.t-banner img{width:100%;max-height:200px;object-fit:cover;display:block}
.t-banner-ov{position:absolute;inset:0;background:linear-gradient(to bottom,transparent 40%,rgba(0,0,0,.7))}
.t-banner-info{position:absolute;bottom:.8rem;left:1rem;right:1rem;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:.4rem;z-index:2}
.t-banner-title{font-family:'Bebas Neue',sans-serif;font-size:1.5rem;color:#fff;letter-spacing:.05em;line-height:1.1}
.t-badge{border-radius:20px;padding:.2rem .8rem;font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em}
.t-admin-bar{background:#f8f9fc;border-bottom:1px solid #e8ecf4;padding:.6rem 1rem;display:flex;gap:.4rem;flex-wrap:wrap;align-items:center}
.tab-pill{padding:.35rem .85rem;border-radius:20px;border:1.5px solid #e0e7ff;font-size:.74rem;font-weight:700;cursor:pointer;background:#fff;color:#0d47a1;transition:all .2s}
.tab-pill.on{background:#0d47a1;color:#fff;border-color:#0d47a1}
.tab-pane{display:none;padding:1rem}.tab-pane.on{display:block}
.reg-card{background:#f8fafc;border-radius:10px;padding:.7rem .9rem;margin-bottom:.5rem;display:flex;align-items:center;justify-content:space-between;gap:.5rem;flex-wrap:wrap}
.bracket-wrap{overflow-x:auto;padding:.5rem 0}
.bracket{display:flex;gap:1.5rem;align-items:flex-start;min-width:max-content}
.bracket-round{display:flex;flex-direction:column;gap:.6rem;min-width:160px}
.bracket-round h5{font-size:.64rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:#0d47a1;text-align:center;padding:.3rem;background:#e3f2fd;border-radius:6px;margin-bottom:.2rem}
.bracket-match{background:#fff;border:1.5px solid #e0e7ff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.bracket-team{display:flex;align-items:center;justify-content:space-between;padding:.45rem .7rem;font-size:.8rem;font-weight:700;border-bottom:1px solid #f0f4f8;gap:.4rem}
.bracket-team:last-child{border-bottom:none}
.bracket-team.winner{background:#f1f8e9;color:#1b5e20}
.bracket-score{background:#0d47a1;color:#fff;border-radius:5px;padding:.1rem .45rem;font-size:.78rem;min-width:22px;text-align:center}
.league-table{width:100%;border-collapse:collapse;font-size:.82rem}
.league-table th{background:#1b5e20;color:#fff;padding:.55rem .6rem;font-size:.65rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em}
.league-table td{padding:.55rem .6rem;border-bottom:1px solid #f0f4f8;vertical-align:middle}
.league-table tr:first-child td{background:#f1f8e9;font-weight:700}
.league-table tr:nth-child(2) td{background:#fafffe}
.match-row{background:#f8fafc;border-radius:10px;padding:.7rem 1rem;margin-bottom:.5rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem}
.score-box{background:#0d47a1;color:#fff;border-radius:8px;padding:.25rem .9rem;font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:.06em}
.team-avatar{width:36px;height:36px;border-radius:50%;object-fit:cover;border:2px solid #e0e7ff}
.team-avatar-ph{width:36px;height:36px;border-radius:50%;background:#e3f2fd;display:flex;align-items:center;justify-content:center;font-size:1rem;border:2px solid #e0e7ff;flex-shrink:0}
.inp-sm{padding:.45rem .7rem;border:1.5px solid #e0e7ff;border-radius:8px;font-family:Inter,sans-serif;font-size:.85rem;width:100%;outline:none}
.inp-sm:focus{border-color:#0d47a1}
.btn-g{background:#1b5e20;color:#fff;border:none;border-radius:8px;padding:.5rem 1rem;font-weight:700;font-size:.8rem;cursor:pointer}
.btn-b{background:#0d47a1;color:#fff;border:none;border-radius:8px;padding:.5rem 1rem;font-weight:700;font-size:.8rem;cursor:pointer}
.btn-r{background:#b71c1c;color:#fff;border:none;border-radius:8px;padding:.4rem .8rem;font-weight:700;font-size:.75rem;cursor:pointer}
.btn-o{background:#e65100;color:#fff;border:none;border-radius:8px;padding:.5rem 1rem;font-weight:700;font-size:.8rem;cursor:pointer}
.fg-row{display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.6rem}
</style>

<div class="ft-hero">
  <h1>⚽ FOOTBALL <span>TOURNAMENT</span></h1>
  <div style="color:rgba(255,255,255,.7);font-size:.82rem;margin-top:.3rem"><?= h(setting('CLUB_NAME','Aishwarya Arts & Sports Club')) ?></div>
</div>
<div class="red-bar"></div>
<div class="section" style="max-width:960px;padding-top:1.2rem">

<?php if ($msg): ?>
<div style="background:<?=$msg['t']==='ok'?'#f0fdf4':'#fff0f0'?>;border:1.5px solid <?=$msg['t']==='ok'?'#bbf7d0':'#fecaca'?>;color:<?=$msg['t']==='ok'?'#166534':'#991b1b'?>;border-radius:10px;padding:.75rem 1rem;margin-bottom:1rem;font-weight:700;font-size:.88rem">
  <?= h($msg['m']) ?>
</div>
<?php endif; ?>

<!-- ══ CREATE TOURNAMENT (admin) ══ -->
<?php if ($isAdmin): ?>
<div style="background:#fff;border-radius:14px;box-shadow:0 2px 12px rgba(0,0,0,.08);overflow:hidden;margin-bottom:1.5rem">
  <button onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'" style="width:100%;background:linear-gradient(135deg,#1b5e20,#2e7d32);color:#fff;border:none;padding:.9rem 1.2rem;font-family:'Bebas Neue',sans-serif;font-size:1rem;letter-spacing:.07em;cursor:pointer;display:flex;align-items:center;gap:.5rem">
    ➕ CREATE NEW TOURNAMENT <span style="margin-left:auto;font-size:.8rem">▼</span>
  </button>
  <div style="display:none;padding:1.2rem">
    <form method="POST" action="<?=url('modules/football.php')?>" enctype="multipart/form-data">
      <div class="fg-row">
        <div><label style="font-size:.72rem;font-weight:700;color:#64748b;text-transform:uppercase;display:block;margin-bottom:.3rem">Tournament Name *</label><input type="text" name="tname" class="inp-sm" required placeholder="e.g. AASC Cup 2025"></div>
        <div><label style="font-size:.72rem;font-weight:700;color:#64748b;text-transform:uppercase;display:block;margin-bottom:.3rem">Format</label>
          <select name="tformat" class="inp-sm">
            <option value="league">🔄 League (All vs All)</option>
            <option value="knockout">⚔️ Knockout</option>
            <option value="group_knockout">🏆 Group Stage + Knockout</option>
          </select></div>
        <div><label style="font-size:.72rem;font-weight:700;color:#64748b;text-transform:uppercase;display:block;margin-bottom:.3rem">Venue</label><input type="text" name="tvenue" class="inp-sm" placeholder="Ground name"></div>
        <div><label style="font-size:.72rem;font-weight:700;color:#64748b;text-transform:uppercase;display:block;margin-bottom:.3rem">Prize</label><input type="text" name="tprize" class="inp-sm" placeholder="₹5000 + Trophy"></div>
        <div><label style="font-size:.72rem;font-weight:700;color:#64748b;text-transform:uppercase;display:block;margin-bottom:.3rem">Start Date</label><input type="date" name="tstart" class="inp-sm" value="<?=date('Y-m-d')?>"></div>
        <div><label style="font-size:.72rem;font-weight:700;color:#64748b;text-transform:uppercase;display:block;margin-bottom:.3rem">End Date</label><input type="date" name="tend" class="inp-sm" value="<?=date('Y-m-d',strtotime('+14 days'))?>"></div>
      </div>
      <div style="margin-bottom:.6rem"><label style="font-size:.72rem;font-weight:700;color:#64748b;text-transform:uppercase;display:block;margin-bottom:.3rem">Banner Photo</label>
        <input type="file" name="banner" accept="image/*" style="width:100%;padding:.45rem;border:1.5px dashed #c7d2fe;border-radius:8px;font-size:.82rem"></div>
      <div style="margin-bottom:.6rem"><label style="font-size:.72rem;font-weight:700;color:#64748b;text-transform:uppercase;display:block;margin-bottom:.3rem">Description</label>
        <textarea name="tdesc" class="inp-sm" rows="2" style="resize:vertical"></textarea></div>
      <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.8rem">
        <input type="checkbox" name="reg_open" value="1" id="ro" checked style="width:16px;height:16px;accent-color:#1b5e20">
        <label for="ro" style="font-size:.82rem;font-weight:600;color:#374151">Allow member registration</label>
      </div>
      <button type="submit" name="create_tourney" class="btn-g" style="padding:.65rem 1.4rem">⚽ Create Tournament</button>
    </form>
  </div>
</div>
<?php endif; ?>

<!-- ══ TOURNAMENT LIST ══ -->
<?php if (empty($tournaments)): ?>
<div style="text-align:center;padding:4rem;color:#94a3b8">
  <div style="font-size:4rem;margin-bottom:1rem">⚽</div>
  <h3 style="margin-bottom:.5rem;color:#475569">No tournaments yet</h3>
  <p style="font-size:.85rem">Football tournament announcements will appear here.</p>
</div>
<?php else: foreach ($tournaments as $ti=>$t):
  $tid    = $t['id'];
  $teams  = db()->prepare("SELECT *,(wins*3+draws) pts FROM tournament_teams WHERE tournament_id=? ORDER BY (wins*3+draws) DESC,(goals_for-goals_against) DESC,goals_for DESC");
  $teams->execute([$tid]); $teams = $teams->fetchAll();
  $allMatches = db()->prepare("SELECT m.*,t1.team_name t1n,t1.team_photo t1p,t2.team_name t2n,t2.team_photo t2p FROM tournament_matches m JOIN tournament_teams t1 ON t1.id=m.team1_id JOIN tournament_teams t2 ON t2.id=m.team2_id WHERE m.tournament_id=? ORDER BY m.match_date,m.match_time");
  $allMatches->execute([$tid]); $allMatches = $allMatches->fetchAll();
  $regs = [];
  if ($isAdmin) {
    $rq = db()->prepare("SELECT r.*,u.name uname,u.blood_group bld,
      (SELECT COUNT(*) FROM subscription_requests sr
       WHERE sr.user_id=r.user_id AND sr.status='approved' AND sr.valid_until>=CURDATE()) +
      (SELECT COUNT(*) FROM subscriptions s
       WHERE s.user_id=r.user_id AND s.valid_until>=CURDATE()) AS has_sub
      FROM tournament_registrations r JOIN users u ON u.id=r.user_id
      WHERE r.tournament_id=? ORDER BY r.registered_at");
    $rq->execute([$tid]); $regs = $rq->fetchAll();
  }
  $myReg = null;
  try {
    $mr = db()->prepare("SELECT * FROM tournament_registrations WHERE tournament_id=? AND user_id=?");
    $mr->execute([$tid,$uid]); $myReg = $mr->fetch();
  } catch(Exception $e){}
  $sc = ['upcoming'=>['#FFF8E1','#E65100'],'ongoing'=>['#E8F5E9','#1B5E20'],'completed'=>['#E3F2FD','#07225c']];
  $s  = $sc[$t['status']] ?? ['#F5F5F5','#555'];
  $tabId = 'tc'.$tid;
?>

<div class="t-card" id="tour_<?=$tid?>">
  <!-- Banner -->
  <div class="t-banner">
    <?php if (!empty($t['banner_photo'])): ?>
    <img src="<?=url('assets/uploads/'.$t['banner_photo'])?>" alt="">
    <div class="t-banner-ov"></div>
    <?php else: ?>
    <div style="height:120px;display:flex;align-items:center;justify-content:center;font-size:4rem;opacity:.3">⚽</div>
    <?php endif; ?>
    <div class="t-banner-info" style="<?=empty($t['banner_photo'])?'position:relative;padding:.7rem 1rem':''?>">
      <div>
        <div class="t-banner-title" style="<?=empty($t['banner_photo'])?'color:#fff':''?>"><?=h($t['name'])?></div>
        <div style="font-size:.7rem;color:<?=empty($t['banner_photo'])?'rgba(255,255,255,.7)':'rgba(255,255,255,.8)'?>"><?=h($t['venue']??'')?> · <?=date('d M',strtotime($t['start_date']))?> – <?=date('d M Y',strtotime($t['end_date']))?></div>
      </div>
      <span class="t-badge" style="background:<?=$s[0]?>;color:<?=$s[1]?>"><?=strtoupper($t['status'])?></span>
    </div>
  </div>

  <!-- Admin controls bar -->
  <?php if ($isAdmin): ?>
  <div class="t-admin-bar">
    <span style="font-size:.72rem;font-weight:700;color:#64748b;margin-right:.2rem">Admin:</span>
    <!-- Status -->
    <form method="POST" style="display:inline">
      <input type="hidden" name="status_tid" value="<?=$tid?>">
      <input type="hidden" name="set_status" value="1">
      <select name="new_status" onchange="this.form.submit()" style="font-size:.72rem;padding:.25rem .5rem;border-radius:8px;border:1.5px solid #e0e7ff;font-weight:700;cursor:pointer;background:#fff">
        <option value="upcoming"  <?=$t['status']==='upcoming' ?'selected':''?>>Upcoming</option>
        <option value="ongoing"   <?=$t['status']==='ongoing'  ?'selected':''?>>Ongoing</option>
        <option value="completed" <?=$t['status']==='completed'?'selected':''?>>Completed</option>
      </select>
    </form>
    <!-- Toggle registration -->
    <form method="POST" style="display:inline">
      <input type="hidden" name="reg_tid" value="<?=$tid?>">
      <button type="submit" name="toggle_reg" style="font-size:.72rem;padding:.28rem .7rem;border-radius:8px;border:1.5px solid <?=$t['registration_open']?'#bbf7d0':'#fecaca'?>;background:<?=$t['registration_open']?'#f0fdf4':'#fff0f0'?>;color:<?=$t['registration_open']?'#166534':'#991b1b'?>;font-weight:700;cursor:pointer">
        <?=$t['registration_open']?'🟢 Reg: Open':'🔴 Reg: Closed'?>
      </button>
    </form>
    <!-- Delete -->
    <form method="POST" style="display:inline;margin-left:auto" onsubmit="return confirm('⚠️ DELETE this entire tournament including all teams and matches? This CANNOT be undone.')">
      <input type="hidden" name="del_tid" value="<?=$tid?>">
      <button type="submit" name="del_tournament" style="font-size:.72rem;padding:.28rem .7rem;border-radius:8px;border:1.5px solid #fecaca;background:#fff0f0;color:#991b1b;font-weight:700;cursor:pointer">🗑 Delete Tournament</button>
    </form>
  </div>
  <?php endif; ?>

  <!-- Tabs -->
  <div style="display:flex;gap:.3rem;padding:.7rem 1rem .3rem;border-bottom:1px solid #f0f4f8;overflow-x:auto;scrollbar-width:none">
    <button class="tab-pill on" onclick="switchTab('<?=$tabId?>','standings',this)">🏆 Table</button>
    <button class="tab-pill" onclick="switchTab('<?=$tabId?>','matches',this)">📅 Matches</button>
    <button class="tab-pill" onclick="switchTab('<?=$tabId?>','bracket',this)">🔲 Bracket</button>
    <button class="tab-pill" onclick="switchTab('<?=$tabId?>','register',this)">📝 Register</button>
    <?php if ($isAdmin): ?>
    <button class="tab-pill" onclick="switchTab('<?=$tabId?>','manage',this)">⚙️ Manage</button>
    <?php endif; ?>
  </div>

  <!-- TAB: STANDINGS -->
  <div class="tab-pane on" id="<?=$tabId?>_standings">
    <?php if (empty($teams)): ?>
    <div style="text-align:center;padding:2rem;color:#94a3b8;font-size:.85rem">No teams yet. Admin adds teams in Manage tab.</div>
    <?php else: ?>
    <div style="margin-bottom:.5rem;font-size:.72rem;color:#64748b">Format: <strong><?=$t['format']==='league'?'League':'Knockout'?></strong> · <?=count($teams)?> teams</div>
    <div style="overflow-x:auto;border-radius:10px;margin-bottom:.5rem">
    <table class="league-table">
      <thead><tr>
        <th style="width:28px">#</th>
        <th style="text-align:left">Team</th>
        <th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>PTS</th>
        <?php if ($isAdmin): ?><th></th><?php endif; ?>
      </tr></thead>
      <tbody>
      <?php foreach ($teams as $ri=>$tm):
        $tp = !empty($tm['team_photo']) ? url('assets/uploads/teams/'.$tm['team_photo']) : '';
      ?>
      <tr>
        <td style="text-align:center"><?=$ri===0?'🥇':($ri===1?'🥈':($ri===2?'🥉':$ri+1))?></td>
        <td>
          <div style="display:flex;align-items:center;gap:.5rem">
            <?php if ($tp): ?><img src="<?=$tp?>" class="team-avatar" alt=""><?php else: ?><div class="team-avatar-ph">⚽</div><?php endif; ?>
            <div>
              <div style="font-weight:700"><?=h($tm['team_name'])?></div>
              <?php if ($tm['captain']): ?><div style="font-size:.65rem;color:#94a3b8">Captain: <?=h($tm['captain'])?></div><?php endif; ?>
            </div>
          </div>
        </td>
        <td style="text-align:center;color:#1b5e20;font-weight:700"><?=$tm['wins']?></td>
        <td style="text-align:center"><?=$tm['draws']?></td>
        <td style="text-align:center;color:#b71c1c"><?=$tm['losses']?></td>
        <td style="text-align:center"><?=$tm['goals_for']?></td>
        <td style="text-align:center"><?=$tm['goals_against']?></td>
        <td style="text-align:center;font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:#0d47a1"><?=$tm['pts']?></td>
        <?php if ($isAdmin): ?>
        <td>
          <form method="POST" style="display:inline" onsubmit="return confirm('Delete team?')">
            <input type="hidden" name="del_team_id" value="<?=$tm['id']?>">
            <button type="submit" name="del_team" style="background:none;border:none;color:#b71c1c;cursor:pointer;font-size:.9rem">🗑</button>
          </form>
        </td>
        <?php endif; ?>
      </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
    </div>
    <div style="font-size:.68rem;color:#94a3b8;padding:.2rem .2rem .5rem">🥇 Top team advances · PTS = 3×Wins + Draws</div>
    <?php endif; ?>
  </div>

  <!-- TAB: MATCHES -->
  <div class="tab-pane" id="<?=$tabId?>_matches">
    <?php if (empty($allMatches)): ?>
    <div style="text-align:center;padding:2rem;color:#94a3b8;font-size:.85rem">No matches scheduled yet.</div>
    <?php else:
      $rounds = [];
      foreach ($allMatches as $mx) { $rounds[$mx['round']][] = $mx; }
      foreach ($rounds as $rname=>$rmatches):
    ?>
    <div style="font-size:.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:#0d47a1;margin-bottom:.4rem;margin-top:.8rem"><?=h($rname)?></div>
    <?php foreach ($rmatches as $mx):
      $t1p = !empty($mx['t1p']) ? url('assets/uploads/teams/'.$mx['t1p']) : '';
      $t2p = !empty($mx['t2p']) ? url('assets/uploads/teams/'.$mx['t2p']) : '';
    ?>
    <div class="match-row">
      <div style="font-size:.68rem;color:#94a3b8;width:100%"><?=date('d M Y',strtotime($mx['match_date']))?><?php if($mx['match_time']): ?> · <?=date('g:i A',strtotime($mx['match_time']))?><?php endif; ?> <?php if($mx['venue']): ?>· <?=h($mx['venue'])?><?php endif; ?></div>
      <div style="display:flex;align-items:center;gap:.6rem;flex:1;justify-content:center">
        <div style="display:flex;align-items:center;gap:.4rem">
          <?php if ($t1p): ?><img src="<?=$t1p?>" class="team-avatar" alt=""><?php endif; ?>
          <span style="font-weight:700;font-size:.9rem"><?=h($mx['t1n'])?></span>
        </div>
        <?php if ($mx['status']==='completed'): ?>
        <span class="score-box"><?=$mx['team1_goals']?> – <?=$mx['team2_goals']?></span>
        <?php elseif ($mx['status']==='live'): ?>
        <span style="background:#e65100;color:#fff;border-radius:8px;padding:.2rem .8rem;font-size:.75rem;font-weight:800;animation:livePulse 1.2s ease-in-out infinite">🔴 LIVE</span>
        <?php else: ?>
        <span style="background:#f0f4f8;color:#64748b;border-radius:8px;padding:.2rem .8rem;font-size:.78rem">VS</span>
        <?php endif; ?>
        <div style="display:flex;align-items:center;gap:.4rem">
          <span style="font-weight:700;font-size:.9rem"><?=h($mx['t2n'])?></span>
          <?php if ($t2p): ?><img src="<?=$t2p?>" class="team-avatar" alt=""><?php endif; ?>
        </div>
      </div>
      <?php if ($mx['status']==='completed'): ?>
      <span style="font-size:.68rem;color:#1b5e20;font-weight:700;width:100%;text-align:center">✅ Final</span>
      <?php endif; ?>
      <?php if ($isAdmin): ?>
      <div style="display:flex;gap:.4rem;align-items:center;width:100%;margin-top:.3rem">
        <form method="POST" style="display:flex;gap:.4rem;align-items:center;flex:1">
          <input type="hidden" name="rid" value="<?=$mx['id']?>">
          <input type="number" name="g1" min="0" max="30" value="<?=$mx['team1_goals']?>" class="inp-sm" style="width:52px;text-align:center">
          <span style="font-weight:700;color:#64748b">:</span>
          <input type="number" name="g2" min="0" max="30" value="<?=$mx['team2_goals']?>" class="inp-sm" style="width:52px;text-align:center">
          <button type="submit" name="update_score" class="btn-g" style="padding:.4rem .8rem;font-size:.75rem">✅</button>
        </form>
        <form method="POST" onsubmit="return confirm('Delete match?')">
          <input type="hidden" name="del_match_id" value="<?=$mx['id']?>">
          <button type="submit" name="del_match" class="btn-r">🗑</button>
        </form>
      </div>
      <?php endif; ?>
    </div>
    <?php endforeach; endforeach; endif; ?>
  </div>

  <!-- TAB: BRACKET / FIXTURE CHART -->
  <div class="tab-pane" id="<?=$tabId?>_bracket">
    <?php
    $byRound = [];
    foreach ($allMatches as $mx) { $byRound[$mx['stage']][$mx['round']][] = $mx; }
    if (empty($byRound)):
    ?>
    <div style="text-align:center;padding:2rem;color:#94a3b8">
      <div style="font-size:2.5rem;margin-bottom:.5rem">🔲</div>
      <p style="font-size:.85rem">No matches scheduled yet. Bracket will appear once admin schedules matches.</p>
    </div>
    <?php else: ?>
    <?php if ($t['format']==='league' || $t['format']==='group_knockout'): ?>
    <!-- League table is in standings tab, show match grid here -->
    <div style="font-size:.75rem;font-weight:700;color:#0d47a1;margin-bottom:.75rem">📊 Match Grid</div>
    <?php
    $n = count($teams);
    if ($n > 1):
    ?>
    <div style="overflow-x:auto">
    <table style="border-collapse:collapse;font-size:.72rem;min-width:max-content">
      <thead>
        <tr>
          <th style="background:#e3f2fd;color:#0d47a1;padding:.4rem .5rem;border:1px solid #c7d2fe;font-size:.65rem">Team</th>
          <?php foreach ($teams as $th): ?>
          <th style="background:#e3f2fd;color:#0d47a1;padding:.4rem .5rem;border:1px solid #c7d2fe;font-size:.62rem;max-width:60px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><?=h(mb_strimwidth($th['team_name'],0,8,'…'))?></th>
          <?php endforeach; ?>
        </tr>
      </thead>
      <tbody>
      <?php foreach ($teams as $row): ?>
      <tr>
        <td style="background:#f8fafc;font-weight:700;padding:.4rem .5rem;border:1px solid #e0e7ff;white-space:nowrap"><?=h($row['team_name'])?></td>
        <?php foreach ($teams as $col): ?>
        <?php
        if ($row['id'] === $col['id']) {
            echo '<td style="background:#e3f2fd;border:1px solid #e0e7ff;text-align:center;color:#0d47a1;font-weight:900">—</td>';
            continue;
        }
        $found = null;
        foreach ($allMatches as $mx) {
            if (($mx['team1_id']==$row['id']&&$mx['team2_id']==$col['id'])||($mx['team1_id']==$col['id']&&$mx['team2_id']==$row['id'])) {
                $found=$mx; break;
            }
        }
        if (!$found) { echo '<td style="border:1px solid #e0e7ff;text-align:center;color:#c7d2fe;padding:.4rem .5rem">·</td>'; }
        elseif ($found['status']==='completed') {
            $g1 = ($found['team1_id']==$row['id']) ? $found['team1_goals'] : $found['team2_goals'];
            $g2 = ($found['team1_id']==$row['id']) ? $found['team2_goals'] : $found['team1_goals'];
            $bg = $g1>$g2?'#f0fdf4':($g1<$g2?'#fff0f0':'#f8fafc');
            $co = $g1>$g2?'#166534':($g1<$g2?'#991b1b':'#374151');
            echo '<td style="background:'.$bg.';color:'.$co.';font-weight:700;border:1px solid #e0e7ff;text-align:center;padding:.4rem .5rem">'.$g1.'-'.$g2.'</td>';
        } else {
            echo '<td style="border:1px solid #e0e7ff;text-align:center;color:#94a3b8;font-size:.68rem;padding:.4rem .5rem">TBD</td>';
        }
        ?>
        <?php endforeach; ?>
      </tr>
      <?php endforeach; ?>
      </tbody>
    </table>
    </div>
    <?php endif; ?>
    <?php endif; ?>

    <?php if (!empty($byRound['knockout']) || $t['format']==='knockout' || $t['format']==='group_knockout'): ?>
    <!-- Knockout bracket -->
    <div style="font-size:.75rem;font-weight:700;color:#e65100;margin:1rem 0 .6rem">⚔️ Knockout Bracket</div>
    <div class="bracket-wrap">
      <div class="bracket">
        <?php
        $koRounds = isset($byRound['knockout']) ? $byRound['knockout'] : (isset($byRound['group']) ? [] : array_values($byRound)[0]??[]);
        if (is_array($koRounds)) foreach ($koRounds as $rn=>$rms):
        ?>
        <div class="bracket-round">
          <h5><?=h($rn)?></h5>
          <?php foreach ($rms as $bm):
            $w1 = $bm['status']==='completed' && $bm['team1_goals']>$bm['team2_goals'];
            $w2 = $bm['status']==='completed' && $bm['team2_goals']>$bm['team1_goals'];
          ?>
          <div class="bracket-match">
            <div class="bracket-team <?=$w1?'winner':''?>">
              <span><?=h($bm['t1n'])?></span>
              <?php if($bm['status']==='completed'): ?><span class="bracket-score"><?=$bm['team1_goals']?></span><?php endif; ?>
            </div>
            <div class="bracket-team <?=$w2?'winner':''?>">
              <span><?=h($bm['t2n'])?></span>
              <?php if($bm['status']==='completed'): ?><span class="bracket-score"><?=$bm['team2_goals']?></span><?php endif; ?>
            </div>
          </div>
          <?php endforeach; ?>
        </div>
        <?php endforeach; ?>
      </div>
    </div>
    <?php endif; ?>
    <?php endif; ?>
  </div>

  <!-- TAB: REGISTER -->
  <div class="tab-pane" id="<?=$tabId?>_register">
    <?php if ($myReg): ?>
    <div style="background:<?=$myReg['status']==='approved'?'#f0fdf4':($myReg['status']==='rejected'?'#fff0f0':'#fff8e1')?>;border-radius:10px;padding:1rem;text-align:center">
      <div style="font-size:1.8rem;margin-bottom:.4rem"><?=$myReg['status']==='approved'?'✅':($myReg['status']==='rejected'?'❌':'⏳')?></div>
      <div style="font-weight:700;font-size:.9rem">Your registration: <span style="color:<?=$myReg['status']==='approved'?'#166534':($myReg['status']==='rejected'?'#991b1b':'#92400e')?>"><?=strtoupper($myReg['status'])?></span></div>
      <div style="font-size:.78rem;color:#64748b;margin-top:.3rem">Player: <?=h($myReg['player_name'])?> · Position: <?=h($myReg['position']??'—')?></div>
    </div>
    <?php elseif ($t['registration_open']): ?>
    <div style="background:#f0fdf4;border-radius:10px;padding:.85rem 1rem;margin-bottom:.8rem">
      <div style="font-weight:700;font-size:.85rem;color:#166534;margin-bottom:.3rem">🟢 Registration Open</div>
      <div style="font-size:.78rem;color:#374151">Register to join this tournament. Admin will form teams from registrations.</div>
    </div>
    <form method="POST">
      <input type="hidden" name="reg_tid" value="<?=$tid?>">
      <div class="fg-row" style="margin-bottom:.6rem">
        <div><label style="font-size:.72rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Your Name</label>
          <input type="text" name="player_name" class="inp-sm" value="<?=h($user['name'])?>" required></div>
        <div><label style="font-size:.72rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Position</label>
          <select name="position" class="inp-sm">
            <option value="">Any</option>
            <option>Goalkeeper</option><option>Defender</option>
            <option>Midfielder</option><option>Striker</option>
          </select></div>
      </div>
      <button type="submit" name="join_tournament" class="btn-g" style="padding:.65rem 1.4rem">📝 Register Now</button>
    </form>
    <?php else: ?>
    <div style="text-align:center;padding:2rem;color:#94a3b8">
      <div style="font-size:2rem;margin-bottom:.4rem">🔒</div>
      <div style="font-size:.85rem">Registration is currently closed.</div>
    </div>
    <?php endif; ?>

    <!-- Registrations list (admin only) -->
    <?php if ($isAdmin && !empty($regs)): ?>
    <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #f0f4f8">
      <div style="font-size:.78rem;font-weight:700;color:#0d47a1;margin-bottom:.6rem">📋 Registrations (<?=count($regs)?>)</div>
      <?php foreach ($regs as $rg): ?>
      <div class="reg-card">
        <div>
          <div style="font-weight:700;font-size:.85rem;display:flex;align-items:center;gap:.4rem">
            <?=h($rg['uname'])?>
            <?php if($rg['has_sub']): ?>
            <span style="background:#e8f5e9;color:#1b5e20;border-radius:20px;padding:.08rem .45rem;font-size:.6rem;font-weight:800">✅ Subscriber</span>
            <?php else: ?>
            <span style="background:#fff8e1;color:#92400e;border-radius:20px;padding:.08rem .45rem;font-size:.6rem;font-weight:800">⚠️ No Sub</span>
            <?php endif; ?>
          </div>
          <div style="font-size:.72rem;color:#64748b">Pos: <?=h($rg['position']??'Any')?> <?php if($rg['bld']): ?>· Blood: <span style="color:#b71c1c;font-weight:700"><?=h($rg['bld'])?></span><?php endif; ?></div>
        </div>
        <div style="display:flex;gap:.35rem;align-items:center">
          <?php if ($rg['status']==='pending'): ?>
          <form method="POST" style="display:flex;gap:.3rem">
            <input type="hidden" name="reg_id" value="<?=$rg['id']?>">
            <button name="reg_action" value="approved" class="btn-g" style="padding:.3rem .7rem;font-size:.72rem">✅</button>
            <button name="reg_action" value="rejected" class="btn-r" style="padding:.3rem .7rem;font-size:.72rem">❌</button>
          </form>
          <?php else: ?>
          <span style="font-size:.7rem;font-weight:700;padding:.2rem .6rem;border-radius:20px;background:<?=$rg['status']==='approved'?'#f0fdf4':'#fff0f0'?>;color:<?=$rg['status']==='approved'?'#166534':'#991b1b'?>"><?=ucfirst($rg['status'])?></span>
          <?php endif; ?>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>
  </div>

  <!-- TAB: MANAGE (admin only) -->
  <?php if ($isAdmin): ?>
  <div class="tab-pane" id="<?=$tabId?>_manage">

    <!-- Add Team Manually -->
    <div style="background:#f8fafc;border-radius:12px;padding:1rem;margin-bottom:1rem">
      <div style="font-weight:700;font-size:.85rem;color:#1b5e20;margin-bottom:.75rem">➕ Add Team Manually</div>
      <form method="POST" action="<?=url('modules/football.php')?>" enctype="multipart/form-data">
        <input type="hidden" name="tid" value="<?=$tid?>">
        <div class="fg-row">
          <div><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Team Name *</label>
            <input type="text" name="team_name" class="inp-sm" required></div>
          <div><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Captain</label>
            <input type="text" name="captain" class="inp-sm"></div>
        </div>
        <div style="margin-bottom:.7rem"><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Team Logo/Photo</label>
          <input type="file" name="team_photo" accept="image/*" style="width:100%;padding:.4rem;border:1.5px dashed #c7d2fe;border-radius:8px;font-size:.78rem"></div>
        <button type="submit" name="add_team" class="btn-g">➕ Add Team</button>
      </form>
    </div>

    <!-- Auto-generate teams from registrations -->
    <div style="background:#f0fdf4;border-radius:12px;padding:1rem;margin-bottom:1rem">
      <div style="font-weight:700;font-size:.85rem;color:#1b5e20;margin-bottom:.4rem">🔀 Auto-Generate Teams from Registrations</div>
      <div style="font-size:.78rem;color:#374151;margin-bottom:.75rem">Randomly shuffles approved registrants into teams.</div>
      <form method="POST">
        <input type="hidden" name="auto_tid" value="<?=$tid?>">
        <div style="display:flex;gap:.5rem;align-items:center">
          <label style="font-size:.78rem;font-weight:600;white-space:nowrap">Number of teams:</label>
          <input type="number" name="team_count" min="2" max="16" value="4" class="inp-sm" style="width:70px">
          <button type="submit" name="auto_teams" class="btn-o" onclick="return confirm('Auto-generate teams from approved registrations?')">🔀 Generate</button>
        </div>
      </form>
    </div>

    <!-- Auto-generate fixtures -->
    <?php if (count($teams) >= 2): ?>
    <div style="background:#e3f2fd;border-radius:12px;padding:1rem;margin-bottom:1rem">
      <div style="font-weight:700;font-size:.85rem;color:#0d47a1;margin-bottom:.4rem">📅 Auto-Generate Fixtures</div>
      <div style="font-size:.78rem;color:#374151;margin-bottom:.75rem">Creates all <?=count($teams)*(count($teams)-1)/2?> matches for <?=count($teams)?> teams (everyone plays everyone once).</div>
      <form method="POST">
        <input type="hidden" name="fix_tid" value="<?=$tid?>">
        <div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.6rem">
          <label style="font-size:.78rem;font-weight:600;white-space:nowrap">Start date:</label>
          <input type="date" name="fix_start_date" class="inp-sm" value="<?=date('Y-m-d',strtotime($t['start_date']))?>" style="flex:1">
        </div>
        <button type="submit" name="gen_fixtures" class="btn-b" onclick="return confirm('Auto-generate all league fixtures?')">📅 Generate All Fixtures</button>
      </form>
    </div>
    <?php endif; ?>

    <!-- Schedule single match -->
    <?php if (count($teams) >= 2): ?>
    <div style="background:#f8fafc;border-radius:12px;padding:1rem">
      <div style="font-weight:700;font-size:.85rem;color:#0d47a1;margin-bottom:.75rem">📝 Schedule Single Match</div>
      <form method="POST" action="<?=url('modules/football.php')?>">
        <input type="hidden" name="mid_t" value="<?=$tid?>">
        <div class="fg-row">
          <div><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Team 1</label>
            <select name="team1" class="inp-sm" required><option value="">— Select —</option><?php foreach($teams as $tm): ?><option value="<?=$tm['id']?>"><?=h($tm['team_name'])?></option><?php endforeach; ?></select></div>
          <div><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Team 2</label>
            <select name="team2" class="inp-sm" required><option value="">— Select —</option><?php foreach($teams as $tm): ?><option value="<?=$tm['id']?>"><?=h($tm['team_name'])?></option><?php endforeach; ?></select></div>
          <div><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Date</label>
            <input type="date" name="mdate" class="inp-sm" required value="<?=date('Y-m-d')?>"></div>
          <div><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Time</label>
            <input type="time" name="mtime" class="inp-sm"></div>
          <div><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Round</label>
            <input type="text" name="mround" class="inp-sm" value="Group Stage"></div>
          <div><label style="font-size:.7rem;font-weight:700;color:#64748b;display:block;margin-bottom:.25rem">Stage</label>
            <select name="mstage" class="inp-sm">
              <option value="group">Group Stage</option>
              <option value="knockout">Knockout</option>
              <option value="semi">Semi Final</option>
              <option value="final">Final</option>
            </select></div>
        </div>
        <button type="submit" name="add_match" class="btn-b">📅 Schedule Match</button>
      </form>
    </div>
    <?php endif; ?>
  </div>
  <?php endif; ?>

</div><!-- /t-card -->
<?php endforeach; endif; ?>
</div>

<style>
@keyframes livePulse{0%,100%{opacity:1}50%{opacity:.4}}
</style>
<script>
function switchTab(card, tab, btn) {
  var prefix = card + '_';
  document.querySelectorAll('[id^="'+prefix+'"]').forEach(function(p){p.classList.remove('on');});
  var el = document.getElementById(prefix+tab);
  if (el) el.classList.add('on');
  var btns = btn.parentElement.querySelectorAll('.tab-pill');
  btns.forEach(function(b){b.classList.remove('on');});
  btn.classList.add('on');
}
</script>
<?php require_once __DIR__ . '/../includes/footer.php'; ?>
