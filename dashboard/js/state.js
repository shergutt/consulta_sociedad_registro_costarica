export const state = {
  summary: null,
  persons: [],
  selectedCedula: null,
  detail: null,
  filter: '',
  fincaMode: 'all',
  activeJobId: null,
  jobTimer: null,
  user: null,
  token: localStorage.getItem('rnp_token'),
};

export function setUser(user) {
  state.user = user;
}

export function setToken(token) {
  state.token = token;
  if (token) {
    localStorage.setItem('rnp_token', token);
  } else {
    localStorage.removeItem('rnp_token');
  }
}

export function setPersons(persons) {
  state.persons = persons || [];
}

export function setSummary(summary) {
  state.summary = summary;
}

export function setDetail(detail) {
  state.detail = detail;
}

export function selectCedula(cedula) {
  state.selectedCedula = cedula;
}

export function setFilter(filter) {
  state.filter = filter;
}

export function setFincaMode(mode) {
  state.fincaMode = mode;
}

export function setActiveJobId(id) {
  state.activeJobId = id;
}

export function setJobTimer(timer) {
  state.jobTimer = timer;
}

export function clearJobTimer() {
  if (state.jobTimer) {
    clearInterval(state.jobTimer);
    state.jobTimer = null;
  }
}
