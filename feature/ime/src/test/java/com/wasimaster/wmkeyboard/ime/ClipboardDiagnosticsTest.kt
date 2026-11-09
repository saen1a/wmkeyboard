package com.wasimaster.wmkeyboard.ime

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class ClipboardDiagnosticsTest {
    @Before
    fun setUp() = ClipboardDiagnostics.reset()

    @After
    fun tearDown() = ClipboardDiagnostics.reset()

    @Test
    fun `reset clears every clipboard counter`() {
        ClipboardDiagnostics.onCaptureAttempt()
        ClipboardDiagnostics.onStoredText()
        ClipboardDiagnostics.reset()

        val summary = ClipboardDiagnostics.summary()
        assertTrue(summary.contains("capture_attempts=0"))
        assertTrue(summary.contains("stored_text=0"))
    }

    @Test
    fun `summary counts each clipboard category`() {
        ClipboardDiagnostics.onCaptureAttempt()
        ClipboardDiagnostics.onCaptureAttempt()
        ClipboardDiagnostics.onSelfWriteSkip()
        ClipboardDiagnostics.onGateDrop()
        ClipboardDiagnostics.onSensitiveDrop()
        ClipboardDiagnostics.onSensitiveMediaDrop()
        ClipboardDiagnostics.onStoredText()
        ClipboardDiagnostics.onStoredImage()
        ClipboardDiagnostics.onStoredFiles(3)
        ClipboardDiagnostics.onStoredPrivate()
        ClipboardDiagnostics.onAbortedTextCapture()
        ClipboardDiagnostics.onAbortedImageCapture()

        val summary = ClipboardDiagnostics.summary()
        assertTrue(summary.contains("capture_attempts=2"))
        assertTrue(summary.contains("self_write_skips=1"))
        assertTrue(summary.contains("gate_drops=1"))
        assertTrue(summary.contains("sensitive_drops=1"))
        assertTrue(summary.contains("sensitive_media_drops=1"))
        assertTrue(summary.contains("stored_text=1"))
        assertTrue(summary.contains("stored_image=1"))
        assertTrue(summary.contains("stored_file=3"))
        assertTrue(summary.contains("stored_private=1"))
        assertTrue(summary.contains("aborted_text=1"))
        assertTrue(summary.contains("aborted_image=1"))
    }

    @Test
    fun `summary contains only the known counter keys and numeric values`() {
        ClipboardDiagnostics.onCaptureAttempt()
        ClipboardDiagnostics.onStoredText()
        ClipboardDiagnostics.onStoredPrivate()

        val tokens = ClipboardDiagnostics.summary().split(" ")
        assertTrue(tokens.all { it.matches(Regex("[a-z_]+=\\d+")) })
        assertEquals(
            setOf(
                "inline_requests", "responses", "suggestions", "autofill", "platform",
                "inflated", "withdrawn", "capture_attempts", "self_write_skips",
                "gate_drops", "sensitive_drops", "sensitive_media_drops",
                "stored_text", "stored_image", "stored_file", "stored_private",
                "aborted_text", "aborted_image",
            ),
            tokens.map { it.substringBefore('=') }.toSet(),
        )
    }
}
