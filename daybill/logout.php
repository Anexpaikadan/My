<?php
require __DIR__ . '/lib.php';

$_SESSION = [];
session_destroy();
redirect('login.php');
