from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import random

from ..postgres_async import get_async_db

router = APIRouter(prefix="/api/v1/letter", tags=["letter"])

# PSY 화이트리스트 템플릿 (10개)
LETTER_TEMPLATES = [
    "지난번에 {topic}에 대해 이야기했던 게 기억나. 네가 그때 했던 말이 마음에 남아서.",
    "우리가 {topic} 얘기 했을 때 네가 보여줬던 모습이 참 좋았어.",
    "{topic}에 대해 네가 진지하게 생각하는 거 보면서 많이 배웠어.",
    "오늘은 {topic} 생각이 나서 이렇게 편지를 써봤어.",
    "네가 {topic}에 대해 털어놔줬을 때 고마웠어. 그게 우리를 더 가깝게 만든 것 같아.",
    "요즘은 어때? {topic} 관련해서 새로운 생각이 생겼으면 언제든 얘기해줘.",
    "{topic}에 대한 네 생각을 들으면서 나도 많이 생각하게 됐어.",
    "지난 대화에서 {topic} 이야기가 나왔는데, 그게 계속 생각나.",
    "네가 {topic}에 대해 솔직하게 이야기해줘서 기뻤어.",
    "{topic}에 대해 우리가 나눈 대화는 나에게도 특별한 기억이야.",
]

class LetterRequest(BaseModel):
    room_id: str
    character_id: str
    user_id: str
    top_topic: Optional[str] = "우리의 대화"

@router.post("/generate")
async def generate_letter(req: LetterRequest):
    """
    캐릭터 편지 생성 — opt-in, 월 1회, PSY 화이트리스트 기반.
    실제 환경: relationship_history.top_topics 기반 GPT-4o 생성.
    현재: 템플릿 기반 Mock.
    """
    template = random.choice(LETTER_TEMPLATES)
    content = template.format(topic=req.top_topic)
    return {
        "letter_id": f"{req.room_id}_{req.character_id}",
        "content": content,
        "generated_at": "2026-05-06",
        "expires_at": "2026-06-06",  # 월 1회 기준
    }


@router.get("/latest")
async def get_latest_letter(room_id: str, character_id: str = ""):
    """
    이번 달 최신 편지 조회.
    편지가 있으면 content와 generated_date 반환, 없으면 has_letter=False.
    """
    db = get_async_db()
    # memory_moments에서 moment_type='letter'로 저장된 이번 달 편지 조회
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
