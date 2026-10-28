<?php
// Member freeze (accident, injury, travel …): add, change or remove from the member page.
// While frozen the member cannot mark attendance; the expiry moves on by the frozen days (asks the password).

require __DIR__ . '/includes/init.php';
require_admin();

$m = q('SELECT * FROM members WHERE id = ?', [(int)post('member_id')])->fetch();
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !$m) {
    redirect('members.php');
}
$back = 'member_view.php?id=' . $m['id'] . '#freeze';
require_verify($back);

$old = post('id') ? q('SELECT * FROM member_freezes WHERE id = ? AND member_id = ?', [(int)post('id'), $m['id']])->fetch() : null;
if (post('action') === 'delete') {
    if ($old) {
        freeze_delete($old);
        flash('success', t('freeze_removed'));
    }
    redirect($back);
}

$from = valid_date(post('from_date')) ? post('from_date') : '';
$to = valid_date(post('to_date')) ? post('to_date') : '';
if ($from === '' || $to === '') {
    flash('danger', t('leave_fill'));
    redirect($back);
}
if ($to < $from) {
    [$from, $to] = [$to, $from];
}
if (day_count($from, $to) > 366) {
    $to = date('Y-m-d', strtotime($from . ' +365 day'));
}
$reason = array_key_exists(post('reason'), FREEZE_REASONS) ? post('reason') : 'other';
$overlap = q('SELECT COUNT(*) FROM member_freezes WHERE member_id = ? AND id <> ? AND from_date <= ? AND to_date >= ?',
    [$m['id'], (int)($old['id'] ?? 0), $to, $from])->fetchColumn();
if ($overlap) {
    flash('danger', t('freeze_overlap'));
    redirect($back);
}
$fid = freeze_save($m, $from, $to, $reason, mb_substr(trim(post('note')), 0, 255), post('extend') === '1', $old ?: null);
$exp = q('SELECT expiry_date FROM members WHERE id = ?', [$m['id']])->fetchColumn();
flash('success', t('freeze_saved', date_range_text($from, $to)) . ($exp ? ' ' . t('valid_till') . ': ' . fdate($exp) : ''));
redirect('member_view.php?id=' . $m['id'] . '&fsent=' . $fid . '#freeze');
