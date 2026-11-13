<?php
// Monthly class timetable: classes (a batch on a date) with their trainer, weekly holidays, students.

// Classes of a date range with batch and trainer: date => [rows].
function class_sessions(string $first, string $last, ?int $trainerId = null, ?int $batchId = null): array
{
    $sql = 'SELECT s.*, b.name batch_name, b.start_time, b.end_time, b.capacity FROM class_sessions s JOIN batches b ON b.id = s.batch_id
            WHERE s.class_date BETWEEN ? AND ?';
    $args = [$first, $last];
    if ($trainerId !== null) {
        $sql .= ' AND s.trainer_id = ?';
        $args[] = $trainerId;
    }
    if ($batchId !== null) {
        $sql .= ' AND s.batch_id = ?';
        $args[] = $batchId;
    }
    $out = [];
    foreach (q($sql . ' ORDER BY s.class_date, b.start_time, b.id', $args)->fetchAll() as $r) {
        $out[$r['class_date']][] = $r;
    }
    return $out;
}

function timetable_month(string $month): ?array
{
    return q('SELECT * FROM timetable_months WHERE month = ?', [$month])->fetch() ?: null;
}

// Creates the classes of a month from the batches: every batch on its days, except the weekly holidays
// and gym leave days. Existing classes of the month are replaced. Returns the number of classes.
function timetable_create(string $month, string $holidays): int
{
    $first = $month . '-01';
    $last = date('Y-m-t', strtotime($first));
    $leave = day_marks($first, $last)['leave'];
    q('DELETE FROM class_sessions WHERE class_date BETWEEN ? AND ?', [$first, $last]);
    $n = 0;
    foreach (batches() as $b) {
        for ($d = $first; $d <= $last; $d = date('Y-m-d', strtotime($d . ' +1 day'))) {
            $dow = (string)date('N', strtotime($d));
            if (!str_contains((string)$b['days'], $dow) || str_contains($holidays, $dow) || isset($leave[$d])) {
                continue;
            }
            q('INSERT INTO class_sessions (class_date, batch_id, trainer_id) VALUES (?, ?, ?)', [$d, $b['id'], $b['trainer_id'] ?: null]);
            $n++;
        }
    }
    q('INSERT INTO timetable_months (month, holidays) VALUES (?, ?) ON DUPLICATE KEY UPDATE holidays = VALUES(holidays), created_at = NOW()', [$month, $holidays]);
    return $n;
}

// Students of a class: active members of the batch, with their check-in time on that date.
function class_students(int $batchId, string $date): array
{
    return q("SELECT m.id, m.name, m.adm_no, m.phone, m.photo, m.level_id, m.expiry_date, m.status, a.check_in
              FROM members m LEFT JOIN attendance a ON a.member_id = m.id AND a.att_date = ?
              WHERE m.batch_id = ? AND m.status = 'active' AND (m.expiry_date IS NULL OR m.expiry_date >= ?) ORDER BY m.name",
        [$date, $batchId, min($date, today())])->fetchAll();
}

// Calendar grid of the month's classes. $link(date) => url or null.
function class_timetable_html(string $month, array $sessions, string $holidays, array $leave, ?callable $link = null): string
{
    $first = $month . '-01';
    $last = date('Y-m-t', strtotime($first));
    $h = '<div class="table-responsive tt-wrap"><table class="tt tt-classes"><thead><tr>';
    for ($i = 1; $i <= 7; $i++) {
        $h .= '<th' . (str_contains($holidays, (string)$i) ? ' class="tt-hol"' : '') . '>' . e(t('day' . $i)) . '</th>';
    }
    $h .= '</tr></thead><tbody><tr>' . str_repeat('<td class="tt-empty"></td>', (int)date('N', strtotime($first)) - 1);
    for ($d = $first; $d <= $last; $d = date('Y-m-d', strtotime($d . ' +1 day'))) {
        $dow = (int)date('N', strtotime($d));
        if ($dow === 1 && $d !== $first) {
            $h .= '</tr><tr>';
        }
        $rows = $sessions[$d] ?? [];
        $on = array_filter($rows, fn($r) => $r['status'] === 'on');
        $isLeave = isset($leave[$d]);
        $isHol = !$on && (str_contains($holidays, (string)$dow) || $isLeave);
        $cls = ($d === today() ? ' tt-today' : '') . ($isLeave ? ' tt-leave' : ($isHol ? ' tt-rest' : '')) . ($d < today() ? ' tt-past' : '');
        $body = '<span class="tt-date">' . (int)substr($d, 8) . ($d === today() ? ' <small>' . e(t('today')) . '</small>' : '') . '</span>';
        if ($isLeave) {
            $body .= '<span class="tt-main"><i class="bi bi-calendar-x"></i> ' . e($leave[$d]['title']) . '</span>';
        } elseif ($isHol) {
            $body .= '<span class="tt-line tt-holiday">' . e(t('holiday')) . '</span>';
        }
        foreach ($rows as $r) {
            $tn = trainer_name($r['trainer_id'] !== null ? (int)$r['trainer_id'] : null);
            $body .= '<span class="tt-class' . ($r['status'] === 'off' ? ' off' : '') . '"><b>' . e(time_text($r['start_time'])) . '</b> ' . e($r['batch_name'])
                . ($tn !== '' ? '<i>' . e($tn) . '</i>' : ($r['status'] === 'on' ? '<i class="tt-warn">' . e(t('no_trainer')) . '</i>' : '')) . '</span>';
        }
        $url = $link ? $link($d) : null;
        $h .= '<td class="tt-cell' . $cls . '">' . ($url ? '<a href="' . e($url) . '">' . $body . '</a>' : '<div>' . $body . '</div>') . '</td>';
    }
    return $h . str_repeat('<td class="tt-empty"></td>', 7 - (int)date('N', strtotime($last))) . '</tr></tbody></table></div>';
}
