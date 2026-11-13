<?php
// Events and fight nights: helpers for the admin page, the public event page and the member app.

const EVENT_KINDS = ['fight' => 'bi-trophy-fill', 'event' => 'bi-calendar-event-fill', 'seminar' => 'bi-mortarboard-fill',
    'grading' => 'bi-award-fill', 'camp' => 'bi-fire', 'other' => 'bi-star-fill'];

function events_upcoming(bool $publicOnly = true, int $limit = 12): array
{
    return q('SELECT e.*, (SELECT COUNT(*) FROM event_regs r WHERE r.event_id = e.id AND r.status <> \'cancelled\') regs
              FROM events e WHERE e.event_date >= ?' . ($publicOnly ? ' AND e.show_public = 1' : '') . ' ORDER BY e.event_date, e.start_time LIMIT ' . $limit,
        [today()])->fetchAll();
}

function event_when(array $ev): string
{
    return t('day' . date('N', strtotime($ev['event_date']))) . ', ' . date('d M Y', strtotime($ev['event_date']))
        . ($ev['start_time'] ? ' · ' . date('g:i A', strtotime($ev['start_time'])) : '');
}

// '' when people can register, otherwise the reason (text key).
function event_closed(array $ev): string
{
    if ($ev['event_date'] < today()) {
        return 'ev_over';
    }
    if (!$ev['reg_open'] || ($ev['reg_last'] && $ev['reg_last'] < today())) {
        return 'ev_reg_closed';
    }
    if ($ev['capacity'] > 0) {
        $n = (int)q("SELECT COUNT(*) FROM event_regs WHERE event_id = ? AND status <> 'cancelled'", [$ev['id']])->fetchColumn();
        if ($n >= $ev['capacity']) {
            return 'ev_full';
        }
    }
    return '';
}

function event_url(array $ev): string
{
    return base_url() . 'event.php?id=' . (int)$ev['id'];
}

// WhatsApp text to invite people to the event.
function event_text(array $ev): string
{
    $out = '*' . $ev['title'] . "*\n📅 " . event_when($ev);
    if ($ev['venue'] !== '') {
        $out .= "\n📍 " . $ev['venue'];
    }
    if ((float)$ev['fee'] > 0) {
        $out .= "\n💰 " . t('ev_fee') . ': ' . money($ev['fee']);
    }
    if (trim((string)$ev['description']) !== '') {
        $out .= "\n\n" . trim($ev['description']);
    }
    return $out . "\n\n" . t('ev_register_here') . ': ' . event_url($ev) . "\n– " . gym_title();
}

// Date badge + title card used in sliders and lists.
function event_card_html(array $ev, string $href): string
{
    $img = safe_img($ev['image']);
    return '<a href="' . e($href) . '" class="ev-card">'
        . '<span class="ev-img"' . ($img !== '' ? ' style="background-image:url(\'' . e($img) . '\')"' : '') . '>'
        . ($img === '' ? '<i class="bi ' . (EVENT_KINDS[$ev['kind']] ?? 'bi-star-fill') . '"></i>' : '')
        . '<span class="ev-date"><b>' . date('d', strtotime($ev['event_date'])) . '</b>' . e(date('M', strtotime($ev['event_date']))) . '</span>'
        . '<span class="ev-kind">' . e(t('evk_' . $ev['kind'])) . '</span></span>'
        . '<span class="ev-body"><span class="ev-title">' . e($ev['title']) . '</span>'
        . '<span class="ev-meta"><i class="bi bi-clock"></i> ' . e(event_when($ev)) . '</span>'
        . ($ev['venue'] !== '' ? '<span class="ev-meta"><i class="bi bi-geo-alt"></i> ' . e($ev['venue']) . '</span>' : '')
        . '</span></a>';
}
