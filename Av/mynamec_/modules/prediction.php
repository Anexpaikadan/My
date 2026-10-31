<?php
// ============================================================
// modules/prediction.php — FIFA World Cup 2026 Prediction League
// Aishwarya Arts & Sports Club — PHP 7.3+ compatible
// ============================================================
require_once __DIR__ . '/../includes/config.php';
@ini_set('display_errors','1'); @ini_set('display_startup_errors','1'); error_reporting(E_ALL); // TEMP DEBUG — remove once fixed
// Ensure IST so auto-live timing matches admin-entered match times
@date_default_timezone_set('Asia/Kolkata');
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '⚽ FIFA WC 2026 Prediction League — Aishwarya Arts & Sports Club',
  'desc'  => 'Predict FIFA World Cup 2026 matches and win points! Compete with AASC members.',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => rtrim(SITE_URL, '/') . '/modules/prediction.php',
];
requireLogin();
require_once __DIR__ . '/../includes/whatsapp_otp.php';
$me      = currentUser();
// Module admin: Sports Committee + Secretary + Developer
$isAdmin = isSportsAdmin($me['role']) || isModuleAdmin('prediction', $me);
$uid     = (int)$me['id'];
// DEBUG - remove after fix
if(isset($_GET['debug_admin'])){
    header('Content-Type: text/plain');
    echo "role=".$me['role']."\n";
    echo "isAdmin=".($isAdmin?'YES':'NO')."\n";
    echo "isSportsAdmin=".isSportsAdmin($me['role'])."\n";
    exit;
}
$CLUB    = setting('CLUB_NAME','Aishwarya Arts & Sports Club');
$pageTitle = '⚽ FIFA WC 2026 Prediction League — '.$CLUB;

// ── DB Setup ─────────────────────────────────────────────────
try { db()->exec("CREATE TABLE IF NOT EXISTS prediction_matches (
  id INT AUTO_INCREMENT PRIMARY KEY,
  team1 VARCHAR(100) NOT NULL, team2 VARCHAR(100) NOT NULL,
  team1_flag VARCHAR(10) DEFAULT NULL, team2_flag VARCHAR(10) DEFAULT NULL,
  team1_code VARCHAR(5) DEFAULT NULL,  team2_code VARCHAR(5) DEFAULT NULL,
  match_date DATETIME NOT NULL, stadium VARCHAR(200) DEFAULT NULL,
  round VARCHAR(80) DEFAULT 'Group Stage',
  status ENUM('upcoming','live','finished') DEFAULT 'upcoming',
  score1 TINYINT DEFAULT NULL, score2 TINYINT DEFAULT NULL,
  winner ENUM('team1','team2','draw') DEFAULT NULL,
  created_by INT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

try { db()->exec("CREATE TABLE IF NOT EXISTS member_predictions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  member_id INT NOT NULL, match_id INT NOT NULL,
  predicted_winner ENUM('team1','team2','draw') NOT NULL,
  predicted_score1 TINYINT DEFAULT NULL, predicted_score2 TINYINT DEFAULT NULL,
  points INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uniq_pred (member_id, match_id)
)"); } catch(Exception $e){}

// Safe alters
foreach([
  "ALTER TABLE prediction_matches ADD COLUMN team1_code VARCHAR(5) DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN team2_code VARCHAR(5) DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN team1_flag VARCHAR(10) DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN team2_flag VARCHAR(10) DEFAULT NULL",
  "ALTER TABLE member_predictions ADD COLUMN is_double TINYINT(1) DEFAULT 0",
  "ALTER TABLE prediction_matches ADD COLUMN sponsor_name VARCHAR(120) DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN sponsor_tag VARCHAR(200) DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN sponsor_link VARCHAR(300) DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN sponsor_image MEDIUMTEXT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN pen_winner ENUM('team1','team2') DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN pen1 TINYINT DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD COLUMN pen2 TINYINT DEFAULT NULL",
] as $sql) { try { db()->exec($sql); } catch(Exception $e){} }

// Helper: did this finished match go to penalties? returns advancing team ('team1'|'team2') or null
function pkWinner($m){
  if (empty($m['pen_winner'])) return null;
  if ($m['score1']===null || $m['score2']===null) return null;
  if ((int)$m['score1'] !== (int)$m['score2']) return null; // only level scores use pens
  return $m['pen_winner'];
}

// ── Auto-set matches to LIVE when kickoff time passes (PHP/IST time) ──
try { db()->prepare("UPDATE prediction_matches SET status='live' WHERE status='upcoming' AND match_date <= ?")->execute([date('Y-m-d H:i:s')]); } catch(Exception $e){}

// ── Country flags & codes ─────────────────────────────────────
$TEAMS = [
  // North America (hosts)
  'United States'      => ['flag'=>'🇺🇸','code'=>'USA'],
  'Canada'             => ['flag'=>'🇨🇦','code'=>'CAN'],
  'Mexico'             => ['flag'=>'🇲🇽','code'=>'MEX'],
  // Asia
  'Japan'              => ['flag'=>'🇯🇵','code'=>'JPN'],
  'South Korea'        => ['flag'=>'🇰🇷','code'=>'KOR'],
  'Iran'               => ['flag'=>'🇮🇷','code'=>'IRN'],
  'Saudi Arabia'       => ['flag'=>'🇸🇦','code'=>'KSA'],
  'Australia'          => ['flag'=>'🇦🇺','code'=>'AUS'],
  'Qatar'              => ['flag'=>'🇶🇦','code'=>'QAT'],
  'Iraq'               => ['flag'=>'🇮🇶','code'=>'IRQ'],
  'Jordan'             => ['flag'=>'🇯🇴','code'=>'JOR'],
  'Uzbekistan'         => ['flag'=>'🇺🇿','code'=>'UZB'],
  // Africa
  'Morocco'            => ['flag'=>'🇲🇦','code'=>'MAR'],
  'Senegal'            => ['flag'=>'🇸🇳','code'=>'SEN'],
  'Egypt'              => ['flag'=>'🇪🇬','code'=>'EGY'],
  'Algeria'            => ['flag'=>'🇩🇿','code'=>'ALG'],
  'Tunisia'            => ['flag'=>'🇹🇳','code'=>'TUN'],
  'Ghana'              => ['flag'=>'🇬🇭','code'=>'GHA'],
  'South Africa'       => ['flag'=>'🇿🇦','code'=>'RSA'],
  "Côte d'Ivoire"      => ['flag'=>'🇨🇮','code'=>'CIV'],
  'Cape Verde'         => ['flag'=>'🇨🇻','code'=>'CPV'],
  'DR Congo'           => ['flag'=>'🇨🇩','code'=>'COD'],
  // South America
  'Argentina'          => ['flag'=>'🇦🇷','code'=>'ARG'],
  'Brazil'             => ['flag'=>'🇧🇷','code'=>'BRA'],
  'Uruguay'            => ['flag'=>'🇺🇾','code'=>'URU'],
  'Colombia'           => ['flag'=>'🇨🇴','code'=>'COL'],
  'Ecuador'            => ['flag'=>'🇪🇨','code'=>'ECU'],
  'Paraguay'           => ['flag'=>'🇵🇾','code'=>'PAR'],
  'Panama'             => ['flag'=>'🇵🇦','code'=>'PAN'],
  'Haiti'              => ['flag'=>'🇭🇹','code'=>'HAI'],
  'Curaçao'            => ['flag'=>'🇨🇼','code'=>'CUW'],
  // Oceania
  'New Zealand'        => ['flag'=>'🇳🇿','code'=>'NZL'],
  // Europe
  'England'            => ['flag'=>'🏴󠁧󠁢󠁥󠁮󠁧󠁿','code'=>'ENG'],
  'France'             => ['flag'=>'🇫🇷','code'=>'FRA'],
  'Germany'            => ['flag'=>'🇩🇪','code'=>'GER'],
  'Spain'              => ['flag'=>'🇪🇸','code'=>'ESP'],
  'Portugal'           => ['flag'=>'🇵🇹','code'=>'POR'],
  'Netherlands'        => ['flag'=>'🇳🇱','code'=>'NED'],
  'Belgium'            => ['flag'=>'🇧🇪','code'=>'BEL'],
  'Croatia'            => ['flag'=>'🇭🇷','code'=>'CRO'],
  'Scotland'           => ['flag'=>'🏴󠁧󠁢󠁳󠁣󠁴󠁿','code'=>'SCO'],
  'Switzerland'        => ['flag'=>'🇨🇭','code'=>'SUI'],
  'Austria'            => ['flag'=>'🇦🇹','code'=>'AUT'],
  'Norway'             => ['flag'=>'🇳🇴','code'=>'NOR'],
  'Czech Republic'     => ['flag'=>'🇨🇿','code'=>'CZE'],
  'Turkey'             => ['flag'=>'🇹🇷','code'=>'TUR'],
  'Sweden'             => ['flag'=>'🇸🇪','code'=>'SWE'],
  'Bosnia and Herzegovina' => ['flag'=>'🇧🇦','code'=>'BIH'],
];

// ── AJAX Handlers ─────────────────────────────────────────────
$ax = array_merge($_GET, $_POST);
if (!empty($ax['action'])) {
  header('Content-Type: application/json');
  $act = trim($ax['action']);

  // Admin: add match
  if ($act === 'add_match' && $isAdmin) {
    $t1 = trim($ax['team1'] ?? ''); $t2 = trim($ax['team2'] ?? '');
    $dt = trim($ax['match_date'] ?? ''); $st = trim($ax['stadium'] ?? '');
    $rd = trim($ax['round'] ?? 'Group Stage');
    $spN = mb_substr(trim($ax['sponsor_name'] ?? ''),0,120);
    $spT = mb_substr(trim($ax['sponsor_tag'] ?? ''),0,200);
    $spL = mb_substr(trim($ax['sponsor_link'] ?? ''),0,300);
    $spImg = (string)($ax['sponsor_image'] ?? '');
    if (strlen($spImg) > 3500000) $spImg = ''; // guard ~3.5MB
    if (!$t1||!$t2||!$dt) { echo json_encode(['ok'=>false,'msg'=>'Fill all required fields.']); exit; }
    $f1 = $TEAMS[$t1]['flag'] ?? '🏳'; $f2 = $TEAMS[$t2]['flag'] ?? '🏳';
    $c1 = $TEAMS[$t1]['code'] ?? $t1; $c2 = $TEAMS[$t2]['code'] ?? $t2;
    try {
      db()->prepare("INSERT INTO prediction_matches(team1,team2,team1_flag,team2_flag,team1_code,team2_code,match_date,stadium,round,sponsor_name,sponsor_tag,sponsor_link,sponsor_image,created_by)VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
         ->execute([$t1,$t2,$f1,$f2,$c1,$c2,$dt,$st,$rd,$spN,$spT,$spL,$spImg,$uid]);
    } catch (Exception $e) {
      // fallback for older schema (no sponsor columns)
      db()->prepare("INSERT INTO prediction_matches(team1,team2,team1_flag,team2_flag,team1_code,team2_code,match_date,stadium,round,created_by)VALUES(?,?,?,?,?,?,?,?,?,?)")
         ->execute([$t1,$t2,$f1,$f2,$c1,$c2,$dt,$st,$rd,$uid]);
    }
    echo json_encode(['ok'=>true,'msg'=>'✅ Match added!']); exit;
  }

  // Admin: edit match details (teams / date / stadium / round)
  if ($act === 'edit_match' && $isAdmin) {
    $mid = (int)($ax['match_id']??0);
    $t1 = trim($ax['team1'] ?? ''); $t2 = trim($ax['team2'] ?? '');
    $dt = trim($ax['match_date'] ?? ''); $st = trim($ax['stadium'] ?? '');
    $rd = trim($ax['round'] ?? 'Group Stage');
    $spN = mb_substr(trim($ax['sponsor_name'] ?? ''),0,120);
    $spT = mb_substr(trim($ax['sponsor_tag'] ?? ''),0,200);
    $spL = mb_substr(trim($ax['sponsor_link'] ?? ''),0,300);
    $spImg = (string)($ax['sponsor_image'] ?? '');
    if (strlen($spImg) > 3500000) $spImg = '';
    if (!$mid||!$t1||!$t2||!$dt) { echo json_encode(['ok'=>false,'msg'=>'Fill all required fields.']); exit; }
    if ($t1===$t2) { echo json_encode(['ok'=>false,'msg'=>'Teams must be different.']); exit; }
    $f1 = $TEAMS[$t1]['flag'] ?? '🏳'; $f2 = $TEAMS[$t2]['flag'] ?? '🏳';
    $c1 = $TEAMS[$t1]['code'] ?? $t1; $c2 = $TEAMS[$t2]['code'] ?? $t2;
    // 'keepimg' = leave existing image untouched (no new upload)
    try {
      if (!empty($ax['keepimg'])) {
        db()->prepare("UPDATE prediction_matches SET team1=?,team2=?,team1_flag=?,team2_flag=?,team1_code=?,team2_code=?,match_date=?,stadium=?,round=?,sponsor_name=?,sponsor_tag=?,sponsor_link=? WHERE id=?")
           ->execute([$t1,$t2,$f1,$f2,$c1,$c2,$dt,$st,$rd,$spN,$spT,$spL,$mid]);
      } else {
        db()->prepare("UPDATE prediction_matches SET team1=?,team2=?,team1_flag=?,team2_flag=?,team1_code=?,team2_code=?,match_date=?,stadium=?,round=?,sponsor_name=?,sponsor_tag=?,sponsor_link=?,sponsor_image=? WHERE id=?")
           ->execute([$t1,$t2,$f1,$f2,$c1,$c2,$dt,$st,$rd,$spN,$spT,$spL,$spImg,$mid]);
      }
    } catch (Exception $e) {
      // fallback for older schema (no sponsor columns)
      db()->prepare("UPDATE prediction_matches SET team1=?,team2=?,team1_flag=?,team2_flag=?,team1_code=?,team2_code=?,match_date=?,stadium=?,round=? WHERE id=?")
         ->execute([$t1,$t2,$f1,$f2,$c1,$c2,$dt,$st,$rd,$mid]);
    }
    echo json_encode(['ok'=>true,'msg'=>'✅ Match details updated!']); exit;
  }

  // Any member: get match + sponsor data (incl. sponsor image) for the share poster
  if ($act === 'sponsor_card') {
    try {
      $mid = (int)($ax['match_id']??0);
      $m = db()->prepare("SELECT * FROM prediction_matches WHERE id=?");
      $m->execute([$mid]); $m = $m->fetch();
    } catch (Exception $e) { echo json_encode(['ok'=>false]); exit; }
    if (!$m) { echo json_encode(['ok'=>false]); exit; }
    $f1 = $m['team1_flag'] ?: ($TEAMS[$m['team1']]['flag'] ?? '🏳');
    $f2 = $m['team2_flag'] ?: ($TEAMS[$m['team2']]['flag'] ?? '🏳');
    echo json_encode(['ok'=>true,'m'=>[
      'team1'=>$m['team1'],'team2'=>$m['team2'],'f1'=>$f1,'f2'=>$f2,
      'date'=>date('D d M Y · g:i A', strtotime($m['match_date'])),
      'round'=>$m['round'],'status'=>$m['status'],'score1'=>$m['score1'],'score2'=>$m['score2'],
      'sponsor_name'=>$m['sponsor_name'],'sponsor_tag'=>$m['sponsor_tag'],
      'sponsor_link'=>$m['sponsor_link'],'sponsor_image'=>$m['sponsor_image']
    ]]); exit;
  }

  if ($act === 'update_match' && $isAdmin) {
    $mid  = (int)($ax['match_id']??0);
    $status = $ax['status'] ?? 'upcoming';
    $s1 = isset($ax['score1']) && $ax['score1']!=='' ? (int)$ax['score1'] : null;
    $s2 = isset($ax['score2']) && $ax['score2']!=='' ? (int)$ax['score2'] : null;
    // Penalty shootout (knockout rounds): only relevant when the score is level
    $penWin = in_array(($ax['pen_winner']??''),['team1','team2'],true) ? $ax['pen_winner'] : null;
    $pen1   = isset($ax['pen1']) && $ax['pen1']!=='' ? (int)$ax['pen1'] : null;
    $pen2   = isset($ax['pen2']) && $ax['pen2']!=='' ? (int)$ax['pen2'] : null;
    $isLevel = ($s1!==null && $s2!==null && $s1===$s2);
    if (!$isLevel) { $penWin = null; $pen1 = null; $pen2 = null; } // clear stray pens if not a draw on the board
    // If shootout score given but no explicit winner, derive winner from it
    if ($isLevel && $penWin===null && $pen1!==null && $pen2!==null && $pen1!==$pen2) {
      $penWin = $pen1>$pen2 ? 'team1' : 'team2';
    }
    $winner = null;
    if ($status==='finished' && $s1!==null && $s2!==null) {
      if ($s1>$s2)      $winner = 'team1';
      elseif ($s2>$s1)  $winner = 'team2';
      else              $winner = $penWin ?: 'draw'; // level → advancing team on pens, else a true draw
    }
    db()->prepare("UPDATE prediction_matches SET status=?,score1=?,score2=?,winner=?,pen_winner=?,pen1=?,pen2=? WHERE id=?")
       ->execute([$status,$s1,$s2,$winner,$penWin,$pen1,$pen2,$mid]);
    // Auto-calc points for all predictions on this match
    if ($status==='finished' && $winner) {
      $preds = db()->prepare("SELECT * FROM member_predictions WHERE match_id=?");
      $preds->execute([$mid]); $preds=$preds->fetchAll();
      foreach($preds as $p) {
        $pts = 0;
        if ($p['predicted_winner']===$winner) {
          $pts += 5; // correct winner/result
          if ($p['predicted_score1']===$s1 && $p['predicted_score2']===$s2) {
            $pts += 10; // exact score bonus
          } elseif ($p['predicted_score1']!==null && $p['predicted_score2']!==null
                    && ($p['predicted_score1'] - $p['predicted_score2']) === ($s1 - $s2)) {
            $pts += 3; // correct goal difference bonus
          }
        }
        // Double-points (confidence) pick doubles the match score
        if (!empty($p['is_double'])) $pts *= 2;
        db()->prepare("UPDATE member_predictions SET points=? WHERE id=?")->execute([$pts,$p['id']]);
      }
    }
    echo json_encode(['ok'=>true,'msg'=>'✅ Match updated!']); exit;
  }

  // Admin: delete match
  if ($act === 'delete_match' && $isAdmin) {
    $mid = (int)($ax['match_id']??0);
    db()->prepare("DELETE FROM member_predictions WHERE match_id=?")->execute([$mid]);
    db()->prepare("DELETE FROM prediction_matches WHERE id=?")->execute([$mid]);
    echo json_encode(['ok'=>true]); exit;
  }

  // Member: submit prediction
  if ($act === 'predict') {
    $mid = (int)($ax['match_id']??0);
    $pw  = trim($ax['predicted_winner']??'');
    $ps1 = isset($ax['score1'])&&$ax['score1']!==''?(int)$ax['score1']:null;
    $ps2 = isset($ax['score2'])&&$ax['score2']!==''?(int)$ax['score2']:null;
    $dbl = !empty($ax['is_double']) ? 1 : 0;
    if (!$mid||!in_array($pw,['team1','team2','draw'])) { echo json_encode(['ok'=>false,'msg'=>'Invalid prediction.']); exit; }
    // Check match is still upcoming
    $m = db()->prepare("SELECT status FROM prediction_matches WHERE id=?"); $m->execute([$mid]); $m=$m->fetch();
    if (!$m||$m['status']!=='upcoming') { echo json_encode(['ok'=>false,'msg'=>'Predictions are closed for this match.']); exit; }
    // Only ONE double-pick allowed among upcoming matches
    if ($dbl) {
      $chk = db()->prepare("SELECT COUNT(*) FROM member_predictions mp
        JOIN prediction_matches pm ON pm.id=mp.match_id
        WHERE mp.member_id=? AND mp.is_double=1 AND pm.status='upcoming' AND mp.match_id<>?");
      $chk->execute([$uid,$mid]);
      if ((int)$chk->fetchColumn() > 0) {
        echo json_encode(['ok'=>false,'msg'=>'⭐ You already have a Double-Points pick on another upcoming match. Remove it first.']); exit;
      }
    }
    db()->prepare("INSERT INTO member_predictions(member_id,match_id,predicted_winner,predicted_score1,predicted_score2,is_double)VALUES(?,?,?,?,?,?)
      ON DUPLICATE KEY UPDATE predicted_winner=VALUES(predicted_winner),predicted_score1=VALUES(predicted_score1),predicted_score2=VALUES(predicted_score2),is_double=VALUES(is_double)")
      ->execute([$uid,$mid,$pw,$ps1,$ps2,$dbl]);
    echo json_encode(['ok'=>true,'msg'=>$dbl?'⭐ Double-Points prediction saved!':'🎯 Prediction saved!']); exit;
  }

  // Leaderboard data
  if ($act === 'leaderboard') {
    $rows = db()->query("SELECT u.id,u.name,u.profile_photo,
      COALESCE(SUM(mp.points),0) AS total_points,
      COUNT(CASE WHEN mp.points>0 THEN 1 END) AS correct,
      COUNT(mp.id) AS total_preds
      FROM users u
      LEFT JOIN member_predictions mp ON mp.member_id=u.id
      WHERE u.status='active'
      GROUP BY u.id,u.name,u.profile_photo
      HAVING total_preds>0
      ORDER BY total_points DESC, correct DESC
      LIMIT 50")->fetchAll();
    foreach($rows as &$r) { $r['photo'] = $r['profile_photo'] ? getMemberPhoto($r['profile_photo']) : ''; unset($r['profile_photo']); }
    echo json_encode(['ok'=>true,'rows'=>$rows]); exit;
  }

  // Admin: WhatsApp share match to group
  if ($act === 'wa_share' && $isAdmin) {
    $mid = (int)($ax['match_id']??0);
    $m   = db()->prepare("SELECT * FROM prediction_matches WHERE id=?");
    $m->execute([$mid]); $m = $m->fetch();
    if (!$m) { echo json_encode(['ok'=>false,'msg'=>'Match not found']); exit; }

    $f1   = $m['team1_flag'] ?: ($TEAMS[$m['team1']]['flag'] ?? '🏳');
    $f2   = $m['team2_flag'] ?: ($TEAMS[$m['team2']]['flag'] ?? '🏳');
    $dt   = date('D d M Y g:i A', strtotime($m['match_date']));
    $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    $place= setting('CLUB_PLACE', 'Vettikkattiri');
    $link = rtrim(SITE_URL, '/') . '/modules/prediction.php';
    // Add version to bust WhatsApp cache if needed
    // $link .= '?v=2';

    $msg = "⚽ *{$club}*\n"
         . "📍 {$place}, Malappuram\n"
         . "━━━━━━━━━━━━━━━━━━━━━━━━\n"
         . "🏆 *FIFA WC 2026 Prediction League*\n\n"
         . "🆕 *New Match Added!*\n\n"
         . "{$f1} *{$m['team1']}* vs {$f2} *{$m['team2']}*\n\n"
         . "*Date:* {$dt}\n"
         . "*Stadium:* " . ($m['stadium'] ?: 'TBA') . "\n"
         . "*Round:* {$m['round']}\n\n"
         . "🎯 *Make your prediction now!*\n"
         . "👉 {$link}\n\n";
    if (!empty($m['sponsor_name'])) {
      $msg .= "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            . "🤝 *Match Sponsor:* {$m['sponsor_name']}\n";
      if (!empty($m['sponsor_tag']))  $msg .= "{$m['sponsor_tag']}\n";
      if (!empty($m['sponsor_link'])) $msg .= "👉 {$m['sponsor_link']}\n";
      $msg .= "\n";
    }
    $msg .= "━━━━━━━━━━━━━━━━━━━━━━━━\n"
         . "⚽ Predict · Compete · Win Points!";

    // Group share URL
    $groupUrl = setting('CLUB_WA_GROUP', '');
    // Individual wa.me link (opens WhatsApp with message ready to paste)
    $waUrl = 'https://wa.me/?text=' . rawurlencode($msg);

    echo json_encode([
      'ok'       => true,
      'msg'      => $msg,
      'wa_url'   => $waUrl,
      'group_url'=> $groupUrl,
    ]); exit;
  }

  // Share FINISHED match RESULT to WhatsApp (any logged-in member)
  if ($act === 'wa_result') {
    $mid = (int)($ax['match_id']??0);
    $m   = db()->prepare("SELECT * FROM prediction_matches WHERE id=?");
    $m->execute([$mid]); $m = $m->fetch();
    if (!$m) { echo json_encode(['ok'=>false,'msg'=>'Match not found']); exit; }
    if ($m['status']!=='finished' || $m['score1']===null || $m['score2']===null) {
      echo json_encode(['ok'=>false,'msg'=>'Result not available yet for this match.']); exit;
    }

    $f1   = $m['team1_flag'] ?: ($TEAMS[$m['team1']]['flag'] ?? '🏳');
    $f2   = $m['team2_flag'] ?: ($TEAMS[$m['team2']]['flag'] ?? '🏳');
    $s1   = (int)$m['score1']; $s2 = (int)$m['score2'];
    $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    $place= setting('CLUB_PLACE', 'Vettikkattiri');
    $link = rtrim(SITE_URL, '/') . '/modules/prediction.php';

    // Winner line
    $pkAdv = pkWinner($m);
    $penTxt = '';
    if ($pkAdv && $m['pen1']!==null && $m['pen2']!==null) $penTxt = " ({$m['pen1']}-{$m['pen2']} on penalties)";
    elseif ($pkAdv) $penTxt = " (on penalties)";
    if ($m['winner']==='team1')      $resultLine = "🎉 *{$f1} {$m['team1']} win!*{$penTxt}";
    elseif ($m['winner']==='team2')  $resultLine = "🎉 *{$f2} {$m['team2']} win!*{$penTxt}";
    else                             $resultLine = "🤝 *It's a Draw!*";

    // Top correct predictors for this match
    $top = db()->prepare("SELECT u.name, mp.points
      FROM member_predictions mp JOIN users u ON u.id=mp.member_id
      WHERE mp.match_id=? AND mp.points>0
      ORDER BY mp.points DESC, u.name ASC LIMIT 5");
    $top->execute([$mid]); $top = $top->fetchAll();
    $topBlock = '';
    if ($top) {
      $topBlock = "\n🎯 *Correct Predictions:*\n";
      $i=1;
      foreach($top as $t) {
        $medal = $i===1?'🥇':($i===2?'🥈':($i===3?'🥉':'▫️'));
        $topBlock .= "{$medal} {$t['name']} — +{$t['points']} pts\n";
        $i++;
      }
    }

    $msg = "🏆 *{$club}*\n"
         . "📍 {$place}, Malappuram\n"
         . "━━━━━━━━━━━━━━━━━━━━━━━━\n"
         . "🏆 *FIFA WC 2026 Prediction League*\n\n"
         . "✅ *FULL TIME RESULT*\n\n"
         . "{$f1} *{$m['team1']}*  {$s1} — {$s2}  *{$m['team2']}* {$f2}\n\n"
         . "{$resultLine}\n\n"
         . "*Round:* {$m['round']}\n"
         . "*Stadium:* " . ($m['stadium'] ?: 'TBA') . "\n"
         . $topBlock
         . "\n📊 *Check your points & rank!*\n"
         . "👉 {$link}\n\n"
         . "━━━━━━━━━━━━━━━━━━━━━━━━\n"
         . "⚽ Predict · Compete · Win Points!";

    $groupUrl = setting('CLUB_WA_GROUP', '');
    $waUrl    = 'https://wa.me/?text=' . rawurlencode($msg);

    echo json_encode([
      'ok'       => true,
      'msg'      => $msg,
      'wa_url'   => $waUrl,
      'group_url'=> $groupUrl,
    ]); exit;
  }

  // Share ALL members' predictions for a match (live/finished) to WhatsApp
  if ($act === 'wa_predictions') {
    $mid = (int)($ax['match_id']??0);
    $m   = db()->prepare("SELECT * FROM prediction_matches WHERE id=?");
    $m->execute([$mid]); $m = $m->fetch();
    if (!$m) { echo json_encode(['ok'=>false,'msg'=>'Match not found']); exit; }

    $f1   = $m['team1_flag'] ?: ($TEAMS[$m['team1']]['flag'] ?? '🏳');
    $f2   = $m['team2_flag'] ?: ($TEAMS[$m['team2']]['flag'] ?? '🏳');
    $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    $link = rtrim(SITE_URL, '/') . '/modules/prediction.php';
    $isFin = ($m['status']==='finished' && $m['score1']!==null);

    // Status header
    if ($m['status']==='finished') $statHdr = "✅ *FULL TIME* — {$f1} *{$m['team1']}* {$m['score1']} — {$m['score2']} *{$m['team2']}* {$f2}";
    elseif ($m['status']==='live')  $statHdr = "🔴 *LIVE NOW* — predictions locked";
    else                            $statHdr = "⏰ *UPCOMING*";

    // All predictions for this match
    $rows = db()->prepare("SELECT u.name, mp.predicted_winner, mp.predicted_score1, mp.predicted_score2, mp.is_double, mp.points
      FROM member_predictions mp JOIN users u ON u.id=mp.member_id
      WHERE mp.match_id=? ORDER BY u.name ASC");
    $rows->execute([$mid]); $rows = $rows->fetchAll();

    $list = '';
    if ($rows) {
      $i = 1;
      foreach($rows as $r) {
        if      ($r['predicted_winner']==='team1') $pick = "{$f1} {$m['team1']}";
        elseif  ($r['predicted_winner']==='team2') $pick = "{$f2} {$m['team2']}";
        else                                       $pick = "🤝 Draw";
        if ($r['predicted_score1']!==null && $r['predicted_score2']!==null) {
          $pick .= " ({$f1}{$r['predicted_score1']}-{$r['predicted_score2']}{$f2})";
        }
        if (!empty($r['is_double'])) $pick .= " ⭐";
        if ($isFin) $pick .= ($r['points']>0 ? " ✅ +{$r['points']}" : " ❌");
        $list .= "{$i}. {$r['name']} — {$pick}\n";
        $i++;
      }
    } else {
      $list = "_No predictions were made for this match._\n";
    }

    // Prediction split (% of members backing each outcome)
    $cT1=$cD=$cT2=0;
    foreach($rows as $r){
      if($r['predicted_winner']==='team1') $cT1++;
      elseif($r['predicted_winner']==='team2') $cT2++;
      else $cD++;
    }
    $totP = count($rows);
    $split = '';
    if($totP>0){
      $pc = function($n) use ($totP){ return round($n/$totP*100); };
      $split = "📊 *Prediction Split:*\n"
             . "{$f1} {$m['team1']}: ".$pc($cT1)."% ({$cT1})\n"
             . "🤝 Draw: ".$pc($cD)."% ({$cD})\n"
             . "{$f2} {$m['team2']}: ".$pc($cT2)."% ({$cT2})\n\n";
    }

    $sponsorBlk = '';
    if (!empty($m['sponsor_name'])) {
      $sponsorBlk = "━━━━━━━━━━━━━━━━━━━━━━━━\n🤝 *Match Sponsor:* {$m['sponsor_name']}\n";
      if (!empty($m['sponsor_tag']))  $sponsorBlk .= "{$m['sponsor_tag']}\n";
      if (!empty($m['sponsor_link'])) $sponsorBlk .= "👉 {$m['sponsor_link']}\n";
    }
    $msg = "⚽ *{$club}*\n"
         . "🏆 *FIFA WC 2026 Prediction League*\n"
         . "━━━━━━━━━━━━━━━━━━━━━━━━\n"
         . "{$f1} *{$m['team1']}* vs *{$m['team2']}* {$f2}\n"
         . "{$statHdr}\n"
         . "*Round:* {$m['round']}\n\n"
         . "🎯 *Members' Predictions (" . count($rows) . "):*\n"
         . $list . "\n"
         . $split
         . ($isFin ? "📊 *Points awarded! Check your rank.*\n" : "")
         . "👉 {$link}\n"
         . $sponsorBlk
         . "━━━━━━━━━━━━━━━━━━━━━━━━\n"
         . "⚽ Predict · Compete · Win Points!";

    $groupUrl = setting('CLUB_WA_GROUP', '');
    $waUrl    = 'https://wa.me/?text=' . rawurlencode($msg);

    echo json_encode([
      'ok'       => true,
      'msg'      => $msg,
      'wa_url'   => $waUrl,
      'group_url'=> $groupUrl,
    ]); exit;
  }

  echo json_encode(['ok'=>false,'msg'=>'Unknown action']); exit;
}

// ── Page Data ────────────────────────────────────────────────
$matches   = db()->query("SELECT * FROM prediction_matches ORDER BY match_date ASC")->fetchAll();
$my_preds  = [];
$pred_stats = [];
if ($matches) {
  $mids = implode(',',array_map(function($m){ return (int)$m['id']; }, $matches));
  $pp = db()->prepare("SELECT * FROM member_predictions WHERE member_id=? AND match_id IN($mids)");
  $pp->execute([$uid]); foreach($pp->fetchAll() as $p) $my_preds[$p['match_id']] = $p;

  // Prediction distribution per match (powers the stats bar + WhatsApp split)
  foreach(db()->query("SELECT match_id, predicted_winner, COUNT(*) c
      FROM member_predictions WHERE match_id IN($mids)
      GROUP BY match_id, predicted_winner")->fetchAll() as $d){
    $mid=(int)$d['match_id'];
    if(!isset($pred_stats[$mid])) $pred_stats[$mid]=['team1'=>0,'draw'=>0,'team2'=>0,'total'=>0];
    $pred_stats[$mid][$d['predicted_winner']] = (int)$d['c'];
    $pred_stats[$mid]['total'] += (int)$d['c'];
  }
}

// ── Match groupings (Matches tab = live + upcoming, Finished tab = finished) ──
$live     = array_filter($matches, function($m){ return $m['status']==='live'; });
$upcoming = array_filter($matches, function($m){ return $m['status']==='upcoming'; });
$finished = array_filter($matches, function($m){ return $m['status']==='finished'; });
usort($finished, function($a,$b){ return strcmp($b['match_date'],$a['match_date']); }); // newest result first

// ── Admin list ordering: 🔴 Live first, then ⏰ Upcoming (soonest), then ✅ Finished (newest) ──
$matches_admin = $matches;
usort($matches_admin, function($a,$b){
  $rank = ['live'=>0,'upcoming'=>1,'finished'=>2];
  $ra = $rank[$a['status']] ?? 3; $rb = $rank[$b['status']] ?? 3;
  if ($ra !== $rb) return $ra - $rb;
  // within finished, newest first; within live/upcoming, soonest first
  return $a['status']==='finished'
    ? strcmp($b['match_date'],$a['match_date'])
    : strcmp($a['match_date'],$b['match_date']);
});

// Featured match for the top banner (live first, else soonest upcoming)
$featured = null; $featLive = false;
if(!empty($live))          { $featured = reset($live); $featLive = true; }
elseif(!empty($upcoming))  { $featured = reset($upcoming); } // $upcoming is match_date ASC → soonest

// ── Reusable match-card renderer (used by both Matches and New tabs) ──
$renderMatchCard = function($m) use ($my_preds, $TEAMS, $pred_stats) {
  $mp = $my_preds[$m['id']] ?? null;
  $locked = $m['status']!=='upcoming';
  $f1 = $m['team1_flag']?: ($TEAMS[$m['team1']]['flag']??'🏳');
  $f2 = $m['team2_flag']?: ($TEAMS[$m['team2']]['flag']??'🏳');
  $c1 = $m['team1_code']?: ($TEAMS[$m['team1']]['code']??$m['team1']);
  $c2 = $m['team2_code']?: ($TEAMS[$m['team2']]['code']??$m['team2']);
  $winSide = ($m['status']==='finished' && in_array($m['winner'],['team1','team2'],true)) ? $m['winner'] : null;
  $winFlag = $winSide==='team1' ? $f1 : ($winSide==='team2' ? $f2 : '');
  $winName = $winSide==='team1' ? $m['team1'] : ($winSide==='team2' ? $m['team2'] : '');
  ?>
  <div class="match-card<?= $winSide?' mc-decided':'' ?>" data-id="<?= $m['id'] ?>"<?php if($winSide): ?> data-win="<?= $winSide ?>" data-wflag="<?= h($winFlag) ?>" data-wname="<?= h(addslashes($winName)) ?>"<?php endif; ?>>
    <div class="mc-header">
      <span class="mc-round"><?= h($m['round']) ?></span>
      <span class="mc-status status-<?= $m['status'] ?>"><?= $m['status']==='upcoming'?'⏰ Upcoming':($m['status']==='live'?'🔴 LIVE':'✅ Final') ?></span>
    </div>
    <div class="mc-teams">
      <div class="mc-team<?= $winSide==='team1'?' mc-win':'' ?>">
        <span class="mc-flag"><?= $f1 ?></span>
        <div class="mc-name"><?= h($m['team1']) ?><?= $winSide==='team1'?' <span class="mc-crown">🏆</span>':'' ?></div>
        <div class="mc-code"><?= h($c1) ?></div>
      </div>
      <div class="mc-vs">
        <?php if($m['status']==='finished' && $m['score1']!==null): ?>
          <div class="mc-score"><?= $m['score1'] ?> — <?= $m['score2'] ?></div>
          <?php if($pk = pkWinner($m)): $pkName = $pk==='team1'?$m['team1']:$m['team2']; ?>
            <div style="font-size:.58rem;font-weight:800;color:#ffd24a;text-align:center;margin-top:.15rem;letter-spacing:.04em"><?php if($m['pen1']!==null&&$m['pen2']!==null): ?>(<?= (int)$m['pen1'] ?>–<?= (int)$m['pen2'] ?> pens) <?php endif; ?><?= h($pkName) ?> win on pens</div>
          <?php endif; ?>
        <?php else: ?>
          <div class="mc-vs-text">VS</div>
          <?php if($m['status']==='upcoming'): ?>
          <div style="font-size:.6rem;color:rgba(255,255,255,.3);font-family:monospace;text-align:center;margin-top:.2rem" id="timer-<?= $m['id'] ?>" data-dt="<?= h($m['match_date']) ?>"></div>
          <?php endif; ?>
        <?php endif; ?>
      </div>
      <div class="mc-team<?= $winSide==='team2'?' mc-win':'' ?>">
        <span class="mc-flag"><?= $f2 ?></span>
        <div class="mc-name"><?= h($m['team2']) ?><?= $winSide==='team2'?' <span class="mc-crown">🏆</span>':'' ?></div>
        <div class="mc-code"><?= h($c2) ?></div>
      </div>
    </div>
    <div class="mc-info">
      <span class="mc-stadium">🏟 <?= h($m['stadium']?:'TBA') ?></span>
      <span class="mc-time"><?= date('d M Y H:i',strtotime($m['match_date'])) ?></span>
    </div>
    <?php if(!empty($m['sponsor_name'])): ?>
    <div style="margin-top:.45rem;padding:.5rem .6rem;border-radius:9px;background:linear-gradient(135deg,rgba(255,211,77,.14),rgba(255,255,255,.03));border:1px solid rgba(255,211,77,.3)">
      <?php if(!empty($m['sponsor_image'])): ?><img src="<?= h($m['sponsor_image']) ?>" style="width:100%;border-radius:7px;margin-bottom:.4rem;display:block"><?php endif; ?>
      <div style="display:flex;align-items:center;gap:.4rem;flex-wrap:wrap">
        <span style="font-size:.62rem;font-weight:800;color:var(--fifa-gold)">🤝 Sponsored by <?= h($m['sponsor_name']) ?></span>
        <?php if(!empty($m['sponsor_tag'])): ?><span style="font-size:.58rem;color:rgba(255,255,255,.45)">· <?= h($m['sponsor_tag']) ?></span><?php endif; ?>
        <?php if(!empty($m['sponsor_link'])): ?><a href="<?= h($m['sponsor_link']) ?>" target="_blank" rel="noopener" style="font-size:.58rem;color:#00d4ff;margin-left:auto;text-decoration:none">Visit ›</a><?php endif; ?>
      </div>
    </div>
    <?php endif; ?>
    <button onclick="shareMatchPoster(<?= $m['id'] ?>)" style="width:100%;margin-top:.45rem;padding:.55rem;background:rgba(255,211,77,.12);color:var(--fifa-gold);border:1.5px solid rgba(255,211,77,.3);border-radius:11px;font-family:'DM Sans',sans-serif;font-size:.78rem;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.4rem">📸 Share Match Poster</button>
    <div class="mc-predict-area">
      <?php if($locked): ?>
        <?php if($mp): ?>
        <div style="text-align:center;font-size:.72rem;color:rgba(255,255,255,.4);padding:.3rem 0">
          🎯 Your pick: <strong style="color:var(--fifa-gold)"><?= $mp['predicted_winner']==='team1'?$f1.' '.$m['team1']:($mp['predicted_winner']==='team2'?$f2.' '.$m['team2']:'🤝 Draw') ?></strong>
          <?php if($mp['predicted_score1']!==null): ?> · <?= $f1 ?> <?= $mp['predicted_score1'] ?>–<?= $mp['predicted_score2'] ?> <?= $f2 ?><?php endif; ?>
          <?php if($m['status']==='finished'): ?>
            · <strong style="color:<?= $mp['points']>0?'#00ff88':'rgba(255,255,255,.3)' ?>"><?= $mp['points'] > 0 ? '+'.$mp['points'].'pts ✅' : '0pts ❌' ?></strong>
          <?php endif; ?>
        </div>
        <?php else: ?>
        <button class="btn-predict closed"><?= $m['status']==='live'?'🔴 Live Now':'✅ Match Finished' ?></button>
        <?php endif; ?>
        <?php if($m['status']==='finished' && $m['score1']!==null): ?>
        <button onclick="openWaResult(<?= $m['id'] ?>,'<?= h(addslashes($m['team1'])) ?> <?= $m['score1'] ?>-<?= $m['score2'] ?> <?= h(addslashes($m['team2'])) ?>')" style="width:100%;margin-top:.45rem;padding:.6rem;background:rgba(37,211,102,.12);color:#25d366;border:1.5px solid rgba(37,211,102,.3);border-radius:11px;font-family:'DM Sans',sans-serif;font-size:.8rem;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.4rem"><svg width="15" height="15" viewBox="0 0 24 24" fill="#25d366"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg> Share Result</button>
        <?php endif; ?>
        <?php if($m['status']==='live' || $m['status']==='finished'): ?>
        <button onclick="openWaPredictions(<?= $m['id'] ?>,'<?= h(addslashes($m['team1'])) ?> vs <?= h(addslashes($m['team2'])) ?>')" style="width:100%;margin-top:.45rem;padding:.6rem;background:rgba(0,212,255,.1);color:#00d4ff;border:1.5px solid rgba(0,212,255,.3);border-radius:11px;font-family:'DM Sans',sans-serif;font-size:.8rem;font-weight:800;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.4rem">📋 Share All Predictions</button>
        <?php endif; ?>
      <?php else: ?>
        <button class="btn-predict <?= $mp?'predicted':'' ?>" onclick="openPredict(<?= $m['id'] ?>,'<?= h(addslashes($m['team1'])) ?>','<?= h(addslashes($m['team2'])) ?>','<?= $f1 ?>','<?= $f2 ?>')">
          <?= $mp ? '✅ Edit Prediction — '.$f1.' '.($mp['predicted_winner']==='team1'?'<b>'.$m['team1'].'</b>':($mp['predicted_winner']==='draw'?'Draw':'')) : '🎯 Make Prediction' ?>
        </button>
      <?php endif; ?>
    </div>
    <?php
      // ── Prediction split bar (only after lock, when there are picks) ──
      $st = $pred_stats[$m['id']] ?? null;
      if($m['status']!=='upcoming' && $st && $st['total']>0):
        $tot=$st['total'];
        $p1=round($st['team1']/$tot*100); $pd=round($st['draw']/$tot*100); $p2=round($st['team2']/$tot*100);
    ?>
    <div style="margin-top:.6rem;padding-top:.55rem;border-top:1px solid rgba(255,255,255,.07)">
      <div style="display:flex;height:9px;border-radius:6px;overflow:hidden;background:rgba(255,255,255,.06)">
        <div style="width:<?= $p1 ?>%;background:#00d4ff"></div>
        <div style="width:<?= $pd ?>%;background:rgba(255,255,255,.28)"></div>
        <div style="width:<?= $p2 ?>%;background:#FFD700"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:.6rem;font-weight:800;margin-top:.3rem">
        <span style="color:#00d4ff"><?= $f1 ?> <?= $p1 ?>%</span>
        <span style="color:rgba(255,255,255,.55)">🤝 <?= $pd ?>%</span>
        <span style="color:#FFD700"><?= $p2 ?>% <?= $f2 ?></span>
      </div>
      <div style="text-align:center;font-size:.55rem;color:rgba(255,255,255,.3);margin-top:.25rem">📊 <?= $tot ?> prediction<?= $tot==1?'':'s' ?></div>
    </div>
    <?php endif; ?>
  </div>
  <?php
};
$my_points = db()->prepare("SELECT COALESCE(SUM(points),0) AS pts, COUNT(CASE WHEN points>0 THEN 1 END) AS correct, COUNT(*) AS total FROM member_predictions WHERE member_id=?");
$my_points->execute([$uid]); $my_points = $my_points->fetch();
// Leaderboard rank
$rank_row = db()->prepare("SELECT COUNT(*)+1 AS rank FROM (SELECT member_id FROM member_predictions GROUP BY member_id HAVING SUM(points) > (SELECT COALESCE(SUM(points),0) FROM member_predictions WHERE member_id=?)) AS above");
$rank_row->execute([$uid]); $rank_row=$rank_row->fetch(); $my_rank = $rank_row['rank'] ?? 1;

// My profile photo (for the shareable rank card)
$my_photo_url = '';
try {
  $pp = db()->prepare("SELECT profile_photo FROM users WHERE id=?");
  $pp->execute([$uid]);
  $pp = $pp->fetchColumn();
  if($pp) $my_photo_url = getMemberPhoto($pp);
} catch(Throwable $e) { $my_photo_url=''; }

$SELF = url('modules/prediction.php');
?>
<?php
// ── OG meta — set BEFORE header.php so it outputs inside <head> ──
require_once __DIR__ . '/../includes/header.php';
?>
<?php @include __DIR__ . '/../includes/sponsor_splash.php'; ?>
<!-- PRED BUILD: SPONSOR-IMG-2 -->

<style>
/* ═══════════════════════════════════════════
   FIFA WC 2026 PREDICTION LEAGUE — STYLES
   ═══════════════════════════════════════════ */
:root{
  --fifa-gold:#FFD700;--fifa-gold2:#FFC107;
  --fifa-dark:#050a1a;--fifa-darker:#020612;
  --fifa-blue:#0a1628;--fifa-blue2:#0d2137;
  --fifa-accent:#00d4ff;--fifa-green:#00ff88;
  --fifa-red:#ff3366;
}
*{-webkit-tap-highlight-color:transparent}

/* ── Page wrapper ── */
.pw{max-width:520px;margin:0 auto;padding-bottom:2rem}

/* ── Hero ── */
.hero-fifa{
  background:linear-gradient(160deg,#020612 0%,#050a1a 40%,#0a1628 70%,#0d2137 100%);
  padding:0;overflow:hidden;position:relative;
  border-bottom:3px solid var(--fifa-gold);
}
.hero-stars{position:absolute;inset:0;overflow:hidden;pointer-events:none}
.hero-stars span{position:absolute;border-radius:50%;background:#fff;animation:twinkle 3s ease-in-out infinite}
.hero-stars span:nth-child(1){width:2px;height:2px;top:10%;left:10%;animation-delay:0s}
.hero-stars span:nth-child(2){width:3px;height:3px;top:20%;left:60%;animation-delay:.5s}
.hero-stars span:nth-child(3){width:2px;height:2px;top:15%;left:80%;animation-delay:1s}
.hero-stars span:nth-child(4){width:2px;height:2px;top:35%;left:25%;animation-delay:1.5s}
.hero-stars span:nth-child(5){width:3px;height:3px;top:8%;left:45%;animation-delay:.8s}
.hero-stars span:nth-child(6){width:2px;height:2px;top:28%;left:90%;animation-delay:2s}
@keyframes twinkle{0%,100%{opacity:.2;transform:scale(1)}50%{opacity:1;transform:scale(1.5)}}

/* Stadium lights */
.stadium-lights{position:absolute;inset:0;pointer-events:none}
.sl{position:absolute;width:150px;height:150px;border-radius:50%;filter:blur(60px);animation:pulse-light 4s ease-in-out infinite}
.sl1{background:rgba(0,212,255,.08);top:-30px;left:-30px;animation-delay:0s}
.sl2{background:rgba(255,215,0,.06);top:-30px;right:-30px;animation-delay:2s}
.sl3{background:rgba(0,255,136,.05);bottom:0;left:50%;animation-delay:1s}
@keyframes pulse-light{0%,100%{opacity:.5;transform:scale(1)}50%{opacity:1;transform:scale(1.2)}}

.hero-inner{position:relative;z-index:2;padding:1.4rem 1rem 1.1rem;text-align:center}
.hero-badge{
  display:inline-flex;align-items:center;gap:.4rem;
  background:linear-gradient(135deg,rgba(255,215,0,.15),rgba(255,215,0,.05));
  border:1px solid rgba(255,215,0,.35);border-radius:20px;
  padding:.3rem .85rem;font-size:.65rem;font-weight:800;color:var(--fifa-gold);
  letter-spacing:.1em;text-transform:uppercase;margin-bottom:.7rem;
}
.hero-trophy{font-size:2.2rem;display:block;margin-bottom:.3rem;animation:trophy-bounce 2s ease-in-out infinite}
@keyframes trophy-bounce{0%,100%{transform:translateY(0) rotate(-3deg)}50%{transform:translateY(-6px) rotate(3deg)}}
.hero-title{
  font-family:'Bebas Neue',sans-serif;font-size:1.6rem;letter-spacing:.12em;
  background:linear-gradient(135deg,#fff 0%,var(--fifa-gold) 50%,#fff 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
  line-height:1.1;margin-bottom:.25rem;
}
.hero-sub{font-size:.72rem;color:rgba(255,255,255,.5);letter-spacing:.08em;text-transform:uppercase;margin-bottom:.8rem}

/* Countdown */
.countdown{display:flex;justify-content:center;gap:.5rem;margin-bottom:.9rem}
.cd-box{
  background:rgba(255,255,255,.05);border:1px solid rgba(255,215,0,.2);
  border-radius:10px;padding:.45rem .55rem;min-width:52px;text-align:center;
}
.cd-num{font-family:'Bebas Neue',sans-serif;font-size:1.4rem;color:var(--fifa-gold);line-height:1;display:block}
.cd-lbl{font-size:.5rem;color:rgba(255,255,255,.4);letter-spacing:.1em;text-transform:uppercase}

/* Stats row */
.my-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;padding:.8rem 1rem;background:rgba(255,255,255,.02);border-top:1px solid rgba(255,255,255,.06)}
.ms{text-align:center;padding:.5rem .3rem}
.ms-n{font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:var(--fifa-gold);line-height:1}
.ms-l{font-size:.58rem;color:rgba(255,255,255,.4);letter-spacing:.08em;text-transform:uppercase;margin-top:.15rem}

/* ── Tabs ── */
.tabs{display:flex;background:var(--fifa-dark);border-bottom:2px solid rgba(255,215,0,.15);position:sticky;top:66px;z-index:400;overflow-x:auto;scrollbar-width:none}
.tab{flex:1;min-width:60px;padding:.65rem .3rem;text-align:center;font-size:.7rem;font-weight:800;color:rgba(255,255,255,.68);cursor:pointer;letter-spacing:.06em;text-transform:uppercase;transition:all .2s;border-bottom:3px solid transparent;margin-bottom:-2px}
.tab.on{color:var(--fifa-gold);border-bottom-color:var(--fifa-gold);background:rgba(255,215,0,.05)}
.tab-icon{font-size:1rem;display:block;margin-bottom:.15rem}

/* ── Screen ── */
.scr{display:none;padding:.8rem}
.scr.on{display:block;animation:fadeUp .2s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ── Match Card ── */
.match-card{
  background:linear-gradient(145deg,#0d2137,#0a1628);
  border:1px solid rgba(255,255,255,.08);border-radius:16px;
  margin-bottom:.75rem;overflow:hidden;
  box-shadow:0 4px 20px rgba(0,0,0,.4);
  transition:transform .2s;
}
.match-card:active{transform:scale(.99)}
.mc-header{
  padding:.45rem .8rem;display:flex;align-items:center;justify-content:space-between;
  border-bottom:1px solid rgba(255,255,255,.06);
  background:rgba(255,255,255,.02);
}
.mc-round{font-size:.6rem;font-weight:800;color:rgba(255,255,255,.4);letter-spacing:.1em;text-transform:uppercase}
.mc-status{font-size:.58rem;font-weight:800;padding:.15rem .55rem;border-radius:20px;letter-spacing:.06em;text-transform:uppercase}
.status-upcoming{background:rgba(0,212,255,.15);color:#00d4ff;border:1px solid rgba(0,212,255,.3)}
.status-live{background:rgba(255,51,102,.15);color:#ff3366;border:1px solid rgba(255,51,102,.3);animation:live-pulse 1.5s infinite}
@keyframes live-pulse{0%,100%{opacity:1}50%{opacity:.6}}
.status-finished{background:rgba(0,255,136,.1);color:#00ff88;border:1px solid rgba(0,255,136,.25)}
.mc-teams{display:flex;align-items:center;justify-content:space-between;padding:.85rem .8rem .6rem}
.mc-team{text-align:center;flex:1;transition:transform .3s ease}
.mc-flag{font-size:2rem;display:block;margin-bottom:.25rem;line-height:1}
.mc-name{font-size:.75rem;font-weight:800;color:#fff;letter-spacing:.04em;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* ── Winning team highlight (Google-style) ── */
.mc-team.mc-win .mc-flag{filter:drop-shadow(0 0 10px rgba(255,211,77,.85));animation:winBob 1.6s ease-in-out infinite}
.mc-team.mc-win .mc-name{color:var(--fifa-gold);text-shadow:0 0 12px rgba(255,211,77,.55)}
.mc-crown{display:inline-block;animation:crownPop .5s ease both;filter:drop-shadow(0 0 6px rgba(255,211,77,.7))}
@keyframes winBob{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}
@keyframes crownPop{0%{transform:scale(0) rotate(-25deg);opacity:0}60%{transform:scale(1.35) rotate(8deg)}100%{transform:scale(1) rotate(0);opacity:1}}
#celebCanvas{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:9500;display:none}
.mc-code{font-size:.58rem;color:rgba(255,255,255,.4);margin-top:.1rem;font-family:monospace;letter-spacing:.06em}
.mc-vs{
  display:flex;flex-direction:column;align-items:center;gap:.2rem;flex-shrink:0;padding:0 .6rem;
}
.mc-vs-text{font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:rgba(255,255,255,.2);letter-spacing:.06em}
.mc-score{font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:var(--fifa-gold);letter-spacing:.1em;line-height:1}
.mc-info{padding:.35rem .8rem;display:flex;align-items:center;justify-content:space-between;border-top:1px solid rgba(255,255,255,.05)}
.mc-stadium{font-size:.6rem;color:rgba(255,255,255,.3);display:flex;align-items:center;gap:.3rem}
.mc-time{font-size:.6rem;color:rgba(255,255,255,.35);font-family:monospace}

/* Predict button */
.mc-predict-area{padding:.5rem .8rem .75rem}
.btn-predict{
  width:100%;padding:.72rem;
  background:linear-gradient(135deg,#0D47A1,#1565C0);
  color:#fff;border:none;border-radius:11px;
  font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:800;
  cursor:pointer;letter-spacing:.04em;
  display:flex;align-items:center;justify-content:center;gap:.5rem;
  box-shadow:0 4px 16px rgba(13,71,161,.4);transition:all .15s;
}
.btn-predict:active{transform:scale(.97)}
.btn-predict.predicted{background:linear-gradient(135deg,#1b5e20,#2e7d32)}
.btn-predict.closed{background:rgba(255,255,255,.06);color:rgba(255,255,255,.3);cursor:default}

/* ── Predict / Edit Modal ── */
.pred-modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:8000;align-items:flex-end;justify-content:center;backdrop-filter:blur(4px)}
.pred-modal.on{display:flex;animation:fadeIn .2s ease}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.pred-box{
  background:linear-gradient(160deg,#050a1a,#0d2137);
  border:1px solid rgba(255,215,0,.2);border-radius:20px 20px 0 0;
  padding:1.2rem 1rem 2rem;width:100%;max-width:520px;
  animation:slideUp .3s ease;max-height:92vh;overflow-y:auto;
}
@keyframes slideUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
.pred-box h3{font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.1em;color:#fff;margin-bottom:.15rem}
.pred-box .pred-sub{font-size:.65rem;color:rgba(255,255,255,.4);margin-bottom:1rem;letter-spacing:.06em;text-transform:uppercase}
.pred-teams{display:flex;align-items:center;justify-content:center;gap:.5rem;margin-bottom:1rem;font-size:1.6rem}
.pred-section{margin-bottom:1rem}
.pred-section label{font-size:.65rem;font-weight:800;color:rgba(255,255,255,.4);letter-spacing:.1em;text-transform:uppercase;display:block;margin-bottom:.5rem}
.winner-btns{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem}
.wb{
  padding:.7rem .4rem;border-radius:11px;border:2px solid rgba(255,255,255,.1);
  background:rgba(255,255,255,.04);color:rgba(255,255,255,.6);
  cursor:pointer;text-align:center;font-size:.7rem;font-weight:700;
  transition:all .18s;
}
.wb:active{transform:scale(.95)}
.wb.on{border-color:var(--fifa-gold);background:rgba(255,215,0,.12);color:var(--fifa-gold)}
.wb .wf{font-size:1.5rem;display:block;margin-bottom:.25rem}
.score-inputs{display:flex;align-items:center;justify-content:center;gap:.6rem}
.score-inp{
  width:64px;padding:.7rem .4rem;text-align:center;
  background:rgba(255,255,255,.06);border:2px solid rgba(255,255,255,.12);
  border-radius:10px;color:#fff;font-size:1.2rem;font-weight:800;
  font-family:'DM Sans',sans-serif;outline:none;-webkit-appearance:none;
}
.score-inp:focus{border-color:var(--fifa-gold)}
.score-dash{font-size:1.4rem;color:rgba(255,255,255,.3);font-weight:800}
.btn-submit-pred{
  width:100%;padding:.82rem;margin-top:.8rem;
  background:linear-gradient(135deg,var(--fifa-gold),#e6a800);
  color:#000;border:none;border-radius:12px;
  font-family:'DM Sans',sans-serif;font-size:.9rem;font-weight:900;
  cursor:pointer;letter-spacing:.04em;
  box-shadow:0 4px 20px rgba(255,215,0,.3);transition:all .15s;
}
.btn-submit-pred:active{transform:scale(.97)}
.btn-cancel-pred{
  width:100%;padding:.65rem;margin-top:.4rem;
  background:rgba(255,255,255,.06);color:rgba(255,255,255,.5);
  border:none;border-radius:10px;font-family:'DM Sans',sans-serif;
  font-size:.82rem;font-weight:700;cursor:pointer;
}

/* Edit-modal field styling (dark inputs) */
.edit-fi label{font-size:.65rem;font-weight:800;color:rgba(255,255,255,.4);letter-spacing:.08em;text-transform:uppercase;display:block;margin-bottom:.3rem;margin-top:.7rem}
.edit-fi input,.edit-fi select{
  width:100%;padding:.65rem .9rem;border:1.5px solid rgba(255,255,255,.12);border-radius:10px;
  background:rgba(255,255,255,.06);color:#fff;font-family:'DM Sans',sans-serif;font-size:.88rem;
  outline:none;-webkit-appearance:none;transition:border-color .15s;
}
.edit-fi input:focus,.edit-fi select:focus{border-color:var(--fifa-gold)}
.edit-fi select option{background:#0d2137;color:#fff}

/* ── Leaderboard ── */
.lb-row{
  display:flex;align-items:center;gap:.75rem;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);
  border-radius:14px;padding:.7rem .85rem;margin-bottom:.5rem;
  transition:all .2s;
}
.lb-row:active{transform:scale(.98)}
.lb-rank{width:28px;text-align:center;flex-shrink:0}
.lb-rank-n{font-family:'Bebas Neue',sans-serif;font-size:1.1rem;color:rgba(255,255,255,.4)}
.lb-photo{width:40px;height:40px;border-radius:50%;overflow:hidden;flex-shrink:0;background:rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;font-size:1rem;border:2px solid rgba(255,255,255,.1)}
.lb-photo img{width:100%;height:100%;object-fit:cover}
.lb-info{flex:1;min-width:0}
.lb-name{font-size:.85rem;font-weight:800;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.lb-meta{font-size:.65rem;color:rgba(255,255,255,.4);margin-top:.1rem}
.lb-pts{text-align:right;flex-shrink:0}
.lb-pts-n{font-family:'Bebas Neue',sans-serif;font-size:1.3rem;color:var(--fifa-gold);line-height:1}
.lb-pts-l{font-size:.55rem;color:rgba(255,255,255,.3);text-transform:uppercase;letter-spacing:.06em}
.lb-top1{background:linear-gradient(135deg,rgba(255,215,0,.12),rgba(255,215,0,.04));border-color:rgba(255,215,0,.3)}
.lb-top2{background:linear-gradient(135deg,rgba(192,192,192,.1),rgba(192,192,192,.03));border-color:rgba(192,192,192,.25)}
.lb-top3{background:linear-gradient(135deg,rgba(205,127,50,.1),rgba(205,127,50,.03));border-color:rgba(205,127,50,.25)}

/* Badge */
.badge-chip{display:inline-flex;align-items:center;gap:.2rem;font-size:.55rem;font-weight:800;padding:.1rem .4rem;border-radius:20px;margin-top:.15rem;letter-spacing:.05em}
.badge-gold{background:rgba(255,215,0,.15);color:var(--fifa-gold);border:1px solid rgba(255,215,0,.3)}
.badge-silver{background:rgba(192,192,192,.12);color:#c0c0c0;border:1px solid rgba(192,192,192,.25)}
.badge-bronze{background:rgba(205,127,50,.12);color:#cd7f32;border:1px solid rgba(205,127,50,.25)}
.badge-blue{background:rgba(0,212,255,.1);color:#00d4ff;border:1px solid rgba(0,212,255,.25)}

/* ── My Predictions ── */
.pred-history-card{
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);
  border-radius:14px;padding:.75rem .9rem;margin-bottom:.5rem;
}
.ph-teams{font-size:.85rem;font-weight:800;color:#fff;margin-bottom:.3rem}
.ph-row{display:flex;align-items:center;justify-content:space-between;margin-top:.25rem}
.ph-pred{font-size:.72rem;color:rgba(255,255,255,.5)}
.ph-pts{font-family:'Bebas Neue',sans-serif;font-size:1.1rem}
.pts-good{color:var(--fifa-green)}
.pts-zero{color:rgba(255,255,255,.3)}
.pts-pending{color:var(--fifa-accent)}

/* ── Admin Panel ── */
.admin-card{
  background:rgba(255,255,255,.03);border:1px solid rgba(255,215,0,.15);
  border-radius:14px;padding:.9rem;margin-bottom:.75rem;
}
.admin-card h4{font-size:.8rem;font-weight:800;color:var(--fifa-gold);letter-spacing:.07em;text-transform:uppercase;margin-bottom:.8rem;display:flex;align-items:center;gap:.4rem}
.nsg-fi label{font-size:.67rem;font-weight:700;color:rgba(255,255,255,.4);letter-spacing:.06em;text-transform:uppercase;display:block;margin-bottom:.2rem;margin-top:.6rem}
.nsg-fi input,.nsg-fi select{
  width:100%;padding:.65rem .9rem;border:1.5px solid rgba(255,255,255,.1);border-radius:10px;
  background:rgba(255,255,255,.06);color:#fff;font-family:'DM Sans',sans-serif;font-size:.88rem;
  outline:none;-webkit-appearance:none;transition:border-color .15s;
}
.nsg-fi input:focus,.nsg-fi select:focus{border-color:var(--fifa-gold)}
.nsg-fi select option{background:#0d2137;color:#fff}
.r2{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}
.btn-fifa{
  width:100%;padding:.78rem;margin-top:.8rem;
  background:linear-gradient(135deg,var(--fifa-gold),#e6a800);
  color:#000;border:none;border-radius:11px;font-family:'DM Sans',sans-serif;
  font-size:.88rem;font-weight:900;cursor:pointer;letter-spacing:.04em;
  transition:all .15s;
}
.btn-fifa:active{transform:scale(.97)}
.btn-danger{background:rgba(255,51,102,.15);color:#ff3366;border:1px solid rgba(255,51,102,.3);border-radius:8px;padding:.4rem .7rem;font-size:.72rem;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif}
.btn-edit{background:rgba(0,212,255,.12);color:#00d4ff;border:1px solid rgba(0,212,255,.3);border-radius:8px;padding:.4rem .7rem;font-size:.72rem;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif}
.btn-edit2{background:rgba(255,215,0,.12);color:var(--fifa-gold);border:1px solid rgba(255,215,0,.3);border-radius:8px;padding:.4rem .7rem;font-size:.72rem;font-weight:700;cursor:pointer;font-family:'DM Sans',sans-serif}

/* Match manage row */
.admin-match-row{
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);
  border-radius:12px;padding:.65rem .8rem;margin-bottom:.45rem;
}
.amr-teams{font-size:.85rem;font-weight:800;color:#fff;margin-bottom:.3rem}
.amr-bottom{display:flex;align-items:center;justify-content:space-between;gap:.4rem;flex-wrap:wrap}
.amr-actions{display:flex;align-items:center;gap:.3rem;flex-wrap:wrap}
.score-small{display:flex;gap:.3rem;align-items:center}
.score-small input{width:40px;padding:.3rem;text-align:center;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#fff;font-size:.85rem;font-weight:800;outline:none}
.status-sel{padding:.3rem .6rem;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:6px;color:#fff;font-size:.72rem;font-weight:700;outline:none;font-family:'DM Sans',sans-serif}
.status-sel option{background:#0d2137}

/* Football animation */
.football-bg{position:fixed;pointer-events:none;z-index:0;top:0;left:0;right:0;bottom:0;overflow:hidden}
.fb-particle{position:absolute;font-size:1rem;opacity:.04;animation:float-ball linear infinite}
@keyframes float-ball{0%{transform:translateY(100vh) rotate(0deg)}100%{transform:translateY(-100px) rotate(720deg)}}

/* Toast */
.toast-fifa{
  position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%) translateY(40px);
  background:linear-gradient(135deg,#0D47A1,#1565C0);color:#fff;
  padding:.65rem 1.3rem;border-radius:25px;font-size:.82rem;font-weight:700;
  z-index:9999;opacity:0;transition:all .3s;white-space:nowrap;
  box-shadow:0 6px 20px rgba(13,71,161,.5);
}
.toast-fifa.on{opacity:1;transform:translateX(-50%) translateY(0)}
.toast-fifa.gold{background:linear-gradient(135deg,#b8860b,var(--fifa-gold))}
.toast-fifa.err{background:linear-gradient(135deg,#b71c1c,#ef5350)}

/* Empty state */
.empty-fifa{text-align:center;padding:2.5rem 1rem;color:rgba(255,255,255,.62)}
.empty-fifa span{font-size:2.5rem;display:block;margin-bottom:.7rem;opacity:.4}
.empty-fifa p{font-size:.82rem}

/* Dark page bg */
body{background:#020612!important}
.page-wrap{background:#020612}
</style>

<!-- Football particles -->
<div class="football-bg" id="fbBg"></div>

<div class="pw">

  <!-- ════ HERO ════ -->
  <div class="hero-fifa">
    <div class="hero-stars">
      <span></span><span></span><span></span>
      <span></span><span></span><span></span>
    </div>
    <div class="stadium-lights">
      <div class="sl sl1"></div>
      <div class="sl sl2"></div>
      <div class="sl sl3"></div>
    </div>
    <div class="hero-inner">
      <div class="hero-badge">⚽ FIFA World Cup 2026</div>
      <span class="hero-trophy">🏆</span>
      <div class="hero-title">PREDICTION<br>LEAGUE</div>
      <div class="hero-sub"><?= h($CLUB) ?> · <?= date('Y') ?></div>
      <button onclick="openHowToPlay()" style="margin-top:.2rem;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35);color:#fff;border-radius:22px;padding:.4rem 1.1rem;font-size:.76rem;font-weight:800;cursor:pointer;font-family:inherit;backdrop-filter:blur(4px)">❓ How to Play</button>
      <div class="countdown" id="worldCupCountdown">
        <div class="cd-box"><span class="cd-num" id="cd-d">---</span><span class="cd-lbl">Days</span></div>
        <div class="cd-box"><span class="cd-num" id="cd-h">--</span><span class="cd-lbl">Hrs</span></div>
        <div class="cd-box"><span class="cd-num" id="cd-m">--</span><span class="cd-lbl">Min</span></div>
        <div class="cd-box"><span class="cd-num" id="cd-s">--</span><span class="cd-lbl">Sec</span></div>
      </div>
    </div>
    <div class="my-stats">
      <div class="ms"><div class="ms-n"><?= (int)$my_points['pts'] ?></div><div class="ms-l">My Points</div></div>
      <div class="ms"><div class="ms-n"><?= (int)$my_points['correct'] ?>/<?= (int)$my_points['total'] ?></div><div class="ms-l">Correct</div></div>
      <div class="ms"><div class="ms-n">#<?= $my_rank ?></div><div class="ms-l">My Rank</div></div>
    </div>
    <div style="padding:0 1rem .9rem;background:rgba(255,255,255,.02)">
      <button onclick="shareRankCard()" style="width:100%;padding:.7rem;background:linear-gradient(135deg,var(--fifa-gold),#e6a800);color:#000;border:none;border-radius:11px;font-family:'DM Sans',sans-serif;font-size:.84rem;font-weight:900;cursor:pointer;letter-spacing:.03em;display:flex;align-items:center;justify-content:center;gap:.45rem;box-shadow:0 4px 16px rgba(255,215,0,.25)">📸 Share My Rank Card</button>
    </div>
  </div>

  <!-- ════ TABS ════ -->
  <div class="tabs" style="background:#020612" tabindex="0" role="region" aria-label="Sections">
    <div class="tab on" id="tab-matches" onclick="showTab('matches')">
      <span class="tab-icon">⚽</span>Matches
    </div>
    <div class="tab" id="tab-finished" onclick="showTab('finished')">
      <span class="tab-icon">✅</span>Finished
    </div>
    <div class="tab" id="tab-leaderboard" onclick="showTab('leaderboard')">
      <span class="tab-icon">🏆</span>Rankings
    </div>
    <div class="tab" id="tab-mypreds" onclick="showTab('mypreds')">
      <span class="tab-icon">🎯</span>My Picks
    </div>
    <?php if($isAdmin): ?>
    <div class="tab" id="tab-admin" onclick="showTab('admin')">
      <span class="tab-icon">🛡️</span>Admin
    </div>
    <?php endif; ?>
  </div>

  <?php if($featured):
    $bf1 = $featured['team1_flag'] ?: ($TEAMS[$featured['team1']]['flag'] ?? '🏳');
    $bf2 = $featured['team2_flag'] ?: ($TEAMS[$featured['team2']]['flag'] ?? '🏳');
    $bc1 = $featured['team1_code'] ?: ($TEAMS[$featured['team1']]['code'] ?? $featured['team1']);
    $bc2 = $featured['team2_code'] ?: ($TEAMS[$featured['team2']]['code'] ?? $featured['team2']);
    $accent = $featLive ? 'var(--fifa-red)' : 'var(--fifa-gold)';
  ?>
  <div onclick="goToMatch(<?= $featured['id'] ?>)"
       style="display:flex;align-items:center;gap:.55rem;padding:.5rem .8rem;cursor:pointer;
              background:linear-gradient(90deg,<?= $featLive?'rgba(255,51,102,.14)':'rgba(255,215,0,.10)' ?>,rgba(255,255,255,0));
              border-bottom:1px solid rgba(255,255,255,.06)">
    <span style="flex:none;font-size:.58rem;font-weight:900;letter-spacing:.05em;color:<?= $accent ?>;
                 border:1.5px solid <?= $accent ?>;border-radius:20px;padding:.18rem .5rem;<?= $featLive?'animation:live-pulse 1.4s infinite':'' ?>">
      <?= $featLive ? '🔴 LIVE' : '⏳ NEXT' ?>
    </span>
    <span style="flex:1;min-width:0;font-size:.82rem;font-weight:800;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
      <?= $bf1 ?> <?= h($bc1) ?> <span style="color:rgba(255,255,255,.35);font-weight:600">vs</span> <?= h($bc2) ?> <?= $bf2 ?>
    </span>
    <?php if($featLive): ?>
    <span style="flex:none;font-size:.6rem;font-weight:800;color:var(--fifa-red)">● NOW</span>
    <?php else: ?>
    <span id="timer-banner" data-dt="<?= h($featured['match_date']) ?>" style="flex:none;font-size:.62rem;font-family:monospace;color:rgba(255,255,255,.55)"></span>
    <?php endif; ?>
    <span style="flex:none;color:rgba(255,255,255,.3);font-size:.9rem">›</span>
  </div>
  <?php endif; ?>

  <!-- ════ SCREEN: MATCHES (Upcoming & Live) ════ -->
  <div class="scr on" id="scr-matches" style="background:#020612;padding-top:.9rem">

    <?php
      $sections = [];
      if($live)     $sections['🔴 LIVE NOW'] = $live;
      if($upcoming) $sections['⏳ UPCOMING'] = $upcoming;
      if(empty($sections)): ?>
    <div class="empty-fifa"><span>⚽</span><p>No live or upcoming matches right now.<br><?= $finished?'See past results in the <b style="color:var(--fifa-gold)">✅ Finished</b> tab.':($isAdmin?'Go to Admin tab to add matches.':'Check back soon!') ?></p></div>
    <?php else: foreach($sections as $title=>$group): ?>
    <div style="padding:.2rem .8rem .3rem;font-size:.62rem;font-weight:800;color:rgba(255,255,255,.3);letter-spacing:.14em;text-transform:uppercase"><?= $title ?></div>
    <?php foreach($group as $m) $renderMatchCard($m); ?>
    <?php endforeach; endif; ?>
  </div>

  <!-- ════ SCREEN: FINISHED ════ -->
  <div class="scr" id="scr-finished" style="background:#020612;padding-top:.9rem">
    <?php if(empty($finished)): ?>
    <div class="empty-fifa"><span>✅</span><p>No finished matches yet.<br>Results will appear here once matches end.</p></div>
    <?php else: ?>
    <div style="padding:.2rem .8rem .3rem;font-size:.62rem;font-weight:800;color:rgba(255,255,255,.3);letter-spacing:.14em;text-transform:uppercase">✅ Finished · Latest first</div>
    <?php foreach($finished as $m) $renderMatchCard($m); ?>
    <?php endif; ?>
  </div>

  <!-- ════ SCREEN: LEADERBOARD ════ -->
  <div class="scr" id="scr-leaderboard" style="background:#020612;padding-top:.9rem">
    <?php if($isAdmin): ?>
    <button onclick="shareLeaderboardImage()" id="lbShareBtn" style="width:100%;margin:0 0 .9rem;padding:.75rem;background:linear-gradient(135deg,#25d366,#128c7e);color:#fff;border:none;border-radius:12px;font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:900;cursor:pointer;letter-spacing:.02em;display:flex;align-items:center;justify-content:center;gap:.45rem;box-shadow:0 4px 16px rgba(37,211,102,.3)"><svg width="17" height="17" viewBox="0 0 24 24" fill="#fff"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg> Share Full Leaderboard</button>
    <?php endif; ?>
    <div id="lbLoading" style="text-align:center;padding:2rem;color:rgba(255,255,255,.3);font-size:.85rem">Loading rankings...</div>
    <div id="lbContent" style="display:none"></div>
  </div>

  <!-- ════ SCREEN: MY PREDICTIONS ════ -->
  <div class="scr" id="scr-mypreds" style="background:#020612;padding-top:.9rem">
    <?php
    $my_hist = db()->prepare("SELECT mp.*,pm.team1,pm.team2,pm.team1_flag,pm.team2_flag,pm.match_date,pm.status,pm.score1,pm.score2,pm.winner FROM member_predictions mp JOIN prediction_matches pm ON pm.id=mp.match_id WHERE mp.member_id=? ORDER BY pm.match_date DESC");
    $my_hist->execute([$uid]); $my_hist=$my_hist->fetchAll();
    if(empty($my_hist)):
    ?>
    <div class="empty-fifa"><span>🎯</span><p>No predictions yet.<br>Go to Matches and make your first pick!</p></div>
    <?php else: ?>
    <?php foreach($my_hist as $h_item):
      $f1 = $h_item['team1_flag']?: ($TEAMS[$h_item['team1']]['flag']??'🏳');
      $f2 = $h_item['team2_flag']?: ($TEAMS[$h_item['team2']]['flag']??'🏳');
      $pw_label = $h_item['predicted_winner']==='team1'?$f1.' '.$h_item['team1']:($h_item['predicted_winner']==='team2'?$f2.' '.$h_item['team2']:'🤝 Draw');
    ?>
    <div class="pred-history-card">
      <div class="ph-teams"><?= $f1 ?> <?= h($h_item['team1']) ?> vs <?= $f2 ?> <?= h($h_item['team2']) ?></div>
      <div style="font-size:.62rem;color:rgba(255,255,255,.3);margin-bottom:.3rem"><?= date('d M Y H:i',strtotime($h_item['match_date'])) ?></div>
      <div class="ph-row">
        <div class="ph-pred">
          🎯 <?= $pw_label ?>
          <?php if($h_item['predicted_score1']!==null): ?> · <?= $f1 ?> <?= $h_item['predicted_score1'] ?>–<?= $h_item['predicted_score2'] ?> <?= $f2 ?><?php endif; ?>
        </div>
        <div class="ph-pts">
          <?php if($h_item['status']==='finished'): ?>
            <span class="ph-pts <?= $h_item['points']>0?'pts-good':'pts-zero' ?>"><?= $h_item['points']>0?'+'.$h_item['points'].'pts':'0 pts' ?></span>
          <?php else: ?>
            <span class="ph-pts pts-pending"><?= strtoupper($h_item['status']) ?></span>
          <?php endif; ?>
        </div>
      </div>
    </div>
    <?php endforeach; endif; ?>
  </div>

  <!-- ════ SCREEN: ADMIN ════ -->
  <?php if($isAdmin): ?>
  <div class="scr" id="scr-admin" style="background:#020612;padding-top:.9rem">

    <!-- BUILD: LB-SHARE-5 (clear-cards) -->
    <!-- Share Full Leaderboard -->
    <div class="admin-card">
      <h4>📢 Share Rankings</h4>
      <p style="font-size:.74rem;color:rgba(255,255,255,.55);margin:-.35rem 0 .75rem;line-height:1.4">Generate a full leaderboard image (with member profile photos) and share it straight to the WhatsApp group.</p>
      <button onclick="shareLeaderboardImage()" style="width:100%;padding:.8rem;background:linear-gradient(135deg,#25d366,#128c7e);color:#fff;border:none;border-radius:12px;font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:900;cursor:pointer;letter-spacing:.02em;display:flex;align-items:center;justify-content:center;gap:.45rem;box-shadow:0 4px 16px rgba(37,211,102,.3)"><svg width="17" height="17" viewBox="0 0 24 24" fill="#fff"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg> Share Full Leaderboard to WhatsApp</button>
    </div>

    <!-- Add Match -->
    <div class="admin-card">
      <h4>➕ Add New Match</h4>
      <div class="nsg-fi"><label>Team 1 *</label>
        <select id="a_t1" onchange="updateFlag('a_t1','flag1')">
          <option value="">Select Team</option>
          <?php foreach($TEAMS as $tn=>$td): ?><option value="<?= h($tn) ?>"><?= $td['flag'] ?> <?= h($tn) ?></option><?php endforeach; ?>
        </select>
      </div>
      <div class="nsg-fi"><label>Team 2 *</label>
        <select id="a_t2" onchange="updateFlag('a_t2','flag2')">
          <option value="">Select Team</option>
          <?php foreach($TEAMS as $tn=>$td): ?><option value="<?= h($tn) ?>"><?= $td['flag'] ?> <?= h($tn) ?></option><?php endforeach; ?>
        </select>
      </div>
      <!-- Flag preview -->
      <div style="display:flex;align-items:center;justify-content:center;gap:1rem;padding:.6rem 0;font-size:2rem">
        <span id="flag1">🏳</span>
        <span style="font-family:'Bebas Neue',sans-serif;color:rgba(255,255,255,.2);font-size:1rem">VS</span>
        <span id="flag2">🏳</span>
      </div>
      <div class="nsg-fi"><label>Match Date & Time *</label><input type="datetime-local" id="a_dt"></div>
      <div class="r2">
        <div class="nsg-fi"><label>Stadium</label><input type="text" id="a_st" placeholder="e.g. MetLife Stadium"></div>
        <div class="nsg-fi"><label>Round</label>
          <select id="a_rd">
            <option>Group Stage</option><option>Round of 32</option>
            <option>Round of 16</option><option>Quarter-final</option>
            <option>Semi-final</option><option>3rd Place</option><option>Final</option>
          </select>
        </div>
      </div>
      <div class="nsg-fi" style="margin-top:.2rem"><label>🤝 Match Sponsor (optional)</label><input type="text" id="a_spn" placeholder="Sponsor name e.g. Cat Walk"></div>
      <div class="nsg-fi"><label>Sponsor tagline</label><input type="text" id="a_spt" placeholder="e.g. Ladies & Kids Footwear & Bags"></div>
      <div class="nsg-fi"><label>Sponsor link (Instagram / website)</label><input type="text" id="a_spl" placeholder="https://instagram.com/..."></div>
      <div class="nsg-fi"><label>Sponsor image (logo / banner)</label>
        <input type="file" id="a_spfile" accept="image/*" onchange="spPick(this,'a_spimg','a_spprev')">
        <input type="hidden" id="a_spimg">
        <img id="a_spprev" style="display:none;max-width:100%;margin-top:.4rem;border-radius:8px;border:1px solid rgba(255,255,255,.15)">
      </div>
      <button class="btn-fifa" onclick="addMatch()">⚽ Add Match</button>
    </div>

    <!-- Manage Matches -->
    <div class="admin-card">
      <h4>🛠 Manage Matches</h4>
      <?php if(empty($matches)): ?>
        <div style="text-align:center;color:rgba(255,255,255,.25);font-size:.8rem;padding:1rem">No matches yet</div>
      <?php else: foreach($matches_admin as $m):
        $f1 = $m['team1_flag']?: ($TEAMS[$m['team1']]['flag']??'🏳');
        $f2 = $m['team2_flag']?: ($TEAMS[$m['team2']]['flag']??'🏳');
      ?>
      <div class="admin-match-row" id="amr-<?= $m['id'] ?>">
        <div class="amr-teams"><?= $f1 ?> <?= h($m['team1']) ?> vs <?= $f2 ?> <?= h($m['team2']) ?> <span style="font-size:.62rem;color:rgba(255,255,255,.3)">· <?= date('d M',strtotime($m['match_date'])) ?></span></div>
        <div class="amr-bottom">
          <div style="display:flex;align-items:center;gap:.4rem">
            <select class="status-sel" id="st-<?= $m['id'] ?>" data-id="<?= $m['id'] ?>">
              <option value="upcoming" <?= $m['status']==='upcoming'?'selected':'' ?>>⏰ Upcoming</option>
              <option value="live" <?= $m['status']==='live'?'selected':'' ?>>🔴 Live</option>
              <option value="finished" <?= $m['status']==='finished'?'selected':'' ?>>✅ Finished</option>
            </select>
          </div>
          <div class="score-small">
            <input type="number" min="0" max="20" id="s1-<?= $m['id'] ?>" value="<?= $m['score1']??'' ?>" placeholder="—" title="<?= h($m['team1']) ?> score">
            <span style="color:rgba(255,255,255,.3)">—</span>
            <input type="number" min="0" max="20" id="s2-<?= $m['id'] ?>" value="<?= $m['score2']??'' ?>" placeholder="—" title="<?= h($m['team2']) ?> score">
          </div>
        </div>
        <!-- Penalty shootout (knockout): only used when full-time score is level -->
        <div class="amr-bottom amr-pen" id="penrow-<?= $m['id'] ?>" style="margin-top:.5rem;align-items:center;gap:.5rem;<?= ($m['score1']!==null && (int)$m['score1']===(int)$m['score2'])?'':'display:none' ?>">
          <div style="display:flex;align-items:center;gap:.4rem;flex-wrap:wrap">
            <span style="font-size:.66rem;font-weight:800;color:#ffd24a">🥅 PEN WIN</span>
            <select class="status-sel" id="pw-<?= $m['id'] ?>" style="min-width:120px">
              <option value="" <?= empty($m['pen_winner'])?'selected':'' ?>>— none (true draw)</option>
              <option value="team1" <?= ($m['pen_winner']??'')==='team1'?'selected':'' ?>><?= $f1 ?> <?= h($m['team1']) ?></option>
              <option value="team2" <?= ($m['pen_winner']??'')==='team2'?'selected':'' ?>><?= $f2 ?> <?= h($m['team2']) ?></option>
            </select>
            <span class="score-small" style="margin-left:.2rem">
              <input type="number" min="0" max="30" id="p1-<?= $m['id'] ?>" value="<?= $m['pen1']??'' ?>" placeholder="–" title="<?= h($m['team1']) ?> pens" style="width:38px">
              <span style="color:rgba(255,255,255,.3);font-size:.7rem">pk</span>
              <input type="number" min="0" max="30" id="p2-<?= $m['id'] ?>" value="<?= $m['pen2']??'' ?>" placeholder="–" title="<?= h($m['team2']) ?> pens" style="width:38px">
            </span>
          </div>
        </div>
        <div class="amr-bottom" style="margin-top:.5rem">
          <div class="amr-actions">
            <button class="btn-edit" onclick="updateMatch(<?= $m['id'] ?>)">💾 Save</button>
            <button class="btn-edit2" onclick="openEditMatch(<?= $m['id'] ?>,'<?= h(addslashes($m['team1'])) ?>','<?= h(addslashes($m['team2'])) ?>','<?= date('Y-m-d\TH:i',strtotime($m['match_date'])) ?>','<?= h(addslashes($m['stadium']??'')) ?>','<?= h(addslashes($m['round']??'Group Stage')) ?>','<?= h(addslashes($m['sponsor_name']??'')) ?>','<?= h(addslashes($m['sponsor_tag']??'')) ?>','<?= h(addslashes($m['sponsor_link']??'')) ?>')">✏️ Edit</button>
          </div>
          <div class="amr-actions">
            <button onclick="openWaShare(<?= $m['id'] ?>,'<?= h(addslashes($m['team1'])) ?> vs <?= h(addslashes($m['team2'])) ?>')" style="background:linear-gradient(135deg,#25d366,#128c7e);color:#fff;border:none;border-radius:8px;padding:.45rem .8rem;font-size:.73rem;font-weight:800;cursor:pointer;font-family:'DM Sans',sans-serif;display:flex;align-items:center;gap:.3rem;box-shadow:0 3px 10px rgba(37,211,102,.3)"><svg width="13" height="13" viewBox="0 0 24 24" fill="white"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg> Share</button>
            <?php if($m['status']==='finished' && $m['score1']!==null): ?>
            <button onclick="openWaResult(<?= $m['id'] ?>,'<?= h(addslashes($m['team1'])) ?> <?= $m['score1'] ?>-<?= $m['score2'] ?> <?= h(addslashes($m['team2'])) ?>')" style="background:linear-gradient(135deg,#1b5e20,#2e7d32);color:#fff;border:none;border-radius:8px;padding:.45rem .8rem;font-size:.73rem;font-weight:800;cursor:pointer;font-family:'DM Sans',sans-serif;display:flex;align-items:center;gap:.3rem;box-shadow:0 3px 10px rgba(46,125,50,.3)">🏆 Result</button>
            <?php endif; ?>
            <?php if($m['status']==='live' || $m['status']==='finished'): ?>
            <button onclick="openWaPredictions(<?= $m['id'] ?>,'<?= h(addslashes($m['team1'])) ?> vs <?= h(addslashes($m['team2'])) ?>')" style="background:linear-gradient(135deg,#0277bd,#01579b);color:#fff;border:none;border-radius:8px;padding:.45rem .8rem;font-size:.73rem;font-weight:800;cursor:pointer;font-family:'DM Sans',sans-serif;display:flex;align-items:center;gap:.3rem;box-shadow:0 3px 10px rgba(2,119,189,.3)">📋 Predictions</button>
            <?php endif; ?>
            <button class="btn-danger" onclick="deleteMatch(<?= $m['id'] ?>,this)">🗑</button>
          </div>
        </div>
      </div>
      <?php endforeach; endif; ?>
    </div>

  </div>
  <?php endif; ?>

</div><!-- end .pw -->

<!-- ════ EDIT MATCH MODAL ════ -->
<?php if($isAdmin): ?>
<div class="pred-modal" id="editModal" onclick="if(event.target===this)closeEditModal()">
  <div class="pred-box">
    <h3>✏️ EDIT MATCH</h3>
    <div class="pred-sub">Update teams, date, stadium or round</div>

    <div class="edit-fi"><label>Team 1 *</label>
      <select id="e_t1" onchange="updateFlag('e_t1','eflag1')">
        <option value="">Select Team</option>
        <?php foreach($TEAMS as $tn=>$td): ?><option value="<?= h($tn) ?>"><?= $td['flag'] ?> <?= h($tn) ?></option><?php endforeach; ?>
      </select>
    </div>
    <div class="edit-fi"><label>Team 2 *</label>
      <select id="e_t2" onchange="updateFlag('e_t2','eflag2')">
        <option value="">Select Team</option>
        <?php foreach($TEAMS as $tn=>$td): ?><option value="<?= h($tn) ?>"><?= $td['flag'] ?> <?= h($tn) ?></option><?php endforeach; ?>
      </select>
    </div>
    <div style="display:flex;align-items:center;justify-content:center;gap:1rem;padding:.5rem 0;font-size:2rem">
      <span id="eflag1">🏳</span>
      <span style="font-family:'Bebas Neue',sans-serif;color:rgba(255,255,255,.2);font-size:1rem">VS</span>
      <span id="eflag2">🏳</span>
    </div>
    <div class="edit-fi"><label>Match Date & Time *</label><input type="datetime-local" id="e_dt"></div>
    <div class="edit-fi"><label>Stadium</label><input type="text" id="e_st" placeholder="e.g. MetLife Stadium"></div>
    <div class="edit-fi"><label>Round</label>
      <select id="e_rd">
        <option>Group Stage</option><option>Round of 32</option>
        <option>Round of 16</option><option>Quarter-final</option>
        <option>Semi-final</option><option>3rd Place</option><option>Final</option>
      </select>
    </div>
    <div class="edit-fi"><label>🤝 Match Sponsor (optional)</label><input type="text" id="e_spn" placeholder="Sponsor name"></div>
    <div class="edit-fi"><label>Sponsor tagline</label><input type="text" id="e_spt" placeholder="Tagline"></div>
    <div class="edit-fi"><label>Sponsor link</label><input type="text" id="e_spl" placeholder="https://instagram.com/..."></div>
    <div class="edit-fi"><label>Sponsor image (logo / banner)</label>
      <input type="file" id="e_spfile" accept="image/*" onchange="spPick(this,'e_spimg','e_spprev')">
      <input type="hidden" id="e_spimg">
      <img id="e_spprev" style="display:none;max-width:100%;margin-top:.4rem;border-radius:8px;border:1px solid rgba(255,255,255,.15)">
      <button type="button" onclick="spClear('e_spimg','e_spprev')" style="margin-top:.35rem;background:rgba(255,70,90,.15);color:#ff8a98;border:1px solid rgba(255,70,90,.3);border-radius:8px;padding:.35rem .7rem;font-size:.72rem;font-weight:700;cursor:pointer">🗑 Remove image</button>
    </div>

    <button class="btn-submit-pred" onclick="submitEditMatch()">💾 SAVE CHANGES</button>
    <button class="btn-cancel-pred" onclick="closeEditModal()">Cancel</button>
  </div>
</div>
<?php endif; ?>

<!-- ════ WHATSAPP SHARE MODAL ════ -->
<div class="pred-modal" id="waModal" onclick="if(event.target===this)closeWaModal()">
  <div class="pred-box" style="padding-bottom:1.5rem">
    <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.9rem">
      <div style="width:40px;height:40px;border-radius:50%;overflow:hidden;flex-shrink:0;border:2px solid rgba(255,215,0,.4)" id="waLogoWrap">
        <span style="font-size:1.2rem;display:flex;align-items:center;justify-content:center;height:100%">🏆</span>
      </div>
      <div>
        <h3 style="margin:0;font-size:1.1rem">📤 Share to WhatsApp</h3>
        <div class="pred-sub" style="margin:0" id="waMatchLabel">Match details</div>
      </div>
    </div>

    <!-- Message preview -->
    <div style="background:rgba(37,211,102,.06);border:1px solid rgba(37,211,102,.2);border-radius:12px;padding:.8rem;margin-bottom:.9rem;max-height:180px;overflow-y:auto">
      <div style="font-size:.62rem;font-weight:800;color:rgba(37,211,102,.7);letter-spacing:.08em;text-transform:uppercase;margin-bottom:.5rem">📋 Message Preview</div>
      <pre id="waPreview" style="font-family:'DM Sans',sans-serif;font-size:.75rem;color:rgba(255,255,255,.7);white-space:pre-wrap;word-break:break-word;line-height:1.5;margin:0"></pre>
    </div>

    <!-- Share buttons -->
    <div style="display:flex;flex-direction:column;gap:.5rem">
      <!-- Share to Group -->
      <button id="waBtnGroup" onclick="openWaGroup()" style="
        display:flex;align-items:center;justify-content:center;gap:.6rem;
        width:100%;padding:.78rem;
        background:linear-gradient(135deg,#25d366,#128c7e);
        color:#fff;border:none;border-radius:12px;
        font-family:'DM Sans',sans-serif;font-size:.88rem;font-weight:800;
        cursor:pointer;letter-spacing:.04em;
        box-shadow:0 4px 16px rgba(37,211,102,.3);transition:all .15s;
      ">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="white"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>
        Share to Club Group
      </button>

      <!-- Copy & Share (fallback) -->
      <button onclick="copyWaMsg()" style="
        display:flex;align-items:center;justify-content:center;gap:.6rem;
        width:100%;padding:.72rem;
        background:rgba(37,211,102,.1);color:#25d366;
        border:1.5px solid rgba(37,211,102,.3);border-radius:12px;
        font-family:'DM Sans',sans-serif;font-size:.85rem;font-weight:700;
        cursor:pointer;transition:all .15s;
      ">
        📋 Copy Message to Clipboard
      </button>

      <!-- WhatsApp Web / Any number -->
      <button id="waBtnAny" onclick="openWaAny()" style="
        display:flex;align-items:center;justify-content:center;gap:.5rem;
        width:100%;padding:.65rem;
        background:rgba(255,255,255,.05);color:rgba(255,255,255,.5);
        border:1px solid rgba(255,255,255,.1);border-radius:10px;
        font-family:'DM Sans',sans-serif;font-size:.78rem;font-weight:700;
        cursor:pointer;
      ">
        🔗 Open WhatsApp (share manually)
      </button>
    </div>

    <button class="btn-cancel-pred" onclick="closeWaModal()" style="margin-top:.5rem">Cancel</button>
  </div>
</div>

<!-- ════ PREDICT MODAL ════ -->
<div class="pred-modal" id="predModal" onclick="if(event.target===this)closePredModal()">
  <div class="pred-box">
    <h3>🎯 YOUR PREDICTION</h3>
    <div class="pred-sub" id="pred-match-label">Team1 vs Team2</div>
    <div class="pred-teams" id="pred-flags">🏳 vs 🏳</div>

    <div class="pred-section">
      <label>Who wins?</label>
      <div class="winner-btns">
        <div class="wb" id="wb-t1" onclick="pickWinner('team1')">
          <span class="wf" id="pred-f1">🏳</span>
          <div id="pred-n1" style="font-size:.72rem">Team 1</div>
        </div>
        <div class="wb" id="wb-draw" onclick="pickWinner('draw')">
          <span class="wf">🤝</span>
          <div style="font-size:.72rem">Draw</div>
        </div>
        <div class="wb" id="wb-t2" onclick="pickWinner('team2')">
          <span class="wf" id="pred-f2">🏳</span>
          <div id="pred-n2" style="font-size:.72rem">Team 2</div>
        </div>
      </div>
    </div>

    <div class="pred-section">
      <label>Predict Score (optional — +10 pts bonus for exact!)</label>
      <div id="pred-score-key" style="display:flex;justify-content:space-around;font-size:.7rem;font-weight:800;color:#0d1b3e;margin-bottom:.35rem">
        <span id="pred-sl1">🏳 Team 1</span><span id="pred-sl2">🏳 Team 2</span>
      </div>
      <div class="score-inputs">
        <input type="number" class="score-inp" id="pred-s1" min="0" max="20" placeholder="0">
        <span class="score-dash">—</span>
        <input type="number" class="score-inp" id="pred-s2" min="0" max="20" placeholder="0">
      </div>
    </div>

    <div class="pred-section">
      <div id="dblToggle" onclick="toggleDouble()" style="display:flex;align-items:center;gap:.6rem;border:2px solid #e0e7ff;border-radius:12px;padding:.65rem .8rem;cursor:pointer;background:#fafbff">
        <span style="font-size:1.4rem">⭐</span>
        <div style="flex:1">
          <div style="font-weight:800;font-size:.82rem;color:#0d1b3e">Double Points pick</div>
          <div style="font-size:.66rem;color:#5f6880">Doubles your points on this match. Only 1 active at a time.</div>
        </div>
        <span id="dblCheck" style="width:22px;height:22px;border-radius:6px;border:2px solid #cbd5e1;display:flex;align-items:center;justify-content:center;font-size:.8rem;color:#fff"></span>
      </div>
    </div>

    <button class="btn-submit-pred" onclick="submitPred()">⚽ LOCK IN PREDICTION</button>
    <button class="btn-cancel-pred" onclick="closePredModal()">Cancel</button>
  </div>
</div>

<!-- Toast -->
<div class="toast-fifa" id="toast"></div>

<!-- ════ HOW TO PLAY MODAL ════ -->
<div id="howPlayOv" onclick="if(event.target===this)closeHowToPlay()" style="display:none;position:fixed;inset:0;background:rgba(2,6,18,.8);z-index:10000;align-items:flex-end;justify-content:center;padding:0">
  <div style="background:#fff;width:100%;max-width:480px;border-radius:22px 22px 0 0;max-height:88vh;overflow-y:auto;animation:hpUp .3s ease">
    <div style="background:linear-gradient(135deg,#0a1a3f,#1e3a8a);padding:1.3rem 1.2rem;text-align:center;position:relative;border-radius:22px 22px 0 0">
      <button onclick="closeHowToPlay()" style="position:absolute;top:.8rem;right:.9rem;width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,.2);border:none;color:#fff;font-size:1rem;cursor:pointer">✕</button>
      <div style="font-size:2rem">🏆</div>
      <div style="font-family:'Bebas Neue',sans-serif;font-size:1.5rem;letter-spacing:.06em;color:#fff;margin-top:.2rem">HOW TO PLAY</div>
      <div style="font-size:.72rem;color:rgba(255,255,255,.6);margin-top:.1rem">Predict · Score · Climb the leaderboard</div>
    </div>
    <div style="padding:1rem 1.2rem 1.4rem">
      <?php
        $playSteps = [
          ['1','🎯 Pick the Winner','Open any upcoming match and choose Team 1, Draw, or Team 2 before kickoff.','#1565c0'],
          ['2','🔢 Predict the Score','Optionally guess the exact score for bonus points.','#1565c0'],
          ['3','⭐ Use Double Points','Mark ONE upcoming match as your Double-Points pick to double your score on it. Choose wisely!','#c8922a'],
          ['4','🔒 Lock It In','Predictions close at kickoff — no changes after that.','#7b1fa2'],
          ['5','🏅 Earn Points','When the match ends, points are added automatically. Climb the leaderboard!','#2e7d32'],
        ];
        foreach($playSteps as [$n,$t,$d,$c]):
      ?>
      <div style="display:flex;gap:.85rem;padding:.7rem 0;border-bottom:1px dashed #e3e8f2;align-items:flex-start">
        <div style="flex-shrink:0;width:36px;height:36px;border-radius:11px;background:<?php echo $c; ?>;color:#fff;font-weight:800;font-size:1rem;display:flex;align-items:center;justify-content:center;font-family:'Bebas Neue',sans-serif"><?php echo $n; ?></div>
        <div style="flex:1">
          <div style="font-weight:800;font-size:.9rem;color:#0d1b3e"><?php echo $t; ?></div>
          <div style="font-size:.8rem;color:#5a6680;line-height:1.5;margin-top:.1rem"><?php echo $d; ?></div>
        </div>
      </div>
      <?php endforeach; ?>

      <!-- Points table -->
      <div style="margin-top:1rem;background:#f8f9ff;border:1px solid #e3e8f7;border-radius:14px;padding:.9rem 1rem">
        <div style="font-weight:800;font-size:.82rem;color:#0d1b3e;margin-bottom:.6rem">🏅 Points System</div>
        <div style="display:flex;justify-content:space-between;font-size:.8rem;padding:.3rem 0;border-bottom:1px dashed #e3e8f2"><span style="color:#5a6680">Correct winner</span><span style="font-weight:800;color:#1565c0">+5</span></div>
        <div style="display:flex;justify-content:space-between;font-size:.8rem;padding:.3rem 0;border-bottom:1px dashed #e3e8f2"><span style="color:#5a6680">Exact score</span><span style="font-weight:800;color:#1565c0">+10 bonus</span></div>
        <div style="display:flex;justify-content:space-between;font-size:.8rem;padding:.3rem 0;border-bottom:1px dashed #e3e8f2"><span style="color:#5a6680">Correct goal difference</span><span style="font-weight:800;color:#1565c0">+3 bonus</span></div>
        <div style="display:flex;justify-content:space-between;font-size:.8rem;padding:.3rem 0"><span style="color:#5a6680">⭐ Double-Points pick</span><span style="font-weight:800;color:#c8922a">×2 total</span></div>
      </div>

      <!-- Badges -->
      <div style="margin-top:.8rem;background:#fffaf0;border:1px solid #f0e2c0;border-radius:14px;padding:.9rem 1rem">
        <div style="font-weight:800;font-size:.82rem;color:#0d1b3e;margin-bottom:.5rem">🎖️ Ranks</div>
        <div style="font-size:.78rem;color:#5a6680;line-height:1.9">
          🎯 Active · 🔥 Rising (20+) · ⚽ Master (50+) · 🏆 Gold (100+)
        </div>
      </div>
    </div>
  </div>
</div>
<style>@keyframes hpUp{from{transform:translateY(100%)}to{transform:translateY(0)}}</style>

<script>
var SELF     = <?= json_encode(url('modules/prediction.php')) ?>;
var LOGO_B64 = <?= json_encode(getLogoB64()) ?>;
var TEAMS_JS = <?= json_encode(array_map(function($t){ return ['flag'=>$t['flag'],'code'=>$t['code']]; }, $TEAMS), JSON_UNESCAPED_UNICODE) ?>;
var RANK_DATA = <?= json_encode([
  'name'    => $me['name'],
  'points'  => (int)$my_points['pts'],
  'correct' => (int)$my_points['correct'],
  'total'   => (int)$my_points['total'],
  'rank'    => (int)$my_rank,
  'photo'   => $my_photo_url,
  'club'    => $CLUB,
  'place'   => setting('CLUB_PLACE','Vettikkattiri'),
], JSON_UNESCAPED_UNICODE) ?>;

// ── Football particles ──
(function(){
  var bg = document.getElementById('fbBg');
  for(var i=0;i<12;i++){
    var s=document.createElement('span');
    s.className='fb-particle';
    s.textContent='⚽';
    s.style.cssText='left:'+(Math.random()*100)+'%;animation-duration:'+(15+Math.random()*20)+'s;animation-delay:'+(-Math.random()*20)+'s;font-size:'+(0.6+Math.random()*0.8)+'rem';
    bg.appendChild(s);
  }
})();

// ── World Cup countdown (June 11, 2026) ──
function updateCD(){
  var target=new Date('2026-06-11T00:00:00');
  var now=new Date(); var diff=target-now;
  if(diff<=0){document.getElementById('worldCupCountdown').innerHTML='<div style="color:var(--fifa-gold);font-family:Bebas Neue,sans-serif;font-size:1.2rem;letter-spacing:.1em">🏆 WORLD CUP IS HERE!</div>';return;}
  var d=Math.floor(diff/86400000),h=Math.floor((diff%86400000)/3600000),m=Math.floor((diff%3600000)/60000),s=Math.floor((diff%60000)/1000);
  document.getElementById('cd-d').textContent=d;
  document.getElementById('cd-h').textContent=String(h).padStart(2,'0');
  document.getElementById('cd-m').textContent=String(m).padStart(2,'0');
  document.getElementById('cd-s').textContent=String(s).padStart(2,'0');
}
updateCD(); setInterval(updateCD,1000);

// ── Match timers ──
function updateTimers(){
  document.querySelectorAll('[id^="timer-"]').forEach(function(el){
    var dt=new Date(el.getAttribute('data-dt').replace(' ','T'));
    var diff=dt-new Date();
    if(diff<=0){el.textContent='Starting soon';return;}
    var d=Math.floor(diff/86400000);
    if(d>0){el.textContent='in '+d+'d '+ Math.floor((diff%86400000)/3600000)+'h';return;}
    var h=Math.floor(diff/3600000),m=Math.floor((diff%3600000)/60000),s=Math.floor((diff%60000)/1000);
    el.textContent='in '+String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
  });
}
updateTimers(); setInterval(updateTimers,1000);

// ── Tabs ──
function showTab(name){
  document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('on')});
  document.querySelectorAll('.scr').forEach(function(s){s.classList.remove('on')});
  document.getElementById('tab-'+name).classList.add('on');
  document.getElementById('scr-'+name).classList.add('on');
  window.scrollTo(0,0);
  if(name==='leaderboard') loadLeaderboard();
}

// ── Jump from the top banner to its match card ──
function goToMatch(id){
  showTab('matches');
  setTimeout(function(){
    var el=document.querySelector('.match-card[data-id="'+id+'"]');
    if(el){
      el.scrollIntoView({behavior:'smooth',block:'center'});
      el.style.transition='box-shadow .3s';
      el.style.boxShadow='0 0 0 2px var(--fifa-gold)';
      setTimeout(function(){el.style.boxShadow='';},1600);
    }
  },80);
}

// ── Toast ──
function toast(msg,type){
  var el=document.getElementById('toast');
  el.textContent=msg; el.className='toast-fifa on'+(type==='gold'?' gold':type==='err'?' err':'');
  setTimeout(function(){el.className='toast-fifa';},2800);
}
// ── How to Play ──
function openHowToPlay(){document.getElementById('howPlayOv').style.display='flex';document.body.style.overflow='hidden';}
function closeHowToPlay(){document.getElementById('howPlayOv').style.display='none';document.body.style.overflow='';}

// ── Predict modal ──
var predMatchId=null, predWinner=null, predDouble=false;
function openPredict(id,t1,t2,f1,f2){
  predMatchId=id; predWinner=null; predDouble=false;
  document.getElementById('pred-match-label').textContent=t1+' vs '+t2;
  document.getElementById('pred-flags').textContent=f1+' vs '+f2;
  document.getElementById('pred-f1').textContent=f1;
  document.getElementById('pred-f2').textContent=f2;
  document.getElementById('pred-n1').textContent=t1;
  document.getElementById('pred-n2').textContent=t2;
  document.getElementById('pred-sl1').textContent=f1+' '+t1;
  document.getElementById('pred-sl2').textContent=f2+' '+t2;
  document.getElementById('pred-s1').value='';
  document.getElementById('pred-s2').value='';
  ['wb-t1','wb-draw','wb-t2'].forEach(function(id){document.getElementById(id).classList.remove('on')});
  renderDouble();
  document.getElementById('predModal').classList.add('on');
  document.body.style.overflow='hidden';
}
function toggleDouble(){ predDouble=!predDouble; renderDouble(); }
function renderDouble(){
  var box=document.getElementById('dblToggle'), chk=document.getElementById('dblCheck');
  if(!box)return;
  if(predDouble){box.style.borderColor='#f0c674';box.style.background='#fffaf0';chk.style.background='#c8922a';chk.style.borderColor='#c8922a';chk.textContent='✓';}
  else{box.style.borderColor='#e0e7ff';box.style.background='#fafbff';chk.style.background='#fff';chk.style.borderColor='#cbd5e1';chk.textContent='';}
}
function closePredModal(){
  document.getElementById('predModal').classList.remove('on');
  document.body.style.overflow='';
}
function pickWinner(w){
  predWinner=w;
  ['wb-t1','wb-draw','wb-t2'].forEach(function(id){document.getElementById(id).classList.remove('on')});
  var map={team1:'wb-t1',draw:'wb-draw',team2:'wb-t2'};
  document.getElementById(map[w]).classList.add('on');
}
function submitPred(){
  if(!predWinner){toast('Please pick a winner!','err');return;}
  var s1=document.getElementById('pred-s1').value;
  var s2=document.getElementById('pred-s2').value;
  var fd=new FormData();
  fd.append('action','predict'); fd.append('match_id',predMatchId);
  fd.append('predicted_winner',predWinner);
  if(s1!==''&&s2!==''){fd.append('score1',s1);fd.append('score2',s2);}
  if(predDouble) fd.append('is_double','1');
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){toast(res.msg,'gold');closePredModal();setTimeout(function(){location.reload();},900);}
    else toast(res.msg,'err');
  });
}

// ── Leaderboard ──
function loadLeaderboard(){
  document.getElementById('lbLoading').style.display='block';
  document.getElementById('lbContent').style.display='none';
  fetch(SELF+'?action=leaderboard').then(function(r){return r.json();}).then(function(res){
    document.getElementById('lbLoading').style.display='none';
    document.getElementById('lbContent').style.display='block';
    if(!res.ok||!res.rows.length){document.getElementById('lbContent').innerHTML='<div class="empty-fifa"><span>🏆</span><p>No rankings yet. Be the first!</p></div>';return;}
    var html='';
    res.rows.forEach(function(r,i){
      var rank=i+1;
      var cls=rank===1?'lb-top1':rank===2?'lb-top2':rank===3?'lb-top3':'';
      var medal=rank===1?'🥇':rank===2?'🥈':rank===3?'🥉':'';
      var badge=r.total_points>=100?'<span class="badge-chip badge-gold">🏆 Gold</span>':
                r.total_points>=50?'<span class="badge-chip badge-silver">⚽ Master</span>':
                r.total_points>=20?'<span class="badge-chip badge-bronze">🔥 Rising</span>':
                r.correct>0?'<span class="badge-chip badge-blue">🎯 Active</span>':'';
      var photoEl=r.photo?'<img src="'+r.photo+'" alt="">':'<span style="font-size:1.1rem">👤</span>';
      html+='<div class="lb-row '+cls+'">'
        +'<div class="lb-rank">'+(medal||'<span class="lb-rank-n">'+rank+'</span>')+'</div>'
        +'<div class="lb-photo">'+photoEl+'</div>'
        +'<div class="lb-info"><div class="lb-name">'+escHtml(r.name)+'</div>'
        +'<div class="lb-meta">'+r.correct+' correct · '+r.total_preds+' picks</div>'
        +badge+'</div>'
        +'<div class="lb-pts"><div class="lb-pts-n">'+r.total_points+'</div><div class="lb-pts-l">Points</div></div>'
        +'</div>';
    });
    document.getElementById('lbContent').innerHTML=html;
  });
}

// ── Admin: flag preview (works for add + edit selects) ──
function updateFlag(selId,spanId){
  var val=document.getElementById(selId).value;
  var f=TEAMS_JS[val]?TEAMS_JS[val].flag:'🏳';
  document.getElementById(spanId).textContent=f;
}

// ── Admin: add match ──
function addMatch(){
  var t1=document.getElementById('a_t1').value;
  var t2=document.getElementById('a_t2').value;
  var dt=document.getElementById('a_dt').value;
  var st=document.getElementById('a_st').value;
  var rd=document.getElementById('a_rd').value;
  if(!t1||!t2||!dt){toast('Select both teams and date','err');return;}
  if(t1===t2){toast('Teams must be different','err');return;}
  var fd=new FormData();
  fd.append('action','add_match');fd.append('team1',t1);fd.append('team2',t2);
  fd.append('match_date',dt.replace('T',' '));fd.append('stadium',st);fd.append('round',rd);
  fd.append('sponsor_name',document.getElementById('a_spn').value);
  fd.append('sponsor_tag',document.getElementById('a_spt').value);
  fd.append('sponsor_link',document.getElementById('a_spl').value);
  fd.append('sponsor_image',document.getElementById('a_spimg').value);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){toast(res.msg,'gold');setTimeout(function(){location.reload();},900);}
    else toast(res.msg,'err');
  });
}

// ── Admin: update match status/score ──
function updateMatch(id){
  var status=document.getElementById('st-'+id).value;
  var s1=document.getElementById('s1-'+id).value;
  var s2=document.getElementById('s2-'+id).value;
  var fd=new FormData();
  fd.append('action','update_match');fd.append('match_id',id);fd.append('status',status);
  if(s1!=='')fd.append('score1',s1); if(s2!=='')fd.append('score2',s2);
  // Penalty fields — only meaningful when the score is level
  var pwEl=document.getElementById('pw-'+id);
  if(pwEl && s1!=='' && s2!=='' && parseInt(s1,10)===parseInt(s2,10)){
    fd.append('pen_winner',pwEl.value);
    var p1=document.getElementById('p1-'+id), p2=document.getElementById('p2-'+id);
    if(p1&&p1.value!=='')fd.append('pen1',p1.value);
    if(p2&&p2.value!=='')fd.append('pen2',p2.value);
  }
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){toast(res.msg,'gold');setTimeout(function(){location.reload();},700);}
    else toast(res.msg,'err');
  });
}
// Show/hide the penalty row when the admin enters a level score
function togglePenRow(id){
  var s1=document.getElementById('s1-'+id), s2=document.getElementById('s2-'+id);
  var row=document.getElementById('penrow-'+id);
  if(!row||!s1||!s2)return;
  var level = s1.value!=='' && s2.value!=='' && parseInt(s1.value,10)===parseInt(s2.value,10);
  row.style.display = level ? 'flex' : 'none';
}
document.addEventListener('input',function(e){
  var m=(e.target.id||'').match(/^s[12]-(\d+)$/);
  if(m)togglePenRow(m[1]);
});

// ── Admin: EDIT MATCH (teams/date/stadium/round) ──
var editMatchId=null;
function openEditMatch(id,t1,t2,dt,st,rd,spn,spt,spl){
  editMatchId=id;
  document.getElementById('e_t1').value=t1;
  document.getElementById('e_t2').value=t2;
  document.getElementById('e_dt').value=dt;
  document.getElementById('e_st').value=st||'';
  document.getElementById('e_rd').value=rd||'Group Stage';
  document.getElementById('e_spn').value=spn||'';
  document.getElementById('e_spt').value=spt||'';
  document.getElementById('e_spl').value=spl||'';
  // load existing sponsor image preview (kept unless replaced/removed)
  editKeepImg=true;
  document.getElementById('e_spimg').value='';
  var prev=document.getElementById('e_spprev'); prev.style.display='none'; prev.src='';
  var ef=document.getElementById('e_spfile'); if(ef) ef.value='';
  fetch(SELF+'?action=sponsor_card&match_id='+id).then(function(r){return r.json();}).then(function(res){
    if(res.ok && res.m && res.m.sponsor_image){ prev.src=res.m.sponsor_image; prev.style.display='block'; }
    else { editKeepImg=false; }
  });
  updateFlag('e_t1','eflag1');
  updateFlag('e_t2','eflag2');
  document.getElementById('editModal').classList.add('on');
  document.body.style.overflow='hidden';
}
function closeEditModal(){
  document.getElementById('editModal').classList.remove('on');
  document.body.style.overflow='';
}
function submitEditMatch(){
  var t1=document.getElementById('e_t1').value;
  var t2=document.getElementById('e_t2').value;
  var dt=document.getElementById('e_dt').value;
  var st=document.getElementById('e_st').value;
  var rd=document.getElementById('e_rd').value;
  if(!t1||!t2||!dt){toast('Select both teams and date','err');return;}
  if(t1===t2){toast('Teams must be different','err');return;}
  var fd=new FormData();
  fd.append('action','edit_match');fd.append('match_id',editMatchId);
  fd.append('team1',t1);fd.append('team2',t2);
  fd.append('match_date',dt.replace('T',' '));fd.append('stadium',st);fd.append('round',rd);
  fd.append('sponsor_name',document.getElementById('e_spn').value);
  fd.append('sponsor_tag',document.getElementById('e_spt').value);
  fd.append('sponsor_link',document.getElementById('e_spl').value);
  if(editKeepImg){ fd.append('keepimg','1'); }
  else { fd.append('sponsor_image',document.getElementById('e_spimg').value); }
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){toast(res.msg,'gold');closeEditModal();setTimeout(function(){location.reload();},900);}
    else toast(res.msg,'err');
  });
}

// ── Admin: delete match ──
function deleteMatch(id,btn){
  if(!confirm('Delete this match and all predictions?'))return;
  var fd=new FormData(); fd.append('action','delete_match'); fd.append('match_id',id);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){btn.closest('.admin-match-row').remove();toast('Deleted');}
  });
}

// ── Shareable personal RANK CARD (canvas image) ──────────────
function rankTier(p){
  if(p>=100) return {t:'🏆 GOLD LEGEND', c:'#FFD700'};
  if(p>=50)  return {t:'⚽ MASTER',       c:'#C0C0C0'};
  if(p>=20)  return {t:'🔥 RISING STAR',  c:'#cd7f32'};
  return {t:'🎯 ACTIVE PLAYER', c:'#00d4ff'};
}
// helper: load an image (returns null on failure). cross=true tries CORS so the
// canvas stays exportable for cross-origin photos; same-origin photos load fine too.
function loadCardImg(src, cross, cb){
  if(!src){ cb(null); return; }
  var im=new Image();
  if(cross) im.crossOrigin='anonymous';
  im.onload=function(){ cb(im); };
  im.onerror=function(){ cb(null); };
  im.src=src;
}
function cardInitials(name){
  var p=(name||'').trim().split(/\s+/);
  var s=(p[0]?p[0].charAt(0):'')+(p.length>1?p[p.length-1].charAt(0):'');
  return s.toUpperCase()||'⚽';
}
function shareRankCard(){
  toast('🎨 Creating your card…');
  var W=1080, H=1350;
  var c=document.createElement('canvas'); c.width=W; c.height=H;
  var x=c.getContext('2d');

  function draw(logoImg, photoImg){
    // Background gradient
    var g=x.createLinearGradient(0,0,0,H);
    g.addColorStop(0,'#020612'); g.addColorStop(.45,'#0a1628');
    g.addColorStop(1,'#0d2137');
    x.fillStyle=g; x.fillRect(0,0,W,H);

    // Soft glow blobs
    x.globalAlpha=.5;
    var rg=x.createRadialGradient(180,200,0,180,200,360);
    rg.addColorStop(0,'rgba(0,212,255,.18)'); rg.addColorStop(1,'rgba(0,212,255,0)');
    x.fillStyle=rg; x.fillRect(0,0,W,H);
    var rg2=x.createRadialGradient(W-160,H-260,0,W-160,H-260,420);
    rg2.addColorStop(0,'rgba(255,215,0,.14)'); rg2.addColorStop(1,'rgba(255,215,0,0)');
    x.fillStyle=rg2; x.fillRect(0,0,W,H);
    x.globalAlpha=1;

    // Gold border
    x.strokeStyle='#FFD700'; x.lineWidth=10;
    x.strokeRect(28,28,W-56,H-56);

    x.textAlign='center';
    var cx=W/2;

    // Small club logo (top)
    var ly=152, lr=56;
    x.save();
    x.beginPath(); x.arc(cx,ly,lr,0,Math.PI*2); x.closePath();
    x.lineWidth=5; x.strokeStyle='rgba(255,215,0,.6)'; x.stroke();
    if(logoImg){ x.clip(); x.drawImage(logoImg,cx-lr,ly-lr,lr*2,lr*2); }
    x.restore();
    if(!logoImg){ x.font='62px sans-serif'; x.fillStyle='#FFD700'; x.fillText('🏆',cx,ly+22); }

    // Club name + place
    x.fillStyle='rgba(255,255,255,.85)'; x.font='bold 38px sans-serif';
    x.fillText(RANK_DATA.club, cx, 266);
    x.fillStyle='rgba(255,255,255,.45)'; x.font='25px sans-serif';
    x.fillText('📍 '+RANK_DATA.place, cx, 304);

    // Title
    x.fillStyle='#FFD700'; x.font='900 54px sans-serif';
    x.fillText('FIFA WC 2026', cx, 384);
    x.fillStyle='rgba(255,255,255,.8)'; x.font='bold 34px sans-serif';
    x.fillText('PREDICTION LEAGUE', cx, 430);

    // ── Member avatar (the hero of the card) ──
    var ay=576, ar=94;
    x.save();
    // gradient ring
    x.beginPath(); x.arc(cx,ay,ar,0,Math.PI*2); x.closePath();
    var ring=x.createLinearGradient(cx-ar,ay-ar,cx+ar,ay+ar);
    ring.addColorStop(0,'#FFD700'); ring.addColorStop(1,'#00d4ff');
    x.lineWidth=8; x.strokeStyle=ring; x.stroke();
    // clip inner circle
    x.beginPath(); x.arc(cx,ay,ar-5,0,Math.PI*2); x.closePath(); x.clip();
    if(photoImg){
      var side=(ar-5)*2, sc=Math.max(side/photoImg.width, side/photoImg.height);
      var dw=photoImg.width*sc, dh=photoImg.height*sc;
      x.drawImage(photoImg, cx-dw/2, ay-dh/2, dw, dh);
    } else {
      x.fillStyle='rgba(255,255,255,.07)'; x.fillRect(cx-ar,ay-ar,ar*2,ar*2);
      x.fillStyle='#FFD700'; x.font='900 82px sans-serif';
      x.textBaseline='middle'; x.fillText(cardInitials(RANK_DATA.name), cx, ay+4);
      x.textBaseline='alphabetic';
    }
    x.restore();

    // Member name
    x.fillStyle='#fff'; x.font='900 60px sans-serif';
    var nm=RANK_DATA.name; if(nm.length>18) nm=nm.slice(0,17)+'…';
    x.fillText(nm, cx, 728);

    // Big RANK
    x.fillStyle='rgba(255,255,255,.5)'; x.font='bold 32px sans-serif';
    x.fillText('CURRENT RANK', cx, 798);
    x.fillStyle='#FFD700'; x.font='900 168px sans-serif';
    x.fillText('#'+RANK_DATA.rank, cx, 952);

    // Divider
    x.strokeStyle='rgba(255,255,255,.12)'; x.lineWidth=2;
    x.beginPath(); x.moveTo(140,1008); x.lineTo(W-140,1008); x.stroke();

    // Points + Correct two columns
    var c1=W*0.32, c2=W*0.68;
    x.fillStyle='#00ff88'; x.font='900 90px sans-serif';
    x.fillText(RANK_DATA.points, c1, 1128);
    x.fillStyle='rgba(255,255,255,.5)'; x.font='bold 28px sans-serif';
    x.fillText('POINTS', c1, 1170);

    x.fillStyle='#00d4ff'; x.font='900 90px sans-serif';
    x.fillText(RANK_DATA.correct+'/'+RANK_DATA.total, c2, 1128);
    x.fillStyle='rgba(255,255,255,.5)'; x.font='bold 28px sans-serif';
    x.fillText('CORRECT', c2, 1170);

    // Tier pill
    var tier=rankTier(RANK_DATA.points);
    x.font='900 38px sans-serif';
    var pillW=x.measureText(tier.t).width+80, pillH=72, py=1216;
    x.fillStyle='rgba(255,255,255,.06)';
    if(x.roundRect){ x.beginPath(); x.roundRect(cx-pillW/2,py,pillW,pillH,36); x.fill();
      x.lineWidth=3; x.strokeStyle=tier.c; x.stroke(); }
    x.fillStyle=tier.c; x.fillText(tier.t, cx, py+50);

    // Footer
    x.fillStyle='rgba(255,255,255,.4)'; x.font='26px sans-serif';
    x.fillText('⚽ Predict · Compete · Win Points!', cx, H-50);

    exportCard(c);
  }

  // Load logo (base64, always safe) → then member photo → then draw
  loadCardImg(LOGO_B64||'', false, function(logoImg){
    loadCardImg(RANK_DATA.photo||'', true, function(photoImg){
      draw(logoImg, photoImg);
    });
  });
}
function exportCard(canvas){
  canvas.toBlob(function(blob){
    if(!blob){ toast('Could not create image','err'); return; }
    var file=new File([blob],'my-rank-card.png',{type:'image/png'});
    if(navigator.canShare && navigator.canShare({files:[file]})){
      navigator.share({files:[file], title:'My Prediction Rank',
        text:'🏆 My FIFA WC 2026 Prediction League rank at '+RANK_DATA.club+'!'})
        .then(function(){toast('✅ Shared!','gold');})
        .catch(function(){ downloadCard(blob); });
    } else {
      downloadCard(blob);
    }
  },'image/png');
}
function downloadCard(blob){
  var url=URL.createObjectURL(blob);
  var a=document.createElement('a'); a.href=url; a.download='my-rank-card.png';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(function(){URL.revokeObjectURL(url);},1000);
  toast('📸 Card saved! Share it in WhatsApp','gold');
}

// ── Shareable FULL LEADERBOARD image (admin) ─────────────────
// Renders every ranked member (with profile photo) onto a tall
// canvas and shares the PNG to WhatsApp via Web Share API.
function preloadLbImages(srcs, cb){
  var imgs=new Array(srcs.length), done=0, n=srcs.length;
  if(!n){ cb(imgs); return; }
  srcs.forEach(function(s,i){
    // member photos are same-origin base64 data URIs → no canvas tainting
    loadCardImg(s||'', false, function(im){ imgs[i]=im; done++; if(done===n) cb(imgs); });
  });
}
function shareLeaderboardImage(){
  toast('🎨 Building leaderboard image…');
  fetch(SELF+'?action=leaderboard').then(function(r){return r.json();}).then(function(res){
    if(!res.ok || !res.rows || !res.rows.length){ toast('No rankings yet','err'); return; }
    var rows=res.rows.slice(0,40); // safety cap for image height
    var photoSrcs=rows.map(function(r){return r.photo||'';});
    loadCardImg(LOGO_B64||'', false, function(logoImg){
      preloadLbImages(photoSrcs, function(photoImgs){
        drawLeaderboard(rows, logoImg, photoImgs);
      });
    });
  }).catch(function(){ toast('Failed to load rankings','err'); });
}
// draws a circular avatar (photo or initials) with a coloured ring
function drawAvatar(x, cx, cy, r, img, ring, name){
  x.save();
  x.beginPath(); x.arc(cx,cy,r,0,Math.PI*2); x.closePath();
  x.lineWidth=Math.max(4,r*0.07); x.strokeStyle=ring; x.stroke();
  x.beginPath(); x.arc(cx,cy,r-3,0,Math.PI*2); x.closePath(); x.clip();
  if(img){
    var side=(r-3)*2, sc=Math.max(side/img.width, side/img.height);
    var dw=img.width*sc, dh=img.height*sc;
    x.drawImage(img, cx-dw/2, cy-dh/2, dw, dh);
  } else {
    x.fillStyle='rgba(255,255,255,.08)'; x.fillRect(cx-r,cy-r,r*2,r*2);
    x.fillStyle=ring; x.font='900 '+Math.round(r*0.85)+'px sans-serif';
    x.textAlign='center'; x.textBaseline='middle';
    x.fillText(cardInitials(name), cx, cy+2);
    x.textBaseline='alphabetic';
  }
  x.restore();
}
function drawLeaderboard(rows, logoImg, photoImgs){
  var W=1080, M=16;
  var headerH=360;
  var usable=W-2*M;

  // top-3 equal cards
  var g3=22, card3W=(usable-2*g3)/3, card3H=362, step3=card3W+g3;
  var top3Top=headerH+16;
  var featureBottom=top3Top+card3H;

  // 2-col grid for rank 4+
  var g2=22, card2W=(usable-g2)/2, card2H=172, rowStep=card2H+26;
  var gridTop=featureBottom+34;
  var gridRows=Math.ceil(Math.max(0,rows.length-3)/2);
  var footerH=150;
  var H=(gridRows>0 ? gridTop+gridRows*rowStep-22 : featureBottom) + footerH;

  var c=document.createElement('canvas'); c.width=W; c.height=H;
  var x=c.getContext('2d');
  var cx=W/2;

  // ── Background ──
  var g=x.createLinearGradient(0,0,0,H);
  g.addColorStop(0,'#020612'); g.addColorStop(.5,'#0a1628'); g.addColorStop(1,'#0d2137');
  x.fillStyle=g; x.fillRect(0,0,W,H);
  x.globalAlpha=.55;
  var rg=x.createRadialGradient(cx,300,0,cx,300,560);
  rg.addColorStop(0,'rgba(255,215,0,.15)'); rg.addColorStop(1,'rgba(255,215,0,0)');
  x.fillStyle=rg; x.fillRect(0,0,W,featureBottom);
  var rg1=x.createRadialGradient(150,160,0,150,160,360);
  rg1.addColorStop(0,'rgba(0,212,255,.16)'); rg1.addColorStop(1,'rgba(0,212,255,0)');
  x.fillStyle=rg1; x.fillRect(0,0,W,420);
  x.globalAlpha=1;
  // thin gold edge accent (top + bottom) — keeps club identity, stays full-bleed
  x.fillStyle='#FFD700'; x.fillRect(0,0,W,8); x.fillRect(0,H-8,W,8);

  // ── Header ──
  x.textAlign='center';
  var ly=120, lr=50;
  x.save();
  x.beginPath(); x.arc(cx,ly,lr,0,Math.PI*2); x.closePath();
  x.lineWidth=5; x.strokeStyle='rgba(255,215,0,.6)'; x.stroke();
  if(logoImg){ x.clip(); x.drawImage(logoImg,cx-lr,ly-lr,lr*2,lr*2); }
  x.restore();
  if(!logoImg){ x.font='50px sans-serif'; x.fillStyle='#FFD700'; x.fillText('🏆',cx,ly+16); }
  x.fillStyle='rgba(255,255,255,.88)'; x.font='bold 32px sans-serif';
  x.fillText(RANK_DATA.club, cx, 206);
  x.fillStyle='#FFD700'; x.font='900 52px sans-serif';
  x.fillText('FIFA WC 2026', cx, 278);
  x.fillStyle='rgba(255,255,255,.85)'; x.font='900 36px sans-serif';
  x.fillText('🏆 LEADERBOARD', cx, 322);

  // ── TOP 3 — equal cards ──
  var medals=['🥇','🥈','🥉'];
  var rings=['#FFD700','#C0C0C0','#cd7f32'];
  var tags=['1ST','2ND','3RD'];
  for(var t=0;t<3;t++){
    var r=rows[t]; if(!r) continue;
    var cardX=M+t*step3, ccx=cardX+card3W/2, ring=rings[t];
    // card surface (clearly defined)
    cardSurface(x, cardX, top3Top, card3W, card3H, 22, ring, 3);
    // medal
    x.textAlign='center'; x.font='46px sans-serif';
    x.fillText(medals[t], ccx, top3Top+62);
    // avatar
    drawAvatar(x, ccx, top3Top+150, 70, photoImgs[t], ring, r.name);
    // name
    x.fillStyle='#fff'; x.font='900 30px sans-serif';
    var nm=r.name||''; if(nm.length>13) nm=nm.slice(0,12)+'…';
    x.fillText(nm, ccx, top3Top+258);
    // points
    x.fillStyle='#00ff88'; x.font='900 38px sans-serif';
    x.fillText(r.total_points+' pts', ccx, top3Top+306);
    // rank tag
    x.fillStyle=ring; x.font='800 22px sans-serif';
    x.fillText(tags[t], ccx, top3Top+342);
  }

  // ── RANK 4+ — 2-column card grid ──
  for(var i=3;i<rows.length;i++){
    var rr=rows[i], rank=i+1, k=i-3;
    var col=k%2, rowi=Math.floor(k/2);
    var cardX=M+col*(card2W+g2), cardY=gridTop+rowi*rowStep;
    var cy=cardY+card2H/2;
    // card surface (clearly defined)
    cardSurface(x, cardX, cardY, card2W, card2H, 18, 'rgba(255,255,255,.20)', 1.6);
    // faint rank number top-right
    x.textAlign='right'; x.fillStyle='rgba(255,255,255,.22)'; x.font='900 44px sans-serif';
    x.fillText(rank, cardX+card2W-26, cardY+58);
    // avatar
    drawAvatar(x, cardX+78, cy, 50, photoImgs[i], 'rgba(255,255,255,.28)', rr.name);
    // name
    x.textAlign='left'; x.fillStyle='#fff'; x.font='800 32px sans-serif';
    var nm2=rr.name||''; if(nm2.length>13) nm2=nm2.slice(0,12)+'…';
    x.fillText(nm2, cardX+148, cy-26);
    // points
    x.fillStyle='#00ff88'; x.font='900 38px sans-serif';
    x.fillText(rr.total_points+' pts', cardX+148, cy+16);
    // meta
    x.fillStyle='rgba(255,255,255,.45)'; x.font='19px sans-serif';
    x.fillText((rr.correct||0)+' correct · '+(rr.total_preds||0)+' picks', cardX+148, cy+48);
  }

  // ── Footer ──
  x.textAlign='center';
  x.strokeStyle='rgba(255,255,255,.12)'; x.lineWidth=2;
  x.beginPath(); x.moveTo(140,H-110); x.lineTo(W-140,H-110); x.stroke();
  x.fillStyle='#FFD700'; x.font='900 30px sans-serif';
  x.fillText('⚽ Predict · Compete · Win Points!', cx, H-62);
  x.fillStyle='rgba(255,255,255,.4)'; x.font='22px sans-serif';
  x.fillText('Updated '+new Date().toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}), cx, H-28);

  exportLbImage(c);
}
// rounded-rect path helper (roundRect fallback for older browsers)
function rrect(ctx,xx,yy,w,h,r){
  if(ctx.roundRect){ ctx.beginPath(); ctx.roundRect(xx,yy,w,h,r); return; }
  ctx.beginPath();
  ctx.moveTo(xx+r,yy);
  ctx.arcTo(xx+w,yy,xx+w,yy+h,r);
  ctx.arcTo(xx+w,yy+h,xx,yy+h,r);
  ctx.arcTo(xx,yy+h,xx,yy,r);
  ctx.arcTo(xx,yy,xx+w,yy,r);
  ctx.closePath();
}
// solid card surface: drop shadow + navy gradient fill + border (clearly defined card)
function cardSurface(x, X, Y, w, h, r, border, bw){
  x.save();
  x.shadowColor='rgba(0,0,0,.55)'; x.shadowBlur=24; x.shadowOffsetY=9;
  var gr=x.createLinearGradient(0,Y,0,Y+h);
  gr.addColorStop(0,'rgba(46,62,94,.94)'); gr.addColorStop(1,'rgba(22,34,58,.94)');
  x.fillStyle=gr; rrect(x,X,Y,w,h,r); x.fill();
  x.restore();                       // clears shadow before border/text
  x.lineWidth=bw||1.6; x.strokeStyle=border; rrect(x,X,Y,w,h,r); x.stroke();
}
function exportLbImage(canvas){
  canvas.toBlob(function(blob){
    if(!blob){ toast('Could not create image','err'); return; }
    var file=new File([blob],'leaderboard.png',{type:'image/png'});
    var caption='🏆 *FIFA WC 2026 Prediction League*\n'+RANK_DATA.club+'\n\n⚽ Current full leaderboard — predict, compete & climb!';
    if(navigator.canShare && navigator.canShare({files:[file]})){
      navigator.share({files:[file], title:'Prediction League Leaderboard', text:caption})
        .then(function(){toast('✅ Shared!','gold');})
        .catch(function(){ downloadLbImage(blob); });
    } else {
      downloadLbImage(blob);
    }
  },'image/png');
}
function downloadLbImage(blob){
  var url=URL.createObjectURL(blob);
  var a=document.createElement('a'); a.href=url; a.download='leaderboard.png';
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(function(){URL.revokeObjectURL(url);},1000);
  toast('📸 Leaderboard saved! Share it in WhatsApp','gold');
}

function escHtml(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}

// ── Sponsor image picker (downscale to base64) ──────────────
var editKeepImg=true;
function spPick(inp,hiddenId,prevId){
  var f=inp.files[0]; if(!f) return;
  var rd=new FileReader();
  rd.onload=function(){
    var img=new Image();
    img.onload=function(){
      var maxW=600, sc=Math.min(1,maxW/img.width);
      var w=Math.round(img.width*sc), h=Math.round(img.height*sc);
      var cv=document.createElement('canvas'); cv.width=w; cv.height=h;
      cv.getContext('2d').drawImage(img,0,0,w,h);
      var data=cv.toDataURL('image/jpeg',0.82);
      document.getElementById(hiddenId).value=data;
      var p=document.getElementById(prevId); if(p){p.src=data;p.style.display='block';}
      if(hiddenId==='e_spimg') editKeepImg=false;
    };
    img.src=rd.result;
  };
  rd.readAsDataURL(f);
}
function spClear(hiddenId,prevId){
  document.getElementById(hiddenId).value='';
  var p=document.getElementById(prevId); if(p){p.src='';p.style.display='none';}
  if(hiddenId==='e_spimg') editKeepImg=false;
}

// ── Share MATCH POSTER (with sponsor image) to WhatsApp ─────
function shareMatchPoster(id){
  toast('🎨 Building poster…','gold');
  fetch(SELF+'?action=sponsor_card&match_id='+id).then(function(r){return r.json();}).then(function(res){
    if(!res.ok){toast('Could not load match','err');return;}
    var d=res.m;
    loadCardImg(LOGO_B64||'',false,function(logo){
      if(d.sponsor_image){ loadCardImg(d.sponsor_image,false,function(sp){ drawMatchPoster(d,logo,sp); }); }
      else drawMatchPoster(d,logo,null);
    });
  }).catch(function(){toast('Failed','err');});
}
function drawMatchPoster(d,logo,spImg){
  var W=1080, hasSp=!!d.sponsor_name;
  // If sponsor exists, make a tall poster where sponsor image dominates
  var H = hasSp ? 1920 : 1180;
  var c=document.createElement('canvas'); c.width=W; c.height=H;
  var x=c.getContext('2d'); var cx=W/2;

  // ── BACKGROUND ──
  var g=x.createLinearGradient(0,0,0,H);
  g.addColorStop(0,'#020612'); g.addColorStop(.5,'#0a1628'); g.addColorStop(1,'#0d2137');
  x.fillStyle=g; x.fillRect(0,0,W,H);

  // Gold border
  x.strokeStyle='#FFD700'; x.lineWidth=10; x.strokeRect(24,24,W-48,H-48);
  x.textAlign='center';

  // ═══════════════════════════════════════════════
  //  HEADER — MINIMAL (small club logo + tiny text)
  // ═══════════════════════════════════════════════
  var hy = 70;  // header Y position
  // Tiny club logo
  var lr=32;
  x.save();
  x.beginPath(); x.arc(70,hy,lr,0,Math.PI*2); x.closePath();
  x.lineWidth=3; x.strokeStyle='rgba(255,215,0,.5)'; x.stroke();
  if(logo){ x.clip(); x.drawImage(logo,70-lr,hy-lr,lr*2,lr*2); }
  x.restore();
  if(!logo){ x.font='28px sans-serif'; x.fillStyle='#FFD700'; x.fillText('🏆',70,hy+10); }

  // Club name — small, left aligned next to logo
  x.textAlign='left';
  x.fillStyle='rgba(255,255,255,.7)'; x.font='bold 22px sans-serif';
  x.fillText(RANK_DATA.club, 118, hy+8);
  x.fillStyle='rgba(255,255,255,.4)'; x.font='16px sans-serif';
  x.fillText('📍 ' + (RANK_DATA.place||'Vettikkattiri'), 118, hy+30);

  // Right side: tiny FIFA WC 2026 badge
  x.textAlign='right';
  x.fillStyle='#FFD700'; x.font='bold 18px sans-serif';
  x.fillText('FIFA WC 2026', W-50, hy+12);
  x.fillStyle='rgba(255,255,255,.4)'; x.font='13px sans-serif';
  x.fillText('PREDICTION LEAGUE', W-50, hy+30);
  x.textAlign='center';

  // ═══════════════════════════════════════════════
  //  MATCH DETAILS — COMPACT BAR
  // ═══════════════════════════════════════════════
  var my = 128;  // match bar Y
  // Background bar
  x.fillStyle='rgba(255,255,255,.06)'; rrect(x,40,my,W-80,64,14); x.fill();
  x.lineWidth=1; x.strokeStyle='rgba(255,215,0,.2)'; rrect(x,40,my,W-80,64,14); x.stroke();

  // Flags + team names (small)
  x.font='36px sans-serif';
  x.fillText(d.f1, cx-220, my+44);
  x.fillText(d.f2, cx+220, my+44);
  x.fillStyle='#fff'; x.font='bold 22px sans-serif';
  var n1=d.team1.length>10?d.team1.slice(0,9)+'…':d.team1;
  var n2=d.team2.length>10?d.team2.slice(0,9)+'…':d.team2;
  x.fillText(n1, cx-220, my+44);  // overlaid on flag position - need adjustment
  // Actually let's do: flag left, name left-of-center, VS center, name right-of-center, flag right
  x.textAlign='left';
  x.fillStyle='#fff'; x.font='bold 24px sans-serif';
  x.fillText(d.f1+' '+n1, 70, my+42);
  x.textAlign='right';
  x.fillText(n2+' '+d.f2, W-70, my+42);
  x.textAlign='center';
  // VS or Score
  if(d.status==='finished' && d.score1!==null){
    x.fillStyle='#00ff88'; x.font='900 32px sans-serif';
    x.fillText(d.score1+'–'+d.score2, cx, my+42);
  } else {
    x.fillStyle='#00d4ff'; x.font='900 26px sans-serif';
    x.fillText('VS', cx, my+42);
  }
  // Round chip below
  x.fillStyle='rgba(255,215,0,.18)'; rrect(x,cx-90,my+72,180,30,15); x.fill();
  x.fillStyle='#FFD700'; x.font='bold 15px sans-serif';
  x.fillText((d.round||'Match')+' · '+d.date, cx, my+92);

  // ═══════════════════════════════════════════════
  //  SPONSOR IMAGE — THE HERO (fills most of poster)
  // ═══════════════════════════════════════════════
  if(hasSp){
    var sy = 228;           // sponsor section starts here
    var sBoxH = H - sy - 200;  // takes up most of remaining space (leaves room for footer)
    var pad=18;
    var boxX=40, boxW=W-80;

    // Draw sponsor image filling the entire box (cover mode)
    if(spImg){
      x.save();
      rrect(x,boxX,sy,boxW,sBoxH,pad); x.clip();
      var sc=Math.max(boxW/spImg.width, sBoxH/spImg.height);
      var dw=spImg.width*sc, dh=spImg.height*sc;
      x.drawImage(spImg, boxX+(boxW-dw)/2, sy+(sBoxH-dh)/2, dw, dh);
      x.restore();
      // Subtle gradient overlay at very bottom for text readability
      var go=x.createLinearGradient(0,sy+sBoxH-220,0,sy+sBoxH);
      go.addColorStop(0,'rgba(2,6,18,0)');
      go.addColorStop(.6,'rgba(2,6,18,.55)');
      go.addColorStop(1,'rgba(2,6,18,.88)');
      x.fillStyle=go; rrect(x,boxX,sy,boxW,sBoxH,pad); x.fill();
    } else {
      x.fillStyle='rgba(255,255,255,.06)'; rrect(x,boxX,sy,boxW,sBoxH,pad); x.fill();
    }

    // Gold border around sponsor box
    x.lineWidth=3; x.strokeStyle='rgba(255,215,0,.5)'; rrect(x,boxX,sy,boxW,sBoxH,pad); x.stroke();

    // Sponsor text overlaid at bottom of image (big, readable)
    x.textAlign='center';
    // Small "MATCH SPONSOR" label at top-left of box
    x.font='bold 16px sans-serif';
    var lbl='🤝 MATCH SPONSOR', lw=x.measureText(lbl).width;
    x.fillStyle='rgba(2,6,18,.7)'; rrect(x,boxX+14,sy+14,lw+24,28,14); x.fill();
    x.lineWidth=1; x.strokeStyle='rgba(255,215,0,.4)'; rrect(x,boxX+14,sy+14,lw+24,28,14); x.stroke();
    x.fillStyle='#FFD700'; x.fillText(lbl, boxX+14+(lw+24)/2, sy+34);

    // Big sponsor name at bottom of box
    x.shadowColor='rgba(0,0,0,.9)'; x.shadowBlur=18; x.shadowOffsetX=0; x.shadowOffsetY=4;
    x.fillStyle='#fff'; x.font='900 52px sans-serif';
    var nm=(d.sponsor_name||''); if(nm.length>22) nm=nm.slice(0,21)+'…';
    x.fillText(nm, cx, sy+sBoxH-68);
    x.shadowColor='transparent'; x.shadowBlur=0;

    // Sponsor tagline
    if(d.sponsor_tag){
      x.fillStyle='rgba(255,255,255,.85)'; x.font='24px sans-serif';
      var tg=(d.sponsor_tag||''); if(tg.length>38) tg=tg.slice(0,37)+'…';
      x.fillText(tg, cx, sy+sBoxH-30);
    }
  }

  // ═══════════════════════════════════════════════
  //  FOOTER — Minimal bottom strip
  // ═══════════════════════════════════════════════
  var fy = H - 110;
  x.fillStyle='rgba(0,0,0,.35)'; rrect(x,30,fy,W-60,80,0); x.fill();
  x.fillStyle='rgba(255,215,0,.45)'; x.fillRect(30,fy,W-60,3);

  // Left: club
  x.textAlign='left';
  if(logo){ x.save(); x.beginPath(); x.arc(72,fy+40,26,0,Math.PI*2); x.closePath(); x.clip(); x.drawImage(logo,46,fy+14,52,52); x.restore(); }
  else { x.font='36px sans-serif'; x.textAlign='center'; x.fillText('🏆',72,fy+50); x.textAlign='left'; }
  x.fillStyle='#FFD700'; x.font='bold 24px sans-serif';
  x.fillText(RANK_DATA.club, 110, fy+38);
  x.fillStyle='rgba(255,255,255,.55)'; x.font='17px sans-serif';
  x.fillText('📍 '+(RANK_DATA.place||''), 110, fy+62);

  // Right: website + tagline
  x.textAlign='right';
  x.fillStyle='rgba(255,255,255,.5)'; x.font='bold 18px sans-serif';
  x.fillText('🌐 '+location.host, W-50, fy+38);
  x.fillStyle='rgba(255,255,255,.35)'; x.font='15px sans-serif';
  x.fillText('⚽ Predict · Compete · Win Points!', W-50, fy+62);

  // "PREDICT & WIN" call to action (small, centered above footer)
  x.textAlign='center';
  x.fillStyle='#FFD700'; x.font='bold 26px sans-serif';
  x.fillText('🎯 PREDICT & WIN POINTS!', cx, fy-18);

  exportMatchPoster(c,d);
}function exportMatchPoster(c,d){
  c.toBlob(function(blob){
    if(!blob){toast('Export failed','err');return;}
    var file=new File([blob],'match.png',{type:'image/png'});
    var link=location.href.split('?')[0];
    var cap='⚽ '+d.f1+' '+d.team1+' vs '+d.team2+' '+d.f2+'\n🏆 '+RANK_DATA.club+' — FIFA WC 2026 Prediction League';
    if(d.sponsor_name){ cap+='\n\n🤝 Sponsored by '+d.sponsor_name; if(d.sponsor_tag) cap+=' — '+d.sponsor_tag; if(d.sponsor_link) cap+='\n'+d.sponsor_link; }
    cap+='\n🎯 Predict now: '+link;
    if(navigator.canShare && navigator.canShare({files:[file]})){
      navigator.share({files:[file],text:cap}).then(function(){toast('✅ Shared!','gold');}).catch(function(){posterDownload(blob);});
    } else { posterDownload(blob); }
  },'image/png');
}
function posterDownload(blob){
  var url=URL.createObjectURL(blob); var a=document.createElement('a');
  a.href=url; a.download='match-poster.png'; document.body.appendChild(a); a.click(); document.body.removeChild(a);
  setTimeout(function(){URL.revokeObjectURL(url);},1000);
  toast('📸 Poster saved! Share it in WhatsApp','gold');
}

// ── WhatsApp Share ──────────────────────────────────────────
var waCurrentMsg='', waGroupUrl='', waAnyUrl='';

function openWaShare(matchId, label){
  // Load club logo into modal header
  var logoWrap = document.getElementById('waLogoWrap');
  if(LOGO_B64){
    logoWrap.innerHTML='<img src="'+LOGO_B64+'" style="width:40px;height:40px;object-fit:cover;border-radius:50%">';
  }
  document.getElementById('waMatchLabel').textContent=label;
  document.getElementById('waPreview').textContent='Loading…';
  document.getElementById('waModal').classList.add('on');
  document.body.style.overflow='hidden';

  // Fetch message from server
  var fd=new FormData();
  fd.append('action','wa_share'); fd.append('match_id',matchId);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      waCurrentMsg = res.msg;
      waGroupUrl   = res.group_url;
      waAnyUrl     = res.wa_url;
      document.getElementById('waPreview').textContent = res.msg;
      // Show/hide group button based on whether group URL is set
      var grpBtn = document.getElementById('waBtnGroup');
      if(!res.group_url || res.group_url.indexOf('YOUR_GROUP')>=0){
        grpBtn.style.opacity='.4'; grpBtn.title='Set Club WA Group URL in Club Settings';
      } else {
        grpBtn.style.opacity='1'; grpBtn.title='';
      }
    } else {
      document.getElementById('waPreview').textContent='Error: '+res.msg;
    }
  });
}

// Share a FINISHED match RESULT to WhatsApp
function openWaResult(matchId, label){
  var logoWrap = document.getElementById('waLogoWrap');
  if(LOGO_B64){
    logoWrap.innerHTML='<img src="'+LOGO_B64+'" style="width:40px;height:40px;object-fit:cover;border-radius:50%">';
  }
  document.getElementById('waMatchLabel').textContent='Result · '+label;
  document.getElementById('waPreview').textContent='Loading…';
  document.getElementById('waModal').classList.add('on');
  document.body.style.overflow='hidden';

  var fd=new FormData();
  fd.append('action','wa_result'); fd.append('match_id',matchId);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      waCurrentMsg = res.msg;
      waGroupUrl   = res.group_url;
      waAnyUrl     = res.wa_url;
      document.getElementById('waPreview').textContent = res.msg;
      var grpBtn = document.getElementById('waBtnGroup');
      if(!res.group_url || res.group_url.indexOf('YOUR_GROUP')>=0){
        grpBtn.style.opacity='.4'; grpBtn.title='Set Club WA Group URL in Club Settings';
      } else {
        grpBtn.style.opacity='1'; grpBtn.title='';
      }
    } else {
      document.getElementById('waPreview').textContent='Error: '+res.msg;
    }
  });
}

// Share ALL members' predictions for a match to WhatsApp
function openWaPredictions(matchId, label){
  var logoWrap = document.getElementById('waLogoWrap');
  if(LOGO_B64){
    logoWrap.innerHTML='<img src="'+LOGO_B64+'" style="width:40px;height:40px;object-fit:cover;border-radius:50%">';
  }
  document.getElementById('waMatchLabel').textContent='Predictions · '+label;
  document.getElementById('waPreview').textContent='Loading…';
  document.getElementById('waModal').classList.add('on');
  document.body.style.overflow='hidden';

  var fd=new FormData();
  fd.append('action','wa_predictions'); fd.append('match_id',matchId);
  fetch(SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      waCurrentMsg = res.msg;
      waGroupUrl   = res.group_url;
      waAnyUrl     = res.wa_url;
      document.getElementById('waPreview').textContent = res.msg;
      var grpBtn = document.getElementById('waBtnGroup');
      if(!res.group_url || res.group_url.indexOf('YOUR_GROUP')>=0){
        grpBtn.style.opacity='.4'; grpBtn.title='Set Club WA Group URL in Club Settings';
      } else {
        grpBtn.style.opacity='1'; grpBtn.title='';
      }
    } else {
      document.getElementById('waPreview').textContent='Error: '+res.msg;
    }
  });
}

function closeWaModal(){
  document.getElementById('waModal').classList.remove('on');
  document.body.style.overflow='';
}

function openWaGroup(){
  if(!waGroupUrl || waGroupUrl.indexOf('YOUR_GROUP')>=0){
    toast('Set Club WA Group URL in Club Settings first','err'); return;
  }
  // First copy message, then open group
  if(navigator.clipboard){
    navigator.clipboard.writeText(waCurrentMsg).then(function(){
      toast('✅ Message copied! Paste it in the group.','gold');
      setTimeout(function(){ window.open(waGroupUrl,'_blank'); }, 500);
    });
  } else {
    window.open(waGroupUrl,'_blank');
    toast('Open group and paste the message','gold');
  }
}

function openWaAny(){
  window.open(waAnyUrl,'_blank');
}

function copyWaMsg(){
  if(!waCurrentMsg){toast('No message to copy','err');return;}
  if(navigator.clipboard){
    navigator.clipboard.writeText(waCurrentMsg).then(function(){
      toast('✅ Copied! Paste in WhatsApp','gold');
    }).catch(function(){
      fallbackCopy();
    });
  } else {
    fallbackCopy();
  }
}
function fallbackCopy(){
  var ta=document.createElement('textarea');
  ta.value=waCurrentMsg; ta.style.position='fixed'; ta.style.opacity='0';
  document.body.appendChild(ta); ta.focus(); ta.select();
  try{document.execCommand('copy');toast('✅ Copied!','gold');}catch(e){toast('Copy failed — select and copy manually','err');}
  document.body.removeChild(ta);
}

// ════ WINNER CELEBRATION — Google-style confetti ════
(function(){
  var canvas,ctx,parts=[],raf=null,fired={};
  var COLORS=['#ffd24a','#ffffff','#00ff88','#ff5a7a','#00d4ff','#ffb347'];
  function ensure(){ canvas=document.getElementById('celebCanvas'); if(!canvas)return false; ctx=canvas.getContext('2d'); return true; }
  function resize(){ if(canvas){canvas.width=window.innerWidth;canvas.height=window.innerHeight;} }
  function burst(flag){
    if(!ensure())return; resize(); canvas.style.display='block';
    for(var i=0;i<95;i++){
      var useFlag=flag&&Math.random()<0.16;
      parts.push({
        x:Math.random()*canvas.width, y:-20-Math.random()*canvas.height*0.35,
        vx:(Math.random()-0.5)*3.2, vy:2+Math.random()*4, g:0.06+Math.random()*0.05,
        rot:Math.random()*6.28, vr:(Math.random()-0.5)*0.3,
        size:useFlag?(16+Math.random()*10):(6+Math.random()*7),
        color:COLORS[(Math.random()*COLORS.length)|0], flag:useFlag?flag:null,
        life:0, ttl:140+Math.random()*60
      });
    }
    if(!raf)raf=requestAnimationFrame(tick);
  }
  function tick(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    for(var i=parts.length-1;i>=0;i--){
      var p=parts[i];
      p.vy+=p.g; p.x+=p.vx; p.y+=p.vy; p.rot+=p.vr; p.life++;
      if(p.life>p.ttl||p.y>canvas.height+30){parts.splice(i,1);continue;}
      ctx.save(); ctx.globalAlpha=Math.max(0,1-(p.life/p.ttl));
      ctx.translate(p.x,p.y); ctx.rotate(p.rot);
      if(p.flag){ctx.font=p.size+'px serif';ctx.textAlign='center';ctx.fillText(p.flag,0,0);}
      else{ctx.fillStyle=p.color;ctx.fillRect(-p.size/2,-p.size/2,p.size,p.size*0.6);}
      ctx.restore();
    }
    if(parts.length)raf=requestAnimationFrame(tick);
    else{raf=null; if(canvas)canvas.style.display='none';}
  }
  window.celebrateCard=function(card,force){
    if(!card||!card.dataset.win)return;
    var id=card.dataset.id;
    if(!force&&fired[id])return;
    fired[id]=true; burst(card.dataset.wflag||'🎉');
  };
  window.addEventListener('resize',resize);
  function wire(){
    var cards=document.querySelectorAll('.match-card.mc-decided');
    if(!cards.length)return;
    if('IntersectionObserver' in window){
      var io=new IntersectionObserver(function(es){
        es.forEach(function(e){ if(e.isIntersecting) window.celebrateCard(e.target,false); });
      },{threshold:0.55});
      cards.forEach(function(c){ io.observe(c); });
    }
    cards.forEach(function(c){
      c.addEventListener('click',function(ev){ if(ev.target.closest('button,a'))return; window.celebrateCard(c,true); });
    });
  }
  if(document.readyState!=='loading') wire();
  else document.addEventListener('DOMContentLoaded',wire);
})();
</script>
<canvas id="celebCanvas"></canvas>

<?php require_once __DIR__ . '/../includes/footer.php'; ?>
