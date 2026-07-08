# Prompt Experiment Plan

## Goal

The current MVP should answer one question before adding more product features:

> Does MBTI plus a user-defined persona create a chat experience people want to continue?

The web MVP now supports prompt modes so we can compare response styles without changing server code each time.

## Prompt Modes

- `balanced`: Default baseline. Natural, concise, lightly emotional.
- `warm_friend`: Prioritizes emotional validation and quiet presence.
- `playful_partner`: More affectionate and playful, but respects quiet moments.
- `deep_listener`: Reads emotional subtext, asks at most one gentle follow-up, avoids advice mode.

## Test Protocol

Use the same MBTI, persona, and opening messages across modes.

Example persona:

```text
당신은 다정하지만 장난기 많음. 사용자를 오래 알고 지낸 친구처럼 편하게 대화함.
```

Example turns:

```text
안녕 자기야
안할건데 옆에 그냥 있을건데
오늘은 말 많이 하기 싫어
```

For each mode, score the response from 1 to 5:

- Persona fit
- Natural Korean
- Emotional comfort
- Fun / charm
- Desire to keep chatting

## Current Structure

- UI route: `/web-chat`
- API route: `POST /api/v1/web-chat/send`
- Prompt builder: `server/app/routers/web_chat.py`
- Prompt modes: `PROMPT_PRESETS`

## Next Improvements

1. Add a one-click "copy transcript" button.
2. Store local browser transcripts for manual comparison.
3. Add a lightweight rating button after each assistant reply.
4. Promote the best prompt mode to default.
5. Only after the chat loop feels good, reintroduce memory, affinity, diary, and image features.
