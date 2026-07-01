# OpenAI 429 Quota Troubleshooting

## What Happened

The web chat MVP returned this error:

```text
Error code: 429
code: insufficient_quota
message: You exceeded your current quota
```

This does not always mean the account has used all expected tokens. It can also happen when the server is using a different API key, project, or billing scope than expected.

## Immediate MVP Behavior

The web chat MVP now falls back to a mock response when this specific quota error happens. That keeps the chat screen usable for UI and flow testing while billing/key state is checked.

The response uses:

```json
{
  "model": "mock:openai_quota",
  "mocked": true
}
```

## Checklist

1. Confirm `server/.env` contains the intended `OPENAI_API_KEY`.
2. Restart the FastAPI server after changing `.env`.
3. Check whether the key belongs to the expected OpenAI project.
4. Check OpenAI Platform billing for the project that owns the key.
5. Check project or monthly usage limits.
6. If multiple organizations are used, confirm the key is not tied to another organization.
7. If the key was recently created, try creating a new project key after billing is active.

## Why This Matters

For the current MVP, the product question is the chat experience, not billing plumbing. The fallback prevents quota state from blocking persona and MBTI conversation testing.
