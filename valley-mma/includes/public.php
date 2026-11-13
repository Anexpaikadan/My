<?php
// Public website (home page, shop, rules): texts and settings the admin changes in
// "Public page" (public_settings.php), the gym rules, product images and the public bottom bar.

const PUB_SECTIONS = ['about', 'programs', 'events', 'achievements', 'fees', 'timings', 'rules', 'shop', 'contact'];

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
        'pub_achievements_title' => 'Our Champions',
        'pub_events_title'   => 'Events & Fight Nights',
        'pub_show_events'    => '1',
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
        'pub_show_rules' => '1', 'pub_show_shop' => '1', 'pub_show_contact' => '1', 'pub_show_achievements' => '1',
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

// ---- Programs and achievements -------------------------------------

// A photo path saved in the database: only the app's own folders, and only when the file is there.
function safe_img(string $path): string
{
    return preg_match('#^(assets/programs|media/(programs|achievements|events))/[\w.-]+\.(jpg|png|webp)$#', $path) && is_file(__DIR__ . '/../' . $path) ? $path : '';
}

function programs_list(bool $all = false): array
{
    static $cache = [];
    return $cache[(int)$all] ??= q('SELECT * FROM programs' . ($all ? '' : ' WHERE active = 1') . ' ORDER BY sort_order, id')->fetchAll();
}

// Program data for the pop-up on the public page.
function program_json(array $p): array
{
    return ['id' => (int)$p['id'], 'name' => $p['name'], 'short' => $p['short_text'], 'details' => (string)$p['details'],
        'for' => $p['suitable_for'], 'schedule' => $p['schedule'], 'trainer' => $p['trainer'], 'trainerAbout' => $p['trainer_about'],
        'img' => safe_img($p['image'])];
}

function achievements_public(): array
{
    return q('SELECT a.*, m.photo FROM achievements a LEFT JOIN members m ON m.id = a.member_id
              WHERE a.show_public = 1 ORDER BY a.sort_order, a.image = \'\', a.ach_date IS NULL, a.ach_date DESC, a.id DESC LIMIT 30')->fetchAll();
}

// Saves an uploaded photo into media/<folder> and returns its path ('' when no file, null when not a photo).
function save_media_upload(string $field, string $folder, int $max = 1200): ?string
{
    if (empty($_FILES[$field]['name'])) {
        return '';
    }
    $f = save_photo($_FILES[$field], $max, __DIR__ . '/../media/' . $folder);
    return $f === null ? null : 'media/' . $folder . '/' . $f;
}

function delete_media(string $path): void
{
    if (str_starts_with($path, 'media/') && safe_img($path) !== '') {
        @unlink(__DIR__ . '/../' . $path);
    }
}

// ---- WhatsApp / social link preview (Open Graph) -------------------
// WhatsApp, Facebook and Telegram show this photo, title and text under every link of the app.

function og_on(): bool
{
    return setting('og_on', '1') === '1';
}

function og_image_path(): string
{
    if (!empty($GLOBALS['vm_og_image'])) { // a page's own photo (e.g. an event)
        return (string)$GLOBALS['vm_og_image'];
    }
    $f = setting('og_img');
    return $f !== '' && is_file(__DIR__ . '/../media/' . $f) ? 'media/' . rawurlencode($f) : hero_url();
}

function og_title(string $page): string
{
    $base = setting('og_title') !== '' ? setting('og_title') : gym_title();
    return $page !== '' && $page !== $base ? $page . ' · ' . $base : $base;
}

function og_text(): string
{
    return setting('og_text') !== '' ? setting('og_text') : pub('pub_hero_text');
}

function og_tags(string $pageTitle): string
{
    if (!og_on()) {
        return '';
    }
    $img = og_image_path();
    $size = @getimagesize(__DIR__ . '/../' . rawurldecode($img));
    $query = (string)($_SERVER['QUERY_STRING'] ?? '');
    $tags = [
        'og:type' => 'website', 'og:site_name' => gym_title(), 'og:title' => og_title($pageTitle), 'og:description' => og_text(),
        'og:url' => base_url() . basename((string)($_SERVER['SCRIPT_NAME'] ?? 'index.php')) . ($query !== '' ? '?' . $query : ''),
        'og:image' => base_url() . $img, 'og:image:alt' => gym_title(),
    ];
    if ($size) {
        $tags['og:image:width'] = (string)$size[0];
        $tags['og:image:height'] = (string)$size[1];
        $tags['og:image:type'] = $size['mime'];
    }
    $h = '';
    foreach ($tags as $k => $v) {
        $h .= '<meta property="' . $k . '" content="' . e($v) . "\">\n";
    }
    return $h . "<meta name=\"twitter:card\" content=\"summary_large_image\">\n<meta name=\"description\" content=\"" . e(og_text()) . "\">\n";
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
