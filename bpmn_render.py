"""Рендер BPMN-структуры (JSON) в HTML со swimlanes и стрелками; при возможности — в PNG."""
import asyncio
import json
from pathlib import Path
from typing import Optional

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def _html_template() -> str:
    return r"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Схема процесса по договору</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; padding: 20px; background: #f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    h1 { font-size: 1.25rem; margin: 0 0 16px 0; color: #1a1a1a; }
    .diagram-wrap { position: relative; background: #fff; border-radius: 8px; padding: 24px; overflow: auto; min-height: 400px; }
    .lane { display: flex; margin-bottom: 2px; min-height: 88px; border: 1px solid #d0d5dd; border-radius: 6px; overflow: visible; }
    .lane:last-child { margin-bottom: 0; }
    .lane-header { width: 140px; min-width: 140px; padding: 12px; background: #e8ecf1; font-weight: 600; font-size: 0.9rem; display: flex; align-items: center; }
    .lane-body { flex: 1; padding: 20px 24px; display: flex; align-items: center; gap: 32px; flex-wrap: nowrap; position: relative; min-height: 72px; }
    .step { position: relative; flex-shrink: 0; }
    .step-inner { padding: 10px 14px; font-size: 13px; text-align: center; max-width: 160px; word-wrap: break-word; border-radius: 4px; line-height: 1.35; }
    .step[data-type="start"] .step-inner { width: 44px; height: 44px; padding: 0; border-radius: 50%; background: #2d7d46; color: #fff; line-height: 44px; font-size: 0; max-width: none; }
    .step[data-type="end"] .step-inner { width: 44px; height: 44px; padding: 0; border-radius: 50%; border: 4px solid #1a1a1a; background: #fff; line-height: 36px; font-size: 0; max-width: none; }
    .step[data-type="task"] .step-inner { background: #dee8f0; border: 1px solid #7ba3c7; color: #1a1a1a; min-width: 80px; }
    .step[data-type="decision"] { min-width: 90px; }
    .step[data-type="decision"] .step-inner { background: #fff4e0; border: 1px solid #d4a84b; transform: rotate(-45deg); width: 70px; height: 70px; padding: 0; max-width: none; display: flex; align-items: center; justify-content: center; }
    .step[data-type="decision"] .step-label { transform: rotate(45deg); display: block; width: 100px; font-size: 11px; line-height: 1.25; text-align: center; word-break: break-word; }
    .arrows { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; overflow: visible; }
  </style>
</head>
<body>
  <h1>Схема бизнес-процесса по договору</h1>
  <div class="diagram-wrap" id="diagram">
    <div class="arrows" id="arrows"></div>
  </div>
  <script>
    (function() {
      const DATA = __BPMN_DATA__;
      const diagram = document.getElementById('diagram');
      const arrowsWrap = document.getElementById('arrows');

      const lanes = DATA.lanes || [];
      const steps = DATA.steps || [];
      const connections = DATA.connections || [];

      const stepById = {};
      steps.forEach(s => { stepById[s.id] = s; });
      const laneOrder = {};
      lanes.forEach((l, i) => { laneOrder[l.id] = i; });

      lanes.forEach(lane => {
        const laneSteps = steps.filter(s => s.laneId === lane.id);
        const row = document.createElement('div');
        row.className = 'lane';
        row.innerHTML = '<div class="lane-header">' + escapeHtml(lane.title) + '</div><div class="lane-body" data-lane-id="' + escapeAttr(lane.id) + '"></div>';
        const body = row.querySelector('.lane-body');
        laneSteps.forEach(step => {
          const el = document.createElement('div');
          el.className = 'step';
          el.dataset.stepId = step.id;
          el.dataset.type = step.type || 'task';
          const label = step.type === 'decision' ? '<span class="step-label">' + escapeHtml(step.label || '') + '</span>' : escapeHtml(step.label || '');
          el.innerHTML = '<div class="step-inner">' + label + '</div>';
          body.appendChild(el);
        });
        diagram.appendChild(row);
      });

      function escapeHtml(s) {
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
      }
      function escapeAttr(s) {
        return String(s).replace(/"/g, '&quot;');
      }

      const arrowsContainer = document.getElementById('arrows');

      function drawArrows() {
        const base = diagram.getBoundingClientRect();
        const OFFSET = 28;
        diagram.querySelectorAll('.step').forEach(el => {
          const r = el.getBoundingClientRect();
          const left = r.left - base.left;
          const right = left + r.width;
          const top = r.top - base.top;
          const bottom = top + r.height;
          const cx = (left + right) / 2;
          const cy = (top + bottom) / 2;
          el.dataset.centerX = cx.toFixed(1);
          el.dataset.centerY = cy.toFixed(1);
          el.dataset.right = right.toFixed(1);
          el.dataset.left = left.toFixed(1);
          el.dataset.top = top.toFixed(1);
          el.dataset.bottom = bottom.toFixed(1);
        });

        const svgNs = 'http://www.w3.org/2000/svg';
        const svgEl = document.createElementNS(svgNs, 'svg');
        svgEl.setAttribute('class', 'arrows');
        svgEl.style.position = 'absolute';
        svgEl.style.top = '0';
        svgEl.style.left = '0';
        svgEl.style.width = '100%';
        svgEl.style.height = '100%';
        svgEl.style.pointerEvents = 'none';

        const defs = document.createElementNS(svgNs, 'defs');
        const marker = document.createElementNS(svgNs, 'marker');
        marker.setAttribute('id', 'arrowhead');
        marker.setAttribute('markerWidth', '10');
        marker.setAttribute('markerHeight', '7');
        marker.setAttribute('refX', '9');
        marker.setAttribute('refY', '3.5');
        marker.setAttribute('orient', 'auto');
        const poly = document.createElementNS(svgNs, 'polygon');
        poly.setAttribute('points', '0 0, 10 3.5, 0 7');
        poly.setAttribute('fill', '#5a6c7d');
        marker.appendChild(poly);
        defs.appendChild(marker);
        svgEl.appendChild(defs);

        connections.forEach(c => {
          const fromEl = diagram.querySelector('.step[data-step-id="' + escapeAttr(c.from) + '"]');
          const toEl = diagram.querySelector('.step[data-step-id="' + escapeAttr(c.to) + '"]');
          if (!fromEl || !toEl) return;
          const x1 = parseFloat(fromEl.dataset.right);
          const y1 = parseFloat(fromEl.dataset.centerY);
          const x2 = parseFloat(toEl.dataset.left);
          const y2 = parseFloat(toEl.dataset.centerY);
          var d;
          if (Math.abs(y1 - y2) < 8) {
            d = 'M' + x1 + ',' + y1 + ' L' + x2 + ',' + y2;
          } else if (x1 + OFFSET <= x2 - OFFSET) {
            d = 'M' + x1 + ',' + y1 + ' L' + (x1 + OFFSET) + ',' + y1 + ' L' + (x1 + OFFSET) + ',' + y2 + ' L' + (x2 - OFFSET) + ',' + y2 + ' L' + x2 + ',' + y2;
          } else {
            var xMid = (x1 + x2) / 2;
            d = 'M' + x1 + ',' + y1 + ' L' + xMid + ',' + y1 + ' L' + xMid + ',' + y2 + ' L' + x2 + ',' + y2;
          }
          const path = document.createElementNS(svgNs, 'path');
          path.setAttribute('d', d);
          path.setAttribute('fill', 'none');
          path.setAttribute('stroke', '#5a6c7d');
          path.setAttribute('stroke-width', '2');
          path.setAttribute('marker-end', 'url(#arrowhead)');
          svgEl.appendChild(path);
        });

        arrowsContainer.innerHTML = '';
        arrowsContainer.appendChild(svgEl);
      }

      requestAnimationFrame(function() { requestAnimationFrame(drawArrows); });
    })();
  </script>
</body>
</html>"""


def render_bpmn_html(bpmn_data: dict, output_path: Path, title: str = "Схема процесса по договору") -> None:
    """
    Генерирует HTML-файл с отрисовкой дорожек (swimlanes) и шагов по bpmn_data.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(bpmn_data, ensure_ascii=False)
    # Экранируем для вставки в JS: </script> и обратные слэши
    json_safe = json_str.replace("\\", "\\\\").replace("</", "<\\/")
    html = _html_template().replace("__BPMN_DATA__", json_safe)
    output_path.write_text(html, encoding="utf-8")


async def render_bpmn_to_png(html_path: Path, png_path: Path) -> bool:
    """
    Открывает HTML со схемой в headless-браузере и сохраняет скриншот в PNG.
    Возвращает True при успехе. Требует: pip install playwright && playwright install chromium.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return False
    html_path = Path(html_path)
    png_path = Path(png_path)
    if not html_path.is_file():
        return False
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1200, "height": 800})
            await page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
            await page.wait_for_selector(".lane", timeout=5000)
            await asyncio.sleep(1.5)  # даём отрисоваться стрелкам (requestAnimationFrame)
            await page.screenshot(path=str(png_path), full_page=True, type="png")
            await browser.close()
        return png_path.is_file()
    except Exception:
        return False
