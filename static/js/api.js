// C:\AI_YEREL\GK_STUDIO_V3\static\js\api.js
export const API = {
  async getStatus() {
    const res = await fetch('/api/status', { cache: 'no-store' });
    return res.json();
  },
  async getModels() {
    const res = await fetch('/api/models', { cache: 'no-store' });
    return res.json();
  },
  async chat(payload, signal) {
    return fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal
    });
  },
  async listProjects() {
    const res = await fetch('/api/projects/list', { cache: 'no-store' });
    return res.json();
  },
  async addProject(name, path, defaultModel) {
    const res = await fetch('/api/projects/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, path, default_model: defaultModel })
    });
    return res.json();
  },
  async indexProject(name) {
    const res = await fetch('/api/projects/index', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    return res.json();
  },
  async deleteProject(name) {
    const res = await fetch('/api/projects/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    return res.json();
  },
  async saveConversations(convs, currentConvId, nextId) {
    return fetch('/save-conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversations: convs, currentConvId, nextId })
    });
  },
  async loadProjectConversations(name) {
    const res = await fetch('/api/projects/conversations/load?name=' + encodeURIComponent(name), {
      cache: 'no-store'
    });
    return res.json();
  },
  async saveProjectConversations(projectName, convs, currentConvId, nextId) {
    const res = await fetch('/api/projects/conversations/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_name: projectName,
        conversations: convs,
        currentConvId,
        nextId
      })
    });
    return res.json();
  },
  async loadConversations() {
    const res = await fetch('/load-conversations', { cache: 'no-store' });
    return res.json();
  },
  async shutdown() {
    return fetch('/api/shutdown', { method: 'POST' });
  }
};