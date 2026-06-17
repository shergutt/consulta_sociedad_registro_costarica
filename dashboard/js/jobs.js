import { state, clearJobTimer, setActiveJobId, setJobTimer, setToken } from './state.js';
import { postJson, fetchJson } from './api.js';
import { el } from './utils.js';
import { showToast, openDialog, closeDialog, bindDialog } from './ui.js';

const statusLabels = {
  queued: 'En cola',
  running: 'Corriendo',
  succeeded: 'Completado',
  failed: 'Falló',
};

export function initJobs(loadAppFn) {
  const chip = document.querySelector('#jobStatus');
  const drawer = document.querySelector('#jobDrawer');
  const modal = document.querySelector('#newAnalysisModal');
  const form = document.querySelector('#newAnalysisForm');
  const input = document.querySelector('#newCedulaInput');
  const submitBtn = document.querySelector('#runAnalysisBtn');
  const openBtn = document.querySelector('#newAnalysisBtn');

  if (drawer) bindDialog(drawer);
  if (modal) bindDialog(modal);

  if (chip) chip.addEventListener('click', () => openDialog(drawer));
  if (openBtn) openBtn.addEventListener('click', () => {
    openDialog(modal);
    if (input) setTimeout(() => input.focus(), 100);
  });

  form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const cedula = input.value.replace(/\D/g, '');
    if (!/^\d{9,12}$/.test(cedula)) {
      showToast('La cédula debe tener entre 9 y 12 dígitos.', 'error');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '';
    submitBtn.append(el('span', 'spinner'), ' Iniciando…');

    try {
      const job = await postJson('/api/run-analysis', { cedula });
      setActiveJobId(job.id);
      renderJobChip(job);
      renderJobDrawer(job);
      closeDialog(modal);
      openDialog(drawer);
      pollJob(job.id, loadAppFn);
      showToast(`Análisis de ${cedula} iniciado`, 'info');
    } catch (error) {
      showToast(error.message, 'error');
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Iniciar análisis';
    }
  });
}

function renderJobChip(job) {
  const chip = document.querySelector('#jobStatus');
  if (!chip) return;

  const label = statusLabels[job.status] || job.status;
  const variant = job.status === 'running' ? 'running' : job.status === 'succeeded' ? 'success' : job.status === 'failed' ? 'error' : '';
  chip.className = `job-chip ${variant ? `job-chip--${variant}` : ''}`;
  chip.innerHTML = '';
  if (job.status === 'running') {
    chip.append(el('span', 'job-chip__dot'));
  }
  chip.append(el('span', '', `${label} · ${job.cedula}`));
  chip.classList.remove('hidden');
}

function renderJobDrawer(job) {
  const statusEl = document.querySelector('#jobDrawerStatus');
  const cedulaEl = document.querySelector('#jobDrawerCedula');
  const logEl = document.querySelector('#jobLog');
  if (!statusEl || !cedulaEl || !logEl) return;

  const label = statusLabels[job.status] || job.status;
  statusEl.textContent = `${label} · ${job.ai_model || 'minimax-m3'}`;
  cedulaEl.textContent = job.cedula ? `Cédula ${job.cedula}` : '';

  const lines = [...(job.log_tail || [])];
  if (job.error) lines.push(`ERROR: ${job.error}`);
  logEl.textContent = lines.join('\n') || 'Sin logs todavía.';
  logEl.scrollTop = logEl.scrollHeight;
}

function pollJob(jobId, loadAppFn) {
  clearJobTimer();

  const INTERVAL_MS = 2500;
  let timeoutId = null;

  const schedule = () => {
    timeoutId = setTimeout(tick, INTERVAL_MS);
    setJobTimer(timeoutId);
  };

  const tick = async () => {
    if (document.hidden) {
      schedule();
      return;
    }

    try {
      const job = await fetchJson(`/api/jobs/${encodeURIComponent(jobId)}`);
      renderJobChip(job);
      renderJobDrawer(job);
      if (job.status === 'succeeded' || job.status === 'failed') {
        clearJobTimer();
        if (job.status === 'succeeded') {
          showToast(`Análisis de ${job.cedula} completado`, 'success');
          await loadAppFn(job.cedula);
        } else {
          showToast(`Análisis de ${job.cedula} falló: ${job.error || 'sin detalle'}`, 'error');
        }
        return;
      }
    } catch (error) {
      clearJobTimer();
      showToast(error.message, 'error');
      return;
    }

    schedule();
  };

  tick();
}
