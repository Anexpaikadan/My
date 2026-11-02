<?php
// ================================================================
// icons.php — one set of line icons for the whole app (24×24, stroke 2)
// Usage:  echo ic('users');            → <svg class="ic">…</svg>
//         echo ic('users', 'ic-lg');   → extra class
// Print the sprite once per page with icon_sprite() (header.php does this).
// ================================================================
if (!function_exists('ic')) {

function icon_paths() {
    return array(
        'home'     => '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h5v-6h4v6h5V9.5"/>',
        'users'    => '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.6-3.6 3.2-5.5 6.5-5.5s5.9 1.9 6.5 5.5"/><circle cx="17.5" cy="9" r="2.5"/><path d="M16.5 14.6c2.6.2 4.4 1.9 5 4.9"/>',
        'calendar' => '<rect x="3" y="4.5" width="18" height="16.5" rx="3"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/><path d="M7.5 13.5h3v3h-3z"/>',
        'droplet'  => '<path d="M12 2.8c3.8 4.3 6.5 7.9 6.5 11.4A6.5 6.5 0 0 1 5.5 14.2c0-3.5 2.7-7.1 6.5-11.4z"/><path d="M9 15a3 3 0 0 0 3 3"/>',
        'store'    => '<path d="M3.5 9 5 3.5h14L20.5 9"/><path d="M3.5 9h17v1.5a3 3 0 0 1-5.7 1.3 3 3 0 0 1-5.6 0 3 3 0 0 1-5.7-1.3z"/><path d="M5 13v8h14v-8M10 21v-5h4v5"/>',
        'star'     => '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
        'image'    => '<rect x="3" y="3.5" width="18" height="17" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15.5-5-5L5 20.5"/>',
        'user'     => '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.1-4 4.2-6 8-6s6.9 2 8 6"/>',
        'idcard'   => '<rect x="2.5" y="4.5" width="19" height="15" rx="3"/><circle cx="8.5" cy="11" r="2.3"/><path d="M5 16.5c.7-1.6 2-2.4 3.5-2.4s2.8.8 3.5 2.4M14.5 9.5h4.5M14.5 13h3"/>',
        'award'    => '<circle cx="12" cy="9" r="6"/><path d="m8.5 13.8-1.5 7.7 5-2.7 5 2.7-1.5-7.7"/>',
        'card'     => '<rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M2.5 10h19M6.5 15h4"/>',
        'trophy'   => '<path d="M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4v1.5A3.5 3.5 0 0 0 7.5 11M17 6h3v1.5a3.5 3.5 0 0 1-3.5 3.5M12 14v3.5M8 21h8M9.5 17.5h5V21h-5z"/>',
        'ball'     => '<circle cx="12" cy="12" r="9"/><path d="m12 7.5 3.4 2.5-1.3 4h-4.2l-1.3-4z"/><path d="M12 3v4.5M15.4 10l4.3-1.4M14.1 14l2.7 3.6M9.9 14l-2.7 3.6M8.6 10 4.3 8.6"/>',
        'masks'    => '<path d="M3 4.5c3 1.2 6 1.2 9 0v6a4.5 4.5 0 0 1-9 0z"/><path d="M12 8.5c3 1.2 6 1.2 9 0v6a4.5 4.5 0 0 1-9 0"/><path d="M5.5 8.5h1M8.5 8.5h1M14.5 12.5h1M17.5 12.5h1M15 16.5c.9.6 2.1.6 3 0M6 12.5c.9-.6 2.1-.6 3 0"/>',
        'flower'   => '<circle cx="12" cy="12" r="2.5"/><path d="M12 9.5C10 7.5 10 4.5 12 3c2 1.5 2 4.5 0 6.5zM12 14.5c-2 2-2 5 0 6.5 2-1.5 2-4.5 0-6.5zM9.5 12c-2-2-5-2-6.5 0 1.5 2 4.5 2 6.5 0zM14.5 12c2-2 5-2 6.5 0-1.5 2-4.5 2-6.5 0z"/>',
        'vote'     => '<path d="M4 13h16v8H4z"/><path d="M8 13V5.5A1.5 1.5 0 0 1 9.5 4h5A1.5 1.5 0 0 1 16 5.5V13"/><path d="m10 8.5 1.5 1.5 3-3"/>',
        'heart'    => '<path d="M12 20.5s-8-4.6-8-10.4A4.6 4.6 0 0 1 12 7.3a4.6 4.6 0 0 1 8 2.8c0 5.8-8 10.4-8 10.4z"/>',
        'coins'    => '<ellipse cx="9" cy="6.5" rx="6" ry="3"/><path d="M3 6.5v4c0 1.7 2.7 3 6 3s6-1.3 6-3v-4"/><path d="M9 13.5v4c0 1.7 2.7 3 6 3s6-1.3 6-3v-4c0-1.7-2.7-3-6-3"/>',
        'megaphone'=> '<path d="M3 10v4a1 1 0 0 0 1 1h3l8 5V4L7 9H4a1 1 0 0 0-1 1z"/><path d="M18.5 8.5a5 5 0 0 1 0 7M7.5 15l1.5 6"/>',
        'shield'   => '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8.3 7.5 9.5 4.3-1.2 7.5-4.9 7.5-9.5V6z"/><path d="m9 12 2 2 4-4"/>',
        'settings' => '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
        'logout'   => '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/>',
        'menu'     => '<path d="M4 7h16M4 12h16M4 17h10"/>',
        'x'        => '<path d="M6 6l12 12M18 6 6 18"/>',
        'back'     => '<path d="M15 18l-6-6 6-6"/>',
        'chevron'  => '<path d="m6 9 6 6 6-6"/>',
        'next'     => '<path d="m9 6 6 6-6 6"/>',
        'bell'     => '<path d="M6 8.5a6 6 0 0 1 12 0c0 6.5 2.5 8 2.5 8h-17S6 15 6 8.5z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
        'bolt'     => '<path d="M13 2.5 4.5 13.5H12l-1 8 8.5-11H12z"/>',
        'wallet'   => '<path d="M19 7V5.5A1.5 1.5 0 0 0 17.5 4H5a2 2 0 0 0 0 4h15v12H5a2 2 0 0 1-2-2V6"/><circle cx="16" cy="14" r="1.3"/>',
        'palette'  => '<path d="M12 3a9 9 0 1 0 0 18c1.2 0 1.8-.8 1.8-1.8 0-.5-.2-.9-.5-1.2-.3-.4-.5-.8-.5-1.3 0-1 .8-1.7 1.8-1.7h2.1A4.3 4.3 0 0 0 21 10.7C21 6.4 17 3 12 3z"/><circle cx="7.5" cy="11.5" r="1.2"/><circle cx="10" cy="7.5" r="1.2"/><circle cx="14.5" cy="7.5" r="1.2"/>',
        'tent'     => '<path d="M12 3 2.5 20h19z"/><path d="M12 3v17M8.5 20 12 13l3.5 7"/>',
        'file'     => '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
        'plus'     => '<path d="M12 5v14M5 12h14"/>',
        'search'   => '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
        'globe'    => '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
        'qr'       => '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M14 14h3v3h-3zM20 14v.01M14 20.5h.01M17.5 17.5H21V21h-3.5z"/>',
        'sparkle'  => '<path d="M12 3c.6 4.6 2.4 6.4 7 7-4.6.6-6.4 2.4-7 7-.6-4.6-2.4-6.4-7-7 4.6-.6 6.4-2.4 7-7z"/><path d="M19 15.5c.2 1.7.8 2.3 2.5 2.5-1.7.2-2.3.8-2.5 2.5-.2-1.7-.8-2.3-2.5-2.5 1.7-.2 2.3-.8 2.5-2.5z"/>',
        'chart'    => '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
        'whatsapp' => '<path d="M4 20.5 5.2 16A8.5 8.5 0 1 1 8.4 19z"/><path d="M9 8.5c0 3.6 2.9 6.5 6.5 6.5l1-1.5-2-1-1 .8a4.6 4.6 0 0 1-2.8-2.8l.8-1-1-2z"/>',
        'clipboard'=> '<rect x="5" y="4" width="14" height="17" rx="2.5"/><path d="M9 4.5V3h6v1.5M9 10h6M9 14h6M9 18h3"/>',
        'check'    => '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
        'download' => '<path d="M12 3v12M7 10l5 5 5-5M4 20h16"/>',
        'scan'     => '<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16M4 12h16"/>',
        'login'    => '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5M15 12H3"/>',
        'phone'    => '<path d="M5 3.5h3.5l1.5 4.5-2.3 1.5a11 11 0 0 0 6.8 6.8l1.5-2.3 4.5 1.5V19a1.5 1.5 0 0 1-1.6 1.5C10.7 20 4 13.3 3.5 5.1A1.5 1.5 0 0 1 5 3.5z"/>',
        'map'      => '<path d="M12 21s-6.5-5.6-6.5-11A6.5 6.5 0 0 1 18.5 10c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.5"/>',
        'mail'     => '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="m3.5 6.5 8.5 6 8.5-6"/>',
        'eye'      => '<path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z"/><circle cx="12" cy="12" r="3"/>',
        'edit'     => '<path d="M4 20h4l11-11a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
        'layout'   => '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/>',
        'install'  => '<rect x="6" y="2.5" width="12" height="19" rx="3"/><path d="M12 7v7M9 11l3 3 3-3M10.5 18.5h3"/>',
    );
}

// 3D picture icon (assets/icons/3d/<name>.webp) — used on app tiles
function app_img($name, $size = 40) {
    return '<img class="app-img" src="' . url('assets/icons/3d/' . $name . '.webp') . '" alt="" width="' . (int)$size . '" height="' . (int)$size . '" loading="lazy" decoding="async">';
}

function ic($name, $cls = '') {
    return '<svg class="ic' . ($cls ? ' ' . $cls : '') . '" aria-hidden="true" focusable="false"><use href="#i-' . $name . '"/></svg>';
}

function icon_sprite() {
    $out = '<svg xmlns="http://www.w3.org/2000/svg" style="position:absolute;width:0;height:0;overflow:hidden" aria-hidden="true"><defs>';
    foreach (icon_paths() as $n => $p) {
        $out .= '<symbol id="i-' . $n . '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' . $p . '</symbol>';
    }
    return $out . '</defs></svg>';
}

// Every member-area module, in one place: used by the dashboard app grid,
// the side menu and the desktop nav.  [file, label, icon, tone, group, img]
// tone = colour for line-icon tiles; img = 3D picture in assets/icons/3d/<img>.webp
function app_modules() {
    return array(
        array('modules/feed.php',          'Feed',          'bolt',     'coral',  'Club', 'feed'),
        array('modules/events.php',        'Events',        'calendar', 'violet', 'Club', 'events'),
        array('modules/members.php',       'Members',       'users',    'teal',   'Club', 'members'),
        array('modules/blood.php',         'Blood Hub',     'droplet',  'rose',   'Club', 'blood'),
        array('modules/market.php',        'Market',        'store',    'lime',   'Club', 'market'),
        array('modules/gallery.php',       'Gallery',       'image',    'sky',    'Club', 'gallery'),
        array('modules/skills.php',        'Talents',       'star',     'amber',  'Club', 'talents'),
        array('modules/football.php',      'Football',      'ball',     'lime',   'Activities', 'football'),
        array('modules/arts_festival.php', 'Arts Festival', 'masks',    'violet', 'Activities', 'arts'),
        array('modules/onam.php',          'Onam',          'flower',   'amber',  'Activities', 'onam'),
        array('modules/fest_manager.php',  'Fests',         'tent',     'coral',  'Activities', 'fests'),
        array('modules/election.php',      'Elections',     'vote',     'sky',    'Activities', 'elections'),
        array('modules/creative_studio.php','Poster Studio','palette',  'rose',   'Activities', 'poster'),
        array('modules/donation.php',      'Donations',     'heart',    'rose',   'Support', 'donations'),
        array('modules/crowdfund.php',     'Crowd Fund',    'coins',    'amber',  'Support', 'crowdfund'),
        array('modules/groundfund.php',    'Ground Fund',   'wallet',   'teal',   'Support', 'groundfund'),
        array('modules/profile.php',       'Profile',       'user',     'teal',   'Me', 'profile'),
        array('modules/idcard.php',        'ID Card',       'idcard',   'sky',    'Me', 'idcard'),
        array('modules/certificate.php',   'Certificates',  'award',    'amber',  'Me', 'certificates'),
        array('modules/subscription.php',  'Subscription',  'card',     'violet', 'Me', 'subscription'),
    );
}

// One-line description under each app card (dashboard, homepage)
function app_desc($file) {
    $d = array(
        'modules/feed.php'=>'Posts, photos & videos', 'modules/events.php'=>'What\'s coming up',
        'modules/members.php'=>'Everyone in the club', 'modules/blood.php'=>'Find & request donors',
        'modules/market.php'=>'Buy & sell locally', 'modules/gallery.php'=>'Club photo albums',
        'modules/skills.php'=>'Members\' talents', 'modules/football.php'=>'Fixtures & standings',
        'modules/arts_festival.php'=>'Programs & results', 'modules/onam.php'=>'Celebrations & sadya',
        'modules/fest_manager.php'=>'Contests & entries', 'modules/election.php'=>'Vote for the committee',
        'modules/creative_studio.php'=>'Make posters fast', 'modules/donation.php'=>'Give to a cause',
        'modules/crowdfund.php'=>'Raise funds together', 'modules/groundfund.php'=>'Club ground fund',
        'modules/profile.php'=>'Your details', 'modules/idcard.php'=>'Digital member card',
        'modules/certificate.php'=>'Achievements & awards', 'modules/subscription.php'=>'Membership fee',
        'admin.php'=>'Approvals & members', 'modules/admin_subscription.php'=>'Fee payments',
        'modules/broadcast.php'=>'Message all on WhatsApp', 'modules/settings.php'=>'Website & club setup',
    );
    return isset($d[$file]) ? $d[$file] : '';
}

// Bootstrap Icon, tile colour and Malayalam name for each page (new Bootstrap design)
function app_meta($file) {
    $m = array(
        'dashboard.php'                 => array('house-door-fill',   'c-navy',   'ഹോം'),
        'index.php'                     => array('globe2',            'c-slate',  'വെബ്സൈറ്റ്'),
        'modules/feed.php'              => array('lightning-charge-fill','c-red',  'ഫീഡ്'),
        'modules/events.php'            => array('calendar-event-fill','c-violet','പരിപാടികൾ'),
        'modules/members.php'           => array('people-fill',       'c-blue',   'അംഗങ്ങൾ'),
        'modules/blood.php'             => array('droplet-fill',      'c-rose',   'ബ്ലഡ് ഹബ്'),
        'modules/market.php'            => array('shop',              'c-green',  'മാർക്കറ്റ്'),
        'modules/gallery.php'           => array('images',            'c-teal',   'ഗാലറി'),
        'modules/skills.php'            => array('star-fill',         'c-amber',  'കഴിവുകൾ'),
        'modules/football.php'          => array('dribbble',          'c-green',  'ഫുട്ബോൾ'),
        'modules/arts_festival.php'     => array('mask',              'c-violet', 'കലോത്സവം'),
        'modules/onam.php'              => array('flower1',           'c-amber',  'ഓണം'),
        'modules/fest_manager.php'      => array('trophy-fill',       'c-red',    'ഫെസ്റ്റുകൾ'),
        'modules/election.php'          => array('check2-square',     'c-blue',   'തിരഞ്ഞെടുപ്പ്'),
        'modules/creative_studio.php'   => array('palette-fill',      'c-pink',   'പോസ്റ്റർ സ്റ്റുഡിയോ'),
        'modules/donation.php'          => array('heart-fill',        'c-rose',   'സംഭാവന'),
        'modules/crowdfund.php'         => array('cash-coin',         'c-amber',  'ക്രൗഡ് ഫണ്ട്'),
        'modules/groundfund.php'        => array('wallet2',           'c-teal',   'ഗ്രൗണ്ട് ഫണ്ട്'),
        'modules/profile.php'           => array('person-circle',     'c-navy',   'പ്രൊഫൈൽ'),
        'modules/idcard.php'            => array('person-vcard-fill', 'c-blue',   'ഐഡി കാർഡ്'),
        'modules/certificate.php'       => array('award-fill',        'c-amber',  'സർട്ടിഫിക്കറ്റുകൾ'),
        'modules/subscription.php'      => array('credit-card-fill',  'c-violet', 'അംഗത്വ ഫീസ്'),
        'admin.php'                     => array('shield-lock-fill',  'c-red',    'അഡ്മിൻ പാനൽ'),
        'modules/admin_subscription.php'=> array('receipt',           'c-amber',  'പേയ്മെന്റുകൾ'),
        'modules/broadcast.php'         => array('megaphone-fill',    'c-green',  'വാട്സാപ്പ് ബ്രോഡ്കാസ്റ്റ്'),
        'modules/settings.php'          => array('gear-fill',         'c-slate',  'ക്ലബ് ക്രമീകരണങ്ങൾ'),
        'modules/site.php'              => array('window-desktop',    'c-blue',   'പബ്ലിക് വെബ്സൈറ്റ്'),
        'modules/enquiries.php'         => array('inbox-fill',        'c-red',    'അന്വേഷണങ്ങൾ'),
        'more.php'                      => array('grid-3x3-gap-fill', 'c-navy',   'കൂടുതൽ'),
    );
    return isset($m[$file]) ? $m[$file] : array('app', 'c-slate', '');
}
// Label in the chosen language
function app_label($file, $en) {
    if (function_exists('lang_current') && lang_current() === 'ml') { $m = app_meta($file); if ($m[2] !== '') return $m[2]; }
    return $en;
}

function admin_modules() {
    return array(
        array('admin.php',                       'Admin Panel',   'shield',    'coral', 'Admin', 'admin'),
        array('modules/admin_subscription.php',  'Payments',      'card',      'amber', 'Admin', 'payments'),
        array('modules/broadcast.php',           'WA Broadcast',  'megaphone', 'lime', 'Admin', 'broadcast'),
        array('modules/site.php',                'Public Website','globe',     'sky',   'Admin', 'website'),
        array('modules/enquiries.php',           'Enquiries',     'mail',      'coral', 'Admin', 'feed'),
        array('modules/settings.php',            'Club Settings', 'settings',  'slate', 'Admin', 'settings'),
    );
}

}
