package com.example.mbtichatfriend.data.local

import com.example.mbtichatfriend.data.MessageConstraints
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ContentFilterTest {

    private fun buildSafeMessage(length: Int): String {
        val seed = "가나다라마바사아자차카타파하"
        return buildString(length) {
            while (this.length < length) {
                append(seed)
            }
        }.take(length)
    }

    @Test
    fun `normal message passes validation`() {
        val result = ContentFilter.check("안녕하세요! 오늘 날씨 좋네요")
        assertTrue(result.isSafe)
        assertEquals("", result.reason)
    }

    @Test
    fun `empty message is blocked`() {
        val result = ContentFilter.check("")
        assertFalse(result.isSafe)
        assertEquals("빈 메시지는 보낼 수 없어요.", result.reason)
    }

    @Test
    fun `whitespace only message is blocked`() {
        val result = ContentFilter.check("   ")
        assertFalse(result.isSafe)
        assertEquals("빈 메시지는 보낼 수 없어요.", result.reason)
    }

    @Test
    fun `message over max chars is blocked`() {
        val longMessage = buildSafeMessage(MessageConstraints.MAX_MESSAGE_LENGTH + 1)
        val result = ContentFilter.check(longMessage)
        assertFalse(result.isSafe)
        assertEquals(
            "메시지는 ${MessageConstraints.MAX_MESSAGE_LENGTH}자 이내로 입력해주세요!",
            result.reason
        )
    }

    @Test
    fun `message exactly max chars passes`() {
        val message = buildSafeMessage(MessageConstraints.MAX_MESSAGE_LENGTH)
        val result = ContentFilter.check(message)
        assertTrue(result.isSafe)
    }

    @Test
    fun `server side moderation is not duplicated on Android`() {
        val result = ContentFilter.check("섹스 관련 내용")
        assertTrue(result.isSafe)
    }

    @Test
    fun `custom max length is respected`() {
        val result = ContentFilter.check("123456", maxLength = 5)
        assertFalse(result.isSafe)
        assertEquals("메시지는 5자 이내로 입력해주세요!", result.reason)
    }
}
