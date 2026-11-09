package com.wasimaster.wmkeyboard.ime

/**
 * Holds a check-up correction that arrives while the replay that will create
 * the record is still running. Replays for the same word can overlap, so the
 * in-flight keys are reference-counted: [finish] only drains a key when its
 * last replay ends. A correction that arrives after that is applied directly
 * by [remember]'s caller and is not retained here.
 */
internal class CheckupCorrectionBuffer {

    data class Correction(val rejected: String, val chosen: String?)

    private val lock = Any()
    private val inFlight = HashMap<String, Int>()
    private val pending = HashMap<String, Correction>()

    /** Marks [keys] as being replayed; overlapping calls increment their count. */
    fun begin(keys: Collection<String>) {
        synchronized(lock) {
            keys.forEach { key -> inFlight[key] = (inFlight[key] ?: 0) + 1 }
        }
    }

    /**
     * Keeps [correction] for [key] only while a replay owns it. Returns true
     * when it was retained, so the caller can skip its immediate apply; false
     * means the caller must apply it directly.
     */
    fun remember(key: String, correction: Correction): Boolean {
        return synchronized(lock) {
            if ((inFlight[key] ?: 0) > 0) {
                pending[key] = correction
                true
            } else {
                false
            }
        }
    }

    /**
     * Ends one replay for [keys] and returns the corrections whose last
     * replay just finished. The caller applies them after this returns.
     */
    fun finish(keys: Collection<String>): List<Correction> {
        return synchronized(lock) {
            val out = ArrayList<Correction>(keys.size)
            keys.forEach { key ->
                val next = (inFlight[key] ?: 0) - 1
                if (next <= 0) {
                    inFlight.remove(key)
                    pending.remove(key)?.let(out::add)
                } else {
                    inFlight[key] = next
                }
            }
            out
        }
    }
}
