#!/usr/bin/env python3
"""Render .mmd to .svg/.png, or plain-text .json to self-contained .html."""

import argparse
import base64
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
VERSION = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
STYLE = """
:root { color-scheme: light dark; font: 16px/1.55 system-ui, sans-serif; }
body { max-width: 1050px; margin: auto; padding: 32px 24px; }
h1 { font-size: 1.8rem; line-height: 1.2; margin: 0 0 16px; }
p { white-space: pre-wrap; overflow-wrap: anywhere; }
.summary { font-size: 1.1rem; margin-bottom: 28px; }
figure { margin: 24px 0 32px; }
img { display: block; width: 100%; height: auto; background: white; }
details { border-top: 1px solid #8886; padding: 14px 0; }
summary { cursor: pointer; font-weight: 600; overflow-wrap: anywhere; }
details p { margin: 16px 0 8px; }
.sheet { color-scheme: light; background: #f7f8fa; color: #26313f;
  max-width: 1440px; font: 14px/1.4 'Arial Narrow', Arial, sans-serif; }
.sheet * { box-sizing: border-box; }
.sheet main { background: #fff; border: 1px solid #7b8491; outline: 1px solid #bcc2cb;
  outline-offset: 7px; padding: 18px; }
.sheet h1 { font-size: 22px; margin: 0 0 6px; }
.sheet .summary { font-size: 13px; margin: 0 0 18px; color: #536174; }
.panels { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 16px; }
.panel { min-width: 0; border: 1px solid #75808e; grid-column: span var(--span); }
.panel h2 { display: flex; align-items: stretch; gap: 12px; font-size: 14px;
  margin: 0; border-bottom: 1px solid #75808e; padding: 0 12px 0 0; line-height: 32px; }
.panel h2 span { display: grid; place-items: center; flex: 0 0 30px;
  font: 12px monospace; background: #26313f; color: #fff; }
.panel-content { padding: 14px; }
.panel figure { margin: 0; }
.panel img { height: 300px; object-fit: contain; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th, td { text-align: left; vertical-align: top; overflow-wrap: anywhere;
  padding: 9px 8px; border-bottom: 1px solid #dce1e8; }
th { font: 11px/1.4 monospace; color: #536174; }
tbody tr:nth-child(odd) { background: #f3f6fa; }
tbody tr:last-child td { border-bottom: 0; }
.steps { margin: 0; padding-left: 24px; }
.steps li { padding: 10px 0 10px 6px; overflow-wrap: anywhere; }
.steps li::marker { font: 12px monospace; color: #245bb0; }
.anatomy { display: grid; gap: 16px; margin: 0; }
.anatomy div { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: center; }
.anatomy dt { font: 14px/1.5 monospace; padding: 8px; background: #f3f6fa;
  border-bottom: 1px solid #245bb0; overflow-wrap: anywhere; }
.anatomy dd { margin: 0; font-size: 12px; color: #245bb0; overflow-wrap: anywhere; }
.sheet footer { display: flex; justify-content: space-between; margin-top: 14px;
  padding-top: 10px; border-top: 1px solid #bcc2cb; font: 11px monospace; color: #536174; }
@media (max-width: 1100px) {
  .panel { grid-column: span 6; }
  .panel[data-span="8"], .panel[data-span="12"] { grid-column: span 12; }
}
@media (max-width: 800px) { .panel { grid-column: span 12; } }
@media (max-width: 600px) { body { padding: 20px 16px; } }
@media print { details::details-content { content-visibility: visible; }
  details p { display: block; } }
"""


def fields(value, required, optional=()):
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    if set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError(f"Required fields: {', '.join(required)}; optional: {', '.join(optional)}")


def text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Text fields must be non-empty strings")
    return html.escape(value)


def render_image(diagram, base, span=None):
    fields(diagram, ("path", "alt"))
    text(diagram["path"])
    image_path = (base / diagram["path"]).resolve()
    if Path(diagram["path"]).is_absolute() or not image_path.is_relative_to(base.resolve()):
        raise ValueError("Diagram must be inside the JSON file's folder")
    mime = {".svg": "image/svg+xml", ".png": "image/png"}.get(image_path.suffix.lower())
    if not mime:
        raise ValueError("Diagram must be SVG or PNG")
    raw = image_path.read_bytes()
    if span is not None:
        if image_path.suffix.lower() != '.svg':
            raise ValueError("Use SVG in sheet panels so label size can be checked. PNG remains available for standalone diagrams.")
        try:
            svg = ET.fromstring(raw)
            _, _, width, height = map(float, svg.attrib['viewBox'].replace(',', ' ').split())
            if not 0 < width < 100000 or not 0 < height < 100000:
                raise ValueError
        except (ET.ParseError, KeyError, ValueError):
            raise ValueError("Sheet SVG needs a valid, positive viewBox") from None
        sizes = re.findall(r'font-size\s*:\s*([\d.]+)px', raw.decode('utf-8'))
        font = float(sizes[0]) if sizes else 16
        # Estimate from the SVG base font at 1440px; later rules can be unused tooltip styles.
        scale = min((1280 * span / 12 - 32) / width, 300 / height)
        if font * scale < 12:
            raise ValueError("Sheet diagram labels would be too small. Redraw a short overview, use a wider span, or put the full flow in detail; do not shrink it.")
    encoded = base64.b64encode(raw).decode("ascii")
    return f'<figure><img src="data:{mime};base64,{encoded}" alt="{text(diagram["alt"])}"></figure>'


def text_list(value):
    if not isinstance(value, list) or not value:
        raise ValueError("Expected a non-empty list of text")
    return [text(item) for item in value]


def short_text(value, limit, location):
    result = text(value)
    if len(value.split()) > limit or len(value) > limit * 14:
        raise ValueError(f"{location}: keep to {limit} words; move the explanation to sections instead of truncating it")
    return result


def render_panels(panels, base):
    if not isinstance(panels, list) or not 1 <= len(panels) <= 6:
        raise ValueError("Use 1–6 panels for a reference sheet")
    rendered = []
    for index, panel in enumerate(panels):
        fields(panel, ("title",), ("diagram", "table", "steps", "anatomy", "span"))
        span = panel.get('span', 6)
        if type(span) is not int or span not in (4, 6, 8, 12):
            raise ValueError("Panel span must be 4, 6, 8, or 12")
        if len(set(panel) & {'diagram', 'table', 'steps', 'anatomy'}) != 1:
            raise ValueError("Each panel needs exactly one diagram, table, steps list, or anatomy")
        title = short_text(panel['title'], 8, 'Panel title')
        if "diagram" in panel:
            content = render_image(panel["diagram"], base, span)
        elif "steps" in panel:
            text_list(panel['steps'])
            if len(panel['steps']) > 4:
                raise ValueError("Sheet example: use at most 4 steps; put the full procedure in sections")
            content = '<ol class="steps">' + ''.join(f'<li>{short_text(item, 16, "Step")}</li>' for item in panel['steps']) + '</ol>'
        elif "anatomy" in panel:
            if not isinstance(panel['anatomy'], list) or not 1 <= len(panel['anatomy']) <= 4:
                raise ValueError("Use 1–4 annotated values")
            parts = []
            for part in panel['anatomy']:
                fields(part, ('value', 'label'))
                parts.append(f'<div><dt>{short_text(part["value"], 8, "Value")}</dt>'
                             f'<dd>{short_text(part["label"], 10, "Annotation")}</dd></div>')
            content = '<dl class="anatomy">' + ''.join(parts) + '</dl>'
        else:
            table = panel["table"]
            fields(table, ("headers", "rows"))
            headers = text_list(table["headers"])
            if not isinstance(table["rows"], list) or not 1 <= len(table["rows"]) <= 6:
                raise ValueError("Sheet tables need 1–6 rows")
            rows = [text_list(row) for row in table["rows"]]
            if any(len(row) != len(headers) for row in rows):
                raise ValueError("Each table row must match the number of headers")
            for row in [table['headers'], *table['rows']]:
                for cell in row:
                    short_text(cell, 12, 'Table cell')
            content = '<table><thead><tr>' + ''.join(f'<th scope="col">{item}</th>' for item in headers)
            content += '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{item}</td>' for item in row) + '</tr>' for row in rows) + '</tbody></table>'
        rendered.append(f'<section class="panel" data-span="{span}" style="--span:{span}"><h2><span>{chr(65 + index)}</span>{title}</h2>'
                        f'<div class="panel-content">{content}</div></section>')
    return '<div class="panels">' + ''.join(rendered) + '</div>'


def render_detail(data, base):
    fields(data, ("title", "summary", "sections"), ("diagram", "panels"))
    title, summary = text(data["title"]), text(data["summary"])
    if not isinstance(data["sections"], list):
        raise ValueError("sections must be a list")
    figure = render_image(data["diagram"], base) if "diagram" in data else ""
    panels = render_panels(data["panels"], base) if "panels" in data else ""
    if panels:
        short_text(data['summary'], 30, 'Sheet summary')
    sections = []
    for section in data["sections"]:
        fields(section, ("title", "text"))
        sections.append(f'<details name="detail"><summary>{text(section["title"])}</summary>'
                        f'<p>{text(section["text"])}</p></details>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="Clearview {VERSION}">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{title}</title><style>{STYLE}</style></head>
<body class="{'sheet' if panels else ''}"><main><h1>{title}</h1><p class="summary">{summary}</p>
{figure}{panels}{''.join(sections)}{'<footer><span>' + title + '</span><span>Clearview · reference sheet</span></footer>' if panels else ''}</main></body></html>
'''


def render(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if source == destination:
        raise ValueError("Source and output must be different files")
    mode = (source.suffix.lower(), destination.suffix.lower())
    if mode not in {(".json", ".html"), (".mmd", ".svg"), (".mmd", ".png")}:
        raise ValueError("Use .json → .html or .mmd → .svg/.png")
    # Stage output so a failed render cannot replace an existing deliverable.
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        staged = Path(folder) / destination.name
        if mode[0] == ".json":
            staged.write_text(render_detail(json.loads(source.read_text(encoding="utf-8")),
                                            source.parent), encoding="utf-8")
        else:
            cli = ROOT / "node_modules/@mermaid-js/mermaid-cli/src/cli.js"
            if not cli.is_file():
                raise ValueError("Diagram renderer is missing. See setup in Clearview's README.md")
            env = dict(os.environ, PUPPETEER_CACHE_DIR=str(ROOT / ".cache/puppeteer"))
            subprocess.run(["node", str(cli), "-i", str(source), "-o", str(staged),
                            "-t", "neutral", "-b", "white", "-s", "2"],
                           env=env, cwd=ROOT, check=True)
        staged.replace(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=f'Clearview {VERSION}')
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        render(args.source, args.output)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Clearview: {error}\n")
    print(args.output.resolve())
