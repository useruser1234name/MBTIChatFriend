package com.example.mbtichatfriend.data.local

/**
 * 클라이언트 사전 입력 필터링
 * 서버 필터와 별도로 빠른 차단을 위한 1차 필터
 */
object ContentFilter {

    data class FilterResult(
        val isSafe: Boolean,
        val reason: String = ""
    )

    private val bannedPatterns = listOf(
        // 성적 표현 (명확한 것만)
        "섹스", "성관계", "야동", "포르노", "자위", "오르가",
        "알몸", "나체", "음란",
        // 폭력 (타인 대상)
        "살인", "칼빵",
        // 혐오
        "니거", "한남충", "한녀충", "틀딱", "급식충",
    )

    // 위기 감지 키워드(자살/자해 등)는 클라이언트에서 차단하지 않는다.
    // 차단하면 서버의 Tier1 자해 위기 개입(전문가 안내) 흐름이 막혀 오히려 위험하다.
    // 이런 메시지는 서버 content_filter의 위기 감지로 전달되어야 한다.

    // 단독으로 사용될 때만 차단 (다른 글자 사이에 섞여 있으면 무시)
    private val standalonePatterns = listOf(
        Regex("(^|\\s)ㅅㅅ($|\\s)"),    // "ㅅㅅ" 단독
        Regex("(^|\\s)ㅂㅇ($|\\s)"),    // "ㅂㅇ" 단독
    )

    private val suspiciousPatterns = listOf(
        // 반복 특수문자 (스팸)
        Regex("(.{1,2})\\1{5,}"),
        // 과도한 특수문자
        Regex("[^가-힣a-zA-Z0-9\\s]{10,}"),
    )

    fun check(input: String): FilterResult {
        val trimmed = input.trim()

        if (trimmed.isEmpty()) {
            return FilterResult(false, "빈 메시지는 보낼 수 없어요")
        }

        if (trimmed.length > 500) {
            return FilterResult(false, "메시지가 너무 길어요 (최대 500자)")
        }

        // 금칙어 체크 (성적/혐오/타인 대상 폭력). 위기 키워드는 의도적으로 제외.
        val lowerInput = trimmed.lowercase()
        for (word in bannedPatterns) {
            if (lowerInput.contains(word)) {
                return FilterResult(false, "부적절한 표현이 포함되어 있어요")
            }
        }

        // 단독 사용 패턴 체크
        for (pattern in standalonePatterns) {
            if (pattern.containsMatchIn(trimmed)) {
                return FilterResult(false, "부적절한 표현이 포함되어 있어요")
            }
        }

        // 의심 패턴 체크 (스팸/도배)
        for (pattern in suspiciousPatterns) {
            if (pattern.containsMatchIn(trimmed)) {
                return FilterResult(false, "올바른 메시지를 입력해주세요")
            }
        }

        return FilterResult(true)
    }
}
