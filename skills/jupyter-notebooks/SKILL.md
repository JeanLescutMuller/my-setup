---
name: jupyter-notebooks
description: Personal Jupyter notebook conventions. Use when writing, editing, or reviewing a .ipynb file for this user.
---

## Owner has no time - optimize for a five-second skim

Same directive as everywhere else on this machine: simple, commented,
graphical, clear. A notebook gets read by someone tired and in a hurry, not
executed by a machine for its own sake - every cell should either set up
the next one or hand back something immediately legible (a chart, a short
clear print, a small table), never a wall of unstyled numbers.

## Code style: `python-coding` applies in full

`.ipynb` code cells are still Python - load the `python-coding` skill
alongside this one rather than duplicating its rules here. In particular:
the `d_`/`a_`/`s_`/`df_`/`l_` variable-prefix convention, concise code over
needless decomposition (a helper function nested inside the cell that uses
it is fine and often preferred), and comment more liberally than the
general default to compensate for terser code.

## Every cell must actually run - verify it, don't assume it

Before considering a notebook edit done, execute it end-to-end and confirm
zero errors. Don't eyeball a diff and call it finished:

```bash
jupyter nbconvert --to notebook --execute --inplace <notebook>.ipynb \
    --ExecutePreprocessor.timeout=120
```

Use the environment the notebook's own docs point at (check for a
`condaPath`/env note, or ask if unclear) - don't assume the first `python3`
on `PATH` has the right packages. After running, check every code cell's
`outputs` for an `error` output_type - a clean nbconvert exit code alone
isn't sufficient if a cell was skipped or the kernel restarted mid-run.

## Outputs must be graphical, not walls of text

A cell that produces output should produce a **chart** wherever the
content is inherently visual (a trend, a comparison across categories, a
breakdown, a distribution) - not a printed table or a loop of `print()`
calls. Load the `dataviz` skill before writing or restyling any chart
cell: its validated palette, chart-form-selection guidance, and
mark/spacing specs apply to matplotlib exactly as they apply to a web
chart, and it's the source of truth for the actual color values - don't
hardcode a palette here that could drift from it.

A short `print()` or a small `pandas`/`polars` table is still fine for
something that's genuinely a handful of numbers (a stat, a sanity check, a
row count) - not everything needs to be a chart. The test: would a chart
make this easier to read at a glance, or is it already about as simple as
it can be as plain text?

When a chart cell changes meaningfully, actually look at the rendered
image (extract the `image/png` output and view it) rather than trusting
the code alone - matplotlib layout issues (overlapping labels, clipped
titles, legends over data) only show up visually.

## Practical defaults

- One shared style/helper cell near the top (colors, a `style_axes()`-style
  spine/gridline cleanup helper) - referenced by every chart cell after
  it, not repeated matplotlib boilerplate per cell.
- Strip chart junk by default: no top/right spines, hairline gridlines
  only, muted axis ink, thin marks.
- A fixed, small categorical color order (2-4 colors, from the `dataviz`
  skill's palette) reused consistently for the same recurring series
  across the whole notebook (e.g. one color always means "Claude", another
  always means "Codex") - never reassigned cell to cell.
- Trim exploratory or superseded narrative before shipping: keep the
  validated finding, cut a "here's what I tried and ruled out" digression
  to a line or two, not a full paragraph, unless the ruling-out itself is
  the point being made.
- No separate `.py` script for something only the notebook itself
  consumes - if nothing else imports it or calls it from a scheduler, it
  belongs inline in a cell, not as an external file the notebook shells
  out to or reads pre-generated output from.
