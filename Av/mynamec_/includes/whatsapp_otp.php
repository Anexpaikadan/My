<?php
require_once __DIR__ . '/config.php';

function sendWhatsAppOTP($phone) {
    $otp = generateOTP();
    $exp = date('Y-m-d H:i:s', time() + OTP_EXPIRY_MIN * 60);
    db()->prepare('UPDATE users SET otp_code=?,otp_expires_at=? WHERE whatsapp_number=?')
       ->execute(array($otp, $exp, $phone));

    // Build WhatsApp click-to-chat URL
    // The member opens this link on their own phone — WhatsApp pre-fills the message
    // They tap SEND once, and the club bot/number receives it
    // BUT here we do self-send: the OTP message goes to the member's OWN number
    $clubPhone = preg_replace('/\D/', '', CLUB_PHONE); // club WhatsApp number
    $msg = "🔐 *" . CLUB_NAME . " Login OTP*\n\n"
         . "Your One-Time Password:\n\n"
         . "*" . $otp . "*\n\n"
         . "Valid for " . OTP_EXPIRY_MIN . " minutes.\n"
         . "Do not share this OTP with anyone.";

    // wa.me link — opens WhatsApp on the member's device with OTP message pre-filled
    // The TO number is the member's own number (self-message / note to self)
    $waUrl = 'https://wa.me/' . $phone . '?text=' . rawurlencode($msg);

    return array(
        'success' => true,
        'otp'     => $otp,        // returned so JS can open WhatsApp
        'wa_url'  => $waUrl,      // JS opens this in new tab → WhatsApp opens with OTP
        'message' => 'OTP ready',
    );
}

function verifyOTP($phone, $otp) {
    $s = db()->prepare("SELECT * FROM users WHERE whatsapp_number=? AND otp_code=? AND otp_expires_at>=NOW()");
    $s->execute(array($phone, $otp));
    $u = $s->fetch();
    if (!$u) return array('success'=>false,'user'=>null,'message'=>'Invalid or expired OTP. Try again.');
    if ($u['status']==='rejected') return array('success'=>false,'user'=>null,'message'=>'Application rejected. Contact Secretary.');
    db()->prepare('UPDATE users SET otp_code=NULL,otp_expires_at=NULL,whatsapp_verified=1 WHERE id=?')->execute(array($u['id']));
    return array('success'=>true,'user'=>$u,'message'=>'Login successful!');
}

// ── Send a WhatsApp message via wa.me click-to-chat ─────────────
// Returns a wa.me URL. The caller (admin browser) opens this link.
function makeWaLink($phone, $message) {
    $phone = preg_replace('/\D/', '', $phone);
    if (!$phone) return null;
    return 'https://wa.me/' . $phone . '?text=' . rawurlencode($message);
}

// ── Build approval welcome message ───────────────────────────────
function memberApprovedMessage($memberName) {
    $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    $place = setting('CLUB_PLACE', 'Vettikkattiri');
    $site  = SITE_URL;
    return "🎉 *Welcome to " . $club . "!*

"
         . "Dear *" . $memberName . "*,

"
         . "Your membership application has been *✅ APPROVED* by the committee.

"
         . "You are now an official member of " . $club . ", " . $place . ".

"
         . "🔐 *Login to your member portal:*
"
         . $site . "

"
         . "Use your registered phone number and passkey to log in.

"
         . "🏆 Access your ID card, events, blood hub, achievements and more!

"
         . "Welcome to the family! 🤝
"
         . "— " . $club . " Committee";
}

// ── Build rejection message ───────────────────────────────────────
function memberRejectedMessage($memberName, $reason = '') {
    $club = setting('CLUB_NAME', 'Aishwarya Arts & Sports Club');
    return "Dear *" . $memberName . "*,

"
         . "We regret to inform you that your membership application to *" . $club . "* could not be approved at this time.

"
         . ($reason ? "Reason: " . $reason . "

" : "")
         . "For more information, please contact the club secretary.

"
         . "— " . $club . " Committee";
}
