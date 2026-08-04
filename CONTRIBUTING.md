# Contributing

本リポジトリは source-available です。利用・複製・改変・再配布・組込の前に [LICENSE](LICENSE) に従い許諾を得てください。

## 不変条件

- `archaeology.config.json` の `protected_source_dirs`（キット既定 `source/`）へは書込・移動・改名・削除禁止
- フィクスチャ再生成のみ例外: `python tools/make_fixture.py`
- 使い捨て `working/_*.py` を増やさず、足りない抽出・検証は `tools/` を改定する
- 推定（役割・呼び出し・業務意味）は証拠必須。正規表現一括の callgraph は作らない

## 開発環境

- Python **3.10+**（標準ライブラリのみ。追加 pip 依存なし）
- Windows / Linux いずれも可。ローカル手順の例は PowerShell 表記

## 検証

変更後は次を緑にしてください。

```powershell
python tools/kit_smoke.py
```

（フィクスチャパイプライン + `tools/` 配下の unittest。CI も同じ入口です。）

## 変更の置き場

| 領域 | 規則 |
|---|---|
| `tools/` · `docs/` · `.cursor/` · ルート入口 | キット改良の主戦場 |
| `working/` | スモーク成果。コミットしない |
| `source/` | 読取専用（上記例外のみ） |

ドキュメントを変えたら、関連する `AGENTS.md` / `docs/` / `tools/README.md` / commands を矛盾なく同期してください。

## エージェント向け

1. `AGENTS.md` → `docs/ai-onboarding.md` を Read
2. 定型作業は `/vb6-extract` 等の commands、または対応 skill から入る
3. キット保守メモは `docs/kit-dev-context.md`
