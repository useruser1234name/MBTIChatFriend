# 에이전트 통합 회의록

**회의 일시**: 2026-04-13
**참석**: backend-dev, frontend-dev, llm-expert, ux-designer, data-analyst, **critic (비판자)**
**진행**: PM

---

## 1. 각 에이전트 발언 요약

### backend-dev

**동의**: Phase 1 보안 패치 순서 적절. FCM IDOR, LIKE 이스케이프 즉시 조치 동의.

**조정 요청**:
- BD-H3(memory_service async 전환)을 Phase 1로 격상 요청. 메모리 추출 10턴마다 10-20초 지연이 사용자 체감 Critical임.
- `affinity_task` 예외 처리(15분 작업)가 Phase 명시에서 빠져 있음. Phase 1 포함 요청.

**기술적 우려**:
- BD-H10(room_id 마이그레이션) 공수 3h는 낙관적. `conversation_memory`의 LIKE 패턴 조회, Android 클라이언트 호환성 창 관리 필요.
- BD-M1(rate limit uid 기반) 전환 시 `REQUIRE_AUTH=false` 환경에서 uid=None 폴백 처리 필수.

**추가 발견**:
- `postgres.py`에서 asyncpg 풀 초기화 실패 시 조용히 psycopg 폴백으로 전환됨. 운영팀이 인지 불가. 경고 로그 강화 필요.

---

### frontend-dev

**동의**: FE-C3(OfflineMessageQueue withLock), FE-C2(AuthInterceptor) Phase 1 적절.

**조정 요청**:
- FE-H1(room_id Migration v8)을 Phase 1 수준으로 당길 것. 서버 먼저 배포 시 기존 Android 클라이언트의 대화 기록 즉시 유실.
- FE-H2(MbtiGroup enum)도 `IllegalArgumentException` 크래시이므로 Phase 2 1일차로 배치 요청.

**기술적 우려**:
- FE-M2(SQLCipher) 4h 예상은 비현실적. 미암호화 DB → 암호화 전환에 파일 복사+재암호화 필요. 별도 PoC 스파이크 선행 제안.
- AuthInterceptor의 `cachedToken`/`tokenExpiry` 두 필드를 `data class CachedToken` 단일 `@Volatile` 참조로 교체 제안.

**추가 발견**:
- `SettingsViewModel.deleteConversationData`가 `roomId`를 전송하지 않음. 서버 소유권 검증 추가 시 Android 요청 스펙도 변경 필요. backend-dev와 `DeleteConversationRequest` 스펙 합의 필요.
- `AppNavHost`에서 Home/Settings 탭에도 `saveState/restoreState` 미적용. Gallery뿐 아니라 전체 탭 일괄 적용 제안.

---

### llm-expert

**동의**: LLM-C1(메모리 추출 블로킹), LLM-C2(호감도 에러 전파) Critical 분류 적절.

**조정 요청**:
- LLM-H1(Prefix Caching)을 Phase 2 최우선으로. mood 변경 시 1100토큰+ 정적 프롬프트 캐시 통째 무효화 중. 비용 절감 효과가 가장 즉각적.
- LLM-H7(Few-shot 8그룹)은 Phase 3으로 이동. 우선 SJ/SP 분리(6그룹)까지만.
- LLM-M5(감정 코드 설명 7개 추가)를 LLM-H3(thinking 필드)과 묶어 Phase 2로. 캐시 무효화 1회로 통합.

**프롬프트 엔지니어링 우려**:
- Prefix Caching 분리 시 `safety_prompt`는 정적 블록에 인라인하고 `mood`만 별도 system 메시지로 분리하는 것이 캐시 히트율에 유리.
- `thinking` 필드 추가 위치: 기존 블록 사이에 "삽입"하면 안 됨. `# 특유 습관` 앞에 추가해야 기존 캐시 무효화 최소화.

**추가 발견**:
- `build_memory_context` 중복 호출(483행, 530행). LLM-C1과 함께 1분 수정 가능.
- 재생성 시 temperature 0.9는 형식 위반율을 높임. 0.7로 낮춰야 함.
- 호감도 분석 프롬프트를 system+user 분리하면 매 호출 수백 토큰 캐시 가능.

---

### ux-designer

**동의**: UX-C2(로딩 중복), UX-C4(삭제 버튼 중복) Critical 적절.

**조정 요청**:
- UX-C3(홈 배너 과밀)을 UX-C6(ChatScreen 애니메이션)보다 먼저 처리. 홈이 첫 진입점이므로 여기서 이탈하면 채팅 개선이 무의미.
- UX-H1(감성 폰트)을 Phase 2 최우선으로. 폰트는 앱 전체 분위기의 기반이므로 이후 모든 화면 개선이 완성된 폰트 위에서 검수되어야 함.

**감정 설계 관점**:
- 가장 임팩트가 큰 개선 = UX-M8(대화 스타터 칩) + UX-M9(호감도 바 펄스). 매 메시지마다 작동하는 피드백 루프가 레벨업 셀레브레이션(드문 이벤트)보다 우선.
- 레벨다운은 AlertDialog가 아닌 `secondaryContainer` 색상의 토스트로. "경고"가 아닌 "잠깐 멀어진 것"이라는 관계적 맥락.

**추가 발견**:
- TopBar Settings + BottomNav Settings가 같은 목적지로 연결되는지 `AppNavHost` 확인 필요. 백스택 불일치 위험.
- `ImageGeneratorBannerCard` FAB 이동 시 발견 가능성(discoverability) 저하 우려. SpeedDial 패턴 또는 갤러리 내 진입점 강화 병행 필요.

---

### data-analyst

**동의**: DA-C1(llm_usage room_id 공백) 즉시 수정 필요.

**측정 인프라 우려**:
- `metric_events`에 `user_id` 컬럼 없음. `room_id`로 uid 추출은 가능하나 포맷 변경(BD-H10) 후 히스토리 조인 불가.
- `session_start`/`session_end` 이벤트 미존재. 리텐션 분석(DA-M2)은 "앱 오픈" 이벤트 없이 추정 수준에 그침.

**KPI 현실성**:
- LLM 비용 30% 절감: **달성 가능**. `history_len > 5` 조건만 제거해도 mini 비율이 30% → 70%로. 보수적 추정.
- Day 7 리텐션 +5%p: **기준값 없이 목표 설정 불가**. DA-M2를 Phase 1로 앞당겨 기준값부터 잡아야 함.

**A/B 테스트 우선순위**:
1. 복잡도 라우팅 점수제(LLM-H2) - 서버 플래그로 온/오프, `llm_usage` 이벤트로 즉시 측정
2. 대화 스타터 칩(UX-M8) - 첫 대화 전환율 측정 가능
3. 레벨업 셀레브레이션(UX-M1) - 측정 가장 어려움. `affinity_level_up` 이벤트 선행 추가 필요.

**추가 발견**:
- `quality_service.py`의 fine-tuning 데이터 필터링이 room 초반 낮은 점수로 인해 개선 후에도 해당 room 전체 제외. 최신값 기준 쿼리로 변경 필요.
- `low_diversity_warning` 이벤트에 room_id 없음. 이벤트 스키마 통일 요청.

---

### critic (비판자)

#### 과대평가된 이슈

1. **quality_service INTERVAL SQL 인젝션 (BD-C4)**: psycopg `%s` 바인딩이 문자열 이스케이프하므로 실제 SQL 인젝션 불가. `days`는 `Query(default=30)` integer 타입. **Medium (입력 범위 검증)이 적절. Critical이 아님.**

2. **AuthInterceptor `runBlocking(Dispatchers.IO)` (FE-C2)**: IO 스레드 하나 추가 소비 수준. 동시 요청 수백 건 아닌 이상 체감 없음. **High가 적절.**

3. **cache_control Anthropic 파라미터**: OpenAI는 이 필드를 무시할 뿐 에러 아님. **진짜 문제는 mood 합치기이지 파라미터 자체가 아님.** 리뷰가 핵심을 벗어남.

#### 과소평가된 이슈

1. **`_get_mbti_group` 주석 불일치**: 서버 리뷰 High → **실제 Critical**. 주석이 틀려서 개발자가 잘못된 few-shot 작성했을 가능성. 이미 잘못된 few-shot이 배포 중일 수 있음.

2. **room_id 포맷 변경**: 코드 리뷰 Medium → **실제 Critical**. 배포 시 대화 기록, 일기, 스토리, 메트릭 전체 조회 불가 = 서비스 장애. Phase 1에 "마이그레이션 없이 머지 금지" 게이트 필요.

3. **content_filter 위기 허용 목록 Tier1 우회**: 코드 리뷰 Low → **최소 High**. 사용자 안전 문제는 Low로 분류하면 안 됨.

4. **anonymous room 공유**: 보안 감사에서 "구조적 관찰"로만 기록. `REQUIRE_AUTH=false` 시 모든 사용자가 같은 room 공유 → 대화 뒤섞임. **Medium으로 격상.**

#### 실행 계획 허점

1. **UX Phase 1이 6.5시간**: 2일 안에 CollapsingToolbar 설계(2h 예상)까지 포함. Compose NestedScrollConnection 커스텀은 실제 하루+. "설계만" vs "구현 포함" 불명확.

2. **Room Migration 테스트 시간 미포함**: FE-H1(3h) + FE-H2(2h) 예상이지만 실제 Migration은 테스트에 추정치의 2-3배.

3. **main.py 동시 수정 7건+**: "PR 분리 권장"만으로 부족. 구체적 머지 순서(보안 패치 → 비동기 전환 → 기능 변경) 필요.

4. **SQLCipher(FE-M2)를 이번 사이클에서 제외 권고**: Phase 2에서 Migration v8 + MbtiGroup, Phase 3에서 SQLCipher → 연속 3번 DB 변경은 위험. 별도 스프린트로 분리.

5. **API 키 재발급(BD-C6) 배포 절차 없음**: 키 재발급 → 환경변수 업데이트 → 서버 재배포를 원자적으로 해야 하는데 절차가 없음.

#### 놓친 근본적 질문

1. **`REQUIRE_AUTH=false`가 production에 배포될 수 있는가?** — 모든 IDOR의 근본 원인. 개별 엔드포인트 패치는 대증 요법.

2. **1인 개발 프로젝트에서 5개 에이전트 병렬 실행이 가능한가?** — 최종 리뷰/머지/배포 조율을 누가 하는지. 서버 작업 먼저 → Android 작업 순차 접근이 현실적일 수 있음.

3. **호감도 밸런스 테스트를 한 적이 있는가?** — Lv.1 → Lv.5 도달 시뮬레이션 데이터 없음. return_bonus 캡핑만으로 해결 안 됨.

4. **보안 패치에 대한 테스트 작성 계획 없음** — 72개 기존 테스트에 인증/소유권 검증 테스트 케이스 추가 필요.

5. **현재 월간 LLM 비용 모름** — 비용 현황 없이 30% 절감 목표는 맹목적.

---

## 2. 회의 결정 사항

### 2.1 비판자 의견 수용/기각 판정

| # | 비판 내용 | 판정 | 사유 |
|---|----------|------|------|
| 1 | INTERVAL SQL 인젝션 → Medium 하향 | **수용** | psycopg 바인딩이 이스케이프. 입력 범위 검증으로 충분 |
| 2 | AuthInterceptor → High 하향 | **수용** | 체감 성능 이슈 낮음. Phase 2 유지 |
| 3 | cache_control 파라미터 자체는 무해 | **수용** | 핵심은 mood 합치기. 리뷰 표현 수정 |
| 4 | `_get_mbti_group` 주석 불일치 → Critical | **수용** | 잘못된 few-shot이 배포 중일 가능성. Phase 2 최우선 |
| 5 | room_id 포맷 변경 → Critical | **수용** | "마이그레이션 없이 머지 금지" 게이트 추가 |
| 6 | 위기 허용 목록 → High | **수용** | 사용자 안전 문제 Low 불가 |
| 7 | anonymous room → Medium | **수용** | 개발 환경 데이터 오염 리스크 |
| 8 | SQLCipher 이번 사이클 제외 | **수용** | 연속 3회 DB 변경 위험. 별도 스프린트 |
| 9 | 5개 에이전트 병렬 비현실적 | **부분 수용** | 서버/Android 순차 접근 채택. 단, 설계 작업은 병렬 허용 |
| 10 | 호감도 밸런스 테스트 필요 | **수용** | data-analyst에 시뮬레이션 추가 |
| 11 | LLM 비용 현황 리포트 필요 | **수용** | DA Phase 1에 추가 |
| 12 | 보안 패치 테스트 계획 부재 | **수용** | BD DoD에 테스트 케이스 수 명시 |
| 13 | REQUIRE_AUTH production 강제 검증 | **수용** | BD-C 신규 항목 추가 |

### 2.2 우선순위 조정 확정

| 변경 | 변경 전 | 변경 후 | 사유 |
|------|--------|--------|------|
| BD-C4 (INTERVAL SQL) | Critical | **Medium** | critic: psycopg 바인딩 안전 |
| FE-C2 (AuthInterceptor) | Critical | **High (Phase 2 Day 1)** | critic: 체감 성능 영향 낮음 |
| room_id 포맷 변경 | Medium (Phase 2) | **Critical 게이트** | critic + frontend-dev: 데이터 손실 |
| FE-H2 (MbtiGroup enum) | High (Phase 2) | **Phase 2 Day 1** | frontend-dev: 크래시 위험 |
| LLM-H1 (Prefix Caching) | Phase 2 | **Phase 2 최우선** | llm-expert: 비용 임팩트 최대 |
| LLM-H7 (Few-shot 8그룹) | Phase 2 (3h) | **Phase 3 (6그룹으로 축소)** | llm-expert + critic: 캐시 효율 상충 |
| LLM-M5 (감정 코드 설명) | Medium (Phase 3) | **Phase 2 (LLM-H3과 묶음)** | llm-expert: 캐시 무효화 1회 통합 |
| UX-C3 (홈 배너 과밀) | Critical #3 | **Critical #1** | ux-designer: 첫 진입점 우선 |
| UX-H1 (감성 폰트) | Phase 2 | **Phase 2 최우선** | ux-designer: 기반 요소 |
| 위기 허용 목록 Tier1 우회 | Low | **High** | critic: 사용자 안전 |
| FE-M2 (SQLCipher) | Phase 3 | **이번 사이클 제외** | critic: 연속 DB 변경 위험 |
| DA: LLM 비용 현황 | 없음 | **DA Phase 1 추가** | critic: 기준값 없이 목표 불가 |
| DA-M2 (리텐션 기준값) | Phase 3 | **Phase 2로 앞당김** | data-analyst: 기준 없이 개선 측정 불가 |

### 2.3 신규 추가 항목

| 항목 | 담당 | Phase | 사유 |
|------|------|-------|------|
| REQUIRE_AUTH production 강제 검증 | backend-dev | 1 | critic: IDOR 근본 원인 |
| `DeleteConversationRequest` 스펙 합의 | backend-dev + frontend-dev | 1 | frontend-dev: uid 전송 필요 |
| `metric_events`에 `user_id` 컬럼 추가 | backend-dev | 2 | data-analyst: 리텐션 측정 선행 조건 |
| `affinity_level_up` 이벤트 추가 | backend-dev | 2 | data-analyst: A/B 측정용 |
| 호감도 밸런스 시뮬레이션 | data-analyst | 3 | critic: Lv.1→5 도달 시간 검증 |
| LLM 비용 현황 리포트 | data-analyst | 1 | critic: 기준값 필수 |
| 보안 패치 테스트 케이스 10건+ | backend-dev | 1-2 | critic: 테스트 없이 배포 금지 |
| `saveState/restoreState` 전체 탭 적용 | frontend-dev | 2 | frontend-dev: Gallery만이 아닌 전체 |
| mood 전송 비율 측정 | data-analyst | 2 | critic: Prefix Caching 효과 검증용 |

---

## 3. 확정된 실행 순서

### 서버 먼저 → Android 후속 (순차 접근 채택)

```
Week 1 (Day 1-2): 서버 Critical + Android Critical (병렬)
  서버: BD-C1~C7 + REQUIRE_AUTH 강제 + LLM-C1~C2
  Android: FE-C1, FE-C3~C5 (서버 무관 항목만)
  UX: Critical 설계 스펙 작성 (구현은 frontend-dev에게 전달)
  DA: LLM 비용 현황 + room_id 영향 산정

Week 1 (Day 3-5): 서버 High 완료
  서버: BD-H1~H9 + LLM-H1~H6
  Android: FE-H2(MbtiGroup) + FE-H3~H8 (서버 무관 항목)
  UX: 감성 폰트 스펙 + 화면별 개선 스펙 작성
  DA: 리텐션 기준값 + mood 전송 비율 측정

Week 2 (Day 6-7): room_id 동시 배포
  서버: BD-H10 (room_id 마이그레이션 스크립트)
  Android: FE-H1 (room_id Migration v8)
  *** 반드시 동시 배포. 마이그레이션 없이 머지 금지 ***

Week 2-3: Phase 3
  서버: BD-M1~M10 + LLM-M1~M8
  Android: FE-M1~M8 (SQLCipher 제외)
  UX: 경쟁력 강화 구현
  DA: A/B 테스트 3건 + 호감도 밸런스 시뮬레이션
```

### main.py 머지 순서 (확정)

```
1. 보안 패치 PR (BD-C1~C5, C7) — 최우선 머지
2. REQUIRE_AUTH 강제 검증 PR — 보안 패치 직후
3. 비동기 전환 PR (BD-H1~H4) — 보안 머지 후
4. 기능 변경 PR (BD-H5~H10) — 비동기 머지 후
5. LLM 관련 PR (LLM-H5 mood_checkin) — 기능 변경 머지 후
```

---

## 4. 기각된 의견 및 사유

| 의견 | 제안자 | 기각 사유 |
|------|--------|----------|
| BD-H3를 Phase 1로 | backend-dev | LLM-C1(메모리 백그라운드)이 Phase 1에 이미 포함. BD-H3는 LLM-C1의 선행이 아닌 독립 작업이므로 Phase 2 유지 |
| 5개 에이전트 완전 순차 | critic | 서버/Android 순차는 채택하되, 설계 작업(UX 스펙)은 구현과 병렬 허용 |
| PostgreSQL 이중 구조 근본 재설계 | critic (암시) | 이번 사이클에서 "하지 않을 것"에 명시적 추가. 땜질 후 별도 스프린트 |
| Few-shot 16개 개별화 | llm-expert (암시) | 토큰 비용 과다. 6그룹이 비용-품질 균형점 |

---

## 5. 액션 아이템

| 담당 | 액션 | 기한 |
|------|------|------|
| backend-dev | BD-C1~C7 + REQUIRE_AUTH 강제 PR 작성 | Day 2 |
| backend-dev | `DeleteConversationRequest` 스펙 초안 → frontend-dev 공유 | Day 1 |
| frontend-dev | FE-C1, C3~C5 PR 작성 | Day 2 |
| frontend-dev | FE-H2(MbtiGroup) `group` 필드 사용처 전수 조사 결과 공유 | Day 3 |
| llm-expert | LLM-C1~C2 PR 작성 | Day 2 |
| llm-expert | Prefix Caching 분리 구조 설계안 → backend-dev 공유 | Day 3 |
| llm-expert | MBTI 16종별 대화 스타터 예시 2개씩 → ux-designer 전달 | Day 5 |
| ux-designer | Phase 1 Critical 6건 설계 스펙 → frontend-dev 전달 | Day 1 |
| ux-designer | 감성 폰트 선정 + Typography 스펙 확정 | Day 3 |
| data-analyst | 현재 LLM 월간 비용 현황 리포트 | Day 2 |
| data-analyst | mood 전송 비율 + room_id 변경 영향 범위 리포트 | Day 3 |
| PM | room_id 마이그레이션 동시 배포 일정 확정 (Day 6-7) | Day 1 |
| PM | main.py 머지 순서 가이드 팀 공유 | Day 1 |

---

## 6. 핵심 집중 지표 (수정)

| 지표 | 목표 | 비고 |
|------|------|------|
| Critical 보안 이슈 | Phase 1 종료 시 **0건** | REQUIRE_AUTH 강제 포함 |
| LLM 비용 | 기준값 측정 후 **30% 절감** | DA Day 2 비용 리포트 기준 |
| 10턴 응답 지연 | **0초** (백그라운드 전환) | LLM-C1 완료 기준 |
| Day 7 리텐션 | **기준값 측정 우선** (+5%p는 기준 확정 후) | DA Phase 2 리텐션 리포트 기준 |
| 보안 패치 테스트 | **10건+ 테스트 케이스** 추가 | BD DoD |

---

## 7. "하지 않을 것" (최종)

1. 크리에이터 이코노미 / UGC 캐릭터
2. Live2D / 3D 캐릭터 전환
3. iOS 포팅
4. 다국어 지원
5. 음성 파인튜닝 / 커스텀 TTS
6. **SQLCipher Room DB 암호화** (이번 사이클 제외, 별도 스프린트)
7. **PostgreSQL asyncpg/psycopg 이중 구조 근본 재설계** (땜질 후 별도 스프린트)
8. **Few-shot 16개 개별화** (6그룹까지만)

---

*회의 종료: 2026-04-13*
*작성: PM*
*참석: backend-dev, frontend-dev, llm-expert, ux-designer, data-analyst, critic*
