<?php
// Member status changes from the member page: activate for N days, deactivate, activate again.
// Approving with a payment goes through payment_add.php.

require __DIR__ . '/includes/init.php';
require_admin();

$id = (int)post('id');
$m = q('SELECT * FROM members WHERE id = ?', [$id])->fetch();
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !$m) {
    redirect('members.php');
}
$back = 'member_view.php?id=' . $id;
$action = post('action');

if ($action === 'activate_days') {
    // Free / trial days give access without payment, so the password is asked.
    require_verify($back);
    $days = max(1, min(366, (int)post('days')));
    $start = $m['expiry_date'] && $m['expiry_date'] >= today() ? date('Y-m-d', strtotime($m['expiry_date'] . ' +1 day')) : today();
    $end = date('Y-m-d', strtotime($start . ' +' . ($days - 1) . ' day'));
    $note = '[' . fdate(today()) . ': ' . sprintf(t_en('free_days_note'), $days) . ']';
    q("UPDATE members SET status = 'active', start_date = ?, expiry_date = ?, approved_at = COALESCE(approved_at, NOW()),
       notes = LEFT(TRIM(CONCAT(notes, ' ', ?)), 500) WHERE id = ?", [$start, $end, $note, $id]);
    flash('success', t('activated_till', fdate($end)));
} elseif ($action === 'deactivate') {
    q("UPDATE members SET status = 'inactive' WHERE id = ?", [$id]);
    flash('warning', t('member_deactivated', $m['name']));
} elseif ($action === 'activate') {
    q("UPDATE members SET status = 'active', approved_at = COALESCE(approved_at, NOW()) WHERE id = ?", [$id]);
    flash('success', t('member_activated', $m['name']));
}
redirect($back);
