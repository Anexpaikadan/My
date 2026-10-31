<?php
// Public website (home page, shop, rules): texts and settings the admin changes in
// "Public page" (public_settings.php), the gym rules, product images and the public bottom bar.

const PUB_SECTIONS = ['about', 'programs', 'fees', 'timings', 'rules', 'shop', 'contact'];

function pub_defaults(): array
{
    return [
        'pub_hero_img'       => '',
        'pub_hero_title'     => 'Train with Champions',
        'pub_hero_text'      => 'MMA · Boxing · Muay Thai · Fitness – for beginners, kids and fighters in Pandikkad.',
        'pub_join_text'      => 'Join Us',
        'pub_trial_text'     => 'Book Your Free Trial',
        'pub_about_title'    => 'Why Valley MMA',
        'pub_about_text'     => "Real fight training from coaches who compete.\nA friendly team for beginners – no experience needed.\nGet fit, learn to defend yourself and build confidence.",
        'pub_programs_title' => 'Programs',
        'pub_programs'       => "MMA | Striking, wrestling and ground work – the complete fight game\nBoxing | Footwork, defence and powerful punches\nMuay Thai | Kicks, knees, elbows and clinch work\nFitness | Strength, stamina and fat loss with fight conditioning",
        'pub_fees_title'     => 'Membership Fees',
        'pub_fees_note'      => 'One-time admission fee: ₹500. Renew every 30 days.',
        'pub_timings_title'  => 'Class Timings',
        'pub_timings'        => "Monday – Saturday | 6:00 AM – 8:00 AM\nMonday – Saturday | 5:00 PM – 9:00 PM\nSunday | Closed",
        'pub_rules_title'    => 'Valley Rules',
        'pub_shop_title'     => 'Fight Shop',
        'pub_shop_text'      => 'Gloves, wraps, shin guards and more – ask us on WhatsApp.',
        'pub_contact_title'  => 'Visit Us',
        'pub_address'        => 'Valley MMA Fight Club, Pandikkad, Malappuram, Kerala',
        'pub_map_url'        => '',
        'pub_instagram'      => '',
        'pub_whatsapp'       => '',
        'shop_whatsapp'      => '',
        'pub_show_about' => '1', 'pub_show_programs' => '1', 'pub_show_fees' => '1', 'pub_show_timings' => '1',
        'pub_show_rules' => '1', 'pub_show_shop' => '1', 'pub_show_contact' => '1',
    ];
}

function pub(string $k): string
{
    return setting($k, pub_defaults()[$k] ?? '');
}

function pub_on(string $section): bool
{
    return pub('pub_show_' . $section) === '1';
}

// "Title | text" lines → [[title, text], …]
function pub_lines(string $k): array
{
    $out = [];
    foreach (preg_split('/\R/', pub($k)) as $line) {
        $line = trim($line);
        if ($line === '') {
            continue;
        }
        $parts = array_map('trim', explode('|', $line, 2));
        $out[] = [$parts[0], $parts[1] ?? ''];
    }
    return $out;
}

function hero_url(): string
{
    $f = pub('pub_hero_img');
    return $f !== '' && is_file(__DIR__ . '/../media/' . $f) ? 'media/' . rawurlencode($f) : 'assets/hero.jpg';
}

// WhatsApp number for enquiries (shop / join).
function pub_wa_phone(string $k = 'pub_whatsapp'): string
{
    return pub($k) !== '' ? pub($k) : (pub('pub_whatsapp') !== '' ? pub('pub_whatsapp') : setting('phone1'));
}

// ---- Gym rules ----------------------------------------------------

function rules_default(): array
{
    return [
        ['icon' => '📜', 'title' => 'Basic Rules', 'rules' => [
            'Bring your water bottle, gloves and towel to every session.',
            'Renew your fee every 30 days.',
            'Missed days are not deducted from the fee.',
            'A fee hold is allowed only for a break of one month or more – inform the manager in advance.',
            'After a break of six months or more, you must rejoin as a new member.',
            'Check the group message every day – it is mandatory.',
            'For any questions, contact your manager.',
        ]],
        ['icon' => '🚪', 'title' => 'At the Gate', 'rules' => [
            'Have your hand wraps on before the session starts.',
            'Late? Do 3 push-ups for every minute you are late.',
            'Follow the rules – or leave the mat.',
        ]],
        ['icon' => '📋', 'title' => 'Training Rules', 'rules' => [
            'One week, one target – stay focused on it.',
            'Train with your group.',
            'Ask your questions during rest time.',
            'Work hard during the round time.',
            'Save the talking for after the session.',
            'Let the coach coach – listen and follow.',
        ]],
    ];
}

function gym_rules(): array
{
    $r = json_decode(setting('gym_rules'), true);
    return is_array($r) && $r ? $r : rules_default();
}

// Rules as editable text: "# 📜 Basic Rules" starts a section, every other line is a rule.
function rules_to_text(array $rules): string
{
    $out = [];
    foreach ($rules as $s) {
        $out[] = '# ' . trim(($s['icon'] ?? '') . ' ' . $s['title']);
        foreach ($s['rules'] as $r) {
            $out[] = $r;
        }
        $out[] = '';
    }
    return trim(implode("\n", $out));
}

function rules_from_text(string $text): array
{
    $out = [];
    foreach (preg_split('/\R/', $text) as $line) {
        $line = trim(preg_replace('/^[-•*]\s*/u', '', trim($line)));
        if ($line === '') {
            continue;
        }
        if (str_starts_with($line, '#')) {
            $title = trim(ltrim($line, '#'));
            $icon = '';
            if (preg_match('/^(\X)\s+(.+)$/u', $title, $mm) && !preg_match('/[\p{L}\p{N}]/u', $mm[1])) {
                [$icon, $title] = [$mm[1], $mm[2]];
            }
            $out[] = ['icon' => $icon, 'title' => mb_substr($title, 0, 60), 'rules' => []];
        } else {
            if (!$out) {
                $out[] = ['icon' => '📜', 'title' => 'Rules', 'rules' => []];
            }
            $out[count($out) - 1]['rules'][] = mb_substr($line, 0, 250);
        }
    }
    return array_values(array_filter($out, fn($s) => $s['rules']));
}

function rules_html(): string
{
    $h = '<div class="rules">';
    foreach (gym_rules() as $s) {
        $h .= '<section class="rule-sec"><h3><span>' . e($s['icon'] ?? '') . '</span>' . e($s['title']) . '</h3><ol>';
        foreach ($s['rules'] as $r) {
            $h .= '<li>' . e($r) . '</li>';
        }
        $h .= '</ol></section>';
    }
    return $h . '</div>';
}

function rules_text(): string
{
    $out = '*' . mb_strtoupper(pub('pub_rules_title')) . ' – ' . gym_title() . '*';
    foreach (gym_rules() as $s) {
        $out .= "\n\n" . trim(($s['icon'] ?? '') . ' *' . $s['title'] . '*');
        foreach ($s['rules'] as $i => $r) {
            $out .= "\n" . ($i + 1) . '. ' . $r;
        }
    }
    return $out . "\n\n" . base_url() . 'rules.php';
}

// ---- Products -----------------------------------------------------

function product_images(array $p): array
{
    $list = json_decode((string)($p['images'] ?? ''), true);
    return array_values(array_filter(is_array($list) ? $list : [], fn($f) => is_string($f) && is_file(__DIR__ . '/../media/products/' . $f)));
}

function product_img_url(string $f): string
{
    return 'media/products/' . rawurlencode($f);
}

function product_price_html(array $p): string
{
    $sale = $p['sale_price'] !== null && (float)$p['sale_price'] > 0 && (float)$p['sale_price'] < (float)$p['price'];
    return $sale
        ? '<span class="price-sale">' . money($p['sale_price']) . '</span> <s class="price-old">' . money($p['price']) . '</s>'
        : '<span class="price-sale">' . money($p['price']) . '</span>';
}

// ---- Public bottom bar: Home · Shop · Login / My account -------------

function public_nav(string $on): string
{
    $acc = admin() ? ['index.php', 'bi-speedometer2', t('dashboard')]
        : (member_user() ? ['me.php', 'bi-person-circle', t('my_account')] : ['login.php', 'bi-box-arrow-in-right', t('login')]);
    $items = [
        ['home.php', 'home', 'bi-house-door-fill', t('home'), ''],
        ['shop.php', 'shop', 'bi-bag-fill', pub('pub_shop_title'), ' center'],
        [$acc[0], 'login', $acc[1], $acc[2], ''],
    ];
    $h = '<nav class="bottom-nav pub-nav d-print-none" aria-label="Menu">';
    foreach ($items as [$href, $key, $icon, $label, $cls]) {
        $h .= '<a href="' . e($href) . '" class="' . ($on === $key ? 'on' : '') . $cls . '"><span class="bn-ico"><i class="bi ' . $icon . '"></i></span><span>' . e($label) . '</span></a>';
    }
    return $h . '</nav>';
}
