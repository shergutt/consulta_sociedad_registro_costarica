import {
  state, setUser, setToken, setPersons, setSummary, setDetail,
  selectCedula, setFilter, setFincaMode,
} from './state.js';
import { fetchJson, postJson } from './api.js';
import {
  formatNumber, formatMoney, text, el, createSvgIcon, ICONS,
} from './utils.js';
import { initTheme, renderThemeIcon, toggleTheme } from './theme.js';
import { showToast, showEmptyState, confirmAction, openDialog, closeDialog, bindDialog } from './ui.js';
import { initGlobalSearch } from './search.js';
import { initJobs } from './jobs.js';
import { initAdmin } from './admin.js';

const TABS = ['summary', 'fincas', 'muebles', 'evidencia', 'fuentes'];

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

const els = {
  loginScreen: document.querySelector('#loginScreen'),
  appShell: document.querySelector('#appShell'),
  loginForm: document.querySelector('#loginForm'),
  loginUsername: document.querySelector('#loginUsername'),
  loginPassword: document.querySelector('#loginPassword'),
  loginError: document.querySelector('#loginError'),
  userDisplay: document.querySelector('#userDisplay'),
  adminPanelBtn: document.querySelector('#adminPanelBtn'),
  logoutBtn: document.querySelector('#logoutBtn'),
  themeToggle: document.querySelector('#themeToggle'),
  personList: document.querySelector('#personList'),
  personFilter: document.querySelector('#personFilter'),
  personCount: document.querySelector('#personCount'),
  heroSection: document.querySelector('#heroSection'),
  heroTitle: document.querySelector('#heroTitle'),
  heroSubtitle: document.querySelector('#heroSubtitle'),
  refreshBtn: document.querySelector('#refreshBtn'),
  actionsDropdown: document.querySelector('#actionsDropdown'),
  actionsDropdownToggle: document.querySelector('#actionsDropdownToggle'),
  actionsDropdownMenu: document.querySelector('#actionsDropdownMenu'),
  openReportBtn: document.querySelector('#openReportBtn'),
  detailView: document.querySelector('#detailView'),
  detailLoading: document.querySelector('#detailLoading'),
  detailStats: document.querySelector('#detailStats'),
  emptyState: document.querySelector('#emptyState'),
  reportDialog: document.querySelector('#reportDialog'),
  reportContent: document.querySelector('#reportContent'),
  closeReportBtn: document.querySelector('#closeReportBtn'),
  sourceDialog: document.querySelector('#sourceDialog'),
  sourceTitle: document.querySelector('#sourceTitle'),
  sourceContent: document.querySelector('#sourceContent'),
  closeSourceBtn: document.querySelector('#closeSourceBtn'),
  sidePanel: document.querySelector('#sidePanel'),
  sidePanelToggle: document.querySelector('#sidePanelToggle'),
};

const TAB_BADGES = {
  summary: 'tab-summary',
  fincas: 'tab-fincas',
  muebles: 'tab-muebles',
  evidencia: 'tab-evidencia',
  fuentes: 'tab-fuentes',
};

function setTabBadge(tab, count) {
  const tabBtn = document.querySelector(`#${TAB_BADGES[tab]}`);
  if (!tabBtn) return;
  const badge = tabBtn.querySelector('.tab__badge');
  if (!badge) return;
  const value = Number(count) || 0;
  badge.dataset.count = String(value);
  badge.textContent = value > 0 ? formatNumber(value) : '';
}

function clearTabBadges() {
  Object.keys(TAB_BADGES).forEach((tab) => setTabBadge(tab, 0));
}

function renderDetailStats(detail) {
  if (!els.detailStats) return;
  els.detailStats.replaceChildren();

  const fincas = detail.fincas?.length || 0;
  const muebles = detail.movable_assets?.length || 0;
  const alertas = detail.alerts?.length || 0;
  const fuentes = detail.source_files?.length || 0;
  const outputs = detail.query_outputs?.length || 0;

  const chips = [
    { label: 'Fincas', value: fincas, variant: '', icon: ICONS.mapPin },
    { label: 'Muebles', value: muebles, variant: '', icon: ICONS.truck },
    { label: 'Evidencias', value: outputs, variant: '', icon: ICONS.fileText },
    { label: 'Fuentes', value: fuentes, variant: '', icon: ICONS.database },
    { label: 'Alertas', value: alertas, variant: alertas > 0 ? 'stat-chip--danger' : '', icon: ICONS.alert },
  ];

  chips.forEach(({ label, value, variant, icon }) => {
    const chip = el('span', `stat-chip ${variant}`.trim());
    const iconEl = createSvgIcon(icon, { size: 14 });
    chip.append(iconEl);
    chip.append(el('span', '', label));
    chip.append(el('span', 'stat-chip__value', formatNumber(value)));
    els.detailStats.append(chip);
  });
}

function initialsFromName(name) {
  if (!name) return '?';
  const cleaned = String(name)
    .trim()
    .replace(/\b(de|del|la|las|el|los|y)\b/gi, '')
    .replace(/\s+/g, ' ');
  const parts = cleaned.split(' ').filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

const AVATAR_COLORS = [
  ['#0aa8c9', '#0885a0'],
  ['#84cf0a', '#5fa300'],
  ['#b54444', '#963a3a'],
  ['#a9780a', '#7a5a08'],
  ['#7c4ddf', '#5a35b8'],
  ['#0aa8c9', '#0885a0'],
  ['#cf5fa0', '#a04576'],
  ['#3a8a4a', '#2a6a38'],
];

function avatarColorFor(name) {
  if (!name) return AVATAR_COLORS[0];
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  const [a, b] = AVATAR_COLORS[hash % AVATAR_COLORS.length];
  return `linear-gradient(135deg, ${a} 0%, ${b} 100%)`;
}

let currentTab = 'summary';

initTheme();
renderThemeIcon();

els.themeToggle?.addEventListener('click', toggleTheme);

function setActionsDropdownOpen(open) {
  els.actionsDropdownToggle?.setAttribute('aria-expanded', String(open));
  els.actionsDropdownMenu?.classList.toggle('hidden', !open);
}

els.actionsDropdownToggle?.addEventListener('click', (event) => {
  event.stopPropagation();
  const isOpen = els.actionsDropdownToggle?.getAttribute('aria-expanded') === 'true';
  setActionsDropdownOpen(!isOpen);
});

els.actionsDropdownMenu?.addEventListener('click', (event) => {
  const item = event.target.closest('[role="menuitem"]');
  if (item && item.id !== 'actionsDropdownToggle') {
    setActionsDropdownOpen(false);
  }
});

document.addEventListener('click', (event) => {
  if (!els.actionsDropdownMenu?.classList.contains('hidden') && !els.actionsDropdown?.contains(event.target)) {
    setActionsDropdownOpen(false);
  }
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && !els.actionsDropdownMenu?.classList.contains('hidden')) {
    setActionsDropdownOpen(false);
  }
  if (event.key === 'Escape' && els.sidePanel?.classList.contains('side-panel--open')) {
    setSidePanelOpen(false);
  }
});

els.loginForm?.addEventListener('submit', handleLogin);
els.logoutBtn?.addEventListener('click', handleLogout);
els.refreshBtn?.addEventListener('click', () => loadApp());
els.openReportBtn?.addEventListener('click', openReport);
document.querySelector('#openReportBtn2')?.addEventListener('click', openReport);
els.reportDialog && bindDialog(els.reportDialog);
els.sourceDialog && bindDialog(els.sourceDialog);

els.personFilter?.addEventListener('input', (event) => {
  setFilter(event.target.value);
  renderPersonList();
});

const backdrop = document.querySelector('#sidePanelBackdrop');

function setSidePanelOpen(open) {
  els.sidePanel?.classList.toggle('side-panel--open', open);
  if (backdrop) {
    backdrop.classList.toggle('hidden', !open);
  }
}

els.sidePanelToggle?.addEventListener('click', () => {
  setSidePanelOpen(!els.sidePanel.classList.contains('side-panel--open'));
});

backdrop?.addEventListener('click', () => {
  setSidePanelOpen(false);
});

window.addEventListener('session-expired', () => {
  showToast('Sesión expirada. Iniciá sesión de nuevo.', 'error');
  showLogin();
});

initGlobalSearch(handleSearchSelect);
initJobs(loadApp);
initAdmin();

TABS.forEach((tab) => {
  document.querySelector(`#tab-${tab}`)?.addEventListener('click', () => switchTab(tab));
});

async function handleLogin(event) {
  event.preventDefault();
  els.loginError.classList.add('hidden');
  const username = els.loginUsername.value.trim();
  const password = els.loginPassword.value;

  try {
    const result = await postJson('/api/login', { username, password });
    setToken(result.token);
    setUser(result.user);
    showApp();
    showToast(`Bienvenido, ${result.user.username}`, 'success');
  } catch (error) {
    els.loginError.textContent = error.message;
    els.loginError.classList.remove('hidden');
  }
}

async function handleLogout() {
  const ok = await confirmAction('¿Cerrar sesión?');
  if (!ok) return;

  if (state.token) {
    try {
      await postJson('/api/logout', {});
    } catch {}
  }
  setToken(null);
  setUser(null);
  showLogin();
  showToast('Sesión cerrada', 'info');
}

async function checkSession() {
  if (!state.token) {
    showLogin();
    return;
  }
  try {
    const user = await fetchJson('/api/me');
    setUser(user);
    showApp();
  } catch {
    setToken(null);
    showLogin();
  }
}

function showLogin() {
  els.loginScreen.classList.remove('hidden');
  els.appShell.classList.add('hidden');
}

function showApp() {
  els.loginScreen.classList.add('hidden');
  els.appShell.classList.remove('hidden');
  els.userDisplay.textContent = `${state.user.username} (${state.user.role})`;
  if (state.user.role === 'admin') {
    els.adminPanelBtn?.classList.remove('hidden');
  } else {
    els.adminPanelBtn?.classList.add('hidden');
  }
  loadApp();
}

async function loadApp(preferredCedula = state.selectedCedula) {
  els.refreshBtn.disabled = true;
  try {
    const [summary, peoplePayload] = await Promise.all([
      fetchJson('/api/summary'),
      fetchJson('/api/persons'),
    ]);
    setSummary(summary);
    setPersons(peoplePayload.persons || []);
    renderPersonList();

    const selected = preferredCedula || state.persons[0]?.cedula;
    if (selected) {
      await selectPerson(selected);
    } else {
      showEmpty('No hay datos seleccionados', 'Ejecutá un análisis o seleccioná una persona de la lista.');
    }
  } catch (error) {
    showEmpty('No se pudo cargar la base', error.message);
  } finally {
    els.refreshBtn.disabled = false;
  }
}

function renderPersonList() {
  const term = state.filter.trim().toLowerCase();
  const filtered = state.persons.filter((person) => {
    const haystack = `${person.cedula} ${person.nombre} ${person.first_name || ''}`.toLowerCase();
    return haystack.includes(term);
  });

  if (els.personCount) {
    els.personCount.textContent = formatNumber(filtered.length);
    els.personCount.dataset.total = String(filtered.length);
  }

  if (!filtered.length) {
    els.personList.replaceChildren(showEmptyState('Sin coincidencias', 'Probá con otro término o ejecutá un nuevo análisis.', 'searchX'));
    return;
  }

  els.personList.replaceChildren(
    ...filtered.map((person) => {
      const button = el('button', `person-card ${person.cedula === state.selectedCedula ? 'person-card--active' : ''}`);
      const name = person.nombre || person.first_name || person.cedula;
      const avatar = el('span', 'person-card__avatar', initialsFromName(name));
      avatar.style.background = avatarColorFor(name);
      button.append(avatar);
      button.append(el('span', 'person-card__name', name));
      button.append(el('span', 'person-card__meta', `Cédula ${person.cedula}`));
      button.append(el('span', 'person-card__stats', `${formatNumber(person.finca_count || 0)} fincas · ${formatNumber(person.movable_asset_count || 0)} muebles · ${formatNumber(person.alert_count || 0)} alertas`));
      button.addEventListener('click', () => {
        selectPerson(person.cedula);
        setSidePanelOpen(false);
      });
      return button;
    }),
  );
}

async function selectPerson(cedula) {
  if (cedula === state.selectedCedula && state.detail) return;
  selectCedula(cedula);
  setFincaMode('all');
  renderPersonList();
  setDetailLoading(true);

  try {
    const detail = await fetchJson(`/api/persons/${encodeURIComponent(cedula)}`);
    setDetail(detail);
    renderDetail();
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    setDetailLoading(false);
  }
}

function setDetailLoading(loading) {
  els.detailLoading.classList.toggle('hidden', !loading);
  if (loading) {
    els.detailView.classList.add('hidden');
    els.emptyState.classList.add('hidden');
    els.heroSection.classList.add('hidden');
    clearTabBadges();
    if (els.detailStats) els.detailStats.replaceChildren();
  }
}

function showEmpty(title, subtitle) {
  els.detailView.classList.add('hidden');
  els.detailLoading.classList.add('hidden');
  els.heroSection.classList.remove('hidden');
  els.emptyState.classList.remove('hidden');
  els.emptyState.querySelector('strong').textContent = title;
  els.emptyState.querySelector('p').textContent = subtitle;
  els.heroTitle.textContent = title;
  els.heroSubtitle.textContent = subtitle;
  els.openReportBtn?.classList.add('hidden');
  clearTabBadges();
  if (els.detailStats) els.detailStats.replaceChildren();
}

function renderDetail() {
  const detail = state.detail;
  if (!detail) return;

  els.emptyState.classList.add('hidden');
  els.detailLoading.classList.add('hidden');
  els.heroSection.classList.add('hidden');
  els.detailView.classList.remove('hidden');

  const detailTitle = els.detailView.querySelector('#detailTitle');
  const detailMeta = els.detailView.querySelector('#detailMeta');
  if (detailTitle) detailTitle.textContent = detail.person.nombre || detail.person.cedula;
  if (detailMeta) detailMeta.textContent = `Último análisis: ${text(detail.analysis.updated_at)} · ${detail.analysis.folder_path}`;
  els.openReportBtn.classList.toggle('hidden', !detail.analysis.report_markdown);
  els.detailView.querySelector('#openReportBtn2')?.classList.toggle('hidden', !detail.analysis.report_markdown);

  renderDetailStats(detail);

  const outputs = detail.query_outputs?.length || 0;
  setTabBadge('summary', detail.alerts?.length || 0);
  setTabBadge('fincas', detail.fincas?.length || 0);
  setTabBadge('muebles', detail.movable_assets?.length || 0);
  setTabBadge('evidencia', outputs);
  setTabBadge('fuentes', detail.source_files?.length || 0);

  renderSummaryTab(detail);
  renderFincasTab(detail);
  renderMueblesTab(detail);
  renderEvidenciaTab(detail);
  renderFuentesTab(detail);

  switchTab(currentTab);
}

function switchTab(tab) {
  currentTab = tab;
  TABS.forEach((t) => {
    document.querySelector(`#tab-${t}`)?.classList.toggle('tab--active', t === tab);
    document.querySelector(`#panel-${t}`)?.classList.toggle('tab-panel--active', t === tab);
  });
}

function renderSummaryTab(detail) {
  const panel = document.querySelector('#panel-summary');
  if (!panel) return;
  panel.innerHTML = '';

  const personCard = el('article', 'card');
  const header = el('div', 'card__header');
  const titleWrap = el('div');
  titleWrap.append(el('p', 'eyebrow', 'Persona'));
  titleWrap.append(el('h3', 'card__title', detail.person.nombre || detail.person.cedula));
  header.append(titleWrap, el('span', 'pill pill--muted', detail.person.cedula));
  personCard.append(header);

  const outputCounts = detail.analysis.output_counts || {};
  const facts = el('dl', 'facts');
  [
    ['Fincas', detail.fincas.length],
    ['Bienes muebles', detail.movable_assets.length],
    ['Alertas', detail.alerts.length],
    ['Archivos fuente', detail.source_files.length],
    ['Finca número', outputCounts.finca_numero || 0],
    ['Catastro', outputCounts.catastro_plano || 0],
    ['Historia', outputCounts.historia_finca || 0],
    ['Diario', outputCounts.documento_diario || 0],
    ['Defectos', outputCounts.diario_defectos || 0],
    ['Primeras pres.', outputCounts.primeras_presentaciones || 0],
    ['Gravámenes', outputCounts.gravamen_hipoteca || 0],
    ['Anotaciones', outputCounts.anotaciones_tramites || 0],
    ['Valores finca', outputCounts.valores_finca || 0],
    ['Run ID', detail.analysis.id],
  ].forEach(([label, value]) => {
    const wrap = el('div');
    wrap.append(el('dt', '', label));
    wrap.append(el('dd', '', formatNumber(value)));
    facts.append(wrap);
  });
  personCard.append(facts);
  panel.append(personCard);

  const alertCard = el('article', 'card');
  const alertHeader = el('div', 'card__header');
  const alertTitleWrap = el('div');
  alertTitleWrap.append(el('p', 'eyebrow', 'Alertas'));
  alertTitleWrap.append(el('h3', 'card__title', 'Señales automáticas'));
  alertHeader.append(alertTitleWrap, el('span', `pill ${detail.alerts.length ? 'pill--danger' : 'pill--success'}`, `${formatNumber(detail.alerts.length)} ${detail.alerts.length === 1 ? 'alerta' : 'alertas'}`));
  alertCard.append(alertHeader);

  if (!detail.alerts.length) {
    alertCard.append(showEmptyState('Sin alertas automáticas', 'No se detectaron señales de riesgo en este análisis.', 'alert'));
  } else {
    const list = el('div', 'alert-list');
    detail.alerts.forEach((alert) => {
      const item = el('article', `alert-item alert-item--${alert.severity || 'low'}`);
      item.append(el('strong', '', `${(alert.severity || 'low').toUpperCase()} · ${text(alert.label)}`));
      item.append(el('span', '', alert.message));
      list.append(item);
    });
    alertCard.append(list);
  }
  panel.append(alertCard);
}

function renderFincasTab(detail) {
  const panel = document.querySelector('#panel-fincas');
  if (!panel) return;
  panel.innerHTML = '';

  const riskyCount = detail.fincas.filter((f) => Number(f.alert_count) > 0).length;
  const tools = el('div', 'segmented');
  [
    ['all', `Todas (${detail.fincas.length})`],
    ['alerts', `Con alertas (${riskyCount})`],
    ['clean', `Sin alertas (${detail.fincas.length - riskyCount})`],
  ].forEach(([mode, label]) => {
    const button = el('button', mode === state.fincaMode ? 'active' : '', label);
    button.addEventListener('click', () => {
      setFincaMode(mode);
      renderFincasTab(detail);
    });
    tools.append(button);
  });
  panel.append(tools);

  const filtered = detail.fincas.filter((finca) => {
    if (state.fincaMode === 'alerts') return Number(finca.alert_count) > 0;
    if (state.fincaMode === 'clean') return Number(finca.alert_count) === 0;
    return true;
  });

  if (!filtered.length) {
    panel.append(showEmptyState('No hay fincas', 'No se encontraron fincas para este filtro.', 'mapPin'));
    return;
  }

  const grid = el('div', 'finca-grid');
  filtered.forEach((finca) => {
    const card = el('article', 'finca-card');
    const header = el('div', 'finca-card__header');
    header.append(el('h4', 'finca-card__title', `${text(finca.provincia)} ${text(finca.numero)} derecho ${text(finca.derecho)}`));
    const alertCount = Number(finca.alert_count) || 0;
    header.append(el('span', alertCount ? 'pill pill--danger' : 'pill pill--muted', alertCount ? `${formatNumber(alertCount)} ${alertCount === 1 ? 'alerta' : 'alertas'}` : 'sin alertas'));
    card.append(header);
    if (finca.naturaleza) card.append(el('p', 'finca-card__nature', text(finca.naturaleza)));

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
    grid.append(card);
  });
  panel.append(grid);
}

function renderMueblesTab(detail) {
  const panel = document.querySelector('#panel-muebles');
  if (!panel) return;
  panel.innerHTML = '';

  const assets = detail.movable_assets || [];
  if (!assets.length) {
    panel.append(showEmptyState('No hay bienes muebles', 'No se encontraron vehículos ni otros activos para esta persona.', 'truck'));
    return;
  }

  const grid = el('div', 'asset-grid');
  assets.forEach((asset) => {
    const card = el('article', 'asset-card');
    const header = el('div', 'asset-card__header');
    const number = asset.numero || asset.placa || asset.serie || asset.vin || asset.motor || asset.identificacion;
    header.append(el('h4', 'asset-card__title', `${text(asset.tipo, 'bien_mueble')} ${text(number)}`));
    const estadoText = text(asset.estado, '');
    header.append(el('span', estadoText ? 'pill pill--info' : 'pill pill--muted', estadoText || 'sin estado'));
    card.append(header);

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
    card.append(meta);
    card.append(el('p', '', `Propietario: ${text(asset.propietario || asset.nombre)}`));
    card.append(el('p', '', `Gravámenes/anotaciones: ${text(asset.gravamenes || asset.anotaciones, 'Sin datos registrados.')}`));
    grid.append(card);
  });
  panel.append(grid);
}

function renderEvidenciaTab(detail) {
  const panel = document.querySelector('#panel-evidencia');
  if (!panel) return;
  panel.innerHTML = '';

  const outputs = detail.query_outputs || [];
  if (!outputs.length) {
    panel.append(showEmptyState('Sin consultas guardadas', 'Ejecutá una consulta desde el panel de análisis para ver los respaldos aquí.', 'fileText'));
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

  const browser = el('div', 'evidence-browser');
  const nav = el('div', 'evidence-nav');
  const content = el('div', 'evidence-sections');

  orderedGroups.forEach(([type, items]) => {
    const chip = el('button', 'evidence-chip');
    chip.type = 'button';
    chip.append(el('span', '', outputLabel(type)));
    chip.append(el('strong', '', formatNumber(items.length)));
    chip.addEventListener('click', () => {
      const target = content.querySelector(`#output-${type}`);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    nav.append(chip);

    const section = el('section', 'evidence-section');
    section.id = `output-${type}`;

    const header = el('div', 'evidence-section__header');
    const titleWrap = el('div');
    titleWrap.append(el('p', 'eyebrow', outputKind(type)));
    titleWrap.append(el('h4', '', outputLabel(type)));
    header.append(titleWrap, el('span', 'pill', `${items.length} registros`));
    section.append(header);

    const list = el('div', 'evidence-list');
    items.forEach((output) => {
      const card = el('article', 'evidence-card');
      const main = el('div', 'evidence-card__main');
      main.append(el('strong', '', text(output.lookup_key)));
      main.append(el('p', '', output.consulta || 'Consulta guardada en SQLite.'));

      const meta = el('dl', 'evidence-meta');
      [
        ['Clave', output.lookup_key],
        ['Ámbito', outputKind(output.query_type)],
        ['Fincas', output.fincas || 'No vinculado'],
        ['Guardado', output.created_at],
      ].forEach(([label, value]) => {
        const row = el('div');
        row.append(el('dt', '', label));
        row.append(el('dd', '', text(value)));
        meta.append(row);
      });
      main.append(meta);

      const actions = el('div', 'source-actions');
      actions.append(makeSourceButton('TXT', output.source_txt));
      actions.append(makeSourceButton('JSON', output.source_json));
      actions.append(makeSourceButton('HTML', output.source_html));

      card.append(main, actions);
      list.append(card);
    });
    section.append(list);
    content.append(section);
  });

  browser.append(nav, content);
  panel.append(browser);

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const id = entry.target.id.replace('output-', '');
        nav.querySelectorAll('.evidence-chip').forEach((chip) => {
          chip.classList.toggle('evidence-chip--active', chip.querySelector('span')?.textContent === outputLabel(id));
        });
      }
    });
  }, { root: browser, rootMargin: '-40% 0px -40% 0px', threshold: 0 });

  content.querySelectorAll('.evidence-section').forEach((section) => observer.observe(section));
}

function renderFuentesTab(detail) {
  const panel = document.querySelector('#panel-fuentes');
  if (!panel) return;
  panel.innerHTML = '';

  const files = detail.source_files || [];
  if (!files.length) {
    panel.append(showEmptyState('No hay archivos fuente', 'No se guardaron respaldos para este análisis.', 'database'));
    return;
  }

  const list = el('div', 'source-list');
  files.forEach((file) => {
    const button = el('button', 'source-item');
    button.append(el('strong', '', file.relative_path));
    button.append(el('span', '', `${file.file_type.toUpperCase()} · ${formatNumber(file.size_bytes)} bytes`));
    button.addEventListener('click', () => openSource(file.id));
    list.append(button);
  });
  panel.append(list);
}

async function openSource(id) {
  els.sourceTitle.textContent = 'Cargando...';
  els.sourceContent.textContent = '';
  openDialog(els.sourceDialog);
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
  openDialog(els.reportDialog);
}

async function handleSearchSelect(result) {
  if (!result) return;
  if (result.result_type === 'finca') currentTab = 'fincas';
  else if (result.result_type === 'bien_mueble') currentTab = 'muebles';
  await selectPerson(result.cedula);
  document.querySelector('#mainContent')?.scrollTo({ top: 0, behavior: 'smooth' });
}

function outputLabel(type) {
  return outputLabels[type] || type;
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

checkSession();
