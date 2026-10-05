"""Rebuild the report from actual benchmark artifacts, without running models."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / f"results/{name}.summary.json").read_text("utf-8"))["all"]


def table_row(label, data):
    return (f"| {label} | {data['rime_top1_accuracy']:.2%} | {data['rerank_top1_accuracy']:.2%} | "
            f"{data['regression_rate_of_originally_correct']:.2%} ({data['regressions_count']}) | "
            f"{data['inference_p50_ms']:.1f} / {data['inference_p95_ms']:.1f} ms | "
            f"{data['rerank_p50_ms']:.1f} / {data['rerank_p95_ms']:.1f} ms |")


models = {
    "laya-cpu": "Laya multilingual 322M",
    "rbt3-slots-cpu": "RBT3 slots（中文 MLM，非 decision model）",
    "rbt3-pll-cpu": "RBT3 PLL",
    "julia-cpu": "Julia 1 144M",
    "verdict-cpu": "Verdict / OpenJev 151M",
    "nanojev-cpu": "NanoJev 0.6B（unified games）",
    "qwen-cpu": "Qwen3 0.6B（AnyJev-style raw next-token）",
}
header = ["| 版本 | Rime Top-1 | 融合後 Top-1 | 誤改率（例數） | inference P50 / P95 | reranking P50 / P95 |",
          "|---|---:|---:|---:|---:|---:|"]
lines = ["# 本地模型續測與 Rime 原句對照", "", "2026-10-05，Ryzen 7 7800X3D、CPU 4 threads、FP32、Python 3.12.14、PyTorch 2.14.1+cpu。",
         "載入及前三次暖機不計，模型量測無 cache、逐個模型跑。誤改率分母是 Rime 原本正確的案例。",
         "人工同音字 challenge set 不能代表日常輸入準確率；所有候選及 quality 都由真正 librime 取得。", "",
         "## 同一批 64 例的模型比較", "", *header]
lines += [table_row(label, read(name)) for name, label in models.items()]
lines += ["", "這批是前兩輪的 48 + 16 例，已屬探索資料。63/64 個目標出現在 Top-8。",
          "RBT3 slots 有 2 例無法處理 tokenizer 不支援的候選，直接保留原排序；summary 另列 model_errors，失敗不算成功推論 latency。",
          "其他六列沒有模型錯誤。NanoJev 的候選逐路徑編碼無自回歸生成；CPU 路線仍很慢，且公開權重主要訓練遊戲動作。",
          "Qwen 只做一次 prefill、取候選字母的 logits，decode_steps=0；沒有使用 AnyJev 的 L1/L2 校準或蒸餾頭。", "",
          "## 新增 32 例：完整上下文是否有效", "", *header,
          table_row("Julia：完整前文＋候選續文", read("julia-holdout-cpu")),
          table_row("Julia：僅最後子句＋候選續文", read("julia-holdout-clause-cpu")), "",
          "這批在選定 Julia 與固定融合 policy 後才首次評估，包含 8 組新同音詞、6 組相同末句但不同前文的對照、4 個長續文。",
          "完整前文修正 4 例、誤改 0/16。這不代表一般使用時誤改率為零。",
          "6 組遠距上下文對照中，完整前文有 3 組兩邊都選對；只留相同末句時無法辨別兩邊。",
          "Rime 未提供「處理這些公事」「修改這段程式」作為同範圍候選，重排無法補出缺少的句子；長候選仍受原始候選供給限制。",
          "「復議／複議」字形在第一次模型評估前列為同義答案，不用模型結果改標籤。", "",
          "## 把 Rime 原本判斷明示給模型", "",
          "三種模式都先用 Rime 真正轉出的中文候選，模型不從注音生成新詞。",
          "semantic：完整前文放 shared state，每個選項是把 Rime 候選換進當前子句的中文續文；原句也在其中，模型評分後再融合原排名及 quality。",
          "rime-sentence：另外把 Rime Top-1 組成的中文子句明標為 rime_original_sentence，提醒它可能有同音誤選。",
          "rime-aware：再提供原始候選文字、original_rank、quality，並指示只有前文支持時才修正。它的 cache 也含 quality/rank，詞庫分數變化會重新推論。",
          "具體請求見 [rime-aware-request.json](../examples/rime-aware-request.json)。這版是目前 segment 與已提交前文的續文比較，尚不是任意整句逐位置替換、雙字修正或讀取 TSF surrounding text。", "",
          *header,
          table_row("Julia／64：semantic", read("julia-cpu")),
          table_row("Julia／64：rime-sentence", read("julia-rime-sentence-cpu")),
          table_row("Julia／64：rime-aware", read("julia-rime-aware-cpu")),
          table_row("Qwen／64：semantic", read("qwen-cpu")),
          table_row("Qwen／64：rime-aware", read("qwen-rime-aware-cpu")),
          table_row("Julia／32：semantic", read("julia-holdout-cpu")),
          table_row("Julia／32：rime-sentence", read("julia-rime-sentence-holdout-cpu")),
          table_row("Julia／32：rime-aware", read("julia-rime-aware-holdout-cpu")), "",
          "這些具體 prompt 的明示原句版本沒有超過 semantic；rime-aware 尤其傾向保留原排序。",
          "因為提示與輸入長度同時改變，不能據此斷言所有明示先驗的設計都不適合。沒有根據這批結果調低信心門檻。",
          "[Jevboard 原始設計](https://github.com/AsheeHuang/Jevboard/blob/1980e994b5cffaa00e0477cb7b4a68881ef604d8/docs/prompt-design.md)也記錄了 shared state 明放原句的定錨問題，改以候選整句比較。", "",
          "## 真正 Rime filter 端到端", "",
          "Julia semantic；每個案例與等待預算先清 semantic cache。計時包括 librime 按鍵、Lua、IPC、模型、融合及候選讀取。",
          "未完成注音時直接略過 AI，不能拿全部按鍵的低 P50 當成模型速度。returned 可包含原排序，不等於 AI 採用。", "",
          "| 資料／預算 | Top-1 | 誤改數 | 最後按鍵 P50 / P95 | 回覆 / 逾時或未就緒 / 略過 |",
          "|---|---:|---:|---:|---:|"]
for name, label in [("julia-e2e-comparison", "64 例"), ("julia-e2e-comparison-120", "64 例"),
                    ("julia-e2e-holdout", "新 32 例")]:
    for budget, data in json.loads((ROOT / f"results/{name}.summary.json").read_text("utf-8")).items():
        counts = data["status_counts"]
        lines.append(f"| {label}／{budget} ms | {data['top1_accuracy']:.2%} | {data['regressions']} | "
                     f"{data['final_update_p50_ms']:.1f} / {data['final_update_p95_ms']:.1f} ms | "
                     f"{counts.get('returned', 0)} / {counts.get('unavailable_or_timeout', 0)} / {counts.get('bypassed', 0)} |")
lines += ["", "80 ms 已提供這輪的實驗改善，120 ms 沒有額外的淨準確率提升；保留 80 ms 作為原 filter 預算。",
          "64 + 32 合計，Rime 49/96（51.04%），Julia semantic 57/96（59.38%），修正 11 例、誤改 3/49（6.12%）。",
          "已有小樣本的上下文改善證據；尚不足以啟用為日常輸入法，也未驗證候選窗 UI、高 DPI 或打字體感。", "",
          "## 資料與可重現性", "",
          "續測途中發現舊 validation_snapshots.json 的 16 例 code 是鍵碼；已 migrate 為 preedit 注音，原鍵碼保存在 keys。",
          "上述 64 例的所有模型表格已統一重跑；舊進度訊息中 Julia 64 例 60.94% 的數字作廢。正確的新 32 例與原有 MLM 比較不受此欄位修正影響。",
          "評估入口現在要求 code == preedit。模型 payload 不含 expected、split 或 gold label。",
          "11 項必要合約測試通過；另驗證 Rime-aware 真模型 service + 原生 filter 可以完成請求。",
          "GPU 嘗試及限制見 [研究報告](research.md#gpu-續測與-cpu-優先)。模型、source、license 與 revision 固定在 assets.lock.json。", "",
          "重跑：`pwsh -File scripts/compare-models.ps1`，報表再生成：`.venv/Scripts/python.exe scripts/generate_comparison.py`。",
          "先停止模型服務，避免測試時 CPU 競爭。所有逐例分數與 timing 位於 results/*.rows.json。"]
(ROOT / "docs/model-comparison.md").write_text("\n".join(lines) + "\n", "utf-8")
manifest = {"models": json.loads((ROOT / "assets.lock.json").read_text("utf-8"))["models"],
            "sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                       for name in ("data/comparison_snapshots.json", "data/holdout_snapshots.json", "requirements-lock.txt")}}
(ROOT / "results/comparison-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")
