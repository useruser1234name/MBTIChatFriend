package com.example.mbtichatfriend.data.local

import com.example.mbtichatfriend.data.MessageConstraints

/**
 * Android only does lightweight input validation.
 * Moderation and crisis policy are enforced on the server.
 */
object ContentFilter {

    data class FilterResult(
        val isSafe: Boolean,
        val reason: String = ""
    )

    fun check(
        input: String,
        maxLength: Int = MessageConstraints.MAX_MESSAGE_LENGTH
    ): FilterResult {
        val trimmed = input.trim()

        if (trimmed.isEmpty()) {
            return FilterResult(false, "빈 메시지는 보낼 수 없어요.")
        }

        if (trimmed.length > maxLength) {
            return FilterResult(false, "메시지는 ${maxLength}자 이내로 입력해주세요!")
        }

        return FilterResult(true)
    }
}
