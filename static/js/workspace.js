// C:\AI_YEREL\GK_STUDIO_V3\static\js\workspace.js
import { API } from './api.js';
import { State } from './state.js';

function makeProjectConversationId(projectName, oldId = '') {
  const existing = String(oldId || '');
  if (existing.startsWith('p_')) return existing;

  const safe = String(projectName || 'project')
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .slice(0, 24);

  return `p_${safe}_${existing || Date.now()}`;
}

export const Workspace = {
  initWorkspaceUI(onRender) {
    this.refreshProjectList(onRender);

    const addBtn = document.getElementById('addProjectBtn');
    if (addBtn) {
      addBtn.onclick = async () => {
        const name = prompt("Proje / Çalışma Alanı Adı:");
        if (!name) return;
        const path = prompt("Klasör Dizin Yolu (örn: C:\\Projelerim\\Muhasebe):");
        if (!path) return;
        try {
          const res = await API.addProject(name, path, "auto");
          if (res.status === 'success') {
            alert(res.message);
            await this.activateProject(name, onRender);
          } else {
            alert('Hata: ' + res.message);
          }
        } catch (e) {
          alert('Hata: ' + e.message);
        }
      };
    }

    const exitBtn = document.getElementById('exitWorkspaceBtn');
    if (exitBtn) {
      exitBtn.onclick = () => this.exitProject(onRender);
    }
  },

  async refreshProjectList(onRender) {
    const listEl = document.getElementById('projectList');
    const banner = document.getElementById('activeProjectBanner');
    const bannerLabel = document.getElementById('activeProjectBannerLabel');

    if (banner && bannerLabel) {
      if (State.activeProjectName) {
        banner.style.display = 'flex';
        bannerLabel.textContent = `⚡ AKTİF WORKSPACE (RAG): ${State.activeProjectName}`;
      } else {
        banner.style.display = 'none';
      }
    }

    if (!listEl) return;

    try {
      const data = await API.listProjects();
      listEl.innerHTML = '';
      const projects = data.projects || {};

      Object.keys(projects).forEach(pName => {
        const proj = projects[pName];
        const isActive = State.activeProjectName === pName;

        const div = document.createElement('div');
        div.className = 'proj-item' + (isActive ? ' active' : '');

        const header = document.createElement('div');
        header.className = 'proj-header';

        const title = document.createElement('span');
        title.className = 'proj-title';
        title.textContent = (proj.indexed ? '⚡ ' : '📁 ') + pName;
        title.onclick = () => this.activateProject(pName, onRender);
        header.appendChild(title);

        const toolbar = document.createElement('div');
        toolbar.className = 'proj-toolbar';

        const runBtn = document.createElement('button');
        runBtn.className = 'proj-btn-action run';
        runBtn.textContent = isActive ? '⏹️ Çık' : '▶️ Çalıştır';
        runBtn.onclick = e => {
          e.stopPropagation();
          if (isActive) this.exitProject(onRender);
          else this.activateProject(pName, onRender);
        };

        const idxBtn = document.createElement('button');
        idxBtn.className = 'proj-btn-action idx';
        idxBtn.textContent = proj.indexed ? '⚡ Yenile' : '⚡ İndeksle';
        idxBtn.onclick = async e => {
          e.stopPropagation();
          idxBtn.textContent = '⏳...';
          try {
            const res = await API.indexProject(pName);
            if (res.status === 'success') {
              alert(`✅ ${pName} RAG indekslendi. (${res.file_count} dosya, ${res.chunk_count} parça)`);
              this.refreshProjectList(onRender);
            } else {
              alert('İndeks Hatası: ' + res.message);
            }
          } catch (err) {
            alert('Hata: ' + err.message);
          } finally {
            idxBtn.textContent = proj.indexed ? '⚡ Yenile' : '⚡ İndeksle';
          }
        };

        const delBtn = document.createElement('button');
        delBtn.className = 'proj-btn-action del';
        delBtn.textContent = '🗑️ Sil';
        delBtn.onclick = async e => {
          e.stopPropagation();
          if (!confirm(`"${pName}" projesi silinsin mi?`)) return;

          try {
            const res = await API.deleteProject(pName);
            if (res.status === 'success' && State.activeProjectName === pName) {
              await this.exitProject(onRender, true);
            }
            this.refreshProjectList(onRender);
          } catch (err) {
            alert('Hata: ' + err.message);
          }
        };

        toolbar.appendChild(runBtn);
        toolbar.appendChild(idxBtn);
        toolbar.appendChild(delBtn);

        div.appendChild(header);
        div.appendChild(toolbar);
        listEl.appendChild(div);
      });
    } catch (e) {
      // Proje listesi hatası ana sohbeti bozmasın.
    }
  },

  async activateProject(pName, onRender) {
    const previousProjectName = State.activeProjectName;
    const previousProjectIds = Object.keys(State.conversations).filter(id => {
      const c = State.conversations[id];
      return c && c.projectName;
    });

    if (previousProjectName) {
      const previousConv = State.conversations[State.currentId];
      if (previousConv) {
        previousConv.webActive = false;
        previousConv.webTarget = '';
      }
    }

    // Önce bellekteki eski RAG sohbetlerini tamamen çıkar.
    previousProjectIds.forEach(id => {
      delete State.conversations[id];
    });

    State.activeProjectName = pName;

    let data;
    try {
      const res = await API.loadProjectConversations(pName);
      if (res.status !== 'success') {
        throw new Error(res.message || 'Proje sohbetleri yüklenemedi.');
      }
      data = res.data || {};
    } catch (e) {
      State.activeProjectName = null;
      alert('Proje sohbetleri yüklenemedi: ' + e.message);
      this.refreshProjectList(onRender);
      if (onRender) onRender();
      return;
    }

    const loaded = data.conversations || {};
    const idMap = {};
    let targetId = null;

    Object.keys(loaded).forEach(oldId => {
      const conv = loaded[oldId];
      if (!conv || typeof conv !== 'object') return;

      const newId = makeProjectConversationId(pName, oldId);
      idMap[String(oldId)] = newId;

      State.conversations[newId] = {
        ...conv,
        projectName: pName,
        isGenerating: false,
        abortCtrl: null
      };
    });

    if (Object.keys(loaded).length) {
      const storedCurrent = data.currentConvId != null ? String(data.currentConvId) : '';
      targetId = idMap[storedCurrent] || Object.keys(State.conversations).find(
        id => State.conversations[id]?.projectName === pName
      );
    }

    if (!targetId) {
      targetId = makeProjectConversationId(pName);
      State.conversations[targetId] = {
        title: '📂 ' + pName,
        projectName: pName,
        model: document.getElementById('modelSelect')?.value || 'auto',
        created: Date.now(),
        isGenerating: false,
        messages: [{
          role: 'assistant',
          content: `⚡ **"${pName}"** RAG çalışma alanı aktif edildi. Projedeki kod ve dokümanlarınız indeks sorgusuna hazır.`
        }]
      };
    }

    State.currentId = targetId;

    const curConv = State.conversations[targetId];
    const modelSelectEl = document.getElementById('modelSelect');
    if (curConv && curConv.model && modelSelectEl) {
      modelSelectEl.value = curConv.model;
    }

    State.saveToStorage();
    this.refreshProjectList(onRender);
    if (onRender) onRender();
  },

  exitProject(onRender, projectDeleted = false) {
    const currentConv = State.conversations[State.currentId];

    if (currentConv) {
      currentConv.webActive = false;
      currentConv.webTarget = '';
    }

    if (State.activeProjectName && !projectDeleted) {
      API.saveProjectConversations(
        State.activeProjectName,
        State.conversations,
        State.currentId,
        State.nextId
      );
    }

    Object.keys(State.conversations).forEach(id => {
      const c = State.conversations[id];
      if (c && c.projectName) {
        delete State.conversations[id];
      }
    });

    State.activeProjectName = null;
    State.currentId = Object.keys(State.conversations)[0] || null;

    if (!State.currentId) {
      const id = String(State.nextId++);
      State.conversations[id] = {
        title: 'Yeni Sohbet',
        model: document.getElementById('modelSelect')?.value || 'auto',
        created: Date.now(),
        messages: [],
        isGenerating: false
      };
      State.currentId = id;
    }

    // Global kayıtta artık yalnızca normal sohbetler vardır.
    API.saveConversations(State.conversations, State.currentId, State.nextId);
    State.saveToStorage();

    this.refreshProjectList(onRender);
    if (onRender) onRender();
  }
};
