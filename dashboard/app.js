const state = {
  summary: null,
  persons: [],
  selectedCedula: null,
  detail: null,
  filter: '',
  fincaMode: 'all',
  activeJobId: null,
  jobTimer: null,
};

function initTheme() {
  const saved = localStorage.getItem('theme');
  const theme = saved || 'light';
  document.documentElement.setAttribute('data-theme', theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}

initTheme();

document.getElementById('themeToggle').addEventListener('click', toggleTheme);

const els = {
  personList: document.querySelector('#personList'),
  searchInput: document.querySelector('#searchInput'),
  metrics: document.querySelector('#metrics'),
  emptyState: document.querySelector('#emptyState'),
  detailView: document.querySelector('#detailView'),
  heroTitle: document.querySelector('#heroTitle'),
  heroSubtitle: document.querySelector('#heroSubtitle'),
  refreshBtn: document.querySelector('#refreshBtn'),
  openReportBtn: document.querySelector('#openReportBtn'),
  personName: document.querySelector('#personName'),
  personCedula: document.querySelector('#personCedula'),
  analysisFacts: document.querySelector('#analysisFacts'),
  alertCountBadge: document.querySelector('#alertCountBadge'),
  alertsList: document.querySelector('#alertsList'),
  fincaTools: document.querySelector('#fincaTools'),
  fincaGrid: document.querySelector('#fincaGrid'),
  assetCountBadge: document.querySelector('#assetCountBadge'),
  assetGrid: document.querySelector('#assetGrid'),
  outputList: document.querySelector('#outputList'),
  outputCountBadge: document.querySelector('#outputCountBadge'),
  sourceList: document.querySelector('#sourceList'),
  sourceDialog: document.querySelector('#sourceDialog'),
  sourceTitle: document.querySelector('#sourceTitle'),
  sourceContent: document.querySelector('#sourceContent'),
  closeSourceBtn: document.querySelector('#closeSourceBtn'),
  reportDialog: document.querySelector('#reportDialog'),
  reportContent: document.querySelector('#reportContent'),
  closeReportBtn: document.querySelector('#closeReportBtn'),
  aiRunForm: document.querySelector('#aiRunForm'),
  newCedulaInput: document.querySelector('#newCedulaInput'),
  runAnalysisBtn: document.querySelector('#runAnalysisBtn'),
  jobPanel: document.querySelector('#jobPanel'),
  jobStatus: document.querySelector('#jobStatus'),
  jobCedula: document.querySelector('#jobCedula'),
  jobLog: document.querySelector('#jobLog'),
};

function formatNumber(value) {
  const number = Number(value || 0);
  if (!Number.isFinite(number)) return String(value);
  return new Intl.NumberFormat('es-CR').format(number);
}

function formatMoney(value) {
  return new Intl.NumberFormat('es-CR', {
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function text(value, fallback = '-') {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

function el(tag, className, content) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.headers || {}),
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

async function postJson(url, payload) {
  return fetchJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

async function loadApp(preferredCedula = state.selectedCedula) {
  els.refreshBtn.disabled = true;
  try {
    const [summary, peoplePayload] = await Promise.all([
      fetchJson('/api/summary'),
      fetchJson('/api/persons'),
    ]);
    state.summary = summary;
    state.persons = peoplePayload.persons || [];
    renderMetrics();
    renderPersonList();

    const selected = preferredCedula || state.persons[0]?.cedula;
    if (selected) {
      await selectPerson(selected);
    } else {
      showEmpty('No hay personas guardadas', 'Corré el análisis y luego refrescá este dashboard.');
    }
  } catch (error) {
    showEmpty('No se pudo cargar la base', error.message);
  } finally {
    els.refreshBtn.disabled = false;
  }
}

function renderMetrics() {
  const summary = state.summary || {};
  const metrics = [
    ['Personas', summary.persons],
    ['Fincas', summary.fincas],
    ['Muebles', summary.movable_assets],
    ['Alertas', summary.alerts],
    ['Archivos', summary.source_files],
    ['Valor fiscal', formatMoney(summary.total_fiscal_value)],
  ];
  els.metrics.replaceChildren(
    ...metrics.map(([label, value], index) => {
      const card = el('article', 'metric');
      card.style.animationDelay = `${index * 45}ms`;
      card.append(el('span', '', label));
      card.append(el('strong', '', formatNumber(value)));
      return card;
    }),
  );
}

function renderPersonList() {
  const term = state.filter.trim().toLowerCase();
  const filtered = state.persons.filter((person) => {
    const haystack = `${person.cedula} ${person.nombre} ${person.first_name || ''}`.toLowerCase();
    return haystack.includes(term);
  });

  if (!filtered.length) {
    els.personList.replaceChildren(el('p', 'empty-note', 'Sin coincidencias.'));
    return;
  }

  const template = document.querySelector('#personTemplate');
  els.personList.replaceChildren(
    ...filtered.map((person) => {
      const node = template.content.firstElementChild.cloneNode(true);
      node.classList.toggle('active', person.cedula === state.selectedCedula);
      node.querySelector('.person-card-name').textContent = person.nombre || person.first_name || person.cedula;
      node.querySelector('.person-card-meta').textContent = `Cédula ${person.cedula}`;
      node.querySelector('.person-card-stats').textContent = `${person.finca_count || 0} fincas · ${person.movable_asset_count || 0} muebles · ${person.alert_count || 0} alertas`;
      node.addEventListener('click', () => selectPerson(person.cedula));
      return node;
    }),
  );
}

async function selectPerson(cedula) {
  state.selectedCedula = cedula;
  state.fincaMode = 'all';
  renderPersonList();
  const detail = await fetchJson(`/api/persons/${encodeURIComponent(cedula)}`);
  state.detail = detail;
  renderDetail();
}

function showEmpty(title, subtitle) {
  els.detailView.classList.add('hidden');
  els.emptyState.classList.remove('hidden');
  els.emptyState.querySelector('h3').textContent = title;
  els.emptyState.querySelector('p').textContent = subtitle;
  els.heroTitle.textContent = title;
  els.heroSubtitle.textContent = subtitle;
}

function renderDetail() {
  const detail = state.detail;
  if (!detail) return;
  const movableAssets = detail.movable_assets || [];

  els.emptyState.classList.add('hidden');
  els.detailView.classList.remove('hidden');
  els.heroTitle.textContent = detail.person.nombre || detail.person.cedula;
  els.heroSubtitle.textContent = `Último análisis: ${text(detail.analysis.updated_at)} · ${detail.analysis.folder_path}`;
  els.personName.textContent = detail.person.nombre || detail.person.first_name || detail.person.cedula;
  els.personCedula.textContent = detail.person.cedula;
  els.alertCountBadge.textContent = `${detail.alerts.length} alertas`;
  els.assetCountBadge.textContent = `${movableAssets.length} bienes`;

  renderFacts(detail);
  renderAlerts(detail.alerts);
  renderFincaTools(detail.fincas);
  renderFincas(detail.fincas);
  renderAssets(movableAssets);
  renderOutputs(detail.query_outputs);
  renderSources(detail.source_files);
}

function renderFacts(detail) {
  const outputCounts = detail.analysis.output_counts || {};
  const movableAssets = detail.movable_assets || [];
  const facts = [
    ['Fincas', detail.analysis.finca_count],
    ['Bienes muebles', movableAssets.length],
    ['Alertas', detail.analysis.alert_count],
    ['Finca número', outputCounts.finca_numero || 0],
    ['Catastro', outputCounts.catastro_plano || 0],
    ['Historia', outputCounts.historia_finca || 0],
    ['Diario', outputCounts.documento_diario || 0],
    ['Defectos', outputCounts.diario_defectos || 0],
    ['Primeras pres.', outputCounts.primeras_presentaciones || 0],
    ['Gravámenes', outputCounts.gravamen_hipoteca || 0],
    ['Anotaciones', outputCounts.anotaciones_tramites || 0],
    ['Valores finca', outputCounts.valores_finca || 0],
    ['Hist. gravámenes', outputCounts.historia_gravamenes_inmuebles || 0],
    ['Hist. muebles', outputCounts.historia_bienes_muebles || 0],
    ['Pres. muebles', outputCounts.historia_presentaciones_muebles || 0],
    ['Citas muebles', outputCounts.citas_presentacion_muebles || 0],
    ['Archivos fuente', detail.source_files.length],
    ['Run ID', detail.analysis.id],
  ];

  els.analysisFacts.replaceChildren(
    ...facts.map(([label, value]) => {
      const wrap = el('div');
      wrap.append(el('dt', '', label));
      wrap.append(el('dd', '', formatNumber(value)));
      return wrap;
    }),
  );
}

function renderAssets(assets) {
  if (!assets.length) {
    els.assetGrid.replaceChildren(el('div', 'compact-item', 'No hay bienes muebles guardados para este análisis.'));
    return;
  }

  els.assetGrid.replaceChildren(
    ...assets.map((asset, index) => {
      const card = el('article', 'asset-card');
      card.style.animationDelay = `${index * 35}ms`;

      const title = el('div', 'finca-title');
      const number = asset.numero || asset.placa || asset.serie || asset.vin || asset.motor || asset.identificacion;
      title.append(
        el('h4', '', `${text(asset.tipo, 'bien_mueble')} ${text(number)}`),
        el('span', 'pill', text(asset.estado, 'sin estado')),
      );

      const meta = el('div', 'asset-meta');
      [
        ['Placa', asset.placa],
        ['Marca', asset.marca],
        ['Modelo', asset.modelo],
        ['Año', asset.year],
        ['Serie', asset.serie],
        ['VIN', asset.vin],
        ['Motor', asset.motor],
        ['Chasis', asset.chasis],
      ].forEach(([label, value]) => {
        const box = el('div');
        box.append(el('span', '', label));
        box.append(el('strong', '', text(value)));
        meta.append(box);
      });

      card.append(title);
      card.append(meta);
      card.append(el('p', '', `Propietario: ${text(asset.propietario || asset.nombre)}`));
      card.append(el('p', '', `Gravámenes/anotaciones: ${text(asset.gravamenes || asset.anotaciones, 'Sin datos registrados.')}`));
      return card;
    }),
  );
}

function renderAlerts(alerts) {
  if (!alerts.length) {
    els.alertsList.replaceChildren(el('div', 'compact-item', 'Sin alertas automáticas.'));
    return;
  }

  els.alertsList.replaceChildren(
    ...alerts.map((alert) => {
      const item = el('article', `alert-item ${alert.severity}`);
      item.append(el('strong', '', `${alert.severity.toUpperCase()} · ${text(alert.label)}`));
      item.append(el('span', '', alert.message));
      return item;
    }),
  );
}

function renderFincaTools(fincas) {
  const riskyCount = fincas.filter((finca) => Number(finca.alert_count) > 0).length;
  const buttons = [
    ['all', `Todas (${fincas.length})`],
    ['alerts', `Con alertas (${riskyCount})`],
    ['clean', `Sin alertas (${fincas.length - riskyCount})`],
  ];

  els.fincaTools.replaceChildren(
    ...buttons.map(([mode, label]) => {
      const button = el('button', mode === state.fincaMode ? 'active' : '', label);
      button.addEventListener('click', () => {
        state.fincaMode = mode;
        renderFincaTools(state.detail.fincas);
        renderFincas(state.detail.fincas);
      });
      return button;
    }),
  );
}

function renderFincas(fincas) {
  const filtered = fincas.filter((finca) => {
    if (state.fincaMode === 'alerts') return Number(finca.alert_count) > 0;
    if (state.fincaMode === 'clean') return Number(finca.alert_count) === 0;
    return true;
  });

  els.fincaGrid.replaceChildren(
    ...filtered.map((finca, index) => {
      const card = el('article', 'finca-card');
      card.style.animationDelay = `${index * 35}ms`;

      const title = el('div', 'finca-title');
      const h4 = el('h4', '', `${text(finca.provincia)} ${text(finca.numero)} derecho ${text(finca.derecho)}`);
      const badge = el('span', Number(finca.alert_count) ? 'pill danger' : 'pill', Number(finca.alert_count) ? `${finca.alert_count} alertas` : 'sin alertas');
      title.append(h4, badge);

      const meta = el('div', 'finca-meta');
      [
        ['Matrícula', finca.matricula],
        ['Plano', finca.plano],
        ['Medida', finca.medida],
        ['Valor', finca.valor_fiscal_text],
        ['Zona catastrada', finca.zona_catastrada],
        ['ID predial', finca.identificador_predial],
        ['Gravámenes', finca.gravamenes],
        ['Anotaciones', finca.anotaciones],
      ].forEach(([label, value]) => {
        const box = el('div');
        box.append(el('span', '', label));
        box.append(el('strong', '', text(value)));
        meta.append(box);
      });

      card.append(title);
      card.append(el('p', 'finca-nature', text(finca.naturaleza)));
      card.append(meta);

      const detailRows = el('div', 'finca-detail-rows');
      [
        ['Ubicación', finca.ubicacion],
        ['Propietario', finca.propietario],
        ['Antecedentes', finca.antecedentes],
        ['Duplicado / horizontal', `${text(finca.duplicado)} / ${text(finca.horizontal)}`],
        ['Consultas vinculadas', `${formatNumber(finca.linked_output_count || 0)} outputs extra`],
        ['Fuentes', [finca.source_json, finca.source_txt, finca.source_html].filter(Boolean).join(' · ')],
      ].forEach(([label, value]) => {
        const row = el('div');
        row.append(el('span', '', label));
        row.append(el('strong', '', text(value)));
        detailRows.append(row);
      });
      card.append(detailRows);
      return card;
    }),
  );
}

const outputLabels = {
  finca_numero: 'Finca por número',
  catastro_plano: 'Catastro por plano',
  historia_finca: 'Historia de finca',
  gravamen_hipoteca: 'Gravamen/Hipoteca',
  documento_diario: 'Documento/Diario',
  diario_defectos: 'Diario de defectos',
  primeras_presentaciones: 'Primeras presentaciones',
  anotaciones_tramites: 'Anotaciones, trámites y marginales',
  valores_finca: 'Valores de finca',
  historia_gravamenes_inmuebles: 'Historia de gravámenes',
  historia_bienes_muebles: 'Historia de bienes muebles',
  historia_presentaciones_muebles: 'Historia presentaciones muebles',
  citas_presentacion_muebles: 'Citas presentación muebles',
  gravamenes_bienes_muebles: 'Gravámenes bienes muebles',
};

const outputPriority = [
  'finca_numero',
  'catastro_plano',
  'historia_finca',
  'valores_finca',
  'gravamen_hipoteca',
  'historia_gravamenes_inmuebles',
  'documento_diario',
  'diario_defectos',
  'anotaciones_tramites',
  'primeras_presentaciones',
  'historia_bienes_muebles',
  'historia_presentaciones_muebles',
  'citas_presentacion_muebles',
  'gravamenes_bienes_muebles',
];

function outputLabel(type) {
  return outputLabels[type] || type;
}

function sourceIdByPath(relativePath) {
  if (!relativePath || !state.detail?.source_files) return null;
  return state.detail.source_files.find((file) => file.relative_path === relativePath)?.id || null;
}

function makeSourceButton(label, relativePath) {
  const id = sourceIdByPath(relativePath);
  const button = el('button', 'mini-source', label);
  button.type = 'button';
  button.disabled = !id;
  button.title = relativePath || 'Sin archivo';
  if (id) button.addEventListener('click', () => openSource(id));
  return button;
}

function describeOutput(output) {
  return output.consulta || 'Consulta guardada en SQLite.';
}

function outputKind(type) {
  if (['historia_bienes_muebles', 'historia_presentaciones_muebles', 'citas_presentacion_muebles', 'gravamenes_bienes_muebles'].includes(type)) {
    return 'Bien mueble';
  }
  if (['documento_diario', 'diario_defectos', 'anotaciones_tramites', 'primeras_presentaciones'].includes(type)) {
    return 'Documento';
  }
  if (['gravamen_hipoteca', 'historia_gravamenes_inmuebles'].includes(type)) {
    return 'Gravamen';
  }
  return 'Finca';
}

function outputMetaRows(output) {
  return [
    ['Clave', output.lookup_key],
    ['Ámbito', outputKind(output.query_type)],
    ['Fincas', output.fincas || 'No vinculado a finca específica'],
    ['Guardado', output.created_at],
  ];
}

function renderOutputs(outputs) {
  els.outputCountBadge.textContent = outputs.length
    ? `${formatNumber(outputs.length)} ${outputs.length === 1 ? 'consulta' : 'consultas'}`
    : '';

  if (!outputs.length) {
    const empty = el('div', 'evidence-empty');
    empty.append(el('strong', '', 'Sin consultas guardadas'));
    empty.append(el('p', '', 'Ejecutá una consulta desde el panel de análisis para ver los respaldos aquí.'));
    els.outputList.replaceChildren(empty);
    return;
  }

  const groups = new Map();
  outputs.forEach((output) => {
    const key = output.query_type || 'otros';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(output);
  });

  const orderedGroups = [...groups.entries()].sort(([a], [b]) => {
    const ai = outputPriority.indexOf(a);
    const bi = outputPriority.indexOf(b);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi) || a.localeCompare(b);
  });

  const nav = el('div', 'evidence-nav');
  orderedGroups.forEach(([type, items]) => {
    const chip = el('button', 'evidence-chip');
    chip.type = 'button';
    chip.append(el('span', '', outputLabel(type)));
    chip.append(el('strong', '', formatNumber(items.length)));
    chip.addEventListener('click', (e) => {
      e.preventDefault();
      const target = content.querySelector(`#output-${type}`);
      const browser = els.outputList;
      if (target && browser) {
        const targetTop = target.offsetTop - browser.offsetTop;
        browser.scrollTo({ top: targetTop, behavior: 'smooth' });
      }
    });
    nav.append(chip);
  });

  const content = el('div', 'evidence-sections');
  orderedGroups.forEach(([type, items]) => {
    const section = el('section', 'evidence-section');
    section.id = `output-${type}`;

    const header = el('div', 'evidence-section-header');
    const titleWrap = el('div');
    titleWrap.append(el('span', 'eyebrow', outputKind(type)));
    titleWrap.append(el('h4', '', outputLabel(type)));
    header.append(titleWrap);
    header.append(el('span', 'pill', `${items.length} registros`));
    section.append(header);

    const list = el('div', 'evidence-list');
      items.forEach((output) => {
        const card = el('article', 'evidence-card');

        const cardMain = el('div', 'evidence-main');
        cardMain.append(el('strong', '', text(output.lookup_key)));
        cardMain.append(el('p', '', describeOutput(output)));

        const meta = el('dl', 'evidence-meta');
        outputMetaRows(output).forEach(([label, value]) => {
          const row = el('div');
          row.append(el('dt', '', label));
          row.append(el('dd', '', text(value)));
          meta.append(row);
        });
        cardMain.append(meta);

        const actions = el('div', 'source-actions');
        actions.append(
          makeSourceButton('TXT', output.source_txt),
          makeSourceButton('JSON', output.source_json),
          makeSourceButton('HTML', output.source_html),
        );

        card.append(cardMain, actions);
        list.append(card);
      });
    section.append(list);
    content.append(section);
  });

  els.outputList.replaceChildren(nav, content);
}

function renderSources(files) {
  if (!files.length) {
    els.sourceList.replaceChildren(el('div', 'compact-item', 'No hay archivos fuente guardados.'));
    return;
  }

  els.sourceList.replaceChildren(
    ...files.map((file) => {
      const button = el('button', 'source-item');
      button.append(el('strong', '', file.relative_path));
      button.append(el('span', '', `${file.file_type.toUpperCase()} · ${formatNumber(file.size_bytes)} bytes`));
      button.addEventListener('click', () => openSource(file.id));
      return button;
    }),
  );
}

async function startAnalysisJob(event) {
  event.preventDefault();
  const cedula = els.newCedulaInput.value.replace(/\D/g, '');
  if (!/^\d{9,12}$/.test(cedula)) {
    renderJob({
      cedula,
      status: 'failed',
      ai_model: 'minimax-m3',
      error: 'La cédula debe tener entre 9 y 12 dígitos.',
      log_tail: ['Entrada inválida.'],
    });
    return;
  }

  els.runAnalysisBtn.disabled = true;
  renderJob({
    cedula,
    status: 'queued',
    ai_model: 'minimax-m3',
    log_tail: ['Enviando job al servidor local...'],
  });

  try {
    const job = await postJson('/api/run-analysis', { cedula });
    state.activeJobId = job.id;
    renderJob(job);
    pollJob(job.id);
  } catch (error) {
    renderJob({
      cedula,
      status: 'failed',
      ai_model: 'minimax-m3',
      error: error.message,
      log_tail: [error.message],
    });
    els.runAnalysisBtn.disabled = false;
  }
}

function renderJob(job) {
  els.jobPanel.classList.remove('hidden');
  els.jobCedula.textContent = job.cedula ? `Cédula ${job.cedula}` : 'sin cédula';
  const statusLabels = {
    queued: 'En cola',
    running: 'Corriendo skill',
    succeeded: 'Completado',
    failed: 'Falló',
  };
  els.jobStatus.textContent = `${statusLabels[job.status] || job.status} · ${job.ai_model || 'minimax-m3'}`;
  const lines = [...(job.log_tail || [])];
  if (job.error) lines.push(`ERROR: ${job.error}`);
  els.jobLog.textContent = lines.join('\n') || 'Sin logs todavía.';
  els.jobLog.scrollTop = els.jobLog.scrollHeight;
}

function pollJob(jobId) {
  if (state.jobTimer) {
    clearInterval(state.jobTimer);
  }

  const tick = async () => {
    try {
      const job = await fetchJson(`/api/jobs/${encodeURIComponent(jobId)}`);
      renderJob(job);
      if (job.status === 'succeeded' || job.status === 'failed') {
        clearInterval(state.jobTimer);
        state.jobTimer = null;
        els.runAnalysisBtn.disabled = false;
        if (job.status === 'succeeded') {
          els.newCedulaInput.value = '';
          await loadApp(job.cedula);
        }
      }
    } catch (error) {
      renderJob({
        status: 'failed',
        ai_model: 'minimax-m3',
        error: error.message,
        log_tail: [error.message],
      });
      clearInterval(state.jobTimer);
      state.jobTimer = null;
      els.runAnalysisBtn.disabled = false;
    }
  };

  tick();
  state.jobTimer = setInterval(tick, 2500);
}

async function openSource(id) {
  els.sourceTitle.textContent = 'Cargando...';
  els.sourceContent.textContent = '';
  els.sourceDialog.showModal();
  try {
    const file = await fetchJson(`/api/source-files/${id}`);
    els.sourceTitle.textContent = file.relative_path;
    els.sourceContent.textContent = file.content_text || '';
  } catch (error) {
    els.sourceTitle.textContent = 'Error';
    els.sourceContent.textContent = error.message;
  }
}

function openReport() {
  if (!state.detail) return;
  els.reportContent.textContent = state.detail.analysis.report_markdown || 'Este análisis no tiene reporte Markdown guardado.';
  els.reportDialog.showModal();
}

els.refreshBtn.addEventListener('click', () => loadApp());
els.aiRunForm.addEventListener('submit', startAnalysisJob);
els.openReportBtn.addEventListener('click', openReport);
els.closeSourceBtn.addEventListener('click', () => els.sourceDialog.close());
els.closeReportBtn.addEventListener('click', () => els.reportDialog.close());
els.searchInput.addEventListener('input', (event) => {
  state.filter = event.target.value;
  renderPersonList();
});

loadApp();
