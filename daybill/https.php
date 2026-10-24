<?php
// HTTPS is required for every page: plain http:// is redirected (GET) or refused (forms/uploads),
// and browsers are told to use only HTTPS for this site from now on.

function is_https(): bool
{
    return (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
        || ($_SERVER['SERVER_PORT'] ?? '') == 443
        || strtolower($_SERVER['HTTP_X_FORWARDED_PROTO'] ?? '') === 'https'; // behind a hosting proxy/CDN
}

if (PHP_SAPI !== 'cli') {
    if (!is_https()) {
        $host = preg_replace('/:\d+$/', '', $_SERVER['HTTP_HOST'] ?? 'localhost');
        if (in_array($_SERVER['REQUEST_METHOD'] ?? 'GET', ['GET', 'HEAD'], true)) {
            header('Location: https://' . $host . ($_SERVER['REQUEST_URI'] ?? '/'), true, 301);
        } else {
            http_response_code(403); // never accept passwords or files over plain http
            header('Content-Type: text/plain; charset=utf-8');
            echo "HTTPS is required: https://$host/";
        }
        exit;
    }
    header('Strict-Transport-Security: max-age=31536000');
}
