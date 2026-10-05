---
name: clearview
description: Turn existing agent work into a rendered diagram or a web page with sections readers can click to read more. Use when a user requests a visual explanation or a shareable overview.
metadata:
  version: "1.0.0"
---

# Clearview

Explain from evidence already available. Resolve only gaps that affect the explanation.
Do not launch another agent, repeat the investigation, or invent missing relationships.

Choose one output:
Honor an explicitly requested format. Otherwise, choose the lightest view that explains the subject.
- **Diagram:** default for relationships, sequence, or behavior. Write Mermaid to a `.mmd` file. Render to `.svg` (scalable) or `.png`. Deliver only the image and its location unless a qualification is essential.
- **Reference sheet:** for a broad overview that a single diagram cannot explain clearly. Use a few short panels: small diagrams, comparisons, or worked examples. Give panels specific titles such as "Where a job goes", not "Structure" or "Behavior". Each panel must add something different. Read `examples/sheet.json` for the input format.
- **Web page with detail:** when requested. Use sections readers can click to read more, optionally below a reference sheet. A diagram is optional.
- A simple factual answer stays text; do not manufacture an artifact.

Use familiar words, short sentences, and consistent names. Explain necessary jargon.
Show cause and effect, not a file inventory. Label arrows with their meaning.
Preserve important branches, conditions, uncertainty, and failures. Mark illustrative
examples and distinguish observed behavior from assumptions or plans.
"Explain", "show me", and "overview" mean help the reader understand, not list every step.
Include exhaustive steps only when requested. Keep a detail only if it changes how the
reader understands or uses the subject. Preserve consequential exceptions.
Use short labels, not sentences inside boxes. Aim for 4–8 main nodes per diagram.
If the overview needs scrolling or tiny labels, regroup it; do not just shrink it.
Use space for relationships and comparisons, not paragraphs or repeated summaries.
For sheets, draw a new small diagram for its panel; never insert the full workflow
as a thumbnail. Use short table entries, not sentences stacked in narrow columns.
Show connections and branches with a diagram; numbered steps are for actions or
a worked example. Do not replace a useful diagram with prose to bypass a layout
error. Report the error if regrouping or widening the diagram cannot resolve it.
Place relevant evidence references in detail text. Do not include secrets in shared output.

Write inputs and outputs in the task's working folder, not inside the installed skill.
Render with Python 3.10+ (replace CLEARVIEW with this folder's path):

```sh
python3 "CLEARVIEW/render.py" explanation.mmd explanation.svg
python3 "CLEARVIEW/render.py" explanation.json explanation.html
```

Web page JSON: `title` and `summary` are strings; `sections` is a list of objects with
`title` and `text` strings. Optional `diagram` contains `path` and `alt` strings.
Paths are relative to the JSON file, inside its folder. Text is plain text, not HTML
or Markdown. Blank lines separate paragraphs. See `examples/detail.json` only if needed.
If including a diagram, render it to SVG or PNG before rendering the web page.
For a reference sheet, add `panels` (1–6); each has `title` and exactly one of
`diagram`, `table` (with `headers` and `rows`), `steps` (a list of strings), or
`anatomy` (a list of `value`/`label` objects for an annotated example).
Optional `span` is 4, 6, 8, or 12 columns; default 6. Aim for 12 per row.
Sheet limits: 30-word summary, 8-word titles, 12-word cells, 6 table rows,
4 steps of 16 words, or 4 annotations. Sheet diagrams must be SVG; the renderer
rejects labels estimated below 12px at desktop width. A rejection means regroup
or move detail into sections, never delete a material condition just to fit.
Use `sections: []` when there is no hidden detail. Keep the overview readable without clicks.

Rendering has no model calls. Do not read or regenerate the renderer or styling.
If diagram dependencies are missing, report what is missing; do not install
automatically. HTML rendering needs only Python. Browser launch needs sandbox
permission where required; report a denial rather than trying other browser apps.
Keep this skill, renderer, and examples from the same checkout throughout a task.
Inspect the output directly when supported, checking for missing labels or clipped content. Correct
demonstrated defects; do not start an open-ended review loop. Report unverified checks.
Give the absolute output path and a working way to open it; source code alone is not delivery.
