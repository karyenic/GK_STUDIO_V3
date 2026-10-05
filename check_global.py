from conversation_store import load_global_conversations
from config import CHAT_DIR

d = load_global_conversations(CHAT_DIR)
convs = d.get('conversations', {})
print(f"Toplam {len(convs)} sohbet\n")
for k, v in convs.items():
    msgs = v.get('messages', [])
    user_msgs = [m for m in msgs if m.get('role') == 'user']
    first = user_msgs[0].get('content', '')[:80] if user_msgs else '(kullanici mesaji yok)'
    model = v.get('lastUsedModel') or v.get('model') or '?'
    print(f"ID {k} [{model}]: {first}")
