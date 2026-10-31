<?php
// ============================================================
//  modules/admin_subscription.php
//  Admin Dashboard: View All Members & Send WhatsApp Requests
// ============================================================

require_once __DIR__.'/../includes/config.php';

requireLogin(); 
$me = currentUser();

// Only global admins or assigned Subscription module admins may access this dashboard
if (!(isAdminRole($me['role']) || isFinanceAdmin($me['role']) || isModuleAdmin('subscription', $me))) {
    header('Location: '.url('dashboard.php')); exit;
}

$msg = '';
$clubName = defined('CLUB_NAME') ? CLUB_NAME : 'AASC Club';

if (!defined('CLUB_BANK_DETAILS')) {
    define('CLUB_BANK_DETAILS', 
        "🏦 Aishwarya Arts & Sports Club\n" .
        "Bank: State Bank of India (SBI)\n" .
        "Account No: 1234567890\n" .
        "IFSC Code: SBIN0001234\n" .
        "UPI ID: aasc@upi"
    );
}

// ── Handle Request Actions (Approve / Reject) ────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action'])) {
    $reqId = (int)$_POST['req_id'];
    $action = $_POST['action'];

    if ($action === 'approve') {
        $stmt = db()->prepare("SELECT * FROM subscription_requests WHERE id = ?");
        $stmt->execute([$reqId]);
        $req = $stmt->fetch();

        if ($req) {
            $startDate = date('Y-m-d');
            $endDate = ($req['plan_type'] === 'monthly') 
                ? date('Y-m-d', strtotime('+30 days'))
                : date('Y-m-d', strtotime('+365 days'));

            $update = db()->prepare("UPDATE subscription_requests SET status='approved', valid_from=?, valid_until=?, approved_by=?, approved_at=NOW() WHERE id=?");
            $update->execute([$startDate, $endDate, $me['id'], $reqId]);
            $msg = ['t' => 'ok', 'm' => '✅ Subscription request #' . $reqId . ' approved!'];
        }
    } elseif ($action === 'reject') {
        $note = trim($_POST['rejection_note'] ?? 'Denied by administration.');
        $update = db()->prepare("UPDATE subscription_requests SET status='rejected', rejection_note=?, approved_by=?, approved_at=NOW() WHERE id=?");
        $update->execute([$note, $me['id'], $reqId]);
        $msg = ['t' => 'warn', 'm' => '❌ Subscription request #' . $reqId . ' rejected.'];
    }
}

// ── Fetch Requests ───────────────────────────────────────────
$allRequests = db()->query("
    SELECT sr.*, u.name AS member_name, u.* FROM subscription_requests sr
    JOIN users u ON u.id = sr.user_id
    ORDER BY sr.requested_at DESC
")->fetchAll();

$pageTitle = 'Admin Subscriptions — ' . $clubName;
require_once __DIR__.'/../includes/header.php';
?>

<div class="hero" style="padding:2rem 1.2rem 1.8rem; background: linear-gradient(135deg, #1A237E, #0D47A1);">
  <h1>⚙️ ADMIN <span>SUBSCRIPTIONS</span></h1>
  <div class="hero-place">Review Club Member Requests & Payments</div>
</div>
<div class="red-bar" style="background: #D32F2F; height: 4px;"></div>

<div class="section" style="max-width:1100px; margin: 2rem auto; padding: 0 1rem;">

  <?php if($msg): ?>
  <div class="alert alert-<?= $msg['t']==='ok'?'ok':($msg['t']==='warn'?'warn':'error') ?>" style="padding: 1rem; margin-bottom: 1.5rem; border-radius: 8px; font-weight: bold;">
    <?= $msg['m'] ?>
  </div>
  <?php endif; ?>

  <div style="background:#fff; border-radius:16px; box-shadow:0 4px 20px rgba(0,0,0,.08); overflow-x:auto;" tabindex="0" role="region" aria-label="Subscriptions table">
    <div style="background:#0D1B3E; padding:1.1rem 1.5rem;">
      <h3 style="color:#fff; font-size:1.1rem; font-weight:700; margin:0;">👥 All Member Subscriptions</h3>
    </div>
    
    <table style="width:100%; border-collapse:collapse; text-align:left; font-family:'DM Sans',sans-serif; font-size:0.9rem;">
      <thead>
        <tr style="background:#F4F6F9; border-bottom:2px solid #E8ECF4; color:#4A5E8A; text-transform:uppercase; font-size:0.75rem; letter-spacing:0.05em;">
          <th style="padding:1rem;">Member</th>
          <th style="padding:1rem;">Plan Details</th>
          <th style="padding:1rem;">Financial Balance</th>
          <th style="padding:1rem;">Status</th>
          <th style="padding:1rem; text-align:right;">Actions / Reminders</th>
        </tr>
      </thead>
      <tbody>
        <?php if(empty($allRequests)): ?>
        <tr>
          <td colspan="5" style="padding:3rem; text-align:center; color:#666666;">No subscription requests found.</td>
        </tr>
        <?php else: ?>
        <?php foreach($allRequests as $r): 
          // Detect if any kind of field exists
          $rawPhone = '';
          if (!empty($r['mobile'])) { $rawPhone = $r['mobile']; }
          elseif (!empty($r['phone'])) { $rawPhone = $r['phone']; }
          elseif (!empty($r['whatsapp'])) { $rawPhone = $r['whatsapp']; }
          
          $pStmt = db()->prepare("SELECT COALESCE(SUM(amount), 0) AS total_paid FROM subscription_payments WHERE request_id = ?");
          $pStmt->execute([$r['id']]);
          $pRow = $pStmt->fetch();
          $totalPaid = $pRow ? $pRow['total_paid'] : 0;
          
          $balance = $r['amount_due'] - $totalPaid;
          
          $bg = '#F5F5F5'; $txt = '#555'; $bdr = '#999'; $lbl = ucfirst($r['status']);
          if ($r['status'] === 'pending')  { $bg = '#FFF8E1'; $txt = '#E65100'; $bdr = '#FFB300'; $lbl = '⏳ Pending'; }
          if ($r['status'] === 'partial')  { $bg = '#E3F2FD'; $txt = '#07225c'; $bdr = '#0D47A1'; $lbl = '⚠️ Partial'; }
          if ($r['status'] === 'approved') { $bg = '#E8F5E9'; $txt = '#1B5E20'; $bdr = '#4CAF50'; $lbl = '✅ Approved'; }
          if ($r['status'] === 'rejected') { $bg = '#FFEBEE'; $txt = '#B71C1C'; $bdr = '#EF5350'; $lbl = '❌ Rejected'; }
          
          // Custom encoded message parameters
          $waMsgText = "Hi " . $r['member_name'] . ",\n\n"
                 . "Regarding your request (#" . $r['id'] . ") for the " . ucfirst($r['plan_type']) . " Plan:\n"
                 . "• Total Owed: ₹" . number_format($r['amount_due']) . "\n"
                 . "• Remaining Balance: ₹" . number_format($balance) . "\n\n"
                 . "Please remit using our details below:\n"
                 . CLUB_BANK_DETAILS;
          $encodedMsg = rawurlencode($waMsgText);
        ?>
        <tr style="border-bottom:1px solid #E8ECF4;">
          
          <td style="padding:1rem; vertical-align:top;">
            <div style="font-weight:700; color:#0D1B3E; font-size:0.95rem;"><?= h($r['member_name']) ?></div>
            <?php if(!empty($rawPhone)): ?>
              <div style="font-size:0.78rem; color:#7A8DB5; margin-top:0.15rem;">📱 <?= h($rawPhone) ?></div>
            <?php else: ?>
              <div style="margin-top:0.3rem;">
                <input type="tel" id="input_phone_<?= $r['id'] ?>" placeholder="Enter WhatsApp #" style="font-size:0.75rem; padding:0.2rem; border:1px solid #CCC; border-radius:4px; width:120px;">
              </div>
            <?php endif; ?>
          </td>
          
          <td style="padding:1rem; vertical-align:top;">
            <span style="background:#E8EAF6; color:#283593; font-size:0.7rem; font-weight:700; padding:0.15rem 0.5rem; border-radius:4px; text-transform:uppercase;">
              <?= h($r['plan_type']) ?>
            </span>
            <div style="font-size:0.75rem; color:#666666; margin-top:0.3rem;">Req: <?= date('d M Y', strtotime($r['requested_at'])) ?></div>
          </td>
          
          <td style="padding:1rem; vertical-align:top;">
            <div style="font-size:0.82rem; color:#3D4F7C;">Due: <strong>₹<?= number_format($r['amount_due']) ?></strong></div>
            <div style="font-size:0.82rem; color:#2E7D32; margin-top:0.15rem;">Paid: <strong>₹<?= number_format($totalPaid) ?></strong></div>
            <?php if($balance > 0): ?>
              <div style="font-size:0.82rem; color:#C62828; font-weight:700; margin-top:0.15rem;">Bal: ₹<?= number_format($balance) ?></div>
            <?php endif; ?>
          </td>
          
          <td style="padding:1rem; vertical-align:top;">
            <span style="background:<?= $bg ?>; color:<?= $txt ?>; border:1px solid <?= $bdr ?>; border-radius:12px; padding:0.15rem 0.6rem; font-size:0.72rem; font-weight:700; display:inline-block; margin-bottom:0.3rem;">
              <?= $lbl ?>
            </span>
          </td>
          
          <td style="padding:1rem; vertical-align:top; text-align:right;">
            <div style="display:flex; flex-direction:column; gap:0.4rem; align-items:flex-end;">
              
              <?php if(in_array($r['status'], ['pending','partial'])): ?>
                
                <button onclick="sendWhatsApp('<?= $r['id'] ?>', '<?= preg_replace('/\D/','',$rawPhone) ?>', '<?= $encodedMsg ?>')" style="display:inline-flex; align-items:center; gap:0.3rem; background:#25D366; color:#fff; border:none; border-radius:6px; padding:0.35rem 0.7rem; font-weight:700; font-size:0.75rem; cursor:pointer;">
                  💬 Share Bank Info
                </button>
                
                <form method="POST" style="margin:0; display:inline; width:100%;">
                  <input type="hidden" name="req_id" value="<?= $r['id'] ?>">
                  <input type="hidden" name="action" value="approve">
                  <button type="submit" style="background:#0D47A1; color:#fff; border:none; border-radius:6px; padding:0.35rem 0.7rem; font-weight:700; font-size:0.75rem; cursor:pointer; width:100%;">
                    Approve
                  </button>
                </form>

                <button onclick="document.getElementById('rejectBox<?= $r['id'] ?>').style.display='block'" style="background:#FFF0F0; color:#C62828; border:1px solid #FFCDD2; border-radius:6px; padding:0.25rem 0.6rem; font-size:0.72rem; cursor:pointer;">
                  Reject
                </button>
                
                <div id="rejectBox<?= $r['id'] ?>" style="display:none; text-align:left; background:#FFF8F8; border:1px solid #FFCDD2; padding:0.5rem; border-radius:8px; margin-top:0.4rem; width:200px;">
                  <form method="POST" style="margin:0;">
                    <input type="hidden" name="req_id" value="<?= $r['id'] ?>">
                    <input type="hidden" name="action" value="reject">
                    <input type="text" name="rejection_note" placeholder="Reason..." required style="width:100%; font-size:0.75rem; padding:0.3rem; margin-bottom:0.3rem; border:1px solid #CCC; border-radius:4px;">
                    <div style="display:flex; gap:0.3rem;">
                      <button type="submit" style="background:#B71C1C; color:#fff; border:none; padding:0.2rem 0.4rem; font-size:0.7rem; border-radius:4px; cursor:pointer;">Confirm</button>
                      <button type="button" onclick="document.getElementById('rejectBox<?= $r['id'] ?>').style.display='none'" style="background:#9E9E9E; color:#fff; border:none; padding:0.2rem 0.4rem; font-size:0.7rem; border-radius:4px; cursor:pointer;">Cancel</button>
                    </div>
                  </form>
                </div>
              <?php else: ?>
                <span style="font-size:0.75rem; color:#666666;">Completed</span>
              <?php endif; ?>
              
            </div>
          </td>
        </tr>
        <?php endforeach; ?>
        <?php endif; ?>
      </tbody>
    </table>
  </div>
</div>

<script>
function sendWhatsApp(id, fixedPhone, msg) {
    var phone = fixedPhone;
    if(!phone) {
        var input = document.getElementById('input_phone_' + id);
        if(input) {
            phone = input.value.replace(/\D/g, '');
        }
    }
    if(!phone) {
        alert('Please provide a valid phone number first!');
        return;
    }
    window.open('https://wa.me/' + phone + '?text=' + msg, '_blank');
}
</script>

<?php require_once __DIR__.'/../includes/footer.php'; ?>
