</main>
<script src="assets/vendor/bootstrap.bundle.min.js"></script>
<?php foreach ($scripts ?? [] as $src): ?>
<script src="<?= e($src) ?>"></script>
<?php endforeach; ?>
<script>window.VM = <?= json_encode([
    'lang' => lang(),
    'gym' => gym_title(),
    'place' => setting('gym_place', 'PANDIKKAD'),
    'phones' => trim(setting('phone1') . '  ' . setting('phone2')),
], JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) ?>;</script>
<script src="assets/app.js?v=4"></script>
</body>
</html>
