"""Просмотр ответов нейросетей в форматированном Markdown."""

from __future__ import annotations

from datetime import datetime

import markdown
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

import appearance

MARKDOWN_EXTENSIONS = [
    "extra",
    "fenced_code",
    "tables",
    "nl2br",
    "sane_lists",
    "codehilite",
]

HTML_TEMPLATE = """
<html>
<head>
<meta charset="utf-8">
<style>
    body {{
        font-family: "Segoe UI", sans-serif;
        font-size: 11pt;
        color: #1a1a1a;
        line-height: 1.5;
        margin: 0;
        padding: 4px;
    }}
    h1 {{ font-size: 18pt; margin-top: 0; margin-bottom: 12px; }}
    h2 {{ font-size: 14pt; margin-top: 18px; margin-bottom: 8px; }}
    h3 {{ font-size: 12pt; margin-top: 14px; margin-bottom: 6px; }}
    p {{ margin: 8px 0; }}
    ul, ol {{ margin: 8px 0 8px 24px; }}
    li {{ margin: 4px 0; }}
    hr {{
        border: none;
        border-top: 1px solid #cccccc;
        margin: 16px 0;
    }}
    code {{
        font-family: Consolas, "Courier New", monospace;
        background: #f3f3f3;
        padding: 2px 4px;
        border-radius: 3px;
    }}
    pre {{
        background: #f3f3f3;
        padding: 12px;
        border-radius: 4px;
        overflow-x: auto;
        white-space: pre-wrap;
        word-wrap: break-word;
    }}
    pre code {{
        background: transparent;
        padding: 0;
    }}
    table {{
        border-collapse: collapse;
        margin: 12px 0;
        width: 100%;
    }}
    th, td {{
        border: 1px solid #cccccc;
        padding: 6px 10px;
        text-align: left;
        vertical-align: top;
    }}
    th {{
        background: #f7f7f7;
    }}
    a {{
        color: #0066cc;
        text-decoration: none;
    }}
    a:hover {{
        text-decoration: underline;
    }}
    strong {{ font-weight: 600; }}
</style>
</head>
<body>
{content}
</body>
</html>
"""


def build_response_markdown(
    model_name: str,
    prompt_text: str,
    response_text: str,
    received_at: str | None = None,
) -> str:
    lines = [f"# Результат от модели: {model_name}", ""]

    if received_at:
        lines.extend([f"**Дата:** {received_at}", ""])

    lines.extend(
        [
            "---",
            "",
            "## Промт",
            "",
            prompt_text.strip(),
            "",
            "---",
            "",
            "## Ответ",
            "",
            response_text.strip(),
            "",
        ]
    )
    return "\n".join(lines)


def render_markdown_to_html(markdown_text: str) -> str:
    html_body = markdown.markdown(
        markdown_text,
        extensions=MARKDOWN_EXTENSIONS,
        output_format="html5",
    )
    return HTML_TEMPLATE.format(content=html_body)


class MarkdownViewerDialog(QDialog):
    """Модальное окно просмотра Markdown."""

    def __init__(
        self,
        model_name: str,
        markdown_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Просмотр: {model_name}")
        self.setModal(True)
        self.resize(820, 620)
        self.setMinimumSize(640, 480)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(render_markdown_to_html(markdown_text))

        close_button = QPushButton("Закрыть")
        close_button.setFixedWidth(100)
        close_button.clicked.connect(self.accept)

        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self.browser, stretch=1)
        layout.addLayout(buttons)
        appearance.apply_fonts_to_widget(self)


def show_response_markdown(
    parent: QWidget,
    model_name: str,
    prompt_text: str,
    response_text: str,
    received_at: str | None = None,
) -> None:
    markdown_text = build_response_markdown(
        model_name=model_name,
        prompt_text=prompt_text,
        response_text=response_text,
        received_at=received_at,
    )
    dialog = MarkdownViewerDialog(model_name, markdown_text, parent=parent)
    dialog.exec()
    parent.activateWindow()
    parent.raise_()


def format_received_at(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value
