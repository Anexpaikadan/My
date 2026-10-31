<?php
// ============================================================
// modules/broadcast.php — WhatsApp Broadcast (Group Mode)
// Aishwarya Arts & Sports Club — PHP 7.3+ compatible
// ============================================================
require_once __DIR__ . '/../includes/config.php';
// OG tags before requireLogin
$pageOG = [
  'title' => '📢 Broadcast — ' . setting('CLUB_NAME','Aishwarya Arts & Sports Club'),
  'desc'  => 'Send WhatsApp announcements to all club members',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/broadcast.php',
];
requireLogin();
$me      = currentUser();
$isAdmin = isAdminRole($me['role']) || canPost($me['role']);
if (!$isAdmin) {
    header('Location: ' . url('dashboard.php')); exit;
}

$CLUB  = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
$PLACE = setting('CLUB_PLACE', 'Vettikkattiri');
$GROUP = setting('CLUB_WA_GROUP', '');

// ── Create broadcast history table ───────────────────────────
try { db()->exec("CREATE TABLE IF NOT EXISTS broadcast_history (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    message     TEXT NOT NULL,
    category    VARCHAR(50) DEFAULT 'general',
    sent_by     INT NOT NULL,
    sent_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)"); } catch(Exception $e){}

// ── Save broadcast to history ─────────────────────────────────
$msg_flash = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['save_broadcast'])) {
    $title   = trim($_POST['broadcast_title'] ?? '');
    $message = trim($_POST['broadcast_msg']   ?? '');
    $cat     = $_POST['broadcast_cat'] ?? 'general';
    if ($title && $message) {
        db()->prepare("INSERT INTO broadcast_history(title,message,category,sent_by) VALUES(?,?,?,?)")
           ->execute([$title, $message, $cat, $me['id']]);
        $msg_flash = ['ok', '✅ Broadcast saved to history!'];
    }
}

// ── Load history ──────────────────────────────────────────────
$history = db()->query("SELECT bh.*, u.name sender FROM broadcast_history bh
    LEFT JOIN users u ON u.id = bh.sent_by
    ORDER BY bh.sent_at DESC LIMIT 30")->fetchAll();

// ── Member stats ──────────────────────────────────────────────
$stats = db()->query("SELECT
    COUNT(*) total,
    SUM(status='active') active,
    SUM(whatsapp_number IS NOT NULL AND whatsapp_number != '') has_wa
    FROM users WHERE status='active'")->fetch();

$pageTitle = '📢 WhatsApp Broadcast — ' . $CLUB;
require_once __DIR__ . '/../includes/header.php';
?>

<style>
/* ── Broadcast Page Styles ── */
.bc-wrap { max-width: 560px; margin: 0 auto; padding: 0 0 3rem; }

/* Hero */
.bc-hero {
    background: linear-gradient(135deg, #075e54 0%, #128c7e 50%, #25d366 100%);
    padding: 1.8rem 1.2rem 1.4rem;
    text-align: center;
    color: #fff;
    position: relative;
    overflow: hidden;
}
.bc-hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(ellipse at 80% 20%, rgba(255,255,255,.12), transparent 60%);
}
.bc-hero-icon { font-size: 2.8rem; display: block; margin-bottom: .4rem; position: relative; z-index: 1; }
.bc-hero h1 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.7rem;
    letter-spacing: .1em;
    color: #fff;
    position: relative;
    z-index: 1;
    margin-bottom: .2rem;
}
.bc-hero p { font-size: .78rem; color: rgba(255,255,255,.75); position: relative; z-index: 1; }

/* Stats bar */
.bc-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    background: #075e54;
    border-bottom: 3px solid #25d366;
}
.bc-stat { padding: .7rem .5rem; text-align: center; border-right: 1px solid rgba(255,255,255,.1); }
.bc-stat:last-child { border-right: none; }
.bc-stat-n { font-family: 'Bebas Neue', sans-serif; font-size: 1.5rem; color: #25d366; line-height: 1; }
.bc-stat-l { font-size: .55rem; color: rgba(255,255,255,.5); text-transform: uppercase; letter-spacing: .08em; margin-top: .1rem; }

/* Main card */
.bc-card {
    background: #fff;
    margin: .9rem;
    border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,.08);
    border: 1px solid #e8ecf4;
    overflow: hidden;
}
.bc-card-head {
    background: linear-gradient(135deg, #075e54, #128c7e);
    padding: .9rem 1.1rem;
    display: flex;
    align-items: center;
    gap: .6rem;
}
.bc-card-head h3 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.1rem;
    letter-spacing: .08em;
    color: #fff;
    margin: 0;
}
.bc-card-body { padding: 1.1rem; }

/* Template buttons */
.tmpl-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin-bottom: 1rem; }
.tmpl-btn {
    padding: .6rem .7rem;
    border: 1.5px solid #e8ecf4;
    border-radius: 10px;
    background: #f8fafc;
    cursor: pointer;
    text-align: left;
    transition: all .2s;
    font-family: 'DM Sans', sans-serif;
}
.tmpl-btn:hover { border-color: #25d366; background: #f0fdf4; }
.tmpl-btn:active { transform: scale(.97); }
.tmpl-em { font-size: 1.2rem; display: block; margin-bottom: .2rem; }
.tmpl-lbl { font-size: .72rem; font-weight: 700; color: #075e54; }
.tmpl-sub { font-size: .62rem; color: #94a3b8; }

/* Form */
.bc-label {
    font-size: .7rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #3d4f7c;
    display: block;
    margin-bottom: .35rem;
}
.bc-inp {
    width: 100%;
    padding: .72rem .9rem;
    border: 2px solid #e8ecf4;
    border-radius: 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: .9rem;
    color: #0d1b3e;
    background: #fff;
    outline: none;
    transition: border-color .18s;
    -webkit-appearance: none;
}
.bc-inp:focus { border-color: #25d366; box-shadow: 0 0 0 3px rgba(37,211,102,.1); }
.bc-textarea {
    width: 100%;
    padding: .72rem .9rem;
    border: 2px solid #e8ecf4;
    border-radius: 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: .88rem;
    color: #0d1b3e;
    background: #fff;
    outline: none;
    resize: vertical;
    min-height: 140px;
    transition: border-color .18s;
    line-height: 1.6;
}
.bc-textarea:focus { border-color: #25d366; box-shadow: 0 0 0 3px rgba(37,211,102,.1); }

/* Preview box */
.preview-box {
    background: #e9feee;
    border: 1.5px solid #25d366;
    border-radius: 12px;
    padding: .85rem 1rem;
    margin: .75rem 0;
    min-height: 60px;
    font-family: 'DM Sans', sans-serif;
    font-size: .82rem;
    color: #0d1b3e;
    line-height: 1.65;
    white-space: pre-wrap;
    word-break: break-word;
    position: relative;
}
.preview-label {
    font-size: .6rem;
    font-weight: 800;
    color: #25d366;
    letter-spacing: .1em;
    text-transform: uppercase;
    margin-bottom: .5rem;
    display: flex;
    align-items: center;
    gap: .4rem;
}
.preview-label::before {
    content: '';
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #25d366;
    display: inline-block;
    animation: pulse-dot 1.5s ease-in-out infinite;
}
@keyframes pulse-dot { 0%,100%{opacity:1}50%{opacity:.3} }

/* Character count */
.char-count {
    font-size: .65rem;
    color: #94a3b8;
    text-align: right;
    margin-top: .25rem;
}
.char-count.warn { color: #f59e0b; }
.char-count.over { color: #ef4444; }

/* Send button */
.btn-send-wa {
    width: 100%;
    padding: .85rem;
    background: linear-gradient(135deg, #25d366, #128c7e);
    color: #fff;
    border: none;
    border-radius: 12px;
    font-family: 'DM Sans', sans-serif;
    font-size: .95rem;
    font-weight: 800;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: .6rem;
    box-shadow: 0 4px 18px rgba(37,211,102,.35);
    transition: all .2s;
    letter-spacing: .03em;
    margin-top: .75rem;
    text-decoration: none;
}
.btn-send-wa:active { transform: scale(.97); }
.btn-save {
    width: 100%;
    padding: .7rem;
    background: #f0f4fa;
    color: #3d4f7c;
    border: 1.5px solid #e8ecf4;
    border-radius: 10px;
    font-family: 'DM Sans', sans-serif;
    font-size: .85rem;
    font-weight: 700;
    cursor: pointer;
    margin-top: .5rem;
    transition: all .2s;
}
.btn-save:hover { background: #e3f2fd; border-color: #90caf9; color: #0d47a1; }

/* Group missing warning */
.group-warn {
    background: #fff8e1;
    border: 1.5px solid #ffc107;
    border-radius: 10px;
    padding: .75rem 1rem;
    font-size: .82rem;
    color: #856404;
    display: flex;
    align-items: flex-start;
    gap: .6rem;
    margin-bottom: .8rem;
}

/* Category select */
.cat-pills { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: .9rem; }
.cat-pill {
    padding: .3rem .8rem;
    border-radius: 20px;
    border: 1.5px solid #e8ecf4;
    background: #f8fafc;
    font-size: .72rem;
    font-weight: 700;
    cursor: pointer;
    transition: all .18s;
    color: #64748b;
}
.cat-pill.on { border-color: #25d366; background: #f0fdf4; color: #075e54; }

/* History */
.hist-item {
    background: #f8fafc;
    border: 1px solid #e8ecf4;
    border-radius: 12px;
    padding: .75rem .9rem;
    margin-bottom: .5rem;
    cursor: pointer;
    transition: all .2s;
}
.hist-item:hover { border-color: #25d366; background: #f0fdf4; }
.hist-item:active { transform: scale(.98); }
.hist-title { font-size: .85rem; font-weight: 800; color: #0d1b3e; margin-bottom: .2rem; }
.hist-meta { font-size: .65rem; color: #94a3b8; display: flex; gap: .6rem; flex-wrap: wrap; }
.hist-cat {
    display: inline-block;
    padding: .08rem .45rem;
    border-radius: 20px;
    font-size: .6rem;
    font-weight: 700;
}
.hist-preview {
    font-size: .75rem;
    color: #64748b;
    margin-top: .3rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    line-height: 1.5;
}
.reuse-btn {
    display: inline-block;
    margin-top: .35rem;
    font-size: .68rem;
    font-weight: 700;
    color: #25d366;
    background: #f0fdf4;
    border: 1px solid #25d366;
    border-radius: 6px;
    padding: .18rem .55rem;
    cursor: pointer;
}
</style>

<div class="bc-wrap">

<!-- Hero -->
<div class="bc-hero">
    <span class="bc-hero-icon">📢</span>
    <h1>WhatsApp Broadcast</h1>
    <p><?= h($CLUB) ?> · <?= h($PLACE) ?></p>
</div>

<!-- Stats -->
<div class="bc-stats">
    <div class="bc-stat">
        <div class="bc-stat-n"><?= (int)$stats['active'] ?></div>
        <div class="bc-stat-l">Members</div>
    </div>
    <div class="bc-stat">
        <div class="bc-stat-n"><?= (int)$stats['has_wa'] ?></div>
        <div class="bc-stat-l">On WhatsApp</div>
    </div>
    <div class="bc-stat">
        <div class="bc-stat-n"><?= count($history) ?></div>
        <div class="bc-stat-l">Broadcasts</div>
    </div>
</div>

<?php if ($msg_flash): ?>
<div style="margin:.7rem .9rem 0">
    <div class="alert alert-<?= $msg_flash[0] === 'ok' ? 'ok' : 'err' ?>"><?= $msg_flash[1] ?></div>
</div>
<?php endif; ?>

<!-- Compose Card -->
<div class="bc-card">
    <div class="bc-card-head">
        <span style="font-size:1.2rem">✍️</span>
        <h3>Compose Message</h3>
    </div>
    <div class="bc-card-body">

        <!-- Group warning -->
        <?php if (!$GROUP || strpos($GROUP, 'YOUR_GROUP') !== false): ?>
        <div class="group-warn">
            <span style="font-size:1.1rem;flex-shrink:0">⚠️</span>
            <div>
                <strong>Club WhatsApp Group not set!</strong><br>
                Go to <a href="<?= url('modules/settings.php') ?>" style="color:#856404;font-weight:700">Club Settings</a> and add your WhatsApp Group link to use broadcast.
            </div>
        </div>
        <?php endif; ?>

        <!-- Quick templates -->
        <label class="bc-label">Quick Templates</label>
        <div class="tmpl-grid">
            <button class="tmpl-btn" onclick="useTemplate('event')">
                <span class="tmpl-em">📅</span>
                <span class="tmpl-lbl">Event Notice</span>
                <span class="tmpl-sub">Upcoming event</span>
            </button>
            <button class="tmpl-btn" onclick="useTemplate('meeting')">
                <span class="tmpl-em">🤝</span>
                <span class="tmpl-lbl">Meeting</span>
                <span class="tmpl-sub">Club meeting</span>
            </button>
            <button class="tmpl-btn" onclick="useTemplate('urgent')">
                <span class="tmpl-em">🚨</span>
                <span class="tmpl-lbl">Urgent Notice</span>
                <span class="tmpl-sub">Important alert</span>
            </button>
            <button class="tmpl-btn" onclick="useTemplate('congratulations')">
                <span class="tmpl-em">🏆</span>
                <span class="tmpl-lbl">Congratulations</span>
                <span class="tmpl-sub">Achievement</span>
            </button>
            <button class="tmpl-btn" onclick="useTemplate('fundraiser')">
                <span class="tmpl-em">❤️</span>
                <span class="tmpl-lbl">Fundraiser</span>
                <span class="tmpl-sub">Donation appeal</span>
            </button>
            <button class="tmpl-btn" onclick="useTemplate('eid')">
                <span class="tmpl-em">🌙</span>
                <span class="tmpl-lbl">Eid / Festival</span>
                <span class="tmpl-sub">Greetings</span>
            </button>
            <button class="tmpl-btn" onclick="useTemplate('blood')">
                <span class="tmpl-em">🩸</span>
                <span class="tmpl-lbl">Blood Needed</span>
                <span class="tmpl-sub">Urgent request</span>
            </button>
            <button class="tmpl-btn" onclick="useTemplate('blank')">
                <span class="tmpl-em">✏️</span>
                <span class="tmpl-lbl">Blank</span>
                <span class="tmpl-sub">Write your own</span>
            </button>
        </div>

        <!-- Category -->
        <label class="bc-label">Category</label>
        <div class="cat-pills" id="catPills">
            <?php
            $cats = ['general'=>['📢','General','#64748b','#f1f5f9'],
                     'event'=>['📅','Event','#0d47a1','#e3f2fd'],
                     'urgent'=>['🚨','Urgent','#b71c1c','#ffebee'],
                     'meeting'=>['🤝','Meeting','#1b5e20','#e8f5e9'],
                     'fundraiser'=>['❤️','Fundraiser','#880e4f','#fce4ec'],
                     'congratulations'=>['🏆','Achievement','#e65100','#fff3e0']];
            foreach($cats as $k=>$v):
            ?>
            <div class="cat-pill" id="cat_<?= $k ?>"
                 data-cat="<?= $k ?>" data-color="<?= $v[2] ?>" data-bg="<?= $v[3] ?>"
                 onclick="selectCat('<?= $k ?>')">
                <?= $v[0] ?> <?= $v[1] ?>
            </div>
            <?php endforeach; ?>
        </div>
        <input type="hidden" id="selectedCat" value="general">

        <!-- Title -->
        <div style="margin-bottom:.75rem">
            <label class="bc-label">Broadcast Title (for your records)</label>
            <input type="text" class="bc-inp" id="bcTitle" placeholder="e.g. Eid Mubarak Wishes">
        </div>

        <!-- Extra fields panel -->
        <div id="extraFields" style="display:none;margin-bottom:.75rem">
          <div style="background:#f0f9ff;border:1.5px solid #90caf9;border-radius:12px;padding:.85rem">
            <div style="font-size:.65rem;font-weight:800;color:#0d47a1;letter-spacing:.08em;text-transform:uppercase;margin-bottom:.6rem">📝 Fill In Details</div>
            <div id="fieldSlots" style="display:flex;flex-direction:column;gap:.45rem"></div>
            <button type="button" onclick="injectFields()" style="width:100%;margin-top:.65rem;padding:.6rem;background:#0d47a1;color:#fff;border:none;border-radius:9px;font-family:'DM Sans',sans-serif;font-weight:700;font-size:.84rem;cursor:pointer">✅ Apply to Message</button>
          </div>
        </div>

        <!-- Message -->
        <div style="margin-bottom:.5rem">
            <label class="bc-label">Message</label>
            <textarea class="bc-textarea" id="bcMsg" placeholder="Type your message here..."
                oninput="updatePreview();updateCount()"></textarea>
            <div class="char-count" id="charCount">0 / 1000 characters</div>
        </div>

        <!-- Live Preview -->
        <div class="preview-label">
            <span>WhatsApp Preview</span>
        </div>
        <div class="preview-box" id="previewBox">
            Your message will appear here...
        </div>

        <!-- Send Button -->
        <?php if ($GROUP && strpos($GROUP, 'YOUR_GROUP') === false): ?>
        <a id="sendBtn" href="#" class="btn-send-wa" onclick="sendBroadcast(event)">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="white">
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
            </svg>
            Send to Club Group
        </a>
        <?php else: ?>
        <button class="btn-send-wa" onclick="alert('Please set Club WhatsApp Group URL in Club Settings first.')" style="opacity:.6">
            📤 Send to Club Group
        </button>
        <?php endif; ?>

        <!-- Save to history -->
        <form method="POST" onsubmit="return saveBroadcast(event)">
            <input type="hidden" name="save_broadcast" value="1">
            <input type="hidden" name="broadcast_title" id="hidTitle">
            <input type="hidden" name="broadcast_msg"   id="hidMsg">
            <input type="hidden" name="broadcast_cat"   id="hidCat">
            <button type="submit" class="btn-save">💾 Save to History</button>
        </form>

    </div>
</div>

<!-- Broadcast History -->
<?php if (!empty($history)): ?>
<div class="bc-card">
    <div class="bc-card-head">
        <span style="font-size:1.2rem">📋</span>
        <h3>Broadcast History</h3>
    </div>
    <div class="bc-card-body">
        <?php
        $catColors = ['general'=>['#64748b','#f1f5f9'],'event'=>['#0d47a1','#e3f2fd'],
                      'urgent'=>['#b71c1c','#ffebee'],'meeting'=>['#1b5e20','#e8f5e9'],
                      'fundraiser'=>['#880e4f','#fce4ec'],'congratulations'=>['#e65100','#fff3e0']];
        foreach($history as $h):
            $cc = $catColors[$h['category']] ?? ['#64748b','#f1f5f9'];
        ?>
        <div class="hist-item" onclick="reuseMessage(<?= htmlspecialchars(json_encode($h['title'])) ?>, <?= htmlspecialchars(json_encode($h['message'])) ?>, '<?= h($h['category']) ?>')">
            <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:.5rem">
                <div style="flex:1;min-width:0">
                    <div class="hist-title"><?= h($h['title']) ?></div>
                    <div class="hist-meta">
                        <span>👤 <?= h($h['sender'] ?? 'Admin') ?></span>
                        <span>🕐 <?= date('d M Y H:i', strtotime($h['sent_at'])) ?></span>
                        <span class="hist-cat" style="background:<?= $cc[1] ?>;color:<?= $cc[0] ?>"><?= ucfirst($h['category']) ?></span>
                    </div>
                    <div class="hist-preview"><?= h($h['message']) ?></div>
                </div>
            </div>
            <span class="reuse-btn">♻️ Reuse</span>
        </div>
        <?php endforeach; ?>
    </div>
</div>
<?php endif; ?>

</div><!-- end .bc-wrap -->

<script>
var CLUB  = <?= json_encode($CLUB) ?>;
var PLACE = <?= json_encode($PLACE) ?>;
var GROUP = <?= json_encode($GROUP) ?>;
var selectedCat = 'general';

// ── Templates ──────────────────────────────────────────────
var templates = {
    event: {
        title: 'Event Notice',
        msg: '📅 *' + CLUB + '*\n📍 ' + PLACE + '\n━━━━━━━━━━━━━━━━━━━\n\n🎉 *Upcoming Event*\n\n[Event Name]\n\n📅 *Date:* [Date]\n📍 *Venue:* [Venue]\n⏰ *Time:* [Time]\n\n✅ All members are invited!\n\n━━━━━━━━━━━━━━━━━━━\n' + CLUB
    },
    meeting: {
        title: 'Club Meeting',
        msg: '🤝 *' + CLUB + '*\n📍 ' + PLACE + '\n━━━━━━━━━━━━━━━━━━━\n\n📋 *Club Meeting Notice*\n\n📅 *Date:* [Date]\n📍 *Venue:* [Venue]\n⏰ *Time:* [Time]\n\n*Agenda:*\n• [Point 1]\n• [Point 2]\n• [Point 3]\n\n🙏 Please attend on time.\n\n━━━━━━━━━━━━━━━━━━━\n' + CLUB
    },
    urgent: {
        title: 'Urgent Notice',
        msg: '🚨 *URGENT — ' + CLUB + '*\n📍 ' + PLACE + '\n━━━━━━━━━━━━━━━━━━━\n\n⚠️ *Important Notice*\n\n[Your urgent message here]\n\nPlease read and share with all members.\n\n━━━━━━━━━━━━━━━━━━━\n' + CLUB
    },
    congratulations: {
        title: 'Congratulations',
        msg: '🏆 *' + CLUB + '*\n📍 ' + PLACE + '\n━━━━━━━━━━━━━━━━━━━\n\n🎉 *Congratulations!*\n\nWe are proud to announce that\n\n*[Member Name]*\n\nhas achieved *[Achievement]*\n\n👏 Congratulations on this wonderful achievement!\n\n━━━━━━━━━━━━━━━━━━━\n' + CLUB
    },
    fundraiser: {
        title: 'Fundraiser Appeal',
        msg: '❤️ *' + CLUB + '*\n📍 ' + PLACE + '\n━━━━━━━━━━━━━━━━━━━\n\n🙏 *Appeal for Support*\n\n[Description of the cause]\n\n💰 *Target Amount:* ₹[Amount]\n🏦 *UPI ID:* [UPI ID]\n\nEvery contribution matters. May Allah reward your generosity.\n\n━━━━━━━━━━━━━━━━━━━\n' + CLUB
    },
    eid: {
        title: 'Eid / Festival Greetings',
        msg: '🌙 *' + CLUB + '*\n📍 ' + PLACE + '\n━━━━━━━━━━━━━━━━━━━\n\n✨ *Eid Mubarak!*\n\nWishing all our members and families a blessed Eid filled with joy, peace and happiness.\n\n🤲 May Allah accept our prayers and good deeds.\n\nEid Mubarak! 🌙⭐\n\n━━━━━━━━━━━━━━━━━━━\n' + CLUB
    },
    blood: {
        title: 'Blood Donation Request',
        msg: '🩸 *URGENT — ' + CLUB + '*\n📍 ' + PLACE + '\n━━━━━━━━━━━━━━━━━━━\n\n🆘 *Blood Required*\n\n*Blood Group:* [Group]\n*Patient:* [Name]\n*Hospital:* [Hospital Name]\n*Units Needed:* [Number]\n\n📞 Contact: [Phone Number]\n\n🙏 Please share with your contacts.\nYour blood can save a life!\n\n━━━━━━━━━━━━━━━━━━━\n' + CLUB
    },
    blank: {
        title: '',
        msg: '📢 *' + CLUB + '*\n📍 ' + PLACE + '\n━━━━━━━━━━━━━━━━━━━\n\n'
    }
};

var templateFields = {
    event:           ['Event Name','Date','Venue','Time'],
    meeting:         ['Date','Venue','Time','Agenda Item 1','Agenda Item 2'],
    urgent:          ['Your Message'],
    congratulations: ['Member Name','Achievement'],
    fundraiser:      ['Cause Description','Target Amount','UPI ID','Contact Number'],
    blood:           ['Blood Group','Patient Name','Hospital Name','Units Needed','Contact Number'],
    eid:[], blank:[]
};
var catMap = {event:'event',meeting:'meeting',urgent:'urgent',
    congratulations:'congratulations',fundraiser:'fundraiser',
    eid:'general',blood:'urgent',blank:'general'};

function useTemplate(key) {
    var t = templates[key];
    document.getElementById('bcTitle').value = t.title;
    document.getElementById('bcMsg').value   = t.msg;
    // Show fill-in fields
    var fields = templateFields[key] || [];
    var ef = document.getElementById('extraFields');
    var fs = document.getElementById('fieldSlots');
    if (fields.length) {
        fs.innerHTML = '';
        fields.forEach(function(f,i) {
            fs.innerHTML += '<div><label style="font-size:.63rem;font-weight:700;color:#3d4f7c;display:block;margin-bottom:.18rem">'+f+'</label>'
                +'<input type="text" id="ef_'+i+'" placeholder="Enter '+f+'"'
                +' style="width:100%;padding:.5rem .75rem;border:1.5px solid #e8ecf4;border-radius:8px;font-family:DM Sans,sans-serif;font-size:.84rem;outline:none">'
                +'</div>';
        });
        ef.setAttribute('data-fields', JSON.stringify(fields));
        ef.style.display = 'block';
    } else {
        ef.style.display = 'none';
    }
    if (catMap[key]) selectCat(catMap[key]);
    updatePreview();
    updateCount();
    document.getElementById('bcMsg').scrollIntoView({behavior:'smooth',block:'center'});
}

function injectFields() {
    var ef     = document.getElementById('extraFields');
    var fields = JSON.parse(ef.getAttribute('data-fields') || '[]');
    var msg    = document.getElementById('bcMsg').value;
    fields.forEach(function(f,i) {
        var val = (document.getElementById('ef_'+i).value || '').trim();
        if (val) {
            var ph = '[' + f + ']';
            msg = msg.split(ph).join(val);
            ph  = '[' + f.split(' ')[0] + ']';
            msg = msg.split(ph).join(val);
        }
    });
    document.getElementById('bcMsg').value = msg;
    updatePreview(); updateCount();
    ef.style.display = 'none';
}

function updatePreview() {
    var msg = document.getElementById('bcMsg').value;
    var box = document.getElementById('previewBox');
    if (!msg.trim()) {
        box.textContent = 'Your message will appear here...';
        box.style.color = '#94a3b8';
        return;
    }
    box.style.color = '#0d1b3e';
    // Render *bold* as bold
    box.innerHTML = msg
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/\*(.*?)\*/g,'<strong>$1</strong>')
        .replace(/\n/g,'<br>');
}

function updateCount() {
    var len = document.getElementById('bcMsg').value.length;
    var el  = document.getElementById('charCount');
    el.textContent = len + ' / 1000 characters';
    el.className = 'char-count' + (len > 900 ? ' over' : len > 700 ? ' warn' : '');
}

function selectCat(cat) {
    selectedCat = cat;
    document.getElementById('selectedCat').value = cat;
    document.querySelectorAll('.cat-pill').forEach(function(p) {
        p.classList.remove('on');
        p.style.borderColor = '#e8ecf4';
        p.style.background  = '#f8fafc';
        p.style.color       = '#64748b';
    });
    var el = document.getElementById('cat_' + cat);
    if (el) {
        el.classList.add('on');
        el.style.borderColor = el.getAttribute('data-color');
        el.style.background  = el.getAttribute('data-bg');
        el.style.color       = el.getAttribute('data-color');
    }
}

function sendBroadcast(e) {
    e.preventDefault();
    var msg = document.getElementById('bcMsg').value.trim();
    if (!msg) { alert('Please write a message first!'); return; }
    if (!GROUP || GROUP.indexOf('YOUR_GROUP') >= 0) {
        alert('Please set Club WhatsApp Group URL in Club Settings first.');
        return;
    }
    // Add website link if not present
    if (msg.indexOf('mynamecc.online') < 0) {
        msg += '\n\n🌐 https://mynamecc.online';
        document.getElementById('bcMsg').value = msg;
        updatePreview();
    }
    // Copy message to clipboard then open group
    if (navigator.clipboard) {
        navigator.clipboard.writeText(msg).then(function() {
            showToast('✅ Message copied! Opening group...');
            setTimeout(function() { window.open(GROUP, '_blank'); }, 600);
        }).catch(function() {
            window.open(GROUP, '_blank');
        });
    } else {
        // Fallback
        var ta = document.createElement('textarea');
        ta.value = msg;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.focus(); ta.select();
        try { document.execCommand('copy'); } catch(e){}
        document.body.removeChild(ta);
        showToast('✅ Message copied! Opening group...');
        setTimeout(function() { window.open(GROUP, '_blank'); }, 600);
    }
}

function saveBroadcast(e) {
    var title = document.getElementById('bcTitle').value.trim();
    var msg   = document.getElementById('bcMsg').value.trim();
    if (!title || !msg) {
        e.preventDefault();
        alert('Please fill in the title and message first!');
        return false;
    }
    document.getElementById('hidTitle').value = title;
    document.getElementById('hidMsg').value   = msg;
    document.getElementById('hidCat').value   = selectedCat;
    return true;
}

function reuseMessage(title, msg, cat) {
    document.getElementById('bcTitle').value = title;
    document.getElementById('bcMsg').value   = msg;
    selectedCat = cat;
    // Activate category pill
    document.querySelectorAll('.cat-pill').forEach(function(p) {
        if (p.getAttribute('data-cat') === cat) {
            selectCat(cat, p);
        }
    });
    updatePreview();
    updateCount();
    window.scrollTo({ top: 0, behavior: 'smooth' });
    document.getElementById('bcMsg').focus();
}

// Toast
function showToast(msg) {
    var t = document.getElementById('bcToast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'bcToast';
        t.style.cssText = 'position:fixed;bottom:1.5rem;left:50%;transform:translateX(-50%);background:#075e54;color:#fff;padding:.65rem 1.3rem;border-radius:25px;font-size:.82rem;font-weight:700;z-index:9999;box-shadow:0 4px 16px rgba(7,94,84,.4);transition:opacity .3s;white-space:nowrap';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = '1';
    setTimeout(function() { t.style.opacity = '0'; }, 2500);
}

// Init
selectCat('general');
updatePreview();
updateCount();
</script>

<?php require_once __DIR__ . '/../includes/footer.php'; ?>
