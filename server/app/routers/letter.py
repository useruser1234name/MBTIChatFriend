import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth_middleware import require_auth_always
from ..config import OPENAI_API_KEY, LLM_MODEL_BASE
from ..postgres_async import get_async_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/letter", tags=["letter"])


class LetterRequest(BaseModel):
    room_id: str
    character_id: str
    user_id: str
    top_topic: Optional[str] = "우리의 대화"


@router.post("/generate")
async def generate_letter(
    req: LetterRequest,
    user: dict = Depends(require_auth_always),
):
    """
    캐릭터 편지 생성 — opt-in, 월 1회, relationship_history.top_topics 기반 gpt-4.1 생성.

    월 1회 중복 방지: memory_moments 테이블의 moment_type='letter' 레코드로 판정.
    """
    db = get_async_db()

    # ── 월 1회 중복 방지 ──────────────────────────────────────────────────────
    if db.available:
        existing = await db.fetchrow(
            """
            SELECT id FROM memory_moments
            WHERE room_id = $1
              AND ($2 = '' OR character_id = $2)
              AND moment_type = 'letter'
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            LIMIT 1
            """,
            req.room_id,
            req.character_id,
        )
        if existing:
            raise HTTPException(
                status_code=429,
                detail="이번 달 편지는 이미 생성되었습니다.",
            )

    # ── top_topics 조회 (diary_entries 기반) ──────────────────────────────────
    top_topics: list[str] = []
    if db.available:
        diary_rows = await db.fetchall(
            """
            SELECT diary_text
            FROM diary_entries
            WHERE room_id = $1
              AND ($2 = '' OR character_id = $2)
            ORDER BY created_at DESC
            LIMIT 20
            """,
            req.room_id,
            req.character_id,
        )
        import re
        from collections import Counter

        def _extract_nouns(text: str) -> list[str]:
            ko_tokens = re.findall(r"[가-힣]{2,}", text)
            stopwords = {
                "그게", "이게", "저게", "것도", "거야", "거지", "있어", "없어",
                "하면", "하고", "그냥", "아니", "맞아", "정말", "너무", "진짜",
            }
            return [t for t in ko_tokens if t not in stopwords]

        all_tokens: list[str] = []
        for row in diary_rows:
            text = row.get("diary_text") or ""
            all_tokens.extend(_extract_nouns(text))
        top_topics = [word for word, _ in Counter(all_tokens).most_common(5)]

    topics_text = ", ".join(top_topics) if top_topics else (req.top_topic or "우리의 대화")

    # ── gpt-4.1 편지 생성 ────────────────────────────────────────────────────
    content = await _generate_letter_llm(topics_text, req.character_id)

    today = datetime.date.today()

    # ── memory_moments에 저장 (DB 사용 가능한 경우) ──────────────────────────
    if db.available:
        try:
            await db.execute(
                """
                INSERT INTO memory_moments (room_id, character_id, moment_type, message_text, user_note)
                VALUES ($1, $2, 'letter', $3, $4)
                """,
                req.room_id,
                req.character_id,
                content,
                topics_text,
            )
        except Exception as e:
            logger.warning(f"[letter] memory_moments 저장 실패 (무시): {e}")

    return {
        "letter_id": f"{req.room_id}_{req.character_id}",
        "content": content,
        "generated_at": today.isoformat(),
        "expires_at": (today + datetime.timedelta(days=30)).isoformat(),
    }


async def _generate_letter_llm(topics_text: str, character_id: str) -> str:
    """top_topics를 기반으로 gpt-4.1 편지 생성. 실패 시 기본 문구 반환."""
    if not OPENAI_API_KEY:
        logger.warning("[letter] OPENAI_API_KEY 미설정 — 기본 편지 반환")
        return f"{topics_text}에 대한 이야기를 나눴던 시간이 정말 좋았어. 또 이야기하자."

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    system_prompt = (
        "너는 사용자와 친밀한 관계를 쌓아온 AI 친구야. "
        "사용자에게 따뜻하고 진심 어린 편지를 한국어로 써줘. "
        "형식: 2~3문단, 100~150자. "
        "어투는 친근하고 자연스럽게. "
        "편지는 '안녕'으로 시작하지 말고, 대화 주제에서 자연스럽게 시작해."
    )
    user_prompt = (
        f"우리가 자주 이야기한 주제는 '{topics_text}'야. "
        "이 주제들을 자연스럽게 녹여서 진심 어린 편지를 써줘."
    )

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL_BASE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=300,
            temperature=0.85,
        )
        letter_text = response.choices[0].message.content or ""
        return letter_text.strip()
    except Exception as e:
        logger.error(f"[letter] LLM 호출 실패: {e}")
        return f"{topics_text}에 대한 우리의 대화가 늘 마음에 남아. 또 이야기하자."


@router.get("/latest")
async def get_latest_letter(room_id: str, character_id: str = ""):
    """
    이번 달 최신 편지 조회.
    편지가 있으면 content와 generated_date 반환, 없으면 has_letter=False.
    """
    db = get_async_db()
    row = await db.fetchone(
        """
        SELECT message_text, user_note, created_at
        FROM memory_moments
        WHERE room_id = $1
          AND ($2 = '' OR character_id = $2)
          AND moment_type = 'letter'
          AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
        ORDER BY created_at DESC
        LIMIT 1
        """,
        room_id,
        character_id,
    )
    if not row:
        return {"has_letter": False, "content": "", "generated_date": ""}

    created_at = row.get("created_at")
    date_str = created_at.date().isoformat() if created_at else ""
    return {
        "has_letter": True,
        "content": row.get("message_text", ""),
        "generated_date": date_str,
    }
