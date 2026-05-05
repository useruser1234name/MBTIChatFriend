package com.example.mbtichatfriend.data.local

import org.junit.Assert.*
import org.junit.Test

class CharacterEntityTest {

    private fun createEntity(affinityScore: Int) = CharacterEntity(
        id = 0,
        name = "Test",
        mbti = "ENFP",
        speechStyle = "CASUAL",
        relationship = "FRIEND",
        affinityScore = affinityScore
    )

    @Test
    fun `affinityScore 0 returns level 1`() {
        assertEquals(1, createEntity(0).affinityLevel)
    }

    @Test
    fun `affinityScore 19 returns level 1`() {
        assertEquals(1, createEntity(19).affinityLevel)
    }

    @Test
    fun `affinityScore 20 returns level 2`() {
        assertEquals(2, createEntity(20).affinityLevel)
    }

    @Test
    fun `affinityScore 39 returns level 2`() {
        assertEquals(2, createEntity(39).affinityLevel)
    }

    @Test
    fun `affinityScore 40 returns level 3`() {
        assertEquals(3, createEntity(40).affinityLevel)
    }

    @Test
    fun `affinityScore 59 returns level 3`() {
        assertEquals(3, createEntity(59).affinityLevel)
    }

    @Test
    fun `affinityScore 60 returns level 4`() {
        assertEquals(4, createEntity(60).affinityLevel)
    }

    @Test
    fun `affinityScore 79 returns level 4`() {
        assertEquals(4, createEntity(79).affinityLevel)
    }

    @Test
    fun `affinityScore 80 returns level 5`() {
        assertEquals(5, createEntity(80).affinityLevel)
    }

    @Test
    fun `affinityScore 100 returns level 5`() {
        assertEquals(5, createEntity(100).affinityLevel)
    }

    @Test
    fun `default values are correct`() {
        val entity = CharacterEntity(
            name = "DefaultTest",
            mbti = "INFP",
            speechStyle = "FORMAL",
            relationship = "STRANGER"
        )
        assertEquals(0L, entity.id)
        assertEquals(0, entity.affinityScore)
        assertEquals(0, entity.totalMessages)
        assertEquals("default", entity.avatarId)
        assertNull(entity.expressionSet)
        assertFalse(entity.expressionSetReady)
    }
}
