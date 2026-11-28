"""Starter cho Lab mẫu 1 — ReAct Tool-Calling Agent."""
import json
import time
from tools import check_inventory, get_order_status

TOOLS = {
    "get_order_status": get_order_status,
    "check_inventory": check_inventory,
}


def run_react(question: str, call_llm, max_steps: int = 6) -> dict:
    """Chạy vòng lặp ReAct tối đa max_steps bước và trả về kết quả kèm trace."""
    trace = []
    history = [{"role": "user", "content": question}]
    for step in range(1, max_steps + 1):
        t0 = time.perf_counter()
        raw = call_llm(history)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            trace.append({"step": step, "error": f"invalid_json: {exc}"})
            history.append({"role": "user", "content": "Observation: JSON không hợp lệ, hãy trả lại đúng JSON."})
            continue
        if "final_answer" in parsed:
            trace.append({"step": step, "action": "final_answer", "latency_ms": round((time.perf_counter() - t0) * 1000)})
            return {"answer": parsed["final_answer"], "trace": trace}
        tool_name = parsed.get("action")
        fn = TOOLS.get(tool_name)
        if fn is None:
            trace.append({"step": step, "tool_name": tool_name, "error": "unknown_tool"})
            history.append({"role": "user", "content": f"Observation: không có công cụ {tool_name}."})
            continue
        result = fn(parsed.get("action_input", ""))
        trace.append({"step": step, "tool_name": tool_name, "latency_ms": round((time.perf_counter() - t0) * 1000)})
        history.append({"role": "user", "content": f"Observation: {result}"})
    return {"answer": "Dừng: vượt quá max_steps.", "trace": trace}
