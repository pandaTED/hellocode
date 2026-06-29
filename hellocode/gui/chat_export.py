"""Chat export functionality."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from .i18n import t


def export_chat_to_markdown(chat_panel, session_id: str, parent=None) -> bool:
    """Export chat history to a Markdown file."""
    messages = chat_panel.get_messages() if hasattr(chat_panel, 'get_messages') else []

    if not messages:
        QMessageBox.information(parent, t("export"), t("no_messages_to_export"))
        return False

    default_name = f"chat_{session_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    file_path, _ = QFileDialog.getSaveFileName(
        parent,
        t("export_chat"),
        str(Path.home() / "Downloads" / default_name),
        "Markdown Files (*.md);;All Files (*)",
    )

    if not file_path:
        return False

    try:
        content = _build_markdown(messages, session_id)
        Path(file_path).write_text(content, encoding="utf-8")
        QMessageBox.information(parent, t("export"), f"{t('export_success')}\n{file_path}")
        return True
    except Exception as e:
        QMessageBox.warning(parent, t("error"), f"{t('export_failed')}: {e}")
        return False


def _build_markdown(messages: list[dict], session_id: str) -> str:
    """Build Markdown content from messages."""
    lines = [
        f"# Chat Session: {session_id[:8]}",
        f"",
        f"Exported at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        "---",
        "",
    ]

    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")

        if role == "user":
            lines.append(f"## You")
            if timestamp:
                lines.append(f"*{timestamp}*")
            lines.append("")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            lines.append(f"## Assistant")
            if timestamp:
                lines.append(f"*{timestamp}*")
            lines.append("")
            lines.append(content)
            lines.append("")
        elif role == "system":
            lines.append(f"> {content}")
            lines.append("")

    lines.append("---")
    lines.append(f"*Session ID: {session_id}*")
    return "\n".join(lines)
