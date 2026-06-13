import { createSvgIcon, ICONS, el } from './utils.js';

export function initTheme() {
  const saved = localStorage.getItem('theme');
  const theme = saved || 'light';
  document.documentElement.setAttribute('data-theme', theme);
}

export function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateThemeIcon(next);
}

export function updateThemeIcon(theme) {
  const button = document.querySelector('#themeToggle');
  if (!button) return;
  button.innerHTML = '';
  const icon = createSvgIcon(theme === 'dark' ? ICONS.sun : ICONS.moon, 18);
  const label = theme === 'dark' ? 'Modo claro' : 'Modo oscuro';
  button.setAttribute('aria-label', `Cambiar a ${label.toLowerCase()}`);
  button.append(icon, el('span', '', label));
}

export function renderThemeIcon() {
  const theme = document.documentElement.getAttribute('data-theme') || 'light';
  updateThemeIcon(theme);
}
