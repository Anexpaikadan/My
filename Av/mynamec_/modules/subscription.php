<?php
// ============================================================
//  modules/subscription.php
//  Member Subscription Request, Payment Tracking & Status
// ============================================================
require_once __DIR__.'/../includes/config.php';
// Fees come from Club Settings → Fees (fallback: config.php)
$feeMonthly = max(0,(int)setting('FEE_MONTHLY', FEE_MONTHLY));
$feeAnnual  = max(0,(int)setting('FEE_ANNUAL',  FEE_ANNUAL));
// OG tags — must be set BEFORE requireLogin() so bots get logo+title
$pageOG = [
  'title' => '💳 Subscription — Aishwarya Arts & Sports Club',
  'desc'  => 'Membership subscription — AASC, Kerala',
  'image' => 'https://mynamecc.online/og_image.php',
  'url'   => 'https://mynamecc.online/modules/subscription.php',
];
requireLogin();
$me  = currentUser();
$msg = '';

// ── Member submits a new subscription request ────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['req_sub'])) {
    $plan   = $_POST['plan_type'] === 'monthly' ? 'monthly' : 'annual';
    $amount = $plan === 'annual' ? $feeAnnual : $feeMonthly;
    $paid   = floatval($_POST['initial_payment'] ?? 0);
    $paid   = max(0, min($paid, $amount));
    $method = $_POST['payment_method'] ?? 'cash';
    $upi    = trim($_POST['upi_ref'] ?? '');
    $notes  = trim($_POST['notes']   ?? '');

    // Check for existing pending request
    $existing = db()->prepare("SELECT id FROM subscription_requests WHERE user_id=? AND status IN('pending','partial')");
    $existing->execute([$me['id']]);
    if ($existing->fetch()) {
        $msg = ['t'=>'warn','m'=>'You already have a pending subscription request. Please wait for admin approval.'];
    } else {
        $status = ($paid >= $amount) ? 'pending' : ($paid > 0 ? 'partial' : 'pending');
        $stmt = db()->prepare("INSERT INTO subscription_requests
            (user_id,plan_type,amount_due,amount_paid,payment_method,upi_ref,status,notes)
            VALUES(?,?,?,?,?,?,?,?)");
        $stmt->execute([$me['id'],$plan,$amount,$paid,$method,$upi,$status,$notes]);
        $reqId = db()->lastInsertId();

        // Record initial payment if any
        if ($paid > 0) {
            db()->prepare("INSERT INTO subscription_payments(request_id,user_id,amount,payment_method,upi_ref,recorded_by,notes)VALUES(?,?,?,?,?,?,?)")
               ->execute([$reqId,$me['id'],$paid,$method,$upi,$me['id'],'Initial payment on request']);
        }

        // Notify secretary via WhatsApp link (generated)
        $msg = ['t'=>'ok','m'=>'✅ Subscription request submitted! The Secretary will review and approve it shortly.'];
    }
}

// ── Member adds a partial/balance payment ───────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['pay_balance'])) {
    $reqId  = (int)$_POST['req_id'];
    $amount = floatval($_POST['pay_amount']);
    $method = $_POST['pay_method'] ?? 'cash';
    $upi    = trim($_POST['pay_upi'] ?? '');

    // Verify this request belongs to this member
    $req = db()->prepare("SELECT * FROM subscription_requests WHERE id=? AND user_id=?");
    $req->execute([$reqId, $me['id']]);
    $reqRow = $req->fetch();

    if (!$reqRow) {
        $msg = ['t'=>'err','m'=>'Invalid request.'];
    } elseif ($reqRow['status'] === 'approved') {
        $msg = ['t'=>'warn','m'=>'This subscription is already fully approved.'];
    } else {
        $newPaid  = $reqRow['amount_paid'] + $amount;
        $newPaid  = min($newPaid, $reqRow['amount_due']);
        $newStatus= ($newPaid >= $reqRow['amount_due']) ? 'pending' : 'partial';

        db()->prepare("UPDATE subscription_requests SET amount_paid=?,status=? WHERE id=?")->execute([$newPaid,$newStatus,$reqId]);
        db()->prepare("INSERT INTO subscription_payments(request_id,user_id,amount,payment_method,upi_ref,recorded_by,notes)VALUES(?,?,?,?,?,?,?)")
           ->execute([$reqId,$me['id'],$amount,$method,$upi,$me['id'],'Balance payment by member']);

        $msg = ['t'=>'ok','m'=>'✅ Payment of ₹'.number_format($amount).' recorded! Admin will verify and approve.'];
    }
}

// ── Fetch this member's subscription history ─────────────────
$myRequests = db()->prepare("
    SELECT sr.*,
           u.name approver_name,
           (SELECT COALESCE(SUM(sp.amount),0) FROM subscription_payments sp WHERE sp.request_id=sr.id) AS total_paid_calc
    FROM subscription_requests sr
    LEFT JOIN users u ON u.id = sr.approved_by
    WHERE sr.user_id = ?
    ORDER BY sr.requested_at DESC
");
$myRequests->execute([$me['id']]);
$myRequests = $myRequests->fetchAll();

// Active/current subscription
$activeSub = null;
foreach ($myRequests as $r) {
    if ($r['status'] === 'approved' && $r['valid_until'] >= date('Y-m-d')) {
        $activeSub = $r;
        break;
    }
}

// Most recent pending
$pendingReq = null;
foreach ($myRequests as $r) {
    if (in_array($r['status'], ['pending','partial'])) { $pendingReq = $r; break; }
}

// Payments for pending request
$pendingPayments = [];
if ($pendingReq) {
    $pp = db()->prepare("SELECT * FROM subscription_payments WHERE request_id=? ORDER BY paid_at");
    $pp->execute([$pendingReq['id']]);
    $pendingPayments = $pp->fetchAll();
}

$logoB64 = getLogoB64();
$pageTitle = 'My Subscription — '.CLUB_NAME;

require_once __DIR__.'/../includes/header.php';
?>

<div class="hero" style="padding:2rem 1.2rem 1.8rem">
  <h1>💳 MY <span>SUBSCRIPTION</span></h1>
  <div class="hero-place"><?= h(CLUB_NAME) ?> · Membership Fees</div>
</div>
<div class="red-bar"></div>

<div class="section" style="max-width:860px">

  <?php if($msg): ?>
  <div class="alert alert-<?= $msg['t']==='ok'?'ok':($msg['t']==='warn'?'warn':'error') ?>">
    <?= $msg['m'] ?>
  </div>
  <?php endif; ?>

  <!-- ── ACTIVE SUBSCRIPTION CARD ──────────────────────────── -->
  <?php if($activeSub): ?>
  <?php
    $daysLeft = (int)ceil((strtotime($activeSub['valid_until']) - time()) / 86400);
    $barPct   = max(0, min(100, ($daysLeft / ($activeSub['plan_type']==='annual'?365:30)) * 100));
    $barColor = $daysLeft > 30 ? '#4CAF50' : ($daysLeft > 7 ? '#FF9800' : '#F44336');
  ?>
  <div style="background:linear-gradient(135deg,#0B1033,#0A14E0);border-radius:18px;padding:1.5rem;margin-bottom:1.5rem;color:#fff;position:relative;overflow:hidden;box-shadow:0 8px 28px rgba(10,20,224,.3)">
    <div style="position:absolute;top:-20px;right:-20px;width:120px;height:120px;border-radius:50%;background:rgba(255,255,255,.05)"></div>
    <div style="position:absolute;bottom:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#B71C1C,#FFC107,#B71C1C)"></div>
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1rem;flex-wrap:wrap;gap:.5rem">
      <div>
        <div style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;letter-spacing:.06em;color:#FFC107">✅ ACTIVE SUBSCRIPTION</div>
        <div style="font-size:.78rem;color:rgba(255,255,255,.65)"><?= h(ucfirst($activeSub['plan_type'])) ?> Plan · <?= h(CLUB_NAME) ?></div>
      </div>
      <span style="background:rgba(76,175,80,.2);border:1.5px solid #4CAF50;color:#A5D6A7;border-radius:20px;padding:.25rem .9rem;font-size:.72rem;font-weight:700">✓ PAID</span>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:1rem;margin-bottom:1.2rem">
      <div><div style="font-size:.6rem;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.07em">Valid From</div><div style="font-weight:700;margin-top:.15rem"><?= date('d M Y',strtotime($activeSub['valid_from'])) ?></div></div>
      <div><div style="font-size:.6rem;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.07em">Valid Until</div><div style="font-weight:700;margin-top:.15rem"><?= date('d M Y',strtotime($activeSub['valid_until'])) ?></div></div>
      <div><div style="font-size:.6rem;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.07em">Amount Paid</div><div style="font-weight:700;color:#FFC107;margin-top:.15rem">₹<?= number_format($activeSub['amount_paid']) ?></div></div>
      <div><div style="font-size:.6rem;color:rgba(255,255,255,.5);text-transform:uppercase;letter-spacing:.07em">Days Left</div><div style="font-weight:700;color:<?= $daysLeft > 30 ? '#A5D6A7' : '#EF9A9A' ?>;margin-top:.15rem"><?= $daysLeft ?> days</div></div>
    </div>
    <!-- Progress Bar -->
    <div style="background:rgba(255,255,255,.15);border-radius:20px;height:8px;overflow:hidden">
      <div style="background:<?= $barColor ?>;width:<?= $barPct ?>%;height:100%;border-radius:20px;transition:width .5s"></div>
    </div>
    <div style="font-size:.7rem;color:rgba(255,255,255,.5);margin-top:.4rem"><?= $daysLeft ?> days remaining of your <?= $activeSub['plan_type'] ?> subscription</div>
  </div>
  <?php else: ?>
  <!-- No active subscription warning -->
  <div style="background:#FFEBEE;border:2px solid #FFCDD2;border-radius:14px;padding:1.2rem;margin-bottom:1.5rem;display:flex;align-items:center;gap:.8rem">
    <span style="font-size:2rem">⚠️</span>
    <div>
      <div style="font-weight:700;color:#B71C1C;margin-bottom:.25rem">No Active Subscription</div>
      <div style="font-size:.84rem;color:#C62828">Your club membership is not active. Submit a subscription request below to renew.</div>
    </div>
  </div>
  <?php endif; ?>

  <!-- ── PLAN CARDS ──────────────────────────────────────────── -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem">
    <!-- Monthly Plan -->
    <div style="background:#fff;border-radius:14px;padding:1.3rem;box-shadow:0 3px 14px rgba(0,0,0,.08);border:2px solid #E3E7F5;position:relative;transition:all .2s" id="planMonthly">
      <div style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.05em;color:#3D4F7C">MONTHLY</div>
      <div style="font-size:2rem;font-weight:700;color:#0A14E0;margin:.3rem 0">₹<?= number_format($feeMonthly) ?></div>
      <div style="font-size:.78rem;color:#666666;margin-bottom:.8rem">per month · Auto-renew available</div>
      <ul style="font-size:.8rem;color:#3D4F7C;padding-left:1.2rem;margin-bottom:.8rem;line-height:1.8">
        <li>Full club access</li>
        <li>Event participation</li>
        <li>Digital ID card</li>
      </ul>
    </div>
    <!-- Annual Plan — recommended -->
    <div style="background:linear-gradient(160deg,#0B1033,#0A14E0);border-radius:14px;padding:1.3rem;box-shadow:0 6px 20px rgba(10,20,224,.3);border:2px solid #1A23C9;position:relative;color:#fff" id="planAnnual">
      <div style="position:absolute;top:-1px;right:12px;background:#FFC107;color:#0B1033;font-size:.62rem;font-weight:700;padding:.2rem .7rem;border-radius:0 0 8px 8px;letter-spacing:.05em">RECOMMENDED</div>
      <div style="font-family:'Bebas Neue',sans-serif;font-size:1.3rem;letter-spacing:.05em;color:#FFC107">ANNUAL</div>
      <div style="font-size:2rem;font-weight:700;color:#fff;margin:.3rem 0">₹<?= number_format($feeAnnual) ?></div>
      <div style="font-size:.78rem;color:rgba(255,255,255,.6);margin-bottom:.8rem">per year · Best value</div>
      <ul style="font-size:.8rem;color:rgba(255,255,255,.8);padding-left:1.2rem;margin-bottom:.8rem;line-height:1.8">
        <li>Full club access</li>
        <li>Priority event entry</li>
        <li>Digital ID card</li>
        <li style="color:#FFC107;font-weight:700">Save ₹<?= number_format(($feeMonthly*12) - $feeAnnual) ?>/year</li>
      </ul>
    </div>
  </div>

  <!-- ── PENDING REQUEST STATUS ─────────────────────────────── -->
  <?php if($pendingReq): ?>
  <?php
    $balance  = $pendingReq['amount_due'] - $pendingReq['total_paid_calc'];
    $paidPct  = $pendingReq['amount_due'] > 0 ? ($pendingReq['total_paid_calc'] / $pendingReq['amount_due'] * 100) : 0;
    $statusColors = ['pending'=>['#FFF8E1','#E65100','#FFB300'],'partial'=>['#ECEEFF','#0B1033','#0A14E0'],'approved'=>['#E8F5E9','#1B5E20','#4CAF50'],'rejected'=>['#FFEBEE','#B71C1C','#EF5350']];
    [$sbg,$stxt,$sbdr] = $statusColors[$pendingReq['status']] ?? ['#F5F5F5','#555','#999'];
  ?>
  <div style="background:#fff;border-radius:16px;box-shadow:0 3px 14px rgba(0,0,0,.09);overflow:hidden;margin-bottom:1.5rem">
    <div style="background:linear-gradient(135deg,#0A14E0,#1A23C9);padding:.9rem 1.2rem;display:flex;justify-content:space-between;align-items:center">
      <h3 style="color:#fff;font-size:.95rem;font-weight:700">📋 Current Request #<?= $pendingReq['id'] ?></h3>
      <span style="background:<?= $sbg ?>;color:<?= $stxt ?>;border:1.5px solid <?= $sbdr ?>;border-radius:20px;padding:.2rem .8rem;font-size:.7rem;font-weight:700;text-transform:uppercase"><?= $pendingReq['status'] === 'partial' ? '⚠️ Partial' : ($pendingReq['status']==='approved'?'✅ Approved':ucfirst($pendingReq['status'])) ?></span>
    </div>
    <div style="padding:1.2rem">
      <!-- Amount breakdown -->
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem;margin-bottom:1rem">
        <div style="text-align:center;padding:.7rem;background:#F7F8FF;border-radius:10px">
          <div style="font-size:.62rem;color:#666666;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem">Plan</div>
          <div style="font-weight:700;color:#0B1033;font-size:.95rem"><?= h(ucfirst($pendingReq['plan_type'])) ?></div>
        </div>
        <div style="text-align:center;padding:.7rem;background:#F7F8FF;border-radius:10px">
          <div style="font-size:.62rem;color:#666666;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem">Total Due</div>
          <div style="font-weight:700;color:#0B1033;font-size:.95rem">₹<?= number_format($pendingReq['amount_due']) ?></div>
        </div>
        <div style="text-align:center;padding:.7rem;background:#F7F8FF;border-radius:10px">
          <div style="font-size:.62rem;color:#666666;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.2rem">Paid So Far</div>
          <div style="font-weight:700;color:#2E7D32;font-size:.95rem">₹<?= number_format($pendingReq['total_paid_calc']) ?></div>
        </div>
      </div>

      <!-- Balance indicator -->
      <?php if($balance > 0): ?>
      <div style="background:#FFF3E0;border:1.5px solid #FFB300;border-radius:10px;padding:.8rem 1rem;margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:.85rem;color:#E65100;font-weight:700">⏳ Balance Remaining</span>
        <span style="font-family:'Bebas Neue',sans-serif;font-size:1.4rem;color:#E65100">₹<?= number_format($balance) ?></span>
      </div>
      <?php else: ?>
      <div style="background:#E8F5E9;border:1.5px solid #4CAF50;border-radius:10px;padding:.8rem 1rem;margin-bottom:1rem;text-align:center">
        <span style="font-size:.85rem;color:#1B5E20;font-weight:700">✅ Fully Paid — Awaiting Admin Approval</span>
      </div>
      <?php endif; ?>

      <!-- Progress bar -->
      <div style="background:#E3E7F5;border-radius:20px;height:10px;overflow:hidden;margin-bottom:.4rem">
        <div style="background:<?= $paidPct >= 100 ? '#4CAF50' : '#0A14E0' ?>;width:<?= min($paidPct,100) ?>%;height:100%;border-radius:20px;transition:width .5s"></div>
      </div>
      <div style="font-size:.7rem;color:#666666;margin-bottom:1rem">₹<?= number_format($pendingReq['total_paid_calc']) ?> paid of ₹<?= number_format($pendingReq['amount_due']) ?> (<?= round($paidPct) ?>%)</div>

      <!-- Payment history -->
      <?php if(!empty($pendingPayments)): ?>
      <div style="margin-bottom:1rem">
        <div style="font-size:.75rem;font-weight:700;color:#3D4F7C;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.5rem">💰 Payment History</div>
        <?php foreach($pendingPayments as $pay): ?>
        <div style="display:flex;justify-content:space-between;align-items:center;padding:.45rem .7rem;background:#F7F8FF;border-radius:8px;margin-bottom:.3rem;font-size:.8rem">
          <span>₹<?= number_format($pay['amount']) ?> via <?= h(ucfirst($pay['payment_method'])) ?><?= $pay['upi_ref']?' (Ref: '.h($pay['upi_ref']).')':'' ?></span>
          <span style="color:#666666"><?= date('d M Y', strtotime($pay['paid_at'])) ?></span>
        </div>
        <?php endforeach; ?>
      </div>
      <?php endif; ?>

      <!-- Pay Balance Form -->
      <?php if($balance > 0 && $pendingReq['status'] !== 'approved'): ?>
      <div style="background:#F0F7FF;border:1.5px solid #D6DAFF;border-radius:12px;padding:1rem">
        <div style="font-size:.8rem;font-weight:700;color:#0B1033;margin-bottom:.8rem">💸 Pay Balance Amount</div>
        <form method="POST" action="<?= url('modules/subscription.php') ?>">
          <input type="hidden" name="req_id" value="<?= $pendingReq['id'] ?>">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.6rem">
            <div>
              <label style="font-size:.68rem;font-weight:700;color:#4A5E8A;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.3rem">Amount (₹) *</label>
              <input type="number" name="pay_amount" min="1" max="<?= $balance ?>" step="0.01" required
                     style="width:100%;padding:.65rem .8rem;border:2px solid #E3E7F5;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none"
                     placeholder="₹<?= number_format($balance) ?>" value="<?= $balance ?>">
            </div>
            <div>
              <label style="font-size:.68rem;font-weight:700;color:#4A5E8A;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.3rem">Payment Method</label>
              <select name="pay_method" style="width:100%;padding:.65rem .8rem;border:2px solid #E3E7F5;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none;cursor:pointer">
                <option value="cash">💵 Cash</option>
                <option value="upi">📱 UPI / GPay / PhonePe</option>
                <option value="bank_transfer">🏦 Bank Transfer</option>
                <option value="cheque">📄 Cheque</option>
              </select>
            </div>
          </div>
          <input type="text" name="pay_upi" placeholder="UPI / Transaction Reference (optional)"
                 style="width:100%;padding:.65rem .8rem;border:2px solid #E3E7F5;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none;margin-bottom:.6rem">
          <button type="submit" name="pay_balance" style="width:100%;padding:.75rem;background:#0A14E0;color:#fff;border:none;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.88rem;cursor:pointer">
            💳 Submit Balance Payment
          </button>
        </form>
      </div>
      <?php endif; ?>

      <!-- WhatsApp Secretary link -->
      <?php
        $waSec = preg_replace('/\D/','',CLUB_PHONE);
        $waMsg = urlencode("Hi Secretary, I've submitted my subscription request #".$pendingReq['id']." for ₹".number_format($pendingReq['amount_due'])." (".ucfirst($pendingReq['plan_type'])." plan). Kindly review and approve. — ".h($me['name']));
      ?>
      <a href="https://wa.me/<?= $waSec ?>?text=<?= $waMsg ?>" target="_blank"
         style="display:flex;align-items:center;justify-content:center;gap:.5rem;margin-top:.8rem;background:#25D366;color:#fff;border-radius:9px;padding:.65rem;font-weight:700;font-size:.85rem;text-decoration:none">
        💬 Notify Secretary on WhatsApp
      </a>
    </div>
  </div>
  <?php endif; ?>

  <!-- ── NEW SUBSCRIPTION REQUEST FORM ─────────────────────── -->
  <?php if(!$pendingReq && !$activeSub): ?>
  <div style="background:#fff;border-radius:16px;box-shadow:0 3px 14px rgba(0,0,0,.09);overflow:hidden;margin-bottom:1.5rem">
    <div style="background:linear-gradient(135deg,#B71C1C,#C62828);padding:.9rem 1.2rem">
      <h3 style="color:#fff;font-size:.95rem;font-weight:700">📝 Request New Subscription</h3>
    </div>
    <div style="padding:1.2rem">
      <form method="POST" action="<?= url('modules/subscription.php') ?>">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-bottom:.8rem">
          <div>
            <label style="font-size:.68rem;font-weight:700;color:#4A5E8A;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.4rem">Plan Type *</label>
            <select name="plan_type" id="planSelect" aria-label="Plan" onchange="updateAmount(this.value)"
                    style="width:100%;padding:.68rem .9rem;border:2px solid #E3E7F5;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none;cursor:pointer">
              <option value="annual">Annual — ₹<?= number_format($feeAnnual) ?> (Recommended)</option>
              <option value="monthly">Monthly — ₹<?= number_format($feeMonthly) ?></option>
            </select>
          </div>
          <div>
            <label style="font-size:.68rem;font-weight:700;color:#4A5E8A;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.4rem">Payment Method</label>
            <select name="payment_method" aria-label="Payment method"
                    style="width:100%;padding:.68rem .9rem;border:2px solid #E3E7F5;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none;cursor:pointer">
              <option value="cash">💵 Cash</option>
              <option value="upi">📱 UPI / GPay / PhonePe</option>
              <option value="bank_transfer">🏦 Bank Transfer</option>
              <option value="cheque">📄 Cheque</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>

        <div style="background:#ECEEFF;border-radius:10px;padding:.8rem 1rem;margin-bottom:.8rem;display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:.85rem;color:#0B1033;font-weight:600">Total Due:</span>
          <span id="totalDue" style="font-family:'Bebas Neue',sans-serif;font-size:1.5rem;color:#0A14E0">₹<?= number_format($feeAnnual) ?></span>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-bottom:.8rem">
          <div>
            <label style="font-size:.68rem;font-weight:700;color:#4A5E8A;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.4rem">Initial Payment (₹)</label>
            <input type="number" name="initial_payment" id="initPay" min="0"
                   style="width:100%;padding:.68rem .9rem;border:2px solid #E3E7F5;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none"
                   placeholder="0 for full payment later" value="0" oninput="updateBalance(this.value)">
            <div style="font-size:.7rem;color:#666666;margin-top:.25rem">Enter 0 if paying cash to secretary</div>
          </div>
          <div>
            <label style="font-size:.68rem;font-weight:700;color:#4A5E8A;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.4rem">UPI / Transaction Ref</label>
            <input type="text" name="upi_ref"
                   style="width:100%;padding:.68rem .9rem;border:2px solid #E3E7F5;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none"
                   placeholder="Optional UPI/transaction ID">
          </div>
        </div>

        <!-- Balance indicator -->
        <div id="balanceBox" style="background:#FFF3E0;border:1.5px solid #FFB300;border-radius:10px;padding:.65rem 1rem;margin-bottom:.8rem;display:flex;justify-content:space-between;align-items:center;display:none">
          <span style="font-size:.82rem;color:#E65100;font-weight:600">Balance you'll owe:</span>
          <span id="balanceAmt" style="font-family:'Bebas Neue',sans-serif;font-size:1.2rem;color:#E65100">₹0</span>
        </div>

        <div>
          <label style="font-size:.68rem;font-weight:700;color:#4A5E8A;text-transform:uppercase;letter-spacing:.06em;display:block;margin-bottom:.4rem">Notes (Optional)</label>
          <textarea name="notes" rows="2"
                    style="width:100%;padding:.68rem .9rem;border:2px solid #E3E7F5;border-radius:9px;font-family:'Plus Jakarta Sans',sans-serif;font-size:.9rem;outline:none;resize:vertical"
                    placeholder="Any message for the Secretary…"></textarea>
        </div>

        <button type="submit" name="req_sub"
                style="width:100%;padding:.82rem;background:linear-gradient(135deg,#0A14E0,#1A23C9);color:#fff;border:none;border-radius:10px;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;font-size:.92rem;cursor:pointer;margin-top:.8rem;box-shadow:0 4px 14px rgba(10,20,224,.3)">
          📤 Submit Subscription Request
        </button>

        <div style="background:#F7F8FF;border-radius:10px;padding:.8rem;margin-top:.8rem;font-size:.78rem;color:#55678F;text-align:center;line-height:1.5">
          ℹ️ After submitting, the Secretary will review your request and approve it.<br>
          You can pay the full amount now or make partial payments later.
        </div>
      </form>
    </div>
  </div>
  <?php elseif($activeSub): ?>
  <!-- Renew option -->
  <div style="background:#F7F8FF;border:2px dashed #C5CEE0;border-radius:14px;padding:1.2rem;text-align:center;margin-bottom:1.5rem">
    <div style="font-size:1.5rem;margin-bottom:.5rem">🔄</div>
    <div style="font-weight:700;color:#3D4F7C;margin-bottom:.3rem">Early Renewal Available</div>
    <div style="font-size:.82rem;color:#666666;margin-bottom:.8rem">Submit a renewal request before your subscription expires</div>
    <a href="?renew=1" style="display:inline-block;background:#0A14E0;color:#fff;border-radius:9px;padding:.6rem 1.3rem;font-weight:700;font-size:.85rem;text-decoration:none">Request Early Renewal</a>
  </div>
  <?php endif; ?>

  <!-- ── SUBSCRIPTION HISTORY ───────────────────────────────── -->
  <?php if(!empty($myRequests)): ?>
  <div style="background:#fff;border-radius:16px;box-shadow:0 3px 14px rgba(0,0,0,.09);overflow:hidden">
    <div style="background:#37474F;padding:.9rem 1.2rem">
      <h3 style="color:#fff;font-size:.95rem;font-weight:700">📜 Subscription History</h3>
    </div>
    <div style="padding:.5rem">
      <?php foreach($myRequests as $r):
        $statusMap=['pending'=>['#FFF8E1','#E65100','⏳'],'partial'=>['#ECEEFF','#0B1033','⚠️'],'approved'=>['#E8F5E9','#1B5E20','✅'],'rejected'=>['#FFEBEE','#B71C1C','❌']];
        [$sbg,$stxt,$sico]=$statusMap[$r['status']]??['#F5F5F5','#555','•'];
      ?>
      <div style="display:flex;justify-content:space-between;align-items:flex-start;padding:.9rem;border-bottom:1px solid #E3E7F5;flex-wrap:wrap;gap:.4rem">
        <div>
          <div style="font-weight:700;font-size:.9rem;color:#0B1033"><?= ucfirst($r['plan_type']) ?> Plan — ₹<?= number_format($r['amount_due']) ?></div>
          <div style="font-size:.75rem;color:#9E9E9E;margin-top:.15rem">
            Requested: <?= date('d M Y', strtotime($r['requested_at'])) ?>
            <?php if($r['approved_at']): ?> · Approved: <?= date('d M Y', strtotime($r['approved_at'])) ?><?php endif; ?>
          </div>
          <?php if($r['valid_from'] && $r['valid_until']): ?>
          <div style="font-size:.75rem;color:#3D4F7C;margin-top:.1rem">
            📅 <?= date('d M Y',strtotime($r['valid_from'])) ?> → <?= date('d M Y',strtotime($r['valid_until'])) ?>
          </div>
          <?php endif; ?>
          <?php if($r['rejection_note']): ?>
          <div style="font-size:.75rem;color:#B71C1C;margin-top:.1rem">Reason: <?= h($r['rejection_note']) ?></div>
          <?php endif; ?>
        </div>
        <div style="text-align:right">
          <span style="background:<?= $sbg ?>;color:<?= $stxt ?>;border-radius:20px;padding:.2rem .75rem;font-size:.68rem;font-weight:700;display:inline-block;margin-bottom:.25rem"><?= $sico ?> <?= h(ucfirst($r['status'])) ?></span>
          <div style="font-size:.75rem;color:#666666">Paid: <strong style="color:#2E7D32">₹<?= number_format($r['total_paid_calc']) ?></strong> / ₹<?= number_format($r['amount_due']) ?></div>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
  <?php endif; ?>

</div>

<script>
var fees={annual:<?= $feeAnnual ?>,monthly:<?= $feeMonthly ?>};
function updateAmount(plan){
  var due=fees[plan]||fees.annual;
  document.getElementById('totalDue').textContent='₹'+due.toLocaleString('en-IN');
  document.getElementById('initPay').max=due;
  updateBalance(document.getElementById('initPay').value,due);
}
function updateBalance(paid,due){
  due=due||(fees[document.getElementById('planSelect').value]||fees.annual);
  paid=parseFloat(paid)||0;
  var bal=Math.max(0,due-paid);
  var box=document.getElementById('balanceBox');
  document.getElementById('balanceAmt').textContent='₹'+bal.toLocaleString('en-IN');
  box.style.display=bal>0&&paid>0?'flex':'none';
}
</script>

<?php require_once __DIR__.'/../includes/footer.php'; ?>
