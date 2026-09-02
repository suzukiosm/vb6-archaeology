# vb6-archaeology

**[English](README.md)** · **[日本語](README.ja.md)**

[![CI](https://github.com/suzukiosm/vb6-archaeology/actions/workflows/ci.yml/badge.svg)](https://github.com/suzukiosm/vb6-archaeology/actions/workflows/ci.yml)

**Understand Visual Basic 6 without breaking it.** Read-only originals, extract → inventory → deep-read → evidence-backed comprehension. Python 3.10+, standard library only.

> **This is VB6, not VBA.** Desktop `.vbp` / `.frm` / `.bas` / `.cls` / `.ctl`. Not Office macros, not VB.NET, not VBScript. A [short comparison](docs/en/vb6-not-vba.md) is in the docs.

![Inventory report for the kit fixture: five files, thirteen procedures, Japanese project title decoded as CP932](docs/assets/inventory.png)

The screenshot is the fixture `mini_vbp` (Japanese captions, CP932). Reports are served over HTTP — do not open them as `file://`.

## Why this exists

Coding agents guess. Japanese VB6 is usually **CP932**, so a UTF-8 read garbles captions and string literals. A guessed call graph then ships the wrong screen.

This kit is an investigation OS, not a converter:

- Originals stay read-only (hooks deny writes into `source/` and any `protected_source_dirs`)
- Facts and guesses are separate. No regex-wide call graph
- Names in reports must exist in the inventory
- “100%” means a checklist is done, not that the whole app is understood

It is closer to field archaeology than to a parser library: copy the site, catalogue what is there, read with evidence, then (optionally) rebuild elsewhere.

## What you get

```text
.vbp (read-only)
    → extract       working/extracts/<stem>/
    → inventory     files, procedures, Show text, VBP metadata
    → verify        End counts / name sets / show_style (separate commands)
    → deep-read     Form chrome + .bas/.cls surface
    → layout        runtime coordinates from code
    → comprehend    evidence ticks (human + citations)
    → excerpt       short handoff HTML for a later rewrite
```

Single entry: `python -m tools <command>` (`python -m tools --help`). No extra pip packages.

## Not a parser, not VBA, not a rewrite

| | This kit | Parser libraries (e.g. [vb6parse](https://github.com/scriptandcompile/vb6parse), [ProLeap](https://github.com/uwol/proleap-vb6-parser)) | VBA tools (e.g. Rubberduck) |
|---|---|---|---|
| Target | VB6 investigation + AI workflow | Syntax tree / CST | Office VBA |
| Originals | Read-only + deny-write hooks | Parse in place | N/A |
| Japanese source | CP932 first-class | Encoding is your problem | Different product |
| Call graphs | Refused (Show text is listed, not inferred) | Possible | N/A |
| Output | Inventory, skeletons, evidence ticks | AST | Inspections |

Use a parser when you need an AST. Use this kit when you must not destroy the tree and must not let an agent invent edges.

## 5 minutes

```bash
cd <this-repo>
python -m tools demo
```

Open the URL printed on stdout (landing, inventory HTML, `/excerpt`). If port 8765 is taken, the printed URL is the real one — do not assume 8765.

Full investigation cycle (verify, deep-read, layout, ticks) is `python -m tools --help`. Self-check:

```bash
python -m tools smoke
```

## Encoding (CP932)

Japanese VB6 is **not UTF-8**. Cursor’s file Read can mojibake. Do not cite garbled text. Decode through `python -m tools lines` or the kit tools.

Details: [English](docs/en/encoding-cp932.md) · [日本語](docs/encoding-cp932.md)

## For AI agents

1. Read **[AGENTS.md](AGENTS.md)** (Japanese operator entry; commands are language-neutral)
2. Read **[docs/ai-onboarding.md](docs/ai-onboarding.md)**
3. Enter through Cursor commands (`/vb6-extract`, …) or the matching skills under `.cursor/skills/`
4. Never write into `source/` (or other `protected_source_dirs`)

The kit does not depend on a global Cursor ruleset. Python 3.10+ and this repo are enough.

## Documentation

| | English | 日本語 |
|---|---|---|
| This landing | [README.md](README.md) | [README.ja.md](README.ja.md) |
| Doc hub | [docs/en/README.md](docs/en/README.md) | [docs/README.md](docs/README.md) |
| VB6 ≠ VBA | [docs/en/vb6-not-vba.md](docs/en/vb6-not-vba.md) | [docs/vb6-not-vba.md](docs/vb6-not-vba.md) |
| Adopt in another repo | [docs/en/adopting-in-a-project.md](docs/en/adopting-in-a-project.md) | [docs/adopting-in-a-project.md](docs/adopting-in-a-project.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) | (same file, bilingual) |

Rewrite product checks: [docs/reimplementation-handoff.md](docs/reimplementation-handoff.md) (Japanese; investigation done ≠ UI done).

## Layout

```
source/                 # read-only VB6 originals (hooks)
working/extracts/       # analysis copies
working/reports/        # inventory / deep-read / excerpt
working/skeletons/      # Form skeleton JSON
tools/                  # CLI (python -m tools)
docs/                   # methodology, adopt guide, templates
docs/en/                # English public docs
docs/assets/            # README screenshots (fixture)
schema/                 # archaeology.config.json JSON Schema
.cursor/                # rules / skills / commands / hooks
archaeology.config.json # protected dirs, outputs, layout hints
```

## Using this in another repo

**Prior permission is required** ([LICENSE](LICENSE)). After a grant, see [docs/en/adopting-in-a-project.md](docs/en/adopting-in-a-project.md).

Minimum set: `tools/` + `.cursor/` + `schema/` + `archaeology.config.json` + an `AGENTS.md` stub.

Viewing and learning from this repository is welcome.

## License

See [LICENSE](LICENSE).
