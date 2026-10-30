<?php
// Fight shop products (admin): add, change, photos (first photo = thumbnail), price and offer price,
// in stock / hidden. Shown on the public shop page with a WhatsApp enquiry button.

require __DIR__ . '/includes/init.php';
require_admin();

const MAX_PRODUCT_IMAGES = 8;
$dir = __DIR__ . '/media/products';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $id = (int)post('id');
    $old = $id ? q('SELECT * FROM products WHERE id = ?', [$id])->fetch() : null;
    if (post('action') === 'delete') {
        require_verify('products.php');
        if ($old) {
            foreach (product_images($old) as $f) {
                @unlink($dir . '/' . $f);
            }
            q('DELETE FROM products WHERE id = ?', [$id]);
            flash('success', t('deleted'));
        }
        redirect('products.php');
    }
    $name = mb_substr(trim(post('name')), 0, 120);
    if ($name === '') {
        flash('danger', t('product_name_needed'));
        redirect('products.php?edit=' . ($id ?: 'new'));
    }
    // photos: keep the ones not removed, cover photo first, then the new uploads
    $imgs = $old ? product_images($old) : [];
    $remove = array_map('strval', (array)($_POST['remove_img'] ?? []));
    foreach ($imgs as $f) {
        if (in_array($f, $remove, true)) {
            @unlink($dir . '/' . $f);
        }
    }
    $imgs = array_values(array_diff($imgs, $remove));
    $cover = post('cover');
    if ($cover !== '' && in_array($cover, $imgs, true)) {
        $imgs = array_values(array_unique(array_merge([$cover], $imgs)));
    }
    $bad = 0;
    if (!empty($_FILES['images']['name'][0])) {
        foreach (array_keys($_FILES['images']['name']) as $i) {
            if (count($imgs) >= MAX_PRODUCT_IMAGES) {
                break;
            }
            $file = ['name' => $_FILES['images']['name'][$i], 'tmp_name' => $_FILES['images']['tmp_name'][$i],
                'error' => $_FILES['images']['error'][$i], 'size' => $_FILES['images']['size'][$i]];
            $f = save_photo($file, 1200, $dir);
            $f === null ? $bad++ : $imgs[] = $f;
        }
    }
    $price = max(0, num(post('price')));
    $sale = post('sale_price') === '' ? null : max(0, num(post('sale_price')));
    $vals = [$name, mb_substr(trim(post('category')), 0, 60), $price, $sale ?: null, mb_substr(trim(post('description')), 0, 3000),
        json_encode($imgs), post('in_stock') === '1' ? 1 : 0, post('active') === '1' ? 1 : 0, (int)post('sort_order')];
    if ($old) {
        $vals[] = $id;
        q('UPDATE products SET name = ?, category = ?, price = ?, sale_price = ?, description = ?, images = ?, in_stock = ?, active = ?, sort_order = ? WHERE id = ?', $vals);
    } else {
        q('INSERT INTO products (name, category, price, sale_price, description, images, in_stock, active, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', $vals);
        $id = (int)db()->lastInsertId();
    }
    if ($bad) {
        flash('warning', t('err_photo'));
    }
    flash('success', t('product_saved', $name));
    redirect('products.php#prod' . $id);
}

$editKey = get('edit');
$edit = $editKey === 'new' ? ['id' => 0, 'name' => '', 'category' => '', 'price' => '', 'sale_price' => null, 'description' => '', 'images' => '[]', 'in_stock' => 1, 'active' => 1, 'sort_order' => 0]
    : ($editKey !== '' ? q('SELECT * FROM products WHERE id = ?', [(int)$editKey])->fetch() : null);
$products = q('SELECT * FROM products ORDER BY sort_order, id DESC')->fetchAll();
$cats = q("SELECT DISTINCT category FROM products WHERE category <> '' ORDER BY category")->fetchAll(PDO::FETCH_COLUMN);

$title = t('products');
$active = 'products';
$back = $edit ? 'products.php' : 'more.php';
$actions = $edit ? '' : '<a href="shop.php" class="btn btn-outline-primary" target="_blank"><i class="bi bi-box-arrow-up-right"></i> ' . e(pub('pub_shop_title')) . '</a>'
    . '<a href="?edit=new" class="btn btn-primary"><i class="bi bi-plus-lg"></i> ' . e(t('add_product')) . '</a>';
require __DIR__ . '/includes/header.php';
?>
<?php if ($edit): $imgs = product_images($edit); ?>
<form method="post" enctype="multipart/form-data" class="card mb-3"><?= csrf_field() ?><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
  <div class="card-header fw-bold"><i class="bi bi-<?= $edit['id'] ? 'pencil' : 'plus-circle' ?>"></i> <?= e(t($edit['id'] ? 'edit_product' : 'add_product')) ?></div>
  <div class="card-body row g-3">
    <div class="col-md-8"><label class="form-label" for="pn"><?= e(t('product_name')) ?> *</label>
      <input class="form-control" id="pn" name="name" maxlength="120" required value="<?= e($edit['name']) ?>" placeholder="<?= e(t('product_name_ph')) ?>"></div>
    <div class="col-md-4"><label class="form-label" for="pc"><?= e(t('category')) ?></label>
      <input class="form-control" id="pc" name="category" maxlength="60" list="catList" value="<?= e($edit['category']) ?>" placeholder="<?= e(t('product_cat_ph')) ?>">
      <datalist id="catList"><?php foreach ($cats as $c): ?><option value="<?= e($c) ?>"><?php endforeach; ?></datalist></div>
    <div class="col-6 col-md-4"><label class="form-label" for="pp"><?= e(t('price')) ?> (₹)</label>
      <input class="form-control" type="number" min="0" step="0.01" id="pp" name="price" required value="<?= e((string)$edit['price']) ?>"></div>
    <div class="col-6 col-md-4"><label class="form-label" for="ps"><?= e(t('offer_price')) ?> (₹)</label>
      <input class="form-control" type="number" min="0" step="0.01" id="ps" name="sale_price" value="<?= e((string)($edit['sale_price'] ?? '')) ?>" placeholder="<?= e(t('optional')) ?>"></div>
    <div class="col-md-4"><label class="form-label" for="po"><?= e(t('sort_order')) ?></label>
      <input class="form-control" type="number" id="po" name="sort_order" value="<?= (int)$edit['sort_order'] ?>"></div>
    <div class="col-12"><label class="form-label" for="pd"><?= e(t('details')) ?></label>
      <textarea class="form-control" id="pd" name="description" rows="4" maxlength="3000" placeholder="<?= e(t('product_desc_ph')) ?>"><?= e((string)$edit['description']) ?></textarea></div>
    <div class="col-12">
      <label class="form-label d-block"><?= e(t('photos')) ?> <span class="small-muted">(<?= e(t('photos_help', MAX_PRODUCT_IMAGES)) ?>)</span></label>
      <?php if ($imgs): ?><div class="d-flex flex-wrap gap-2 mb-2">
        <?php foreach ($imgs as $i => $f): ?>
          <div class="prod-edit-img"><img src="<?= e(product_img_url($f)) ?>" alt="">
            <div class="form-check small"><input class="form-check-input" type="radio" name="cover" value="<?= e($f) ?>" id="cv<?= $i ?>"<?= $i === 0 ? ' checked' : '' ?>><label class="form-check-label" for="cv<?= $i ?>"><?= e(t('cover_photo')) ?></label></div>
            <div class="form-check small"><input class="form-check-input" type="checkbox" name="remove_img[]" value="<?= e($f) ?>" id="rm<?= $i ?>"><label class="form-check-label text-danger" for="rm<?= $i ?>"><?= e(t('remove')) ?></label></div>
          </div>
        <?php endforeach; ?></div><?php endif; ?>
      <input class="form-control" type="file" name="images[]" accept="image/*" multiple>
    </div>
    <div class="col-12 d-flex flex-wrap gap-4">
      <div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="in_stock" value="1" id="pis"<?= $edit['in_stock'] ? ' checked' : '' ?>><label class="form-check-label" for="pis"><?= e(t('in_stock')) ?></label></div>
      <div class="form-check form-switch"><input class="form-check-input" type="checkbox" role="switch" name="active" value="1" id="pac"<?= $edit['active'] ? ' checked' : '' ?>><label class="form-check-label" for="pac"><?= e(t('show_in_shop')) ?></label></div>
    </div>
    <div class="col-12 d-flex gap-2"><a href="products.php" class="btn btn-light"><?= e(t('cancel')) ?></a>
      <button class="btn btn-primary flex-fill"><i class="bi bi-check2-circle"></i> <?= e(t('save')) ?></button></div>
  </div>
</form>
<?php if ($edit['id']): ?>
  <form method="post" class="text-end mb-4" data-verify="<?= e(t('confirm_delete')) ?>"><?= csrf_field() ?><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="<?= (int)$edit['id'] ?>">
    <button class="btn btn-sm btn-outline-danger"><i class="bi bi-trash"></i> <?= e(t('delete')) ?></button></form>
<?php endif; ?>
<?php else: ?>
  <?php if (!$products): ?><div class="card card-body text-muted"><?= e(t('no_products')) ?></div><?php endif; ?>
  <div class="row g-2">
    <?php foreach ($products as $p): $imgs = product_images($p); ?>
      <div class="col-6 col-md-4 col-lg-3" id="prod<?= $p['id'] ?>"><a href="?edit=<?= $p['id'] ?>" class="card h-100 text-decoration-none text-reset<?= $p['active'] ? '' : ' opacity-50' ?>">
        <div class="prod-thumb"><?php if ($imgs): ?><img src="<?= e(product_img_url($imgs[0])) ?>" alt="" loading="lazy"><?php else: ?><i class="bi bi-bag"></i><?php endif; ?></div>
        <div class="card-body p-2">
          <div class="fw-semibold small"><?= e($p['name']) ?></div>
          <div class="small"><?= product_price_html($p) ?></div>
          <div class="small-muted"><?= e($p['category']) ?><?= !$p['in_stock'] ? ' · ' . e(t('out_of_stock')) : '' ?><?= !$p['active'] ? ' · ' . e(t('hidden')) : '' ?> · <i class="bi bi-images"></i> <?= count($imgs) ?></div>
        </div></a></div>
    <?php endforeach; ?>
  </div>
<?php endif; ?>
<?php require __DIR__ . '/includes/footer.php';
