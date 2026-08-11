"""M1 disclosure 게이팅 A/B 응답 생성기 (two-arm, 워킹 트리 비파괴).

docs/EVAL_KIT_M1_disclosure_2026-08.md 의 12셀 설계를 그대로 따르되,
킷 3.3의 `git stash` 방식을 쓰지 않는다. 다른 에이전트가 동시에 서버 파일을
수정 중일 수 있으므로 **워킹 트리는 절대 건드리지 않는다.**

  after  = 현재 워킹 트리의 app.prompts.build_system_prompt (M1 반영본)
  before = `git show <M1커밋>~1:server/app/prompts.py` 를 임시 디렉터리에
           추출해 별도 패키지로 임포트한 것

두 arm은 `chat_service._build_chat_messages` 를 공유하고, before arm만
`chat_service.build_system_prompt` 심볼을 before 모듈의 것으로 치환한다.
따라서 safety 프롬프트/히스토리 조립/유저 스타일 미러링/메시지 경계 등
프롬프트 이외의 모든 요소가 두 arm에서 바이트 단위로 동일하다.

모델은 메인 앱과 동일하게 `_classify_message_complexity` 로 턴마다 라우팅한다
(유저 발화와 history_len만의 함수 → 두 arm에서 항상 동일한 모델이 선택된다).

사용:
    cd server
    python tools/eval_m1_generate.py --arm after  --out ../eval_after.jsonl
    python tools/eval_m1_generate.py --arm before --out ../eval_before.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

# M1 커밋 — before arm은 이 커밋의 부모 시점 prompts.py 를 쓴다.
M1_COMMIT = os.getenv("EVAL_M1_COMMIT", "ce515aa")

TEMPERATURE = float(os.getenv("EVAL_TEMPERATURE", "0.85"))  # 프로덕션 메인 경로와 동일
MAX_TOKENS = int(os.getenv("EVAL_MAX_TOKENS", "1200"))      # 프로덕션 메인 경로와 동일
SEED = int(os.getenv("EVAL_SEED", "20260811"))              # 두 arm 동일(샘플링 잡음 축소)
MODEL_OVERRIDE = os.getenv("EVAL_MODEL", "")                # 비우면 복잡도 라우팅 사용
CONCURRENCY = int(os.getenv("EVAL_CONCURRENCY", "6"))

MBTIS = ["INTJ", "INFP", "ISFJ", "ESFP"]
TIERS = {
    "T1": (2, ["오늘 진짜 별로였어", "면접 봤는데 망한 거 같아", "...",
               "너는 이런 적 없어?", "그냥 얘기 들어줘서 고마워"]),
    "T2": (4, ["오늘 되게 힘든 하루였어", "너 요즘 나한테 좀 달라진 거 같은데",
               "다른 사람이랑 밥 먹었어. 왜, 신경 쓰여?", "ㅇㅇ", "너 지금 무슨 생각해?"]),
    "T3": (5, ["보고 싶었어", "오늘 진짜 힘들었어...", "너 나 좋아하는 거 맞지?",
               "ㅋㅋ", "너는 나 왜 좋아해?"]),
}


# ── .env 로드 (python-dotenv 의존 없이) ────────────────────────────────
def load_env() -> None:
    env_path = SERVER_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

from app import chat_service  # noqa: E402
from app.models import HistoryMessage, VALID_EMOTIONS  # noqa: E402
from app.quality_service import quick_score  # noqa: E402

# 프로덕션 품질 게이트(generate_reply)와 동일한 재시도 유도 메시지
RETRY_HINT = {
    "role": "user",
    "content": (
        "직전 응답 형식이 올바르지 않았어. 반드시 "
        '[{"text":"...","emotion":"EMOTION_CODE"}] '
        "형태의 JSON 배열로만 다시 답해줘. "
        "코드블록·설명·다른 텍스트는 절대 붙이지 마."
    ),
}
QUALITY_GATE_THRESHOLD = float(os.getenv("EVAL_GATE", "0.4"))


# ── before arm 로더 ────────────────────────────────────────────────────
def load_before_build_system_prompt():
    """M1 직전 커밋의 prompts.py 를 임시 패키지로 임포트해 함수를 돌려준다.

    워킹 트리는 읽기만 한다(`git show`). prompts.py 는 `from .mbti import ...`
    상대 임포트가 있으므로 mbti.py 도 같은 시점 버전으로 함께 추출한다.
    """
    tmp = Path(tempfile.mkdtemp(prefix="m1_before_"))
    pkg = tmp / "before_app"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    for name in ("prompts.py", "mbti.py"):
        blob = subprocess.run(
            ["git", "show", f"{M1_COMMIT}~1:server/app/{name}"],
            cwd=REPO_DIR, capture_output=True, check=True,
        ).stdout.decode("utf-8")
        (pkg / name).write_text(blob, encoding="utf-8")

    src = (pkg / "prompts.py").read_text(encoding="utf-8")
    assert "disclosure" not in src, "before arm에 M1 disclosure 키가 들어있다 — 커밋 지정 오류"

    sys.path.insert(0, str(tmp))
    spec = importlib.util.find_spec("before_app.prompts")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_system_prompt


# ── 형식 검증 ──────────────────────────────────────────────────────────
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")


def validate_reply(content: str):
    """(strict_ok, bubbles, reason). strict = 펜스 제거 후 그대로 JSON 배열."""
    if not content:
        return False, [], "empty"
    text = _FENCE.sub("", content.strip())
    try:
        data = json.loads(text)
    except Exception as e:
        return False, [], f"json_error:{type(e).__name__}"
    if not isinstance(data, list) or not data:
        return False, [], "not_a_nonempty_array"
    bubbles = []
    for item in data:
        if not isinstance(item, dict):
            return False, [], "item_not_object"
        t = item.get("text")
        emo = item.get("emotion")
        if not isinstance(t, str) or not t.strip():
            return False, [], "missing_text"
        if emo not in VALID_EMOTIONS:
            return False, [], f"bad_emotion:{emo}"
        bubbles.append({"text": t.strip(), "emotion": emo})
    return True, bubbles, ""


# ── 셀 실행 ────────────────────────────────────────────────────────────
async def run_cell(client, build_system_prompt, arm, mbti, tier, sem):
    level, turns = TIERS[tier]
    history: list[HistoryMessage] = []
    records = []
    stats = {"retries": 0, "strict_fail_final": 0}

    for idx, user_turn in enumerate(turns, start=1):
        complexity = chat_service._classify_message_complexity(user_turn, len(history))
        model = MODEL_OVERRIDE or (
            chat_service.LLM_MODEL_COMPLEX if complexity == "complex"
            else chat_service.LLM_MODEL_SIMPLE
        )
        messages = chat_service._build_chat_messages(
            mbti=mbti, speech_style="CASUAL", relationship="FRIEND",
            nickname="유저", character_name="", affinity_level=level,
            user_mbti="", persona_raw="", persona_summary="",
            dialogue_prompt="", visual_prompt="",
            memory_dicts=None, mem_ctx="", episode_context="", mood=None,
            conversation_history=history, message=user_turn,
        )

        # 프로덕션 generate_reply 품질 게이트와 동일: quick_score < 0.4 이면 1회
        # 재생성하고, 점수가 매우 낮으면(<=0.2, 형식 붕괴) 형식 환기 메시지를 덧붙인다.
        send = messages
        content, ok, bubbles, reason, attempts, score = "", False, [], "", 0, 0.0
        for attempt in range(2):
            attempts = attempt + 1
            async with sem:
                r = await client.chat.completions.create(
                    model=model, messages=send,
                    temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
                    seed=SEED, timeout=90,
                )
            content = r.choices[0].message.content or ""
            ok, bubbles, reason = validate_reply(content)
            score = quick_score(user_turn, content, mbti)
            if ok and score >= QUALITY_GATE_THRESHOLD:
                break
            if attempt == 0:
                stats["retries"] += 1
                send = messages + [RETRY_HINT] if score <= 0.2 else messages
        if not ok:
            stats["strict_fail_final"] += 1

        # 프로덕션이 실제로 사용자에게 내보내는 형태 = 관대한 _parse_reply 복구 결과
        lenient = chat_service._parse_reply(content)
        lenient_bubbles = [{"text": p.text, "emotion": p.emotion} for p in lenient]
        if not ok:
            # 형식이 깨져도 대화는 이어간다 — 관대 파서 결과를, 그것도 없으면 원문을 사용
            bubbles = lenient_bubbles or [
                {"text": content.strip(), "emotion": "PARSE_FAILED"}
            ]

        records.append({
            "turn": idx, "user": user_turn, "model": model,
            "complexity": complexity, "attempts": attempts,
            "strict_ok": ok, "reason": reason, "quick_score": round(score, 3),
            "lenient_recovered": bool(lenient_bubbles),
            "bubbles": bubbles, "raw": content,
        })

        # 프로덕션과 동일한 히스토리 형태: 유저 원문 1건 + 말풍선별 assistant 1건씩
        history.append(HistoryMessage(role="user", content=user_turn))
        for b in bubbles:
            history.append(HistoryMessage(role="assistant", content=b["text"]))

    return {"arm": arm, "mbti": mbti, "tier": tier, "level": level,
            "turns": records, "stats": stats}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["before", "after"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    if a.arm == "before":
        chat_service.build_system_prompt = load_before_build_system_prompt()
        print(f"[before] prompts.py @ {M1_COMMIT}~1 로드 완료")
    else:
        print("[after] 워킹 트리 app.prompts 사용")

    sem = asyncio.Semaphore(CONCURRENCY)
    cells = [(m, t) for m in MBTIS for t in TIERS]
    results = await asyncio.gather(*(
        run_cell(client, chat_service.build_system_prompt, a.arm, m, t, sem)
        for m, t in cells
    ))

    out = Path(a.out)
    with out.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    retries = sum(r["stats"]["retries"] for r in results)
    fails = sum(r["stats"]["strict_fail_final"] for r in results)
    calls = sum(t["attempts"] for r in results for t in r["turns"])
    unrecovered = sum(
        1 for r in results for t in r["turns"]
        if not t["strict_ok"] and not t["lenient_recovered"]
    )
    print(f"{a.arm}: cells={len(results)} turns={len(results)*5} "
          f"api_calls={calls} retries={retries} strict_fail_final={fails} "
          f"lenient_unrecovered={unrecovered} -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
