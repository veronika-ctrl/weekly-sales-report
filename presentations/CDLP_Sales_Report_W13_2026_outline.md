# CDLP Sales Report — W13 2026 (outline)

Source deck (local reference, not in repo):

`~/Downloads/CDLP Sales Report W13 2026.pptx`

## Why most slides have no “copy” here

That file is built from **embedded screenshots** (exported from the weekly report app / Google Slides). Text lives inside **images**, not in PowerPoint text boxes — so automated extraction only sees **titles** on slides that still use native text.

## Slide map (18 slides)

| # | Type | Visible text in source | What to put here |
|---|------|------------------------|------------------|
| 1 | Title | **WEEKLY REPORT** · **23 – 29 March 2026** | Keep as cover; update dates per week. |
| 2 | Screenshot | *(image only)* | Re-capture from app or paste updated screenshot. |
| 3 | Screenshot | *(image only)* | Same. |
| 4 | Screenshot | *(image only)* | Same. |
| 5 | Screenshot | *(image only)* | Same. |
| 6 | Screenshot | *(image only)* | Same. |
| 7 | Screenshot | *(image only)* — slide 7 uses **two** stacked images | Same (often two charts in one slide). |
| 8 | Section title | **Markets** · **16 – 22 March 2026** | Section break; dates may differ from slide 1 (different reporting window in source). |
| 9–18 | Screenshot | *(image only)* | Markets / audience / detail views from app. |

## Text + numbers without PowerPoint

From the repo root, after saving JSON exports under `reports/`:

```bash
python scripts/build_slides_markdown.py 2026-12 http://127.0.0.1:8000
```

Copy the printed markdown into speaker notes, Google Docs, or slide bodies.

## Generated starter deck

To create a **blank structured .pptx** with the same titles and placeholder instructions:

```bash
pip install -e ".[slides]"
python scripts/generate_weekly_report_pptx_outline.py
```

Output: `presentations/CDLP_Sales_Report_outline_generated.pptx` (overwritten each run unless you pass `--out`).
