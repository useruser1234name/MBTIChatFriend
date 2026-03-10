"""이미지 생성 + Firebase Storage 업로드 서비스"""

import asyncio
import base64
import logging
import uuid
from io import BytesIO
from typing import Optional

from openai import AsyncOpenAI

from .config import OPENAI_API_KEY, FIREBASE_STORAGE_BUCKET

logger = logging.getLogger(__name__)

# Firebase Storage (선택적)
_storage_bucket = None

try:
    import firebase_admin
    from firebase_admin import storage as fb_storage

    _firebase_storage_available = True
except ImportError:
    _firebase_storage_available = False
    logger.warning("firebase-admin not installed, Storage features disabled")


def init_storage():
    """Firebase Storage 버킷 초기화. firebase_service.init_firebase() 이후 호출."""
    global _storage_bucket
    if not _firebase_storage_available:
        return
    if not FIREBASE_STORAGE_BUCKET:
        logger.info("FIREBASE_STORAGE_BUCKET not set, Storage disabled")
        return
    try:
        _storage_bucket = fb_storage.bucket(FIREBASE_STORAGE_BUCKET)
        logger.info(f"Firebase Storage bucket initialized: {FIREBASE_STORAGE_BUCKET}")
    except Exception as e:
        logger.warning(f"Firebase Storage init failed: {e}")


# ── 표정/오버레이 프롬프트 ──

EMOTION_PROMPTS = {
    "neutral": "calm, relaxed, neutral expression",
    "happy": "very happy, bright smile, joyful",
    "sad": "sad, tearful eyes, melancholy expression",
    "angry": "angry, furrowed brows, irritated",
    "shy": "shy, blushing, looking away slightly",
    "surprised": "surprised, wide eyes, open mouth slightly",
    "love": "loving, heart eyes, deeply affectionate",
    "playful": "playful, winking, mischievous smile",
    "worried": "worried, anxious, biting lip",
    "touched": "deeply moved, teary-eyed, grateful smile",
}

OVERLAY_PROMPTS = {
    "eyes_half_closed": "same face, eyes half closed, drowsy look",
    "eyes_closed": "same face, eyes completely closed, peaceful",
    "mouth_small": "same face, mouth slightly open, speaking softly",
    "mouth_medium": "same face, mouth moderately open, speaking normally",
    "mouth_open": "same face, mouth wide open, talking loudly or laughing",
}

# ── 진행 중인 표정 세트 작업 ──

_tasks: dict[str, dict] = {}


def _upload_to_storage(data: bytes, path: str, content_type: str = "image/png") -> str:
    """Firebase Storage에 바이트 업로드 후 공개 URL 반환."""
    if not _storage_bucket:
        raise RuntimeError("Firebase Storage not initialized")

    blob = _storage_bucket.blob(path)
    blob.upload_from_string(data, content_type=content_type)
    blob.make_public()
    return blob.public_url


async def generate_single_image(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "standard",
) -> tuple[bytes, Optional[str]]:
    """gpt-image-1으로 이미지 1장 생성, (bytes, revised_prompt) 반환."""
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
        response_format="b64_json",
    )
    image_data = response.data[0]

    # gpt-image-1은 b64_json 형식으로 반환
    if hasattr(image_data, "b64_json") and image_data.b64_json:
        img_bytes = base64.b64decode(image_data.b64_json)
    elif hasattr(image_data, "url") and image_data.url:
        # URL인 경우 다운로드
        import httpx
        async with httpx.AsyncClient() as http:
            resp = await http.get(image_data.url)
            resp.raise_for_status()
            img_bytes = resp.content
    else:
        raise ValueError("No image data returned from API")

    revised = getattr(image_data, "revised_prompt", None)
    return img_bytes, revised


async def generate_and_upload_base(
    prompt: str,
    character_id: str,
    size: str = "1024x1024",
    quality: str = "standard",
) -> tuple[str, Optional[str]]:
    """기본 이미지 생성 → Firebase Storage 업로드 → (url, revised_prompt)."""
    img_bytes, revised = await generate_single_image(prompt, size, quality)
    path = f"characters/{character_id}/base.png"
    url = _upload_to_storage(img_bytes, path)
    return url, revised


async def _generate_expression(
    base_prompt: str,
    expression_key: str,
    expression_desc: str,
    character_id: str,
    size: str,
) -> tuple[str, str]:
    """표정 하나 생성 → 업로드 → (key, url)."""
    is_overlay = expression_key in OVERLAY_PROMPTS
    if is_overlay:
        prompt = (
            f"Same character as described: {base_prompt}. "
            f"Extreme close-up of face only. {expression_desc}. "
            f"Same art style, same colors, same lighting, clean background."
        )
    else:
        prompt = (
            f"Same character as described: {base_prompt}. "
            f"Expression: {expression_desc}. "
            f"Same art style, same angle, same lighting, same background."
        )

    img_bytes, _ = await generate_single_image(prompt, size, quality="standard")

    if is_overlay:
        path = f"characters/{character_id}/overlays/{expression_key}.png"
    else:
        path = f"characters/{character_id}/expressions/{expression_key}.png"

    url = _upload_to_storage(img_bytes, path)
    return expression_key, url


async def generate_expression_set(task_id: str, base_prompt: str, character_id: str, size: str):
    """표정 세트 15장을 배치로 생성 (5개씩 병렬)."""
    all_expressions = {**EMOTION_PROMPTS, **OVERLAY_PROMPTS}
    keys = list(all_expressions.keys())
    total = len(keys)

    _tasks[task_id] = {
        "status": "processing",
        "completed": 0,
        "total": total,
        "urls": {},
    }

    try:
        # 5개씩 배치 (API rate limit 고려)
        batch_size = 5
        for i in range(0, total, batch_size):
            batch_keys = keys[i : i + batch_size]
            coros = [
                _generate_expression(
                    base_prompt=base_prompt,
                    expression_key=k,
                    expression_desc=all_expressions[k],
                    character_id=character_id,
                    size=size,
                )
                for k in batch_keys
            ]
            results = await asyncio.gather(*coros, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"Expression generation failed: {r}")
                    continue
                key, url = r
                _tasks[task_id]["urls"][key] = url
                _tasks[task_id]["completed"] += 1

        _tasks[task_id]["status"] = "completed"
        logger.info(
            f"Expression set completed for {character_id}: "
            f"{_tasks[task_id]['completed']}/{total}"
        )
    except Exception as e:
        logger.error(f"Expression set generation failed: {e}")
        _tasks[task_id]["status"] = "failed"


def start_expression_set_task(base_prompt: str, character_id: str, size: str = "1024x1024") -> str:
    """표정 세트 생성 백그라운드 작업 시작. task_id 반환."""
    task_id = str(uuid.uuid4())
    asyncio.create_task(generate_expression_set(task_id, base_prompt, character_id, size))
    return task_id


def get_task_status(task_id: str) -> Optional[dict]:
    """작업 진행 상황 조회."""
    return _tasks.get(task_id)
