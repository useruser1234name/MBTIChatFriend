# MBTIChatFriend Agent Guide

This repository is a monorepo for the Android app and FastAPI backend.

## Project Layout

- `android/`: Kotlin Android app using Jetpack Compose, Hilt, Room, Retrofit, Firebase, and Gradle.
- `server/`: Python FastAPI backend with routers, services, PostgreSQL support, ChromaDB usage, and pytest tests.
- `docs/` and the Korean meeting-notes directory: planning and review documents. Preserve Korean document content and filenames.

## General Rules

- Keep app and server source in this repository together unless the user explicitly asks to split them.
- Do not commit secrets, local credentials, Firebase service files, `.env`, `local.properties`, generated pytest temp folders, Gradle caches, or local assistant state.
- Do not re-add AWS ECS deployment workflows unless the user explicitly asks for AWS deployment.
- Prefer GCP Cloud Run, Firebase, and/or Supabase for future cloud deployment work unless the user changes direction.
- Keep changes scoped to the user's request. Do not rewrite unrelated app screens, backend routers, or documents.
- Preserve existing Korean user-facing copy unless the task is specifically to rewrite text.
- Use repo-local patterns before introducing new frameworks or abstractions.

## Verification Commands

Run focused checks for the area changed. For broad changes, run both app and server checks.

### Server

```bash
cd server
python -m pytest -q --basetemp=.pytest-tmp-codex
```

If pytest hits Windows/local temp permission issues, retry with a new ignored basetemp directory.

### Android

```bash
cd android
./gradlew.bat :app:compileDebugKotlin :app:testDebugUnitTest
```

On non-Windows runners, use `./gradlew` instead of `./gradlew.bat`.

## Cloud Codex Setup Notes

For Codex Cloud environments, install dependencies during setup rather than committing local generated files.

Suggested setup script:

```bash
python -m pip install -r server/requirements.txt
cd android && chmod +x ./gradlew
```

Required runtime secrets should be configured in the Codex/GitHub/cloud secret store, not in git:

- `OPENAI_API_KEY`
- `DATABASE_URL`
- Firebase service account or app config values
- Supabase or GCP credentials, if deployment work needs them

## Deployment Direction

The previous AWS ECS GitHub Actions workflow was removed. Do not restore it by default.

Preferred future deployment path:

- Backend: GCP Cloud Run
- App backend services: Firebase where appropriate
- Database: Supabase Postgres or GCP Cloud SQL, depending on the user's final choice

When adding deployment automation, make it explicit and gated behind user-provided cloud credentials.
