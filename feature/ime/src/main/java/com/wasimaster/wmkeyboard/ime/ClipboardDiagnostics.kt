package com.wasimaster.wmkeyboard.ime

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
    private val requests = AtomicLong()
    private val responses = AtomicLong()
    private val suggestions = AtomicLong()
    private val autofillLane = AtomicLong()
    private val platformLane = AtomicLong()
    private val inflated = AtomicLong()
    private val withdrawn = AtomicLong()

    private val captureAttempts = AtomicLong()
    private val selfWriteSkips = AtomicLong()
    private val gateDrops = AtomicLong()
    private val sensitiveDrops = AtomicLong()
    private val sensitiveMediaDrops = AtomicLong()
    private val storedText = AtomicLong()
    private val storedImage = AtomicLong()
    private val storedFiles = AtomicLong()
    private val storedPrivate = AtomicLong()
    private val abortedTextCaptures = AtomicLong()
    private val abortedImageCaptures = AtomicLong()

    fun onRequest() = requests.incrementAndGet()

    fun onResponse(
        rawSuggestions: Int,
        autofill: Int,
        platform: Int,
    ) {
        responses.incrementAndGet()
        suggestions.addAndGet(rawSuggestions.toLong())
        autofillLane.addAndGet(autofill.toLong())
        platformLane.addAndGet(platform.toLong())
    }

    fun onInflation(ready: Int) = inflated.addAndGet(ready.toLong())

    fun onWithdrawn() = withdrawn.incrementAndGet()

    // Clipboard capture counters. None of these takes any clip content.

    fun onCaptureAttempt() = captureAttempts.incrementAndGet()

    fun onSelfWriteSkip() = selfWriteSkips.incrementAndGet()

    fun onGateDrop() = gateDrops.incrementAndGet()

    fun onSensitiveDrop() = sensitiveDrops.incrementAndGet()

    fun onSensitiveMediaDrop() = sensitiveMediaDrops.incrementAndGet()

    fun onStoredText() = storedText.incrementAndGet()

    fun onStoredImage() = storedImage.incrementAndGet()

    fun onStoredFiles(count: Int = 1) = storedFiles.addAndGet(count.toLong())

    fun onStoredPrivate() = storedPrivate.incrementAndGet()

    fun onAbortedTextCapture() = abortedTextCaptures.incrementAndGet()

    fun onAbortedImageCapture() = abortedImageCaptures.incrementAndGet()

    /** Clears every counter. Tests only; a debug summary never resets. */
    fun reset() {
        requests.set(0)
        responses.set(0)
        suggestions.set(0)
        autofillLane.set(0)
        platformLane.set(0)
        inflated.set(0)
        withdrawn.set(0)
        captureAttempts.set(0)
        selfWriteSkips.set(0)
        gateDrops.set(0)
        sensitiveDrops.set(0)
        sensitiveMediaDrops.set(0)
        storedText.set(0)
        storedImage.set(0)
        storedFiles.set(0)
        storedPrivate.set(0)
        abortedTextCaptures.set(0)
        abortedImageCaptures.set(0)
    }

    fun summary(): String =
        "inline_requests=${requests.get()} responses=${responses.get()} " +
            "suggestions=${suggestions.get()} autofill=${autofillLane.get()} " +
            "platform=${platformLane.get()} inflated=${inflated.get()} " +
            "withdrawn=${withdrawn.get()} " +
            "capture_attempts=${captureAttempts.get()} " +
            "self_write_skips=${selfWriteSkips.get()} gate_drops=${gateDrops.get()} " +
            "sensitive_drops=${sensitiveDrops.get()} " +
            "sensitive_media_drops=${sensitiveMediaDrops.get()} " +
            "stored_text=${storedText.get()} stored_image=${storedImage.get()} " +
            "stored_file=${storedFiles.get()} stored_private=${storedPrivate.get()} " +
            "aborted_text=${abortedTextCaptures.get()} " +
            "aborted_image=${abortedImageCaptures.get()}"
}
