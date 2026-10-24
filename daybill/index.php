<?php
// Customer upload page – this is the page the shop QR code opens.

require __DIR__ . '/lib.php';

function make_code(): string
{
    $chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // no 0/O/1/I
    $code = '';
    for ($i = 0; $i < 4; $i++) {
        $code .= $chars[random_int(0, strlen($chars) - 1)];
    }
    return $code;
}

function handle_upload(): array
{
    if (empty($_FILES['files']) || !is_array($_FILES['files']['name'])) {
        return ['ok' => false, 'error' => t('err_none')];
    }
    $files = $_FILES['files'];
    if (count($files['name']) > cfg('max_files')) {
        return ['ok' => false, 'error' => t('err_max', cfg('max_files'))];
    }
    $maxBytes = cfg('max_file_mb') * 1048576;
    $dir = cfg('upload_dir');
    if (!is_dir($dir)) {
        mkdir($dir, 0770, true);
    }

    $accepted = [];
    foreach ($files['name'] as $i => $name) {
        if ($files['error'][$i] === UPLOAD_ERR_NO_FILE) {
            continue;
        }
        if ($files['error'][$i] === UPLOAD_ERR_INI_SIZE || $files['error'][$i] === UPLOAD_ERR_FORM_SIZE
            || $files['size'][$i] > $maxBytes) {
            return ['ok' => false, 'error' => t('err_big', $name, cfg('max_file_mb'))];
        }
        if ($files['error'][$i] !== UPLOAD_ERR_OK) {
            return ['ok' => false, 'error' => t('err_fail', $name)];
        }
        $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
        if (!in_array($ext, ALLOWED_EXT, true)) {
            return ['ok' => false, 'error' => t('err_type', $name)];
        }
        $tmp = $files['tmp_name'][$i];
        $head = (string)file_get_contents($tmp, false, null, 0, 8);
        if ($ext === 'pdf' && strncmp($head, '%PDF', 4) !== 0) {
            return ['ok' => false, 'error' => t('err_pdf', $name)];
        }
        if (in_array($ext, ['jpg', 'jpeg', 'png'], true) && @getimagesize($tmp) === false) {
            return ['ok' => false, 'error' => t('err_img', $name)];
        }
        $accepted[] = ['i' => $i, 'name' => $name, 'ext' => $ext, 'tmp' => $tmp, 'size' => (int)$files['size'][$i]];
    }
    if (!$accepted) {
        return ['ok' => false, 'error' => t('err_none')];
    }

    $pdo = db();
    $pdo->beginTransaction();
    $saved = [];
    $total = 0.0;
    $unknown = false;
    try {
        $jobId = 0;
        for ($try = 0; $try < 20 && !$jobId; $try++) {
            $code = make_code();
            try {
                $st = $pdo->prepare('INSERT INTO jobs (code, customer_name, phone, note) VALUES (?, ?, ?, ?)');
                $st->execute([
                    $code,
                    mb_substr(trim((string)($_POST['customer_name'] ?? '')), 0, 100),
                    mb_substr(trim((string)($_POST['phone'] ?? '')), 0, 30),
                    mb_substr(trim((string)($_POST['note'] ?? '')), 0, 500),
                ]);
                $jobId = (int)$pdo->lastInsertId();
            } catch (PDOException $e) {
                if ($e->errorInfo[1] != 1062) { // not a duplicate code
                    throw $e;
                }
            }
        }
        if (!$jobId) {
            throw new RuntimeException('Could not create order code');
        }

        $ins = $pdo->prepare('INSERT INTO job_files
            (job_id, original_name, stored_name, ext, size_bytes, pages_total, copies, paper, color, sides, orientation, page_range)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
        $opts = $_POST['opt'] ?? [];
        foreach ($accepted as $f) {
            $stored = bin2hex(random_bytes(16)) . '.' . $f['ext'];
            if (!move_uploaded_file($f['tmp'], $dir . '/' . $stored)) {
                throw new RuntimeException('Could not save file');
            }
            $saved[] = $dir . '/' . $stored;
            $pages = $f['ext'] === 'pdf' ? pdf_page_count($dir . '/' . $stored)
                : (in_array($f['ext'], ['jpg', 'jpeg', 'png'], true) ? 1 : 0);
            $o = clean_options(is_array($opts[$f['i']] ?? null) ? $opts[$f['i']] : []);
            $ins->execute([$jobId, mb_substr(basename($f['name']), 0, 255), $stored, $f['ext'], $f['size'], $pages,
                $o['copies'], $o['paper'], $o['color'], $o['sides'], $o['orientation'], $o['page_range']]);
            $total += auto_price($o + ['pages_total' => $pages]);
            $unknown = $unknown || $pages === 0;
        }
        $pdo->commit();
    } catch (Throwable $e) {
        $pdo->rollBack();
        array_map('unlink', $saved);
        error_log('Daybill upload error: ' . $e->getMessage());
        return ['ok' => false, 'error' => t('err_server')];
    }
    return ['ok' => true, 'code' => $code, 'files' => count($accepted),
        'price' => $unknown ? '' : money($total)];
}

$lang = lang();
$result = null;

// Page count only (nothing is stored) – fallback for phones that cannot read the PDF themselves.
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['ajax'] ?? '') === 'count') {
    $tmp = $_FILES['pdf']['tmp_name'] ?? '';
    $ok = $tmp !== '' && ($_FILES['pdf']['error'] ?? 1) === UPLOAD_ERR_OK
        && strncmp((string)file_get_contents($tmp, false, null, 0, 4), '%PDF', 4) === 0;
    header('Content-Type: application/json');
    echo json_encode(['pages' => $ok ? pdf_page_count($tmp) : 0]);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $result = empty($_POST) && empty($_FILES)
        ? ['ok' => false, 'error' => t('err_post', cfg('max_file_mb'))]
        : handle_upload();
    if (($_POST['ajax'] ?? '') === '1' || empty($_POST)) {
        header('Content-Type: application/json');
        echo json_encode($result);
        exit;
    }
}

$papers = enabled_papers();
$colors = enabled_colors();
$sides = enabled_sides();

// Rules for every offered combination, for the live price estimate.
$rules = [];
foreach ($papers as $p) {
    foreach ($colors as $c) {
        foreach ($sides as $s) {
            $rules[$p][$c][$s] = price_rule($p, $c, $s);
        }
    }
}

// A select, or a fixed label when only one choice is offered.
function choice(string $key, string $label, array $values, bool $translate): string
{
    $text = fn($v) => $translate ? t($v) : $v;
    if (count($values) === 1) {
        return '<label>' . h(t($label)) . '<span class="fixed">' . h($text($values[0])) . '</span>'
            . '<input type="hidden" data-k="' . $key . '" value="' . h($values[0]) . '"></label>';
    }
    $s = '<label>' . h(t($label)) . '<select data-k="' . $key . '">';
    foreach ($values as $v) {
        $s .= '<option value="' . h($v) . '">' . h($text($v)) . '</option>';
    }
    return $s . '</select></label>';
}

function rule_text(array $r): string
{
    [$n, $base, $extra] = $r;
    if ($n <= 1 && abs($base - $extra) < 0.001) {
        return t('rule_flat', money($extra));
    }
    return t('rule', $n, money($base), money($extra));
}

page_header(t('title'), false, $lang);
$accept = '.' . implode(',.', ALLOWED_EXT);
?>
<?php if ($result && $result['ok']): ?>
  <div class="card center">
    <h1><?= h(t('sent')) ?></h1>
    <p><?= h(t('show_code')) ?></p>
    <div class="bigcode"><?= h($result['code']) ?></div>
    <p class="pay-box"><?= h($result['price'] !== '' ? t('estimate') : t('estimate_ph')) ?><?php if ($result['price'] !== ''): ?><b><?= h($result['price']) ?></b><?php endif; ?></p>
    <p class="muted"><?= h(t('final_note')) ?></p>
    <a class="btn block" href="index.php"><?= h(t('send_more')) ?></a>
  </div>
<?php else: ?>
  <?php if ($result): ?><div class="alert err"><?= h($result['error']) ?></div><?php endif; ?>

  <div id="done" class="card center hidden">
    <h1><?= h(t('sent')) ?></h1>
    <p><?= h(t('show_code')) ?></p>
    <div class="bigcode" id="doneCode"></div>
    <p id="donePrice" class="pay-box"></p>
    <p class="muted"><?= h(t('final_note')) ?></p>
    <a class="btn block" href="index.php"><?= h(t('send_more')) ?></a>
  </div>

  <form id="upForm" method="post" enctype="multipart/form-data" class="card">
    <h1><?= h(t('title')) ?></h1>
    <p class="muted"><?= h(t('hint', cfg('max_file_mb'))) ?></p>

    <label class="drop" id="drop">
      <input type="file" id="picker" name="files[]" multiple accept="<?= h($accept) ?>">
      <span><?= h(t('choose')) ?></span>
    </label>

    <div id="list"></div>
    <div id="total" class="pay-box hidden"></div>

    <!-- Used when JavaScript is off: options of the first file -->
    <noscript>
      <div class="opts">
        <label><?= h(t('copies')) ?><input type="number" name="opt[0][copies]" value="1" min="1" max="999"></label>
        <label><?= h(t('paper')) ?><select name="opt[0][paper]"><?php foreach ($papers as $p): ?><option><?= h($p) ?></option><?php endforeach; ?></select></label>
      </div>
    </noscript>

    <details class="more">
      <summary><?= h(t('prices')) ?></summary>
      <table class="tbl prices">
        <?php foreach ($rules as $p => $byColor): foreach ($byColor as $c => $bySides): foreach ($bySides as $s => $r): ?>
          <tr><td><b><?= h($p) ?></b> · <?= h(t($c)) ?> · <?= h(t($s)) ?></td><td><?= h(rule_text($r)) ?></td></tr>
        <?php endforeach; endforeach; endforeach; ?>
      </table>
    </details>

    <details class="more">
      <summary><?= h(t('optional')) ?></summary>
      <label><?= h(t('name')) ?><input name="customer_name" maxlength="100" autocomplete="name"></label>
      <label><?= h(t('phone')) ?><input name="phone" maxlength="30" inputmode="tel" autocomplete="tel"></label>
      <label><?= h(t('note')) ?><input name="note" maxlength="500" placeholder="<?= h(t('note_ph')) ?>"></label>
    </details>

    <div id="err" class="alert err hidden"></div>
    <div id="progress" class="progress hidden"><div></div></div>
    <button class="btn primary block big" id="sendBtn"><?= h(t('send')) ?></button>
  </form>

  <template id="tpl">
    <div class="file">
      <div class="file-head"><span class="fname"></span><button type="button" class="x" aria-label="<?= h(t('remove')) ?>">✕</button></div>
      <div class="opts">
        <label><?= h(t('copies')) ?>
          <span class="stepper"><button type="button" data-step="-1">−</button><input type="number" data-k="copies" value="1" min="1" max="999"><button type="button" data-step="1">+</button></span>
        </label>
        <?= choice('paper', 'paper', $papers, false) ?>
        <?= choice('color', 'colour', $colors, true) ?>
        <?= choice('sides', 'sides', $sides, true) ?>
        <?= choice('orientation', 'layout', ['portrait', 'landscape'], true) ?>
        <label><?= h(t('pages')) ?>
          <input data-k="page_range" placeholder="<?= h(t('pages_ph')) ?>" inputmode="numeric" pattern="[0-9,\- ]*">
        </label>
        <div class="price wide muted"></div>
      </div>
    </div>
  </template>

  <script>
  (function () {
    var maxFiles = <?= (int)cfg('max_files') ?>, maxMb = <?= (int)cfg('max_file_mb') ?>;
    var rules = <?= json_encode($rules) ?>, currency = <?= json_encode(setting('currency', 'SR')) ?>;
    var T = <?php $keys = ['err_none', 'err_server', 'err_net', 'estimate', 'estimate_ph', 'pages_count', 'counting'];
                echo json_encode(array_combine($keys, array_map('t', $keys))); ?>;
    var Terr = { max: <?= json_encode(t('err_max', cfg('max_files'))) ?>, big: <?= json_encode(t('err_big', '%s', cfg('max_file_mb'))) ?> };
    var picker = document.getElementById('picker'), list = document.getElementById('list'),
        tpl = document.getElementById('tpl'), form = document.getElementById('upForm'),
        err = document.getElementById('err'), prog = document.getElementById('progress'),
        btn = document.getElementById('sendBtn'), totalEl = document.getElementById('total');
    var items = [];

    picker.removeAttribute('name'); // files are sent by JavaScript instead
    picker.addEventListener('change', function () {
      for (var i = 0; i < picker.files.length; i++) addFile(picker.files[i]);
      picker.value = '';
    });

    function showErr(m) { err.textContent = m; err.classList.toggle('hidden', !m); }
    function money(v) { var s = v.toFixed(2); return (s.slice(-3) === '.00' ? s.slice(0, -3) : s) + ' ' + currency; }
    function val(node, k) { return node.querySelector('[data-k=' + k + ']').value; }

    // Same logic as pages_selected() in lib.php.
    function selected(total, range) {
      range = range.replace(/\s+/g, '');
      if (!/^(\d+(-\d+)?)(,\d+(-\d+)?)*$/.test(range)) return Math.max(1, total);
      var pages = {};
      range.split(',').forEach(function (part) {
        var ab = part.split('-'), a = +ab[0], b = ab.length > 1 ? +ab[1] : a;
        if (b < a) { var t = a; a = b; b = t; }
        if (total > 0) b = Math.min(b, total);
        for (var i = a; i <= b && i - a < 10000; i++) pages[i] = 1;
      });
      return Math.max(1, Object.keys(pages).length);
    }

    function price(it) {
      if (!it.pages) return null;
      var r = ((rules[val(it.node, 'paper')] || {})[val(it.node, 'color')] || {})[val(it.node, 'sides')];
      if (!r) return null;
      var n = selected(it.pages, val(it.node, 'page_range')) * Math.max(1, parseInt(val(it.node, 'copies'), 10) || 1);
      return r[1] + Math.max(0, n - r[0]) * r[2];
    }

    function refresh() {
      var sum = 0, known = items.length > 0;
      items.forEach(function (it) {
        var p = price(it), el = it.node.querySelector('.price');
        el.textContent = it.counting ? T.counting
          : (it.pages ? T.pages_count.replace('%d', it.pages) + ' · ' : '')
            + (p === null ? T.estimate_ph : T.estimate + ': ' + money(p));
        if (p === null) known = false; else sum += p;
      });
      totalEl.innerHTML = '';
      if (known) {
        totalEl.appendChild(document.createTextNode(T.estimate));
        var b = document.createElement('b'); b.textContent = money(sum); totalEl.appendChild(b);
      }
      totalEl.classList.toggle('hidden', !known);
    }

    function latin1(buf) { return new TextDecoder('latin1').decode(buf); }

    // Same logic as pdf_tree_count() in lib.php.
    function treeCount(s) {
      var m, max = 0, re = /<<[^<>]*\/Type\s*\/Pages\b[^<>]*>>/g;
      while ((m = re.exec(s))) { var c = /\/Count\s+(\d+)/.exec(m[0]); if (c) max = Math.max(max, +c[1]); }
      if (!max) { re = /\/Type\s*\/Pages\b[^>]*?\/Count\s+(\d+)/g; while ((m = re.exec(s))) max = Math.max(max, +m[1]); }
      return max;
    }

    function inflate(bytes) {
      var ds = new DecompressionStream('deflate');
      return new Response(new Blob([bytes]).stream().pipeThrough(ds)).arrayBuffer().then(latin1, function () { return ''; });
    }

    // Same approach as pdf_page_count() in lib.php: plain text plus compressed object streams.
    function pdfPages(buf) {
      var s = latin1(buf), parts = [], re = /stream\r?\n/g, m;
      while (window.DecompressionStream && (m = re.exec(s))) {
        var start = m.index + m[0].length, end = s.indexOf('endstream', start);
        if (end < 0) break;
        var dict = s.slice(Math.max(0, m.index - 400), m.index);
        dict = dict.slice(Math.max(0, dict.lastIndexOf('obj')));
        if (dict.indexOf('/ObjStm') >= 0 && dict.indexOf('/FlateDecode') >= 0) {
          while (end > start && (s[end - 1] === '\n' || s[end - 1] === '\r')) end--;
          parts.push(inflate(new Uint8Array(buf, start, end - start)));
        }
        re.lastIndex = end;
      }
      return Promise.all(parts).then(function (texts) {
        var all = s + '\n' + texts.join('\n');
        return treeCount(all) || (all.match(/\/Type\s*\/Page\b(?!s)/g) || []).length;
      });
    }

    // Asks the server to count pages when the phone could not (old browser or unusual PDF).
    function serverPages(file) {
      var fd = new FormData(); fd.append('ajax', 'count'); fd.append('pdf', file, file.name);
      return fetch('index.php', { method: 'POST', body: fd }).then(function (r) { return r.json(); })
        .then(function (d) { return d.pages || 0; }, function () { return 0; });
    }

    function countPages(it) {
      var ext = it.file.name.split('.').pop().toLowerCase();
      if (['jpg', 'jpeg', 'png'].indexOf(ext) >= 0) { it.pages = 1; return refresh(); }
      if (ext !== 'pdf') return refresh();
      it.counting = true; refresh();
      var local = it.file.arrayBuffer && window.TextDecoder
        ? it.file.arrayBuffer().then(pdfPages).catch(function () { return 0; }) : Promise.resolve(0);
      local.then(function (n) { return n || serverPages(it.file); }).then(function (n) {
        it.pages = n; it.counting = false; refresh();
      });
    }

    function addFile(file) {
      if (items.length >= maxFiles) return showErr(Terr.max);
      if (file.size > maxMb * 1048576) return showErr(Terr.big.replace('%s', file.name));
      showErr('');
      var node = tpl.content.firstElementChild.cloneNode(true);
      node.querySelector('.fname').textContent = file.name;
      var item = { file: file, node: node, pages: 0 };
      node.querySelector('.x').onclick = function () {
        items.splice(items.indexOf(item), 1); node.remove(); refresh();
      };
      node.querySelectorAll('[data-step]').forEach(function (b) {
        b.onclick = function () {
          var inp = node.querySelector('[data-k=copies]');
          inp.value = Math.max(1, Math.min(999, (parseInt(inp.value, 10) || 1) + parseInt(b.dataset.step, 10)));
          refresh();
        };
      });
      node.addEventListener('input', refresh);
      node.addEventListener('change', refresh);
      items.push(item);
      list.appendChild(node);
      countPages(item);
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!items.length) return showErr(T.err_none);
      showErr('');
      var fd = new FormData();
      fd.append('ajax', '1');
      ['customer_name', 'phone', 'note'].forEach(function (n) { fd.append(n, form.elements[n].value); });
      items.forEach(function (it, i) {
        fd.append('files[]', it.file, it.file.name);
        it.node.querySelectorAll('[data-k]').forEach(function (el) {
          fd.append('opt[' + i + '][' + el.dataset.k + ']', el.value);
        });
      });
      var xhr = new XMLHttpRequest();
      xhr.open('POST', 'index.php');
      btn.disabled = true; prog.classList.remove('hidden');
      xhr.upload.onprogress = function (ev) {
        if (ev.lengthComputable) prog.firstElementChild.style.width = (ev.loaded / ev.total * 100) + '%';
      };
      xhr.onload = function () {
        btn.disabled = false; prog.classList.add('hidden');
        var r; try { r = JSON.parse(xhr.responseText); } catch (x) { r = { ok: false, error: T.err_server }; }
        if (!r.ok) return showErr(r.error);
        form.classList.add('hidden');
        document.getElementById('doneCode').textContent = r.code;
        var dp = document.getElementById('donePrice');
        dp.textContent = r.price ? T.estimate : T.estimate_ph;
        if (r.price) { var b = document.createElement('b'); b.textContent = r.price; dp.appendChild(b); }
        document.getElementById('done').classList.remove('hidden');
        window.scrollTo(0, 0);
      };
      xhr.onerror = function () { btn.disabled = false; prog.classList.add('hidden'); showErr(T.err_net); };
      xhr.send(fd);
    });
  })();
  </script>
<?php endif; ?>
<?php page_footer(); ?>
