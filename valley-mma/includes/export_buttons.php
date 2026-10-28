<?php // Print / PDF / Excel (CSV) buttons for the table with id="reportTable". ?>
<div class="btn-group btn-group-sm no-print" role="group">
  <button type="button" class="btn btn-outline-dark" data-export="print"><i class="bi bi-printer"></i> <?= e(t('print')) ?></button>
  <button type="button" class="btn btn-outline-danger" data-export="pdf"><i class="bi bi-file-earmark-pdf"></i> PDF</button>
  <button type="button" class="btn btn-outline-success" data-export="csv"><i class="bi bi-file-earmark-spreadsheet"></i> Excel</button>
</div>
