<?php
// ---------------------------------------------------------------
// Daybill Print – configuration
// Edit these values for your shop PC (XAMPP defaults shown).
// ---------------------------------------------------------------

return [
    // MySQL (XAMPP default: user "root", empty password)
    'db_host' => '127.0.0.1',
    'db_port' => 3306,
    'db_name' => 'daybill_print',
    'db_user' => 'root',
    'db_pass' => '',

    // Redirect every http:// request to https://
    'force_https' => true,

    // Where uploaded files are stored (must NOT be web-accessible;
    // the bundled uploads/.htaccess blocks direct access).
    'upload_dir' => __DIR__ . '/uploads',

    // Maximum size per uploaded file in MB (also raise upload_max_filesize
    // and post_max_size in php.ini if you increase this).
    'max_file_mb' => 25,

    // Maximum number of files a customer can send in one order.
    'max_files' => 10,

    // ---- Printing -------------------------------------------------
    // Windows (XAMPP): install SumatraPDF and point to SumatraPDF.exe.
    //   https://www.sumatrapdfreader.org/download-free-pdf-viewer
    'sumatra_path' => 'C:\\Program Files\\SumatraPDF\\SumatraPDF.exe',

    // Optional: LibreOffice, used to convert Word/Excel/PowerPoint
    // files to PDF before printing. Leave empty to disable.
    'soffice_path' => 'C:\\Program Files\\LibreOffice\\program\\soffice.exe',

    // Linux / macOS: uses CUPS "lp" command.
    'lp_path' => '/usr/bin/lp',

    // Set to true to only log print commands instead of running them
    // (useful for testing without a printer).
    'print_dry_run' => false,
];
