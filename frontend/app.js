/* ── PSI Compare — app.js ────────────────────────────────────────── */
'use strict';

// ── State ───────────────────────────────────────────────────────────
let _state = {
  sessionId: null,
  oldLabel: '',
  newLabel: '',
  futureWeeks: [],
  compareData: [],
  windowData: [],
  showAllWeeks: false,
  MAX_WEEKS_DEFAULT: 20,
  compareFilteredOrder: [],
  comparePage: 1,
  pageSize: 100,
};

// ── DOM refs ────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const uploadSection  = $('upload-section');
const resultsSection = $('results-section');
const loadingOverlay = $('loading-overlay');
const compareForm    = $('compare-form');
const errorBox       = $('error-box');
const progressWrap   = $('progress-wrap');
const progressBar    = $('progress-bar');
const progressLabel  = $('progress-label');
const downloadBtn    = $('download-btn');
const newCompareBtn  = $('new-compare-btn');
const toggleWeeksBtn = $('toggle-weeks-btn');

// ── Utility ─────────────────────────────────────────────────────────
function formatNum(n) {
  if (n == null || n === '') return '-';
  const num = Number(n);
  if (!isFinite(num) || num === 0) return '-';
  return num.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function formatNumRaw(n) {
  const num = Number(n);
  if (!isFinite(num)) return '-';
  return num.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function formatPct(p) {
  if (p == null || !isFinite(Number(p))) return '-';
  const v = Number(p) * 100;
  return (v >= 0 ? '+' : '') + v.toFixed(1) + '%';
}

function heatClass(pct) {
  if (pct == null || !isFinite(pct)) return '';
  if (pct >= 0.5)  return 'heat-p50';
  if (pct >= 0.2)  return 'heat-p20';
  if (pct >= 0.1)  return 'heat-p10';
  if (pct > -0.1)  return 'heat-neutral';
  if (pct > -0.2)  return 'heat-n10';
  if (pct > -0.5)  return 'heat-n20';
  return 'heat-n50';
}

function statusBadge(status) {
  const cls = {
    NEW: 'badge-new', REMOVED: 'badge-removed',
    SPIKE: 'badge-spike', DROP: 'badge-drop',
    CHANGED: 'badge-changed', SAME: 'badge-same'
  }[status] || 'badge-same';
  const label = {
    SPIKE: 'DEMAND UP', DROP: 'DEMAND DOWN'
  }[status] || status;
  return `<span class="badge ${cls}">${label}</span>`;
}

function directionBadge(dir) {
  const cls = {
    'INCREASE':   'dir-increase',
    'DECREASE':   'dir-decrease',
    'NEW DEMAND': 'dir-newdemand',
    'ZERO OUT':   'dir-zeroout',
  }[dir] || '';
  return `<span class="badge ${cls}">${dir}</span>`;
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── File Upload & Drag-Drop ─────────────────────────────────────────
function initUploadZone(dropId, inputId, nameId) {
  const dropZone = $(dropId);
  const input    = $(inputId);
  const nameEl   = $(nameId);

  // Click on zone opens file picker
  dropZone.addEventListener('click', () => input.click());

  input.addEventListener('change', () => {
    if (input.files && input.files[0]) {
      setFile(input.files[0], dropZone, nameEl);
    }
  });

  // Drag events
  dropZone.addEventListener('dragenter', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', e => {
    if (!dropZone.contains(e.relatedTarget)) dropZone.classList.remove('drag-over');
  });
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) {
      if (!file.name.endsWith('.xlsx')) {
        showError('Please upload .xlsx files only.');
        return;
      }
      // Assign to input
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      setFile(file, dropZone, nameEl);
    }
  });
}

function setFile(file, dropZone, nameEl) {
  if (!file.name.endsWith('.xlsx')) {
    showError('Please upload .xlsx files only.');
    return;
  }
  nameEl.textContent = file.name;
  dropZone.classList.add('has-file');
}

initUploadZone('drop-old', 'file-old', 'name-old');
initUploadZone('drop-new', 'file-new', 'name-new');

// ── Form Submit ─────────────────────────────────────────────────────
compareForm.addEventListener('submit', async e => {
  e.preventDefault();
  hideError();

  const fileOld = $('file-old').files[0];
  const fileNew = $('file-new').files[0];
  const startWeek = $('start-week').value.trim().toUpperCase();

  if (!fileOld) { showError('Please select the OLD PSI file.'); return; }
  if (!fileNew) { showError('Please select the NEW PSI file.'); return; }
  if (!startWeek || !/^W\d{2}$/.test(startWeek)) {
    showError('Start week must be in format W## (e.g. W20).'); return;
  }

  const thresholdCompare = (parseFloat($('threshold-compare').value) || 20) / 100;
  const thresholdWindow  = (parseFloat($('threshold-window').value)  || 10) / 100;

  const fd = new FormData();
  fd.append('file_old', fileOld);
  fd.append('file_new', fileNew);
  fd.append('start_week', startWeek);
  fd.append('threshold_compare', thresholdCompare);
  fd.append('threshold_window',  thresholdWindow);

  // Show progress
  progressWrap.classList.remove('hidden');
  progressBar.style.width = '30%';
  progressLabel.textContent = 'Uploading files...';
  loadingOverlay.classList.remove('hidden');
  $('compare-btn').disabled = true;

  try {
    progressBar.style.width = '60%';
    progressLabel.textContent = 'Analyzing PSI data...';

    const resp = await fetch('/api/compare', { method: 'POST', body: fd });
    progressBar.style.width = '90%';

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || 'Server error');
    }

    const data = await resp.json();
    progressBar.style.width = '100%';
    progressLabel.textContent = 'Done!';

    // Store state
    _state.sessionId   = data.session_id;
    _state.oldLabel    = data.old_label;
    _state.newLabel    = data.new_label;
    _state.futureWeeks = data.future_weeks;
    _state.compareData = data.compare;
    _state.windowData  = data.window;
    _state.showAllWeeks = false;

    setTimeout(() => {
      uploadSection.classList.add('hidden');
      resultsSection.classList.remove('hidden');
      renderCompareTab();
      renderWindowTab();
      switchTab('tab-compare');
    }, 300);

  } catch (err) {
    showError('Error: ' + (err.message || String(err)));
  } finally {
    loadingOverlay.classList.add('hidden');
    progressWrap.classList.add('hidden');
    progressBar.style.width = '0%';
    $('compare-btn').disabled = false;
  }
});

// ── Tab switching ────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => { p.classList.remove('active'); p.style.display = 'none'; });
  const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  const pane = $(tabId);
  if (btn) btn.classList.add('active');
  if (pane) { pane.style.display = 'block'; requestAnimationFrame(() => pane.classList.add('active')); }
}

// ── New comparison button ────────────────────────────────────────────
newCompareBtn.addEventListener('click', () => {
  resultsSection.classList.add('hidden');
  uploadSection.classList.remove('hidden');
  // Reset form
  $('file-old').value = '';
  $('file-new').value = '';
  $('name-old').textContent = 'No file selected';
  $('name-new').textContent = 'No file selected';
  $('drop-old').classList.remove('has-file');
  $('drop-new').classList.remove('has-file');
  hideError();
  _state = { ...{
    sessionId: null, oldLabel: '', newLabel: '',
    futureWeeks: [], compareData: [], windowData: [],
    showAllWeeks: false, MAX_WEEKS_DEFAULT: 20,
    compareFilteredOrder: [], comparePage: 1, pageSize: 100,
  }};
});

// ── Download ─────────────────────────────────────────────────────────
downloadBtn.addEventListener('click', () => {
  if (_state.sessionId) {
    window.open(`/api/download/${_state.sessionId}`, '_blank');
  }
});

// ── Toggle weeks ─────────────────────────────────────────────────────
toggleWeeksBtn.addEventListener('click', () => {
  _state.showAllWeeks = !_state.showAllWeeks;
  toggleWeeksBtn.textContent = _state.showAllWeeks ? 'Show Less Weeks' : 'Show All Weeks';
  applyWeekVisibility();
});

function applyWeekVisibility() {
  const max = _state.showAllWeeks ? Infinity : _state.MAX_WEEKS_DEFAULT;
  const weekCols = document.querySelectorAll('.week-col-wrapper');
  weekCols.forEach((el, i) => {
    if (i < max) el.classList.remove('week-col-hidden');
    else el.classList.add('week-col-hidden');
  });
}

// ── Error / message helpers ───────────────────────────────────────────
function showError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.remove('hidden');
}
function hideError() {
  errorBox.classList.add('hidden');
  errorBox.textContent = '';
}

// ── RENDER: PSI Compare Tab ─────────────────────────────────────────
function renderCompareTab() {
  const data = _state.compareData;
  const weeks = _state.futureWeeks;

  // KPI
  const demand = data.filter(r => r.seg_type === 'Demand');
  $('kpi-new-count').textContent     = demand.filter(r => r.status === 'NEW').length;
  $('kpi-removed-count').textContent = demand.filter(r => r.status === 'REMOVED').length;
  $('kpi-spike-count').textContent   = demand.filter(r => r.status === 'SPIKE').length;
  $('kpi-drop-count').textContent    = demand.filter(r => r.status === 'DROP').length;

  // Build thead
  const thead = $('compare-thead');
  const MAX = _state.MAX_WEEKS_DEFAULT;

  const fixedHeaders = ['#', 'Item', 'Vendor', 'Description', 'Type',
                        'Metric', 'Status', 'Total OLD', 'Total NEW', 'Delta', '%Delta', 'Flag'];
  let thHTML = '<tr>';
  fixedHeaders.forEach((h, i) => {
    const w = [40, 110, 140, 180, 110, 70, 80, 90, 90, 90, 75, 100][i];
    thHTML += `<th style="width:${w}px;min-width:${w}px">${esc(h)}</th>`;
  });
  weeks.forEach((w, i) => {
    const hidden = i >= MAX ? ' week-col-hidden' : '';
    thHTML += `<th class="week-col week-col-wrapper${hidden}" data-week-idx="${i}">${esc(w)}</th>`;
  });
  thHTML += '</tr>';
  thead.innerHTML = thHTML;

  // Group items
  const groups = {};
  const groupOrder = [];
  data.forEach(row => {
    if (!groups[row.item]) { groups[row.item] = []; groupOrder.push(row.item); }
    groups[row.item].push(row);
  });
  // Sort seg_type within group: Demand first
  groupOrder.forEach(item => {
    groups[item].sort((a, b) => (a.seg_type === 'Demand' ? -1 : 1));
  });

  _state.groups = groups;
  _state.groupOrder = groupOrder;

  // Filters
  const searchEl  = $('compare-search');
  const statusEl  = $('compare-status-filter');
  const typeEl    = $('compare-type-filter');

  const applyFilter = () => applyCompareFilter();
  searchEl.addEventListener('input', applyFilter);
  statusEl.addEventListener('change', applyFilter);
  typeEl.addEventListener('change', applyFilter);

  applyCompareFilter();
}

function applyCompareFilter() {
  const search = $('compare-search').value.toLowerCase().trim();
  const statusF = $('compare-status-filter').value;
  const typeF   = $('compare-type-filter').value;

  const groups = _state.groups;

  _state.compareFilteredOrder = _state.groupOrder.filter(itemKey => {
    const itemRows = groups[itemKey];
    const matchesSearch = !search ||
      itemKey.toLowerCase().includes(search) ||
      (itemRows[0].vendor || '').toLowerCase().includes(search) ||
      (itemRows[0].desc   || '').toLowerCase().includes(search);

    const matchesStatus = statusF === 'ALL' || itemRows.some(r => r.status === statusF);
    const matchesType   = typeF   === 'ALL' || itemRows.some(r => r.seg_type === typeF);

    return matchesSearch && matchesStatus && matchesType;
  });

  _state.comparePage = 1;
  const hasResults = _state.compareFilteredOrder.length > 0;
  $('compare-empty').classList.toggle('hidden', hasResults);
  $('compare-table-wrap').classList.toggle('hidden', !hasResults);
  $('compare-pagination').classList.toggle('hidden', !hasResults);

  if (hasResults) {
    renderComparePage();
  }
}

function renderComparePage() {
  const tbody = $('compare-tbody');
  const startIdx = (_state.comparePage - 1) * _state.pageSize;
  const endIdx = startIdx + _state.pageSize;
  const pageOrder = _state.compareFilteredOrder.slice(startIdx, endIdx);

  tbody.innerHTML = buildCompareRows(pageOrder, _state.groups, _state.futureWeeks, startIdx);

  // Collapse toggles
  tbody.querySelectorAll('.collapse-toggle').forEach(el => {
    el.addEventListener('click', () => {
      const groupId = el.dataset.group;
      const isCollapsed = el.classList.contains('collapsed');
      el.classList.toggle('collapsed');
      tbody.querySelectorAll(`tr[data-group="${groupId}"].group-child`).forEach(tr => {
        tr.classList.toggle('collapsed', !isCollapsed);
      });
    });
  });

  applyWeekVisibility();
  renderPaginationControls();
}

function renderPaginationControls() {
  const totalItems = _state.compareFilteredOrder.length;
  const totalPages = Math.ceil(totalItems / _state.pageSize) || 1;
  
  $('page-info').textContent = `Page ${_state.comparePage} of ${totalPages} (${totalItems} items)`;
  
  const prevBtn = $('page-prev');
  const nextBtn = $('page-next');
  
  prevBtn.disabled = _state.comparePage <= 1;
  nextBtn.disabled = _state.comparePage >= totalPages;
  
  prevBtn.onclick = () => {
    if (_state.comparePage > 1) {
      _state.comparePage--;
      renderComparePage();
      $('compare-table-wrap').scrollTop = 0;
    }
  };
  
  nextBtn.onclick = () => {
    if (_state.comparePage < totalPages) {
      _state.comparePage++;
      renderComparePage();
      $('compare-table-wrap').scrollTop = 0;
    }
  };
}

function buildCompareRows(groupOrder, groups, weeks, sttOffset) {
  const MAX = _state.MAX_WEEKS_DEFAULT;
  let html = '';
  let stt = sttOffset;
  let zebraFlag = false;

  groupOrder.forEach(itemKey => {
    stt++;
    zebraFlag = !zebraFlag;
    const zebraClass = zebraFlag ? 'group-zebra' : '';
    const groupId = `g${stt}`;
    const itemRows = groups[itemKey];

    itemRows.forEach((r, segIdx) => {
      const isLast = segIdx === itemRows.length - 1;
      const baseClass = `${zebraClass}`;

      // Helper to generate the metadata cells (common to all 4 rows)
      const makeMetaCells = (metricVal, showToggle) => {
        const flagBadge = (r.seg_type === 'Demand' && r.flag)
          ? `<span class="badge ${{ NEW: 'badge-new', REMOVED: 'badge-removed', SPIKE: 'badge-spike', DROP: 'badge-drop' }[r.status] || ''}">${esc(r.flag)}</span>`
          : '';
        const itemCellContent = showToggle
          ? `<span class="collapse-toggle" data-group="${groupId}"><span class="arrow">&#9660;</span> ${esc(r.item)}</span>`
          : esc(r.item);

        return `
          <td style="text-align:center;font-weight:700;color:var(--text-muted);">${stt}</td>
          <td style="font-weight:700;font-size:0.8rem;">${itemCellContent}</td>
          <td style="font-size:0.78rem;">${esc(r.vendor)}</td>
          <td style="font-size:0.78rem;white-space:normal;word-break:break-word;">${esc(r.desc)}</td>
          <td style="font-size:0.78rem;font-weight:600;text-align:center;">${esc(r.seg_type)}</td>
          <td class="metric-cell">${esc(metricVal)}</td>
          <td style="text-align:center;">${statusBadge(r.status)}</td>
          <td class="num-cell">${formatNumRaw(r.old_total)}</td>
          <td class="num-cell">${formatNumRaw(r.new_total)}</td>
          <td class="num-cell" style="font-weight:700;">${r.delta_total !== 0 ? (r.delta_total >= 0 ? '+' : '') + formatNumRaw(r.delta_total) : '-'}</td>
          <td class="num-cell" style="font-weight:700;">${formatPct(r.pct_total)}</td>
          <td style="text-align:center;">${flagBadge}</td>
        `;
      };

      // ---- OLD row ----
      const oldRowClass = `row-old ${baseClass}`;
      html += `<tr class="${oldRowClass}" data-group="${groupId}" data-item="${esc(r.item)}"
                   data-seg="${esc(r.seg_type)}" data-status="${r.status}">`;
      html += makeMetaCells(_state.oldLabel, segIdx === 0);
      // Week values OLD
      weeks.forEach((w, wi) => {
        const hidden = wi >= MAX ? ' week-col-hidden' : '';
        const wdata = r.weeks[wi] || {};
        const val = wdata.old || 0;
        html += `<td class="week-col week-col-wrapper${hidden}" data-week-idx="${wi}">${val !== 0 ? formatNumRaw(val) : ''}</td>`;
      });
      html += '</tr>';

      // ---- NEW row ----
      const newRowClass = `row-new ${baseClass} group-child`;
      html += `<tr class="${newRowClass}" data-group="${groupId}" data-item="${esc(r.item)}"
                   data-seg="${esc(r.seg_type)}" data-status="${r.status}">`;
      html += makeMetaCells(_state.newLabel, false);
      // Week values NEW
      weeks.forEach((w, wi) => {
        const hidden = wi >= MAX ? ' week-col-hidden' : '';
        const wdata = r.weeks[wi] || {};
        const val = wdata.new || 0;
        html += `<td class="week-col week-col-wrapper${hidden}" data-week-idx="${wi}">${val !== 0 ? formatNumRaw(val) : ''}</td>`;
      });
      html += '</tr>';

      // ---- DELTA row ----
      const deltaRowClass = `row-delta ${baseClass} group-child`;
      html += `<tr class="${deltaRowClass}" data-group="${groupId}" data-item="${esc(r.item)}"
                   data-seg="${esc(r.seg_type)}" data-status="${r.status}">`;
      html += makeMetaCells('Δ', false);
      // Week values Delta
      weeks.forEach((w, wi) => {
        const hidden = wi >= MAX ? ' week-col-hidden' : '';
        const wdata = r.weeks[wi] || { old: 0, new: 0, delta: 0, pct: 0 };
        const d = wdata.delta || 0;
        const p = wdata.pct || 0;
        const o = wdata.old || 0;
        const nv = wdata.new || 0;
        let cellVal = '';
        if (o !== 0 || nv !== 0) {
          const ds = d >= 0 ? '+' : '';
          cellVal = `${ds}${formatNumRaw(d)}`;
        }
        const hc = cellVal ? heatClass(p) : '';
        html += `<td class="week-col week-col-wrapper ${hc}${hidden}" data-week-idx="${wi}" style="font-weight:700;">${cellVal}</td>`;
      });
      html += '</tr>';

      // ---- PCT row ----
      const deltaEndClass = isLast ? 'group-end' : '';
      const pctRowClass = `row-pct ${baseClass} group-child ${deltaEndClass}`;
      html += `<tr class="${pctRowClass}" data-group="${groupId}" data-item="${esc(r.item)}"
                   data-seg="${esc(r.seg_type)}" data-status="${r.status}">`;
      html += makeMetaCells('%Δ', false);
      // Week values Pct
      weeks.forEach((w, wi) => {
        const hidden = wi >= MAX ? ' week-col-hidden' : '';
        const wdata = r.weeks[wi] || { old: 0, new: 0, delta: 0, pct: 0 };
        const p = wdata.pct || 0;
        const o = wdata.old || 0;
        const nv = wdata.new || 0;
        let cellVal = '';
        if (o !== 0 || nv !== 0) {
          cellVal = formatPct(p);
        }
        const hc = cellVal ? heatClass(p) : '';
        html += `<td class="week-col week-col-wrapper ${hc}${hidden}" data-week-idx="${wi}" style="font-weight:700;">${cellVal}</td>`;
      });
      html += '</tr>';
    });
  });

  return html;
}

// ── RENDER: Window 3W Tab ────────────────────────────────────────────
function renderWindowTab() {
  const data = _state.windowData;

  // KPI
  const demand = data.filter(a => a.seg_type === 'Demand');
  $('kpi-increase-count').textContent  = demand.filter(a => a.direction === 'INCREASE').length;
  $('kpi-decrease-count').textContent  = demand.filter(a => a.direction === 'DECREASE').length;
  $('kpi-newdemand-count').textContent = demand.filter(a => a.direction === 'NEW DEMAND').length;
  $('kpi-zeroout-count').textContent   = demand.filter(a => a.direction === 'ZERO OUT').length;

  // Render rows
  renderWindowRows(data);

  // Filters
  const searchEl = $('window-search');
  const dirEl    = $('window-direction-filter');
  const typeEl   = $('window-type-filter');
  const applyFilter = () => filterWindowTable();
  searchEl.addEventListener('input', applyFilter);
  dirEl.addEventListener('change', applyFilter);
  typeEl.addEventListener('change', applyFilter);
}

function renderWindowRows(data) {
  const tbody = $('window-tbody');
  if (!data || data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="17" style="text-align:center;padding:2rem;color:var(--text-muted);">No alerts generated.</td></tr>`;
    return;
  }

  let html = '';
  data.forEach((a, i) => {
    const pctClass = heatClass(a.pct);
    const dirCls = {
      'INCREASE':   'dir-increase',
      'DECREASE':   'dir-decrease',
      'NEW DEMAND': 'dir-newdemand',
      'ZERO OUT':   'dir-zeroout',
    }[a.direction] || '';

    const deltaSign = a.delta >= 0 ? '+' : '';
    const pctStr = formatPct(a.pct);

    html += `<tr data-direction="${esc(a.direction)}" data-seg="${esc(a.seg_type)}"
                 data-item="${esc(a.item)}" data-vendor="${esc(a.vendor)}" data-desc="${esc(a.desc)}">
      <td style="text-align:center;font-weight:700;color:var(--text-muted);">${i + 1}</td>
      <td style="font-weight:700;font-size:0.8rem;">${esc(a.item)}</td>
      <td style="font-size:0.78rem;white-space:normal;word-break:break-word;">${esc(a.desc)}</td>
      <td style="font-size:0.78rem;">${esc(a.vendor)}</td>
      <td style="text-align:center;font-size:0.78rem;">${esc(a.seg_type)}</td>
      <td style="text-align:center;"><span class="badge ${dirCls}">${esc(a.direction)}</span></td>
      <td style="text-align:center;font-weight:600;">${esc(a.zone_window)}</td>
      <td style="text-align:center;">${a.n_wks}</td>
      <td class="num-cell">${formatNumRaw(a.old_total)}</td>
      <td class="num-cell">${formatNumRaw(a.new_total)}</td>
      <td class="num-cell" style="font-weight:700;">${deltaSign}${formatNumRaw(a.delta)}</td>
      <td class="num-cell ${pctClass}" style="font-weight:700;">${pctStr}</td>
      <td style="text-align:center;">${a.lt}</td>
      <td style="text-align:center;">${formatNumRaw(a.moq)}</td>
      <td class="num-cell">${formatNumRaw(a.ss)}</td>
      <td class="num-cell">${formatNumRaw(a.ending)}</td>
      <td style="font-size:0.78rem;white-space:normal;word-break:break-word;line-height:1.4;">${esc(a.action)}</td>
    </tr>`;
  });

  tbody.innerHTML = html;
}

function filterWindowTable() {
  const search = $('window-search').value.toLowerCase().trim();
  const dirF   = $('window-direction-filter').value;
  const typeF  = $('window-type-filter').value;
  const tbody  = $('window-tbody');

  let count = 0;
  tbody.querySelectorAll('tr').forEach(tr => {
    const dir  = tr.dataset.direction || '';
    const seg  = tr.dataset.seg || '';
    const item = tr.dataset.item || '';
    const vend = tr.dataset.vendor || '';
    const desc = tr.dataset.desc || '';

    const matchSearch = !search ||
      item.toLowerCase().includes(search) ||
      vend.toLowerCase().includes(search) ||
      desc.toLowerCase().includes(search);
    const matchDir  = dirF  === 'ALL' || dir === dirF;
    const matchType = typeF === 'ALL' || seg === typeF;

    const visible = matchSearch && matchDir && matchType;
    tr.style.display = visible ? '' : 'none';
    if (visible) count++;
  });

  $('window-empty').classList.toggle('hidden', count > 0);
}

// ── Tab pane initial display fix ─────────────────────────────────────
document.querySelectorAll('.tab-pane').forEach(p => {
  if (!p.classList.contains('active')) p.style.display = 'none';
});
