// C:\AI_YEREL\GK_STUDIO_V3\static\js\ui.js
import { API } from './api.js';
import { State } from './state.js';
import { Workspace } from './workspace.js';

export const UI = {
  chatBox: null,
  promptEl: null,
  sendBtn: null,
  modelSelect: null,
  roleSelect: null,
  historyList: null,
  statusBar: null,
  gpuIndicator: null,
  badgeEl: null,
  imagePreview: null,
  packagePreview: null,
  sidebar: null,
  recognition: null,
  isListening: false,
  userScrolledUp: false,

  async init() {
    this.chatBox = document.getElementById('chatBox');
    this.promptEl = document.getElementById('prompt');
    this.sendBtn = document.getElementById('sendBtn');
    this.modelSelect = document.getElementById('modelSelect');
    this.roleSelect = document.getElementById('roleSelect');
    this.historyList = document.getElementById('history-list');
    this.statusBar = document.getElementById('statusBar');
    this.gpuIndicator = document.getElementById('gpu-indicator');
    this.badgeEl = document.getElementById('currentModelBadge');
    this.imagePreview = document.getElementById('imagePreview');
    this.packagePreview = document.getElementById('packagePreview');
    this.sidebar = document.getElementById('sidebar');

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
    return `≡ƒôà ${dateStr} ${timeStr}`;
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
      this.statusBar.innerHTML = '<span class="pill down">Ba─ƒlant─▒ yok</span>';
    }
  },

  populateModels(d) {
    this.modelSelect.innerHTML = '<option value="auto">≡ƒñû Otomatik Y├╢nlendirme (Auto Router)</option>';
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
    add('Ak─▒l Y├╝r├╝tme', d.reasoning || []);
    add('Bulut', d.cloud || []);
  },

  updateTopBadge(conv) {
    if (!this.badgeEl) return;
    const selectedInDropdown = this.modelSelect.value || 'auto';
    const activeModel = conv ? (conv.lastUsedModel || conv.model || selectedInDropdown) : selectedInDropdown;
    this.badgeEl.textContent = activeModel;
  },

  createNewChat() {
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
    API.saveConversations(State.conversations, State.currentId, State.nextId);
    this.renderHistory();
    this.renderChat();
    this.updateTopBadge(State.conversations[id]);
    this.setSendBtnState(false);
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
      tag.textContent = isProjectConv ? 'ΓÜí RAG' : mName;

      const del = document.createElement('button');
      del.className = 'del';
      del.textContent = 'Sil';
      del.onclick = e => { 
        e.stopPropagation(); 
        delete State.conversations[id]; 
        if (State.currentId === id) {
          const remaining = Object.keys(State.conversations);
          State.currentId = remaining[0] || null;
        }
        if (!State.currentId) this.createNewChat();
        else { this.renderHistory(); this.renderChat(); }
        API.saveConversations(State.conversations, State.currentId, State.nextId);
      };

      div.appendChild(t);
      div.appendChild(tag);
      div.appendChild(del);
      
      // ESK─░ SOHBETE TIKLANDI─₧INDA TIBB─░ D├£ZELTME: STATE VE BUTON SENRON─░ZASYONU
      div.onclick = () => { 
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

        // Sohbetin ├╝retim durumuna g├╢re G├╢nder/Dur butonunu esnek hale getir
        if (c.isGenerating) {
          this.setSendBtnState(true);
        } else {
          this.setSendBtnState(false);
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
        ts.textContent = `${dateString} ┬╖ ΓÅ▒∩╕Å 0.0 sn (d├╝┼ƒ├╝n├╝yor...)`;
      } else if (m.elapsedTime !== undefined) {
        ts.textContent = `${dateString} ┬╖ ΓÅ▒∩╕Å ${m.elapsedTime} sn`;
      } else {
        ts.textContent = dateString;
      }
      footer.appendChild(ts);

      if (m.role === 'assistant' && !m.isLiveTimer && m.content) {
        const actions = document.createElement('div');
        actions.className = 'msg-actions';

        const copyBtn = document.createElement('button');
        copyBtn.className = 'msg-act-btn';
        copyBtn.textContent = '≡ƒôï Kopyala';
        copyBtn.onclick = () => {
          navigator.clipboard.writeText(m.content);
          copyBtn.textContent = 'Γ£à Kopyaland─▒!';
          setTimeout(() => copyBtn.textContent = '≡ƒôï Kopyala', 2000);
        };

        const dlBtn = document.createElement('button');
        dlBtn.className = 'msg-act-btn';
        dlBtn.textContent = '≡ƒÆ╛ ─░ndir';
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
    this.packagePreview.innerHTML = `<span>≡ƒôü <strong>${label}</strong> pakete al─▒nd─▒.</span><button style="background:#ef4444;color:#fff;border:none;border-radius:4px;padding:2px 6px;cursor:pointer;margin-left:8px;" id="removePkgBtn">Kald─▒r</button>`;
    this.packagePreview.style.display = 'flex';
    document.getElementById('removePkgBtn').onclick = () => {
      State.currentFilePackage = null;
      this.packagePreview.innerHTML = '';
      this.packagePreview.style.display = 'none';
    };
  },

  setSendBtnState(isGenerating) {
    if (isGenerating) {
      this.sendBtn.textContent = "≡ƒ¢æ DUR";
      this.sendBtn.classList.add("stop-mode");
    } else {
      this.sendBtn.textContent = "G├╢nder";
      this.sendBtn.classList.remove("stop-mode");
    }
  },

  initSpeech() {
    const micBtn = document.getElementById('micBtn');
    if (!micBtn) return;
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      micBtn.title = "Taray─▒c─▒ ses tan─▒may─▒ desteklemiyor";
      return;
    }

    this.recognition = new SpeechRecognition();
    this.recognition.lang = 'tr-TR';
    this.recognition.continuous = false;
    this.recognition.interimResults = false;

    this.recognition.onstart = () => {
      this.isListening = true;
      micBtn.style.background = '#dc2626';
      micBtn.textContent = '≡ƒö┤ Dinleniyor...';
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
      micBtn.textContent = '≡ƒÄñ Ses';
    };

    this.recognition.onend = () => {
      this.isListening = false;
      micBtn.style.background = '#0284c7';
      micBtn.textContent = '≡ƒÄñ Ses';
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
      if (!confirm("GK Studio kapat─▒ls─▒n m─▒?")) return;
      try { await API.shutdown(); } catch {}
      document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;background:#0b0b0f;color:#fff;font-size:1.2rem;">GK Studio kapat─▒ld─▒. Bu sekmeyi kapatabilirsiniz.</div>';
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
        if (!res.ok) throw new Error('Tablo bulunamad─▒');
        const blob = await res.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `excel_tablo_${Date.now()}.xlsx`;
        a.click();
      } catch (err) { alert('Excel Hatas─▒: ' + err.message); }
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
      let pkg = "[KLAS├ûR ─░├çER─░─₧─░]\n";
      for (const f of files) {
        try { pkg += `\n--- DOSYA: ${f.name} ---\n${await f.text()}\n`; } catch {}
      }
      this.setFilePackage(`Klas├╢r (${files.length} dosya)`, pkg);
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
      let pkg = "[KOD DOSYALARI PAKET─░]\n";
      for (const f of files) {
        try { pkg += `\n--- KOD DOSYASI: ${f.name} ---\n${await f.text()}\n`; } catch {}
      }
      this.setFilePackage(`Kod Paketi (${files.length} dosya)`, pkg);
      e.target.value = '';
    };

    this.sendBtn.onclick = () => {
      const conv = State.conversations[State.currentId];
      if (conv && conv.isGenerating && conv.abortCtrl) {
        conv.abortCtrl.abort();
        conv.isGenerating = false;
        this.setSendBtnState(false);
      } else {
        this.handleSend();
      }
    };

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

    if (conv.projectName) {
      State.activeProjectName = conv.projectName;
      Workspace.refreshProjectList();
    }

    this.userScrolledUp = false;

    let displayMsg = text;
    if (!displayMsg) {
      if (pkg) displayMsg = "≡ƒôü [Dosya/Kod Paketi Y├╝klendi] Analiz Ba┼ƒlat─▒ld─▒.";
      else if (imgs.length) displayMsg = "≡ƒô╖ [G├╢rsel Y├╝klendi] Analiz Ba┼ƒlat─▒ld─▒.";
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

    const tStart = performance.now();
    const liveTimerInterval = setInterval(() => {
      const liveTag = document.getElementById('liveTimerTag');
      if (liveTag) {
        const currentElapsed = ((performance.now() - tStart) / 1000).toFixed(1);
        const dateStr = this.getFormattedDate(assistantMsg.created);
        liveTag.textContent = `${dateStr} ┬╖ ΓÅ▒∩╕Å ${currentElapsed} sn (├╝retiliyor...)`;
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
        project_name: State.activeProjectName || ''
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
            API.saveConversations(State.conversations, State.currentId, State.nextId);
          }
        }
      }
    } catch (e) {
      clearInterval(liveTimerInterval);
      assistantMsg.isLiveTimer = false;
      if (e.name === 'AbortError') {
        assistantMsg.content += '\n[├£retim kullan─▒c─▒ taraf─▒ndan durduruldu.]';
      } else {
        assistantMsg.content += '\n[Hata]: ' + e.message;
      }
      this.renderChat();
    } finally {
      conv.isGenerating = false;
      conv.abortCtrl = null;
      this.setSendBtnState(false);
    }
  }
};
// ============================================================
// GK V3 CLEAN CONTROLS LAYER
// - Ayrı Gönder / DUR
// - Gerçek üretim yokken stale generating temizliği
// - Asistan mesaj balonunda Sil
// ============================================================

const _gkBaseInit = UI.init.bind(UI);

UI._gkEnsureStopButton = function () {
  if (!this.sendBtn) return null;

  let btn = document.getElementById('stopBtn');

  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'stopBtn';
    btn.className = 'tool-btn stop';
    btn.textContent = '🛑 DUR';
    btn.style.cssText = 'display:none;min-width:78px;min-height:44px;background:#dc2626;color:#fff;border:none;border-radius:6px;font-weight:800;cursor:pointer;';
    this.sendBtn.parentNode.insertBefore(btn, this.sendBtn.nextSibling);
  }

  btn.style.minWidth = '78px';
  btn.style.minHeight = '44px';
  btn.style.padding = '0 14px';
  btn.style.fontSize = '1rem';
  btn.style.fontWeight = '800';
  btn.style.background = '#dc2626';
  btn.style.color = '#fff';
  btn.style.border = 'none';
  btn.style.borderRadius = '6px';
  btn.style.cursor = 'pointer';

  return btn;
};

UI._gkStopGeneration = function () {
  const conv = State.conversations?.[State.currentId];
  if (!conv) return;

  if (conv.abortCtrl) {
    try { conv.abortCtrl.abort(); } catch {}
  }

  conv.isGenerating = false;
  conv.pending = false;
  conv.abortCtrl = null;

  this.setSendBtnState(false);
  State.saveToStorage();
  this.renderHistory();
  this.renderChat();
};

UI.setSendBtnState = function () {
  if (!this.sendBtn) return;

  const btn = this._gkEnsureStopButton();
  const conv = State.conversations?.[State.currentId];

  const active = !!(
    conv &&
    conv.isGenerating &&
    conv.abortCtrl
  );

  if (!active && conv && conv.isGenerating && !conv.abortCtrl) {
    conv.isGenerating = false;
    conv.pending = false;
  }

  this.sendBtn.textContent = 'Gönder';
  this.sendBtn.classList.remove('stop-mode');
  this.sendBtn.style.background = 'var(--accent)';
  this.sendBtn.style.color = '#fff';
  this.sendBtn.style.minWidth = '90px';
  this.sendBtn.style.minHeight = '44px';
  this.sendBtn.style.fontWeight = '800';

  if (btn) {
    btn.style.display = active ? 'inline-block' : 'none';
  }
};

UI._gkAddDeleteButtons = function () {
  if (!this.chatBox) return;

  const conv = State.conversations?.[State.currentId];
  if (!conv || !Array.isArray(conv.messages)) return;

  const assistantMessages = conv.messages.filter(
    m => m && m.role === 'assistant'
  );

  const assistantWraps = Array.from(
    this.chatBox.querySelectorAll('.msg-wrapper.assistant')
  ).filter(w => {
    const msg = w.querySelector('.msg');
    return msg && msg.textContent.trim();
  });

  assistantWraps.forEach((wrap, assistantIndex) => {
    const targetMessage = assistantMessages[assistantIndex];
    if (!targetMessage || targetMessage.isLiveTimer) return;

    let actions = wrap.querySelector('.msg-actions');

    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'msg-actions';
      wrap.appendChild(actions);
    }

    if (actions.querySelector('.gk-delete-btn')) return;

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'msg-act-btn gk-delete-btn';
    deleteBtn.textContent = '🗑 Sil';
    deleteBtn.title = 'Bu sohbet balonunu sil';

    deleteBtn.onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();

      if (!confirm('Bu yanıt balonu silinsin mi?')) return;

      const currentConv = State.conversations?.[State.currentId];
      if (!currentConv || !Array.isArray(currentConv.messages)) return;

      const realIndex = currentConv.messages.indexOf(targetMessage);

      if (realIndex < 0) return;

      currentConv.messages.splice(realIndex, 1);
      State.saveToStorage();

      try {
        if (typeof API.saveConversations === 'function') {
          await API.saveConversations(
            State.conversations,
            State.currentId,
            State.nextId
          );
        }
      } catch {}

      this.renderChat();
      this.renderHistory();
    };

    actions.appendChild(deleteBtn);
  });
};

UI.renderChat = (function (original) {
  return function () {
    const result = original.apply(this, arguments);

    setTimeout(() => {
      this._gkAddDeleteButtons();
      this.setSendBtnState();
    }, 0);

    return result;
  };
})(UI.renderChat);

UI.init = async function () {
  const result = await _gkBaseInit();

  // Eski oturumlarda kalan ama gerçekte çalışmayan kilitleri temizle.
  Object.values(State.conversations || {}).forEach(conv => {
    if (!conv) return;
    if (conv.isGenerating && !conv.abortCtrl) {
      conv.isGenerating = false;
      conv.pending = false;
      conv.abortCtrl = null;
    }
  });

  this._gkEnsureStopButton();

  // Mevcut UI'nin Gönder handler'ini tamamen temiz kontrol mantigi ile degistir.
  this.sendBtn.onclick = () => {
    const conv = State.conversations?.[State.currentId];
    if (!conv) return;

    if (conv.isGenerating && conv.abortCtrl) {
      this._gkStopGeneration();
      return;
    }

    if (conv.isGenerating && !conv.abortCtrl) {
      conv.isGenerating = false;
      conv.pending = false;
      conv.abortCtrl = null;
    }

    this.handleSend();
  };

  const stopBtn = this._gkEnsureStopButton();

  if (stopBtn) {
    stopBtn.onclick = () => this._gkStopGeneration();
  }

  // Izgaradaki stale generating durumunu ilk render sonrasinda tekrar temizle.
  setTimeout(() => {
    this.setSendBtnState();
    this._gkAddDeleteButtons();
  }, 0);

  return result;
};

console.log('[GK V3] Clean controls layer loaded.');
