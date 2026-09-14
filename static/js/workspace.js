// C:\AI_YEREL\GK_STUDIO_V3\static\js\workspace.js
import { API } from './api.js';
import { State } from './state.js';

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
            this.activateProject(name, onRender);
          } else { alert('Hata: ' + res.message); }
        } catch (e) { alert('Hata: ' + e.message); }
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
        runBtn.onclick = (e) => {
          e.stopPropagation();
          if (isActive) this.exitProject(onRender);
          else this.activateProject(pName, onRender);
        };

        const idxBtn = document.createElement('button');
        idxBtn.className = 'proj-btn-action idx';
        idxBtn.textContent = proj.indexed ? '⚡ Yenile' : '⚡ İndeksle';
        idxBtn.onclick = async (e) => {
          e.stopPropagation();
          idxBtn.textContent = '⏳...';
          try {
            const res = await API.indexProject(pName);
            if (res.status === 'success') {
              alert(`✅ ${pName} RAG indekslendi. (${res.file_count} dosya, ${res.chunk_count} parça)`);
              this.refreshProjectList(onRender);
            } else { alert('İndeks Hatası: ' + res.message); }
          } catch (err) { alert('Hata: ' + err.message); }
        };

        const delBtn = document.createElement('button');
        delBtn.className = 'proj-btn-action del';
        delBtn.textContent = '🗑️ Sil';
        delBtn.onclick = async (e) => {
          e.stopPropagation();
          if (!confirm(`"${pName}" projesi silinsin mi?`)) return;
          await API.deleteProject(pName);
          if (State.activeProjectName === pName) this.exitProject(onRender);
          this.refreshProjectList(onRender);
        };

        toolbar.appendChild(runBtn);
        toolbar.appendChild(idxBtn);
        toolbar.appendChild(delBtn);
        
        div.appendChild(header);
        div.appendChild(toolbar);
        listEl.appendChild(div);
      });
    } catch (e) {}
  },

  activateProject(pName, onRender) {
    State.activeProjectName = pName;
    
    // RAG Projeleri İçin Sabit Tekil Sohbet Kimliği (Deterministic ID)
    const safeName = pName.replace(/[^a-zA-Z0-9_-]/g, '_');
    const convId = 'rag_proj_' + safeName;

    // Proje için geçmiş sohbet yoksa tek bir kez oluştur
    if (!State.conversations[convId]) {
      State.conversations[convId] = {
        title: '📂 ' + pName,
        projectName: pName,
        model: 'auto',
        created: Date.now(),
        messages: [{ role: 'assistant', content: `⚡ **"${pName}"** RAG çalışma alanı aktif edildi. Projedeki kod ve dokümanlarınız indeks sorgusuna hazır.` }]
      };
    } else {
      State.conversations[convId].projectName = pName;
    }

    State.currentId = convId;
    State.saveToStorage();
    API.saveConversations(State.conversations, State.currentId, State.nextId);

    this.refreshProjectList(onRender);
    if (onRender) onRender();
  },

  exitProject(onRender) {
    State.activeProjectName = null;
    this.refreshProjectList(onRender);
    if (onRender) onRender();
  }
};