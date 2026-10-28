<?php
// Fields to change one member's position: pick a level, or let attendance decide. Needs $mm (member row) and $levels.
$uid = 'm' . (int)$mm['id'];
?>
<div class="d-flex flex-wrap gap-1 mb-2 cat-opt">
  <?php foreach ($levels as $l): ?>
    <input type="radio" class="btn-check" name="level_id" value="<?= $l['id'] ?>" id="lv<?= $uid . $l['id'] ?>"<?= (int)$mm['level_id'] === (int)$l['id'] ? ' checked' : '' ?>>
    <label class="btn btn-sm btn-outline-secondary" for="lv<?= $uid . $l['id'] ?>"><?= e($l['name']) ?></label>
  <?php endforeach; ?>
</div>
<div class="d-flex flex-wrap gap-2 align-items-center">
  <button class="btn btn-sm btn-primary" name="auto" value="0"><i class="bi bi-hand-index"></i> <?= e(t('set_position')) ?></button>
  <button class="btn btn-sm btn-outline-primary" name="auto" value="1"><i class="bi bi-magic"></i> <?= e(t('set_auto')) ?></button>
</div>
<div class="form-text"><?= e(t('set_position_help')) ?></div>
