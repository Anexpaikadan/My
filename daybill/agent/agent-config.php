<?php
// Print agent settings – edit on the shop PC.

return [
    // Address of your hosted app (the folder that contains api.php).
    'server_url' => 'https://yourdomain.com/daybill/',

    // Copy the agent key from Admin → Print mode on the website.
    'agent_key' => 'PASTE-AGENT-KEY-HERE',

    // SumatraPDF (Windows) – https://www.sumatrapdfreader.org
    // Leave '' to find it automatically (normal install, or SumatraPDF.exe in a "tools" folder here).
    'sumatra_path' => '',

    // Optional LibreOffice for Word/Excel/PowerPoint files ('' = disabled).
    'soffice_path' => 'C:\\Program Files\\LibreOffice\\program\\soffice.exe',

    // Linux / macOS CUPS command.
    'lp_path' => '/usr/bin/lp',

    // Printer to use instead of the one set in Admin ('' = use Admin setting).
    'printer_override' => '',

    // If PHP says "certificate verify failed", download https://curl.se/ca/cacert.pem
    // and put its full path here, e.g. 'C:\\xampp\\php\\extras\\ssl\\cacert.pem'.
    'ca_file' => '',

    // Seconds to wait before trying again after a connection problem.
    // (New jobs arrive instantly – the agent keeps a connection open to the website.)
    'poll_seconds' => 1,

    // true = only log what would be printed.
    'dry_run' => false,
];
