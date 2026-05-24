"""
Auth 미들웨어 스켈레톤
현재: X-User-Id 헤더 패스스루 (개발/테스트용)
향후: Supabase JWT 검증으로 교체
"""
from fastapi import Request
import os

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")


def get_user_id(request: Request) -> str:
    """
    요청에서 user_id 추출.
    1. X-User-Id 헤더 (개발용)
    2. Authorization: Bearer <token> → JWT decode (Supabase Auth)
    3. IP 기반 익명 ID
    """
    # 개발/테스트: 헤더 직접 사용
    if user_id := request.headers.get("X-User-Id"):
        return user_id

    # TODO: Supabase JWT 검증
    # if auth := request.headers.get("Authorization"):
    #     token = auth.removeprefix("Bearer ").strip()
    #     try:
    #         import jwt
    #         payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
    #         return payload["sub"]
    #     except Exception as e:
    #         print(f"[auth] JWT 검증 실패: {e}")

    # 익명: IP 기반
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "anonymous")
    return f"anon:{ip}"
