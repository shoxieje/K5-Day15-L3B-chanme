"""Bộ truy xuất từ khóa đơn giản cho Lab mẫu 2 — RAG có trích dẫn."""
import re


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9À-ỹ]+", text.lower()))


def retrieve_top_k(query: str, chunks: list[dict], k: int = 3) -> list[dict]:
    """Chấm điểm trùng từ khóa và trả về top-k đoạn có điểm > 0."""
    q_tokens = tokenize(query)
    scored = []
    for chunk in chunks:
        c_tokens = tokenize(chunk.get("text", ""))
        score = len(q_tokens & c_tokens)
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:k]]


def verify_citations(answer_citations: list[str], retrieved: list[dict]) -> list[str]:
    """Trả danh sách mã trích dẫn không nằm trong các đoạn đã truy xuất."""
    valid_ids = {f"{c['doc_id']}:{c['chunk_id']}" for c in retrieved}
    return [cid for cid in answer_citations if cid not in valid_ids]
