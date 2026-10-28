<?php
// ---------------------------------------------------------------
// Valley MMA Fight Club – configuration
// XAMPP defaults are shown. On hosting, copy the database name,
// user, password and host from your hosting control panel.
// ---------------------------------------------------------------

return [
    'db_host' => '127.0.0.1',
    'db_port' => 3306,
    'db_name' => 'valley_mma',
    'db_user' => 'root',
    'db_pass' => '',

    // Time zone for dates (payments, attendance, expiry).
    'timezone' => 'Asia/Kolkata',

    // Admins and members stay logged in this many days.
    'login_days' => 7,

    // Member photos are stored here (must be writable).
    'photo_dir' => __DIR__ . '/uploads/photos',
];
