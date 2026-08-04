# ディレクトリレイアウト

```
vb6-archaeology/
├── AGENTS.md                 # AI 入口（短い）
├── README.md                 # 人間向け
├── CONTRIBUTING.md
├── SECURITY.md
├── CHANGELOG.md
├── LICENSE
├── archaeology.config.json   # 保護 dir・出力先
├── source/                   # 読取専用正本（既定）
│   ├── README.md
│   └── mini_vbp/             # スモーク用フィクスチャ
├── working/
│   ├── extracts/<stem>/      # 切り出し
│   ├── reports/              # 調査成果
│   └── skeletons/            # Form skeleton / runtime-layout.json
├── tools/
│   ├── README.md
│   ├── kit_smoke.py          # 自己点検（pipeline + unittest）
│   ├── lib/
│   │   ├── config.py
│   │   ├── vbparse.py
│   │   └── cache.py
│   ├── extract_vbp.py
│   ├── vb6_inventory.py
│   ├── verify_inventory.py
│   ├── verify_report_names.py
│   ├── frm_deep_read.py
│   ├── frm_deep_read_all.py
│   ├── runtime_layout.py
│   ├── frm_lines.py
│   ├── scan_control_chars.py
│   └── make_fixture.py
├── docs/
│   ├── README.md             # 本ディレクトリの索引
│   ├── ai-onboarding.md      # AI 必読（AGENTS の次）
│   ├── kit-dev-context.md    # キット保守（消費者 ai-dev-context ではない）
│   ├── methodology.md
│   ├── workflow.md
│   ├── adopting-in-a-project.md
│   ├── directory-layout.md
│   ├── encoding-cp932.md
│   ├── flow/_master.md
│   ├── templates/
│   └── reference/
├── .github/workflows/ci.yml
└── .cursor/
    ├── rules/
    ├── skills/
    ├── commands/
    ├── hooks.json
    └── hooks/
```

書込してよい領域: `working/` · `tools/` · `docs/` · `.cursor/` · ルートの設定/入口ファイル。  
書込禁止: `protected_source_dirs` 配下。

定型入口（commands）: `/vb6-extract` · `/vb6-inventory` · `/frm-deep-read` · `/vb6-comprehend` · `/vb6-report` · `/vb6-verify-reports` · `/serve-reports` · `/kit-smoke`。
