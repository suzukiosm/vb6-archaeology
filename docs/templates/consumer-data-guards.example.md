# 消費者データ I/O ガード（hooks 例・プレースホルダ）

考古学キットの `protect_source` / `guard_shell` は **VB6 正本**を守る。  
再実装消費者では、加えて **本番データツリーへの試験書き**を hooks で抑止するのが実戦上ほぼ必須である。

本ファイルはサンプル。パス断片・環境変数名は必ず自リポの実名に置き換える。  
キット本体の hooks には組み込まない（消費者 `.cursor/hooks/` へコピーして改稿）。

---

## 方針（要約）

| 操作 | 既定 |
|---|---|
| 読取 | 本番パス可（調査・突合） |
| 書込 | **ミラー**（例: `working/data_mirror/`） |
| 本番書込 | 明示フラグ（例: 環境変数 `〈WRITE_MODE〉=production`）が無い限り deny |

詳細: [`../adopting-in-a-project.md`](../adopting-in-a-project.md)「データ I/O ミラー方針」。

---

## 例: beforeShellExecution / beforeSubmitPrompt で見る条件

疑似コード（言語は消費者 hooks に合わせる）:

```text
PRODUCTION_MARKERS = ["〈/path/to/production/data〉", "〈PROD_SHARE〉"]
MIRROR_ROOT = "working/data_mirror"
WRITE_MODE_ENV = "〈WRITE_MODE〉"   # 例: DELIVERY_WRITE_MODE

if tool is write-like AND path matches PRODUCTION_MARKERS:
    if env(WRITE_MODE_ENV) != "production":
        deny("production write blocked; use mirror or set WRITE_MODE=production")
    else:
        ask("explicit production write")
```

- マーカーはキットの `protected_path_markers` と同様、**パス区切りで分割した一致**が安全
- ミラーへの書込は allow（または ask を緩める）
- フラグ名もパスもリポにコミットしてよいが、実ホストの絶対パスをそのまま公開ドキュメントに書かない

---

## キットとの役割分担

| 層 | 守るもの |
|---|---|
| キット hooks | `protected_source_dirs` / `protected_path_markers`（VB6 正本） |
| 消費者 hooks（本例） | 本番業務データ・共有フォルダへの書込 |

両方必要。片方では足りない。
