"""
Stripe 결제 연동 스켈레톤
설정: api/.env에 STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET 추가 후 활성화
"""
import os
from typing import Optional

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID_MONTHLY = os.getenv("STRIPE_PRICE_ID_MONTHLY", "")


def create_checkout_session(user_id: str, success_url: str, cancel_url: str) -> dict:
    """
    Stripe Checkout 세션 생성

    Returns:
        dict: {"session_id": "...", "url": "..."}

    Raises:
        RuntimeError: STRIPE_SECRET_KEY가 설정되지 않은 경우
    """
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

    if not STRIPE_PRICE_ID_MONTHLY:
        raise RuntimeError("STRIPE_PRICE_ID_MONTHLY 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

    # import stripe
    # stripe.api_key = STRIPE_SECRET_KEY
    # session = stripe.checkout.Session.create(
    #     payment_method_types=["card"],
    #     line_items=[{
    #         "price": STRIPE_PRICE_ID_MONTHLY,
    #         "quantity": 1,
    #     }],
    #     mode="subscription",
    #     customer_email=None,  # TODO: user_id로 Stripe Customer 조회
    #     metadata={"user_id": user_id},
    #     success_url=success_url,
    #     cancel_url=cancel_url,
    # )
    # return {
    #     "session_id": session.id,
    #     "url": session.url,
    # }

    raise NotImplementedError(
        "Stripe 키가 설정되지 않았습니다. "
        "STRIPE_SECRET_KEY와 STRIPE_PRICE_ID_MONTHLY를 .env에 추가한 후 "
        "이 함수의 주석 처리를 해제하세요."
    )


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """
    Stripe 웹훅 처리 (결제 완료 시 quota_type = 'premium' 업그레이드)

    Args:
        payload: 웹훅 페이로드
        sig_header: Stripe-Signature 헤더

    Returns:
        dict: {"ok": True, "event_type": "..."}

    Raises:
        RuntimeError: STRIPE_WEBHOOK_SECRET가 설정되지 않은 경우
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise RuntimeError("STRIPE_WEBHOOK_SECRET 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

    # import stripe
    # try:
    #     event = stripe.Webhook.construct_event(
    #         payload, sig_header, STRIPE_WEBHOOK_SECRET
    #     )
    # except ValueError as e:
    #     raise ValueError(f"Invalid payload: {e}")
    # except stripe.error.SignatureVerificationError as e:
    #     raise ValueError(f"Invalid signature: {e}")
    #
    # if event["type"] == "checkout.session.completed":
    #     session = event["data"]["object"]
    #     user_id = session["metadata"].get("user_id")
    #
    #     if user_id:
    #         from db import execute
    #         execute(
    #             """
    #             UPDATE stt_analysis.user_quota
    #             SET quota_type = 'premium', updated_at = NOW()
    #             WHERE user_id = %s
    #             """,
    #             (user_id,)
    #         )
    #
    # return {
    #     "ok": True,
    #     "event_type": event["type"],
    # }

    raise NotImplementedError(
        "Stripe 키가 설정되지 않았습니다. "
        "STRIPE_WEBHOOK_SECRET를 .env에 추가한 후 "
        "이 함수의 주석 처리를 해제하세요."
    )


def get_customer_id(user_id: str) -> Optional[str]:
    """
    user_id로부터 Stripe Customer ID 조회

    Args:
        user_id: 사용자 ID

    Returns:
        str: Stripe Customer ID 또는 None

    Note:
        Supabase 또는 별도 고객 테이블에서 stripe_customer_id를 저장하여 관리해야 함.
    """
    # TODO: DB에서 stripe_customer_id 조회
    # from db import query_one
    # row = query_one(
    #     "SELECT stripe_customer_id FROM stt_analysis.user_quota WHERE user_id = %s",
    #     (user_id,)
    # )
    # return row["stripe_customer_id"] if row else None

    raise NotImplementedError("Stripe Customer ID 조회 구현 필요")
