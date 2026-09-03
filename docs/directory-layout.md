# ディレクトリレイアウト

```
vb6-archaeology/
├── AGENTS.md                 # AI 入口（短い）
├── README.md                 # 人間向け（English・GitHub 既定）
├── README.ja.md              # 人間向け（日本語）
├── .gitattributes            # Linguist: .bas/.frm は VB6（VBA ではない）
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── LICENSE
├── archaeology.config.json   # 保護 dir・出力先・layout hints（mdi_chrome 等）
├── schema/
│   └── archaeology.config.schema.json   # 上記設定の JSON Schema
├── source/                   # 読取専用正本（既定）
│   ├── README.md
│   └── mini_vbp/             # スモーク用フィクスチャ
├── working/
│   ├── extracts/<stem>/      # 切り出し
│   ├── readable/<stem>/      # UTF-8 読取コピー（行番号は extracts と同じ）
│   ├── reports/              # 調査成果（inventory / deep_read / excerpt 等）
│   └── skeletons/            # Form skeleton / runtime-layout.json
├── tools/
│   ├── README.md
│   ├── __main__.py           # python -m tools
│   ├── cli.py                # サブコマンド表（COMMANDS）
│   ├── kit_smoke.py          # 自己点検（pipeline + unittest）
│   ├── demo.py               # extract → inventory → excerpt → serve
│   ├── lib/
│   │   ├── config.py
│   │   ├── config_schema.py
│   │   ├── console.py
│   │   ├── report_html.py
│   │   ├── show_style.py
│   │   ├── vbparse.py
│   │   └── cache.py
│   ├── extract_vbp.py
│   ├── vb6_inventory.py
│   ├── verify_inventory.py
│   ├── verify_report_names.py
│   ├── frm_deep_read.py
│   ├── frm_deep_read_all.py
│   ├── runtime_layout.py
│   ├── comprehension_scaffold.py
│   ├── reimpl_excerpt.py
│   ├── io_catalog.py
│   ├── status.py
│   ├── serve_reports.py
│   ├── frm_lines.py
│   ├── readable.py
│   ├── scan_control_chars.py
│   └── make_fixture.py
├── docs/
│   ├── README.md             # 本ディレクトリの索引
│   ├── vb6-not-vba.md        # VB6 ≠ VBA（公開）
│   ├── en/                   # 英語の公開ドキュメント
│   ├── assets/               # README 用画面（フィクスチャ）
│   ├── ai-onboarding.md      # AI 必読（AGENTS の次）
│   ├── kit-dev-context.md    # キット保守（消費者 ai-dev-context ではない）
│   ├── reimplementation-handoff.md
│   ├── methodology.md
│   ├── workflow.md
│   ├── adopting-in-a-project.md
│   ├── directory-layout.md
│   ├── encoding-cp932.md
│   ├── QUICKREF.md
│   ├── flow/_master.md
│   ├── templates/
│   └── reference/
├── .github/
│   ├── workflows/ci.yml
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODEOWNERS
└── .cursor/
    ├── rules/
    ├── skills/
    ├── commands/
    ├── hooks.json
    └── hooks/
```

書込してよい領域: `working/` · `tools/` · `docs/` · `schema/` · `.cursor/` · ルートの設定/入口ファイル。  
書込禁止: `protected_source_dirs` 配下。

定型入口（commands）: `/vb6-extract` · `/vb6-inventory` · `/frm-deep-read` · `/runtime-layout` · `/vb6-comprehend` · `/vb6-report` · `/vb6-verify-reports` · `/serve-reports` · `/kit-smoke`。  
CLI のみ: `python -m tools excerpt` · `python -m tools config-check`。  
ツール入口: `python -m tools <command>`（一覧は `python -m tools --help`）。
