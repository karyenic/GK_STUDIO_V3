# GK Studio V3 - RAG Conversation Isolation Diagnostic
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "=== V3 RAG CONVERSATION ISOLATION TEST ===" -ForegroundColor Cyan
Write-Host ""

@'
import json
import os
import tempfile

from conversation_store import (
    load_global_conversations,
    save_global_conversations,
    load_project_conversations,
    save_project_conversations,
    migrate_legacy_project_conversations,
    project_conversation_path,
)

with tempfile.TemporaryDirectory() as td:
    chat_dir = os.path.join(td, "chat_history")
    project_dir = os.path.join(td, "MyProject")
    os.makedirs(chat_dir, exist_ok=True)
    os.makedirs(project_dir, exist_ok=True)

    normal = {
        "1": {
            "title": "Normal",
            "model": "qwen2.5-coder:7b",
            "created": 1,
            "messages": [{"role": "user", "content": "normal"}],
        }
    }
    rag = {
        "2": {
            "title": "RAG",
            "projectName": "MyProject",
            "model": "auto",
            "created": 2,
            "messages": [{"role": "user", "content": "rag"}],
        }
    }

    save_global_conversations(
        chat_dir, {**normal, **rag}, current_conv_id="1", next_id=3
    )
    global_data = load_global_conversations(chat_dir)

    assert "1" in global_data["conversations"], "Normal sohbet global kayda yazılmadı."
    assert "2" not in global_data["conversations"], "RAG sohbeti global geçmişe sızdı."

    save_project_conversations(
        project_dir, "MyProject", rag, current_conv_id="2", next_id=3
    )
    project_data = load_project_conversations(project_dir)

    assert "2" in project_data["conversations"], "RAG sohbeti proje dosyasına yazılmadı."
    assert project_data["conversations"]["2"]["projectName"] == "MyProject"

    legacy_dir = os.path.join(td, "legacy")
    os.makedirs(legacy_dir, exist_ok=True)
    legacy_path = os.path.join(legacy_dir, "auto.json")
    with open(legacy_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "conversations": {**normal, **rag},
                "currentConvId": "2",
                "nextId": 3,
            },
            f,
            ensure_ascii=False,
        )

    # migrate_legacy_project_conversations taban dizinde chat_history bekler.
    base_dir = os.path.join(td, "migration_root")
    os.makedirs(os.path.join(base_dir, "chat_history"), exist_ok=True)
    with open(os.path.join(base_dir, "chat_history", "auto.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "conversations": {**normal, **rag},
                "currentConvId": "2",
                "nextId": 3,
            },
            f,
            ensure_ascii=False,
        )

    projects_config = {
        "MyProject": {"path": project_dir}
    }

    moved, skipped = migrate_legacy_project_conversations(base_dir, projects_config)
    migrated = load_project_conversations(project_dir)
    global_after = load_global_conversations(os.path.join(base_dir, "chat_history"))

    assert moved >= 1, "Eski RAG sohbeti proje dosyasına taşınmadı."
    assert "2" in migrated["conversations"], "Taşınan RAG sohbeti proje dosyasında yok."
    assert "2" not in global_after["conversations"], "Taşınan RAG sohbeti global okumaya geri sızdı."
    assert os.path.exists(project_conversation_path(project_dir)), "Proje conversation.json oluşmadı."

    print("[OK] Normal sohbet global chat_history'de.")
    print("[OK] RAG sohbeti global chat_history'ye yazılmıyor/okunmuyor.")
    print("[OK] RAG sohbeti proje/.gk_studio/conversation.json içinde.")
    print(f"[OK] Legacy migration moved={moved}, skipped={skipped}.")
    print("[OK] RAG conversation isolation architecture passed.")
'@ | python -

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[HATA] RAG conversation isolation testi başarısız." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "TEST TAMAMLANDI." -ForegroundColor Green
