"""합성 학습 데이터 생성 CLI - 파인튜닝용 고품질 MBTI 대화 데이터 생성.

사용법:
    python generate_synthetic_data.py --mbti INTJ --affinity 3 --count 50 --output synthetic_intj.jsonl
    python generate_synthetic_data.py --all --count-per-combo 10
"""

import argparse
import asyncio
import json
import logging
import random
import sys
from pathlib import Path
from typing import List, Optional

from openai import AsyncOpenAI

# 프로젝트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import OPENAI_API_KEY
from app.prompts import (
    MBTI_PERSONALITIES,
    AFFINITY_BEHAVIORS,
    build_system_prompt,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

ALL_MBTI = list(MBTI_PERSONALITIES.keys())

# ── 시나리오 템플릿 ──────────────────────────────────────────────

SCENARIO_TEMPLATES = {
    "daily": [
        "평범한 하루에 대한 일상 대화",
        "날씨, 음식, 취미에 대한 가벼운 수다",
        "주말 계획에 대한 이야기",
        "최근 본 영화나 드라마에 대한 감상",
        "오늘 있었던 재미있는 일",
    ],
    "emotional": [
        "사용자가 직장/학교에서 스트레스를 받아 힘들어하는 상황",
        "사용자가 좋은 일이 있어서 기뻐하는 상황",
        "사용자가 외로움을 느끼고 있는 상황",
        "사용자가 미래에 대한 불안감을 느끼는 상황",
        "사용자가 감동적인 경험을 공유하는 상황",
    ],
    "conflict": [
        "사용자와 의견이 다른 주제로 가벼운 토론",
        "사용자가 캐릭터의 행동에 서운함을 표현하는 상황",
        "서로 다른 가치관이 드러나는 대화",
        "사용자가 화가 나서 불만을 표현하는 상황",
    ],
    "advice": [
        "사용자가 진로/직업 고민을 상담하는 상황",
        "사용자가 인간관계 조언을 구하는 상황",
        "사용자가 자기계발에 대한 동기부여를 구하는 상황",
        "사용자가 건강이나 생활습관에 대해 물어보는 상황",
    ],
    "bonding": [
        "함께 여행 계획을 세우는 대화",
        "서로의 어릴 적 이야기를 공유하는 대화",
        "좋아하는 음악이나 취미를 공유하는 대화",
        "서로에 대한 첫인상을 이야기하는 대화",
    ],
}

# 호감도별 시나리오 가중치
AFFINITY_SCENARIO_WEIGHTS = {
    1: {"daily": 0.5, "emotional": 0.1, "conflict": 0.0, "advice": 0.2, "bonding": 0.2},
    2: {"daily": 0.4, "emotional": 0.2, "conflict": 0.05, "advice": 0.15, "bonding": 0.2},
    3: {"daily": 0.3, "emotional": 0.25, "conflict": 0.1, "advice": 0.15, "bonding": 0.2},
    4: {"daily": 0.2, "emotional": 0.3, "conflict": 0.1, "advice": 0.15, "bonding": 0.25},
    5: {"daily": 0.15, "emotional": 0.3, "conflict": 0.1, "advice": 0.1, "bonding": 0.35},
}


def _select_scenario(affinity_level: int) -> str:
    """호감도에 따라 시나리오 카테고리 선택 후 랜덤 시나리오 반환"""
    weights = AFFINITY_SCENARIO_WEIGHTS.get(affinity_level, AFFINITY_SCENARIO_WEIGHTS[3])
    categories = list(weights.keys())
    probs = list(weights.values())
    category = random.choices(categories, weights=probs, k=1)[0]
    return random.choice(SCENARIO_TEMPLATES[category])


async def generate_single_conversation(
    mbti: str,
    affinity_level: int,
    scenario: str,
    nickname: str = "사용자",
    character_name: str = "캐릭터",
    turns: int = 10,
) -> Optional[dict]:
    """gpt-4o로 단일 대화 생성 (OpenAI fine-tuning JSONL 형식)"""
    if not client:
        logger.error("OpenAI API 키가 없습니다.")
        return None

    personality = MBTI_PERSONALITIES.get(mbti, MBTI_PERSONALITIES["ENFP"])
    affinity = AFFINITY_BEHAVIORS.get(affinity_level, AFFINITY_BEHAVIORS[1])

    generation_prompt = f"""다음 설정으로 자연스러운 한국어 대화 {turns}턴을 생성해줘.

## 설정
- 캐릭터 MBTI: {mbti}
- 성격: {personality['traits']}
- 말투: {personality['style']}
- 감정 표현: {personality['emotional']}
- 호감도: {affinity_level}/5 ({affinity['description']})
- 분위기: {affinity['tone']}
- 캐릭터 이름: {character_name}
- 사용자 닉네임: {nickname}
- 상황: {scenario}

## 규칙
1. 사용자 메시지는 자연스러운 한국어 (존댓말/반말 혼용 가능)
2. 캐릭터 응답은 반드시 JSON 배열 형식: [{{"text": "내용", "emotion": "감정코드"}}]
3. emotion: NEUTRAL | HAPPY | SHY | SAD | ANGRY | SURPRISED | LOVE | PLAYFUL | WORRIED | TOUCHED
4. 캐릭터는 {mbti} 성격답게 반응하고, 호감도 {affinity_level} 수준에 맞는 친밀도 유지
5. 이모지/이모티콘 사용 금지 (ㅋㅋ, ㅎㅎ, ㅠㅠ 같은 텍스트 표현만 허용)
6. 각 캐릭터 응답은 1~4개 객체로 구성

## 출력 형식 (JSON만 출력)
{{"conversation": [
  {{"role": "user", "content": "사용자 메시지"}},
  {{"role": "assistant", "content": "[{{\\"text\\": \\"응답\\", \\"emotion\\": \\"HAPPY\\"}}]"}},
  ...
]}}"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": generation_prompt}],
            temperature=0.9,
            max_tokens=4000,
        )
        content = response.choices[0].message.content or ""

        # JSON 파싱
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            logger.warning(f"JSON 파싱 실패: {content[:100]}")
            return None

        data = json.loads(content[start:end])
        conversation = data.get("conversation", [])

        if len(conversation) < 4:
            logger.warning(f"대화 턴 부족: {len(conversation)}턴")
            return None

        # 시스템 프롬프트 생성 (fine-tuning용)
        system_prompt = build_system_prompt(
            mbti=mbti,
            speech_style="CASUAL",
            relationship="FRIEND",
            nickname=nickname,
            character_name=character_name,
            affinity_level=affinity_level,
        )

        # OpenAI fine-tuning 형식으로 변환
        training_example = {
            "messages": [{"role": "system", "content": system_prompt}] + conversation
        }

        return training_example

    except json.JSONDecodeError as e:
        logger.warning(f"JSON 디코딩 오류: {e}")
        return None
    except Exception as e:
        logger.error(f"대화 생성 실패: {e}")
        return None


async def generate_batch(
    mbti: str,
    affinity_level: int,
    count: int,
    nickname: str = "사용자",
    character_name: str = "캐릭터",
) -> List[dict]:
    """지정 MBTI × 호감도 조합에 대해 count개의 대화 생성"""
    results = []
    retries = 0
    max_retries = count  # 최대 재시도 횟수

    while len(results) < count and retries < max_retries:
        scenario = _select_scenario(affinity_level)
        logger.info(
            f"[{mbti}/Lv{affinity_level}] 생성 중 ({len(results)+1}/{count}): {scenario}"
        )

        example = await generate_single_conversation(
            mbti=mbti,
            affinity_level=affinity_level,
            scenario=scenario,
            nickname=nickname,
            character_name=character_name,
        )

        if example:
            results.append(example)
        else:
            retries += 1
            logger.warning(f"재시도 {retries}/{max_retries}")

        # API 레이트 리밋 방지
        await asyncio.sleep(1)

    return results


def save_jsonl(examples: List[dict], output_path: str) -> None:
    """JSONL 형식으로 저장"""
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    logger.info(f"저장 완료: {output_path} ({len(examples)}개)")


async def main():
    parser = argparse.ArgumentParser(description="MBTI 합성 학습 데이터 생성")
    parser.add_argument("--mbti", type=str, help="MBTI 유형 (e.g. INTJ)")
    parser.add_argument("--affinity", type=int, default=3, help="호감도 레벨 (1-5)")
    parser.add_argument("--count", type=int, default=10, help="생성 개수")
    parser.add_argument("--output", type=str, default="synthetic_data.jsonl", help="출력 파일 경로")
    parser.add_argument("--all", action="store_true", help="전체 MBTI × 호감도 조합 생성")
    parser.add_argument("--count-per-combo", type=int, default=5, help="--all 사용 시 조합당 생성 수")
    parser.add_argument("--nickname", type=str, default="사용자", help="사용자 닉네임")
    parser.add_argument("--character-name", type=str, default="캐릭터", help="캐릭터 이름")

    args = parser.parse_args()

    if not client:
        logger.error("OPENAI_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    all_examples = []

    if args.all:
        # 전체 조합 생성 (16 MBTI × 5 호감도)
        for mbti in ALL_MBTI:
            for affinity in range(1, 6):
                examples = await generate_batch(
                    mbti=mbti,
                    affinity_level=affinity,
                    count=args.count_per_combo,
                    nickname=args.nickname,
                    character_name=args.character_name,
                )
                all_examples.extend(examples)
                logger.info(f"[{mbti}/Lv{affinity}] {len(examples)}개 완료")
    else:
        if not args.mbti:
            logger.error("--mbti 또는 --all 옵션을 지정해주세요.")
            sys.exit(1)

        if args.mbti not in ALL_MBTI:
            logger.error(f"유효하지 않은 MBTI: {args.mbti}. 가능한 값: {ALL_MBTI}")
            sys.exit(1)

        all_examples = await generate_batch(
            mbti=args.mbti,
            affinity_level=args.affinity,
            count=args.count,
            nickname=args.nickname,
            character_name=args.character_name,
        )

    if all_examples:
        # 셔플 후 저장
        random.shuffle(all_examples)
        save_jsonl(all_examples, args.output)
        logger.info(f"총 {len(all_examples)}개 합성 데이터 생성 완료")
    else:
        logger.warning("생성된 데이터가 없습니다.")


if __name__ == "__main__":
    asyncio.run(main())
