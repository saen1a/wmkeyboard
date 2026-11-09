package com.wasimaster.wmkeyboard.ime

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

/**
 * Content-free counters for the inline-autofill and clipboard-capture paths.
 *
 * Password-manager bugs are almost always a request that was never built, a
 * response that never arrived, or a chip that failed to inflate remotely. A
 * missing clipboard entry is a capture attempt that never reached the store,
 * or a gate that dropped it. None of those needs a credential, and none of
 * them should put one in a log. This object counts events only; [summary] is
 * safe to show in a debug screen or a support report.
 */
object ClipboardDiagnostics {
    private enum class Counter(val key: String) {
        INLINE_REQUESTS("inline_requests"),
        RESPONSES("responses"),
        SUGGESTIONS("suggestions"),
        AUTOFILL_LANE("autofill"),
        PLATFORM_LANE("platform"),
        INFLATED("inflated"),
        WITHDRAWN("withdrawn"),
        CAPTURE_ATTEMPTS("capture_attempts"),
        SELF_WRITE_SKIPS("self_write_skips"),
        GATE_DROPS("gate_drops"),
        SENSITIVE_DROPS("sensitive_drops"),
        SENSITIVE_MEDIA_DROPS("sensitive_media_drops"),
        STORED_TEXT("stored_text"),
        STORED_IMAGE("stored_image"),
        STORED_FILES("stored_file"),
        STORED_PRIVATE("stored_private"),
        ABORTED_TEXT("aborted_text"),
        ABORTED_IMAGE("aborted_image"),
    }

    /**
     * One entry per counter. Keeping the registry in one enum means adding a
     * counter cannot leave reset() or summary() behind.
     */
    private val counters = ConcurrentHashMap<Counter, AtomicLong>().apply {
        Counter.entries.forEach { counter -> put(counter, AtomicLong()) }
    }

    private fun add(counter: Counter, delta: Long = 1L): Long =
        counters.getValue(counter).addAndGet(delta)

    fun onRequest() = add(Counter.INLINE_REQUESTS)

    fun onResponse(
        rawSuggestions: Int,
        autofill: Int,
        platform: Int,
    ) {
        add(Counter.RESPONSES)
        add(Counter.SUGGESTIONS, rawSuggestions.toLong())
        add(Counter.AUTOFILL_LANE, autofill.toLong())
        add(Counter.PLATFORM_LANE, platform.toLong())
    }

    fun onInflation(ready: Int) = add(Counter.INFLATED, ready.toLong())

    fun onWithdrawn() = add(Counter.WITHDRAWN)

    // Clipboard capture counters. None of these takes any clip content.

    fun onCaptureAttempt() = add(Counter.CAPTURE_ATTEMPTS)

    fun onSelfWriteSkip() = add(Counter.SELF_WRITE_SKIPS)

    fun onGateDrop() = add(Counter.GATE_DROPS)

    fun onSensitiveDrop() = add(Counter.SENSITIVE_DROPS)

    fun onSensitiveMediaDrop() = add(Counter.SENSITIVE_MEDIA_DROPS)

    fun onStoredText() = add(Counter.STORED_TEXT)

    fun onStoredImage() = add(Counter.STORED_IMAGE)

    fun onStoredFiles(count: Int = 1) = add(Counter.STORED_FILES, count.toLong())

    fun onStoredPrivate() = add(Counter.STORED_PRIVATE)

    fun onAbortedTextCapture() = add(Counter.ABORTED_TEXT)

    fun onAbortedImageCapture() = add(Counter.ABORTED_IMAGE)

    /** Clears every counter. Tests only; a debug summary never resets. */
    fun reset() {
        counters.values.forEach { it.set(0) }
    }

    fun summary(): String =
        Counter.entries.joinToString(separator = " ") { counter ->
            "${counter.key}=${counters.getValue(counter).get()}"
        }
}
