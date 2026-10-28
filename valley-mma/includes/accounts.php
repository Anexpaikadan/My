<?php
// Accounts helpers: ledger rows, account balances and totals.
// Membership payments (payments table) count as income automatically, in the category
// "acc_fee_category" and the account set for their payment method (Accounts → Settings).

function acc_accounts(bool $all = false): array
{
    return q('SELECT * FROM acc_accounts' . ($all ? '' : ' WHERE active = 1') . ' ORDER BY sort_order, id')->fetchAll();
}

function acc_categories(?string $type = null, bool $all = false): array
{
    $w = [];
    $a = [];
    if ($type) {
        $w[] = 'type = ?';
        $a[] = $type;
    }
    if (!$all) {
        $w[] = 'active = 1';
    }
    return q('SELECT * FROM acc_categories' . ($w ? ' WHERE ' . implode(' AND ', $w) : '') . ' ORDER BY type, sort_order, name', $a)->fetchAll();
}

function acc_fee_category(): int
{
    return (int)setting('acc_fee_category', '1');
}

// SQL CASE that turns a payment method into the account id it is paid into.
function acc_method_case(): string
{
    $parts = [];
    foreach (['cash', 'upi', 'card', 'bank'] as $m) {
        $parts[] = "WHEN '$m' THEN " . (int)setting('acc_map_' . $m, $m === 'cash' ? '1' : '2');
    }
    return 'CASE p.method ' . implode(' ', $parts) . ' ELSE 1 END';
}

// One list of money movements: own entries + membership payments.
// Columns: src, id, no, d, type, category_id, account_id, to_account_id, amount, party, description, ref_no
function acc_union_sql(): string
{
    $fee = acc_fee_category();
    return "SELECT 'entry' src, e.id, e.voucher_no no, e.entry_date d, e.type, e.category_id, e.account_id, e.to_account_id,
                   e.amount, e.party, e.description, e.ref_no
            FROM acc_entries e
            UNION ALL
            SELECT 'payment', p.id, p.receipt_no, p.pay_date, 'income', $fee, " . acc_method_case() . ", NULL,
                   p.paid, m.name, CONCAT('Receipt #', p.receipt_no), p.upi_ref
            FROM payments p JOIN members m ON m.id = p.member_id WHERE p.paid > 0";
}

// Ledger rows with filters: from, to, type, category, account, s (search).
function acc_ledger(array $f): array
{
    $w = ['x.d BETWEEN ? AND ?'];
    $a = [$f['from'], $f['to']];
    if (!empty($f['type'])) {
        $w[] = 'x.type = ?';
        $a[] = $f['type'];
    }
    if (!empty($f['category'])) {
        $w[] = 'x.category_id = ?';
        $a[] = (int)$f['category'];
    }
    if (!empty($f['account'])) {
        $w[] = '(x.account_id = ? OR x.to_account_id = ?)';
        array_push($a, (int)$f['account'], (int)$f['account']);
    }
    if (!empty($f['s'])) {
        $w[] = '(x.party LIKE ? OR x.description LIKE ? OR x.ref_no LIKE ? OR x.no = ?)';
        array_push($a, '%' . $f['s'] . '%', '%' . $f['s'] . '%', '%' . $f['s'] . '%', (int)$f['s']);
    }
    return q('SELECT x.*, c.name category, ac.name account, ta.name to_account FROM (' . acc_union_sql() . ') x
              LEFT JOIN acc_categories c ON c.id = x.category_id
              LEFT JOIN acc_accounts ac ON ac.id = x.account_id
              LEFT JOIN acc_accounts ta ON ta.id = x.to_account_id
              WHERE ' . implode(' AND ', $w) . ' ORDER BY x.d, x.src DESC, x.id', $a)->fetchAll();
}

// Effect of a row on an account (or on all accounts when $account is 0).
function acc_effect(array $r, int $account = 0): float
{
    $amt = (float)$r['amount'];
    if ($r['type'] === 'transfer') {
        if (!$account) {
            return 0;
        }
        return ((int)$r['to_account_id'] === $account ? $amt : 0) - ((int)$r['account_id'] === $account ? $amt : 0);
    }
    if ($account && (int)$r['account_id'] !== $account) {
        return 0;
    }
    return $r['type'] === 'income' ? $amt : -$amt;
}

// Balance of one account (or all accounts) at the end of $date (null = today and later too).
function acc_balance(int $account = 0, ?string $before = null): float
{
    $opening = $account
        ? (float)q('SELECT opening_balance FROM acc_accounts WHERE id = ?', [$account])->fetchColumn()
        : (float)q('SELECT COALESCE(SUM(opening_balance), 0) FROM acc_accounts')->fetchColumn();
    $sql = 'SELECT
              COALESCE(SUM(CASE WHEN type = \'income\' AND (? = 0 OR account_id = ?) THEN amount END), 0)
            - COALESCE(SUM(CASE WHEN type = \'expense\' AND (? = 0 OR account_id = ?) THEN amount END), 0)
            + COALESCE(SUM(CASE WHEN type = \'transfer\' AND ? <> 0 AND to_account_id = ? THEN amount END), 0)
            - COALESCE(SUM(CASE WHEN type = \'transfer\' AND ? <> 0 AND account_id = ? THEN amount END), 0)
            FROM (' . acc_union_sql() . ') x' . ($before ? ' WHERE x.d < ?' : '');
    $args = array_merge(array_fill(0, 8, $account), $before ? [$before] : []);
    return $opening + (float)q($sql, $args)->fetchColumn();
}

// Income and expense totals per category for a period.
function acc_by_category(string $from, string $to): array
{
    return q('SELECT x.type, x.category_id, COALESCE(c.name, \'-\') category, SUM(x.amount) total, COUNT(*) n
              FROM (' . acc_union_sql() . ') x LEFT JOIN acc_categories c ON c.id = x.category_id
              WHERE x.type <> \'transfer\' AND x.d BETWEEN ? AND ? GROUP BY x.type, x.category_id, c.name ORDER BY x.type, total DESC',
        [$from, $to])->fetchAll();
}

function acc_totals(string $from, string $to): array
{
    $r = q('SELECT COALESCE(SUM(CASE WHEN type = \'income\' THEN amount END), 0) inc,
                   COALESCE(SUM(CASE WHEN type = \'expense\' THEN amount END), 0) exp
            FROM (' . acc_union_sql() . ') x WHERE x.d BETWEEN ? AND ?', [$from, $to])->fetch();
    return ['income' => (float)$r['inc'], 'expense' => (float)$r['exp'], 'profit' => (float)$r['inc'] - (float)$r['exp']];
}

function next_voucher_no(): int
{
    return max(1, (int)q('SELECT COALESCE(MAX(voucher_no), 0) + 1 FROM acc_entries')->fetchColumn());
}

function acc_type_badge(string $type): string
{
    $cls = ['income' => 'success', 'expense' => 'danger', 'transfer' => 'secondary'][$type] ?? 'secondary';
    return '<span class="badge bg-' . $cls . '" data-en="' . e(t_en('acc_' . $type)) . '">' . e(t('acc_' . $type)) . '</span>';
}
