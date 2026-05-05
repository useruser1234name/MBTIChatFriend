# MBTIChatFriend 보안 감사 보고서

**감사 일시**: 2026-04-13  
**감사 범위**: Android 앱 전체 + FastAPI 서버 전체  
**감사 도구**: 정적 코드 분석 (수동 리뷰)

---

## 종합 현황

| 심각도 | 서버 | Android | 합계 |
|--------|------|---------|------|
| Critical | 3 | 1 | **4** |
| High | 6 | 5 | **11** |
| Medium | 7 | 6 | **13** |
| Low | 4 | 5 | **9** |
| **총계** | **20** | **17** | **37** |

---

## 1. Critical (즉시 조치 필요)

### [CRIT-S1] OpenAI API 키 `.env` 파일 내 평문 노출

- **대상**: `server/.env:1`
- **설명**: 실제 운영 API 키(`sk-svcacct-...`)가 `.env` 파일에 저장되어 있음. `.gitignore`에 등록되어 커밋에는 포함되지 않으나, 키가 한 번이라도 공유/백업된 적이 있다면 이미 노출된 것으로 간주해야 함.
- **위험**: API 키 탈취 시 무제한 OpenAI API 호출 → 과금 폭탄
- **조치**:
  1. OpenAI 대시보드에서 해당 키 즉시 폐기 및 재발급
  2. 배포 환경에서는 GitHub Secrets / GCP Secret Manager 등 환경변수 시스템으로 주입
  3. `git log`에서 `.env` 커밋 이력 확인, 존재 시 히스토리 정리

---

### [CRIT-S2] FCM 푸시 발송 엔드포인트 IDOR — 타인에게 임의 알림 발송

- **대상**: `server/app/main.py:390-417`
- **설명**: `/api/v1/fcm/send` 엔드포인트에서 `req.user_id`를 클라이언트가 임의 지정 가능. 인증된 사용자의 `uid`와 `req.user_id` 간 비교 검증이 없음. `REQUIRE_AUTH=false` 환경에서는 인증 없이도 접근 가능.
- **위험**: 공격자가 피해자의 `user_id`를 알면 임의 내용의 푸시 알림 발송 가능
- **조치**:
  ```python
  async def send_fcm_notification(req: FcmSendRequest, user: dict = Depends(require_auth_always)):
      uid = user.get("uid")
      if uid != req.user_id:
          raise HTTPException(status_code=403, detail="다른 사용자에게 알림을 보낼 수 없습니다.")
  ```

---

### [CRIT-S3] FCM 토큰 등록 시 user_id 임의 지정 가능 — 토큰 탈취

- **대상**: `server/app/main.py:379-387`, `server/app/models.py:67-70`
- **설명**: `FcmTokenRequest.user_id`에 검증 없이 타인의 ID를 지정해 FCM 토큰을 덮어쓸 수 있음. 피해자에게 오는 모든 알림을 가로채거나 차단 가능.
- **위험**: 알림 하이재킹, 사용자 경험 방해
- **조치**:
  ```python
  async def register_fcm_token(req: FcmTokenRequest, user: dict = Depends(require_auth_always)):
      user_id = user["uid"]  # 클라이언트 입력 무시, 토큰에서 추출
      register_token(user_id, req.token)
  ```

---

### [CRIT-A1] FCM 토큰 평문 로그 노출

- **대상**: `ChatFirebaseMessagingService.kt:25`, `FcmTokenManager.kt:19`
- **설명**: `Log.d(TAG, "New FCM token: $token")`으로 토큰 전체가 logcat에 평문 출력됨. 루팅 기기 또는 `adb logcat`으로 즉시 탈취 가능.
- **위험**: FCM 토큰 탈취 → 대상 사용자에게 임의 푸시 발송
- **조치**:
  ```kotlin
  if (BuildConfig.DEBUG) {
      Log.d(TAG, "FCM token: ...${token.takeLast(6)}")
  }
  ```

---

## 2. High (이번 스프린트 조치)

### 서버

#### [HIGH-S1] 대화 삭제 엔드포인트 소유권 미검증 (IDOR)

- **대상**: `server/app/main.py:669-743`
- **설명**: 인증된 사용자가 다른 사람의 `room_id`/`character_id`를 지정해 타인의 대화 기록, 일기, 메트릭, 피드백을 모두 삭제 가능. `REQUIRE_AUTH=false`이면 인증 없이도 가능.
- **조치**: `room_id` 포맷(`{uid}:{character}`)을 활용한 소유권 검증:
  ```python
  uid = (user or {}).get("uid")
  if uid and req.room_id and not req.room_id.startswith(f"{uid}:"):
      raise HTTPException(status_code=403, detail="삭제 권한이 없습니다.")
  ```

#### [HIGH-S2] LIKE 쿼리 와일드카드 주입

- **대상**: `server/app/main.py:717`
- **설명**: `conversation_memory` 삭제 시 `room_id`가 LIKE 패턴에 직접 삽입됨. `room_id=%`를 입력하면 전체 테이블 삭제. psycopg의 `%s` 바인딩은 SQL 인젝션은 막지만 LIKE 와일드카드 이스케이프는 처리하지 않음.
- **조치**:
  ```python
  safe_room_id = req.room_id.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
  pg_execute(
      "DELETE FROM conversation_memory WHERE memory_key LIKE %s ESCAPE '\\'",
      (f"{safe_room_id}%",)
  )
  ```

#### [HIGH-S3] `payload::text LIKE` 전체 테이블 스캔 + 와일드카드 주입

- **대상**: `server/app/main.py:850-855`
- **설명**: `get_memories` 엔드포인트에서 `character_name` 경로 파라미터가 길이 제한/와일드카드 검증 없이 LIKE 패턴에 삽입됨. `payload::text LIKE`는 인덱스를 사용하지 못해 테이블 전체 스캔 → DoS 가능.
- **조치**: JSONB 연산자 사용 또는 `character_id` 컬럼으로 직접 조회

#### [HIGH-S4] 경로 파라미터 길이/소유권 미검증

- **대상**: `server/app/main.py:831-862`
- **설명**: `character_name`, `nickname` URL 경로 파라미터에 길이/형식 제한 없음. 타인의 character_name+nickname 조합으로 기억 데이터 열람 가능(IDOR).
- **조치**: `Path` 파라미터 길이 제한 + 소유권 검증 추가

#### [HIGH-S5] Fine-tuning 엔드포인트 관리자 보호 없음

- **대상**: `server/app/main.py:538-555`
- **설명**: `/api/v1/finetune/activate`에서 임의의 `model_id`로 모델 파일을 덮어쓸 수 있음. Rate limit 없음. `REQUIRE_AUTH=false`이면 인증 없이 접근 가능. Fine-tuning은 비용이 큰 작업.
- **조치**: `require_auth_always` + rate limit + 관리자 UID 화이트리스트

#### [HIGH-S6] Production에서 API 문서 공개

- **대상**: `server/app/main.py:99-103`
- **설명**: FastAPI 기본값으로 `/docs`, `/redoc`, `/openapi.json`이 환경 무관하게 공개됨. 전체 API 스펙 노출.
- **조치**:
  ```python
  app = FastAPI(
      ...,
      docs_url="/docs" if ENVIRONMENT != "production" else None,
      redoc_url="/redoc" if ENVIRONMENT != "production" else None,
      openapi_url="/openapi.json" if ENVIRONMENT != "production" else None,
  )
  ```

### Android

#### [HIGH-A1] 평문 HTTP 허용 — 개발자 IP 하드코딩

- **대상**: `res/xml/network_security_config.xml:4-7`, `app/build.gradle.kts:26`
- **설명**: 개발자 로컬 IP(`192.168.219.107`)가 소스코드에 하드코딩. 해당 IP에 cleartext HTTP 허용 → MITM 취약. 릴리즈 APK에도 IP 정보 포함.
- **조치**: debug 전용 network security config 분리, `local.properties`에서 URL 읽도록 변경

#### [HIGH-A2] Room DB 암호화 미적용

- **대상**: `di/AppModule.kt:40-69`
- **설명**: `messages`, `memories`, `diaries` 테이블에 대화 전문/기억/일기가 SQLite 평문 파일로 저장됨. 루팅 기기, ADB 백업, USB 디버깅으로 전체 추출 가능.
- **조치**: SQLCipher for Android 적용
  ```kotlin
  Room.databaseBuilder(...)
      .openHelperFactory(SupportFactory(SQLiteDatabase.getBytes("keyFromKeystore".toCharArray())))
      .build()
  ```

#### [HIGH-A3] 백업 규칙 미설정 — 민감 데이터 클라우드 백업 포함

- **대상**: `AndroidManifest.xml:12`, `res/xml/backup_rules.xml`, `res/xml/data_extraction_rules.xml`
- **설명**: `allowBackup="true"` 상태에서 백업 규칙이 모두 주석 처리된 템플릿. Room DB, DataStore 파일이 Google 클라우드 백업에 포함됨.
- **조치**: `backup_rules.xml`에 DB/DataStore 제외 규칙 추가

#### [HIGH-A4] DataStore에 Firebase UID/FCM 토큰 평문 저장

- **대상**: `data/local/UserPreferences.kt:33-36`
- **설명**: `FIREBASE_UID`, `FCM_TOKEN`이 DataStore 평문 파일로 저장됨. H-03 백업 취약점과 결합 시 클라우드 유출. `OPENAI_API_KEY` 관련 `@Deprecated` 코드도 미삭제.
- **조치**: Android Keystore 래핑 또는 `EncryptedSharedPreferences` 이전. `OPENAI_API_KEY` 관련 코드 완전 삭제.

#### [HIGH-A5] 로그아웃 시 Room DB 데이터 미삭제

- **대상**: `ui/settings/SettingsViewModel.kt:89-95`
- **설명**: `signOut` + `clearAll`은 Firebase 세션과 DataStore만 삭제. Room DB(`messages`, `characters`, `memories`, `diaries`)는 그대로 잔류. 공유 기기에서 다음 사용자가 이전 대화에 접근 가능.
- **조치**: `logout` 시 각 DAO의 `deleteAll()` 호출 추가

---

## 3. Medium

### 서버

| ID | 취약점 | 대상 | 설명 |
|----|--------|------|------|
| MED-S1 | Rate limit IP 기반 | `main.py:84` | 공유 NAT에서 타 사용자 차단, IP 순환으로 우회 가능. uid 기반 전환 필요 |
| MED-S2 | `HistoryMessage.content` 길이 무제한 | `models.py:12-15` | 50개 메시지 x 무제한 길이 → LLM 비용 공격. `max_length=2000` 추가 |
| MED-S3 | `ImageSetRequest.size` 자유 문자열 | `models.py:148-153` | `ImageGenerateRequest`와 달리 `Literal` 제한 없음. DALL-E API 오류/비용 낭비 |
| MED-S4 | 개발 환경 예외 상세 정보 HTTP 응답 노출 | `main.py:468,492` | `str(e)`에 파일 경로/내부 URL/라이브러리 버전 포함 가능 |
| MED-S5 | CORS `credentials=True` + `origins=["*"]` | `main.py:108-114` | 브라우저 스펙 위반 조합. production 설정 실수 시 Credential 크로스오리진 허용 |
| MED-S6 | `quality/dashboard` `days` 미검증 | `main.py:592-599` | 음수/극대값으로 전체 테이블 스캔 DoS. `Query(ge=1, le=365)` 필요 |
| MED-S7 | `uvicorn.run(reload=True)` production 잔류 | `main.py:866-871` | Docker에서 직접 실행 시 production에서도 reload 활성화 |

### Android

| ID | 취약점 | 대상 | 설명 |
|----|--------|------|------|
| MED-A1 | 인증서 피닝 미적용 | `di/AppModule.kt:100-115` | OkHttpClient에 `CertificatePinner` 없음. MITM 가능 |
| MED-A2 | 입력 길이 한계 불일치 | `ContentFilter.kt:54` vs `remote_config:1000` vs 서버 `2000` | 클라이언트 우회 시 서버 한도까지 입력 가능 |
| MED-A3 | 토큰 캐싱 Race Condition | `AuthInterceptor.kt:17-21` | `@Volatile` 단독으로 복합 연산 원자성 미보장. `Mutex`/`synchronized` 필요 |
| MED-A4 | FCM 메시지 데이터 검증 없음 | `ChatFirebaseMessagingService.kt:35-41` | 길이/내용 검증 없이 알림 표시. 스팸/혼란 유발 |
| MED-A5 | ProGuard keep 규칙 과도 | `proguard-rules.pro:6-7` | `data/remote` 패키지 전체 보존 → API 구조 역공학 노출 |
| MED-A6 | 딥링크 Intent Extra 정수 오버플로우 | `MainActivity.kt:133-136` | `characterId.toInt()` 오버플로우 시 PendingIntent 충돌 |

---

## 4. Low

### 서버

| ID | 취약점 | 대상 |
|----|--------|------|
| LOW-S1 | Content filter 로그에서 메시지 길이 노출 | `content_filter.py:127` |
| LOW-S2 | `FinetuneRequest.conversations` 크기 무제한 | `models.py:113` |
| LOW-S3 | `FcmTokenRequest.token` 형식 검증 없음 | `models.py:67-70` |
| LOW-S4 | `firebase-admin` 6.5.0 → 7.x 업데이트 필요 | `requirements.txt:9` |

### Android

| ID | 취약점 | 대상 |
|----|--------|------|
| LOW-A1 | FCM 메시지 내용 로그 출력 | `ChatFirebaseMessagingService.kt:33` |
| LOW-A2 | Firestore에 연령/성별 저장 (PIPA 주의) | `FirestoreManager.kt:36-43` |
| LOW-A3 | Remote Config 무결성 보장 없음 | `RemoteConfigManager.kt:24-34` |
| LOW-A4 | `@Deprecated` API 키 코드 미삭제 | `UserPreferences.kt:39-41, 174-184` |
| LOW-A5 | 알림 PendingIntent requestCode Int 범위 제한 | `NotificationHelper.kt:56` |

---

## 5. 구조적 관찰 사항

### AUTH 아키텍처 일관성

`verify_firebase_token`은 `REQUIRE_AUTH=false` 환경에서 `None`을 반환하고 진행함. 대부분의 엔드포인트가 개발 환경에서 완전 무인증 접근됨. 개발 환경에서도 최소한의 test token을 강제하거나, 엔드포인트별 인증 필요 여부를 명시적으로 관리 권장.

### Anonymous Room 공유

`_resolve_room_id`에서 `uid`가 없으면 `"anonymous"` 고정 문자열 사용. 모든 미인증 사용자가 `"anonymous:{character_id}"` room을 공유 → 데이터 혼재 발생.

### SQL Injection 안전 확인

- **서버**: psycopg/asyncpg의 `%s` 파라미터 바인딩 사용으로 SQL 인젝션 안전 (LIKE 와일드카드 주입은 별도 이슈)
- **Android**: Room `@Query` 어노테이션이 파라미터 바인딩 사용으로 SQL 인젝션 안전

### WebView

코드베이스 내 WebView 사용 없음 → XSS/JavaScript Interface 위험 없음.

---

## 6. 조치 우선순위 로드맵

### Phase 1: 즉시 (1일 이내)

| 항목 | 예상 작업 | 담당 |
|------|----------|------|
| CRIT-S1: OpenAI API 키 폐기/재발급 | 5분 | Ops |
| CRIT-S2/S3: FCM 엔드포인트 uid 검증 | 30분 | Server |
| CRIT-A1: FCM 토큰 로그 마스킹 | 10분 | Android |

### Phase 2: 이번 스프린트

| 항목 | 예상 작업 | 담당 |
|------|----------|------|
| HIGH-S1: 대화 삭제 소유권 검증 | 1시간 | Server |
| HIGH-S2/S3: LIKE 쿼리 이스케이프/최적화 | 2시간 | Server |
| HIGH-S4/S5: 경로 파라미터 검증, finetune 보호 | 1시간 | Server |
| HIGH-S6: Production `/docs` 비활성화 | 30분 | Server |
| HIGH-A3: 백업 규칙 설정 | 30분 | Android |
| HIGH-A5: 로그아웃 시 Room DB 삭제 | 1시간 | Android |
| LOW-A4: `@Deprecated` API 키 코드 삭제 | 15분 | Android |

### Phase 3: 다음 스프린트

| 항목 | 예상 작업 | 담당 |
|------|----------|------|
| MED-S1: Rate limit uid 기반 전환 | 2시간 | Server |
| MED-S2: HistoryMessage 길이 제한 | 30분 | Server |
| MED-S3~S7: 입력 검증/설정 정리 | 2시간 | Server |
| MED-A1: 인증서 피닝 적용 | 2시간 | Android |
| MED-A2: 입력 길이 일치화 | 1시간 | Android |
| HIGH-A1: 개발 IP 외부화 | 1시간 | Android |

### Phase 4: 중기

| 항목 | 예상 작업 | 담당 |
|------|----------|------|
| HIGH-A2: Room DB 암호화 (SQLCipher) | 4시간 | Android |
| HIGH-A4: DataStore 암호화 | 2시간 | Android |
| MED-A3: 토큰 갱신 동기화 (Mutex) | 1시간 | Android |
| MED-A5: ProGuard keep 규칙 최소화 | 1시간 | Android |
| LOW-S4: CI에 pip-audit/dependency 스캔 추가 | 2시간 | DevOps |

---

## 7. 참고

- 본 감사는 정적 코드 분석 기반이며, 동적 침투 테스트는 포함되지 않음
- Firestore Security Rules는 Firebase 콘솔에서 별도 감사 필요
- 서버 배포 환경(Docker/Cloud Run 등)의 네트워크 보안 설정은 별도 검토 필요
- 다음 정기 보안 감사 권장 시점: 2026-07 (분기별)
