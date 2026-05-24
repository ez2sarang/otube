"""sentence-transformers 기반 임베딩 서비스"""
from typing import List
import os

# Lazy load: 첫 호출 시만 모델 로드
_model = None

def get_model():
    """multilingual-e5-small 모델 lazy load"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")
        print(f"[embed] Loading model: {model_name}")
        _model = SentenceTransformer(model_name)
    return _model


def embed_text(text: str) -> List[float]:
    """
    단일 텍스트 임베딩.
    multilingual-e5는 검색 쿼리에 "query: " prefix 필요.
    """
    if not text or not text.strip():
        return [0.0] * 384

    model = get_model()
    prefix = "query: "
    embeddings = model.encode([prefix + text], convert_to_numpy=False)
    return embeddings[0].tolist()


def embed_batch(texts: List[str], is_query: bool = False) -> List[List[float]]:
    """
    배치 임베딩.

    Args:
        texts: 임베딩할 텍스트 리스트
        is_query: True면 "query: " prefix, False면 "passage: " prefix
    """
    if not texts:
        return []

    model = get_model()
    prefix = "query: " if is_query else "passage: "

    # 빈 텍스트 필터링 및 prefix 추가
    prefixed = []
    valid_indices = []
    for i, text in enumerate(texts):
        if text and text.strip():
            prefixed.append(prefix + text)
            valid_indices.append(i)
        else:
            valid_indices.append(None)

    if not prefixed:
        return [[0.0] * 384 for _ in texts]

    # 배치 임베딩
    embeddings = model.encode(prefixed, convert_to_numpy=False)

    # 결과를 원래 순서대로 복원
    result = []
    embed_idx = 0
    for i in range(len(texts)):
        if valid_indices[i] is not None:
            result.append(embeddings[embed_idx].tolist())
            embed_idx += 1
        else:
            result.append([0.0] * 384)

    return result
