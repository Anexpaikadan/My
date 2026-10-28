<?php
// SQL helpers for the installer and backup/restore (no mysqldump needed, works on shared hosting).

// Splits an SQL file into statements; understands quotes and -- / # / /* */ comments.
function split_sql(string $sql): array
{
    $out = [];
    $cur = '';
    $len = strlen($sql);
    $quote = null;
    for ($i = 0; $i < $len; $i++) {
        $c = $sql[$i];
        if ($quote !== null) {
            $cur .= $c;
            if ($c === '\\' && $i + 1 < $len) {
                $cur .= $sql[++$i];
            } elseif ($c === $quote) {
                if ($i + 1 < $len && $sql[$i + 1] === $quote) {
                    $cur .= $sql[++$i];
                } else {
                    $quote = null;
                }
            }
            continue;
        }
        if ($c === "'" || $c === '"' || $c === '`') {
            $quote = $c;
            $cur .= $c;
        } elseif (($c === '-' && substr($sql, $i, 3) === '-- ') || $c === '#' || ($c === '-' && substr($sql, $i, 3) === "--\n")) {
            $nl = strpos($sql, "\n", $i);
            $i = $nl === false ? $len : $nl;
            $cur .= "\n";
        } elseif ($c === '/' && ($sql[$i + 1] ?? '') === '*') {
            $end = strpos($sql, '*/', $i + 2);
            $i = $end === false ? $len : $end + 1;
        } elseif ($c === ';') {
            if (trim($cur) !== '') {
                $out[] = trim($cur);
            }
            $cur = '';
        } else {
            $cur .= $c;
        }
    }
    if (trim($cur) !== '') {
        $out[] = trim($cur);
    }
    return $out;
}

function run_sql(PDO $pdo, string $sql): int
{
    $n = 0;
    foreach (split_sql($sql) as $stmt) {
        $pdo->exec($stmt);
        $n++;
    }
    return $n;
}

// Full backup of all app tables as SQL text.
function dump_sql(PDO $pdo): string
{
    $tables = ['admins', 'settings', 'plans', 'members', 'payments', 'attendance', 'activities', 'acc_accounts', 'acc_categories', 'acc_entries', 'gym_leaves', 'member_freezes', 'levels', 'complaints', 'complaint_msgs'];
    $out = "-- Valley MMA Fight Club backup\n-- Made: " . date('Y-m-d H:i:s') . "\n\nSET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS = 0;\n\n";
    foreach ($tables as $t) {
        $create = $pdo->query("SHOW CREATE TABLE `$t`")->fetch(PDO::FETCH_NUM)[1];
        $out .= "DROP TABLE IF EXISTS `$t`;\n" . $create . ";\n";
        $rows = $pdo->query("SELECT * FROM `$t`", PDO::FETCH_ASSOC);
        $batch = [];
        $cols = null;
        foreach ($rows as $r) {
            $cols = $cols ?? '(`' . implode('`, `', array_keys($r)) . '`)';
            $batch[] = '(' . implode(', ', array_map(fn($v) => $v === null ? 'NULL' : $pdo->quote((string)$v), $r)) . ')';
            if (count($batch) >= 200) {
                $out .= "INSERT INTO `$t` $cols VALUES\n" . implode(",\n", $batch) . ";\n";
                $batch = [];
            }
        }
        if ($batch) {
            $out .= "INSERT INTO `$t` $cols VALUES\n" . implode(",\n", $batch) . ";\n";
        }
        $out .= "\n";
    }
    return $out . "SET FOREIGN_KEY_CHECKS = 1;\n";
}
