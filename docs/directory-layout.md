# ディレクトリレイアウト

```
vb6-archaeology/
├── AGENTS.md                 # AI 入口（短い）
├── README.md                 # 人間向け
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
│   ├── lib/config.py
│   ├── extract_vbp.py
│   ├── vb6_inventory.py
│   ├── verify_inventory.py
│   ├── frm_deep_read.py
│   ├── runtime_layout.py
│   └── make_fixture.py
├── docs/
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
└── .cursor/
    ├── rules/
    ├── skills/
    ├── commands/
    ├── hooks.json
    └── hooks/
```

書込してよい領域: `working/` · `tools/` · `docs/` · `.cursor/` · ルートの設定/入口ファイル。  
書込禁止: `protected_source_dirs` 配下。
