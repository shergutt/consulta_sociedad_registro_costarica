import { state } from './state.js';
import { fetchJson, postJson, deleteJson } from './api.js';
import { el } from './utils.js';
import { showToast, confirmAction } from './ui.js';

export function initAdmin() {
  const panelBtn = document.querySelector('#adminPanelBtn');
  const dialog = document.querySelector('#adminDialog');
  const closeBtn = document.querySelector('#closeAdminBtn');
  const addForm = document.querySelector('#addUserForm');

  panelBtn?.addEventListener('click', () => {
    dialog?.showModal();
    loadUsers();
  });
  closeBtn?.addEventListener('click', () => dialog?.close());

  addForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = document.querySelector('#newUsername')?.value.trim();
    const password = document.querySelector('#newUserPassword')?.value;
    const role = document.querySelector('#newUserRole')?.value;

    try {
      await postJson('/api/users', { username, password, role });
      addForm.reset();
      await loadUsers();
      showToast('Usuario creado', 'success');
    } catch (error) {
      showToast(error.message, 'error');
    }
  });
}

async function loadUsers() {
  const list = document.querySelector('#userList');
  if (!list) return;
  try {
    const result = await fetchJson('/api/users');
    renderUserList(result.users || []);
  } catch (error) {
    list.replaceChildren(el('p', '', error.message));
  }
}

function renderUserList(users) {
  const list = document.querySelector('#userList');
  list.replaceChildren(
    ...users.map((user) => {
      const item = el('div', 'user-item');
      const info = el('div', 'user-info');
      info.append(el('strong', '', user.username));
      info.append(el('span', 'pill', user.role));
      item.append(info);

      if (user.id !== state.user?.id) {
        const deleteBtn = el('button', 'button button--ghost button--sm', 'Eliminar');
        deleteBtn.addEventListener('click', async () => {
          const ok = await confirmAction(`¿Eliminar usuario ${user.username}?`);
          if (!ok) return;
          try {
            await deleteJson(`/api/users/${user.id}`);
            await loadUsers();
            showToast('Usuario eliminado', 'success');
          } catch (error) {
            showToast(error.message, 'error');
          }
        });
        item.append(deleteBtn);
      }
      return item;
    }),
  );
}
