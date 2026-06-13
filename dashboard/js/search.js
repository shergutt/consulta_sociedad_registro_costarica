import { fetchJson } from './api.js';
import { el, debounce, text } from './utils.js';
import { showToast } from './ui.js';

const GROUP_LABELS = {
  person: 'Personas',
  finca: 'Fincas',
  bien_mueble: 'Bienes muebles',
};

export function initGlobalSearch(onSelect) {
  const trigger = document.querySelector('#searchTrigger');
  const palette = document.querySelector('#searchPalette');
  const backdrop = document.querySelector('#searchPaletteBackdrop');
  const input = document.querySelector('#searchPaletteInput');
  const results = document.querySelector('#searchPaletteResults');

  if (!trigger || !palette || !input || !results) return;

  let abortController = null;
  let selectedIndex = -1;
  let items = [];

  const open = () => {
    palette.classList.remove('hidden');
    if (backdrop) backdrop.classList.remove('hidden');
    input.value = '';
    input.focus();
    results.innerHTML = '';
    selectedIndex = -1;
    items = [];
  };

  const close = () => {
    palette.classList.add('hidden');
    if (backdrop) backdrop.classList.add('hidden');
    if (abortController) {
      abortController.abort();
      abortController = null;
    }
  };

  const renderItem = (result, index, totalItems) => {
    const button = el('button', 'command-palette__item');
    button.type = 'button';
    button.dataset.index = String(index);

    const title = el('span', '', resultLabel(result));
    const meta = el('span', 'command-palette__item-meta', resultMeta(result));
    button.append(title, meta);

    button.addEventListener('click', () => {
      onSelect(result);
      close();
    });

    return button;
  };

  const updateSelection = () => {
    results.querySelectorAll('.command-palette__item').forEach((node, idx) => {
      node.classList.toggle('command-palette__item--selected', idx === selectedIndex);
    });
    const active = results.querySelector('.command-palette__item--selected');
    if (active) active.scrollIntoView({ block: 'nearest' });
  };

  const performSearch = debounce(async (term) => {
    const clean = term.trim();
    if (clean.length < 3) {
      results.innerHTML = '';
      items = [];
      return;
    }

    if (abortController) abortController.abort();
    abortController = new AbortController();

    results.innerHTML = '';
    results.append(el('div', 'command-palette__empty', 'Buscando…'));

    try {
      const payload = await fetchJson(`/api/search?q=${encodeURIComponent(clean)}&limit=40`, {
        signal: abortController.signal,
      });
      const raw = payload.results || [];
      items = raw;
      results.innerHTML = '';

      if (raw.length === 0) {
        results.append(el('div', 'command-palette__empty', 'No se encontraron resultados.'));
        selectedIndex = -1;
        return;
      }

      const groups = groupResults(raw);
      let globalIndex = 0;

      Object.entries(groups).forEach(([type, groupItems]) => {
        const groupEl = el('div', 'command-palette__group');
        groupEl.append(el('div', 'command-palette__group-title', GROUP_LABELS[type] || type));
        groupItems.forEach((result) => {
          groupEl.append(renderItem(result, globalIndex, raw.length));
          globalIndex += 1;
        });
        results.append(groupEl);
      });

      selectedIndex = 0;
      updateSelection();
    } catch (error) {
      if (error.name === 'AbortError') return;
      results.innerHTML = '';
      results.append(el('div', 'command-palette__empty', `Error: ${error.message}`));
      selectedIndex = -1;
    }
  }, 300);

  trigger.addEventListener('click', open);
  backdrop?.addEventListener('click', close);

  document.addEventListener('keydown', (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
      event.preventDefault();
      open();
    }
    if (event.key === 'Escape' && !palette.classList.contains('hidden')) {
      close();
    }
  });

  input.addEventListener('input', (event) => performSearch(event.target.value));

  input.addEventListener('keydown', (event) => {
    if (items.length === 0) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      selectedIndex = (selectedIndex + 1) % items.length;
      updateSelection();
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      selectedIndex = (selectedIndex - 1 + items.length) % items.length;
      updateSelection();
    } else if (event.key === 'Enter' && selectedIndex >= 0) {
      event.preventDefault();
      onSelect(items[selectedIndex]);
      close();
    }
  });

  palette.addEventListener('click', (event) => {
    if (event.target === palette) close();
  });
}

function groupResults(results) {
  const groups = {};
  results.forEach((result) => {
    const type = result.result_type === 'bien_mueble' ? 'bien_mueble' : result.result_type;
    if (!groups[type]) groups[type] = [];
    groups[type].push(result);
  });
  return groups;
}

function resultLabel(result) {
  if (result.result_type === 'person') {
    return `${text(result.nombre)} · ${text(result.cedula)}`;
  }
  if (result.result_type === 'finca') {
    return `${text(result.provincia)} ${text(result.numero)} der. ${text(result.derecho)}`;
  }
  if (result.result_type === 'bien_mueble') {
    return `${text(result.tipo)} ${text(result.placa || result.matricula || result.numero)}`;
  }
  return 'Resultado';
}

function resultMeta(result) {
  if (result.result_type === 'person') return 'Persona';
  return text(result.cedula, 'sin cédula');
}
