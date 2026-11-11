# Aha Benchmark 実行記録

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
