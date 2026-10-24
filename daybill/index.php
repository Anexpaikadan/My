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
        return ['ok' => false, 'error' => 'Please choose at least one file.'];
    }
    $files = $_FILES['files'];
    $count = count($files['name']);
    if ($count > cfg('max_files')) {
        return ['ok' => false, 'error' => 'Maximum ' . cfg('max_files') . ' files per order.'];
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
            return ['ok' => false, 'error' => "\"$name\" is too large (max " . cfg('max_file_mb') . ' MB).'];
        }
        if ($files['error'][$i] !== UPLOAD_ERR_OK) {
            return ['ok' => false, 'error' => "Upload of \"$name\" failed. Please try again."];
        }
        $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
        if (!in_array($ext, ALLOWED_EXT, true)) {
            return ['ok' => false, 'error' => "\"$name\": file type not supported."];
        }
        $tmp = $files['tmp_name'][$i];
        $head = (string)file_get_contents($tmp, false, null, 0, 8);
        if ($ext === 'pdf' && strncmp($head, '%PDF', 4) !== 0) {
            return ['ok' => false, 'error' => "\"$name\" is not a valid PDF."];
        }
        if (in_array($ext, ['jpg', 'jpeg', 'png'], true) && @getimagesize($tmp) === false) {
            return ['ok' => false, 'error' => "\"$name\" is not a valid image."];
        }
        $accepted[] = ['i' => $i, 'name' => $name, 'ext' => $ext, 'tmp' => $tmp, 'size' => (int)$files['size'][$i]];
    }
    if (!$accepted) {
        return ['ok' => false, 'error' => 'Please choose at least one file.'];
    }

    $pdo = db();
    $pdo->beginTransaction();
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
            $pages = $f['ext'] === 'pdf' ? pdf_page_count($dir . '/' . $stored)
                : (in_array($f['ext'], ['jpg', 'jpeg', 'png'], true) ? 1 : 0);
            $o = clean_options(is_array($opts[$f['i']] ?? null) ? $opts[$f['i']] : []);
            $ins->execute([$jobId, mb_substr(basename($f['name']), 0, 255), $stored, $f['ext'], $f['size'], $pages,
                $o['copies'], $o['paper'], $o['color'], $o['sides'], $o['orientation'], $o['page_range']]);
        }
        $pdo->commit();
    } catch (Throwable $e) {
        $pdo->rollBack();
        error_log('Daybill upload error: ' . $e->getMessage());
        return ['ok' => false, 'error' => 'Server error while saving. Please try again.'];
    }
    return ['ok' => true, 'code' => $code, 'files' => count($accepted)];
}

$result = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $result = empty($_POST) && empty($_FILES)
        ? ['ok' => false, 'error' => 'Upload too large for the server (max ' . cfg('max_file_mb') . ' MB per file).']
        : handle_upload();
    if (($_POST['ajax'] ?? '') === '1' || empty($_POST)) {
        header('Content-Type: application/json');
        echo json_encode($result);
        exit;
    }
}

page_header('Send files to print');
$accept = '.' . implode(',.', ALLOWED_EXT);
?>
<?php if ($result && $result['ok']): ?>
  <div class="card center">
    <h1>✅ Sent!</h1>
    <p>Show this code at the counter:</p>
    <div class="bigcode"><?= h($result['code']) ?></div>
    <a class="btn block" href="index.php">Send more files</a>
  </div>
<?php else: ?>
  <?php if ($result): ?><div class="alert err"><?= h($result['error']) ?></div><?php endif; ?>

  <div id="done" class="card center hidden">
    <h1>✅ Sent!</h1>
    <p>Show this code at the counter:</p>
    <div class="bigcode" id="doneCode"></div>
    <a class="btn block" href="index.php">Send more files</a>
  </div>

  <form id="upForm" method="post" enctype="multipart/form-data" class="card">
    <h1>Send files to print</h1>
    <p class="muted">PDF, photos, Word, Excel, PowerPoint · max <?= (int)cfg('max_file_mb') ?> MB each</p>

    <label class="drop" id="drop">
      <input type="file" id="picker" name="files[]" multiple accept="<?= h($accept) ?>">
      <span>📄 Tap to choose files</span>
    </label>

    <div id="list"></div>

    <!-- Used when JavaScript is off: one set of options for all files -->
    <noscript>
      <div class="opts">
        <label>Copies<input type="number" name="opt[0][copies]" value="1" min="1" max="999"></label>
        <label>Paper<select name="opt[0][paper]"><?php foreach (PAPER_SIZES as $p): ?><option><?= $p ?></option><?php endforeach; ?></select></label>
      </div>
    </noscript>

    <details class="more">
      <summary>Your name / phone (optional)</summary>
      <label>Name<input name="customer_name" maxlength="100" autocomplete="name"></label>
      <label>Phone<input name="phone" maxlength="30" inputmode="tel" autocomplete="tel"></label>
      <label>Note for the shop<input name="note" maxlength="500" placeholder="e.g. staple, spiral binding"></label>
    </details>

    <div id="err" class="alert err hidden"></div>
    <div id="progress" class="progress hidden"><div></div></div>
    <button class="btn primary block big" id="sendBtn">Upload &amp; send to shop</button>
  </form>

  <template id="tpl">
    <div class="file">
      <div class="file-head"><span class="fname"></span><button type="button" class="x" aria-label="Remove">✕</button></div>
      <div class="opts">
        <label>Copies
          <span class="stepper"><button type="button" data-step="-1">−</button><input type="number" data-k="copies" value="1" min="1" max="999"><button type="button" data-step="1">+</button></span>
        </label>
        <label>Paper size
          <select data-k="paper"><?php foreach (PAPER_SIZES as $p): ?><option><?= $p ?></option><?php endforeach; ?></select>
        </label>
        <label>Colour
          <select data-k="color"><option value="bw">Black &amp; white</option><option value="color">Colour</option></select>
        </label>
        <label>Sides
          <select data-k="sides"><option value="single">One side</option><option value="double">Both sides</option></select>
        </label>
        <label>Layout
          <select data-k="orientation"><option value="portrait">Portrait</option><option value="landscape">Landscape</option></select>
        </label>
        <label>Pages
          <input data-k="page_range" placeholder="All  (or e.g. 1-3,5)" inputmode="numeric" pattern="[0-9,\- ]*">
        </label>
      </div>
    </div>
  </template>

  <script>
  (function () {
    var maxFiles = <?= (int)cfg('max_files') ?>, maxMb = <?= (int)cfg('max_file_mb') ?>;
    var picker = document.getElementById('picker'), list = document.getElementById('list'),
        tpl = document.getElementById('tpl'), form = document.getElementById('upForm'),
        err = document.getElementById('err'), prog = document.getElementById('progress'),
        btn = document.getElementById('sendBtn');
    var items = [];

    picker.removeAttribute('name'); // files are sent by JavaScript instead
    picker.addEventListener('change', function () {
      for (var i = 0; i < picker.files.length; i++) addFile(picker.files[i]);
      picker.value = '';
    });

    function showErr(m) { err.textContent = m; err.classList.toggle('hidden', !m); }

    function addFile(file) {
      if (items.length >= maxFiles) return showErr('Maximum ' + maxFiles + ' files.');
      if (file.size > maxMb * 1048576) return showErr('"' + file.name + '" is larger than ' + maxMb + ' MB.');
      showErr('');
      var node = tpl.content.firstElementChild.cloneNode(true);
      node.querySelector('.fname').textContent = file.name;
      var item = { file: file, node: node };
      node.querySelector('.x').onclick = function () {
        items.splice(items.indexOf(item), 1); node.remove();
      };
      node.querySelectorAll('[data-step]').forEach(function (b) {
        b.onclick = function () {
          var inp = node.querySelector('[data-k=copies]');
          inp.value = Math.max(1, Math.min(999, (parseInt(inp.value, 10) || 1) + parseInt(b.dataset.step, 10)));
        };
      });
      items.push(item);
      list.appendChild(node);
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!items.length) return showErr('Please choose at least one file.');
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
        var r; try { r = JSON.parse(xhr.responseText); } catch (x) { r = { ok: false, error: 'Server error. Please try again.' }; }
        if (!r.ok) return showErr(r.error);
        form.classList.add('hidden');
        document.getElementById('doneCode').textContent = r.code;
        document.getElementById('done').classList.remove('hidden');
        window.scrollTo(0, 0);
      };
      xhr.onerror = function () { btn.disabled = false; prog.classList.add('hidden'); showErr('Network error. Please try again.'); };
      xhr.send(fd);
    });
  })();
  </script>
<?php endif; ?>
<?php page_footer(); ?>
