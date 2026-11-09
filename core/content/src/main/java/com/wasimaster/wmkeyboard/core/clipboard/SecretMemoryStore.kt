package com.wasimaster.wmkeyboard.core.clipboard

/**
 * The process-memory home for clips that must never reach disk: passwords,
 * one-time codes, and anything else the classifier marks sensitive.
 *
 * The store is deliberately not a second [ClipboardStore]. It has no file, no
 * images directory, no pin, no tags and no search index. Its entries are
 * dropped on expiry, on lock, on clear and when the process dies. Expiry
 * removes the reference; Kotlin strings are not zeroized, so the guarantee is
 * "no longer reachable or pasteable", not "memory wiped".
 *
 * [ClipboardStore] owns one instance and merges [items] into its own list, so
 * the panel and paste paths keep one list while the persistence boundary stays
 * separate.
 */
internal class SecretMemoryStore(
    /** 0 means no expiry; the caller then uses the normal history expiry. */
    var expiryMillis: Long = ClipboardStore.DEFAULT_SENSITIVE_EXPIRY_MILLIS,
 ) {
    private val entries = ArrayList<ClipItem>()
    private val maxEntries = MAX_SECRET_ENTRIES
    private val maxEntryChars = MAX_SECRET_ENTRY_CHARS

    /** Adds or refreshes [item], which must already be marked sensitive. */
    fun add(item: ClipItem, now: Long): ClipItem {
        prune(now)
        entries.removeAll { it.kind.isTextual && item.kind.isTextual && it.text == item.text }
        val capped = if (item.text.length > maxEntryChars) {
            item.copy(
                text = capClipText(item.text, maxEntryChars),
                htmlText = null,
                kind = if (item.kind == ClipKind.HTML) ClipKind.TEXT else item.kind,
                mimeType = if (item.kind == ClipKind.HTML) "text/plain" else item.mimeType,
            )
        } else {
            item
        }
        entries.add(0, capped.copy(sensitive = true, timestamp = minOf(capped.timestamp, now)))
        while (entries.size > maxEntries) entries.removeAt(entries.lastIndex)
        return entries.first()
    }

    /** A copy of the live entries, expired ones removed. */
    fun items(now: Long): List<ClipItem> {
        prune(now)
        return entries.toList()
    }

    /** Finds a secret with the same text, so a clear re-copy cannot bypass it. */
    fun findTextual(text: String, now: Long = System.currentTimeMillis()): ClipItem? {
        prune(now)
        return entries.firstOrNull { it.kind.isTextual && it.text == text }
    }

    /** Makes [id] the newest secret, as a fresh copy would. */
    fun bump(id: Long, now: Long): ClipItem? {
        prune(now)
        val item = entries.firstOrNull { it.id == id }
        if (item == null) return null
        entries.remove(item)
        val bumped = item.copy(timestamp = now)
        entries.add(0, bumped)
        return bumped
    }

    fun remove(id: Long): Boolean {
        val item = entries.firstOrNull { it.id == id }
        if (item == null) return false
        entries.remove(item)
        return true
    }

    /** Clears every secret. Returns whether anything was there. */
    fun clear(): Boolean {
        val had = entries.isNotEmpty()
        entries.clear()
        return had
    }

    fun maxId(): Long = entries.maxOfOrNull { it.id } ?: 0L

    /** Drops entries past their TTL; callers that only need that can say so. */
    fun prune(now: Long) {
        if (expiryMillis <= 0) return
        // A timestamp ahead of now means the clock moved backwards. Treat it
        // as expired rather than letting a secret outlive its TTL until the
        // clock catches up.
        entries.removeAll { it.timestamp > now || now - it.timestamp >= expiryMillis }
    }

    companion object {
        const val MAX_SECRET_ENTRIES = 20
        const val MAX_SECRET_ENTRY_CHARS = 32_768
    }
}
