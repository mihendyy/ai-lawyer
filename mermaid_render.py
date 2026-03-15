"""Рендер Mermaid-кода в PNG и HTML."""
import re
from pathlib import Path
from typing import Optional

# mermaido может быть не установлен (mermaido install) — работаем с fallback
try:
    import mermaido

    MERMAIDO_AVAILABLE = True
except ImportError:
    MERMAIDO_AVAILABLE = False


def _sanitize_mermaid(code: str) -> str:
    """Убирает обёртку mermaid/``` и маркеры разделителей из кода."""
    code = code.strip()
    if code.startswith("```"):
        code = re.sub(r"^```\w*\n?", "", code)
    if code.endswith("```"):
        code = code.rsplit("```", 1)[0].strip()
    if code.lower().startswith("mermaid"):
        code = code[6:].strip()
    # Удаляем маркеры ---MERMAID--- / ---РЕКОМЕНДАЦИИ--- (модель иногда вставляет в конец)
    for marker in ("---MERMAID---", "---РЕКОМЕНДАЦИИ---"):
        if marker in code:
            code = code.split(marker)[0].strip().rstrip(";")
    return code


def mermaid_to_png(mermaid_code: str, output_path: Path) -> bool:
    """
    Рендерит Mermaid в PNG. Возвращает True при успехе.
    Если mermaido не установлен или не инициализирован — False.
    """
    if not MERMAIDO_AVAILABLE:
        return False
    code = _sanitize_mermaid(mermaid_code)
    if not code:
        return False
    try:
        mermaido.render(code, str(output_path))
        return output_path.is_file()
    except Exception:
        return False


def mermaid_to_html(mermaid_code: str, output_path: Path, title: str = "Схема по договору") -> None:
    """
    Генерирует HTML-файл с Mermaid.js (CDN). Открывается в браузере, можно зумить и скроллить.
    """
    code = _sanitize_mermaid(mermaid_code)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
  </script>
  <style>
    body {{ margin: 0; padding: 24px; background: #f5f5f5; font-family: sans-serif; }}
    .mermaid {{ background: white; padding: 24px; border-radius: 8px; overflow: auto; }}
  </style>
</head>
<body>
  <div class="mermaid">
{code}
  </div>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")


def render_mermaid(
    mermaid_code: str,
    out_dir: Path,
    base_name: str = "diagram",
) -> tuple[Optional[Path], Path]:
    """
    Создаёт PNG (если возможно) и HTML. Возвращает (path_png или None, path_html).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    png_path = out_dir / f"{base_name}.png"
    html_path = out_dir / f"{base_name}.html"

    png_ok = mermaid_to_png(mermaid_code, png_path)
    mermaid_to_html(mermaid_code, html_path, title="Схема бизнес-процесса по договору")

    return (png_path if png_ok else None, html_path)

    
