import { el, trapFocus, createSvgIcon, ICONS } from './utils.js';

let toastContainer = null;
let initializedDialogs = new WeakSet();

const TOAST_ICONS = {
  info: 'info',
  success: 'check',
  error: 'alert',
  warning: 'alert',
};

function ensureToastContainer() {
  if (!toastContainer) {
    toastContainer = el('div', 'toast-container');
    toastContainer.setAttribute('aria-live', 'polite');
    toastContainer.setAttribute('aria-atomic', 'true');
    document.body.append(toastContainer);
  }
  return toastContainer;
}

export function showToast(message, type = 'info') {
  const container = ensureToastContainer();
  const toast = el('div', `toast toast--${type}`);
  const iconKey = TOAST_ICONS[type] || 'info';
  const iconPaths = ICONS[iconKey] || ICONS.info;
  const icon = createSvgIcon(iconPaths, { size: 18, className: 'toast__icon' });
  const msg = el('p', 'toast__message', message);
  const close = el('button', 'toast__close');
  close.setAttribute('aria-label', 'Cerrar notificación');
  close.append(createSvgIcon(ICONS.close, { size: 14 }));
  const progress = el('span', 'toast__progress');

  let timeout;
  let paused = false;
  const dismiss = () => {
    clearTimeout(timeout);
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(28px)';
    setTimeout(() => toast.remove(), 200);
  };

  const scheduleDismiss = () => {
    timeout = setTimeout(dismiss, 5000);
  };

  close.addEventListener('click', dismiss);
  toast.addEventListener('mouseenter', () => {
    clearTimeout(timeout);
    paused = true;
  });
  toast.addEventListener('mouseleave', () => {
    if (paused) {
      paused = false;
      timeout = setTimeout(dismiss, 3000);
    }
  });
  toast.append(icon, msg, close, progress);
  container.append(toast);

  scheduleDismiss();
}

export function showEmptyState(title, message, iconName = 'search') {
  const node = el('div', 'empty-state');
  const iconWrap = el('div', 'empty-state__icon');
  iconWrap.append(createSvgIcon(ICONS[iconName] || ICONS.search, { width: 28, height: 28 }));
  node.append(iconWrap);
  node.append(el('strong', '', title));
  node.append(el('p', '', message));
  return node;
}

export function createSkeleton(type, count = 1) {
  const wrapper = el('div', '');
  for (let i = 0; i < count; i += 1) {
    wrapper.append(el('div', `skeleton skeleton--${type}`));
  }
  return wrapper;
}

/**
 * Wires up generic <dialog> behavior: backdrop click to close, [data-close] buttons,
 * and a close animation. Safe to call multiple times on the same dialog.
 * Returns a cleanup function that removes the listeners.
 */
export function bindDialog(dialog) {
  if (!dialog || initializedDialogs.has(dialog)) return () => {};
  initializedDialogs.add(dialog);

  const onBackdropClick = (event) => {
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      const insideDialog = event.clientX >= rect.left
        && event.clientX <= rect.right
        && event.clientY >= rect.top
        && event.clientY <= rect.bottom;
      if (!insideDialog) animateClose(dialog);
    }
  };

  const onCloseClick = (event) => {
    const btn = event.target.closest('[data-close]');
    if (btn && dialog.contains(btn)) {
      event.preventDefault();
      animateClose(dialog);
    }
  };

  const onCancel = (event) => {
    if (dialog.hasAttribute('data-no-animate')) return;
    event.preventDefault();
    animateClose(dialog);
  };

  dialog.addEventListener('click', onBackdropClick);
  dialog.addEventListener('click', onCloseClick);
  dialog.addEventListener('cancel', onCancel);

  return () => {
    dialog.removeEventListener('click', onBackdropClick);
    dialog.removeEventListener('click', onCloseClick);
    dialog.removeEventListener('cancel', onCancel);
    initializedDialogs.delete(dialog);
  };
}

function animateClose(dialog) {
  if (dialog.classList.contains('is-closing')) return;
  dialog.classList.add('is-closing');
  const duration = dialog.classList.contains('drawer') ? 220 : 200;

  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    dialog.removeEventListener('animationend', onEnd);
    clearTimeout(fallback);
    // Remove is-closing first, then close — keeps the close animation visible
    // for the full duration because [open] is still present.
    if (typeof dialog.close === 'function') {
      dialog.close();
    } else {
      dialog.removeAttribute('open');
    }
    dialog.classList.remove('is-closing');
  };

  const onEnd = (event) => {
    if (event.target !== dialog) return;
    finish();
  };

  const fallback = setTimeout(finish, duration + 50);
  dialog.addEventListener('animationend', onEnd);
}

/**
 * Opens a <dialog> with focus trap and backdrop-click handling.
 * Returns a cleanup function.
 */
export function openDialog(dialogId) {
  const dialog = typeof dialogId === 'string' ? document.querySelector(dialogId) : dialogId;
  if (!dialog) return () => {};
  bindDialog(dialog);
  if (typeof dialog.showModal === 'function') {
    if (!dialog.open) dialog.showModal();
  } else {
    dialog.setAttribute('open', '');
  }
  const release = trapFocus(dialog);
  return () => {
    release();
    if (typeof dialog.close === 'function') {
      if (dialog.open) dialog.close();
    } else {
      dialog.removeAttribute('open');
    }
  };
}

export function closeDialog(dialogId) {
  const dialog = typeof dialogId === 'string' ? document.querySelector(dialogId) : dialogId;
  if (!dialog) return;
  if (typeof dialog.close === 'function') {
    if (dialog.open) dialog.close();
  } else {
    dialog.removeAttribute('open');
  }
}

export function confirmAction(message, options = {}) {
  return new Promise((resolve) => {
    const dialog = document.querySelector('#confirmDialog');
    const messageEl = document.querySelector('#confirmMessage');
    const titleEl = document.querySelector('#confirmDialogTitle');
    const eyebrowEl = document.querySelector('#confirmDialogEyebrow');
    const confirmBtn = document.querySelector('#confirmYesBtn');

    if (!dialog || !messageEl || !confirmBtn) {
      resolve(confirm(message));
      return;
    }

    messageEl.textContent = message;
    if (titleEl) titleEl.textContent = options.title || 'Confirmar';
    if (eyebrowEl) {
      if (options.eyebrow) {
        eyebrowEl.textContent = options.eyebrow;
        eyebrowEl.hidden = false;
      } else {
        eyebrowEl.hidden = true;
      }
    }
    if (options.confirmText) confirmBtn.textContent = options.confirmText;
    if (options.danger === false) {
      confirmBtn.classList.remove('button--danger');
      confirmBtn.classList.add('button--primary');
    } else {
      confirmBtn.classList.add('button--danger');
      confirmBtn.classList.remove('button--primary');
    }

    bindDialog(dialog);
    if (typeof dialog.showModal === 'function') {
      if (!dialog.open) dialog.showModal();
    } else {
      dialog.setAttribute('open', '');
    }
    const release = trapFocus(dialog);

    const cleanup = () => {
      release();
      confirmBtn.removeEventListener('click', onConfirm);
      dialog.removeEventListener('close', onClose);
      if (typeof dialog.close === 'function') {
        if (dialog.open) dialog.close();
      } else {
        dialog.removeAttribute('open');
      }
    };

    const onConfirm = () => {
      cleanup();
      resolve(true);
    };
    const onClose = () => {
      cleanup();
      resolve(false);
    };

    confirmBtn.addEventListener('click', onConfirm);
    dialog.addEventListener('close', onClose, { once: true });
  });
}

export function renderIconButton(id, iconPath, label) {
  const button = el('button', 'button button--icon');
  button.id = id;
  button.setAttribute('aria-label', label);
  button.append(createSvgIcon(iconPath, 20));
  return button;
}
