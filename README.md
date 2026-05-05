# MBTIChatFriend Monorepo

- `android/`: Android app project
- `server/`: FastAPI backend project

## Quick Start

### Server
1. `cd server`
2. `python -m venv venv`
3. `venv\Scripts\activate`
4. `pip install -r requirements.txt`
5. `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

### Server + PostgreSQL (Docker Compose)
1. Run from repo root: `docker compose up`
2. Backend uses default DB URL: `postgresql://mbti:mbti@db:5432/mbti_chat`
3. To run server locally without Docker DB, set `DATABASE_URL` in `server/.env`.

### Android
- Open `android/` in Android Studio.

## Notes
- This repository is set up as a monorepo for synchronized app/server development.
- Keep secrets out of git (`server/.env`, tokens, local.properties).
