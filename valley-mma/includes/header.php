<?php
// Page start for admin pages. Set $title and $active before including.
// $bare = true gives a page without the menu (login, member pages, print views).

$title = $title ?? '';
$active = $active ?? '';
$bare = $bare ?? false;
$v = '3';
?><!doctype html>
<html lang="<?= e(lang()) ?>">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#360DD9">
<title><?= e(($title !== '' ? $title . ' · ' : '') . setting('gym_name', 'VALLEY MMA')) ?></title>
<link rel="manifest" href="manifest.php<?= !empty($memberApp) ? '?app=member' : '' ?>">
<link rel="icon" type="image/png" href="assets/icons/favicon.png">
<link rel="apple-touch-icon" href="assets/icons/apple-touch-icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<link rel="stylesheet" href="assets/vendor/bootstrap.min.css">
<link rel="stylesheet" href="assets/vendor/bootstrap-icons.min.css">
<link rel="stylesheet" href="assets/style.css?v=<?= $v ?>">
</head>
<body class="<?= $bare ? 'bare' : 'with-nav' ?> lang-<?= e(lang()) ?>">
<?php if (!$bare): ?>
<header class="topbar d-lg-none d-print-none">
  <button class="btn btn-link text-white fs-2 p-0 me-2" type="button" data-bs-toggle="offcanvas" data-bs-target="#sidebar" aria-label="<?= e(t('menu')) ?>"><i class="bi bi-list"></i></button>
  <a href="index.php" class="brand-mini"><?= e(setting('gym_name', 'VALLEY MMA')) ?></a>
  <a href="lang.php?l=<?= lang() === 'en' ? 'ml' : 'en' ?>" class="btn btn-sm btn-outline-light ms-auto"><?= lang() === 'en' ? 'മലയാളം' : 'English' ?></a>
</header>
<?php require __DIR__ . '/nav.php'; ?>
<main class="main">
  <div class="page-head d-flex flex-wrap align-items-center gap-2 mb-3">
    <h1 class="h4 mb-0 me-auto"><?= e($title) ?></h1>
    <?= $actions ?? '' ?>
  </div>
  <?= flashes() ?>
<?php else: ?>
<main class="main-bare">
  <?= flashes() ?>
<?php endif; ?>
