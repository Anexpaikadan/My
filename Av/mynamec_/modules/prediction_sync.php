<?php
// ============================================================
// modules/prediction_sync.php
// Auto-import FIFA World Cup 2026 fixtures + live results
// Source: football-data.org (free tier covers competition "WC")
// Run via Hostinger CRON. Awards points like the admin panel.
// BUILD: PSYNC-4
// ============================================================
//
//  SETUP (one time):
//  1) Get a FREE token at https://www.football-data.org/client/register
//  2) Paste it into $API_TOKEN below.
//  3) Change $SYNC_KEY to your own secret word.
//  4) Add a Hostinger cron job (hPanel → Advanced → Cron Jobs), every 15 min:
//        wget -q -O /dev/null "https://mynamecc.online/modules/prediction_sync.php?key=YOUR_SECRET"
//     (or: curl -s "https://mynamecc.online/modules/prediction_sync.php?key=YOUR_SECRET")
//  You can also open that URL in a browser any time to sync manually.
// ============================================================

require_once __DIR__ . '/../includes/config.php';
@set_time_limit(120);

// ───── CONFIG ─────
$API_TOKEN = '';                                     // <-- your free football-data.org token
$SYNC_KEY  = 'avwcd389ced1e2fd';               // <-- your own secret
$COMP      = 'WC';                               // World Cup competition code
// NEW matches are ONLY added when you give a period (from/to) or a date.
// A plain run (cron with no dates) just updates live scores/results — it never adds.
//   Add a period : ?key=KEY&from=2026-06-02&to=2026-06-04
//   Add one day  : ?key=KEY&date=2026-06-02
//   Picker page  : ?key=KEY&ui=1

// ───── auth (works for both URL ?key= and CLI key=) ─────
$key = $_GET['key'] ?? '';
if ($key === '' && !empty($argv)) {
  foreach ($argv as $a) { if (strpos($a, 'key=') === 0) { $key = substr($a, 4); } }
}
$UI = isset($_GET['ui']);   // browser control panel (date picker)
if ($UI) { header('Content-Type: text/html; charset=utf-8'); }
else      { header('Content-Type: text/plain; charset=utf-8'); }

function ps_die($msg) {
  global $UI, $SYNC_KEY;
  if ($UI) { echo ps_page('<p style="color:#ff6a8a">'.htmlspecialchars($msg).'</p>', $SYNC_KEY); }
  else     { echo $msg."\n"; }
  exit;
}
function ps_page($body, $key) {
  $tz = new DateTimeZone('Asia/Kolkata');
  $today = (new DateTime('now', $tz))->format('Y-m-d');
  $plus2 = (new DateTime('now', $tz))->modify('+2 day')->format('Y-m-d');
  $k = htmlspecialchars($key);
  return '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">'
    .'<title>WC Match Sync</title><style>body{font-family:system-ui,sans-serif;background:#0b1020;color:#eef;margin:0;padding:1.2rem;max-width:520px;margin:auto}'
    .'h2{color:#FFD700;margin:.2rem 0 1rem}.card{background:#141c33;border:1px solid #2a3556;border-radius:14px;padding:1rem;margin-bottom:1rem}'
    .'label{font-size:.8rem;color:#9fb0d6}input[type=date]{width:100%;padding:.6rem;border-radius:9px;border:1px solid #2a3556;background:#0b1020;color:#fff;font-size:1rem;margin:.3rem 0 .8rem}'
    .'.two{display:flex;gap:.6rem}.two>div{flex:1}'
    .'button,.btn{display:inline-block;background:linear-gradient(135deg,#FFD700,#FFC107);color:#1a1300;border:none;border-radius:9px;padding:.65rem 1rem;font-weight:800;cursor:pointer;text-decoration:none;font-size:.85rem;margin:.2rem .2rem 0 0}'
    .'.btn.d{background:#22305a;color:#fff}pre{background:#0b1020;border:1px solid #2a3556;border-radius:9px;padding:.7rem;white-space:pre-wrap;font-size:.8rem;color:#bfe}'
    .'small{color:#7f8db5}</style>'
    .'<h2>⚽ World Cup Match Sync</h2>'
    .'<div class="card"><form method="get"><input type="hidden" name="key" value="'.$k.'"><input type="hidden" name="ui" value="1">'
    .'<label>Add matches in a period (From → To)</label>'
    .'<div class="two"><div><label>From</label><input type="date" name="from" value="'.$today.'"></div>'
    .'<div><label>To</label><input type="date" name="to" value="'.$plus2.'"></div></div>'
    .'<button type="submit">➕ Add matches in this period</button>'
    .'<div style="margin-top:.5rem"><small>Pick the same date in both boxes to add just one day.</small></div></form></div>'
    .'<div class="card"><label>Update results only (no new matches)</label><br>'
    .'<a class="btn d" href="?key='.$k.'&ui=1">🔄 Update results now</a></div>'
    .'<div class="card">'.$body.'</div>';
}

if (!hash_equals($SYNC_KEY, (string)$key)) { http_response_code(403); ps_die('Forbidden: bad key'); }
if ($API_TOKEN === '' || strlen($API_TOKEN) < 16) {
  ps_die('⚠ No API token set. Get a free token at football-data.org and paste it into $API_TOKEN.');
}

// ───── ensure schema (idempotent) ─────
foreach ([
  "ALTER TABLE prediction_matches ADD COLUMN ext_id INT DEFAULT NULL",
  "ALTER TABLE prediction_matches ADD UNIQUE KEY uniq_ext (ext_id)"
] as $sql) { try { db()->exec($sql); } catch (Exception $e) {} }

// ───── helper maps ─────
function ps_status($s) {
  $s = strtoupper($s);
  if (in_array($s, ['IN_PLAY','PAUSED','LIVE'], true)) return 'live';
  if (in_array($s, ['FINISHED','AWARDED'], true))      return 'finished';
  return 'upcoming'; // SCHEDULED, TIMED, POSTPONED, SUSPENDED, CANCELLED
}
function ps_round($stage, $group) {
  $stage = strtoupper((string)$stage);
  if ($stage === 'GROUP_STAGE') return $group ? ('Group ' . substr($group, -1)) : 'Group Stage';
  $map = [
    'LAST_32'=>'Round of 32','LAST_16'=>'Round of 16','QUARTER_FINALS'=>'Quarter-final',
    'SEMI_FINALS'=>'Semi-final','THIRD_PLACE'=>'Third place','FINAL'=>'Final','PLAYOFFS'=>'Play-off'
  ];
  if (isset($map[$stage])) return $map[$stage];
  return $stage ? ucwords(strtolower(str_replace('_', ' ', $stage))) : 'Knockout';
}
function ps_flag($tla) {
  static $m = [
    'ARG'=>'🇦🇷','AUS'=>'🇦🇺','AUT'=>'🇦🇹','BEL'=>'🇧🇪','BRA'=>'🇧🇷','CMR'=>'🇨🇲','CAN'=>'🇨🇦','CHI'=>'🇨🇱',
    'COL'=>'🇨🇴','CRC'=>'🇨🇷','CRO'=>'🇭🇷','CIV'=>'🇨🇮','DEN'=>'🇩🇰','ECU'=>'🇪🇨','EGY'=>'🇪🇬','ENG'=>'🏴󠁧󠁢󠁥󠁮󠁧󠁿',
    'FRA'=>'🇫🇷','GER'=>'🇩🇪','GHA'=>'🇬🇭','GRE'=>'🇬🇷','IRN'=>'🇮🇷','ITA'=>'🇮🇹','JAM'=>'🇯🇲','JPN'=>'🇯🇵',
    'KOR'=>'🇰🇷','MEX'=>'🇲🇽','MAR'=>'🇲🇦','NED'=>'🇳🇱','NGA'=>'🇳🇬','NZL'=>'🇳🇿','NOR'=>'🇳🇴','PAN'=>'🇵🇦',
    'PAR'=>'🇵🇾','PER'=>'🇵🇪','POL'=>'🇵🇱','POR'=>'🇵🇹','QAT'=>'🇶🇦','IRL'=>'🇮🇪','KSA'=>'🇸🇦','SCO'=>'🏴󠁧󠁢󠁳󠁣󠁴󠁿',
    'SEN'=>'🇸🇳','SRB'=>'🇷🇸','SVN'=>'🇸🇮','RSA'=>'🇿🇦','ESP'=>'🇪🇸','SWE'=>'🇸🇪','SUI'=>'🇨🇭','TUN'=>'🇹🇳',
    'TUR'=>'🇹🇷','UKR'=>'🇺🇦','USA'=>'🇺🇸','URU'=>'🇺🇾','UZB'=>'🇺🇿','WAL'=>'🏴󠁧󠁢󠁷󠁬󠁳󠁿','ALG'=>'🇩🇿','DZA'=>'🇩🇿',
    'CPV'=>'🇨🇻','JOR'=>'🇯🇴','HAI'=>'🇭🇹','CUW'=>'🇨🇼','NCL'=>'🇳🇨','PAN'=>'🇵🇦','HON'=>'🇭🇳','UAE'=>'🇦🇪'
  ];
  $tla = strtoupper((string)$tla);
  return $m[$tla] ?? null;
}

// ───── fetch from API ─────
$url = "https://api.football-data.org/v4/competitions/{$COMP}/matches";
$ch = curl_init($url);
curl_setopt_array($ch, [
  CURLOPT_RETURNTRANSFER => true,
  CURLOPT_HTTPHEADER     => ['X-Auth-Token: ' . $API_TOKEN],
  CURLOPT_TIMEOUT        => 30,
  CURLOPT_SSL_VERIFYPEER => true,
]);
$resp = curl_exec($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$err  = curl_error($ch);
curl_close($ch);

if ($resp === false) { ps_die("❌ Network error: {$err}"); }
if ($code === 403)   { ps_die("❌ 403 — token invalid or competition not on your plan."); }
if ($code === 429)   { ps_die("❌ 429 — rate limited (free tier = 10 req/min). Try a longer interval."); }
if ($code !== 200)   { ps_die("❌ HTTP {$code} from API."); }

$data = json_decode($resp, true);
if (!isset($data['matches']) || !is_array($data['matches'])) { ps_die("❌ Unexpected response."); }

// ───── upsert ─────
$added = 0; $updated = 0; $skipped = 0; $deferred = 0; $rescore = [];
$tz = new DateTimeZone('Asia/Kolkata');

// ── Decide what to ADD (default = nothing; only update results) ──
$tz_now = new DateTime('now', $tz);
function ps_param($name){ // read from GET or CLI "name=value"
  if (isset($_GET[$name])) return trim($_GET[$name]);
  if (!empty($GLOBALS['argv'])) { foreach ($GLOBALS['argv'] as $a) { if (strpos($a,$name.'=')===0) return substr($a,strlen($name)+1); } }
  return '';
}
function ps_isdate($d){ return preg_match('/^\d{4}-\d{2}-\d{2}$/', $d) === 1; }

$from = ps_param('from'); $to = ps_param('to'); $pickDate = ps_param('date'); $days = ps_param('days');
$addMode = 'none'; $dStart = ''; $dEnd = ''; $modeText = 'results only (no new matches added)';

if (ps_isdate($from) || ps_isdate($to)) {
  // PERIOD: From → To (inclusive)
  if (!ps_isdate($from)) $from = ps_isdate($to) ? $to : $tz_now->format('Y-m-d');
  if (!ps_isdate($to))   $to   = $from;
  if ($to < $from) { $t=$from; $from=$to; $to=$t; }
  $addMode='range'; $dStart=$from.' 00:00:00'; $dEnd=$to.' 23:59:59';
  $modeText = "adding matches from {$from} to {$to}";
} elseif (ps_isdate($pickDate)) {
  // single DATE
  $addMode='range'; $dStart=$pickDate.' 00:00:00'; $dEnd=$pickDate.' 23:59:59';
  $modeText = "adding matches on {$pickDate}";
} elseif ($days !== '' && ctype_digit($days)) {
  // optional rolling window (only if days= is explicitly given)
  $d=(int)$days; if($d>400)$d=400;
  $addMode='range';
  $dStart=(clone $tz_now)->modify('-1 day')->format('Y-m-d H:i:s');
  $dEnd  =(clone $tz_now)->modify("+{$d} day")->format('Y-m-d H:i:s');
  $modeText = "adding matches up to {$d} day(s) ahead";
}

foreach ($data['matches'] as $m) {
  $ext = (int)($m['id'] ?? 0);
  $t1  = $m['homeTeam']['name'] ?? null;
  $t2  = $m['awayTeam']['name'] ?? null;
  if (!$ext || !$t1 || !$t2) { $skipped++; continue; } // skip TBD knockout placeholders

  $c1 = $m['homeTeam']['tla'] ?? null;
  $c2 = $m['awayTeam']['tla'] ?? null;
  $f1 = ps_flag($c1); $f2 = ps_flag($c2);

  try { $dt = new DateTime($m['utcDate'], new DateTimeZone('UTC')); $dt->setTimezone($tz); $when = $dt->format('Y-m-d H:i:s'); }
  catch (Exception $e) { $when = date('Y-m-d H:i:s'); }

  $venue  = $m['venue'] ?? null;
  $round  = ps_round($m['stage'] ?? '', $m['group'] ?? null);
  $status = ps_status($m['status'] ?? '');
  $s1 = $m['score']['fullTime']['home'] ?? null;
  $s2 = $m['score']['fullTime']['away'] ?? null;
  $s1 = ($s1 === null) ? null : (int)$s1;
  $s2 = ($s2 === null) ? null : (int)$s2;
  $winner = null;
  if ($status === 'finished' && $s1 !== null && $s2 !== null) {
    $winner = $s1 > $s2 ? 'team1' : ($s2 > $s1 ? 'team2' : 'draw');
  }

  // existing?
  $ex = db()->prepare("SELECT id,status,score1,score2 FROM prediction_matches WHERE ext_id=?");
  $ex->execute([$ext]); $row = $ex->fetch();

  if ($row) {
    db()->prepare("UPDATE prediction_matches SET team1=?,team2=?,team1_flag=?,team2_flag=?,team1_code=?,team2_code=?,
                   match_date=?,stadium=?,round=?,status=?,score1=?,score2=?,winner=? WHERE id=?")
       ->execute([$t1,$t2,$f1,$f2,$c1,$c2,$when,$venue,$round,$status,$s1,$s2,$winner,$row['id']]);
    $updated++;
    $becameFinished = ($status === 'finished' && $winner !== null) &&
                      ($row['status'] !== 'finished' || (string)$row['score1'] !== (string)$s1 || (string)$row['score2'] !== (string)$s2);
    if ($becameFinished) $rescore[] = ['id'=>(int)$row['id'],'winner'=>$winner,'s1'=>$s1,'s2'=>$s2];
  } else {
    // NEW match → only add if a period/date was given AND it falls inside it
    if ($addMode === 'none')          { $deferred++; continue; }
    if ($when < $dStart || $when > $dEnd) { $deferred++; continue; }
    db()->prepare("INSERT INTO prediction_matches(ext_id,team1,team2,team1_flag,team2_flag,team1_code,team2_code,
                   match_date,stadium,round,status,score1,score2,winner,created_by)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)")
       ->execute([$ext,$t1,$t2,$f1,$f2,$c1,$c2,$when,$venue,$round,$status,$s1,$s2,$winner]);
    $added++;
    if ($status === 'finished' && $winner !== null) {
      $rescore[] = ['id'=>(int)db()->lastInsertId(),'winner'=>$winner,'s1'=>$s1,'s2'=>$s2];
    }
  }
}

// ───── award points for newly-finished matches (same rules as admin) ─────
$scoredPreds = 0;
foreach ($rescore as $r) {
  $preds = db()->prepare("SELECT * FROM member_predictions WHERE match_id=?");
  $preds->execute([$r['id']]); $preds = $preds->fetchAll();
  foreach ($preds as $p) {
    $pts = 0;
    if ($p['predicted_winner'] === $r['winner']) {
      $pts += 5; // correct result
      if ($p['predicted_score1'] !== null && $p['predicted_score2'] !== null) {
        $p1 = (int)$p['predicted_score1']; $p2 = (int)$p['predicted_score2'];
        if ($p1 === $r['s1'] && $p2 === $r['s2'])        $pts += 10;        // exact score
        elseif (($p1 - $p2) === ($r['s1'] - $r['s2']))   $pts += 3;         // goal difference
      }
    }
    if (!empty($p['is_double'])) $pts *= 2;
    db()->prepare("UPDATE member_predictions SET points=? WHERE id=?")->execute([$pts, $p['id']]);
    $scoredPreds++;
  }
}

$lines = "✅ World Cup sync complete @ " . date('Y-m-d H:i:s') . " IST\n"
       . "   Mode              : {$modeText}\n"
       . "   Added new matches : {$added}\n"
       . "   Updated matches   : {$updated}\n"
       . "   Not in range      : {$deferred}\n"
       . "   Skipped (TBD)     : {$skipped}\n"
       . "   Finished/scored   : " . count($rescore) . " matches, {$scoredPreds} predictions recalculated\n";

if ($UI) { echo ps_page('<pre>'.htmlspecialchars($lines).'</pre>', $SYNC_KEY); }
else      { echo $lines; }
