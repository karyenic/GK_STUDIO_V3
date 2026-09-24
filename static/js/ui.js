// C:\AI_YEREL\GK_STUDIO_V3\static\js\ui.js
import { API } from './api.js';
import { State } from './state.js';
import { Workspace } from './workspace.js';

export const UI = {
  chatBox: null,
  promptEl: null,
  sendBtn: null,
    stopBtn: null,
  modelSelect: null,
  roleSelect: null,
  historyList: null,
  statusBar: null,
  gpuIndicator: null,
  badgeEl: null,
  imagePreview: null,
  packagePreview: null,
  sidebar: null,
  webBanner: null,
  recognition: null,
  isListening: false,
  userScrolledUp: false,

  async init() {
    this.chatBox = document.getElementById('chatBox');
    this.promptEl = document.getElementById('prompt');
    this.sendBtn = document.getElementById('sendBtn');
    this.stopBtn = document.getElementById('stopBtn');
    this.modelSelect = document.getElementById('modelSelect');
    this.roleSelect = document.getElementById('roleSelect');
    this.historyList = document.getElementById('history-list');
    this.statusBar = document.getElementById('statusBar');
    this.gpuIndicator = document.getElementById('gpu-indicator');
    this.badgeEl = document.getElementById('currentModelBadge');
    this.imagePreview = document.getElementById('imagePreview');
    this.packagePreview = document.getElementById('packagePreview');
    this.sidebar = document.getElementById('sidebar');
    this.webBanner = document.getElementById('webSearchBanner');

    try {
      const backendData = await API.loadConversations();
      if (backendData && backendData.found && backendData.data) {
        State.conversations = backendData.data.conversations || {};
        State.currentId = backendData.data.currentConvId || null;
        State.nextId = backendData.data.nextId || 1;
      }
    } catch (e) {
      State.loadFromStorage();
    }

    this.applyTheme();
    this.initEvents();
    this.initSpeech();

    API.getModels().then(d => this.populateModels(d)).catch(() => this.populateModels({}));
    this.updateStatus();
    setInterval(() => this.updateStatus(), 3000);

    Workspace.initWorkspaceUI(() => { 
      this.renderHistory(); 
      this.renderChat(); 
      if (State.conversations[State.currentId]) {
        this.updateTopBadge(State.conversations[State.currentId]);
      }
    });

    if (!State.currentId || !State.conversations[State.currentId]) {
      this.createNewChat();
    } else {
      const curConv = State.conversations[State.currentId];
      if (curConv && curConv.projectName) {
        State.activeProjectName = curConv.projectName;
        Workspace.refreshProjectList();
      }
      this.renderHistory();
      this.renderChat();
      this.updateTopBadge(curConv);
    }
  },

  applyTheme() {
    document.body.classList.remove('light-theme', 'dim-theme');
    if (State.themeMode === 1) document.body.classList.add('light-theme');
    if (State.themeMode === 2) document.body.classList.add('dim-theme');
  },

  kind(m) {
    if (!m) return 'yerel';
    const lm = (m + '').toLowerCase();
    if (lm.includes('vision') || lm.includes('vl') || lm.includes('moondream')) return 'vision';
    if (lm.includes('coder') || lm.includes('r1') || lm.includes('deepseek')) return 'skill';
    if (lm.includes('gemini')) return 'bulut';
    return 'yerel';
  },

  badgeCls(k) {
    if (k === 'bulut') return 'badge-bulut';
    if (k === 'vision') return 'badge-vision';
    if (k === 'skill') return 'badge-skill';
    return 'badge-yerel';
  },

  getFormattedDate(ts) {
    const d = ts ? new Date(ts) : new Date();
    const dateStr = d.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const timeStr = d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    return `📅 ${dateStr} ${timeStr}`;
  },

  async updateStatus() {
    try {
      const d = await API.getStatus();
      this.statusBar.innerHTML = '';

      const mkPill = (txt, ok) => {
        const s = document.createElement('span');
        s.className = 'pill ' + (ok ? 'ok' : 'down');
        s.textContent = txt;
        return s;
      };

      this.statusBar.appendChild(mkPill('Ollama', d.ollama));
      this.statusBar.appendChild(mkPill('Bulut', d.gemini));
      this.statusBar.appendChild(mkPill(d.gpu ? 'GPU: Aktif' : 'GPU: Pasif', d.gpu));

      if (this.gpuIndicator) {
        this.gpuIndicator.textContent = d.gpu_info || 'CPU: %0 | RAM: %0 | GPU: %0';
      }
    } catch {
      this.statusBar.innerHTML = '<span class="pill down">Bağlantı yok</span>';
    }
  },

  populateModels(d) {
    this.modelSelect.innerHTML = '<option value="auto">🤖 Otomatik Yönlendirme (Auto Router)</option>';
    const add = (lab, arr) => {
      if (!arr || !arr.length) return;
      const g = document.createElement('optgroup');
      g.label = lab;
      arr.forEach(m => {
        const o = document.createElement('option');
        o.value = m; o.textContent = m;
        g.appendChild(o);
      });
      this.modelSelect.appendChild(g);
    };
    add('Yerel', d.local || []);
    add('Kod (Coder)', d.coder || []);
    add('Akıl Yürütme', d.reasoning || []);
    add('Bulut', d.cloud || []);
  },

  updateWebBanner(conv) {
    if (!this.webBanner) return;
    const active = !!(conv && conv.webActive);
    this.webBanner.style.display = active ? 'flex' : 'none';
    const target = this.webBanner.querySelector('.web-target');
    if (target) target.textContent = conv && conv.webTarget ? conv.webTarget : 'Genel web araştırması';
  },

  extractWebTarget(text) {
    const m = String(text || '').match(/https?:\/\/[^\s<>"']+|www\.[^\s<>"']+/i);
    return m ? m[0].replace(/[.,);\]}> ]+$/g, '') : '';
  },

  needsWebSearch(text) {
    const p = String(text || '').trim().toLowerCase();
    if (!p) return false;
    if (this.extractWebTarget(p)) return true;
    const keys = [
      'güncel','guncel','araştır','arastir','internetten','internet','web',
      'siteyi incele','siteyi araştır','siteyi arastir','son durum',
      'son 6 ay','son altı ay','fiyat','satış','satis','kaç adet','kac adet',
      'istatistik','veri','pazar payı','pazar payi','ciro','katalog','pdf',
      'kaynak','karşılaştır','karsilastir','incele','bul'
    ];
    return keys.some(k => p.includes(k));
  },

  showWebApproval(conv, originalText) {
    this.chatBox.querySelectorAll('.web-approval').forEach(el => el.remove());

    const box = document.createElement('div');
    box.className = 'web-approval msg-wrapper assistant';
    box.innerHTML = '<div class="badge badge-bulut">WEB ARAŞTIRMA</div>' +
      '<div class="msg">Bu işlem için web araştırması yapılacak.<div style="margin-top:10px;display:flex;gap:8px;">' +
      '<button class="web-approve-btn">Onay</button>' +
      '<button class="web-cancel-btn">İptal</button></div></div>';

    box.querySelector('.web-approve-btn').onclick = () => {
      conv.webActive = true;
      conv.webTarget = this.extractWebTarget(originalText);
      this.updateWebBanner(conv);
      box.remove();
      this.executeSend(originalText);
    };

    box.querySelector('.web-cancel-btn').onclick = () => {
      box.remove();
      this.executeSend(originalText, false);
    };

    this.chatBox.appendChild(box);
    this.chatBox.scrollTop = this.chatBox.scrollHeight;
  },

  closeWebMode() {
    const conv = State.conversations[State.currentId];
    if (!conv) return;
    conv.webActive = false;
    conv.webTarget = '';
    this.updateWebBanner(conv);
    this.persistConversationState(conv);
  },

  async persistConversationState(conv = null) {
    const current = conv || State.conversations[State.currentId];
    if (current && current.projectName) {
      return API.saveProjectConversations(
        current.projectName,
        State.conversations,
        State.currentId,
        State.nextId
      );
    }

    return API.saveConversations(
      State.conversations,
      State.currentId,
      State.nextId
    );
  },

  updateTopBadge(conv) {
    if (!this.badgeEl) return;
    const selectedInDropdown = this.modelSelect.value || 'auto';
    const activeModel = conv ? (conv.lastUsedModel || conv.model || selectedInDropdown) : selectedInDropdown;
    this.badgeEl.textContent = activeModel;
  },

  createNewChat() {
    Object.keys(State.conversations).forEach(id => {
      if (State.conversations[id]?.projectName) {
        delete State.conversations[id];
      }
    });
    State.activeProjectName = null;
    Workspace.refreshProjectList();

    const curId = State.currentId;
    if (curId && State.conversations[curId]) {
      const curConv = State.conversations[curId];
      const hasUserMsg = (curConv.messages || []).some(m => m.role === 'user');
      if (!hasUserMsg && !curConv.projectName) {
        curConv.model = this.modelSelect.value || 'auto';
        this.updateTopBadge(curConv);
        return;
      }
    }
    const id = String(State.nextId++);
    const selectedModel = this.modelSelect.value || 'auto';
    State.conversations[id] = { title: 'Yeni Sohbet', model: selectedModel, created: Date.now(), messages: [], isGenerating: false };
    State.currentId = id;
    State.saveToStorage();
    this.persistConversationState();
    this.renderHistory();
    this.renderChat();
    this.updateTopBadge(State.conversations[id]);
    this.updateWebBanner(State.conversations[id]);
    this.setSendBtnState(false);
    this.setStopBtnState(false);
  },

  renderHistory() {
    this.historyList.innerHTML = '';
    
    Object.keys(State.conversations).forEach(id => {
      const c = State.conversations[id];
      const hasUserMsg = (c.messages || []).some(m => m.role === 'user');
      if (!hasUserMsg && id !== State.currentId && !c.projectName) {
        delete State.conversations[id];
      }
    });

    const keys = Object.keys(State.conversations).sort((a, b) => (State.conversations[b].created || 0) - (State.conversations[a].created || 0));
    keys.forEach(id => {
      const c = State.conversations[id];
      const isProjectConv = !!c.projectName;

      // RAG sohbeti yalnızca kendi aktif workspace'i içindeyken görünür.
      if (isProjectConv && c.projectName !== State.activeProjectName) return;

      const div = document.createElement('div');
      div.className = 'hist-item' + (id === State.currentId ? ' active' : '') + (isProjectConv ? ' rag-conv-item' : '');
      
      const t = document.createElement('span');
      t.className = 'title';
      t.textContent = c.title || 'Yeni Sohbet';

      const mName = c.lastUsedModel || c.model || 'Auto';
      const tag = document.createElement('span');
      tag.className = 'badge ' + (isProjectConv ? 'badge-rag' : this.badgeCls(this.kind(mName)));
      tag.style.fontSize = '0.75rem';
      tag.style.padding = '2px 6px';
      tag.style.marginBottom = '0';
      tag.textContent = isProjectConv ? '⚡ RAG' : mName;

      const del = document.createElement('button');
      del.className = 'del';
      del.textContent = 'Sil';
      del.onclick = async e => { 
        e.stopPropagation();

        const deletedConv = State.conversations[id];
        const deletedWasProject = !!deletedConv?.projectName;
        const deletedProjectName = deletedConv?.projectName || null;

        delete State.conversations[id];

        if (deletedWasProject) {
          // Silinen RAG sohbetinin son halini aynı proje dosyasına yaz.
          // Sunucu yalnızca aynı projectName taşıyan kayıtları kabul eder.
          await this.persistConversationState({ projectName: deletedProjectName });

          const projectIds = Object.keys(State.conversations).filter(otherId => {
            return State.conversations[otherId]?.projectName === deletedProjectName;
          });

          if (!projectIds.length && State.activeProjectName === deletedProjectName) {
            State.activeProjectName = null;
            State.currentId = null;
            this.createNewChat();
            return;
          }

          if (State.currentId === id || !State.currentId) {
            State.currentId = projectIds[0] || null;
          }

          this.renderHistory();
          this.renderChat();
          return;
        }

        if (State.currentId === id) {
          const remaining = Object.keys(State.conversations).filter(otherId => {
            return !State.conversations[otherId]?.projectName;
          });
          State.currentId = remaining[0] || null;
        }

        if (!State.currentId) {
          this.createNewChat();
          return;
        }

        this.persistConversationState();
        this.renderHistory();
        this.renderChat();
      };

      div.appendChild(t);
      div.appendChild(tag);
      div.appendChild(del);
      
      // ESKİ SOHBETE TIKLANDIĞINDA TIBBİ DÜZELTME: STATE VE BUTON SENRONİZASYONU
      div.onclick = () => { 
        const previousConv = State.conversations[State.currentId];
        if (previousConv && previousConv !== c) {
          previousConv.webActive = false;
          previousConv.webTarget = '';
        }
        if (!c.projectName && State.activeProjectName) {
          Object.keys(State.conversations).forEach(otherId => {
            if (State.conversations[otherId]?.projectName) {
              delete State.conversations[otherId];
            }
          });
        }

        State.currentId = id; 
        if (c.projectName) {
          State.activeProjectName = c.projectName;
        } else {
          State.activeProjectName = null;
        }
        Workspace.refreshProjectList();
        this.renderHistory(); 
        this.renderChat(); 
        this.updateTopBadge(c);
        this.updateWebBanner(c);

        // Sohbetin üretim durumuna göre Gönder/Dur butonunu esnek hale getir
        if (c.isGenerating) {
          this.setSendBtnState(true);
    this.setStopBtnState(true);
        } else {
          this.setSendBtnState(false);
    this.setStopBtnState(false);
        }
      };
      this.historyList.appendChild(div);
    });
  },

  renderChat() {
    const conv = State.conversations[State.currentId];
    if (!conv) return;

    this.chatBox.innerHTML = '';
    this.updateTopBadge(conv);
    this.updateWebBanner(conv);

    (conv.messages || []).forEach(m => {
      const wrap = document.createElement('div');
      wrap.className = 'msg-wrapper ' + (m.role || 'assistant');

      if (m.role === 'assistant') {
        const badge = document.createElement('div');
        const mName = m.model || conv.lastUsedModel || conv.model || 'Auto';
        badge.className = 'badge ' + this.badgeCls(this.kind(mName));
        badge.textContent = m.route ? `${mName} [${m.route}]` : mName;
        wrap.appendChild(badge);
      }

      const msg = document.createElement('div');
      msg.className = 'msg';
      try { msg.innerHTML = marked.parse(m.content || ''); } catch { msg.textContent = m.content; }
      wrap.appendChild(msg);

      const footer = document.createElement('div');
      footer.className = 'msg-footer';

      const ts = document.createElement('div');
      ts.className = 'msg-timestamp';
      const dateString = this.getFormattedDate(m.created);

      if (m.isLiveTimer) {
        ts.id = 'liveTimerTag';
        ts.textContent = `${dateString} · ⏱️ 0.0 sn (düşünüyor...)`;
      } else if (m.elapsedTime !== undefined) {
        ts.textContent = `${dateString} · ⏱️ ${m.elapsedTime} sn`;
      } else {
        ts.textContent = dateString;
      }
      footer.appendChild(ts);

      if (m.role === 'assistant' && !m.isLiveTimer && m.content) {
        const actions = document.createElement('div');
        actions.className = 'msg-actions';

        const copyBtn = document.createElement('button');
        copyBtn.className = 'msg-act-btn';
        copyBtn.textContent = '📋 Kopyala';
        copyBtn.onclick = () => {
          navigator.clipboard.writeText(m.content);
          copyBtn.textContent = '✅ Kopyalandı!';
          setTimeout(() => copyBtn.textContent = '📋 Kopyala', 2000);
        };

        const dlBtn = document.createElement('button');
        dlBtn.className = 'msg-act-btn';
        dlBtn.textContent = '💾 İndir';
        dlBtn.onclick = () => {
          const blob = new Blob([m.content], { type: 'text/markdown;charset=utf-8' });
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = `asistan_yaniti_${Date.now()}.md`;
          a.click();
        };

        actions.appendChild(copyBtn);
        actions.appendChild(dlBtn);
        footer.appendChild(actions);
      }

      wrap.appendChild(footer);
      this.chatBox.appendChild(wrap);
    });

    if (window.hljs) this.chatBox.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
    if (!this.userScrolledUp) {
      this.chatBox.scrollTop = this.chatBox.scrollHeight;
    }
  },

  updateLiveStreamContent(assistantMsg, accText) {
    assistantMsg.content = accText;
    const lastMsgWrapper = this.chatBox.querySelector('.msg-wrapper.assistant:last-child');
    if (lastMsgWrapper) {
      const msgDiv = lastMsgWrapper.querySelector('.msg');
      if (msgDiv) {
        try { msgDiv.innerHTML = marked.parse(accText); } catch { msgDiv.textContent = accText; }
        if (window.hljs) msgDiv.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
      }
    }
    if (!this.userScrolledUp) {
      this.chatBox.scrollTop = this.chatBox.scrollHeight;
    }
  },

  toBase64(file) {
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result.split(',')[1]);
      r.onerror = rej;
      r.readAsDataURL(file);
    });
  },

  setFilePackage(label, textContent) {
    State.currentFilePackage = textContent;
    this.packagePreview.innerHTML = `<span>📁 <strong>${label}</strong> pakete alındı.</span><button style="background:#ef4444;color:#fff;border:none;border-radius:4px;padding:2px 6px;cursor:pointer;margin-left:8px;" id="removePkgBtn">Kaldır</button>`;
    this.packagePreview.style.display = 'flex';
    document.getElementById('removePkgBtn').onclick = () => {
      State.currentFilePackage = null;
      this.packagePreview.innerHTML = '';
      this.packagePreview.style.display = 'none';
    };
  },

  setSendBtnState(isGenerating) {
    if (!this.sendBtn) return;

    this.sendBtn.textContent = "Gönder";
    this.sendBtn.classList.remove("stop-mode");
    this.sendBtn.disabled = !!isGenerating;
  },

  setStopBtnState(isGenerating) {
    if (!this.stopBtn) return;

    this.stopBtn.disabled = !isGenerating;
    this.stopBtn.classList.toggle("active", !!isGenerating);
  },

  stopGeneration() {
    const conv = State.conversations[State.currentId];

    if (!conv || !conv.isGenerating || !conv.abortCtrl) {
      return;
    }

    console.log("[DUR] AbortController.abort() cagriliyor...");
    conv.abortCtrl.abort();
  },

  initSpeech() {
    const micBtn = document.getElementById('micBtn');
    if (!micBtn) return;
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      micBtn.title = "Tarayıcı ses tanımayı desteklemiyor";
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.lang = 'tr-TR';
    this.recognition.continuous = false;
    this.recognition.interimResults = false;

    this.recognition.onstart = () => {
      this.isListening = true;
      micBtn.style.background = '#dc2626';
      micBtn.textContent = '🔴 Dinleniyor...';
    };

    this.recognition.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      if (transcript) {
        this.promptEl.value = (this.promptEl.value ? this.promptEl.value + ' ' : '') + transcript;
      }
    };

    this.recognition.onerror = () => {
      this.isListening = false;
      micBtn.style.background = '#0284c7';
      micBtn.textContent = '🎤 Ses';
    };

    this.recognition.onend = () => {
      this.isListening = false;
      micBtn.style.background = '#0284c7';
      micBtn.textContent = '🎤 Ses';
    };

    micBtn.onclick = () => {
      if (this.isListening) {
        this.recognition.stop();
      } else {
        try { this.recognition.start(); } catch { this.recognition.stop(); }
      }
    };
  },

  initEvents() {
    if (this.chatBox) {
      this.chatBox.addEventListener('scroll', () => {
        const distanceToBottom = this.chatBox.scrollHeight - this.chatBox.scrollTop - this.chatBox.clientHeight;
        this.userScrolledUp = distanceToBottom > 30;
      });
    }

    document.getElementById('newChatBtn').onclick = () => this.createNewChat();
    document.getElementById('themeToggle').onclick = () => {
      State.themeMode = (State.themeMode + 1) % 3;
      this.applyTheme();
      State.saveToStorage();
    };
    document.getElementById('sidebarToggle').onclick = () => {
      this.sidebar.classList.toggle('collapsed');
    };

    document.getElementById('shutdownBtn').onclick = async () => {
      if (!confirm("GK Studio kapatılsın mı?")) return;
      try { await API.shutdown(); } catch {}
      document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;background:#0b0b0f;color:#fff;font-size:1.2rem;">GK Studio kapatıldı. Bu sekmeyi kapatabilirsiniz.</div>';
    };

    this.modelSelect.onchange = () => {
      const conv = State.conversations[State.currentId];
      if (conv) {
        conv.model = this.modelSelect.value;
        this.updateTopBadge(conv);
      }
    };

    document.getElementById('selectImageBtn').onclick = () => document.getElementById('imageInput').click();
    document.getElementById('imageInput').onchange = async e => {
      for (const f of Array.from(e.target.files || [])) {
        const b64 = await this.toBase64(f);
        State.currentImages.push(b64);
        const div = document.createElement('div');
        div.className = 'preview-item';
        const img = document.createElement('img');
        img.src = URL.createObjectURL(f);
        const rm = document.createElement('span');
        rm.className = 'remove-img';
        rm.textContent = 'x';
        rm.onclick = () => {
          const idx = State.currentImages.indexOf(b64);
          if (idx >= 0) State.currentImages.splice(idx, 1);
          div.remove();
          if (!State.currentImages.length) this.imagePreview.style.display = 'none';
        };
        div.appendChild(img);
        div.appendChild(rm);
        this.imagePreview.appendChild(div);
      }
      this.imagePreview.style.display = 'flex';
      e.target.value = '';
    };

    document.getElementById('excelBtn').onclick = async () => {
      const conv = State.conversations[State.currentId];
      if (!conv || !conv.messages || !conv.messages.length) return;
      const lastMsg = conv.messages[conv.messages.length - 1].content || '';
      try {
        const res = await fetch('/markdown-to-excel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ markdown_text: lastMsg })
        });
        if (!res.ok) throw new Error('Tablo bulunamadı');
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `excel_tablo_${Date.now()}.xlsx`;
        a.click();
      } catch (err) { alert('Excel Hatası: ' + err.message); }
    };

    document.getElementById('pdfBtn').onclick = () => document.getElementById('pdfInput').click();
    document.getElementById('pdfInput').onchange = async e => {
      const f = e.target.files[0];
      if (f) {
        const txt = await f.text();
        this.setFilePackage(`PDF: ${f.name}`, txt);
      }
      e.target.value = '';
    };

    document.getElementById('folderBtn').onclick = () => document.getElementById('folderInput').click();
    document.getElementById('folderInput').onchange = async e => {
      const files = Array.from(e.target.files || []);
      let pkg = "[KLASÖR İÇERİĞİ]\n";
      for (const f of files) {
        try { pkg += `\n--- DOSYA: ${f.name} ---\n${await f.text()}\n`; } catch {}
      }
      this.setFilePackage(`Klasör (${files.length} dosya)`, pkg);
      e.target.value = '';
    };

    document.getElementById('txtBtn').onclick = () => document.getElementById('txtInput').click();
    document.getElementById('txtInput').onchange = async e => {
      const f = e.target.files[0];
      if (f) this.setFilePackage(`TXT: ${f.name}`, await f.text());
      e.target.value = '';
    };

    document.getElementById('codeBtn').onclick = () => document.getElementById('codeInput').click();
    document.getElementById('codeInput').onchange = async e => {
      const files = Array.from(e.target.files || []);
      let pkg = "[KOD DOSYALARI PAKETİ]\n";
      for (const f of files) {
        try { pkg += `\n--- KOD DOSYASI: ${f.name} ---\n${await f.text()}\n`; } catch {}
      }
      this.setFilePackage(`Kod Paketi (${files.length} dosya)`, pkg);
      e.target.value = '';
    };

    this.sendBtn.onclick = () => {
      this.handleSend();
    };

    if (this.stopBtn) {
      this.stopBtn.onclick = () => {
        this.stopGeneration();
      };
    }

    const webCloseBtn = document.getElementById('webSearchCloseBtn');
    if (webCloseBtn) {
      webCloseBtn.onclick = () => this.closeWebMode();
    }

    this.promptEl.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { 
        e.preventDefault(); 
        const conv = State.conversations[State.currentId];
        if (!conv || !conv.isGenerating) {
          this.handleSend();
        }
      }
    });
  },

  async handleSend() {
    const text = this.promptEl.value.trim();
    const pkg = State.currentFilePackage;
    const imgs = State.currentImages.slice();

    if (!text && !imgs.length && !pkg) return;

    const conv = State.conversations[State.currentId];
    if (!conv) return;

    if (text && conv.webActive) {
      const newTarget = this.extractWebTarget(text);
      if (newTarget) conv.webTarget = newTarget;
      this.updateWebBanner(conv);
    }

    if (text && !conv.webActive && this.needsWebSearch(text)) {
      this.showWebApproval(conv, text);
      return;
    }

    await this.executeSend(text, true, pkg, imgs);
  },

  async executeSend(text, webApproved = true, pkgOverride = undefined, imgsOverride = undefined) {
    const pkg = pkgOverride !== undefined ? pkgOverride : State.currentFilePackage;
    const imgs = imgsOverride !== undefined ? imgsOverride : State.currentImages.slice();
    const conv = State.conversations[State.currentId];
    if (!conv) return;

    if (conv.projectName) {
      State.activeProjectName = conv.projectName;
      Workspace.refreshProjectList();
    }

    this.userScrolledUp = false;

    let displayMsg = text;
    if (!displayMsg) {
      if (pkg) displayMsg = "📁 [Dosya/Kod Paketi Yüklendi] Analiz Başlatıldı.";
      else if (imgs.length) displayMsg = "📷 [Görsel Yüklendi] Analiz Başlatıldı.";
    }

    conv.messages.push({ role: 'user', content: displayMsg, created: Date.now() });
    if (conv.messages.filter(m => m.role === 'user').length === 1 && !conv.projectName) {
      conv.title = displayMsg.length > 25 ? displayMsg.slice(0, 25) + '...' : displayMsg;
    }

    this.promptEl.value = '';
    State.currentImages = [];
    this.imagePreview.innerHTML = '';
    this.imagePreview.style.display = 'none';
    State.currentFilePackage = null;
    this.packagePreview.style.display = 'none';

    this.renderChat();
    this.renderHistory();

    const assistantMsg = { role: 'assistant', content: '', isLiveTimer: true, created: Date.now() };
    conv.messages.push(assistantMsg);
    this.renderChat();

    conv.isGenerating = true;
    conv.abortCtrl = new AbortController();
    this.setSendBtnState(true);
    this.setStopBtnState(true);

    const tStart = performance.now();
    const liveTimerInterval = setInterval(() => {
      const liveTag = document.getElementById('liveTimerTag');
      if (liveTag) {
        const currentElapsed = ((performance.now() - tStart) / 1000).toFixed(1);
        const dateStr = this.getFormattedDate(assistantMsg.created);
        liveTag.textContent = `${dateStr} · ⏱️ ${currentElapsed} sn (üretiliyor...)`;
      }
    }, 100);

    try {
      const payload = {
        prompt: text,
        model: conv.model || this.modelSelect.value || 'auto',
        role: this.roleSelect.value || 'default',
        history: conv.messages.slice(0, -2),
        images: imgs.length ? imgs : undefined,
        filePackage: pkg,
        is_project: !!State.activeProjectName,
        project_name: State.activeProjectName || '',
        web_search: !!conv.webActive && !!webApproved,
        web_target: conv.webActive ? (conv.webTarget || '') : '',
        web_session_context: ''
      };

      const res = await API.chat(payload, conv.abortCtrl.signal);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '', acc = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();

        for (const line of lines) {
          let clean = line.trim();
          if (clean.startsWith('data: ')) clean = clean.substring(6).trim();
          if (!clean) continue;
          let evt; try { evt = JSON.parse(clean); } catch { continue; }

          if (evt.type === 'meta') {
            assistantMsg.model = evt.model;
            assistantMsg.route = evt.route;
            conv.lastUsedModel = evt.model;
            conv.lastRoute = evt.route;
            this.updateTopBadge(conv);
          } else if (evt.type === 'chunk') {
            acc += evt.text;
            this.updateLiveStreamContent(assistantMsg, acc);
          } else if (evt.type === 'done') {
            clearInterval(liveTimerInterval);
            assistantMsg.isLiveTimer = false;
            assistantMsg.elapsedTime = evt.elapsed_time || ((performance.now() - tStart) / 1000).toFixed(2);
            this.renderChat();
            this.persistConversationState(conv);
          }
        }
      }
    } catch (e) {
      clearInterval(liveTimerInterval);
      assistantMsg.isLiveTimer = false;
      if (e.name === 'AbortError') {
        assistantMsg.content += '\n[Üretim kullanıcı tarafından durduruldu.]';
      } else {
        assistantMsg.content += '\n[Hata]: ' + e.message;
      }
      this.renderChat();
    } finally {
      conv.isGenerating = false;
      conv.abortCtrl = null;
      this.setSendBtnState(false);
      this.setStopBtnState(false);
    }
  }};

