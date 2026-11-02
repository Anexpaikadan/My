<?php
// og_image.php — Serves club logo as image, NO login required
// Upload to: public_html/og_image.php
// This file serves the logo directly as an image response
// WhatsApp/Facebook can use: https://mynamecc.online/og_image.php

// No session, no login, no redirect — pure image output
$paths = [
    __DIR__ . '/assets/logo.jpg',
    __DIR__ . '/assets/logo.png',
];

foreach ($paths as $path) {
    if (file_exists($path)) {
        $ext  = strtolower(pathinfo($path, PATHINFO_EXTENSION));
        $mime = ($ext === 'png') ? 'image/png' : 'image/jpeg';
        $data = file_get_contents($path);

        // Allow all origins — critical for WhatsApp/Facebook
        header('Access-Control-Allow-Origin: *');
        header('Content-Type: ' . $mime);
        header('Content-Length: ' . strlen($data));
        header('Cache-Control: public, max-age=86400');
        header('X-Robots-Tag: noindex');
        echo $data;
        exit;
    }
}

// Fallback: 1x1 transparent PNG if no logo found
header('Content-Type: image/png');
echo base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==');
