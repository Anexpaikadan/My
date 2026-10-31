<?php
// ============================================================
// modules/fixtures.php — FIFA World Cup 2026 Live Fixtures
// Aishwarya Arts & Sports Club — PHP 7.3+ compatible
// Data source: football-data.org API v4 (competition WC / id 2000)
// ============================================================
require_once __DIR__ . '/../includes/config.php';
@date_default_timezone_set('Asia/Kolkata'); // display in IST

$pageOG = [
  'title' => '🏆 World Cup 2026 Fixtures — Aishwarya Arts & Sports Club',
  'desc'  => 'Live FIFA World Cup 2026 fixtures, upcoming matches & results — AASC.',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => rtrim(SITE_URL, '/') . '/modules/fixtures.php',
];
requireLogin();
$me      = currentUser();
$isAdmin = isSportsAdmin($me['role']) || isModuleAdmin('fixtures', $me);
$uid     = (int)$me['id'];
$CLUB    = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
$pageTitle = '🏆 World Cup 2026 Fixtures — '.$CLUB;

// ── Tables (self-contained: API key + response cache) ──────────
try { db()->exec("CREATE TABLE IF NOT EXISTS wc_config (
  k VARCHAR(50) PRIMARY KEY, v TEXT
)"); } catch(Exception $e){}
try { db()->exec("CREATE TABLE IF NOT EXISTS wc_fixtures_cache (
  id TINYINT PRIMARY KEY, payload LONGTEXT, fetched_at DATETIME
)"); } catch(Exception $e){}
try { db()->exec("CREATE TABLE IF NOT EXISTS wc_teams (
  id INT PRIMARY KEY, name VARCHAR(100), tla VARCHAR(8), crest VARCHAR(300)
)"); } catch(Exception $e){}
try { db()->exec("CREATE TABLE IF NOT EXISTS wc_overrides (
  match_id BIGINT NOT NULL, side VARCHAR(4) NOT NULL,
  name VARCHAR(100), tla VARCHAR(8), crest VARCHAR(300),
  PRIMARY KEY(match_id, side)
)"); } catch(Exception $e){}

// ── Tiny config store (API key etc.) ───────────────────────────
function wc_cfg($k, $d=''){
  try {
    $s = db()->prepare("SELECT v FROM wc_config WHERE k=?");
    $s->execute([$k]); $v = $s->fetchColumn();
    return ($v===false || $v===null) ? $d : $v;
  } catch(Exception $e){ return $d; }
}
function wc_setcfg($k, $v){
  try {
    db()->prepare("INSERT INTO wc_config(k,v) VALUES(?,?) ON DUPLICATE KEY UPDATE v=VALUES(v)")
       ->execute([$k, $v]);
  } catch(Exception $e){}
}
// Key resolution order: config.php constant → wc_config → global setting()
function wc_key(){
  if (defined('FOOTBALL_DATA_KEY') && FOOTBALL_DATA_KEY) return FOOTBALL_DATA_KEY;
  $k = wc_cfg('api_key', '');
  if ($k !== '') return $k;
  return setting('FOOTBALL_DATA_KEY', '');
}

// ── API call (cURL with file_get_contents fallback) ────────────
function wc_api($path){
  $key = wc_key();
  if (!$key) return null;
  $url = 'https://api.football-data.org/v4' . $path;

  if (function_exists('curl_init')) {
    $ch = curl_init($url);
    curl_setopt_array($ch, [
      CURLOPT_RETURNTRANSFER => true,
      CURLOPT_HTTPHEADER     => ['X-Auth-Token: '.$key],
      CURLOPT_TIMEOUT        => 12,
      CURLOPT_CONNECTTIMEOUT => 6,
      CURLOPT_SSL_VERIFYPEER => true,
    ]);
    $res  = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($res === false || $code !== 200) return null;
    $j = json_decode($res, true);
    return is_array($j) ? $j : null;
  }

  // Fallback
  $ctx = stream_context_create(['http'=>[
    'method'=>'GET', 'timeout'=>12,
    'header'=>"X-Auth-Token: ".$key."\r\n",
    'ignore_errors'=>true
  ]]);
  $res = @file_get_contents($url, false, $ctx);
  if ($res === false) return null;
  $j = json_decode($res, true);
  return is_array($j) ? $j : null;
}

// Which data source is active? ('openfootball' default — free & keyless; or 'football-data' / 'worldcup26')
function wc_source(){ $s = wc_cfg('source',''); return $s ? $s : 'openfootball'; }

// Generic JSON GET (cURL → file_get_contents), optional Bearer token
function wc_http_get($url,$token=''){
  $headers = ['Accept: application/json'];
  if ($token) $headers[] = 'Authorization: Bearer '.$token;
  if (function_exists('curl_init')) {
    $ch=curl_init($url);
    curl_setopt_array($ch,[CURLOPT_RETURNTRANSFER=>true,CURLOPT_HTTPHEADER=>$headers,
      CURLOPT_TIMEOUT=>15,CURLOPT_CONNECTTIMEOUT=>7,CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_FOLLOWLOCATION=>true]);
    $res=curl_exec($ch); $code=(int)curl_getinfo($ch,CURLINFO_HTTP_CODE); curl_close($ch);
    if ($res===false || $code!==200) return null;
    $j=json_decode($res,true); return is_array($j)?$j:null;
  }
  $ctx=stream_context_create(['http'=>['method'=>'GET','timeout'=>15,'header'=>implode("\r\n",$headers)."\r\n",'ignore_errors'=>true]]);
  $res=@file_get_contents($url,false,$ctx); if($res===false) return null;
  $j=json_decode($res,true); return is_array($j)?$j:null;
}

// Fetch all WC matches from the active source, normalise, and cache. Returns payload|null.
function wc_fetch_store(){
  wc_setcfg('last_try', (string)time());
  $src = wc_source();
  if     ($src==='worldcup26')   $j = wc_fetch_worldcup26();
  elseif ($src==='openfootball') $j = wc_fetch_openfootball();
  else                           $j = wc_fetch_footballdata();
  if ($j && isset($j['matches'])) {
    try {
      db()->prepare("INSERT INTO wc_fixtures_cache(id,payload,fetched_at) VALUES(1,?,NOW())
        ON DUPLICATE KEY UPDATE payload=VALUES(payload), fetched_at=VALUES(fetched_at)")
         ->execute([json_encode($j, JSON_UNESCAPED_UNICODE)]);
    } catch(Exception $e){}
    return $j;
  }
  return null;
}

// ── Adapter: football-data.org (v4) ──
function wc_fetch_footballdata(){
  $j = wc_api('/competitions/WC/matches');
  if ($j && isset($j['matches'])) {
    wc_fetch_teams(); // keep the master team list fresh for the picker
    return $j; // already in the internal shape
  }
  return null;
}

// ── Adapter: worldcup26.ir (rezarahiminia) → normalise into the internal shape ──
// Free, but needs a JWT: register once at worldcup26.ir, paste the token in Admin.
function wc_fetch_worldcup26(){
  $base = rtrim(wc_cfg('wc26_base','https://worldcup26.ir'),'/');
  $tok  = wc_cfg('wc26_token','');
  // 1) team id → {name,tla,crest}
  $teamsRaw = wc_http_get($base.'/get/teams', $tok);
  $teamList = wc_wc26_list($teamsRaw);
  $teamMap = [];
  foreach ($teamList as $t) {
    $tid = isset($t['id']) ? (string)$t['id'] : '';
    if ($tid==='') continue;
    $nm  = isset($t['name_en']) ? $t['name_en'] : (isset($t['name'])?$t['name']:'');
    $tla = isset($t['fifa_code']) ? $t['fifa_code'] : (isset($t['code'])?$t['code']:'');
    $cr  = isset($t['flag']) ? $t['flag'] : (isset($t['crest'])?$t['crest']:'');
    $teamMap[$tid] = ['name'=>$nm,'tla'=>$tla,'crest'=>$cr];
  }
  // persist to wc_teams (picker + crest lookup)
  if ($teamMap) {
    try {
      $st=db()->prepare("INSERT INTO wc_teams(id,name,tla,crest) VALUES(?,?,?,?)
        ON DUPLICATE KEY UPDATE name=VALUES(name),tla=VALUES(tla),crest=VALUES(crest)");
      foreach ($teamMap as $tid=>$tv){ if(is_numeric($tid)) $st->execute([(int)$tid,$tv['name'],$tv['tla'],$tv['crest']]); }
    } catch(Exception $e){}
  }
  // 2) games → matches[]
  $gamesRaw = wc_http_get($base.'/get/games', $tok);
  $games = wc_wc26_list($gamesRaw);
  if (!$games) return null;
  $stageMap = ['group'=>'GROUP_STAGE','r32'=>'LAST_32','round32'=>'LAST_32','roundof32'=>'LAST_32',
    'r16'=>'LAST_16','round16'=>'LAST_16','roundof16'=>'LAST_16','last16'=>'LAST_16',
    'qf'=>'QUARTER_FINALS','quarter'=>'QUARTER_FINALS','quarterfinal'=>'QUARTER_FINALS','quarterfinals'=>'QUARTER_FINALS',
    'sf'=>'SEMI_FINALS','semi'=>'SEMI_FINALS','semifinal'=>'SEMI_FINALS','semifinals'=>'SEMI_FINALS',
    'third'=>'THIRD_PLACE','thirdplace'=>'THIRD_PLACE','3rd'=>'THIRD_PLACE','bronze'=>'THIRD_PLACE',
    'final'=>'FINAL'];
  $out = [];
  foreach ($games as $g) {
    $type = strtolower(preg_replace('/[^a-z0-9]/','', isset($g['type'])?$g['type']:''));
    $stage = isset($stageMap[$type]) ? $stageMap[$type] : 'GROUP_STAGE';
    $hid = isset($g['home_team_id']) ? (string)$g['home_team_id'] : '';
    $aid = isset($g['away_team_id']) ? (string)$g['away_team_id'] : '';
    $home = ($hid!=='' && $hid!=='0' && isset($teamMap[$hid])) ? $teamMap[$hid] : null;
    $away = ($aid!=='' && $aid!=='0' && isset($teamMap[$aid])) ? $teamMap[$aid] : null;
    $hs = (isset($g['home_score']) && $g['home_score']!==null && $g['home_score']!=='') ? (int)$g['home_score'] : null;
    $as = (isset($g['away_score']) && $g['away_score']!==null && $g['away_score']!=='') ? (int)$g['away_score'] : null;
    $fin = !empty($g['finished']) && $g['finished']!=='false';
    $live = !empty($g['live']) || (isset($g['status']) && strtolower($g['status'])==='live');
    $winner = null;
    if ($fin && $hs!==null && $as!==null) $winner = ($hs>$as?'HOME_TEAM':($as>$hs?'AWAY_TEAM':'DRAW'));
    $ld = isset($g['local_date']) ? $g['local_date'] : (isset($g['date'])?$g['date']:'');
    $ts = $ld ? strtotime($ld) : false; $iso = $ts ? gmdate('Y-m-d\TH:i:s\Z',$ts) : '';
    $status = $fin ? 'FINISHED' : ($live ? 'IN_PLAY' : 'SCHEDULED');
    $out[] = [
      'id'      => (int)(isset($g['id'])?$g['id']:0),
      'stage'   => $stage,
      'group'   => !empty($g['group']) ? ('GROUP_'.$g['group']) : null,
      'utcDate' => $iso,
      'status'  => $status,
      'homeTeam'=> $home ? ['name'=>$home['name'],'tla'=>$home['tla'],'crest'=>$home['crest']] : ['name'=>null],
      'awayTeam'=> $away ? ['name'=>$away['name'],'tla'=>$away['tla'],'crest'=>$away['crest']] : ['name'=>null],
      'score'   => ['winner'=>$winner,'fullTime'=>['home'=>$hs,'away'=>$as]],
    ];
  }
  return ['matches'=>$out];
}
// worldcup26 responses may be a bare array or wrapped ({data:[…]} / {games:[…]} / {teams:[…]})
function wc_wc26_list($j){
  if (!is_array($j)) return [];
  if (isset($j[0])) return $j;
  foreach (['data','games','matches','teams','result','results','items'] as $k){
    if (isset($j[$k]) && is_array($j[$k])) return $j[$k];
  }
  return [];
}

// ── Adapter: openfootball/worldcup.json → normalise into the internal shape ──
// Completely FREE, no key, public-domain JSON on GitHub. Real team names, scores
// (full-time / extra-time / penalties) and "W80"/"L101" placeholder labels for
// undetermined knockout slots. This is the recommended source for the 48-team R32.
function wc_fetch_openfootball(){
  $url = wc_cfg('of_url','https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json');
  $j = wc_http_get($url);
  if (!$j || empty($j['matches'])) return null;
  $roundMap = [
    'round of 32'=>'LAST_32','round of 16'=>'LAST_16',
    'quarter-final'=>'QUARTER_FINALS','quarter-finals'=>'QUARTER_FINALS','quarterfinal'=>'QUARTER_FINALS',
    'semi-final'=>'SEMI_FINALS','semi-finals'=>'SEMI_FINALS','semifinal'=>'SEMI_FINALS',
    'match for third place'=>'THIRD_PLACE','third place'=>'THIRD_PLACE','third-place play-off'=>'THIRD_PLACE',
    'final'=>'FINAL',
  ];
  $out=[]; $i=0;
  foreach ($j['matches'] as $m) {
    $i++;
    $rk = strtolower(trim(isset($m['round'])?$m['round']:''));
    $stage = isset($roundMap[$rk]) ? $roundMap[$rk] : 'GROUP_STAGE';
    $id = isset($m['num']) ? (int)$m['num'] : (900+$i); // FIFA match number when present
    $iso = wc_of_iso(isset($m['date'])?$m['date']:'', isset($m['time'])?$m['time']:'');
    $home = wc_of_side(isset($m['team1'])?trim($m['team1']):'');
    $away = wc_of_side(isset($m['team2'])?trim($m['team2']):'');
    $sc = isset($m['score'])&&is_array($m['score']) ? $m['score'] : null;
    $hs=$as=null; $winner=null; $fin=false;
    if ($sc) {
      $ft = (isset($sc['ft'])&&is_array($sc['ft']))?$sc['ft']:null;
      $et = (isset($sc['et'])&&is_array($sc['et']))?$sc['et']:null;
      $p  = (isset($sc['p']) &&is_array($sc['p'])) ?$sc['p'] :null;
      if ($ft){ $hs=(int)$ft[0]; $as=(int)$ft[1]; $fin=true; }
      if ($et){ $hs=(int)$et[0]; $as=(int)$et[1]; }   // show after-ET score; winner may be on pens
      $dec = $p ? $p : ($et ? $et : $ft);             // penalties decide, else ET, else FT
      if ($dec){
        if ((int)$dec[0] > (int)$dec[1]) $winner='HOME_TEAM';
        elseif ((int)$dec[1] > (int)$dec[0]) $winner='AWAY_TEAM';
        else $winner='DRAW';
      }
    }
    $row = [
      'id'=>$id,'stage'=>$stage,
      'group'=> !empty($m['group']) ? strtoupper(str_replace('GROUP ','GROUP_',strtoupper($m['group']))) : null,
      'utcDate'=>$iso,'status'=>($fin?'FINISHED':'SCHEDULED'),
      'homeTeam'=>$home['team'], 'awayTeam'=>$away['team'],
      'score'=>['winner'=>$winner,'fullTime'=>['home'=>$hs,'away'=>$as]],
    ];
    if ($home['label']!=='') $row['homeTeamLabel']=$home['label'];
    if ($away['label']!=='') $row['awayTeamLabel']=$away['label'];
    $out[]=$row;
  }
  return ['matches'=>$out];
}
// openfootball date "2026-06-29" + time "16:30 UTC-4" → UTC ISO 8601
function wc_of_iso($date,$time){
  if (!$date) return '';
  $hm='00:00'; $off='+0000';
  if ($time && preg_match('/(\d{1,2}):(\d{2})/',$time,$mm)){
    $hm=sprintf('%02d:%02d',(int)$mm[1],(int)$mm[2]);
    if (preg_match('/UTC\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?/i',$time,$oo)){
      $off=sprintf('%s%02d%02d',$oo[1],(int)$oo[2],isset($oo[3])&&$oo[3]!==''?(int)$oo[3]:0);
    }
  }
  try {
    $dt=new DateTime($date.' '.$hm, new DateTimeZone($off));
    $dt->setTimezone(new DateTimeZone('UTC'));
    return $dt->format('Y-m-d\TH:i:s\Z');
  } catch(Exception $e){
    $ts=strtotime($date.' '.$hm); return $ts?gmdate('Y-m-d\TH:i:s\Z',$ts):($date.'T00:00:00Z');
  }
}
// classify an openfootball team string: real name vs placeholder label
function wc_of_side($name){
  if ($name==='') return ['team'=>['name'=>null],'label'=>''];
  if (preg_match('/^([WL])\s*0*(\d+)$/i',$name,$mm)){   // W80 / L101
    $lbl=(strtoupper($mm[1])==='W'?'Winner M':'Loser M').$mm[2];
    return ['team'=>['name'=>null],'label'=>$lbl];
  }
  if (preg_match('/^([123])\s*([A-L])$/i',$name,$mm)){  // 1A / 2B / 3C group slots
    $ord=['1'=>'Winner','2'=>'Runner-up','3'=>'3rd']; 
    return ['team'=>['name'=>null],'label'=>$ord[$mm[1]].' Grp '.strtoupper($mm[2])];
  }
  $tla=substr(strtoupper(preg_replace('/[^A-Za-z]/','',$name)),0,3);
  $iso=wc_iso($name);
  $crest=$iso?('https://flagcdn.com/w40/'.$iso.'.png'):'';
  return ['team'=>['name'=>$name,'tla'=>$tla,'crest'=>$crest],'label'=>''];
}

// ── National-flag helpers (name → ISO code → flagcdn image + flag emoji) ──
function wc_flag_key($s){
  $s=strtolower(trim((string)$s));
  $s=strtr($s,['ç'=>'c','ã'=>'a','á'=>'a','à'=>'a','é'=>'e','è'=>'e','í'=>'i','ó'=>'o','ú'=>'u','ñ'=>'n','ü'=>'u','ö'=>'o','ş'=>'s','ı'=>'i']);
  return preg_replace('/[^a-z]/','',$s);
}
function wc_iso($name){
  static $map=[
    'algeria'=>'dz','argentina'=>'ar','australia'=>'au','austria'=>'at','belgium'=>'be',
    'bosniaherzegovina'=>'ba','bosnia'=>'ba','brazil'=>'br','canada'=>'ca','capeverde'=>'cv','caboverde'=>'cv',
    'colombia'=>'co','croatia'=>'hr','curacao'=>'cw','czechrepublic'=>'cz','czechia'=>'cz',
    'drcongo'=>'cd','congodr'=>'cd','ecuador'=>'ec','egypt'=>'eg','england'=>'gb-eng','france'=>'fr',
    'germany'=>'de','ghana'=>'gh','haiti'=>'ht','iran'=>'ir','iraq'=>'iq','ivorycoast'=>'ci','cotedivoire'=>'ci',
    'japan'=>'jp','jordan'=>'jo','mexico'=>'mx','morocco'=>'ma','netherlands'=>'nl','newzealand'=>'nz',
    'norway'=>'no','panama'=>'pa','paraguay'=>'py','portugal'=>'pt','qatar'=>'qa','saudiarabia'=>'sa',
    'scotland'=>'gb-sct','wales'=>'gb-wls','senegal'=>'sn','southafrica'=>'za','southkorea'=>'kr','korearepublic'=>'kr',
    'spain'=>'es','sweden'=>'se','switzerland'=>'ch','tunisia'=>'tn','turkey'=>'tr','turkiye'=>'tr',
    'usa'=>'us','unitedstates'=>'us','uruguay'=>'uy','uzbekistan'=>'uz',
    'nigeria'=>'ng','cameroon'=>'cm','italy'=>'it','denmark'=>'dk','poland'=>'pl','serbia'=>'rs','peru'=>'pe',
    'chile'=>'cl','venezuela'=>'ve','costarica'=>'cr','jamaica'=>'jm','ukraine'=>'ua','greece'=>'gr',
  ];
  $k=wc_flag_key($name);
  return isset($map[$k])?$map[$k]:'';
}
function wc_u($cp){
  $cp=intval($cp);
  if($cp<0x80)   return chr($cp);
  if($cp<0x800)  return chr(0xC0|($cp>>6)).chr(0x80|($cp&0x3F));
  if($cp<0x10000)return chr(0xE0|($cp>>12)).chr(0x80|(($cp>>6)&0x3F)).chr(0x80|($cp&0x3F));
  return chr(0xF0|($cp>>18)).chr(0x80|(($cp>>12)&0x3F)).chr(0x80|(($cp>>6)&0x3F)).chr(0x80|($cp&0x3F));
}
function wc_flag_emoji_iso($iso){
  if ($iso==='') return '';
  if ($iso==='gb-eng') return wc_u(0x1F3F4).wc_u(0xE0067).wc_u(0xE0062).wc_u(0xE0065).wc_u(0xE006E).wc_u(0xE0067).wc_u(0xE007F);
  if ($iso==='gb-sct') return wc_u(0x1F3F4).wc_u(0xE0067).wc_u(0xE0062).wc_u(0xE0073).wc_u(0xE0063).wc_u(0xE0074).wc_u(0xE007F);
  if ($iso==='gb-wls') return wc_u(0x1F3F4).wc_u(0xE0067).wc_u(0xE0062).wc_u(0xE0077).wc_u(0xE006C).wc_u(0xE0073).wc_u(0xE007F);
  if (strlen($iso)!==2) return '';
  $c=strtoupper($iso);
  return wc_u(0x1F1E6+(ord($c[0])-65)).wc_u(0x1F1E6+(ord($c[1])-65));
}
function wc_flag_emoji($name){ return wc_flag_emoji_iso(wc_iso($name)); }

// Fetch the 48-team master list (names + crests) for the team picker
function wc_fetch_teams(){
  $j = wc_api('/competitions/WC/teams');
  if ($j && !empty($j['teams'])) {
    try {
      $st = db()->prepare("INSERT INTO wc_teams(id,name,tla,crest) VALUES(?,?,?,?)
        ON DUPLICATE KEY UPDATE name=VALUES(name),tla=VALUES(tla),crest=VALUES(crest)");
      foreach ($j['teams'] as $t) {
        $st->execute([(int)$t['id'], isset($t['name'])?$t['name']:'', isset($t['tla'])?$t['tla']:'', isset($t['crest'])?$t['crest']:'']);
      }
    } catch(Exception $e){}
    return true;
  }
  return false;
}

// Read cache → [matches[], fetched_at|null]
function wc_cached(){
  try {
    $r = db()->query("SELECT payload, fetched_at FROM wc_fixtures_cache WHERE id=1")->fetch();
    if ($r && $r['payload']) {
      $j = json_decode($r['payload'], true);
      if (is_array($j) && isset($j['matches'])) return [$j['matches'], $r['fetched_at']];
    }
  } catch(Exception $e){}
  return [[], null];
}

// Master team list for the picker. Falls back to teams seen in the matches payload.
function wc_all_teams($matches){
  $out = [];
  try {
    foreach (db()->query("SELECT name,tla,crest FROM wc_teams WHERE name<>'' ORDER BY name ASC") as $t) {
      $out[$t['name']] = ['name'=>$t['name'],'tla'=>$t['tla'],'crest'=>$t['crest']];
    }
  } catch(Exception $e){}
  if (!$out) { // fallback: collect resolved teams from fixtures
    foreach ($matches as $m) {
      foreach (['homeTeam','awayTeam'] as $k) {
        $t = isset($m[$k]) ? $m[$k] : null;
        if ($t && !empty($t['name'])) {
          $out[$t['name']] = ['name'=>$t['name'],'tla'=>(isset($t['tla'])?$t['tla']:''),'crest'=>(isset($t['crest'])?$t['crest']:'')];
        }
      }
    }
    ksort($out);
  }
  return array_values($out);
}

// Load admin overrides → $ovr[match_id]['home'|'away'] = ['name','tla','crest']
function wc_overrides(){
  $ovr = [];
  try {
    foreach (db()->query("SELECT match_id,side,name,tla,crest FROM wc_overrides") as $r) {
      $ovr[(int)$r['match_id']][$r['side']] = ['name'=>$r['name'],'tla'=>$r['tla'],'crest'=>$r['crest']];
    }
  } catch(Exception $e){}
  return $ovr;
}

// ── AJAX ───────────────────────────────────────────────────────
$act = isset($_POST['action']) ? $_POST['action'] : (isset($_GET['action']) ? $_GET['action'] : '');

// Admin: choose data source (openfootball | football-data | worldcup26)
if ($act === 'savesource' && $isAdmin) {
  header('Content-Type: application/json');
  $s = isset($_POST['source']) ? $_POST['source'] : '';
  $allowed = ['openfootball','football-data','worldcup26'];
  if (!in_array($s,$allowed,true)) { echo json_encode(['ok'=>false,'msg'=>'Unknown source']); exit; }
  wc_setcfg('source', $s);
  if (isset($_POST['wc26_token'])) wc_setcfg('wc26_token', trim($_POST['wc26_token']));
  wc_setcfg('last_try','0');            // allow an immediate re-fetch
  $j = wc_fetch_store();
  echo json_encode(['ok'=>true,'msg'=> $j!==null ? '✅ Source set & fixtures loaded!' : '⚠️ Source saved, but fetch failed — try Refresh.']);
  exit;
}

// Admin: save API key
if ($act === 'savekey' && $isAdmin) {
  header('Content-Type: application/json');
  $k = trim(isset($_POST['key']) ? $_POST['key'] : '');
  wc_setcfg('api_key', $k);
  // try an immediate fetch to validate
  $ok = $k ? (wc_fetch_store() !== null) : false;
  echo json_encode(['ok'=>true, 'valid'=>$ok, 'msg'=>$ok ? '✅ Key saved & fixtures loaded!' : ($k?'⚠️ Key saved but fetch failed — check the key/plan.':'Key cleared.')]);
  exit;
}

// Admin: force refresh
if ($act === 'refresh' && $isAdmin) {
  header('Content-Type: application/json');
  wc_setcfg('last_try','0');
  $j = wc_fetch_store();
  echo json_encode(['ok'=> $j!==null, 'msg'=> $j!==null ? '✅ Fixtures refreshed!' : '⚠️ Could not fetch from '.wc_source().' — check source/network.']);
  exit;
}

// Admin: swap two Round-of-32 teams (custom bracket)
if ($act === 'swap_slots' && $isAdmin) {
  header('Content-Type: application/json');
  $an=(int)(isset($_POST['a_num'])?$_POST['a_num']:0); $as=(isset($_POST['a_side'])&&$_POST['a_side']==='a')?'a':'h';
  $bn=(int)(isset($_POST['b_num'])?$_POST['b_num']:0); $bs=(isset($_POST['b_side'])&&$_POST['b_side']==='a')?'a':'h';
  if($an<73||$an>88||$bn<73||$bn>88){ echo json_encode(['ok'=>false,'msg'=>'Only Round-of-32 teams can be swapped.']); exit; }
  if($an===$bn && $as===$bs){ echo json_encode(['ok'=>false,'msg'=>'Pick two different teams.']); exit; }
  list($ms,) = wc_cached();
  $real=[];
  foreach ($ms as $m){
    $sg=strtoupper(str_replace([' ','-'],'_', isset($m['stage'])?$m['stage']:''));
    if($sg!=='LAST_32') continue; $num=(int)(isset($m['id'])?$m['id']:0); if($num<73||$num>88) continue;
    $real[$num]=[isset($m['homeTeam']['name'])?$m['homeTeam']['name']:'', isset($m['awayTeam']['name'])?$m['awayTeam']['name']:''];
  }
  $sw=json_decode(wc_cfg('r32_swaps','{}'),true); if(!is_array($sw))$sw=[];
  $eff=$real; foreach($sw as $k=>$p){ if(is_array($p)) $eff[(int)$k]=[isset($p[0])?$p[0]:'', isset($p[1])?$p[1]:'']; }
  if(!isset($eff[$an])||!isset($eff[$bn])){ echo json_encode(['ok'=>false,'msg'=>'Slot not found — tap Refresh first.']); exit; }
  $ai=$as==='h'?0:1; $bi=$bs==='h'?0:1;
  $tmp=$eff[$an][$ai]; $eff[$an][$ai]=$eff[$bn][$bi]; $eff[$bn][$bi]=$tmp;
  $sw[$an]=$eff[$an]; $sw[$bn]=$eff[$bn];
  wc_setcfg('r32_swaps', json_encode($sw));
  echo json_encode(['ok'=>true,'msg'=>'Swapped']); exit;
}
// Admin: reset to the real draw
if ($act === 'reset_bracket' && $isAdmin) {
  header('Content-Type: application/json');
  wc_setcfg('r32_swaps','{}'); wc_setcfg('ko_wins','{}');
  echo json_encode(['ok'=>true,'msg'=>'Reset to the real draw.']); exit;
}

// Admin: assign a team to a knockout slot (fills a "To be decided" position)
if ($act === 'set_team' && $isAdmin) {
  header('Content-Type: application/json');
  $mid  = (int)(isset($_POST['match_id'])?$_POST['match_id']:0);
  $side = (isset($_POST['side']) && $_POST['side']==='away') ? 'away' : 'home';
  $name = trim(isset($_POST['name'])?$_POST['name']:'');
  if (!$mid || $name==='') { echo json_encode(['ok'=>false,'msg'=>'Pick a team.']); exit; }
  // look up tla + crest from the master list
  $tla=''; $crest='';
  try {
    $s = db()->prepare("SELECT tla,crest FROM wc_teams WHERE name=? LIMIT 1");
    $s->execute([$name]); if ($row=$s->fetch()) { $tla=$row['tla']; $crest=$row['crest']; }
  } catch(Exception $e){}
  if (!$tla) $tla = strtoupper(substr($name,0,3));
  try {
    db()->prepare("INSERT INTO wc_overrides(match_id,side,name,tla,crest) VALUES(?,?,?,?,?)
      ON DUPLICATE KEY UPDATE name=VALUES(name),tla=VALUES(tla),crest=VALUES(crest)")
       ->execute([$mid,$side,$name,$tla,$crest]);
  } catch(Exception $e){ echo json_encode(['ok'=>false,'msg'=>'Save failed.']); exit; }
  echo json_encode(['ok'=>true,'msg'=>'✅ '.$name.' set!','name'=>$name,'tla'=>$tla,'crest'=>$crest]);
  exit;
}

// Admin: clear a slot override (back to "To be decided")
if ($act === 'clear_team' && $isAdmin) {
  header('Content-Type: application/json');
  $mid  = (int)(isset($_POST['match_id'])?$_POST['match_id']:0);
  $side = (isset($_POST['side']) && $_POST['side']==='away') ? 'away' : 'home';
  try { db()->prepare("DELETE FROM wc_overrides WHERE match_id=? AND side=?")->execute([$mid,$side]); } catch(Exception $e){}
  echo json_encode(['ok'=>true,'msg'=>'Slot cleared']);
  exit;
}

// Admin: save many slots at once (bulk bracket edit)
if ($act === 'set_team_bulk' && $isAdmin) {
  header('Content-Type: application/json');
  $picks = json_decode(isset($_POST['picks'])?$_POST['picks']:'[]', true);
  if (!is_array($picks)) { echo json_encode(['ok'=>false,'msg'=>'Bad data']); exit; }
  $n = 0;
  try {
    $look = db()->prepare("SELECT tla,crest FROM wc_teams WHERE name=? LIMIT 1");
    $up   = db()->prepare("INSERT INTO wc_overrides(match_id,side,name,tla,crest) VALUES(?,?,?,?,?)
      ON DUPLICATE KEY UPDATE name=VALUES(name),tla=VALUES(tla),crest=VALUES(crest)");
    $del  = db()->prepare("DELETE FROM wc_overrides WHERE match_id=? AND side=?");
    foreach ($picks as $p) {
      $mid  = (int)(isset($p['match_id'])?$p['match_id']:0);
      $side = (isset($p['side']) && $p['side']==='away') ? 'away' : 'home';
      $name = trim(isset($p['name'])?$p['name']:'');
      if (!$mid) continue;
      if ($name==='') { $del->execute([$mid,$side]); $n++; continue; }
      $tla=''; $crest='';
      $look->execute([$name]); if ($row=$look->fetch()) { $tla=$row['tla']; $crest=$row['crest']; }
      if (!$tla) $tla = strtoupper(mb_substr($name,0,3));
      $up->execute([$mid,$side,$name,$tla,$crest]); $n++;
    }
  } catch(Exception $e){ echo json_encode(['ok'=>false,'msg'=>'Save failed']); exit; }
  echo json_encode(['ok'=>true,'msg'=>'✅ Saved '.$n.' slots']);
  exit;
}

// Admin: set the winner of a bracket node (advances the team). match_id = node (73-104), side='win'
if ($act === 'set_win' && $isAdmin) {
  header('Content-Type: application/json');
  $node = (int)(isset($_POST['node'])?$_POST['node']:0);
  $name = trim(isset($_POST['name'])?$_POST['name']:'');
  if ($node<73 || $node>104) { echo json_encode(['ok'=>false,'msg'=>'Bad node']); exit; }
  try {
    if ($name==='') db()->prepare("DELETE FROM wc_overrides WHERE match_id=? AND side='win'")->execute([$node]);
    else db()->prepare("INSERT INTO wc_overrides(match_id,side,name) VALUES(?,'win',?)
      ON DUPLICATE KEY UPDATE name=VALUES(name)")->execute([$node,$name]);
  } catch(Exception $e){ echo json_encode(['ok'=>false,'msg'=>'Save failed']); exit; }
  echo json_encode(['ok'=>true,'msg'=> $name?('✅ '.$name.' advances!'):'Cleared']);
  exit;
}

// Admin: bulk-save bracket winners
if ($act === 'set_win_bulk' && $isAdmin) {
  header('Content-Type: application/json');
  $picks = json_decode(isset($_POST['picks'])?$_POST['picks']:'[]', true);
  if (!is_array($picks)) { echo json_encode(['ok'=>false,'msg'=>'Bad data']); exit; }
  $n=0;
  try {
    $up = db()->prepare("INSERT INTO wc_overrides(match_id,side,name) VALUES(?,'win',?) ON DUPLICATE KEY UPDATE name=VALUES(name)");
    $del= db()->prepare("DELETE FROM wc_overrides WHERE match_id=? AND side='win'");
    foreach ($picks as $p) {
      $node=(int)(isset($p['node'])?$p['node']:0);
      $name=trim(isset($p['name'])?$p['name']:'');
      if ($node<73 || $node>104) continue;
      if ($name==='') $del->execute([$node]); else $up->execute([$node,$name]);
      $n++;
    }
  } catch(Exception $e){ echo json_encode(['ok'=>false,'msg'=>'Save failed']); exit; }
  echo json_encode(['ok'=>true,'msg'=>'✅ Saved '.$n.' matches']);
  exit;
}

// Live data (lightweight) — used by client polling to update scores
if ($act === 'data') {
  header('Content-Type: application/json');
  list($ms, $fa) = wc_cached();
  $out = [];
  foreach ($ms as $m) {
    $ft = isset($m['score']['fullTime']) ? $m['score']['fullTime'] : ['home'=>null,'away'=>null];
    $out[] = [
      'id'     => (int)$m['id'],
      'status' => $m['status'],
      'minute' => isset($m['minute']) ? $m['minute'] : null,
      'h'      => isset($ft['home']) ? $ft['home'] : null,
      'a'      => isset($ft['away']) ? $ft['away'] : null,
    ];
  }
  echo json_encode(['ok'=>true, 'fetched_at'=>$fa, 'matches'=>$out]);
  exit;
}

// ── Load matches for render (refresh if stale) ─────────────────
$CACHE_TTL = 900; // 15 min
list($matches, $fetchedAt) = wc_cached();
$hasKey = (wc_key() !== '');
$srcNow = wc_source();
$needsKey = ($srcNow==='football-data'); // openfootball is keyless; worldcup26 uses a token but still fetches
$canFetch = (!$needsKey || $hasKey);
$stale  = (!$fetchedAt) || (strtotime($fetchedAt) < time() - $CACHE_TTL);
$lastTry = (int)wc_cfg('last_try', '0');
if ($canFetch && $stale && (time() - $lastTry > 60)) {
  $j = wc_fetch_store();
  if ($j !== null) { $matches = $j['matches']; $fetchedAt = date('Y-m-d H:i:s'); }
}

// ── Helpers for display ────────────────────────────────────────
function wc_pretty_stage($s){
  $map = [
    'GROUP_STAGE'=>'Group Stage','LAST_32'=>'Round of 32','LAST_16'=>'Round of 16',
    'QUARTER_FINALS'=>'Quarter-final','SEMI_FINALS'=>'Semi-final',
    'THIRD_PLACE'=>'3rd Place','FINAL'=>'Final','PRELIMINARY'=>'Preliminary',
  ];
  return isset($map[$s]) ? $map[$s] : ucwords(strtolower(str_replace('_',' ', (string)$s)));
}
function wc_team_name($t){
  if (!$t || empty($t['name'])) return 'To be decided';
  return $t['name'];
}
function wc_team_tla($t){
  if ($t && !empty($t['tla'])) return $t['tla'];
  if ($t && !empty($t['name'])) return strtoupper(substr($t['name'],0,3));
  return 'TBD';
}
function wc_crest($t){
  return ($t && !empty($t['crest'])) ? $t['crest'] : '';
}

// ── Split & sort ───────────────────────────────────────────────
$live = []; $upcoming = []; $finished = [];
foreach ($matches as $m) {
  $st = isset($m['status']) ? $m['status'] : 'SCHEDULED';
  if ($st==='IN_PLAY' || $st==='PAUSED') $live[] = $m;
  elseif ($st==='FINISHED' || $st==='AWARDED') $finished[] = $m;
  elseif ($st==='SCHEDULED' || $st==='TIMED') $upcoming[] = $m;
  // POSTPONED / SUSPENDED / CANCELLED are skipped from the main lists
}
usort($upcoming, function($a,$b){ return strcmp($a['utcDate'],$b['utcDate']); });   // soonest first
usort($live,     function($a,$b){ return strcmp($a['utcDate'],$b['utcDate']); });
usort($finished, function($a,$b){ return strcmp($b['utcDate'],$a['utcDate']); });   // newest first

// ── Knockout helpers: overrides, elimination, alive-team picker list ──
$KO_STAGES = ['LAST_32','LAST_16','QUARTER_FINALS','SEMI_FINALS','THIRD_PLACE','FINAL'];
$ovr = wc_overrides();

// Eliminated = the loser of any FINISHED knockout match (uses score.winner)
$eliminated = []; // lowercased name => true
foreach ($matches as $m) {
  $st = isset($m['status']) ? $m['status'] : '';
  if (($st!=='FINISHED' && $st!=='AWARDED') || !in_array((isset($m['stage'])?$m['stage']:''), $KO_STAGES, true)) continue;
  $w = isset($m['score']['winner']) ? $m['score']['winner'] : null; // HOME_TEAM | AWAY_TEAM | DRAW
  $hn = (isset($m['homeTeam']['name'])) ? $m['homeTeam']['name'] : null;
  $an = (isset($m['awayTeam']['name'])) ? $m['awayTeam']['name'] : null;
  if ($w==='HOME_TEAM' && $an) $eliminated[mb_strtolower($an)] = true;
  elseif ($w==='AWAY_TEAM' && $hn) $eliminated[mb_strtolower($hn)] = true;
}

// Alive teams for the picker dropdown (knocked-out teams auto-removed)
$allTeams = wc_all_teams($matches);
$aliveTeams = [];
foreach ($allTeams as $t) {
  if (!isset($eliminated[mb_strtolower($t['name'])])) $aliveTeams[] = $t;
}

// ══ Knockout structure is derived from REAL API matches below — no team is ever hardcoded. ══
// (These structural maps are kept only as an inert fallback; the live bracket ignores them.)
$WC_R32 = [];
$WC_FEED = [89=>[74,77],90=>[73,75],91=>[76,78],92=>[79,80],93=>[83,84],94=>[81,82],95=>[86,88],96=>[85,87],
 97=>[89,90],98=>[93,94],99=>[91,92],100=>[95,96],101=>[97,98],102=>[99,100],104=>[101,102],103=>[101,102]];
$WC_COLS = [
  'Round of 32'   => [74,77,73,75,83,84,81,82, 76,78,79,80,86,88,85,87],
  'Round of 16'   => [89,90,93,94, 91,92,95,96],
  'Quarter-finals'=> [97,98, 99,100],
  'Semi-finals'   => [101,102],
  'Final'         => [104],
];

// Normalise team names so football-data spellings match the hardcoded bracket
function wc_norm($s){
  $s=strtolower(trim((string)$s)); $s=preg_replace('/[^a-z]/','',$s);
  $al=['caboverde'=>'capeverde','capeverdeislands'=>'capeverde','congodr'=>'drcongo','drcongo'=>'drcongo',
       'democraticrepublicofcongo'=>'drcongo','unitedstates'=>'usa','usa'=>'usa','unitedstatesofamerica'=>'usa',
       'bosniaandherzegovina'=>'bosnia','bosniaherzegovina'=>'bosnia','cotedivoire'=>'ivorycoast','ivorycoast'=>'ivorycoast',
       'korearepublic'=>'southkorea','southkorea'=>'southkorea'];
  return isset($al[$s])?$al[$s]:$s;
}
function wc_key2($a,$b){ $x=[wc_norm($a),wc_norm($b)]; sort($x); return $x[0].'|'.$x[1]; }

// Index football-data knockout matches by normalised team-set → result + match
$WC_RES=[]; $WC_RESM=[];
foreach ($matches as $m) {
  $sg = isset($m['stage'])?$m['stage']:'';
  if (!in_array($sg,$KO_STAGES,true)) continue;
  $hn = isset($m['homeTeam']['name'])?$m['homeTeam']['name']:null;
  $an = isset($m['awayTeam']['name'])?$m['awayTeam']['name']:null;
  if (!$hn || !$an) continue;
  $k = wc_key2($hn,$an);
  $WC_RESM[$k] = $m;
  $wn = isset($m['score']['winner'])?$m['score']['winner']:null;
  if ($wn==='HOME_TEAM') $WC_RES[$k]=$hn;
  elseif ($wn==='AWAY_TEAM') $WC_RES[$k]=$an;
}

// Admin winner-overrides keyed by node number (match_id 73..104, side 'win')
$nodeOvr = [];
try {
  foreach (db()->query("SELECT match_id,name FROM wc_overrides WHERE side='win' AND match_id BETWEEN 73 AND 104") as $r) {
    $nodeOvr[(int)$r['match_id']] = $r['name'];
  }
} catch(Exception $e){}

// Engine: participants, winner, subtree — driven by the tree, not by API ordering
function wc_win($n,$R32,$FEED,$RES,$ovr,&$memo){
  if (array_key_exists($n,$memo)) return $memo[$n];
  if (isset($ovr[$n])) return $memo[$n]=$ovr[$n];
  $tt = wc_teams($n,$R32,$FEED,$RES,$ovr,$memo);
  $w = null;
  if ($tt[0] && $tt[1]) { $k=wc_key2($tt[0],$tt[1]); if (isset($RES[$k])) $w=$RES[$k]; }
  return $memo[$n]=$w;
}
function wc_teams($n,$R32,$FEED,$RES,$ovr,&$memo){
  if (isset($R32[$n])) return $R32[$n];
  if (!isset($FEED[$n])) return [null,null];
  $f = $FEED[$n];
  return [wc_win($f[0],$R32,$FEED,$RES,$ovr,$memo), wc_win($f[1],$R32,$FEED,$RES,$ovr,$memo)];
}
function wc_sub($n,$R32,$FEED){
  if (isset($R32[$n])) return $R32[$n];
  if (!isset($FEED[$n])) return [];
  $f=$FEED[$n];
  return array_merge(wc_sub($f[0],$R32,$FEED), wc_sub($f[1],$R32,$FEED));
}

// Apply an override to a team slot (used only by the Upcoming/Live/Results card renderer)
function wc_resolve($m, $side, $ovr){
  $key = $side==='home' ? 'homeTeam' : 'awayTeam';
  $t = isset($m[$key]) ? $m[$key] : null;
  $mid = (int)$m['id'];
  if ((!$t || empty($t['name'])) && isset($ovr[$mid][$side])) {
    $o = $ovr[$mid][$side];
    return ['name'=>$o['name'],'tla'=>$o['tla'],'crest'=>$o['crest'],'_override'=>true];
  }
  return $t;
}

// crest lookup by normalised name (from the cached team list)
$WC_CREST = []; $WC_TLA = [];
foreach ($allTeams as $t) {
  if (!empty($t['name'])) {
    $WC_CREST[wc_norm($t['name'])] = isset($t['crest'])?$t['crest']:'';
    $WC_TLA[wc_norm($t['name'])]   = isset($t['tla'])?$t['tla']:'';
  }
}
function wc_crest_for($name,$WC_CREST){ $k=wc_norm($name); return isset($WC_CREST[$k])?$WC_CREST[$k]:''; }
function wc_tla_for($name){
  global $WC_TLA; $k=wc_norm($name);
  if (isset($WC_TLA[$k]) && $WC_TLA[$k]!=='') return $WC_TLA[$k];
  // fallback: first 3 letters, upper
  $clean=preg_replace('/[^A-Za-z]/','',(string)$name);
  return strtoupper(mb_substr($clean,0,3));
}

// Per-node winner candidates for the picker (its two participants if known, else its still-alive subtree)
$nodeCand = []; $memoC = [];
foreach (array_keys($WC_FEED) as $n) {
  $tt = wc_teams($n,$WC_R32,$WC_FEED,$WC_RES,$nodeOvr,$memoC);
  if ($tt[0] && $tt[1]) { $cand=[$tt[0],$tt[1]]; }
  else { $cand = wc_sub($n,$WC_R32,$WC_FEED); }
  $clean=[]; foreach ($cand as $c){ if (!isset($eliminated[mb_strtolower($c)])) $clean[]=$c; }
  $nodeCand[$n] = array_values(array_unique($clean));
}
// R32 nodes: winner candidates are the two actual teams
foreach ($WC_R32 as $n=>$pair) {
  $clean=[]; foreach ($pair as $c){ if (!isset($eliminated[mb_strtolower($c)])) $clean[]=$c; }
  $nodeCand[$n] = $clean;
}

// Build the full render/share tree
$memoT = [];
function wc_node_view($n,$R32,$FEED,$RES,$RESM,$ovr,$WC_CREST,&$memoT){
  $tt = wc_teams($n,$R32,$FEED,$RES,$ovr,$memoT);
  // slot labels: resolved team, else (for R16) the R32 pair "A / B", else TBD
  $slot = function($idx) use ($n,$tt,$R32,$FEED,$RES,$ovr,&$memoT){
    if ($tt[$idx]) return $tt[$idx];
    if (!isset($R32[$n]) && isset($FEED[$n])) {
      $f = $FEED[$n][$idx];
      if (isset($R32[$f])) return $R32[$f][0].' / '.$R32[$f][1]; // R16 cell shows the R32 pairing
    }
    return 'TBD';
  };
  $h = isset($R32[$n]) ? $R32[$n][0] : $slot(0);
  $a = isset($R32[$n]) ? $R32[$n][1] : $slot(1);
  // score/status from football-data if this exact pairing exists
  $sh=$sa=null; $win=null; $stt='';
  if ($tt[0] && $tt[1]) {
    $k = wc_key2($tt[0],$tt[1]);
    if (isset($RESM[$k])) {
      $mm=$RESM[$k];
      $ft=isset($mm['score']['fullTime'])?$mm['score']['fullTime']:['home'=>null,'away'=>null];
      $stt=isset($mm['status'])?$mm['status']:'';
      // orient score to (tt[0],tt[1])
      $hn=isset($mm['homeTeam']['name'])?$mm['homeTeam']['name']:'';
      if (wc_norm($hn)===wc_norm($tt[0])) { $sh=isset($ft['home'])?$ft['home']:null; $sa=isset($ft['away'])?$ft['away']:null; }
      else { $sh=isset($ft['away'])?$ft['away']:null; $sa=isset($ft['home'])?$ft['home']:null; }
    }
  }
  $wTeam = wc_win($n,$R32,$FEED,$RES,$ovr,$memoT);
  if ($wTeam && $tt[0] && wc_norm($wTeam)===wc_norm($tt[0])) $win='h';
  elseif ($wTeam && $tt[1] && wc_norm($wTeam)===wc_norm($tt[1])) $win='a';
  return ['n'=>$n,'h'=>$h,'a'=>$a,'sh'=>$sh,'sa'=>$sa,'win'=>$win,'status'=>$stt,
          'hc'=>wc_crest_for($tt[0]?:$h,$WC_CREST),'ac'=>wc_crest_for($tt[1]?:$a,$WC_CREST),
          'ht'=>($tt[0]?wc_tla_for($tt[0]):''),'at'=>($tt[1]?wc_tla_for($tt[1]):''),
          'resolved'=>($tt[0]&&$tt[1])];
}

// Champion
$champion = wc_win(104,$WC_R32,$WC_FEED,$WC_RES,$nodeOvr,$memoT);

// Render one bracket cell (two participant rows; tappable for admins to pick the winner)
function wc_tree_cell($v,$isAdmin){
  $click = $isAdmin ? ' onclick="fxOpenNode('.((int)$v['n']).')" style="cursor:pointer"' : '';
  ob_start();
  echo '<div class="fx-cell" data-node="'.((int)$v['n']).'"'.$click.'>';
  foreach (['h','a'] as $sd) {
    $name  = $sd==='h' ? $v['h'] : $v['a'];
    $sc    = $sd==='h' ? $v['sh'] : $v['sa'];
    $crest = $sd==='h' ? $v['hc'] : $v['ac'];
    $isWin = ($v['win']===$sd);
    $isPair= (strpos($name,' / ')!==false);
    $cls   = 'fx-brow'.($isWin?' win':'').(($name==='TBD'||$isPair)?' tbd':'');
    echo '<div class="'.$cls.'">';
    if ($crest && !$isPair && $name!=='TBD') echo '<img class="fx-brc" src="'.h($crest).'" alt="" onerror="this.style.display=\'none\'">';
    echo '<span class="fx-brn">'.h($name).'</span>';
    echo '<span class="fx-brs">'.($sc===null?'':(int)$sc).'</span>';
    echo '</div>';
  }
  echo '</div>';
  return ob_get_clean();
}

// Share tree (rounds → matches) for the image
$shareTree = [];
foreach ($WC_COLS as $rname=>$nodes) {
  $ms=[];
  foreach ($nodes as $n) { $v=wc_node_view($n,$WC_R32,$WC_FEED,$WC_RES,$WC_RESM,$nodeOvr,$WC_CREST,$memoT); $ms[]=['h'=>$v['h'],'a'=>$v['a'],'sh'=>$v['sh'],'sa'=>$v['sa'],'w'=>$v['win']]; }
  $shareTree[] = ['round'=>$rname,'matches'=>$ms];
}

// ══ Mirrored two-pathway layout (matches the official FIFA bracket art) ══
// Pathway 1 = left half (feeds Semi-final 101); Pathway 2 = right half (feeds Semi-final 102).
$WC_P1 = ['Round of 32'=>[74,77,73,75,83,84,81,82], 'Round of 16'=>[89,90,93,94], 'Quarter-finals'=>[97,98], 'Semi-final'=>[101]];
// P2 ordered from the centre outward so the right side mirrors the left.
$WC_P2 = ['Semi-final'=>[102], 'Quarter-finals'=>[99,100], 'Round of 16'=>[91,92,95,96], 'Round of 32'=>[76,78,79,80,86,88,85,87]];

// Full node→view map for the shareable mirrored image (nodes 73..104)
$FX_NODES = [];
for ($n=73; $n<=104; $n++) {
  $v = wc_node_view($n,$WC_R32,$WC_FEED,$WC_RES,$WC_RESM,$nodeOvr,$WC_CREST,$memoT);
  $FX_NODES[$n] = ['h'=>$v['h'],'a'=>$v['a'],'ht'=>$v['ht'],'at'=>$v['at'],
                   'sh'=>$v['sh'],'sa'=>$v['sa'],'w'=>$v['win'],'res'=>$v['resolved']];
}

// Is there a knockout bracket yet? (drives the default landing tab)
$haveKO = false;
foreach ($matches as $m) { if (in_array(isset($m['stage'])?$m['stage']:'', $KO_STAGES, true)) { $haveKO = true; break; } }
$defaultTab = $haveKO ? 'bracket' : 'upcoming';

// ══════════════════════════════════════════════════════════════════════════
//  LIVE KNOCKOUT BRACKET — built entirely from the REAL API matches.
//  No team is ever hardcoded. Undetermined slots stay "TBD" until the feed
//  fills them in (or an admin sets them). Pairings and who-advances come
//  straight from the live data, so France/Sweden etc. can never be misplaced.
// ══════════════════════════════════════════════════════════════════════════
$KO_ROUND_MAP = [
  'LAST_32'=>'Round of 32','ROUND_OF_32'=>'Round of 32','R32'=>'Round of 32',
  'LAST_16'=>'Round of 16','ROUND_OF_16'=>'Round of 16','R16'=>'Round of 16',
  'QUARTER_FINALS'=>'Quarter-finals','QUARTER_FINAL'=>'Quarter-finals','QUARTERFINALS'=>'Quarter-finals',
  'SEMI_FINALS'=>'Semi-finals','SEMI_FINAL'=>'Semi-finals','SEMIFINALS'=>'Semi-finals',
  'THIRD_PLACE'=>'Third place','3RD_PLACE'=>'Third place','THIRD_PLACE_FINAL'=>'Third place',
  'FINAL'=>'Final',
];
$KO_ROUND_ORDER = ['Round of 32','Round of 16','Quarter-finals','Semi-finals','Final'];

$koByRound = [];
foreach ($matches as $m) {
  $sg = strtoupper(str_replace([' ','-'],'_', isset($m['stage'])?$m['stage']:''));
  if (!isset($KO_ROUND_MAP[$sg])) continue;
  $koByRound[$KO_ROUND_MAP[$sg]][] = $m;
}
foreach ($koByRound as $rn=>&$arr) {
  usort($arr, function($a,$b){
    // FIFA match number (id) gives the true bracket order; date only as a tiebreak
    $d=((int)(isset($a['id'])?$a['id']:0)) - ((int)(isset($b['id'])?$b['id']:0));
    if ($d!==0) return $d;
    return strcmp(isset($a['utcDate'])?$a['utcDate']:'', isset($b['utcDate'])?$b['utcDate']:'');
  });
}
unset($arr);
$haveKObracket = false; foreach ($KO_ROUND_ORDER as $rn){ if(!empty($koByRound[$rn])){ $haveKObracket=true; break; } }

// one side of a knockout match → real team, admin override, or a TBD placeholder label
function wc_bside($m,$side,$ovr){
  $key = $side==='home'?'homeTeam':'awayTeam';
  $mid = (int)(isset($m['id'])?$m['id']:0);
  $t = isset($m[$key])?$m[$key]:null;
  if ($t && !empty($t['name'])) {
    return ['name'=>$t['name'],'crest'=>isset($t['crest'])?$t['crest']:'','tla'=>isset($t['tla'])?$t['tla']:'','tbd'=>false,'ov'=>false];
  }
  if (isset($ovr[$mid][$side])) {
    $o=$ovr[$mid][$side];
    return ['name'=>$o['name'],'crest'=>isset($o['crest'])?$o['crest']:'','tla'=>isset($o['tla'])?$o['tla']:'','tbd'=>false,'ov'=>true];
  }
  $lbl='';
  foreach ([$side.'TeamLabel',$key.'Label',$side.'_team_label'] as $lk){ if(!empty($m[$lk])){ $lbl=$m[$lk]; break; } }
  return ['name'=>$lbl?:'TBD','crest'=>'','tla'=>'','tbd'=>true,'ov'=>false];
}
function wc_mv($m,$ovr){
  $mid=(int)(isset($m['id'])?$m['id']:0);
  $home=wc_bside($m,'home',$ovr); $away=wc_bside($m,'away',$ovr);
  $ft=isset($m['score']['fullTime'])?$m['score']['fullTime']:['home'=>null,'away'=>null];
  $sh=isset($ft['home'])?$ft['home']:null; $sa=isset($ft['away'])?$ft['away']:null;
  $wn=isset($m['score']['winner'])?$m['score']['winner']:null;
  $win=$wn==='HOME_TEAM'?'h':($wn==='AWAY_TEAM'?'a':null);
  return ['mid'=>$mid,'h'=>$home,'a'=>$away,'sh'=>$sh,'sa'=>$sa,'win'=>$win,
          'status'=>isset($m['status'])?$m['status']:'','date'=>isset($m['utcDate'])?$m['utcDate']:''];
}
$koViews = [];
foreach ($KO_ROUND_ORDER as $rn){ if(empty($koByRound[$rn])) continue; foreach($koByRound[$rn] as $m){ $koViews[$rn][]=wc_mv($m,$ovr); } }

// champion = winner of the real Final (null until it's actually played)
$champion=null; $championCrest='';
if (!empty($koByRound['Final'])) {
  $fv=wc_mv($koByRound['Final'][0],$ovr);
  if ($fv['win']==='h'){ $champion=$fv['h']['name']; $championCrest=$fv['h']['crest']; }
  elseif ($fv['win']==='a'){ $champion=$fv['a']['name']; $championCrest=$fv['a']['crest']; }
}
$thirdView = !empty($koByRound['Third place']) ? wc_mv($koByRound['Third place'][0],$ovr) : null;

// candidate names for the admin picker (still-alive teams only)
$fxCandNames=[]; foreach ($aliveTeams as $t){ if(!empty($t['name'])) $fxCandNames[]=$t['name']; }

// FX rounds for the shareable image (real data only)
$FX_ROUNDS=[];
foreach ($KO_ROUND_ORDER as $rn){
  if (empty($koViews[$rn])) continue;
  $ms=[];
  foreach ($koViews[$rn] as $v){
    $ms[]=['h'=>$v['h']['tbd']?'TBD':$v['h']['name'],'a'=>$v['a']['tbd']?'TBD':$v['a']['name'],
           'ht'=>$v['h']['tla'],'at'=>$v['a']['tla'],'sh'=>$v['sh'],'sa'=>$v['sa'],'w'=>$v['win'],
           'hf'=>$v['h']['tbd']?'':wc_flag_emoji($v['h']['name']),'af'=>$v['a']['tbd']?'':wc_flag_emoji($v['a']['name'])];
  }
  $FX_ROUNDS[]=['round'=>$rn,'matches'=>$ms];
}

// render one REAL bracket cell; admins tap a TBD/override side to assign a team
function wc_live_cell($v,$isAdmin){
  ob_start();
  echo '<div class="fx-cell" data-mid="'.$v['mid'].'">';
  foreach (['h','a'] as $sd){
    $t=$v[$sd]; $sc=($sd==='h')?$v['sh']:$v['sa']; $isWin=($v['win']===$sd);
    $tap=$isAdmin && ($t['tbd'] || $t['ov']);
    $cls='fx-brow'.($isWin?' win':'').($t['tbd']?' tbd':'');
    $click=$tap?' onclick="fxOpenPicker('.$v['mid'].',\''.($sd==='h'?'home':'away').'\')" style="cursor:pointer" data-editable="1"':'';
    echo '<div class="'.$cls.'" data-mid="'.$v['mid'].'" data-side="'.($sd==='h'?'home':'away').'" data-team="'.h($t['tbd']?'':$t['name']).'"'.$click.'>';
    if (!$t['tbd'] && !empty($t['crest'])) echo '<img class="fx-brc" src="'.h($t['crest']).'" alt="" onerror="this.style.display=\'none\'">';
    echo '<span class="fx-brn">'.h($t['name']).($t['ov']?' ✏️':'').'</span>';
    echo '<span class="fx-brs">'.($sc===null?'':(int)$sc).'</span>';
    echo '</div>';
  }
  echo '</div>';
  return ob_get_clean();
}
// split a round's matches into the two pathways (top half / bottom half)
function wc_split($views,$rn){
  if (empty($views[$rn])) return [[],[]];
  $a=$views[$rn]; $n=count($a); $half=(int)ceil($n/2);
  return [array_slice($a,0,$half), array_slice($a,$half)];
}

// ── Official FIFA 2026 bracket structure (fixed & public) — teams filled from LIVE data. ──
// This is the true tree: it decides which side each match sits on, so two teams in the SAME
// half meet before the final. Column arrays are top-to-bottom so feeder pairs line up.
$FIFA_P1 = ['Round of 32'=>[74,77,73,75,83,84,81,82],'Round of 16'=>[89,90,93,94],'Quarter-finals'=>[97,98],'Semi-final'=>[101]];
$FIFA_P2 = ['Semi-final'=>[102],'Quarter-finals'=>[99,100],'Round of 16'=>[91,92,95,96],'Round of 32'=>[76,78,79,80,86,88,85,87]];
$FIFA_FINAL=104; $FIFA_THIRD=103;

// index live views by match id (= FIFA match number when the feed provides it, e.g. openfootball)
$koByMid = [];
foreach ($koViews as $rn=>$vs){ foreach($vs as $v){ $koByMid[(int)$v['mid']]=$v; } }
$useFifa = false;
foreach ([73,74,75,76,89,101,104] as $probe){ if(isset($koByMid[$probe])){ $useFifa=true; break; } }

// ══ CUSTOM BRACKET (admin swap/move) ══════════════════════════════════════
// Teams still come from real data — the admin only changes WHICH slot a team
// sits in. When any swap exists we recompute the whole tree from the rearranged
// Round of 32 (winners propagate using real results; unresolved slots show TBD).
$WC_FEED_ALL = [89=>[74,77],90=>[73,75],91=>[76,78],92=>[79,80],93=>[83,84],94=>[81,82],95=>[86,88],96=>[85,87],
 97=>[89,90],98=>[93,94],99=>[91,92],100=>[95,96],101=>[97,98],102=>[99,100],104=>[101,102]];
function wc_pair_results($matches){
  $r=[];
  foreach ($matches as $m){
    $hn=isset($m['homeTeam']['name'])?$m['homeTeam']['name']:null;
    $an=isset($m['awayTeam']['name'])?$m['awayTeam']['name']:null;
    if(!$hn||!$an) continue;
    $wn=isset($m['score']['winner'])?$m['score']['winner']:null;
    $sh=isset($m['score']['fullTime']['home'])?$m['score']['fullTime']['home']:null;
    $sa=isset($m['score']['fullTime']['away'])?$m['score']['fullTime']['away']:null;
    $win=$wn==='HOME_TEAM'?$hn:($wn==='AWAY_TEAM'?$an:'');
    $r[wc_key2($hn,$an)]=['win'=>$win,'sh'=>$sh,'sa'=>$sa,'hi'=>$hn];
  }
  return $r;
}
function wc_c_winAt($num,$eff,$FEED,$pr,$kw,&$mw){
  if (array_key_exists($num,$mw)) return $mw[$num];
  if (isset($kw[$num]) && $kw[$num]!=='') return $mw[$num]=$kw[$num];
  $mw[$num]=''; // cycle guard
  $h=wc_c_teamAt($num,'h',$eff,$FEED,$pr,$kw,$mw);
  $a=wc_c_teamAt($num,'a',$eff,$FEED,$pr,$kw,$mw);
  if ($h===''||$a==='') return $mw[$num]='';
  $k=wc_key2($h,$a);
  return $mw[$num]=(isset($pr[$k])?$pr[$k]['win']:'');
}
function wc_c_teamAt($num,$side,$eff,$FEED,$pr,$kw,&$mw){
  if (isset($eff[$num])) return $side==='h'?$eff[$num][0]:$eff[$num][1];
  if (!isset($FEED[$num])) return '';
  $f=$FEED[$num]; $feeder=$side==='h'?$f[0]:$f[1];
  return wc_c_winAt($feeder,$eff,$FEED,$pr,$kw,$mw);
}
function wc_c_side($name){
  if($name===''||$name===null) return ['name'=>'TBD','crest'=>'','tla'=>'','tbd'=>true,'ov'=>false];
  $s=wc_of_side($name); $t=$s['team'];
  return ['name'=>$t['name'],'crest'=>isset($t['crest'])?$t['crest']:'','tla'=>isset($t['tla'])?$t['tla']:'','tbd'=>false,'ov'=>false];
}
function wc_c_view($num,$eff,$FEED,$pr,$kw,&$mw){
  $h=wc_c_teamAt($num,'h',$eff,$FEED,$pr,$kw,$mw);
  $a=wc_c_teamAt($num,'a',$eff,$FEED,$pr,$kw,$mw);
  $k=($h!==''&&$a!=='')?wc_key2($h,$a):''; $res=($k&&isset($pr[$k]))?$pr[$k]:null;
  $sh=$sa=null;
  if($res){ if($res['hi']===$h){$sh=$res['sh'];$sa=$res['sa'];} else {$sh=$res['sa'];$sa=$res['sh'];} }
  $wn=wc_c_winAt($num,$eff,$FEED,$pr,$kw,$mw);
  $win=$wn!==''?($wn===$h?'h':($wn===$a?'a':null)):null;
  return ['mid'=>$num,'h'=>wc_c_side($h),'a'=>wc_c_side($a),'sh'=>$sh,'sa'=>$sa,'win'=>$win,'status'=>'','date'=>''];
}
function wc_real_r32($koByMid){
  $r=[];
  for($n=73;$n<=88;$n++){ if(isset($koByMid[$n])){ $v=$koByMid[$n];
    $r[$n]=[$v['h']['tbd']?'':$v['h']['name'], $v['a']['tbd']?'':$v['a']['name']]; } }
  return $r;
}
$r32Swaps = json_decode(wc_cfg('r32_swaps','{}'), true); if(!is_array($r32Swaps)) $r32Swaps=[];
$koWins   = json_decode(wc_cfg('ko_wins','{}'),   true); if(!is_array($koWins))   $koWins=[];
$bracketCustom = ($useFifa && (!empty($r32Swaps) || !empty($koWins)));
if ($bracketCustom) {
  $pairRes = wc_pair_results($matches);
  $effR32  = wc_real_r32($koByMid);
  foreach ($r32Swaps as $nn=>$pair){ if(is_array($pair)) $effR32[(int)$nn]=[isset($pair[0])?$pair[0]:'', isset($pair[1])?$pair[1]:'']; }
  $mw=[]; $custom=[];
  foreach (range(73,104) as $n){ if($n===103) continue; $custom[$n]=wc_c_view($n,$effR32,$WC_FEED_ALL,$pairRes,$koWins,$mw); }
  // safety: only switch to the custom bracket if it actually has real R32 teams
  $anyReal=false; for($n=73;$n<=88;$n++){ if(isset($custom[$n]) && empty($custom[$n]['h']['tbd'])){ $anyReal=true; break; } }
  if ($anyReal) {
    $koByMid = $custom;
    $fv=$custom[104];
    if     ($fv['win']==='h'){ $champion=$fv['h']['name']; $championCrest=$fv['h']['crest']; }
    elseif ($fv['win']==='a'){ $champion=$fv['a']['name']; $championCrest=$fv['a']['crest']; }
    else   { $champion=null; $championCrest=''; }
  } else {
    $bracketCustom=false; // computed bracket was empty — keep the real draw
  }
}

// view for a given FIFA match number: the live match if present, else an override-aware TBD slot
function wc_view_for($num,$koByMid,$ovr){
  if (isset($koByMid[$num])) return $koByMid[$num];
  return wc_mv(['id'=>$num], $ovr);
}
function wc_share_cell($v){
  return ['h'=>$v['h']['tbd']?'TBD':$v['h']['name'],'a'=>$v['a']['tbd']?'TBD':$v['a']['name'],
          'ht'=>$v['h']['tla'],'at'=>$v['a']['tla'],'sh'=>$v['sh'],'sa'=>$v['sa'],'w'=>$v['win'],
          'hf'=>$v['h']['tbd']?'':wc_flag_emoji($v['h']['name']),'af'=>$v['a']['tbd']?'':wc_flag_emoji($v['a']['name'])];
}

// Structured pathway data for the shareable image (correct FIFA sides, live teams)
$FX_P1=[]; $FX_P2=[]; $FX_FINAL=null;
if ($useFifa) {
  foreach($FIFA_P1 as $rn=>$nums){ $FX_P1[$rn]=[]; foreach($nums as $nn){ $FX_P1[$rn][]=wc_share_cell(wc_view_for($nn,$koByMid,$ovr)); } }
  foreach($FIFA_P2 as $rn=>$nums){ $FX_P2[$rn]=[]; foreach($nums as $nn){ $FX_P2[$rn][]=wc_share_cell(wc_view_for($nn,$koByMid,$ovr)); } }
  $FX_FINAL = wc_share_cell(wc_view_for($FIFA_FINAL,$koByMid,$ovr));
}

// ── Per-slot dropdown candidates ───────────────────────────────────────────
// A knockout slot can only be filled by a team coming through its FEEDER match
// (QF slot ← its R16 feeder, SF ← QF, Final ← SF). Finished feeder → only the
// winner is offered; unplayed feeder → its possible participants. Works on
// $koByMid, so it also follows the admin's custom (swapped) bracket.
function wc_cand_side($num,$i,$byMid,$FEED,$depth=0){
  // who can occupy side $i (0=home, 1=away) of match $num?
  if ($depth>8) return [];
  $v = isset($byMid[$num]) ? $byMid[$num] : null;
  if ($v){ $t = ($i===0) ? $v['h'] : $v['a']; if (empty($t['tbd']) && $t['name']!=='') return [$t['name']]; }
  if (!isset($FEED[$num])) return [];
  return wc_cand_win($FEED[$num][$i], $byMid, $FEED, $depth+1);
}
function wc_cand_win($num,$byMid,$FEED,$depth=0){
  // who can WIN match $num?
  if ($depth>8) return [];
  $v = isset($byMid[$num]) ? $byMid[$num] : null;
  if ($v && !empty($v['win'])){
    $w = ($v['win']==='h') ? $v['h'] : $v['a'];
    if (empty($w['tbd'])) return [$w['name']];      // decided → only the winner advances
  }
  $out = array_merge(wc_cand_side($num,0,$byMid,$FEED,$depth+1),
                     wc_cand_side($num,1,$byMid,$FEED,$depth+1));
  return array_values(array_unique($out));
}
function wc_cand_lose($num,$byMid,$FEED){
  // who can LOSE match $num? (feeds the third-place playoff)
  $v = isset($byMid[$num]) ? $byMid[$num] : null;
  if ($v && !empty($v['win'])){
    $l = ($v['win']==='h') ? $v['a'] : $v['h'];
    if (empty($l['tbd'])) return [$l['name']];
  }
  return wc_cand_win($num,$byMid,$FEED);            // undecided: either participant could lose
}
$fxSlotCand = [];
if ($useFifa) {
  $FEED_PICK = $WC_FEED_ALL;
  $FEED_PICK[103] = [101,102];                       // 3rd place ← SF losers
  foreach ($FEED_PICK as $num=>$fd){
    foreach (['home'=>0,'away'=>1] as $side=>$i){
      $cand = ($num===103) ? wc_cand_lose($fd[$i],$koByMid,$WC_FEED_ALL)
                           : wc_cand_win($fd[$i],$koByMid,$WC_FEED_ALL);
      if ($cand) $fxSlotCand[$num.':'.$side] = $cand;
    }
  }
}

// Reverse feed: which next-round slot does match index $i of $stage feed into?
$NEXT = ['LAST_32'=>'LAST_16','LAST_16'=>'QUARTER_FINALS','QUARTER_FINALS'=>'SEMI_FINALS','SEMI_FINALS'=>'FINAL'];
function wc_next_slot($stage,$idx,$FEED,$NEXT){
  if (!isset($NEXT[$stage])) return null;
  $ns = $NEXT[$stage];
  if (!isset($FEED[$ns])) return null;
  foreach ($FEED[$ns] as $ni=>$pair) {
    if ($pair[0]===$idx) return [$ns,$ni,'home'];
    if ($pair[1]===$idx) return [$ns,$ni,'away'];
  }
  return null;
}
// store one override row (looks up tla/crest from master list)
function wc_save_override($mid,$side,$name){
  if (!$name) return;
  $tla=''; $crest='';
  try { $s=db()->prepare("SELECT tla,crest FROM wc_teams WHERE name=? LIMIT 1"); $s->execute([$name]); if($r=$s->fetch()){ $tla=$r['tla']; $crest=$r['crest']; } } catch(Exception $e){}
  if (!$tla) $tla = strtoupper(mb_substr($name,0,3));
  try { db()->prepare("INSERT INTO wc_overrides(match_id,side,name,tla,crest) VALUES(?,?,?,?,?)
    ON DUPLICATE KEY UPDATE name=VALUES(name),tla=VALUES(tla),crest=VALUES(crest)")->execute([$mid,$side,$name,$tla,$crest]); } catch(Exception $e){}
}

// Render a single team slot: resolved team, or a tappable "Set team" for admins on TBD slots
function wc_slot_html($team, $mid, $side, $isWin, $isAdmin){
  $hasTeam = ($team && !empty($team['name']));
  $isOv = ($hasTeam && !empty($team['_override']));
  $cls = 'fxc-team'.($side==='away'?' right':'').($isWin?' fxc-win':'');
  $tap = $isAdmin && (!$hasTeam || $isOv);
  $click = $tap ? ' onclick="fxOpenPicker('.((int)$mid).',\''.$side.'\')" style="cursor:pointer"' : '';
  ob_start();
  echo '<div class="'.$cls.'" data-mid="'.((int)$mid).'" data-side="'.$side.'" data-team="'.h($hasTeam?$team['name']:'').'"'.$click.'>';
  if ($hasTeam) {
    $crest = !empty($team['crest']) ? $team['crest'] : '';
    $tla = !empty($team['tla']) ? $team['tla'] : strtoupper(mb_substr($team['name'],0,3));
    if ($crest) echo '<img class="fxc-crest" src="'.h($crest).'" alt="" loading="lazy" onerror="this.style.display=\'none\'">';
    else echo '<div class="fxc-crest-fallback">'.h($tla).'</div>';
    echo '<div class="fxc-tname">'.h($team['name']).($isOv?' <span style="font-size:.62rem;opacity:.7">✏️</span>':'').'</div>';
  } else {
    if ($isAdmin) {
      echo '<div class="fxc-crest-fallback" style="background:rgba(255,210,74,.14);color:var(--fx-gold);border:1px dashed rgba(255,210,74,.4)">＋</div>';
      echo '<div class="fxc-tname" style="color:var(--fx-gold)">Set team</div>';
    } else {
      echo '<div class="fxc-crest-fallback">TBD</div>';
      echo '<div class="fxc-tname" style="color:rgba(255,255,255,.5)">To be decided</div>';
    }
  }
  echo '</div>';
  return ob_get_clean();
}

// Compact one-line team row used inside the bracket cells
function wc_bracket_row($team,$mid,$side,$score,$fin,$isWin,$isAdmin){
  $hasTeam = ($team && !empty($team['name']));
  $isOv = ($hasTeam && !empty($team['_override']));
  $tap = $isAdmin && (!$hasTeam || $isOv);
  $click = $tap ? ' onclick="fxOpenPicker('.((int)$mid).',\''.$side.'\')" style="cursor:pointer"' : '';
  $cls = 'fx-brow'.($isWin?' win':'').(!$hasTeam?' tbd':'');
  ob_start();
  echo '<div class="'.$cls.'" data-mid="'.((int)$mid).'" data-side="'.$side.'" data-team="'.h($hasTeam?$team['name']:'').'"'.($tap?' data-editable="1"':'').$click.'>';
  if ($hasTeam) {
    $crest = !empty($team['crest']) ? $team['crest'] : '';
    if ($crest) echo '<img class="fx-brc" src="'.h($crest).'" alt="" onerror="this.style.display=\'none\'">';
    echo '<span class="fx-brn">'.h($team['name']).($isOv?' ✏️':'').'</span>';
  } else {
    echo '<span class="fx-brn" style="color:'.($isAdmin?'var(--fx-gold)':'rgba(255,255,255,.45)').'">'.($isAdmin?'＋ TBD':'TBD').'</span>';
  }
  echo '<span class="fx-brs">'.($score===null?'':(int)$score).'</span>';
  echo '</div>';
  return ob_get_clean();
}

// Group upcoming by IST match-day
$upByDay = [];
foreach ($upcoming as $m) {
  $day = date('D d M', strtotime($m['utcDate'])); // utcDate parsed → converted to IST by default_timezone
  if (!isset($upByDay[$day])) $upByDay[$day] = [];
  $upByDay[$day][] = $m;
}

$SELF = url('modules/fixtures.php');
$nextMatch = isset($upcoming[0]) ? $upcoming[0] : null;
?>
<?php require_once __DIR__ . '/../includes/header.php'; ?>

<style>
/* ═══════════════════════════════════════════
   WORLD CUP 2026 FIXTURES — STYLES
   ═══════════════════════════════════════════ */
:root{
  --fx-gold:#FFD24A;--fx-gold2:#FFC107;
  --fx-dark:#050a1a;--fx-darker:#020612;
  --fx-blue:#0a1628;--fx-blue2:#0d2137;
  --fx-accent:#00d4ff;--fx-green:#00ff88;--fx-red:#ff3366;
}
*{-webkit-tap-highlight-color:transparent;box-sizing:border-box}
.fxw{max-width:540px;margin:0 auto;padding-bottom:2.5rem;font-family:'DM Sans',system-ui,sans-serif;color:#fff;background:var(--fx-darker)}

/* ── HERO ── */
.fx-hero{position:relative;overflow:hidden;border-bottom:3px solid var(--fx-gold);
  background:linear-gradient(135deg,#020612,#071330 45%,#0a1d3d 75%,#0d2137);padding:1.5rem 1rem 1.3rem}
.fx-hero::before{content:'';position:absolute;inset:-50%;background:
  radial-gradient(circle at 30% 20%,rgba(255,210,74,.16),transparent 40%),
  radial-gradient(circle at 75% 80%,rgba(0,212,255,.14),transparent 42%);
  animation:fxGlow 9s ease-in-out infinite alternate}
@keyframes fxGlow{0%{transform:translate(0,0) scale(1)}100%{transform:translate(-4%,3%) scale(1.12)}}
.fx-ball{position:absolute;font-size:1.1rem;opacity:.18;animation:fxFloat linear infinite;pointer-events:none}
@keyframes fxFloat{0%{transform:translateY(110%) rotate(0)}100%{transform:translateY(-130%) rotate(360deg)}}
.fx-hero-in{position:relative;z-index:2;text-align:center}
.fx-trophy{font-size:2.6rem;display:inline-block;animation:fxTrophy 3s ease-in-out infinite;filter:drop-shadow(0 0 14px rgba(255,210,74,.6))}
@keyframes fxTrophy{0%,100%{transform:translateY(0) rotate(-6deg)}50%{transform:translateY(-7px) rotate(6deg)}}
.fx-title{font-family:'Bebas Neue',sans-serif;font-size:2.05rem;letter-spacing:.06em;line-height:.95;margin:.35rem 0 .1rem;
  background:linear-gradient(180deg,#fff 30%,var(--fx-gold));-webkit-background-clip:text;background-clip:text;color:transparent}
.fx-sub{font-size:.72rem;color:rgba(255,255,255,.55);letter-spacing:.05em;font-weight:600}
.fx-hostline{margin-top:.5rem;font-size:.64rem;color:var(--fx-gold);font-weight:800;letter-spacing:.08em}

/* ── Next-match countdown banner ── */
.fx-next{margin:.9rem .85rem 0;border-radius:16px;padding:.9rem;position:relative;overflow:hidden;
  background:linear-gradient(135deg,rgba(255,210,74,.14),rgba(0,212,255,.08));border:1.5px solid rgba(255,210,74,.32)}
.fx-next-lbl{font-size:.6rem;font-weight:900;letter-spacing:.14em;color:var(--fx-gold);text-transform:uppercase}
.fx-next-teams{display:flex;align-items:center;justify-content:center;gap:.7rem;margin:.5rem 0 .4rem;font-weight:800;font-size:.92rem}
.fx-next-cd{display:flex;justify-content:center;gap:.5rem;margin-top:.3rem}
.fx-cd-box{background:rgba(0,0,0,.35);border:1px solid rgba(255,255,255,.12);border-radius:10px;padding:.4rem .55rem;min-width:48px;text-align:center}
.fx-cd-n{font-family:'Bebas Neue',sans-serif;font-size:1.5rem;line-height:1;color:#fff}
.fx-cd-l{font-size:.52rem;letter-spacing:.1em;color:rgba(255,255,255,.45);text-transform:uppercase;margin-top:.15rem}

/* ── Tabs ── */
.fx-tabs{display:flex;gap:.4rem;padding:.9rem .85rem .3rem;position:sticky;top:0;z-index:20;background:var(--fx-darker)}
.fx-tab{flex:1;padding:.6rem .3rem;border-radius:11px;text-align:center;font-weight:800;font-size:.76rem;cursor:pointer;
  background:rgba(255,255,255,.05);border:1.5px solid rgba(255,255,255,.08);color:rgba(255,255,255,.55);transition:.2s}
.fx-tab.on{background:linear-gradient(135deg,var(--fx-gold),var(--fx-gold2));color:#0a1020;border-color:transparent;box-shadow:0 5px 16px rgba(255,210,74,.3)}
.fx-tab .cnt{display:inline-block;min-width:18px;font-size:.66rem;opacity:.85}

/* ── Sections / day headers ── */
.fx-screen{display:none;padding:.4rem .85rem}
.fx-screen.on{display:block;animation:fxFade .35s ease}
@keyframes fxFade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.fx-day{display:flex;align-items:center;gap:.5rem;margin:.9rem .15rem .5rem;font-size:.7rem;font-weight:900;letter-spacing:.05em;color:var(--fx-gold)}
.fx-day::after{content:'';flex:1;height:1px;background:linear-gradient(90deg,rgba(255,210,74,.4),transparent)}

/* ── Match card ── */
.fxc{background:linear-gradient(135deg,#08152e,#0a1628);border:1px solid rgba(255,255,255,.08);border-radius:15px;
  padding:.85rem .8rem;margin-bottom:.7rem;position:relative;overflow:hidden;opacity:0;transform:translateY(14px);
  animation:fxIn .5s ease forwards}
@keyframes fxIn{to{opacity:1;transform:none}}
.fxc-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:.55rem}
.fxc-stage{font-size:.6rem;font-weight:800;letter-spacing:.05em;color:rgba(255,255,255,.45);text-transform:uppercase}
.fxc-badge{font-size:.58rem;font-weight:900;padding:.18rem .45rem;border-radius:20px;letter-spacing:.06em}
.b-up{background:rgba(0,212,255,.12);color:var(--fx-accent);border:1px solid rgba(0,212,255,.3)}
.b-live{background:rgba(255,51,102,.15);color:#ff6b8a;border:1px solid rgba(255,51,102,.4)}
.b-fin{background:rgba(0,255,136,.1);color:var(--fx-green);border:1px solid rgba(0,255,136,.25)}
.live-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#ff3b5c;margin-right:.25rem;animation:livePulse 1.1s infinite}
@keyframes livePulse{0%{box-shadow:0 0 0 0 rgba(255,59,92,.7)}70%{box-shadow:0 0 0 6px rgba(255,59,92,0)}100%{box-shadow:0 0 0 0 rgba(255,59,92,0)}}

.fxc-body{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:.5rem}
.fxc-team{display:flex;flex-direction:column;align-items:center;gap:.3rem;text-align:center}
.fxc-team.right{order:3}
.fxc-crest{width:38px;height:38px;object-fit:contain;filter:drop-shadow(0 2px 5px rgba(0,0,0,.5));transition:transform .3s}
.fxc:hover .fxc-crest{transform:scale(1.08)}
.fxc-crest-fallback{width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  background:rgba(255,255,255,.08);font-size:.7rem;font-weight:900;color:var(--fx-gold)}
.fxc-tname{font-size:.74rem;font-weight:800;line-height:1.05}
.fxc-mid{text-align:center;min-width:62px}
.fxc-score{font-family:'Bebas Neue',sans-serif;font-size:1.7rem;letter-spacing:.06em;line-height:1;color:var(--fx-gold)}
.fxc-vs{font-family:'Bebas Neue',sans-serif;font-size:1rem;color:rgba(255,255,255,.3)}
.fxc-time{font-size:.62rem;color:#fff;font-weight:800;margin-top:.15rem}
.fxc-cd{font-size:.56rem;color:var(--fx-accent);font-weight:700;font-family:monospace;margin-top:.15rem}
.fxc-foot{display:flex;justify-content:space-between;align-items:center;margin-top:.55rem;padding-top:.5rem;border-top:1px dashed rgba(255,255,255,.08)}
.fxc-venue{font-size:.6rem;color:rgba(255,255,255,.4)}
.fxc-predict{font-size:.62rem;font-weight:800;color:var(--fx-gold);text-decoration:none}
.fxc-win .fxc-crest{filter:drop-shadow(0 0 8px rgba(255,210,74,.7))}
.fxc-win .fxc-tname{color:var(--fx-gold)}

/* ── Empty / notice ── */
.fx-empty{text-align:center;padding:2.5rem 1rem;color:rgba(255,255,255,.4)}
.fx-empty .ic{font-size:2.4rem;display:block;margin-bottom:.5rem;animation:fxTrophy 3s ease-in-out infinite}
.fx-notice{margin:.9rem .85rem;padding:.9rem;border-radius:13px;background:rgba(255,210,74,.08);border:1px solid rgba(255,210,74,.25);font-size:.74rem;color:rgba(255,255,255,.7);line-height:1.5}
.fx-meta{text-align:center;font-size:.58rem;color:rgba(255,255,255,.3);padding:.6rem;letter-spacing:.04em}

/* ── Admin panel ── */
.fx-admin{margin:.9rem .85rem;padding:1rem;border-radius:15px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1)}
.fx-admin h4{margin:0 0 .6rem;font-size:.8rem;color:var(--fx-gold);font-weight:900}
.fx-admin input{width:100%;padding:.6rem;border-radius:9px;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);color:#fff;font-size:.8rem;outline:none;margin-bottom:.5rem}
.fx-btn{padding:.6rem 1rem;border:none;border-radius:10px;font-weight:800;font-size:.76rem;cursor:pointer;font-family:inherit}
.fx-btn-g{background:linear-gradient(135deg,var(--fx-gold),var(--fx-gold2));color:#0a1020}
.fx-btn-o{background:rgba(0,212,255,.12);color:var(--fx-accent);border:1px solid rgba(0,212,255,.3)}
.fx-refresh{display:block;margin:.5rem auto 0;background:rgba(255,255,255,.06);color:rgba(255,255,255,.6);border:1px solid rgba(255,255,255,.12);padding:.5rem 1rem;border-radius:20px;font-size:.7rem;font-weight:700;cursor:pointer}

/* ── Bracket view (horizontal scroll, column per round) ── */
.fx-bracket{display:flex;gap:.7rem;overflow-x:auto;padding:.3rem .15rem 1rem;-webkit-overflow-scrolling:touch}
.fx-col{flex:0 0 auto;min-width:148px;display:flex;flex-direction:column;gap:.55rem}
.fx-col-h{font-family:'Bebas Neue',sans-serif;letter-spacing:.08em;font-size:.85rem;color:var(--fx-gold);text-align:center;padding:.25rem;border-bottom:1px solid rgba(255,210,74,.25)}
.fx-cell{background:linear-gradient(135deg,#08152e,#0a1628);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:.45rem;animation:fxIn .45s ease forwards;opacity:0}
.fx-brow{display:flex;align-items:center;gap:.35rem;padding:.28rem .2rem;border-radius:6px}
.fx-brow+.fx-brow{margin-top:.15rem;border-top:1px dashed rgba(255,255,255,.07)}
.fx-brow.win{background:rgba(255,210,74,.12)}
.fx-brow.win .fx-brn{color:var(--fx-gold)}
.fx-brow.tbd .fx-brn{font-style:italic}
.fx-brc{width:18px;height:18px;object-fit:contain;flex:0 0 auto}
.fx-brn{font-size:.68rem;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.fx-brs{font-family:'Bebas Neue',sans-serif;font-size:.9rem;color:#fff;min-width:12px;text-align:right}
.fx-cell-d{font-size:.55rem;color:rgba(255,255,255,.35);text-align:center;margin-top:.35rem;padding-top:.3rem;border-top:1px solid rgba(255,255,255,.06)}

/* ── Mirrored two-pathway "root map" bracket ── */
.fx-mirror{align-items:stretch}
.fx-side{display:flex;flex-direction:column;flex:0 0 auto}
.fx-side-tag{font-family:'Bebas Neue',sans-serif;font-size:.8rem;letter-spacing:.18em;color:var(--fx-gold);opacity:.65;margin:0 .25rem .3rem}
.fx-p2 .fx-side-tag{text-align:right}
.fx-rounds{display:flex;gap:.7rem;align-items:stretch;flex:1}
.fx-mirror .fx-col{justify-content:center;gap:.4rem;min-width:122px}
.fx-mirror .fx-col .fx-col-h{align-self:stretch}
.fx-mirror .fx-cell{position:relative;margin:0}
/* connector ticks toward the centre */
.fx-p1 .fx-cell::after{content:'';position:absolute;right:-.72rem;top:50%;width:.72rem;height:2px;background:rgba(255,210,74,.22)}
.fx-p2 .fx-cell::before{content:'';position:absolute;left:-.72rem;top:50%;width:.72rem;height:2px;background:rgba(255,210,74,.22)}
.fx-center{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.3rem;flex:0 0 auto;min-width:150px;padding:0 .4rem}
.fx-trophy{font-size:2.5rem;line-height:1;filter:drop-shadow(0 0 14px rgba(255,210,74,.6));animation:fxTrophy 4s ease-in-out infinite}
.fx-final-h{color:var(--fx-gold);font-size:1.05rem;letter-spacing:.14em;border:0}
.fx-third-h{color:#bdbdbd;font-size:.68rem;letter-spacing:.12em;border:0;margin-top:.5rem}
.fx-center .fx-cell{min-width:138px;border-color:rgba(255,210,74,.5);box-shadow:0 0 18px rgba(255,210,74,.16)}

/* ── Team picker popup ── */
.fx-pop{display:none;position:fixed;inset:0;z-index:9000;background:rgba(0,0,0,.78);backdrop-filter:blur(4px);align-items:flex-end;justify-content:center}
.fx-pop.on{display:flex;animation:fxFade .2s ease}
.fx-pop-box{width:100%;max-width:540px;background:linear-gradient(160deg,#0a1628,#050a1a);border-top:3px solid var(--fx-gold);border-radius:20px 20px 0 0;padding:1.1rem 1rem 1.4rem;animation:fxUp .25s ease}
@keyframes fxUp{from{transform:translateY(40px);opacity:.4}to{transform:none;opacity:1}}
.fx-pop-box h3{margin:0 0 .2rem;font-size:1rem;color:var(--fx-gold);font-weight:900}
.fx-pop-box p{margin:0 0 .9rem;font-size:.72rem;color:rgba(255,255,255,.5)}
.fx-pop-box select{width:100%;padding:.75rem;border-radius:11px;background:rgba(0,0,0,.45);border:1.5px solid rgba(255,255,255,.18);color:#fff;font-size:.92rem;font-weight:700;outline:none;font-family:inherit;margin-bottom:.5rem}
.fx-pop-box select:focus{border-color:var(--fx-gold)}
.fx-pop-act{display:flex;gap:.5rem;margin-top:.6rem}
.fx-pop-act .fx-btn{flex:1}
.fx-pop-clear{background:rgba(255,70,90,.14);color:#ff8a98;border:1px solid rgba(255,70,90,.3)}
.fx-pop-x{background:rgba(255,255,255,.06);color:rgba(255,255,255,.6);border:1px solid rgba(255,255,255,.12)}

/* ── Champion banner ── */
.fx-champ{position:relative;overflow:hidden;display:flex;align-items:center;gap:.8rem;margin:.2rem .15rem .7rem;padding:.9rem 1rem;border-radius:15px;border:1.5px solid rgba(255,210,74,.5);background:linear-gradient(135deg,rgba(255,210,74,.18),rgba(255,255,255,.03))}
.fx-champ-g{position:absolute;inset:-50%;background:radial-gradient(circle at 30% 50%,rgba(255,210,74,.3),transparent 55%);animation:fxGlow 5s ease-in-out infinite alternate}
.fx-champ-c{width:46px;height:46px;object-fit:contain;position:relative;z-index:2;filter:drop-shadow(0 0 8px rgba(255,210,74,.7))}
.fx-champ-l{font-size:.6rem;font-weight:900;letter-spacing:.14em;color:var(--fx-gold)}
.fx-champ-n{font-family:'Bebas Neue',sans-serif;font-size:1.6rem;letter-spacing:.04em;color:#fff;line-height:1}

/* ── Bracket toolbar + Save All ── */
.fx-path-title{font-family:'Bebas Neue',sans-serif;text-align:center;font-size:1.5rem;letter-spacing:.14em;color:var(--fx-gold);margin:.3rem 0 .5rem;text-shadow:0 2px 12px rgba(255,210,74,.3)}
.fx-custom-badge{text-align:center;font-size:.62rem;font-weight:700;letter-spacing:.05em;color:#0a1628;background:linear-gradient(90deg,#ffd24a,#ffb300);border-radius:20px;padding:.35rem .6rem;margin:0 auto .5rem;max-width:max-content}
.fx-brow.swappable{outline:1px dashed var(--fx-gold);outline-offset:-1px;cursor:pointer}
.fx-brow.swapsel{background:rgba(255,210,74,.28)!important}
.fx-bracket-bar{display:flex;gap:.5rem;margin:.2rem .15rem .2rem}
.fx-bracket-bar .fx-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:.3rem}
.fx-saveall{position:sticky;bottom:.6rem;display:flex;gap:.5rem;margin:.7rem .15rem 0;padding:.5rem;border-radius:13px;background:rgba(5,10,26,.92);border:1px solid rgba(255,210,74,.3);backdrop-filter:blur(6px);box-shadow:0 6px 20px rgba(0,0,0,.5);z-index:30}
.fx-saveall .fx-btn{flex:1}
.fx-edit-sel{width:100%;padding:.3rem;border-radius:6px;background:rgba(0,0,0,.5);border:1px solid var(--fx-gold);color:#fff;font-size:.66rem;font-weight:700;outline:none;font-family:inherit}
.fx-brow.editing{background:rgba(255,210,74,.08)}
</style>

<div class="fxw">

  <!-- HERO -->
  <div class="fx-hero">
    <div id="fxBalls"></div>
    <div class="fx-hero-in">
      <span class="fx-trophy">🏆</span>
      <div class="fx-title">WORLD CUP 2026</div>
      <div class="fx-sub">Fixtures · Live Scores · Results</div>
      <div class="fx-hostline">🇨🇦 CANADA · 🇲🇽 MEXICO · 🇺🇸 USA</div>
    </div>
  </div>

  <?php if($nextMatch):
    $nh = $nextMatch['homeTeam']; $na = $nextMatch['awayTeam']; ?>
  <!-- NEXT MATCH COUNTDOWN -->
  <div class="fx-next">
    <div style="text-align:center"><span class="fx-next-lbl">⏱ Next Kick-off</span></div>
    <div class="fx-next-teams">
      <span><?= h(wc_team_tla($nh)) ?></span>
      <span style="color:rgba(255,255,255,.3);font-weight:900">vs</span>
      <span><?= h(wc_team_tla($na)) ?></span>
    </div>
    <div class="fx-next-cd" id="nextCd" data-utc="<?= h($nextMatch['utcDate']) ?>">
      <div class="fx-cd-box"><div class="fx-cd-n" data-d>--</div><div class="fx-cd-l">Days</div></div>
      <div class="fx-cd-box"><div class="fx-cd-n" data-h>--</div><div class="fx-cd-l">Hrs</div></div>
      <div class="fx-cd-box"><div class="fx-cd-n" data-m>--</div><div class="fx-cd-l">Min</div></div>
      <div class="fx-cd-box"><div class="fx-cd-n" data-s>--</div><div class="fx-cd-l">Sec</div></div>
    </div>
  </div>
  <?php endif; ?>

  <?php if(!$hasKey): ?>
  <div class="fx-notice">
    ⚙️ <b>No API key set yet.</b> This module pulls live fixtures from the football-data.org API.
    <?php if($isAdmin): ?> Add your free API key below to start.<?php else: ?> Ask an admin to configure the API key.<?php endif; ?>
  </div>
  <?php elseif(empty($matches)): ?>
  <div class="fx-notice">
    📡 No fixtures cached yet. <?php if($isAdmin): ?>Tap <b>Refresh</b> below to pull the schedule.<?php else: ?>Check back shortly.<?php endif; ?>
  </div>
  <?php endif; ?>

  <!-- TABS -->
  <div class="fx-tabs">
    <div class="fx-tab" id="t-upcoming" onclick="fxTab('upcoming')">⏰ Upcoming <span class="cnt">(<?= count($upcoming) ?>)</span></div>
    <div class="fx-tab" id="t-live" onclick="fxTab('live')"><?= $live?'<span class="live-dot"></span>':'' ?>LIVE <span class="cnt">(<?= count($live) ?>)</span></div>
    <div class="fx-tab" id="t-finished" onclick="fxTab('finished')">✅ Results <span class="cnt">(<?= count($finished) ?>)</span></div>
    <div class="fx-tab on" id="t-bracket" onclick="fxTab('bracket')">🏆 Bracket</div>
  </div>

  <?php
  // Reusable card renderer
  $renderCard = function($m, $idx) use ($ovr, $isAdmin) {
    $st  = isset($m['status']) ? $m['status'] : 'SCHEDULED';
    $hh  = wc_resolve($m, 'home', $ovr);
    $aa  = wc_resolve($m, 'away', $ovr);
    $ft  = isset($m['score']['fullTime']) ? $m['score']['fullTime'] : ['home'=>null,'away'=>null];
    $sh  = isset($ft['home']) ? $ft['home'] : null;
    $sa  = isset($ft['away']) ? $ft['away'] : null;
    $isLive = ($st==='IN_PLAY' || $st==='PAUSED');
    $isFin  = ($st==='FINISHED' || $st==='AWARDED');
    $win = null;
    if (($isFin || $isLive) && $sh!==null && $sa!==null) {
      if ($sh>$sa) $win='home'; elseif ($sa>$sh) $win='away';
    }
    $kt = date('g:i A', strtotime($m['utcDate']));
    $kd = date('D d M', strtotime($m['utcDate']));
    $delay = min($idx*0.05, 0.6);
    ?>
    <div class="fxc" data-mid="<?= (int)$m['id'] ?>" style="animation-delay:<?= $delay ?>s">
      <div class="fxc-top">
        <span class="fxc-stage"><?= h(wc_pretty_stage(isset($m['stage'])?$m['stage']:'')) ?><?= !empty($m['group'])?' · '.h(str_replace('GROUP_','Grp ',$m['group'])):'' ?></span>
        <?php if($isLive): ?>
          <span class="fxc-badge b-live" data-badge><span class="live-dot"></span>LIVE<?= isset($m['minute'])&&$m['minute']?" {$m['minute']}'":'' ?></span>
        <?php elseif($isFin): ?>
          <span class="fxc-badge b-fin" data-badge>FULL TIME</span>
        <?php else: ?>
          <span class="fxc-badge b-up" data-badge><?= h($kd) ?></span>
        <?php endif; ?>
      </div>
      <div class="fxc-body">
        <?= wc_slot_html($hh, (int)$m['id'], 'home', $win==='home', $isAdmin) ?>
        <div class="fxc-mid">
          <?php if($isLive || $isFin): ?>
            <div class="fxc-score" data-score><?= $sh===null?'-':$sh ?> <span style="color:rgba(255,255,255,.25)">:</span> <?= $sa===null?'-':$sa ?></div>
            <div class="fxc-time"><?= $isFin?'FT':h($kt) ?></div>
          <?php else: ?>
            <div class="fxc-vs">VS</div>
            <div class="fxc-time"><?= h($kt) ?></div>
            <div class="fxc-cd" data-cd data-utc="<?= h($m['utcDate']) ?>"></div>
          <?php endif; ?>
        </div>
        <?= wc_slot_html($aa, (int)$m['id'], 'away', $win==='away', $isAdmin) ?>
      </div>
      <div class="fxc-foot">
        <span class="fxc-venue">🏟 <?= h(!empty($m['venue'])?$m['venue']:'Venue TBA') ?></span>
        <a class="fxc-predict" href="<?= h(url('modules/prediction.php')) ?>">🎯 Predict ›</a>
      </div>
    </div>
    <?php
  };
  ?>

  <!-- UPCOMING (default) -->
  <div class="fx-screen" id="s-upcoming">
    <?php if(empty($upcoming)): ?>
      <div class="fx-empty"><span class="ic">⚽</span>No upcoming matches right now.</div>
    <?php else: $gi=0; foreach($upByDay as $day=>$dayMatches): ?>
      <div class="fx-day">📅 <?= h($day) ?></div>
      <?php foreach($dayMatches as $m){ $renderCard($m, $gi++); } ?>
    <?php endforeach; endif; ?>
  </div>

  <!-- LIVE -->
  <div class="fx-screen" id="s-live">
    <?php if(empty($live)): ?>
      <div class="fx-empty"><span class="ic">📺</span>No matches live at the moment.<br><span style="font-size:.7rem">Live scores appear here on match day.</span></div>
    <?php else: $i=0; foreach($live as $m){ $renderCard($m, $i++); } endif; ?>
  </div>

  <!-- FINISHED -->
  <div class="fx-screen" id="s-finished">
    <?php if(empty($finished)): ?>
      <div class="fx-empty"><span class="ic">🏁</span>No results yet.</div>
    <?php else: $i=0; foreach($finished as $m){ if($i>=60)break; $renderCard($m, $i++); } endif; ?>
  </div>

  <!-- BRACKET (real API matches, two-pathway layout) -->
  <div class="fx-screen on" id="s-bracket">
    <?php if($champion): ?>
    <div class="fx-champ">
      <div class="fx-champ-g"></div>
      <?php if($championCrest): ?><img src="<?= h($championCrest) ?>" class="fx-champ-c" onerror="this.style.display='none'"><?php endif; ?>
      <div style="position:relative;z-index:2"><div class="fx-champ-l">🏆 WORLD CHAMPIONS 2026</div><div class="fx-champ-n"><?= h($champion) ?></div></div>
    </div>
    <?php endif; ?>

    <?php if(!$haveKObracket): ?>
      <div class="fx-empty"><span class="ic">🏆</span>The knockout bracket will appear here once the feed provides the Round of 32.<br>
        <span style="font-size:.72rem;color:rgba(255,255,255,.5)">If it stays empty, your data source may not cover the 48-team Round of 32 yet — tap Refresh, or see the note in Admin.</span></div>
    <?php else:
      if ($useFifa) {
        // Correct tournament tree: place every match on its true side (teams from live data)
        $P1=[]; foreach($FIFA_P1 as $rn=>$nums){ $P1[$rn]=[]; foreach($nums as $nn){ $P1[$rn][]=wc_view_for($nn,$koByMid,$ovr); } }
        $P2=[]; foreach($FIFA_P2 as $rn=>$nums){ $P2[$rn]=[]; foreach($nums as $nn){ $P2[$rn][]=wc_view_for($nn,$koByMid,$ovr); } }
        $finalV   = wc_view_for($FIFA_FINAL,$koByMid,$ovr);
        $thirdView = isset($koByMid[$FIFA_THIRD]) ? $koByMid[$FIFA_THIRD] : $thirdView;
      } else {
        // fallback for feeds without FIFA match numbers: simple half-split
        $splitR32=wc_split($koViews,'Round of 32'); $splitR16=wc_split($koViews,'Round of 16');
        $splitQF =wc_split($koViews,'Quarter-finals'); $splitSF=wc_split($koViews,'Semi-finals');
        $P1=['Round of 32'=>$splitR32[0],'Round of 16'=>$splitR16[0],'Quarter-finals'=>$splitQF[0],'Semi-final'=>$splitSF[0]];
        $P2=['Semi-final'=>$splitSF[1],'Quarter-finals'=>$splitQF[1],'Round of 16'=>$splitR16[1],'Round of 32'=>$splitR32[1]];
        $finalV = !empty($koViews['Final']) ? $koViews['Final'][0] : null;
      }
    ?>
    <div class="fx-path-title">🏆 PATH TO THE FINAL</div>
    <?php if($bracketCustom): ?><div class="fx-custom-badge">⚙️ CUSTOM BRACKET — rearranged by admin · not the official draw</div><?php endif; ?>
    <div class="fx-bracket-bar">
      <button class="fx-btn fx-btn-o" onclick="fxShareBracket()">📲 Share Bracket</button>
      <?php if($isAdmin): ?>
      <button class="fx-btn fx-btn-g" id="fxRearrBtn" onclick="fxRearrange(true)">🔀 Rearrange</button>
      <?php if($bracketCustom): ?><button class="fx-btn fx-pop-x" onclick="fxResetBracket()">↩ Reset draw</button><?php endif; ?>
      <?php endif; ?>
    </div>
    <?php if($isAdmin): ?>
    <div id="fxSwapBar" style="display:none;align-items:center;gap:.6rem;margin:.3rem .15rem .4rem">
      <span style="font-size:.72rem;color:var(--fx-gold)">🔀 Tap two teams to swap their positions</span>
      <button class="fx-btn fx-pop-x" onclick="fxRearrange(false)">Done</button>
    </div>
    <?php endif; ?>
    <div style="font-size:.62rem;color:rgba(255,255,255,.38);margin:.1rem .15rem .55rem">← swipe across the rounds →<?= $isAdmin?' · <b style="color:var(--fx-gold)">Rearrange</b> to move teams':'' ?></div>

    <div class="fx-bracket fx-mirror">
      <!-- PATHWAY 1 (left half) -->
      <div class="fx-side fx-p1">
        <div class="fx-side-tag">◂ PATHWAY 1</div>
        <div class="fx-rounds">
          <?php foreach($P1 as $rn=>$vs): if(empty($vs)) continue; ?>
            <div class="fx-col">
              <div class="fx-col-h"><?= h($rn) ?></div>
              <?php foreach($vs as $v) echo wc_live_cell($v,$isAdmin); ?>
            </div>
          <?php endforeach; ?>
        </div>
      </div>

      <!-- CENTRE: Final + trophy + 3rd place -->
      <div class="fx-center">
        <div class="fx-trophy">🏆</div>
        <div class="fx-col-h fx-final-h">FINAL</div>
        <?php if($finalV) echo wc_live_cell($finalV,$isAdmin); else echo '<div class="fx-cell"><div class="fx-brow tbd"><span class="fx-brn">TBD</span></div><div class="fx-brow tbd"><span class="fx-brn">TBD</span></div></div>'; ?>
        <?php if($thirdView): ?>
          <div class="fx-col-h fx-third-h">3RD PLACE</div>
          <?= wc_live_cell($thirdView,$isAdmin) ?>
        <?php endif; ?>
      </div>

      <!-- PATHWAY 2 (right half) -->
      <div class="fx-side fx-p2">
        <div class="fx-side-tag">PATHWAY 2 ▸</div>
        <div class="fx-rounds">
          <?php foreach($P2 as $rn=>$vs): if(empty($vs)) continue; ?>
            <div class="fx-col">
              <div class="fx-col-h"><?= h($rn) ?></div>
              <?php foreach($vs as $v) echo wc_live_cell($v,$isAdmin); ?>
            </div>
          <?php endforeach; ?>
        </div>
      </div>
    </div>

    <?php if($isAdmin): ?>
    <div class="fx-saveall" id="fxSaveAllBar" style="display:none">
      <button class="fx-btn fx-pop-x" onclick="fxBracketEdit(false)">Cancel</button>
      <button class="fx-btn fx-btn-g" onclick="fxSaveAll()">💾 Save All</button>
    </div>
    <?php endif; ?>
    <?php endif; ?>
  </div>
  <div class="fx-meta">
    <?php
      $srcLabel = $srcNow==='openfootball' ? 'openfootball (free)' : ($srcNow==='worldcup26' ? 'worldcup26.ir' : 'football-data.org');
      if($fetchedAt): ?>Updated <?= h(date('d M, g:i A', strtotime($fetchedAt))) ?> IST<?php else: ?>Not yet synced<?php endif; ?>
    · Source: <?= h($srcLabel) ?> · <span style="color:var(--fx-gold)">bracket v8 · true FIFA bracket sides</span>
  </div>

  <?php if($isAdmin): ?>
  <div class="fx-admin">
    <h4>⚙️ Fixtures Admin</h4>

    <label style="font-size:.7rem;color:rgba(255,255,255,.55);display:block;margin-bottom:.3rem">Data source</label>
    <select id="fxSource" onchange="fxSourceChange()" style="width:100%;padding:.55rem;border-radius:10px;background:#0a1628;color:#fff;border:1px solid rgba(255,255,255,.15);margin-bottom:.4rem">
      <option value="openfootball" <?= $srcNow==='openfootball'?'selected':'' ?>>openfootball — free, no key, full 48-team R32 (recommended)</option>
      <option value="football-data" <?= $srcNow==='football-data'?'selected':'' ?>>football-data.org — needs key, may lack R32</option>
      <option value="worldcup26" <?= $srcNow==='worldcup26'?'selected':'' ?>>worldcup26.ir — needs a token</option>
    </select>

    <div id="fxSrcOF" style="display:<?= $srcNow==='openfootball'?'block':'none' ?>;font-size:.64rem;color:rgba(255,255,255,.45);margin:.2rem 0 .5rem;line-height:1.5">
      ✅ Free & keyless. Pulls real teams, scores and knockout placeholders (public-domain data). Just tap Refresh.
    </div>

    <div id="fxSrcWC26" style="display:<?= $srcNow==='worldcup26'?'block':'none' ?>;margin-bottom:.5rem">
      <input type="text" id="fxWc26Token" placeholder="worldcup26.ir JWT token" autocomplete="off" style="width:100%;padding:.55rem;border-radius:10px;background:#0a1628;color:#fff;border:1px solid rgba(255,255,255,.15)">
      <div style="font-size:.62rem;color:rgba(255,255,255,.4);margin-top:.3rem">Register once at worldcup26.ir, then paste the token.</div>
    </div>

    <div id="fxSrcFD" style="display:<?= $srcNow==='football-data'?'block':'none' ?>;margin-bottom:.5rem">
      <?php if(!defined('FOOTBALL_DATA_KEY')): ?>
        <input type="text" id="fxKey" placeholder="<?= $hasKey?'•••••••• (saved — paste to replace)':'football-data.org API token' ?>" autocomplete="off" style="width:100%;padding:.55rem;border-radius:10px;background:#0a1628;color:#fff;border:1px solid rgba(255,255,255,.15)">
        <button class="fx-btn fx-btn-g" onclick="fxSaveKey()" style="margin-top:.4rem">💾 Save key</button>
        <div style="font-size:.62rem;color:rgba(255,255,255,.4);margin-top:.3rem">Free token at football-data.org. Note: free plan may not expose the 48-team Round of 32.</div>
      <?php else: ?>
        <div style="font-size:.7rem;color:var(--fx-green)">✅ Key loaded from server config.</div>
      <?php endif; ?>
    </div>

    <button class="fx-btn fx-btn-g" onclick="fxSaveSource()">💾 Use this source</button>
    <button class="fx-btn fx-btn-o" onclick="fxRefresh(this)" style="margin-left:.4rem">🔄 Refresh now</button>
    <div style="font-size:.62rem;color:rgba(255,255,255,.4);margin-top:.6rem">Fixtures auto-refresh periodically. After deploying, bump your service-worker cache version so the new file loads.</div>
  </div>
  <?php elseif(true): ?>
  <button class="fx-refresh" onclick="location.reload()">🔄 Reload fixtures</button>
  <?php endif; ?>

</div>

<?php if($isAdmin): ?>
<!-- TEAM PICKER POPUP -->
<div class="fx-pop" id="fxPop" onclick="if(event.target===this)fxClosePicker()">
  <div class="fx-pop-box">
    <h3>🎯 Assign Team</h3>
    <p id="fxPickHint">Knocked-out teams are hidden automatically. Pick who reaches this slot.</p>
    <select id="fxPickSel" onchange="fxPreview()"></select>
    <div style="text-align:right;margin:-.2rem 0 .2rem"><span id="fxPickToggle" onclick="fxToggleAll()" style="display:none;font-size:.68rem;font-weight:800;color:var(--fx-accent);cursor:pointer"></span></div>
    <div id="fxPickPrev" style="display:none;align-items:center;gap:.6rem;padding:.6rem .7rem;border-radius:11px;background:rgba(255,210,74,.1);border:1px solid rgba(255,210,74,.3);margin-bottom:.3rem">
      <img id="fxPickPrevImg" style="width:34px;height:34px;object-fit:contain" onerror="this.style.display='none'">
      <div><div style="font-size:.55rem;color:var(--fx-gold);font-weight:800;letter-spacing:.1em">SELECTED</div><div id="fxPickPrevName" style="font-size:.95rem;font-weight:900;color:#fff"></div></div>
    </div>
    <div class="fx-pop-act">
      <button class="fx-btn fx-btn-g" onclick="fxSavePicker()">💾 Save</button>
      <button class="fx-btn fx-pop-clear" onclick="fxClearPicker()">↺ Clear</button>
      <button class="fx-btn fx-pop-x" onclick="fxClosePicker()">Cancel</button>
    </div>
  </div>
</div>
<?php endif; ?>

<script>
var FX_SELF = <?= json_encode(url('modules/fixtures.php')) ?>;
var FX_HAS_LIVE = <?= $live ? 'true':'false' ?>;
var FX_ADMIN = <?= $isAdmin ? 'true':'false' ?>;
// Teams still alive (knocked-out teams already removed server-side) for the picker dropdown
var FX_ALIVE = <?= json_encode(array_map(function($t){ return ['name'=>$t['name'],'tla'=>$t['tla'],'crest'=>(isset($t['crest'])?$t['crest']:'')]; }, $aliveTeams), JSON_UNESCAPED_UNICODE) ?>;
// Names of teams still alive (for the admin "assign a team" picker on TBD slots)
var FX_CAND = <?= json_encode($fxCandNames, JSON_UNESCAPED_UNICODE) ?>;
// Per-slot candidates ("97:home" → teams that can actually reach that slot via its feeder match)
var FX_SLOTCAND = <?= json_encode($fxSlotCand, JSON_UNESCAPED_UNICODE) ?>;
var FX_USER = <?= json_encode($me['name']) ?>;
var FX_CLUB = <?= json_encode($CLUB) ?>;
var FX_PLACE = <?= json_encode(setting('CLUB_PLACE','Vettikkattiri')) ?>;
var FX_ROUNDS = <?= json_encode($FX_ROUNDS, JSON_UNESCAPED_UNICODE) ?>;
var FX_P1 = <?= json_encode($FX_P1, JSON_UNESCAPED_UNICODE) ?>;
var FX_P2 = <?= json_encode($FX_P2, JSON_UNESCAPED_UNICODE) ?>;
var FX_FINAL = <?= json_encode($FX_FINAL, JSON_UNESCAPED_UNICODE) ?>;

// ── Hero floating balls ──
(function(){
  var b=document.getElementById('fxBalls'); if(!b)return;
  for(var i=0;i<7;i++){
    var s=document.createElement('span'); s.className='fx-ball'; s.textContent=(i%2?'⚽':'🏆');
    s.style.left=(Math.random()*100)+'%';
    s.style.animationDuration=(7+Math.random()*7)+'s';
    s.style.animationDelay=(-Math.random()*8)+'s';
    s.style.fontSize=(0.9+Math.random()*1.3)+'rem';
    b.appendChild(s);
  }
})();

// ── Tabs ──
function fxTab(name){
  ['upcoming','live','finished','bracket'].forEach(function(n){
    var t=document.getElementById('t-'+n), s=document.getElementById('s-'+n);
    if(t) t.classList.toggle('on', n===name);
    if(s) s.classList.toggle('on', n===name);
  });
  // restart entrance animation on the shown cards/cells
  document.querySelectorAll('#s-'+name+' .fxc, #s-'+name+' .fx-cell').forEach(function(c,i){
    c.style.animation='none'; void c.offsetWidth;
    c.style.animation='fxIn .5s ease forwards'; c.style.animationDelay=Math.min(i*0.04,0.7)+'s';
  });
  window.scrollTo({top:0,behavior:'smooth'});
}

// ── Countdown helpers ──
function fxFmt(ms){
  if(ms<=0) return null;
  var s=Math.floor(ms/1000);
  return {d:Math.floor(s/86400),h:Math.floor(s%86400/3600),m:Math.floor(s%3600/60),s:s%60};
}
function fxPad(n){return (n<10?'0':'')+n;}
function fxTickAll(){
  var now=Date.now();
  // big banner
  var nb=document.getElementById('nextCd');
  if(nb){
    var t=fxFmt(new Date(nb.dataset.utc).getTime()-now);
    if(t){
      nb.querySelector('[data-d]').textContent=t.d;
      nb.querySelector('[data-h]').textContent=fxPad(t.h);
      nb.querySelector('[data-m]').textContent=fxPad(t.m);
      nb.querySelector('[data-s]').textContent=fxPad(t.s);
    } else { nb.querySelectorAll('.fx-cd-n').forEach(function(e){e.textContent='0';}); }
  }
  // per-card mini countdowns
  document.querySelectorAll('[data-cd]').forEach(function(el){
    var t=fxFmt(new Date(el.dataset.utc).getTime()-now);
    if(!t){ el.textContent='🔴 Kick-off!'; return; }
    if(t.d>0) el.textContent='in '+t.d+'d '+t.h+'h';
    else if(t.h>0) el.textContent='in '+t.h+'h '+fxPad(t.m)+'m';
    else el.textContent='in '+t.m+'m '+fxPad(t.s)+'s';
  });
}
fxTickAll(); setInterval(fxTickAll,1000);

// ── Live score polling (only when there are live games) ──
function fxPollLive(){
  fetch(FX_SELF+'?action=data').then(function(r){return r.json();}).then(function(res){
    if(!res.ok)return;
    var anyLive=false;
    res.matches.forEach(function(m){
      var card=document.querySelector('.fxc[data-mid="'+m.id+'"]');
      if(!card)return;
      if(m.status==='IN_PLAY'||m.status==='PAUSED'){
        anyLive=true;
        var sc=card.querySelector('[data-score]');
        if(sc) sc.innerHTML=(m.h===null?'-':m.h)+' <span style="color:rgba(255,255,255,.25)">:</span> '+(m.a===null?'-':m.a);
        var bd=card.querySelector('[data-badge]');
        if(bd){bd.className='fxc-badge b-live';bd.innerHTML='<span class="live-dot"></span>LIVE'+(m.minute?(" "+m.minute+"'"):'');}
      }
    });
    // if live status changed (a game started/ended), refresh to re-bucket the tabs
    if(anyLive!==FX_HAS_LIVE){ setTimeout(function(){location.reload();},900); }
  }).catch(function(){});
}
if(FX_HAS_LIVE){ setInterval(fxPollLive,45000); }

// ── Admin ──
function fxSaveKey(){
  var k=document.getElementById('fxKey').value.trim();
  var fd=new FormData(); fd.append('action','savekey'); fd.append('key',k);
  fetch(FX_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    alert(res.msg||'Saved'); if(res.ok) location.reload();
  });
}
function fxRefresh(btn){
  if(btn){btn.disabled=true;btn.textContent='⏳ Fetching…';}
  var fd=new FormData(); fd.append('action','refresh');
  fetch(FX_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    alert(res.msg||'Done'); location.reload();
  }).catch(function(){ if(btn){btn.disabled=false;btn.textContent='🔄 Refresh now';} });
}
function fxSourceChange(){
  var v=document.getElementById('fxSource').value;
  var of=document.getElementById('fxSrcOF'), wc=document.getElementById('fxSrcWC26'), fd=document.getElementById('fxSrcFD');
  if(of) of.style.display=(v==='openfootball')?'block':'none';
  if(wc) wc.style.display=(v==='worldcup26')?'block':'none';
  if(fd) fd.style.display=(v==='football-data')?'block':'none';
}
function fxSaveSource(){
  var v=document.getElementById('fxSource').value;
  var fd=new FormData(); fd.append('action','savesource'); fd.append('source',v);
  var tk=document.getElementById('fxWc26Token'); if(tk) fd.append('wc26_token',tk.value.trim());
  fetch(FX_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    alert(res.msg||'Saved'); location.reload();
  });
}

// ── Assign-team picker: fill a TBD bracket slot (by match id + side) ──
// The list is scoped to the slot: only teams that can reach it through its
// feeder match are shown (QF ← its R16 feeder, SF ← QF, ...). A "Show all
// teams" toggle falls back to every still-alive team if ever needed.
var fxPick={mid:null,side:null};
var fxPickScoped=null, fxPickCur='', fxPickAll=false;
function fxCandsFor(mid,side){
  if (typeof FX_SLOTCAND==='undefined') return null;
  var l=FX_SLOTCAND[mid+':'+side];
  return (l && l.length) ? l.slice() : null;
}
function fxFillPickSel(list,cur){
  var sel=document.getElementById('fxPickSel');
  sel.innerHTML='<option value="">— TBD —</option>';
  if (cur && list.indexOf(cur)<0) list=list.concat([cur]); // keep the current pick visible
  list.forEach(function(nm){
    var f=FX_ALIVE.filter(function(t){return t.name===nm;})[0]||{name:nm,tla:''};
    var o=document.createElement('option'); o.value=nm; o.textContent=nm+(f.tla?(' ('+f.tla+')'):'');
    if(cur&&nm===cur)o.selected=true; sel.appendChild(o);
  });
}
function fxOpenPicker(mid,side){
  if(typeof FX_ADMIN!=='undefined' && !FX_ADMIN) return;
  fxPick={mid:mid,side:side};
  var h3=document.querySelector('#fxPop h3'); if(h3) h3.textContent='🎯 Assign team';
  var cell=document.querySelector('.fx-brow[data-mid="'+mid+'"][data-side="'+side+'"]');
  fxPickCur=cell?(cell.getAttribute('data-team')||''):'';
  fxPickScoped=fxCandsFor(mid,side);
  fxPickAll=false;
  fxFillPickSel(fxPickScoped||FX_CAND, fxPickCur);
  var hint=document.getElementById('fxPickHint');
  if(hint) hint.textContent = fxPickScoped
    ? 'Only teams that can reach this slot (from its feeder match) are listed.'
    : 'Pick the team for this slot. Only teams still in the tournament are listed.';
  var tgl=document.getElementById('fxPickToggle');
  if(tgl){ tgl.style.display=fxPickScoped?'inline':'none'; tgl.textContent='Show all teams'; }
  fxPreview();
  document.getElementById('fxPop').classList.add('on'); document.body.style.overflow='hidden';
}
function fxPreview(){
  var name=document.getElementById('fxPickSel').value;
  var box=document.getElementById('fxPickPrev'); if(!box)return;
  if(!name){ box.style.display='none'; return; }
  var t=FX_ALIVE.filter(function(x){return x.name===name;})[0]||{name:name,crest:''};
  document.getElementById('fxPickPrevName').textContent=name;
  var img=document.getElementById('fxPickPrevImg');
  if(t.crest){ img.src=t.crest; img.style.display='block'; } else { img.style.display='none'; }
  box.style.display='flex';
}
function fxToggleAll(){
  if(!fxPickScoped) return;
  fxPickAll=!fxPickAll;
  fxFillPickSel(fxPickAll?FX_CAND.slice():fxPickScoped.slice(), fxPickCur);
  var tgl=document.getElementById('fxPickToggle');
  if(tgl) tgl.textContent=fxPickAll?'Show qualified only':'Show all teams';
  var hint=document.getElementById('fxPickHint');
  if(hint) hint.textContent=fxPickAll
    ? 'Showing every team still in the tournament.'
    : 'Only teams that can reach this slot (from its feeder match) are listed.';
  fxPreview();
}
function fxClosePicker(){ var p=document.getElementById('fxPop'); if(p)p.classList.remove('on'); document.body.style.overflow=''; }
function fxSavePicker(){
  var name=document.getElementById('fxPickSel').value;
  var fd=new FormData(); fd.append('action','set_team'); fd.append('match_id',fxPick.mid); fd.append('side',fxPick.side); fd.append('name',name);
  fetch(FX_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok) location.reload(); else alert(res.msg||'Failed');
  });
}
function fxClearPicker(){
  var fd=new FormData(); fd.append('action','clear_team'); fd.append('match_id',fxPick.mid); fd.append('side',fxPick.side);
  fetch(FX_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(){ location.reload(); });
}

// ── Batch edit: every TBD/override slot becomes a dropdown, save all at once ──
function fxBuildSlotSel(mid,side,current){
  var sel=document.createElement('select'); sel.className='fx-edit-sel'; sel.setAttribute('data-mid',mid); sel.setAttribute('data-side',side);
  var o0=document.createElement('option'); o0.value=''; o0.textContent='— TBD —'; sel.appendChild(o0);
  var list=fxCandsFor(mid,side)||FX_CAND.slice();
  if(current && list.indexOf(current)<0) list=list.concat([current]); // keep the current pick visible
  list.forEach(function(nm){ var f=FX_ALIVE.filter(function(t){return t.name===nm;})[0]||{name:nm,tla:''}; var o=document.createElement('option'); o.value=nm; o.textContent=nm+(f.tla?(' ('+f.tla+')'):''); if(current&&nm===current)o.selected=true; sel.appendChild(o); });
  return sel;
}
function fxBracketEdit(on){
  if(!on){ location.reload(); return; }
  document.querySelectorAll('#s-bracket .fx-brow[data-editable="1"]').forEach(function(row){
    var mid=row.getAttribute('data-mid'), side=row.getAttribute('data-side'), cur=row.getAttribute('data-team')||'';
    row.innerHTML=''; row.appendChild(fxBuildSlotSel(mid,side,cur)); row.classList.add('editing'); row.onclick=null;
  });
  var eb=document.getElementById('fxEditBtn'); if(eb) eb.style.display='none';
  var sb=document.getElementById('fxSaveAllBar'); if(sb) sb.style.display='flex';
}
function fxSaveAll(){
  var picks=[];
  document.querySelectorAll('#s-bracket select.fx-edit-sel').forEach(function(sel){
    picks.push({match_id:parseInt(sel.getAttribute('data-mid'),10), side:sel.getAttribute('data-side'), name:sel.value});
  });
  if(!picks.length){ location.reload(); return; }
  var fd=new FormData(); fd.append('action','set_team_bulk'); fd.append('picks',JSON.stringify(picks));
  fetch(FX_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok) location.reload(); else alert(res.msg||'Save failed');
  });
}

// ── Rearrange mode: swap two Round-of-32 teams to build a custom bracket ──
var fxSwapMode=false, fxSwapSel=null;
function fxRearrange(on){
  fxSwapMode=on; if(fxSwapSel){fxSwapSel.classList.remove('swapsel');} fxSwapSel=null;
  document.querySelectorAll('#s-bracket .fx-cell').forEach(function(c){
    var mid=parseInt(c.getAttribute('data-mid'),10);
    var isR32=(mid>=73&&mid<=88);
    c.querySelectorAll('.fx-brow').forEach(function(r){
      var hasTeam=r.getAttribute('data-team');
      if(on&&isR32&&hasTeam){ r.classList.add('swappable'); r.onclick=function(){fxPickSwap(r);}; }
      else { r.classList.remove('swappable','swapsel'); if(on){ r.onclick=null; } }
    });
  });
  var rb=document.getElementById('fxRearrBtn'); if(rb) rb.style.display=on?'none':'';
  var bar=document.getElementById('fxSwapBar'); if(bar) bar.style.display=on?'flex':'none';
}
function fxPickSwap(row){
  if(!fxSwapMode) return;
  if(!fxSwapSel){ fxSwapSel=row; row.classList.add('swapsel'); return; }
  if(fxSwapSel===row){ row.classList.remove('swapsel'); fxSwapSel=null; return; }
  var fd=new FormData(); fd.append('action','swap_slots');
  fd.append('a_num',fxSwapSel.getAttribute('data-mid')); fd.append('a_side',fxSwapSel.getAttribute('data-side')==='home'?'h':'a');
  fd.append('b_num',row.getAttribute('data-mid'));        fd.append('b_side',row.getAttribute('data-side')==='home'?'h':'a');
  fetch(FX_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(res){
    if(res.ok) location.reload(); else { alert(res.msg||'Swap failed'); fxSwapSel.classList.remove('swapsel'); fxSwapSel=null; }
  });
}
function fxResetBracket(){
  if(!confirm('Reset the bracket to the real draw? This clears all your swaps.')) return;
  var fd=new FormData(); fd.append('action','reset_bracket');
  fetch(FX_SELF,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(){ location.reload(); });
}
function fxRoundMatches(name){ for(var i=0;i<FX_ROUNDS.length;i++){ if(FX_ROUNDS[i].round===name) return FX_ROUNDS[i].matches; } return []; }
function fxSplit(name){ var a=fxRoundMatches(name); var half=Math.ceil(a.length/2); return [a.slice(0,half), a.slice(half)]; }
function fxRenderShareImage(){
  var W=1500, H=950;
  var c=document.createElement('canvas'); c.width=W; c.height=H;
  var x=c.getContext('2d');
  var g=x.createLinearGradient(0,0,0,H); g.addColorStop(0,'#071330'); g.addColorStop(1,'#020610');
  x.fillStyle=g; x.fillRect(0,0,W,H);
  x.fillStyle='#FFD24A'; x.fillRect(0,0,W,8);
  x.textAlign='center';
  x.fillStyle='#FFD24A'; x.font='800 26px DM Sans, sans-serif'; x.fillText('FIFA WORLD CUP 2026', W/2, 50);
  x.fillStyle='#fff'; x.font='900 30px Bebas Neue, sans-serif'; x.fillText('PATH TO THE FINAL', W/2, 84);
  x.fillStyle='rgba(255,255,255,.65)'; x.font='700 16px DM Sans, sans-serif';
  x.fillText((FX_CLUB||'').toUpperCase()+(FX_PLACE?(' \u00b7 '+FX_PLACE.toUpperCase()):''), W/2, 110);
  var label='Shared by '+(FX_USER||'Member');
  x.font='800 15px DM Sans, sans-serif';
  var tw=x.measureText(label).width, pw=tw+36;
  x.fillStyle='rgba(255,210,74,.16)';
  if(x.roundRect){x.beginPath();x.roundRect(W/2-pw/2,124,pw,30,15);x.fill();} else {x.fillRect(W/2-pw/2,124,pw,30);}
  x.fillStyle='#FFD24A'; x.fillText(label,W/2,144);
  x.textAlign='left'; x.font='700 15px Bebas Neue, sans-serif'; x.fillStyle='rgba(255,210,74,.6)'; x.fillText('PATHWAY 1',30,178);
  x.textAlign='right'; x.fillText('PATHWAY 2',W-30,178);

  var p1, p2, finalM;
  if (FX_P1 && FX_P1['Round of 32']) {
    // correct FIFA sides (teams from live data)
    p1=[FX_P1['Round of 32'],FX_P1['Round of 16'],FX_P1['Quarter-finals'],FX_P1['Semi-final']];
    p2=[FX_P2['Semi-final'],FX_P2['Quarter-finals'],FX_P2['Round of 16'],FX_P2['Round of 32']];
    finalM=FX_FINAL;
  } else {
    var sR32=fxSplit('Round of 32'), sR16=fxSplit('Round of 16'), sQF=fxSplit('Quarter-finals'), sSF=fxSplit('Semi-finals');
    p1=[sR32[0],sR16[0],sQF[0],sSF[0]];
    p2=[sSF[1],sQF[1],sR16[1],sR32[1]];
    var fin=fxRoundMatches('Final'); finalM=fin.length?fin[0]:null;
  }

  var top=210, bot=H-70, cellW=126, cellH=48;
  var colX=[], marg=72, span=W-2*marg, i, r;
  for(i=0;i<9;i++){ colX[i]=marg+(i+0.5)*span/9; }
  function colY(cnt){ var a=[]; for(var j=0;j<cnt;j++) a.push(top+(j+0.5)*(bot-top)/Math.max(cnt,1)); return a; }
  var p1Y=p1.map(function(col){return colY(col.length);});
  var p2Y=p2.map(function(col){return colY(col.length);});
  var finalY=H/2+40;

  function connect(x1,y1,x2,y2){ var mx=(x1+x2)/2; x.strokeStyle='rgba(255,210,74,.25)'; x.lineWidth=1.5; x.beginPath(); x.moveTo(x1,y1); x.lineTo(mx,y1); x.lineTo(mx,y2); x.lineTo(x2,y2); x.stroke(); }
  for(r=0;r<3;r++){ var cur=p1[r], nxt=p1[r+1]; if(!nxt.length)continue;
    for(i=0;i<cur.length;i++){ var pj=Math.floor(i/2); if(pj<p1Y[r+1].length) connect(colX[r]+cellW/2,p1Y[r][i],colX[r+1]-cellW/2,p1Y[r+1][pj]); } }
  if(p1[3].length&&finalM) connect(colX[3]+cellW/2,p1Y[3][0],colX[4]-cellW/2,finalY);
  for(r=0;r<3;r++){ var ci=3-r, pi=2-r, cCol=5+ci, pCol=5+pi; var curr=p2[ci], nxtt=p2[pi]; if(!nxtt.length)continue;
    for(i=0;i<curr.length;i++){ var pk=Math.floor(i/2); if(pk<p2Y[pi].length) connect(colX[cCol]-cellW/2,p2Y[ci][i],colX[pCol]+cellW/2,p2Y[pi][pk]); } }
  if(p2[0].length&&finalM) connect(colX[5]-cellW/2,p2Y[0][0],colX[4]+cellW/2,finalY);

  function cell(cx,cy,m,big){
    var cw=big?cellW+16:cellW, ch=big?cellH+8:cellH; var X=cx-cw/2, Y=cy-ch/2;
    x.fillStyle=big?'rgba(255,210,74,.1)':'rgba(8,21,46,.96)';
    x.strokeStyle=big?'rgba(255,210,74,.6)':'rgba(255,255,255,.12)'; x.lineWidth=big?2:1.5;
    if(x.roundRect){x.beginPath();x.roundRect(X,Y,cw,ch,8);x.fill();x.stroke();} else {x.fillRect(X,Y,cw,ch);x.strokeRect(X,Y,cw,ch);}
    var rows=[['h',m?m.h:'TBD',m?m.ht:'',m?m.sh:null,m?m.hf:''],['a',m?m.a:'TBD',m?m.at:'',m?m.sa:null,m?m.af:'']];
    rows.forEach(function(rw,ri){
      var ry=Y+(big?18:15)+ri*(big?24:21);
      var sd=rw[0], full=rw[1]||'TBD', tla=rw[2]||'', flag=rw[4]||''; 
      var nm=(flag?flag+' ':'')+(tla||(full.length>12?full.slice(0,11)+'\u2026':full));
      var sc=rw[3]; var winr=(m&&m.w===sd);
      x.textAlign='left'; x.font=(winr?'800 ':'600 ')+(big?'16px':'14px')+' DM Sans, sans-serif';
      x.fillStyle=winr?'#FFD24A':(full==='TBD'?'rgba(255,255,255,.4)':'#e8ecf4'); x.fillText(nm,X+11,ry+4);
      if(sc!==null&&sc!==undefined){ x.textAlign='right'; x.fillStyle=winr?'#FFD24A':'rgba(255,255,255,.72)'; x.font='800 15px DM Sans, sans-serif'; x.fillText(String(sc),X+cw-11,ry+4); }
    });
    x.strokeStyle='rgba(255,255,255,.08)'; x.lineWidth=1; x.beginPath(); x.moveTo(X+6,Y+ch/2); x.lineTo(X+cw-6,Y+ch/2); x.stroke();
  }
  for(r=0;r<4;r++){ for(i=0;i<p1[r].length;i++) cell(colX[r],p1Y[r][i],p1[r][i],false); }
  for(r=0;r<4;r++){ for(i=0;i<p2[r].length;i++) cell(colX[5+r],p2Y[r][i],p2[r][i],false); }
  x.textAlign='center'; x.font='44px serif'; x.fillText('\ud83c\udfc6',colX[4],finalY-46);
  x.font='800 16px Bebas Neue, sans-serif'; x.fillStyle='#FFD24A'; x.fillText('FINAL',colX[4],finalY-28);
  cell(colX[4],finalY,finalM,true);
  var champ=null; if(finalM&&finalM.w){ champ=finalM.w==='h'?finalM.h:finalM.a; }
  if(champ){ x.font='900 22px Bebas Neue, sans-serif'; x.fillStyle='#FFD24A'; x.fillText('CHAMPIONS: '+String(champ).toUpperCase(),colX[4],finalY+66); }
  x.textAlign='center'; x.fillStyle='rgba(255,255,255,.4)'; x.font='600 14px DM Sans, sans-serif'; x.fillText(location.host,W/2,H-20);
  return c;
}

function fxShareBracket(){
  var c;
  try { c=fxRenderShareImage(); } catch(e){ alert('Could not build image'); return; }
  var text=(FX_CLUB||'')+' — ⚽ World Cup 2026 Bracket\nShared by '+(FX_USER||'')+'\n'+location.href;
  c.toBlob(function(blob){
    if(!blob){ alert('Image failed'); return; }
    var file=new File([blob],'wc2026-bracket.png',{type:'image/png'});
    if(navigator.canShare && navigator.canShare({files:[file]})){
      navigator.share({files:[file], text:text}).catch(function(){});
    } else {
      var a=document.createElement('a'); a.href=c.toDataURL('image/png'); a.download='wc2026-bracket.png'; a.click();
      setTimeout(function(){ window.open('https://wa.me/?text='+encodeURIComponent(text),'_blank'); }, 400);
    }
  },'image/png');
}
</script>

<?php require_once __DIR__ . '/../includes/footer.php'; ?>
