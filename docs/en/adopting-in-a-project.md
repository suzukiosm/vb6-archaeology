# Adopting the kit in another repo

**[English](adopting-in-a-project.md)** · **[日本語](../adopting-in-a-project.md)**

## License first

This kit is **source-available**, not open source ([LICENSE](../../LICENSE)). Viewing and learning are welcome. Copying, modifying, redistributing, or embedding in another product needs prior permission (which may be paid).

The steps below are for **after a grant**, inside that contract.

## Goal

Ship `vb6-archaeology` as an investigation OS on an app repo.

## No global Cursor dependency

The kit does not need `~/.cursor/rules/_core.mdc`. You need Python 3.10+ and this repo’s `AGENTS.md` / `docs/` / `.cursor/` / `tools/`.

## Minimum copy

```
archaeology.config.json
schema/
AGENTS.md
tools/
.cursor/rules/
.cursor/skills/
.cursor/commands/
.cursor/hooks.json
.cursor/hooks/
docs/methodology.md
docs/workflow.md
docs/flow/_master.md
docs/ai-onboarding.md
docs/reimplementation-handoff.md
docs/QUICKREF.md
docs/templates/
```

Do **not** copy `source/mini_vbp/` (fixture), `working/` contents, or `docs/kit-dev-context.md` (kit maintenance, not app session facts).

## Config

Default originals directory is **`source/`**. If your tree has another name, change `protected_source_dirs` / `default_source_dir` only. Do not rename a live VB6 tree just to match the default.

```json
{
  "protected_source_dirs": ["source"],
  "default_source_dir": "source",
  "extracts_dir": "working/extracts",
  "reports_dir": "working/reports",
  "skeletons_dir": "working/skeletons",
  "geometry_hints": {},
  "deep_read_name_map": {},
  "encoding": "cp932"
}
```

Validate: `python -m tools config-check`.

App-specific Form names, MDI chrome, and layout scores belong in the **consumer** config (`mdi_chrome`, `layout_sub_scores`). Keep the kit defaults empty.

## After copy

1. Write a short consumer `AGENTS.md` (no long status dumps — those go in `docs/ai-dev-context.md`)
2. Run `python -m tools extract` on the real `.vbp`, then `inventory` / `verify`
3. Keep originals read-only. The only kit exception is `python -m tools fixture` for the sample VBP

Japanese original with extra consumer notes: [../adopting-in-a-project.md](../adopting-in-a-project.md).
