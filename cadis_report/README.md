# CADIS report (LaTeX)

Drag-and-drop this whole folder into Overleaf. Set **`main.tex`** as the main document and compile
(Overleaf runs `pdflatex` + `bibtex` automatically). Locally: `pdflatex main` → `bibtex main` →
`pdflatex main` → `pdflatex main`.

## Contents
- `main.tex` — the document (Introduction, Related Work, Development, Testing Environment,
  Results, Discussion, Limitations, Conclusion). Self-contained: the flowchart and activity diagram
  are drawn inline in TikZ; all three result tables are inline.
- `references.bib` — bibliography.
- `figures/` — empty; drop the result diagrams here later and `\includegraphics` them where you want.

## Notes
- **Formatting is intentionally minimal** (plain `article` class) — restyle as you like.
- **Citations** are the standard works in the area (self-consistency, PentestGPT, AutoPenBench,
  calibration, AI-safety oversight, MITRE ATT&CK). Replace/extend `references.bib` to match the exact
  literature you reviewed.
- **Angle:** the document argues CADIS *works as a precise, efficient risk-gating layer*, with the
  honesty guardrails (HCR=0 so the claim is about mechanism not realised-harm; risk=productivity on
  these targets) kept in Discussion/Limitations.
- Data in the tables comes from the four billable runs (3-model core suite + AutoPenBench). Regenerate
  the underlying numbers with the scripts under `benchmark/risk_gating_figures/`.
