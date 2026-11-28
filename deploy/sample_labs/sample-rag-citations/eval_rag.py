"""Đo Recall@k trên tập câu hỏi chuẩn."""
from retriever import retrieve_top_k


def evaluate_recall_at_k(eval_set: list[dict], chunks: list[dict], k: int = 3) -> float:
    """Tính tỉ lệ câu hỏi tìm đúng đoạn nguồn chuẩn trong top-k."""
    if not eval_set:
        return 0.0
    hits = 0
    for row in eval_set:
        top_k = retrieve_top_k(row["question"], chunks, k=k)
        got = {f"{c['doc_id']}:{c['chunk_id']}" for c in top_k}
        if row["expected_chunk"] in got:
            hits += 1
    return hits / len(eval_set)
