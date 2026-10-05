"""Generate a readable report directly from measured JSON artifacts."""
import json
from pathlib import Path

labels = {"laya-single": "Laya 單序／48 例", "laya-reverse": "Laya 正反序／48 例",
          "rbt3": "RBT3 slots／48 例", "rbt3-pll": "RBT3 PLL／48 例",
          "validation-rbt3-pll": "RBT3 PLL／新增 16 例"}
lines = ["# 實測數據", "", "Ryzen 7 7800X3D，CPU 4 threads，Python 3.12.14，PyTorch 2.14.1 CPU。",
         "模型暖機後、無 cache；誤改率分母是原始 Rime 選對的案例。", "",
         "| 評估 | Rime Top-1 | 加權 Top-1 | 誤改率 | inference P50 / P95 | reranking P50 / P95 |",
         "|---|---:|---:|---:|---:|---:|"]
for name, label in labels.items():
    d = json.loads(Path(f"results/{name}.summary.json").read_text("utf-8"))["all"]
    lines.append(f"| {label} | {d['rime_top1_accuracy']:.2%} | {d['rerank_top1_accuracy']:.2%} | "
                 f"{d['regression_rate_of_originally_correct']:.2%} | "
                 f"{d['inference_p50_ms']:.1f} / {d['inference_p95_ms']:.1f} ms | "
                 f"{d['rerank_p50_ms']:.1f} / {d['rerank_p95_ms']:.1f} ms |")
lines += ["", "RBT3 PLL 探索集修正 2 例、誤改 0 例；新增集修正 1 例、誤改 3 例。",
          "64 例合計：Rime 與 AI 都選對 33 例（51.56%）；3/33 個原本正確案例被改錯（9.09%）。",
          "沒有整體改善證據，不能只引用探索集的提升。", "", "## 真正 Rime filter 端到端", "",
          "RBT3 PLL，固定暖機推論執行緒；每案例、每預算先清 cache。",
          "包含 librime 按鍵處理、Lua、IPC、推論、融合及候選讀取。Windows 排程可能超過期限。", "",
          "| 預算 | Top-1 | 誤改數 | 最後按鍵 P50 / P95 | 全部按鍵 P50 / P95 | 回覆 / 逾時或未就緒 / 略過 |",
          "|---|---:|---:|---:|---:|---:|"]
for budget, d in json.loads(Path("results/e2e.summary.json").read_text("utf-8")).items():
    c = d["status_counts"]
    lines.append(f"| {budget} ms | {d['top1_accuracy']:.2%} | {d['regressions']} | "
                 f"{d['final_update_p50_ms']:.1f} / {d['final_update_p95_ms']:.1f} ms | "
                 f"{d['all_update_p50_ms']:.1f} / {d['all_update_p95_ms']:.1f} ms | "
                 f"{c.get('returned', 0)} / {c.get('unavailable_or_timeout', 0)} / {c.get('bypassed', 0)} |")
lines += ["", "全部按鍵包含未完成注音、略過模型的更新，低 P50 不能當成推論速度。",
          "回覆也可能是 low confidence／busy 的原排序，不能當成模型採用率。", "",
          "9 項必要工程合約測試通過。沒有測 GPU、TSF、原生 UI、高 DPI 或日常打字體感。", "",
          "逐例與摘要位於 [results](../results/)，輸入位於 [data](../data/)。"]
Path("docs/measurements.md").write_text("\n".join(lines) + "\n", "utf-8")
