// static/js/ui.js - AI STUDIO V3 Onarılmış Sürüm

// --- 1. DOM ELEMENTLERİ ---
const sendBtn = document.getElementById("btn-send"); // Mavi Gönder Butonu
const stopBtn = document.getElementById("btn-stop-generate"); // Kırmızı Dur Butonu (HTML'de eklediğin)
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");
const chatHistoryList = document.getElementById("chat-history-list");
const workspaceStatus = document.getElementById("workspace-status"); // Üstteki aktif proje barı
const modelSelect = document.getElementById("model-select");

// --- 2. GLOBAL DURUM (STATE) ---
window.activeProj = null;
window.is_project = false;
let abortController = null;

// --- 3. SOHBET GÖNDERME VE DURDURMA MANTIĞI ---

async function handleSend() {
    const text = chatInput.value.trim();
    if (!text) return;

    // UI'da kullanıcı mesajını göster ve input'u temizle
    appendMessage("user", text);
    chatInput.value = "";
    
    // BUTON KİLİTLEME: Mavi gönder butonunu inaktif yap, kırmızı dur butonunu göster
    sendBtn.disabled = true;
    stopBtn.style.display = "inline-block";

    // Gateway'e gidecek Payload
    const payload = {
        message: text,
        model: modelSelect ? modelSelect.value : "deepseek-r1:7b",
        is_project: window.is_project,
        project_name: window.activeProj
    };

    // İptal mekanizmasını başlat
    abortController = new AbortController();
    const loadingId = appendLoading(); // Yükleniyor animasyonu

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
            signal: abortController.signal
        });

        removeElement(loadingId);

        if (!response.ok) throw new Error("Sunucu yanıt vermedi veya hata oluştu.");

        // AI Yanıtını Stream Olarak Okuma
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let aiMessageId = appendMessage("ai", ""); 
        let aiMessageElement = document.getElementById(aiMessageId);

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            
            // Eğer markdown parser kullanıyorsan burada marked.parse(text) yapabilirsin.
            aiMessageElement.innerHTML += chunk; 
            scrollToBottom();
        }

    } catch (error) {
        removeElement(loadingId);
        
        // Kullanıcı durdur butonuna bastıysa
        if (error.name === 'AbortError') {
            appendMessage("system", "⚠️ İşlem kullanıcı tarafından durduruldu.");
            console.log("[UI] Üretim iptal edildi.");
        } else {
            appendMessage("system", "❌ Bir hata oluştu: " + error.message);
        }
    } finally {
        // İŞLEM BİTTİĞİNDE: Mavi butonu tekrar aktif et, kırmızıyı gizle
        sendBtn.disabled = false;
        stopBtn.style.display = "none";
        abortController = null;
    }
}

// Olay Dinleyicileri (Event Listeners)
if (stopBtn) {
    stopBtn.addEventListener("click", () => {
        if (abortController) {
            abortController.abort(); // Fetch isteğini keser ve catch(AbortError) bloğuna düşürür
        }
    });
}

if (sendBtn) {
    sendBtn.addEventListener("click", handleSend);
}

if (chatInput) {
    chatInput.addEventListener("keypress", (e) => {
        // Enter'a basıldığında ve Shift'e basılmadığında gönder
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });
}

// --- 4. SOHBET GEÇMİŞİ VE RAG YÖNETİMİ ---

function renderChatList(historyList) {
    if (!chatHistoryList) return;
    chatHistoryList.innerHTML = "";

    historyList.forEach(chat => {
        // RAG ETİKETİ: Sohbet bir projeye aitse sol menüde belirginleştir
        const ragBadge = chat.is_project ? `<span class="badge bg-primary ms-2" style="font-size: 0.7em;">RAG</span>` : "";
        
        const li = document.createElement("li");
        li.className = "chat-history-item p-2 border-bottom d-flex justify-content-between align-items-center";
        li.style.cursor = "pointer";
        
        li.innerHTML = `
            <div class="chat-title text-truncate" style="max-width: 75%;">${chat.title} ${ragBadge}</div>
            <button class="btn btn-sm btn-danger delete-chat-btn" data-id="${chat.id}">Sil</button>
        `;
        
        // Sohbete Tıklanma Olayı (Silme butonu hariç)
        li.addEventListener("click", (e) => {
            if (e.target.classList.contains("delete-chat-btn")) return; // Silmeye basıldıysa sohbeti yükleme

            loadChatMessages(chat.id); // Backend'den geçmişi çek (API'ye göre ayarla)
            
            // RAG MÜHRÜNÜN GERİ YÜKLENMESİ
            if (chat.is_project) {
                window.activeProj = chat.project_name;
                window.is_project = true;
                
                if (workspaceStatus) {
                    workspaceStatus.innerHTML = `
                        <div class="alert alert-info d-flex justify-content-between align-items-center mb-0 p-2">
                            <span>⚡ AKTİF WORKSPACE (RAG): ${chat.project_name}</span>
                            <button id="btn-close-workspace" class="btn btn-sm btn-danger">Çalışmayı Bitir</button>
                        </div>`;
                    
                    document.getElementById("btn-close-workspace").addEventListener("click", () => {
                        window.activeProj = null;
                        window.is_project = false;
                        workspaceStatus.innerHTML = "";
                    });
                }
            } else {
                // Normal sohbet ise projeden çık
                window.activeProj = null;
                window.is_project = false;
                if (workspaceStatus) workspaceStatus.innerHTML = "";
            }
        });

        chatHistoryList.appendChild(li);
    });
}

// --- 5. YARDIMCI FONKSİYONLAR ---

function appendMessage(role, text) {
    const msgDiv = document.createElement("div");
    const msgId = "msg-" + Date.now();
    msgDiv.id = msgId;
    // Rolüne göre CSS class ataması (user-message, ai-message, system-message)
    msgDiv.className = `message ${role}-message mb-3 p-3 rounded`;
    msgDiv.innerHTML = text; 
    
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return msgId;
}

function appendLoading() {
    const loadingId = "loading-" + Date.now();
    const msgDiv = document.createElement("div");
    msgDiv.id = loadingId;
    msgDiv.className = "message system-message mb-3 p-3 text-muted";
    msgDiv.innerHTML = "<i>Yapay zeka yanıt üretiyor...</i>";
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    return loadingId;
}

function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

// Geçmişi yüklemek için sahte/örnek fonksiyon (Senin mevcut API uç noktana bağlanmalı)
async function loadChatMessages(chatId) {
    console.log(`[UI] Sohbet yükleniyor: ${chatId}`);
    // fetch(`/api/history/${chatId}`) vs.
}