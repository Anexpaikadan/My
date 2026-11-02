<?php
// ================================================================
// lang.php — English / Malayalam texts in one place
// Use:  echo t('nav_home');      → "Home" or "ഹോം"
//       lang_url('ml')           → link that switches the language
// The choice is kept in a cookie for one year. Add new keys to BOTH lists.
// ================================================================
if (!function_exists('t')) {

function lang_current() {
    static $l = null;
    if ($l !== null) return $l;
    if (isset($_GET['setlang']) && in_array($_GET['setlang'], array('en', 'ml'), true)) {
        $l = $_GET['setlang'];
        if (!headers_sent()) setcookie('lang', $l, array('expires' => time() + 31536000, 'path' => '/', 'samesite' => 'Lax'));
        return $l;
    }
    $l = (isset($_COOKIE['lang']) && $_COOKIE['lang'] === 'ml') ? 'ml' : 'en';
    return $l;
}
function lang_url($to) {
    $uri = isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '/';
    $uri = preg_replace('/([?&])setlang=[a-z]+&?/', '$1', $uri);
    $uri = rtrim($uri, '?&');
    return $uri . (strpos($uri, '?') === false ? '?' : '&') . 'setlang=' . $to;
}

function lang_strings() {
    return array(
    'en' => array(
        // navigation
        'nav_home' => 'Home', 'nav_market' => 'Market', 'nav_login' => 'Login', 'nav_dashboard' => 'Dashboard',
        'nav_account' => 'My account', 'nav_more' => 'More', 'nav_members' => 'Members', 'nav_events' => 'Events',
        'nav_feed' => 'Feed', 'nav_admin' => 'Admin', 'nav_settings' => 'Settings', 'nav_logout' => 'Log out',
        'nav_website' => 'Website', 'nav_menu' => 'Menu', 'nav_back' => 'Back', 'nav_add' => 'Add',
        'lang_switch' => 'മലയാളം', 'lang_label' => 'Change language to Malayalam',
        // public site
        'hero_join' => 'Join the Club', 'hero_whatsapp' => 'WhatsApp', 'hero_call' => 'Call',
        'sec_about' => 'About the club', 'sec_programs' => 'Our programs', 'sec_achievements' => 'Achievements',
        'sec_gallery' => 'Gallery', 'sec_events' => 'Upcoming events', 'sec_fees' => 'Membership fees',
        'sec_timings' => 'Timings', 'sec_rules' => 'Rules & info', 'sec_shop' => 'Mini market', 'sec_contact' => 'Contact us',
        'sec_notices' => 'Notice board', 'sec_committee' => 'Our committee',
        'more_details' => 'More details', 'suitable_for' => 'Suitable for', 'time' => 'Time', 'contact_person' => 'Contact person',
        'join_now' => 'Join now', 'enquire' => 'Enquire', 'most_popular' => 'Most popular', 'per_month' => 'per month', 'per_year' => 'per year',
        'offer' => 'Offer', 'enquire_whatsapp' => 'Enquire on WhatsApp', 'see_all' => 'See all', 'no_items' => 'Nothing here yet.',
        'address' => 'Address', 'phone' => 'Phone', 'open_map' => 'Open in Google Maps', 'instagram' => 'Instagram',
        'developed_by' => 'Developed by', 'previous' => 'Previous', 'next' => 'Next', 'close' => 'Close',
        'today' => 'Today', 'tomorrow' => 'Tomorrow', 'days_left' => 'in %d days',
        // enquiry form
        'form_title' => 'Join the club', 'form_sub' => 'Send your details. The secretary will contact you on WhatsApp.',
        'form_name' => 'Your name', 'form_place' => 'Place', 'form_whatsapp' => 'WhatsApp number', 'form_interest' => 'Interested in',
        'form_send' => 'Send', 'form_thanks' => 'Thank you!', 'form_thanks_sub' => 'We got your details. WhatsApp is opening so you can send them to the club.',
        'form_open_wa' => 'Open WhatsApp again', 'form_err_name' => 'Please enter your name.', 'form_err_phone' => 'Please enter a 10-digit WhatsApp number.',
        'form_err_limit' => 'Too many requests. Please try again later.', 'form_err_net' => 'Network error. Please try again.',
        'form_member_login' => 'Already a member? Log in',
        // app shell
        'app_today' => 'Today', 'app_members_sec' => 'Members', 'app_this_month' => 'This month', 'app_quick' => 'Quick actions',
        'app_all_pages' => 'All pages', 'app_greet_m' => 'Good morning', 'app_greet_a' => 'Good afternoon', 'app_greet_e' => 'Good evening',
        'tile_new_members' => 'New members', 'tile_pending' => 'Waiting approval', 'tile_events_today' => 'Events today',
        'tile_enquiries' => 'New enquiries', 'tile_active' => 'Active members', 'tile_donors' => 'Blood donors',
        'tile_committee' => 'Committee', 'tile_events_month' => 'Events this month', 'tile_collected' => 'Fees collected',
        'tile_blood_req' => 'Blood requests', 'tile_market' => 'Market items', 'tile_posts' => 'Feed posts',
        // passkey check
        'sudo_title' => 'Confirm it is you', 'sudo_sub' => 'Enter your 6-digit login passkey to continue.',
        'sudo_btn' => 'Confirm', 'sudo_wrong' => 'Wrong passkey. Try again.',
        // contact page
        'ct_title' => 'Send a message', 'ct_sub' => 'Write to us about membership, events or anything else. We reply on WhatsApp.',
        'ct_email' => 'Email (optional)', 'ct_subject' => 'Subject', 'ct_message' => 'Message', 'ct_send' => 'Send message',
        'ct_sent' => 'Message sent!', 'ct_sent_sub' => 'Thank you. We will get back to you soon.', 'ct_again' => 'Send another',
        'ct_group' => 'WhatsApp group', 'ct_group_join' => 'Join our community group', 'ct_portal' => 'Member portal',
        'ct_portal_go' => 'Log in or apply to join', 'ct_err' => 'Please enter your name and a message.',
    ),
    'ml' => array(
        'nav_home' => 'ഹോം', 'nav_market' => 'മാർക്കറ്റ്', 'nav_login' => 'ലോഗിൻ', 'nav_dashboard' => 'ഡാഷ്ബോർഡ്',
        'nav_account' => 'എന്റെ അക്കൗണ്ട്', 'nav_more' => 'കൂടുതൽ', 'nav_members' => 'അംഗങ്ങൾ', 'nav_events' => 'പരിപാടികൾ',
        'nav_feed' => 'ഫീഡ്', 'nav_admin' => 'അഡ്മിൻ', 'nav_settings' => 'ക്രമീകരണങ്ങൾ', 'nav_logout' => 'ലോഗൗട്ട്',
        'nav_website' => 'വെബ്സൈറ്റ്', 'nav_menu' => 'മെനു', 'nav_back' => 'തിരികെ', 'nav_add' => 'ചേർക്കുക',
        'lang_switch' => 'English', 'lang_label' => 'ഭാഷ ഇംഗ്ലീഷിലേക്ക് മാറ്റുക',
        'hero_join' => 'ക്ലബ്ബിൽ ചേരൂ', 'hero_whatsapp' => 'വാട്സാപ്പ്', 'hero_call' => 'വിളിക്കൂ',
        'sec_about' => 'ക്ലബ്ബിനെക്കുറിച്ച്', 'sec_programs' => 'ഞങ്ങളുടെ പരിപാടികൾ', 'sec_achievements' => 'നേട്ടങ്ങൾ',
        'sec_gallery' => 'ഗാലറി', 'sec_events' => 'വരാനിരിക്കുന്ന പരിപാടികൾ', 'sec_fees' => 'അംഗത്വ ഫീസ്',
        'sec_timings' => 'സമയക്രമം', 'sec_rules' => 'നിയമങ്ങളും വിവരങ്ങളും', 'sec_shop' => 'മിനി മാർക്കറ്റ്', 'sec_contact' => 'ബന്ധപ്പെടുക',
        'sec_notices' => 'നോട്ടീസ് ബോർഡ്', 'sec_committee' => 'ഞങ്ങളുടെ കമ്മിറ്റി',
        'more_details' => 'കൂടുതൽ വിവരങ്ങൾ', 'suitable_for' => 'അനുയോജ്യം', 'time' => 'സമയം', 'contact_person' => 'ബന്ധപ്പെടേണ്ട ആൾ',
        'join_now' => 'ഇപ്പോൾ ചേരൂ', 'enquire' => 'അന്വേഷിക്കൂ', 'most_popular' => 'ഏറ്റവും ജനപ്രിയം', 'per_month' => 'പ്രതിമാസം', 'per_year' => 'പ്രതിവർഷം',
        'offer' => 'ഓഫർ', 'enquire_whatsapp' => 'വാട്സാപ്പിൽ അന്വേഷിക്കൂ', 'see_all' => 'എല്ലാം കാണുക', 'no_items' => 'ഇവിടെ ഇതുവരെ ഒന്നുമില്ല.',
        'address' => 'വിലാസം', 'phone' => 'ഫോൺ', 'open_map' => 'ഗൂഗിൾ മാപ്പിൽ തുറക്കുക', 'instagram' => 'ഇൻസ്റ്റാഗ്രാം',
        'developed_by' => 'നിർമ്മിച്ചത്', 'previous' => 'മുമ്പത്തേത്', 'next' => 'അടുത്തത്', 'close' => 'അടയ്ക്കുക',
        'today' => 'ഇന്ന്', 'tomorrow' => 'നാളെ', 'days_left' => '%d ദിവസത്തിനുള്ളിൽ',
        'form_title' => 'ക്ലബ്ബിൽ ചേരൂ', 'form_sub' => 'നിങ്ങളുടെ വിവരങ്ങൾ അയക്കൂ. സെക്രട്ടറി വാട്സാപ്പിൽ ബന്ധപ്പെടും.',
        'form_name' => 'നിങ്ങളുടെ പേര്', 'form_place' => 'സ്ഥലം', 'form_whatsapp' => 'വാട്സാപ്പ് നമ്പർ', 'form_interest' => 'താൽപ്പര്യം',
        'form_send' => 'അയക്കുക', 'form_thanks' => 'നന്ദി!', 'form_thanks_sub' => 'നിങ്ങളുടെ വിവരങ്ങൾ ലഭിച്ചു. ക്ലബ്ബിലേക്ക് അയക്കാൻ വാട്സാപ്പ് തുറക്കുന്നു.',
        'form_open_wa' => 'വാട്സാപ്പ് വീണ്ടും തുറക്കുക', 'form_err_name' => 'ദയവായി നിങ്ങളുടെ പേര് നൽകുക.', 'form_err_phone' => 'ദയവായി 10 അക്ക വാട്സാപ്പ് നമ്പർ നൽകുക.',
        'form_err_limit' => 'വളരെയധികം അഭ്യർത്ഥനകൾ. പിന്നീട് ശ്രമിക്കുക.', 'form_err_net' => 'നെറ്റ്‌വർക്ക് പ്രശ്നം. വീണ്ടും ശ്രമിക്കുക.',
        'form_member_login' => 'അംഗമാണോ? ലോഗിൻ ചെയ്യൂ',
        'app_today' => 'ഇന്ന്', 'app_members_sec' => 'അംഗങ്ങൾ', 'app_this_month' => 'ഈ മാസം', 'app_quick' => 'പെട്ടെന്നുള്ളവ',
        'app_all_pages' => 'എല്ലാ പേജുകളും', 'app_greet_m' => 'സുപ്രഭാതം', 'app_greet_a' => 'ശുഭ ഉച്ചതിരിഞ്ഞ്', 'app_greet_e' => 'ശുഭ സായാഹ്നം',
        'tile_new_members' => 'പുതിയ അംഗങ്ങൾ', 'tile_pending' => 'അംഗീകാരം കാത്ത്', 'tile_events_today' => 'ഇന്നത്തെ പരിപാടികൾ',
        'tile_enquiries' => 'പുതിയ അന്വേഷണങ്ങൾ', 'tile_active' => 'സജീവ അംഗങ്ങൾ', 'tile_donors' => 'രക്തദാതാക്കൾ',
        'tile_committee' => 'കമ്മിറ്റി', 'tile_events_month' => 'ഈ മാസത്തെ പരിപാടികൾ', 'tile_collected' => 'ലഭിച്ച ഫീസ്',
        'tile_blood_req' => 'രക്ത അഭ്യർത്ഥനകൾ', 'tile_market' => 'മാർക്കറ്റ് സാധനങ്ങൾ', 'tile_posts' => 'ഫീഡ് പോസ്റ്റുകൾ',
        'sudo_title' => 'ഇത് നിങ്ങളാണെന്ന് ഉറപ്പാക്കൂ', 'sudo_sub' => 'തുടരാൻ നിങ്ങളുടെ 6 അക്ക ലോഗിൻ പാസ്‌കീ നൽകുക.',
        'sudo_btn' => 'ഉറപ്പാക്കുക', 'sudo_wrong' => 'തെറ്റായ പാസ്‌കീ. വീണ്ടും ശ്രമിക്കുക.',
        'ct_title' => 'സന്ദേശം അയക്കുക', 'ct_sub' => 'അംഗത്വം, പരിപാടികൾ, മറ്റെന്തും ഞങ്ങളോട് ചോദിക്കൂ. വാട്സാപ്പിൽ മറുപടി നൽകും.',
        'ct_email' => 'ഇമെയിൽ (ആവശ്യമെങ്കിൽ)', 'ct_subject' => 'വിഷയം', 'ct_message' => 'സന്ദേശം', 'ct_send' => 'സന്ദേശം അയക്കുക',
        'ct_sent' => 'സന്ദേശം അയച്ചു!', 'ct_sent_sub' => 'നന്ദി. ഞങ്ങൾ ഉടൻ ബന്ധപ്പെടും.', 'ct_again' => 'വീണ്ടും അയക്കുക',
        'ct_group' => 'വാട്സാപ്പ് ഗ്രൂപ്പ്', 'ct_group_join' => 'ഞങ്ങളുടെ ഗ്രൂപ്പിൽ ചേരൂ', 'ct_portal' => 'അംഗങ്ങളുടെ പോർട്ടൽ',
        'ct_portal_go' => 'ലോഗിൻ ചെയ്യുക / അംഗമാകുക', 'ct_err' => 'പേരും സന്ദേശവും നൽകുക.',
    ),
    );
}

function t($key) {
    static $s = null;
    if ($s === null) $s = lang_strings();
    $l = lang_current();
    if (isset($s[$l][$key])) return $s[$l][$key];
    return isset($s['en'][$key]) ? $s['en'][$key] : $key;
}
function te($key) { echo htmlspecialchars(t($key), ENT_QUOTES, 'UTF-8'); }

// Editable public texts: club_settings key + '_ml' holds the Malayalam version
function tset($value_en, $value_ml) {
    return (lang_current() === 'ml' && trim((string)$value_ml) !== '') ? $value_ml : $value_en;
}

}
