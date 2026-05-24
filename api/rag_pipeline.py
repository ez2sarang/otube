"""LangChain LCEL 기반 RAG 파이프라인"""
import os
from typing import List, Optional, Dict, Any
from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

import embed
from db import query, query_one

# LLM 클라이언트 (lazy init)
_llm = None


def get_llm():
    """Claude Anthropic LLM 클라이언트 lazy load"""
    global _llm
    if _llm is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        _llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", api_key=api_key)
    return _llm


def semantic_search(
    query_text: str,
    top_k: int = 5,
    channel: Optional[str] = None,
    playlist_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    pgvector로 의미론적 검색.

    Args:
        query_text: 검색 쿼리
        top_k: 상위 K개 결과
        channel: 채널 필터 (옵션)
        playlist_id: 플레이리스트 필터 (옵션)

    Returns:
        [{video_id, title, channel, score, snippet}]
    """
    if not query_text or not query_text.strip():
        return []

    # 쿼리 임베딩 (query: prefix)
    query_embedding = embed.embed_text(query_text)

    # pgvector 검색 (cosine 유사도)
    sql = """
        SELECT
            t.video_id,
            v.title,
            v.channel,
            1 - (t.embedding <=> %s::vector) AS score,
            SUBSTRING(t.full_text, 1, 200) AS snippet
        FROM stt_analysis.transcripts t
        JOIN stt_analysis.videos v ON t.video_id = v.video_id
    """
    params = [str(query_embedding)]  # pgvector는 string으로 변환 필요

    # 채널 필터
    if channel:
        sql += " WHERE v.channel = %s"
        params.append(channel)
    else:
        sql += " WHERE 1=1"

    # 플레이리스트 필터
    if playlist_id:
        sql += """
            AND t.video_id IN (
                SELECT video_id FROM stt_analysis.video_playlists
                WHERE playlist_id = %s
            )
        """
        params.append(playlist_id)

    sql += " ORDER BY score DESC LIMIT %s"
    params.append(top_k)

    results = query(sql, tuple(params))
    return [dict(row) for row in results] if results else []


def rag_answer(
    question: str,
    video_ids: List[str],
    history: Optional[List[Dict]] = None,
) -> str:
    """
    RAG 답변 생성.

    Args:
        question: 사용자 질문
        video_ids: 검색할 영상 ID 리스트
        history: 대화 이력 (옵션, [{role, content}])

    Returns:
        Claude 답변 텍스트
    """
    if not video_ids or not question:
        return "영상이나 질문이 없습니다."

    # video_ids의 transcripts 조회
    placeholders = ", ".join(["%s"] * len(video_ids))
    rows = query(
        f"""
        SELECT t.video_id, v.title, t.full_text
        FROM stt_analysis.transcripts t
        JOIN stt_analysis.videos v ON t.video_id = v.video_id
        WHERE t.video_id IN ({placeholders})
        """,
        tuple(video_ids),
    )

    if not rows:
        return "해당 영상의 스크립트를 찾을 수 없습니다."

    # 컨텍스트 구성
    context_parts = []
    for row in rows:
        context_parts.append(
            f"[{row['title']}]\n{row['full_text'][:1000]}..."
            if len(row["full_text"]) > 1000
            else f"[{row['title']}]\n{row['full_text']}"
        )
    context = "\n\n".join(context_parts)

    # RAG 프롬프트
    rag_prompt = ChatPromptTemplate.from_template(
        """당신은 영상 분석 어시스턴트입니다.
제공된 영상 스크립트를 기반으로 사용자의 질문에 정확하게 답변하세요.

<context>
{context}
</context>

질문: {question}

답변:"""
    )

    # LCEL 체인 구성
    chain = (
        {"context": RunnablePassthrough(), "question": RunnablePassthrough()}
        | rag_prompt
        | get_llm()
        | StrOutputParser()
    )

    # 답변 생성 (context와 question을 분리하여 전달)
    answer = chain.invoke({"context": context, "question": question})
    return answer


def extract_qa_pair(answer_text: str, question: str) -> Dict[str, str]:
    """답변과 질문을 Q&A 페어로 정리"""
    return {
        "question": question,
        "answer": answer_text,
        "created_at": datetime.utcnow().isoformat(),
    }
