import { el, trapFocus, createSvgIcon, ICONS } from './utils.js';

let toastContainer = null;

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

  let timeout;
  const dismiss = () => {
    clearTimeout(timeout);
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(24px)';
    setTimeout(() => toast.remove(), 200);
  };

  close.addEventListener('click', dismiss);
  toast.append(icon, msg, close);
  container.append(toast);

  timeout = setTimeout(dismiss, 5000);
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

export function confirmAction(message) {
  return new Promise((resolve) => {
    const dialog = document.querySelector('#confirmDialog');
    const messageEl = document.querySelector('#confirmMessage');
    const confirmBtn = document.querySelector('#confirmYesBtn');
    const cancelBtns = document.querySelectorAll('[id^="confirmNoBtn"]');

    if (!dialog || !messageEl || !confirmBtn || !cancelBtns.length) {
      resolve(confirm(message));
      return;
    }

    messageEl.textContent = message;
    dialog.showModal();
    const release = trapFocus(dialog);

    const cleanup = () => {
      release();
      dialog.close();
      confirmBtn.removeEventListener('click', onConfirm);
      cancelBtns.forEach((btn) => btn.removeEventListener('click', onCancel));
      dialog.removeEventListener('close', onClose);
    };

    const onConfirm = () => {
      cleanup();
      resolve(true);
    };
    const onCancel = () => {
      cleanup();
      resolve(false);
    };
    const onClose = () => {
      cleanup();
      resolve(false);
    };

    confirmBtn.addEventListener('click', onConfirm);
    cancelBtns.forEach((btn) => btn.addEventListener('click', onCancel));
    dialog.addEventListener('close', onClose);
  });
}

export function openDialog(dialogId) {
  const dialog = document.querySelector(dialogId);
  if (!dialog) return () => {};
  dialog.showModal();
  const release = trapFocus(dialog);
  return () => {
    release();
    dialog.close();
  };
}

export function closeDialog(dialogId) {
  const dialog = document.querySelector(dialogId);
  if (dialog) dialog.close();
}

export function renderIconButton(id, iconPath, label) {
  const button = el('button', 'button button--icon');
  button.id = id;
  button.setAttribute('aria-label', label);
  button.append(createSvgIcon(iconPath, 20));
  return button;
}
