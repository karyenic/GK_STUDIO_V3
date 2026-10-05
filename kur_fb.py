# -*- coding: utf-8 -*-
import shutil, os, sys
BASE = r"C:\AI_YEREL\GK_STUDIO_V3"
UI_PATH = os.path.join(BASE, "static", "js", "ui.js")
CSS_PATH = os.path.join(BASE, "static", "css", "style.css")

if not os.path.exists(UI_PATH):
    print("[HATA] ui.js bulunamadi"); sys.exit(1)
if not os.path.exists(CSS_PATH):
    print("[HATA] style.css bulunamadi"); sys.exit(1)

print("[1/5] Yedekler aliniyor...")
shutil.copy(UI_PATH, UI_PATH + ".before_fb_20260925")
shutil.copy(CSS_PATH, CSS_PATH + ".before_fb_20260925")

with open(UI_PATH, "r", encoding="utf-8") as f:
    ui = f.read()

if "FB_MODELS" in ui:
    print("[!] FB zaten eklenmis. Iptal."); sys.exit(1)

print("[2/5] FB_MODELS ekleniyor...")
fb_models = """// FB (Fallback) modelleri
const FB_MODELS = [
  { id: "deepseek-r1:7b",       label: "DeepSeek R1 7B (Hizli Reasoning)" },
  { id: "deepseek-r1-64k:14b",  label: "DeepSeek R1 64K 14B (Derin Reasoning)" },
  { id: "qwen2.5:7b",           label: "Qwen 2.5 7B (Genel)" },
  { id: "ministral-3:14b",      label: "Ministral 3 14B (Guclu Genel)" },
  { id: "gemma2:2b",            label: "Gemma 2 2B (Cok Hizli)" },
];

export const UI = {"""

if "export const UI = {" not in ui:
    print("[HATA] 'export const UI = {' yok"); sys.exit(2)
ui = ui.replace("export const UI = {", fb_models, 1)

print("[3/5] FB butonu ekleniyor...")
old = """        actions.appendChild(copyBtn);
        actions.appendChild(dlBtn);
        actions.appendChild(delBtn);
        footer.appendChild(actions);"""
new = """        actions.appendChild(copyBtn);
        actions.appendChild(dlBtn);
        actions.appendChild(delBtn);

        const fbBtn = document.createElement('button');
        fbBtn.className = 'msg-act-btn fb-btn';
        fbBtn.textContent = 'FB Dene';
        fbBtn.onclick = (e) => {
          e.stopPropagation();
          this.showFbMenu(m, conv, actions);
        };
        actions.appendChild(fbBtn);

        footer.appendChild(actions);"""

if old not in ui:
    print("[HATA] actions blogu yok"); sys.exit(3)
ui = ui.replace(old, new, 1)

print("[4/5] FB fonksiyonlari ekleniyor...")
ui = ui.rstrip()
if not ui.endswith("};"):
    print("[HATA] ui.js formati"); sys.exit(4)

fb_funcs = r"""
  showFbMenu(assistantMsg, conv, anchorEl) {
    document.querySelectorAll('.fb-menu').forEach(el => el.remove());
    const menu = document.createElement('div');
    menu.className = 'fb-menu';
    const title = document.createElement('div');
    title.className = 'fb-menu-title';
    title.textContent = 'FB Modeli Sec';
    menu.appendChild(title);
    FB_MODELS.forEach(m => {
      const item = document.createElement('button');
      item.className = 'fb-menu-item';
      item.textContent = m.label;
      item.onclick = async (e) => {
        e.stopPropagation();
        menu.remove();
        await this.executeFallback(assistantMsg, conv, m.id, m.label);
      };
      menu.appendChild(item);
    });
    document.body.appendChild(menu);
    const rect = anchorEl.getBoundingClientRect();
    menu.style.position = 'fixed';
    menu.style.top = (rect.bottom + 4) + 'px';
    menu.style.left = Math.max(8, rect.left - 120) + 'px';
    const closeHandler = (ev) => {
      if (!menu.contains(ev.target)) {
        menu.remove();
        document.removeEventListener('click', closeHandler);
      }
    };
    setTimeout(() => document.addEventListener('click', closeHandler), 100);
  },

  async executeFallback(originalAssistantMsg, conv, fbModelId, fbModelLabel) {
    const idx = conv.messages.indexOf(originalAssistantMsg);
    if (idx < 0) return;
    let userIdx = -1;
    for (let i = idx - 1; i >= 0; i--) {
      if (conv.messages[i].role === 'user') { userIdx = i; break; }
    }
    if (userIdx < 0) { alert('FB icin orijinal soru yok'); return; }
    const originalPrompt = conv.messages[userIdx].content;
    const history = conv.messages.slice(0, userIdx);
    const fbMsg = {
      role: 'assistant', content: '', isLiveTimer: true,
      created: Date.now(), model: fbModelId, route: 'FB',
      fbFrom: conv.lastUsedModel || conv.model || 'auto',
    };
    conv.messages.push(fbMsg);
    this.renderChat();
    conv.isGenerating = true;
    conv.abortCtrl = new AbortController();
    this.setSendBtnState(true);
    this.setStopBtnState(true);
    const tStart = performance.now();
    const liveTimerInterval = setInterval(() => {
      const liveTag = document.getElementById('liveTimerTag');
      if (liveTag) {
        const cur = ((performance.now() - tStart) / 1000).toFixed(1);
        const dateStr = this.getFormattedDate(fbMsg.created);
        liveTag.textContent = dateStr + ' - ' + cur + ' sn (FB uretiliyor...)';
      }
    }, 100);
    try {
      const payload = {
        prompt: originalPrompt, model: fbModelId,
        role: this.roleSelect.value || 'default',
        history: history,
        is_project: !!State.activeProjectName,
        project_name: State.activeProjectName || '',
        web_search: false, web_target: '', web_session_context: ''
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
            fbMsg.model = evt.model; fbMsg.route = evt.route;
            this.renderChat();
          } else if (evt.type === 'chunk') {
            acc += evt.text;
            this.updateLiveStreamContent(fbMsg, acc);
          } else if (evt.type === 'done') {
            clearInterval(liveTimerInterval);
            fbMsg.isLiveTimer = false;
            fbMsg.elapsedTime = evt.elapsed_time || ((performance.now() - tStart) / 1000).toFixed(2);
            this.renderChat();
            this.persistConversationState(conv);
          }
        }
      }
    } catch (e) {
      clearInterval(liveTimerInterval);
      fbMsg.isLiveTimer = false;
      if (e.name === 'AbortError') fbMsg.content += '\n[FB durduruldu.]';
      else fbMsg.content += '\n[FB Hatasi]: ' + e.message;
      this.renderChat();
    } finally {
      conv.isGenerating = false;
      conv.abortCtrl = null;
      this.setSendBtnState(false);
      this.setStopBtnState(false);
    }
  },
"""

ui = ui[:-2] + fb_funcs + "\n};\n"
with open(UI_PATH, "w", encoding="utf-8") as f:
    f.write(ui)
print("[OK] ui.js guncellendi")

print("[5/5] style.css guncelleniyor...")
with open(CSS_PATH, "r", encoding="utf-8") as f:
    css = f.read()

fb_css = """

.fb-btn {
  background: #0284c7 !important;
  color: #fff !important;
  border: 1px solid #0369a1 !important;
}
.fb-btn:hover { background: #0369a1 !important; }
.fb-menu {
  background: #1e1e2e;
  border: 1px solid #444;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  padding: 6px;
  z-index: 9999;
  min-width: 260px;
}
.fb-menu-title {
  font-size: 0.75rem;
  color: #94a3b8;
  padding: 4px 8px 8px 8px;
  border-bottom: 1px solid #333;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.fb-menu-item {
  display: block; width: 100%; text-align: left;
  background: transparent; color: #e2e8f0;
  border: none; padding: 8px 12px;
  border-radius: 4px; cursor: pointer;
  font-size: 0.85rem;
}
.fb-menu-item:hover { background: #334155; color: #fff; }
body.light-theme .fb-menu { background: #fff; border-color: #cbd5e1; }
body.light-theme .fb-menu-item { color: #1e293b; }
body.light-theme .fb-menu-item:hover { background: #e2e8f0; }
body.light-theme .fb-menu-title { color: #64748b; border-bottom-color: #e2e8f0; }
"""
css = css.rstrip() + "\n" + fb_css
with open(CSS_PATH, "w", encoding="utf-8") as f:
    f.write(css)
print("[OK] style.css guncellendi")
print()
print("=" * 50)
print("[BASARILI] FB ozelligi kuruldu!")
print("=" * 50)
print("Tarayicida Ctrl+F5 yap ve test et.")
