<?php
// Public fight shop: products two in a row; tap one for photos (slideshow), details, price and a
// WhatsApp enquiry to the gym's shop number.

require_once __DIR__ . '/includes/init.php';

$products = q('SELECT * FROM products WHERE active = 1 ORDER BY sort_order, id DESC')->fetchAll();
$cats = array_values(array_unique(array_filter(array_column($products, 'category'))));
$wa = pub_wa_phone('shop_whatsapp');

$title = pub('pub_shop_title');
$bare = true;
$publicPage = 'shop';
require __DIR__ . '/includes/header.php';
?>
<div class="pub-wrap pt-3">
  <div class="pub-page-head">
    <img src="assets/logo.png" alt="<?= e(gym_title()) ?>" width="612" height="106">
    <h1 class="pub-h mb-1"><?= e(pub('pub_shop_title')) ?></h1>
    <?php if (pub('pub_shop_text') !== ''): ?><p class="pub-note mb-0"><?= e(pub('pub_shop_text')) ?></p><?php endif; ?>
  </div>
  <?php if (count($cats) > 1): ?>
    <div class="shop-cats" role="tablist">
      <button type="button" class="on" data-cat=""><?= e(t('all')) ?></button>
      <?php foreach ($cats as $c): ?><button type="button" data-cat="<?= e($c) ?>"><?= e($c) ?></button><?php endforeach; ?>
    </div>
  <?php endif; ?>
  <?php if (!$products): ?><div class="pub-card"><?= e(t('shop_empty')) ?></div><?php endif; ?>
  <div class="shop-grid">
    <?php foreach ($products as $p): $imgs = product_images($p); ?>
      <button type="button" class="shop-item" id="p<?= $p['id'] ?>" data-product="<?= $p['id'] ?>" data-cat="<?= e($p['category']) ?>">
        <div class="shop-thumb"><?php if ($imgs): ?><img src="<?= e(product_img_url($imgs[0])) ?>" alt="" loading="lazy"><?php else: ?><i class="bi bi-bag"></i><?php endif; ?>
          <?php if (!$p['in_stock']): ?><span class="shop-tag"><?= e(t('out_of_stock')) ?></span><?php elseif ($p['sale_price'] !== null && (float)$p['sale_price'] > 0 && (float)$p['sale_price'] < (float)$p['price']): ?><span class="shop-tag sale"><?= e(t('offer')) ?></span><?php endif; ?></div>
        <div class="shop-name"><?= e($p['name']) ?></div>
        <div class="shop-price"><?= product_price_html($p) ?></div>
      </button>
    <?php endforeach; ?>
  </div>
</div>

<div class="modal fade" id="productModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable"><div class="modal-content pub-modal">
    <div class="modal-header border-0 pb-0"><h2 class="modal-title h5" id="pmName"></h2>
      <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button></div>
    <div class="modal-body">
      <div id="pmCarousel" class="carousel slide mb-3" data-bs-touch="true">
        <div class="carousel-indicators" id="pmDots"></div>
        <div class="carousel-inner" id="pmSlides"></div>
        <button class="carousel-control-prev" type="button" data-bs-target="#pmCarousel" data-bs-slide="prev"><span class="carousel-control-prev-icon"></span></button>
        <button class="carousel-control-next" type="button" data-bs-target="#pmCarousel" data-bs-slide="next"><span class="carousel-control-next-icon"></span></button>
      </div>
      <div class="d-flex align-items-center gap-2 mb-2"><div class="shop-price fs-4" id="pmPrice"></div><span class="badge ms-auto" id="pmStock"></span></div>
      <div class="small-muted mb-1" id="pmCat"></div>
      <p id="pmDesc" style="white-space:pre-line"></p>
    </div>
    <div class="modal-footer border-0 pt-0">
      <a class="btn btn-whatsapp btn-lg w-100" id="pmWa" target="_blank" rel="noopener"><i class="bi bi-whatsapp"></i> <?= e(t('enquire_whatsapp')) ?></a>
    </div>
  </div></div>
</div>
<script>window.VM_SHOP = <?= json_encode(array_map(function ($p) use ($wa) {
    $sale = $p['sale_price'] !== null && (float)$p['sale_price'] > 0 && (float)$p['sale_price'] < (float)$p['price'];
    return [
        'id' => (int)$p['id'], 'name' => $p['name'], 'cat' => $p['category'], 'desc' => (string)$p['description'],
        'price' => product_price_html($p), 'stock' => (bool)$p['in_stock'],
        'imgs' => array_map('product_img_url', product_images($p)),
        'wa' => wa_link($wa, t('wa_product_enquiry', $p['name'], money($sale ? $p['sale_price'] : $p['price']), base_url() . 'shop.php#p' . $p['id'])),
    ];
}, $products), JSON_UNESCAPED_UNICODE | JSON_HEX_TAG | JSON_HEX_AMP) ?>;
window.VM_SHOP_T = <?= json_encode(['in' => t('in_stock'), 'out' => t('out_of_stock')], JSON_UNESCAPED_UNICODE) ?>;</script>
<?php
$scripts = ['assets/shop.js?v=' . APP_VERSION];
require __DIR__ . '/includes/footer.php';
