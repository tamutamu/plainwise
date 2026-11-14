# Aha Benchmark 実行記録

## 2026-11-12 夜：追加の整備

- Codex CLIの利用制限が依然継続していることを実行で再確認しました。新規の比較回答は生成されていません
- 16問を3種類のA/B比較票（各16問）に分配する、回答元を伏せた**人間向け評価票**とCSV記入欄を追加しました
- 記入結果について、実際の「なるほど」評価を出所別に集計するスクリプトを追加。重大な事実誤りのある説明を高評価であっても勝ちと数えないようにしました
- 盲検票の見出しからPlainwiseの名称を除去し、読み手への事前誘導を抑えました
- オフラインテストは**14件すべて合格**。コード・手順書を作業ブランチに保存しました
- Codex利用可能になる見込みの2026-11-13 13:25以降、**翌13:45（日本時間）に検証を再開する定期チェック**を設定しました。完成した場合のみ通知する設定です

**継続方針**：AIの利用枠が戻ったら固定の16問による同条件比較を実行します。実際の人間による評価を未実施のまま、あたかも「なるほど」という学習効果を実証したかのような完成宣言は行いません。

---

## 2026-11-12：再開

- Windowsの`zenn`ローカルMCP接続を再開し、`tamutamu/plainwise`の`redesign/aha-first-2026-11`を作業用ディレクトリにチェックアウト
- `python -m unittest evaluation.test_benchmark -v` を実行。合計4テスト成功
- `python evaluation/run_aha_benchmark.py --dry-run` 相当の実行により、16問×3回×3条件＝144出力の計画を確認
- Codex CLI（`gpt-5.6-sol`）の本番実行は**初回のAPI利用上限エラーで停止**。生成回答0件、比較結果0件
- Codexの応答で示された再試行可能日時：2026-11-13 13:25（表示された日時。環境のタイムゾーンに注意）
- Claude Code：ログイン情報は存在するが、組織側がClaude Codeのサブスクリプション利用を無効化しているため、推論に利用できず
- Gemini CLI：当該クライアントの利用資格エラー。OpenCodeの試行した無料モデルでもモデル利用エラー。**他モデルで成功した評価はない**

### コードに対する是正

最初のオフラインテストでは、ダミー問題の必須キー `accuracy_guard` が不足して失敗したため修正。さらに、生成が一度エラーになった場合でも、以前のランナーは次回その記録を「完了済み」として飛ばしてしまう不具合を発見し、修正しました。

現在は、前回の失敗がある場合は明示的に停止し、`--retry-failures` が指定された場合に限り、失敗履歴を残しつつ再試行します。モデル・スキル・設問・プロンプト・反復回数が異なる実行結果は同じ出力へ混ぜません。

修正後のオフラインテストはすべて成功しました。

### 再開方法

```bash
python -m unittest evaluation.test_benchmark -v
python evaluation/run_aha_benchmark.py --dry-run
python evaluation/run_aha_benchmark.py
python evaluation/make_blind_review.py
```

WindowsでCodex CLIがPATHから呼べない場合は、`evaluation/README.md` の`PLAINWISE_CODEX_CMD_JSON` を利用します。個別環境ではユーザー自身の利用枠と認証状態に従ってください。

**本記録は検証完了報告ではありません。** 生成回答も匿名評価も未実施のため、新版Plainwiseの品質が旧版や強い一般指示より良いかどうかは未判定です。利用制限が解除されるまでは、結果を創作して埋めません。


## 2026-11-14：144回答生成完了・盲検評価準備

- Windows `zenn` セッションの作業ブランチを `git pull --ff-only` で同期
- `python -m unittest evaluation.test_benchmark evaluation.test_reader_forms -v`：10件すべて成功
- `evaluation/results/aha_v1_raw.json` を確認。16問 × 3反復 × 3条件 = **144回答すべて生成済み**（各条件48回答）
- `exit_code != 0` は0件、空回答0件、ツール呼び出し0件、エラー文字列あり0件、失敗履歴0件
- 回答の平均文字数：baseline 188.9、strong_general_instruction 208.8、plainwise_candidate 207.7。長さが近いことは品質優位の証拠ではない
- `python _run_local.py` で再開・整合性確認。新たな推論を要求せず、完了した回答を維持
- `python evaluation/make_blind_review.py`：48組の3条件比較資料を生成
- `python evaluation/make_reader_forms.py`：2回答ずつの盲検比較フォームを3枚生成。設問ごとに3種類のペアを割り当てる。回答元を示すanswer-keyは別ファイル
- 原本・盲検資料はローカルの `evaluation/results/` に保持。個別回答には第三者による正確性検証・読者評価がまだ必要
- **未判定**：Plainwiseが強い一般指示より読者の理解・発見を改善するか。144回答の生成成功を「品質実証」と呼ばない
- 次工程：全回答の事実・計算・因果を `accuracy_guard` と照合し、盲検で読者評価を収集。強い一般指示との差が実証できない場合は改稿し、新規ホールドアウトで再評価する

