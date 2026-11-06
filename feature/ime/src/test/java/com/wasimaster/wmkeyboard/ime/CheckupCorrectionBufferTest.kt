package com.wasimaster.wmkeyboard.ime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CheckupCorrectionBufferTest {

    @Test
    fun `a correction during the replay is retained and drained once`() {
        val buffer = CheckupCorrectionBuffer()
        buffer.begin(setOf("hello", "hallo"))
        assertTrue(
            buffer.remember(
                "hello",
                CheckupCorrectionBuffer.Correction("hello", "hallo"),
            ),
        )
        assertEquals(
            listOf(CheckupCorrectionBuffer.Correction("hello", "hallo")),
            buffer.finish(setOf("hello", "hallo")),
        )
        assertTrue(buffer.finish(setOf("hello", "hallo")).isEmpty())
    }

    @Test
    fun `a correction after the replay is not retained`() {
        val buffer = CheckupCorrectionBuffer()
        buffer.begin(setOf("hello"))
        assertTrue(buffer.finish(setOf("hello")).isEmpty())
        assertFalse(
            buffer.remember(
                "hello",
                CheckupCorrectionBuffer.Correction("hello", "hallo"),
            ),
        )
        assertTrue(buffer.finish(setOf("hello")).isEmpty())
    }

    @Test
    fun `overlapping replays keep the correction until the last one finishes`() {
        val buffer = CheckupCorrectionBuffer()
        buffer.begin(setOf("hello"))
        buffer.begin(setOf("hello"))
        assertTrue(
            buffer.remember(
                "hello",
                CheckupCorrectionBuffer.Correction("hello", "hallo"),
            ),
        )
        assertTrue("the first replay must not drain", buffer.finish(setOf("hello")).isEmpty())
        assertEquals(
            listOf(CheckupCorrectionBuffer.Correction("hello", "hallo")),
            buffer.finish(setOf("hello")),
        )
    }

    @Test
    fun `only the last correction for a key is kept`() {
        val buffer = CheckupCorrectionBuffer()
        buffer.begin(setOf("hello"))
        assertTrue(buffer.remember("hello", CheckupCorrectionBuffer.Correction("hello", null)))
        assertTrue(
            buffer.remember(
                "hello",
                CheckupCorrectionBuffer.Correction("hello", "hallo"),
            ),
        )
        assertEquals(
            listOf(CheckupCorrectionBuffer.Correction("hello", "hallo")),
            buffer.finish(setOf("hello")),
        )
    }
}
