"""LangGraph 기반 멀티스텝 에이전트"""
import os
from typing import List, Optional, Dict, Any
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.types import Send
from langchain.tools import tool
from langchain_core.messages import HumanMessage, AIMessage

from db import query
import embed
import llm_gateway


class AgentState(dict):
    pass


class GradeEnum(str, Enum):
    GOOD = "good"
    RETRY = "retry"


def _call_llm(prompt: str, model: str = "sonnet") -> str:
    """llm_gateway를 통한 Claude 호출 (Claude CLI 폴백 포함)"""
    result = llm_gateway.call_llm(
        task="당신은 영상 분석 어시스턴트입니다. 제공된 정보를 기반으로 정확하게 답변하세요.",
        text=prompt,
        model=model,
        timeout=60,
    )
    return result or "답변을 생성할 수 없습니다."


# --- Tools ---

@tool
def search_videos(
    query: str, channel: Optional[str] = None, top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    영상 의미론적 검색.

    Args:
        query: 검색 쿼리
        channel: 채널 필터 (옵션)
        top_k: 상위 K개 결과

    Returns:
        [{video_id, title, channel, score}]
    """
    if not query or not query.strip():
        return []

    query_embedding = embed.embed_text(query)

    sql = """
        SELECT
            t.video_id,
            v.title,
            v.channel,
            1 - (t.embedding <=> %s::vector) AS score
        FROM stt_analysis.transcripts t
        JOIN stt_analysis.videos v ON t.video_id = v.video_id
    """
    params = [str(query_embedding)]

    if channel:
        sql += " WHERE v.channel = %s"
        params.append(channel)
    else:
        sql += " WHERE 1=1"

    sql += " ORDER BY score DESC LIMIT %s"
    params.append(top_k)

    results = query(sql, tuple(params))
    return [dict(row) for row in results] if results else []


@tool
def get_transcript(video_id: str) -> str:
    """특정 영상의 전체 트랜스크립트 조회"""
    row = query(
        "SELECT full_text FROM stt_analysis.transcripts WHERE video_id = %s",
        (video_id,),
    )
    if row:
        return row[0].get("full_text", "")
    return ""


# --- Graph Nodes ---

def retrieve_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """검색 노드: 질문과 관련된 영상 찾기"""
    from rag_pipeline import semantic_search
    question = state.get("question", "")
    channel = state.get("channel")
    playlist_id = state.get("playlist_id")

    # 의미론적 검색 (rag_pipeline 직접 호출)
    search_results = semantic_search(question, top_k=10, channel=channel, playlist_id=playlist_id)

    if not search_results:
        state["retrieved_docs"] = []
        state["video_ids"] = []
    else:
        # 상위 5개 영상의 트랜스크립트 조회
        video_ids = [r["video_id"] for r in search_results[:5]]
        transcripts = []

        for vid in video_ids:
            text = get_transcript(vid)
            if text:
                transcripts.append({
                    "video_id": vid,
                    "title": next(
                        (r["title"] for r in search_results if r["video_id"] == vid),
                        vid,
                    ),
                    "content": text[:2000],  # 처음 2000글자만
                })

        state["retrieved_docs"] = transcripts
        state["video_ids"] = video_ids

    return state


def generate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """생성 노드: 검색 결과 기반 답변 생성"""
    question = state.get("question", "")
    retrieved_docs = state.get("retrieved_docs", [])

    if not retrieved_docs:
        state["answer"] = "관련 영상을 찾을 수 없습니다."
        return state

    # 컨텍스트 구성
    context = "\n\n".join(
        [f"[{doc['title']}]\n{doc['content']}" for doc in retrieved_docs]
    )

    prompt = f"""제공된 영상 스크립트를 기반으로 질문에 정확하게 답변하세요.

<context>
{context}
</context>

질문: {question}

답변:"""
    state["answer"] = _call_llm(prompt)
    state["generation_attempts"] = state.get("generation_attempts", 0) + 1

    return state


def grade_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """판정 노드: 답변 품질 평가"""
    question = state.get("question", "")
    answer = state.get("answer", "")
    generation_attempts = state.get("generation_attempts", 0)

    # 3회 이상 시도하면 강제 종료
    if generation_attempts >= 3:
        state["grade"] = GradeEnum.GOOD
        return state

    grade_prompt = f"""사용자 질문: {question}

생성된 답변: {answer}

위 답변이 질문에 충분히 잘 답변했는지 평가하세요.
응답은 다음 중 하나만: "good" 또는 "retry"

판정:"""
    grade_text = _call_llm(grade_prompt, model="haiku").strip().lower()

    if "retry" in grade_text or "부족" in grade_text:
        state["grade"] = GradeEnum.RETRY
    else:
        state["grade"] = GradeEnum.GOOD

    return state


# --- Graph 구성 ---

def build_agent_graph():
    """RAG 에이전트 그래프 구성"""
    workflow = StateGraph(dict)

    # 노드 추가
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("grade", grade_node)

    # 엣지 정의
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "grade")

    # 조건부 엣지: grade 결과에 따라 분기
    def route_grade(state: Dict[str, Any]) -> str:
        grade = state.get("grade")
        if grade == GradeEnum.RETRY:
            return "retrieve"
        return END

    workflow.add_conditional_edges("grade", route_grade)

    return workflow.compile()


def run_agent(
    question: str,
    channel: Optional[str] = None,
) -> Dict[str, Any]:
    """
    에이전트 실행.

    Args:
        question: 사용자 질문
        channel: 채널 필터 (옵션)

    Returns:
        {question, answer, video_ids, retrieved_docs}
    """
    graph = build_agent_graph()

    initial_state = {
        "question": question,
        "channel": channel,
        "retrieved_docs": [],
        "video_ids": [],
        "answer": "",
        "grade": None,
        "generation_attempts": 0,
    }

    # 그래프 실행
    result = graph.invoke(initial_state)

    return {
        "question": question,
        "answer": result.get("answer", ""),
        "video_ids": result.get("video_ids", []),
        "retrieved_docs": result.get("retrieved_docs", []),
    }
