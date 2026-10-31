<?php
// sticker_pdf.php — Laser Printer Ready PDF with Cut Marks
// Upload to: public_html/modules/sticker_pdf.php
// Called via AJAX from nameslip.php
// Generates A4 PDF with crop/cut marks for laser cutter / guillotine

require_once __DIR__ . '/../includes/config.php';
requireLogin();

// ── Accept POST data ──────────────────────────────────────────
$slips = json_decode($_POST['slips'] ?? '[]', true);
if (empty($slips)) {
    http_response_code(400);
    echo 'No slip data provided';
    exit;
}

// ── Load TCPDF or fallback to FPDF ────────────────────────────
// We'll use pure PHP FPDF (no composer needed) via CDN download
// Actually use HTML → PDF approach via browser print
// Since we can't install composer, we'll generate an SVG/HTML optimized for PDF

// ── Settings ──────────────────────────────────────────────────
$CLUB     = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
$PLACE    = setting('CLUB_PLACE', 'Vettikkattiri');
$SITE     = rtrim(SITE_URL, '/');

// A4 dimensions in mm
$A4_W     = 210;
$A4_H     = 297;
$MARGIN   = 10;    // mm page margin
$BLEED    = 2;     // mm bleed around each slip
$CUT_LEN  = 5;     // mm cut mark line length
$CUT_GAP  = 1;     // mm gap between slip edge and cut mark
$COLS     = 2;
$ROWS     = 4;     // 2×4 = 8 per page

// Cell size calculation
$cellW = ($A4_W - ($MARGIN * 2)) / $COLS;  // ~95mm each
$cellH = ($A4_H - ($MARGIN * 2)) / $ROWS;  // ~69.25mm each

// Slip size (inside bleed)
$slipW = $cellW - ($BLEED * 2);  // ~91mm
$slipH = $cellH - ($BLEED * 2);  // ~65.25mm

// Logo base64 for embedding
$logoB64 = getLogoB64();

// ── Serve HTML optimized for print-to-PDF ─────────────────────
header('Content-Type: text/html; charset=utf-8');
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>✂️ Laser Cut Sheet — <?= h($CLUB) ?></title>
<link href="https://fonts.googleapis.com/css2?family=Pacifico&family=Fredoka+One&family=Nunito:wght@400;700;800;900&family=Dancing+Script:wght@700&family=Bebas+Neue&family=DM+Sans:wght@400;700;800&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
<style>
/* ═══════════════════════════════════════
   LASER PRINT — STICKER CUT SHEET
   Designed for: A4, 2×4 grid, cut marks
   ═══════════════════════════════════════ */

/* Force exact colors for laser printer */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  -webkit-print-color-adjust: exact !important;
  print-color-adjust: exact !important;
  color-adjust: exact !important;
}

/* Page setup */
@page {
  size: 210mm 297mm;
  margin: 0;
}

html, body {
  width: 210mm;
  background: #fff;
  font-family: 'DM Sans', sans-serif;
}

/* ── Print instruction bar (screen only) ── */
.print-bar {
  background: #0d47a1;
  color: #fff;
  padding: .85rem 1.2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  font-size: .85rem;
}
.print-bar h3 { font-size: 1rem; margin-bottom: .15rem; }
.print-bar p  { opacity: .8; font-size: .75rem; }
.print-bar .btns { display: flex; gap: .5rem; flex-wrap: wrap; }
.print-bar button {
  background: #fff;
  color: #0d47a1;
  border: none;
  padding: .5rem 1.1rem;
  border-radius: 8px;
  font-weight: 800;
  cursor: pointer;
  font-size: .85rem;
  font-family: 'DM Sans', sans-serif;
}
.print-bar button.red { background: #ffebee; color: #b71c1c; }

/* Instructions box */
.instructions {
  background: #e3f2fd;
  border-left: 4px solid #1565c0;
  padding: .65rem 1rem;
  margin: .5rem 0;
  font-size: .78rem;
  color: #0d47a1;
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}
.instructions span { display: flex; align-items: center; gap: .3rem; }

@media print {
  .print-bar, .instructions { display: none !important; }
}

/* ── SHEET ── */
.sheet {
  width: 210mm;
  min-height: 297mm;
  padding: <?= $MARGIN ?>mm;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: repeat(<?= $ROWS ?>, 1fr);
  gap: 0;
  background: #fff;
  position: relative;
}

/* ── CELL — holds cut marks + slip ── */
.cell {
  position: relative;
  width: <?= $cellW ?>mm;
  height: <?= $cellH ?>mm;
  padding: <?= $BLEED ?>mm;
  break-inside: avoid;
  page-break-inside: avoid;
}

/* ── CUT MARKS ── */
/* Each corner has L-shaped cut mark lines */
.cut { position: absolute; z-index: 100; }

/* Top-Left corner */
.cut.tl {
  top: 0; left: 0;
  /* Horizontal line */
  border-top: 0.3mm solid #999;
  width: <?= $CUT_LEN ?>mm;
}
.cut.tl::after {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 0.3mm;
  height: <?= $CUT_LEN ?>mm;
  background: #999;
}

/* Top-Right corner */
.cut.tr {
  top: 0; right: 0;
  border-top: 0.3mm solid #999;
  width: <?= $CUT_LEN ?>mm;
}
.cut.tr::after {
  content: '';
  position: absolute;
  top: 0; right: 0;
  width: 0.3mm;
  height: <?= $CUT_LEN ?>mm;
  background: #999;
}

/* Bottom-Left corner */
.cut.bl {
  bottom: 0; left: 0;
  border-bottom: 0.3mm solid #999;
  width: <?= $CUT_LEN ?>mm;
}
.cut.bl::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0;
  width: 0.3mm;
  height: <?= $CUT_LEN ?>mm;
  background: #999;
}

/* Bottom-Right corner */
.cut.br {
  bottom: 0; right: 0;
  border-bottom: 0.3mm solid #999;
  width: <?= $CUT_LEN ?>mm;
}
.cut.br::after {
  content: '';
  position: absolute;
  bottom: 0; right: 0;
  width: 0.3mm;
  height: <?= $CUT_LEN ?>mm;
  background: #999;
}

/* ── CENTER REGISTRATION MARKS on sheet edges ── */
.reg {
  position: fixed;
  background: #ccc;
  z-index: 200;
}
.reg.top    { top: <?= $MARGIN ?>mm; left: 50%; transform: translateX(-50%); width: 0.3mm; height: 4mm; }
.reg.bottom { bottom: <?= $MARGIN ?>mm; left: 50%; transform: translateX(-50%); width: 0.3mm; height: 4mm; }
.reg.left   { left: <?= $MARGIN ?>mm; top: 50%; transform: translateY(-50%); width: 4mm; height: 0.3mm; }
.reg.right  { right: <?= $MARGIN ?>mm; top: 50%; transform: translateY(-50%); width: 4mm; height: 0.3mm; }

/* ── SLIP inner ── */
.slip-inner {
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: 6px;
}
.slip-inner .slip-wrap {
  width: 100% !important;
  min-width: 0 !important;
  height: 100% !important;
}

/* ── SHEET INFO FOOTER (prints on sheet) ── */
.sheet-footer {
  position: fixed;
  bottom: 3mm;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 6pt;
  color: #666666;
  letter-spacing: .05em;
}
</style>
</head>
<body>

<!-- ── Print instruction bar (hidden on print) ── -->
<div class="print-bar">
  <div>
    <h3>✂️ Laser Cut Sticker Sheet — <?= h($CLUB) ?></h3>
    <p><?= count($slips) ?> slips · A4 · 2×4 grid · Cut marks included</p>
  </div>
  <div class="btns">
    <button onclick="window.print()">🖨️ Send to Printer</button>
    <button class="red" onclick="window.close()">✕ Close</button>
  </div>
</div>

<div class="instructions">
  <span>📋 <strong>Step 1:</strong> Send to laser printer → Save as PDF</span>
  <span>✂️ <strong>Step 2:</strong> Cut along the corner marks</span>
  <span>📚 <strong>Step 3:</strong> Stick on book covers</span>
  <span>⚙️ <strong>Printer:</strong> Enable "Background graphics" for colors</span>
</div>

<!-- ── Sheet with cut marks ── -->
<div class="sheet" id="sheet">

  <!-- Registration marks on sheet edges -->
  <div class="reg top"></div>
  <div class="reg bottom"></div>
  <div class="reg left"></div>
  <div class="reg right"></div>

  <?php foreach ($slips as $i => $slip): ?>
  <div class="cell">
    <!-- Cut marks at each corner -->
    <div class="cut tl"></div>
    <div class="cut tr"></div>
    <div class="cut bl"></div>
    <div class="cut br"></div>

    <!-- Slip content rendered server-side -->
    <div class="slip-inner">
      <?= renderSlip($slip, $logoB64, $CLUB, $SITE) ?>
    </div>
  </div>
  <?php endforeach; ?>

</div>

<!-- Sheet footer (visible on print) -->
<div class="sheet-footer"><?= h($CLUB) ?> · <?= h($PLACE) ?> · <?= date('d M Y') ?> · <?= count($slips) ?> slips</div>

<script>
// Auto-trigger print after fonts load
document.fonts.ready.then(function(){
  // Small delay for images to render
  setTimeout(function(){
    // Don't auto-print — let user review first
  }, 500);
});
</script>
</body>
</html>
<?php

// ── Render a single slip as HTML ──────────────────────────────
function renderSlip($slip, $logoB64, $CLUB, $SITE) {
    $name    = h($slip['name']    ?? 'Student Name');
    $school  = h($slip['school']  ?? '');
    $cls     = h($slip['class']   ?? '');
    $div     = h($slip['div']     ?? '');
    $subj    = h($slip['subject'] ?? 'General');
    $phone   = h($slip['contact'] ?? '');
    $tpl     = (int)($slip['template'] ?? 1);
    $photo   = $slip['photo'] ?? '';  // base64 or URL
    $uid     = (int)($slip['uid'] ?? 0);

    // QR code URL
    $qrData  = $SITE . '/modules/nameslip.php?view=' . $uid;
    $qrSrc   = 'https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=' . urlencode($qrData) . '&margin=4&ecc=M';

    // Photo element
    $photoEl = $photo
        ? '<img src="' . ($photo) . '" style="width:100%;height:100%;object-fit:cover">'
        : '<div style="width:100%;height:100%;background:#e0e0e0;display:flex;align-items:center;justify-content:center;font-size:2rem">👤</div>';

    // Logo
    $logoEl  = $logoB64
        ? '<img src="' . $logoB64 . '" style="width:18px;height:18px;border-radius:50%;object-fit:cover;margin-right:4px;vertical-align:middle">'
        : '';

    // Subject icons
    $subjIcons = ['Math'=>'🔢','English'=>'📚','Science'=>'🔬','Social Science'=>'🌎',
                  'Hindi'=>'🇮🇳','Arabic'=>'☪️','Malayalam'=>'🌴','Computer'=>'💻',
                  'Art'=>'🎨','PE'=>'⚽','General'=>'📖'];
    $icon = $subjIcons[$slip['subject'] ?? ''] ?? '📖';

    // Templates — compact versions optimized for 91×65mm print size
    $templates = [
        1 => renderTpl1($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB),
        2 => renderTpl2($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB),
        3 => renderTpl3($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB),
        4 => renderTpl4($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB),
        5 => renderTpl5($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB),
        6 => renderTpl6($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB),
    ];
    return $templates[$tpl] ?? $templates[1];
}

function slipWrap($bg, $border, $content) {
    return '<div class="slip-wrap" style="width:100%;height:65mm;background:' . $bg . ';border-radius:6px;overflow:hidden;position:relative;border:' . $border . ';font-family:DM Sans,sans-serif">'
         . $content
         . '</div>';
}

function clubBar($logoEl, $CLUB, $color='#555') {
    return '<div style="display:flex;align-items:center;padding:2px 6px;font-size:5.5pt;color:' . $color . ';letter-spacing:.04em;font-weight:700;text-transform:uppercase;opacity:.8">'
         . $logoEl . $CLUB
         . '</div>';
}

function rightContent($name, $nc, $cls, $div, $subj, $icon, $phone, $school, $sc, $qrSrc, $width='54%') {
    return '<div style="position:absolute;right:0;top:0;bottom:0;width:' . $width . ';display:flex;flex-direction:column;justify-content:center;padding:18px 6px 4px 4px">'
        . '<div style="font-size:11pt;font-weight:900;color:' . $nc . ';line-height:1.1;margin-bottom:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' . $name . '</div>'
        . '<div style="font-size:7pt;color:' . $sc . ';margin-bottom:1px">Class ' . $cls . ' &nbsp;·&nbsp; Div. ' . $div . '</div>'
        . '<div style="font-size:7pt;color:' . $sc . ';margin-bottom:1px">Subject &nbsp;' . $subj . ' ' . $icon . '</div>'
        . ($phone ? '<div style="font-size:7pt;color:' . $sc . ';margin-bottom:2px">Phone &nbsp;' . $phone . '</div>' : '')
        . '<div style="display:flex;align-items:flex-end;justify-content:space-between;margin-top:2px">'
        .   '<div style="font-size:6pt;color:' . $sc . ';text-transform:uppercase;letter-spacing:.04em;font-weight:700;line-height:1.3">' . $school . '</div>'
        .   '<img src="' . $qrSrc . '" style="width:40px;height:40px;flex-shrink:0;border-radius:4px">'
        . '</div>'
        . '</div>';
}

function photoCircle($photoEl, $borderColor, $size='80px', $left='6px', $top='calc(50% + 10px)', $transform='translateY(-50%)') {
    return '<div style="position:absolute;left:' . $left . ';top:' . $top . ';transform:' . $transform . ';z-index:4">'
         . '<div style="width:' . $size . ';height:' . $size . ';border-radius:50%;overflow:hidden;border:3px solid ' . $borderColor . ';background:#f0f0f0">'
         . $photoEl
         . '</div></div>';
}

// ── 6 Template renderers ──────────────────────────────────────

function renderTpl1($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB) {
    $c = slipWrap('linear-gradient(135deg,#e3f2fd 0%,#bbdefb 40%,#e8eaf6 100%)','2px solid #1565c0',
        clubBar($logoEl,$CLUB,'#0d47a1')
        . '<div style="position:absolute;top:5px;left:-8px;width:55px;height:48px;border-radius:50%;background:rgba(33,150,243,.12)"></div>'
        . '<div style="position:absolute;bottom:5px;left:-5px;width:42px;height:38px;border-radius:50%;background:rgba(100,181,246,.15)"></div>'
        . photoCircle($photoEl,'#1976d2')
        . rightContent($name,'#0d47a1',$cls,$div,$subj,$icon,$phone,$school,'#1565c0')
    );
    return $c;
}

function renderTpl2($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB) {
    return slipWrap('linear-gradient(135deg,#e8f5e9 0%,#c8e6c9 40%,#f1f8e9 100%)','2px solid #2e7d32',
        clubBar($logoEl,$CLUB,'#1b5e20')
        . '<div style="position:absolute;top:5px;left:-8px;width:55px;height:48px;border-radius:50%;background:rgba(76,175,80,.12)"></div>'
        . '<div style="position:absolute;bottom:5px;left:-5px;width:42px;height:38px;border-radius:50%;background:rgba(129,199,132,.15)"></div>'
        . photoCircle($photoEl,'#2e7d32')
        . rightContent($name,'#1b5e20',$cls,$div,$subj,$icon,$phone,$school,'#2e7d32')
    );
}

function renderTpl3($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB) {
    return slipWrap('linear-gradient(145deg,#1a237e 0%,#283593 50%,#1565c0 100%)','2px solid #7986cb',
        '<div style="position:absolute;top:0;left:0;right:0;height:14px;background:linear-gradient(90deg,rgba(255,193,7,.8),rgba(255,235,59,.6),rgba(255,193,7,.8))"></div>'
        . clubBar($logoEl,$CLUB,'rgba(255,255,255,.7)')
        . '<div style="position:absolute;top:5px;right:10px;font-size:9pt;opacity:.2">⭐</div>'
        . photoCircle($photoEl,'rgba(255,193,7,.8)')
        . rightContent($name,'#fff',$cls,$div,$subj,$icon,$phone,$school,'rgba(255,255,255,.75)')
    );
}

function renderTpl4($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB) {
    return slipWrap('linear-gradient(145deg,#fff9c4 0%,#fff8e1 50%,#fff3e0 100%)','2px solid #f9a825',
        '<div style="position:absolute;top:0;left:0;right:0;height:5px;background:linear-gradient(90deg,#f57f17,#f9a825,#fdd835,#f9a825,#f57f17)"></div>'
        . clubBar($logoEl,$CLUB,'#e65100')
        . '<div style="position:absolute;top:5px;left:-8px;width:55px;height:48px;border-radius:50%;background:rgba(255,193,7,.2)"></div>'
        . '<div style="position:absolute;bottom:5px;right:45px;width:32px;height:28px;border-radius:50%;background:rgba(255,152,0,.15)"></div>'
        . photoCircle($photoEl,'#f9a825')
        . rightContent($name,'#e65100',$cls,$div,$subj,$icon,$phone,$school,'#bf360c')
    );
}

function renderTpl5($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB) {
    return slipWrap('linear-gradient(135deg,#fce4ec 0%,#f8bbd0 40%,#fce4ec 100%)','2.5px solid #e91e63',
        '<div style="position:absolute;top:0;left:0;right:0;height:5px;background:linear-gradient(90deg,#880e4f,#e91e63,#f48fb1,#e91e63,#880e4f)"></div>'
        . clubBar($logoEl,$CLUB,'#880e4f')
        . '<div style="position:absolute;top:5px;left:-8px;width:55px;height:48px;border-radius:50%;background:rgba(233,30,99,.12)"></div>'
        . '<div style="position:absolute;bottom:5px;left:-5px;width:42px;height:38px;border-radius:50%;background:rgba(244,143,177,.2)"></div>'
        . photoCircle($photoEl,'#e91e63')
        . rightContent($name,'#880e4f',$cls,$div,$subj,$icon,$phone,$school,'#c2185b')
    );
}

function renderTpl6($name,$school,$cls,$div,$subj,$icon,$phone,$photoEl,$logoEl,$qrSrc,$CLUB) {
    return slipWrap('linear-gradient(135deg,#e8f5e9 0%,#f1f8e9 50%,#fff8e1 100%)','2.5px solid #2e7d32',
        '<div style="position:absolute;top:0;left:0;right:0;height:7px;background:linear-gradient(90deg,#1b5e20,#2e7d32,#43a047,#66bb6a,#2e7d32,#1b5e20)"></div>'
        . clubBar($logoEl,$CLUB,'#1b5e20')
        . '<div style="position:absolute;top:10px;right:8px;font-size:9pt;opacity:.3">☪️</div>'
        . '<div style="position:absolute;top:5px;left:-8px;width:55px;height:48px;border-radius:50%;background:rgba(46,125,50,.1)"></div>'
        . photoCircle($photoEl,'#2e7d32')
        . rightContent($name,'#1b5e20',$cls,$div,$subj,$icon,$phone,$school,'#2e7d32')
    );
}
