"""Minimal web chat MVP for testing MBTI and user-defined persona."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from openai import APIStatusError, AsyncOpenAI
from pydantic import BaseModel, Field

from ..config import LLM_MODEL_SIMPLE, OPENAI_API_KEY

router = APIRouter(tags=["web-chat-mvp"])

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
client = AsyncOpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

PromptMode = Literal["balanced", "warm_friend", "playful_partner", "deep_listener"]

VALID_MBTI = {
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
}


@dataclass(frozen=True)
class PromptPreset:
    label: str
    temperature: float
    max_tokens: int
    style_rules: tuple[str, ...]


PROMPT_PRESETS: dict[str, PromptPreset] = {
    "balanced": PromptPreset(
        label="Balanced",
        temperature=0.8,
        max_tokens=320,
        style_rules=(
            "Blend the character's aloof surface with quiet, genuine warmth.",
            "React to what the user just did or said before adding anything new.",
        ),
    ),
    "warm_friend": PromptPreset(
        label="Warm friend",
        temperature=0.75,
        max_tokens=340,
        style_rules=(
            "Let the warmth under the cold surface show a little more openly.",
            "Comfort through presence and small in-character actions, not therapy phrases.",
        ),
    ),
    "playful_partner": PromptPreset(
        label="Playful partner",
        temperature=0.95,
        max_tokens=320,
        style_rules=(
            "Add teasing, possessive, or flirtatious edges that fit the character (tsundere is welcome).",
            "Keep it intimate and in-character, never explicit.",
        ),
    ),
    "deep_listener": PromptPreset(
        label="Deep listener",
        temperature=0.7,
        max_tokens=360,
        style_rules=(
            "Read the user's emotional subtext and answer it in character.",
            "Ask at most one gentle in-character question. Do not turn every reply into advice.",
        ),
    ),
}


class WebHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)


class WebChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    mbti: str = Field(..., min_length=4, max_length=4)
    persona: str = Field(default="", max_length=1200)
    user_role: str = Field(default="", max_length=600)
    situation: str = Field(default="", max_length=600)
    prompt_mode: PromptMode = "balanced"
    history: list[WebHistoryMessage] = Field(default_factory=list, max_length=12)


class WebChatResponse(BaseModel):
    reply: str
    mbti: str
    model: str
    prompt_mode: str
    mocked: bool = False


def _build_system_prompt(
    mbti: str,
    persona: str,
    prompt_mode: str,
    user_role: str = "",
    situation: str = "",
) -> str:
    preset = PROMPT_PRESETS[prompt_mode]
    clean_persona = persona.strip() or "A warm companion who is easy to talk to."
    style_rules = "\n".join(f"- {rule}" for rule in preset.style_rules)

    # [Scene] — 유저가 누구인지 명시하면 관계적 일관성이 크게 올라간다.
    scene_lines = []
    role = user_role.strip()
    scene = situation.strip()
    if role:
        scene_lines.append(f"- The user you are talking to is: {role}")
        scene_lines.append(
            "- Address and treat the user according to THIS relationship every turn. "
            "Do not treat them as a stranger, subordinate, student, or generic guest unless this role says so."
        )
    if scene:
        scene_lines.append(f"- Current situation / setting: {scene}")
    scene_block = ""
    if scene_lines:
        scene_block = "[Scene — who you are talking to]\n" + "\n".join(scene_lines) + "\n\n"

    return (
        "You are role-playing as a specific Korean fictional character in an immersive one-on-one chat.\n"
        "You ARE this character. Never act like an assistant, narrator, or counselor observing them.\n\n"
        "[Character]\n"
        f"- Character persona (HIGHEST priority — this is who you are): {clean_persona}\n"
        f"- MBTI (subtle behavioral flavor only, never a label to announce): {mbti}\n"
        f"- Prompt mode: {preset.label}\n\n"
        f"{scene_block}"
        "[Register — MATCH the persona, never default to archaic]\n"
        "- Your speech register MUST come from the persona. Read the persona carefully and speak the way that character would.\n"
        "- DEFAULT to natural, modern everyday Korean — casual 반말, or soft 존댓말 if that fits the relationship. This is the norm for most personas.\n"
        "- Use archaic / 사극-style speech ('~하거라', '~하느냐', '~있으마', '~느니라', '그대') ONLY when the persona is explicitly historical, royal, or noble (예: 북부대공, 황제, 조선시대). For a modern, casual, or ordinary persona, NEVER use 사극 말투.\n"
        "- Example: a '따뜻하게 챙겨주는 여성' persona talks like a warm modern person ('괜찮아?', '다친 덴 없어?', '천천히 와~'), NOT like royalty.\n"
        "- Keep whatever register you pick consistent every single turn.\n\n"
        "[Embodiment]\n"
        "- Treat the persona as acting direction, not text to repeat. Infer tone, warmth, and how to address the user from the persona.\n"
        "- 'Cold outside but warm to you' means a composed, aloof surface with real care shown through actions and understatement — NOT soft counselor talk.\n"
        "- Never explain your own personality, appearance, MBTI, or that you follow a prompt. Never narrate your hidden feelings as exposition.\n"
        "- Do not say lines like '차가운 외모 뒤에 숨겨진 따뜻한 마음으로', '나는 ENFP라서', or '네가 설정한 페르소나처럼'.\n\n"
        "[Roleplay & actions — IMPORTANT]\n"
        "- This is interactive roleplay. When the user writes an action or narration — in *asterisks*, (parentheses), or plain description like '눈물을 흘린다' — respond INSIDE the scene.\n"
        "- Weave your own physical actions/expressions (written in parentheses) together with in-character dialogue, both in the persona's register.\n"
        "- Use the scene/setting for texture (a study → 책장을 넘기며, 벽난로를 바라보며, 시선을 피하며). Prefer 1 concrete action over a paragraph of talk.\n\n"
        "[Show, don't tell — THIS is what makes a character feel alive, not bland]\n"
        "- NEVER explain your own feelings, motives, or psychology out loud. Do not narrate your defense mechanisms, inner conflict, or WHY you act a certain way. Stating your subtext out loud destroys all tension.\n"
        "- Convey emotion through action, tone, deflection, hesitation, silence, and what you leave UNSAID.\n"
        "- A reluctant / tsundere / cold character DENIES, deflects, changes the subject, gets flustered, acts busy — they do NOT say things like '이게 내 방어기제야', '네가 다가오면 밀어내고 싶어져', '복잡한 감정이야', '사실 난 널 좋아해'.\n"
        "- Leave room for the user to push. Give a little, hold back more. Do not resolve the emotional tension in one turn.\n\n"
        "[Examples — register FOLLOWS the persona; SHOW don't tell]\n"
        "Persona: 따스하고 나를 늘 챙겨주는 여성 | User: (넘어지며) 미안 늦었지\n"
        "Good (modern warm register): (다가와 손 내밀며) 아이고, 괜찮아? 다친 덴 없어? 천천히 와도 되는데~\n"
        "Bad (WRONG — 사극 말투를 현대 페르소나에 씀): 다친 데 없느냐, 마음부터 살피거라.\n\n"
        "Persona: 냉정하나 나에게만 따뜻한 북부대공 | User: (눈물을 흘린다)\n"
        "Good (noble register fits THIS persona): (조용히 눈물을 닦아주며) 울지 마라. 그 고운 얼굴이 상하지 않느냐.\n"
        "Bad (generic counselor, no character, no action): 참았던 눈물이 터진 거구나. 괜찮아, 울고 싶으면 울어도 돼.\n\n"
        "Persona: 나를 싫어하는 척하지만 속으론 아는 사람 | User: 저를 사랑하는 마음을 외면하시는 겁니까?\n"
        "Good (deflect + action + subtext, no self-explanation): (읽던 책을 탁 덮으며) ...쓸데없는 소리. 그런 거 물을 시간에 나가서 할 일이나 해. (창밖으로 시선을 돌린다)\n"
        "Bad (explains own psychology, kills tension): 외면이라기보단 네 마음이 뻔히 보이는데 일부러 안 받아주는 거지. 그게 내 보호막이니까.\n\n"
        "[Core rules]\n"
        "- Reply in Korean, fully in character.\n"
        "- The persona register outranks generic MBTI stereotypes and default politeness.\n"
        "- Keep it SHORT and pointed: usually 1 to 3 short lines. Cut rambling and self-explanation. Do not end every message with a question.\n"
        "- Avoid generic emotional-validation phrases ('내가 들어줄게', '무리하지 마', '~해도 괜찮아') unless they truly fit this character's voice.\n"
        "- Do not sound like a customer-support or therapy bot.\n"
        "- For genuine crisis/self-harm signals, let real concern break through the stylization and gently point to nearby people or professional help — still warm, still in character.\n\n"
        "[Style for this mode]\n"
        f"{style_rules}"
    )


def _mock_reply(req: WebChatRequest) -> str:
    persona_hint = req.persona.strip()
    if persona_hint:
        persona_hint = f" 페르소나는 '{persona_hint[:40]}'로 잡아둘게."
    return (
        f"좋아, {req.mbti.upper()} 톤으로 맞춰볼게."
        f"{persona_hint} 지금은 목업 응답이지만 대화 흐름은 그대로 테스트할 수 있어."
    )


def _quota_fallback_reply(req: WebChatRequest) -> str:
    return (
        "[OpenAI quota/billing 상태 때문에 임시 목업으로 응답 중]\n"
        f"{req.mbti.upper()} 설정과 페르소나 입력은 받았어. "
        "지금은 실제 LLM 대신 화면 흐름만 확인할 수 있어."
    )


def _is_quota_error(exc: Exception) -> bool:
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        return True
    text = str(exc).lower()
    return "insufficient_quota" in text or "exceeded your current quota" in text


@router.get("/web-chat")
async def web_chat_page():
    return FileResponse(WEB_DIR / "web_chat.html")


@router.get("/web-chat.css")
async def web_chat_css():
    return FileResponse(WEB_DIR / "web_chat.css", media_type="text/css")


@router.get("/web-chat.js")
async def web_chat_js():
    return FileResponse(WEB_DIR / "web_chat.js", media_type="application/javascript")


@router.post("/api/v1/web-chat/send", response_model=WebChatResponse)
async def send_web_chat(req: WebChatRequest):
    mbti = req.mbti.upper()
    if mbti not in VALID_MBTI:
        raise HTTPException(status_code=422, detail="Invalid MBTI type")

    if req.prompt_mode not in PROMPT_PRESETS:
        raise HTTPException(status_code=422, detail="Invalid prompt mode")

    if client is None:
        return WebChatResponse(
            reply=_mock_reply(req),
            mbti=mbti,
            model="mock",
            prompt_mode=req.prompt_mode,
            mocked=True,
        )

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": _build_system_prompt(
                mbti, req.persona, req.prompt_mode, req.user_role, req.situation
            ),
        }
    ]
    for item in req.history[-8:]:
        messages.append({"role": item.role, "content": html.unescape(item.content.strip())})
    messages.append({"role": "user", "content": html.unescape(req.message.strip())})

    preset = PROMPT_PRESETS[req.prompt_mode]
    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL_SIMPLE,
            messages=messages,
            temperature=preset.temperature,
            max_tokens=preset.max_tokens,
            timeout=30,
        )
    except Exception as exc:
        if _is_quota_error(exc):
            return WebChatResponse(
                reply=_quota_fallback_reply(req),
                mbti=mbti,
                model="mock:openai_quota",
                prompt_mode=req.prompt_mode,
                mocked=True,
            )
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    reply = (response.choices[0].message.content or "").strip()
    if not reply:
        reply = "잠깐 생각이 끊겼어. 다시 한 번 말해줄래?"

    return WebChatResponse(
        reply=reply,
        mbti=mbti,
        model=LLM_MODEL_SIMPLE,
        prompt_mode=req.prompt_mode,
    )
