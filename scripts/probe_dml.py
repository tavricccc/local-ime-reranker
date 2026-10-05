import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper

root = Path("runtime/gpu-probe")
root.mkdir(parents=True, exist_ok=True)
graph = helper.make_graph([helper.make_node("MatMul", ["a", "b"], ["result"])], "gpu-matmul",
    [helper.make_tensor_value_info(n, TensorProto.FLOAT, [64, 64]) for n in ("a", "b")],
    [helper.make_tensor_value_info("result", TensorProto.FLOAT, [64, 64])])
model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], ir_version=10)
onnx.save(model, root / "matmul.onnx")
options = ort.SessionOptions()
options.enable_mem_pattern = False
options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
options.enable_profiling = True
options.profile_file_prefix = str(root / "ort-profile")
options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
session = ort.InferenceSession(str(root / "matmul.onnx"), options, providers=[("DmlExecutionProvider", {"device_id": 0})])
output = session.run(None, {"a": np.ones((64, 64), np.float32), "b": np.ones((64, 64), np.float32)})[0]
assert np.all(output == 64)
profile = Path(session.end_profiling())
events = json.loads(profile.read_text("utf-8"))
providers = [x["args"].get("provider") for x in events if "provider" in x.get("args", {})]
print(json.dumps({"onnxruntime": ort.__version__, "providers": session.get_providers(),
                  "executed_providers": providers, "matmul": float(output[0, 0])}, indent=2))
