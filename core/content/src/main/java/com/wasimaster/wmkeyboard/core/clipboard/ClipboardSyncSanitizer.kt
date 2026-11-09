package com.wasimaster.wmkeyboard.core.clipboard

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull

/**
 * Cleans a clipboard bundle before it is decoded or written, so one bad item
 * cannot take the whole history with it.
 *
 * A bundle arrives as raw JSON (`{"items":[...]}`): a ConfigBackup section, a
 * sync payload, a file another install wrote. It is not trusted. The store's
 * own decoder needs an `id` and a `timestamp` on every item and would reject
 * the whole file if one is missing, so the raw JSON is filtered here first,
 * item by item, and only what survives reaches the typed decoder. A crafted or
 * corrupt item is dropped on its own; the bounds are the same ones
 * [ClipboardStore] keeps for clips it takes in.
 *
 * The bundle carries text, HTML and link clips only. Image, file, folder and
 * video clips point at bytes or content URIs that only exist on the source
 * device, so carrying them across would just leave broken entries. Anything
 * sensitive or shaped like a secret is dropped too: a bundle is the one place
 * a password that expires in minutes would otherwise live forever.
 *
 * Pure and Android-free: no Context, no store, no I/O. It only reads and
 * rewrites a [JsonElement].
 */
object ClipboardSyncSanitizer {

    /** Clip kinds worth carrying: the ones whose content travels as text. */
    private val TEXTUAL_KINDS = ClipKind.entries.filter { it.isTextual }.map { it.name }.toSet()

    /** The most characters a synced clip may keep; the store's hard cap. */
    private val MAX_TEXT_CHARS = ClipboardStore.HARD_MAX_TEXT_CHARS

    /** The most bytes of rich-text markup a synced clip may carry. */
    private val MAX_HTML_BYTES = ClipboardStore.HARD_MAX_HTML_BYTES

    /**
     * The bundle as it may be persisted: only the items that pass
     * [isPortableItem]. A non-object element, or one with no `items` array,
     * becomes an empty `{"items":[]}` rather than an error, so one malformed
     * section cannot sink a restore.
     */
    fun sanitize(element: JsonElement): JsonObject {
        val obj = element as? JsonObject ?: return emptyBundle()
        val items = obj["items"] as? JsonArray ?: return emptyBundle()
        val seenIds = HashSet<Long>()
        val kept = items.filter { item ->
            if (!isPortableItem(item)) return@filter false
            // Two items with one id would collide in the store; keep the first
            // and drop the later duplicate.
            val id = ((item as? JsonObject)?.get("id") as? JsonPrimitive)
                ?.contentOrNull?.toLongOrNull() ?: return@filter false
            seenIds.add(id)
        }
        return buildJsonObject { put("items", JsonArray(kept)) }
    }

    /**
     * Whether [item] is a text/HTML/link clip that may travel: not sensitive,
     * not shaped like a secret, carrying none of the file metadata a textual
     * clip never needs, and complete enough for the store's decoder.
     */
    fun isPortableItem(item: JsonElement): Boolean {
        val entry = item as? JsonObject ?: return false
        val kind = entry.rawKind()
        if (entry.rawSensitive() || kind !in TEXTUAL_KINDS) return false
        val text = (entry["text"] as? JsonPrimitive)?.contentOrNull ?: return false
        // A textual clip never needs file paths or URIs. Accepting them from a
        // bundle would let a crafted item make restore/prune delete a file.
        if ((entry["imagePath"] as? JsonPrimitive)?.contentOrNull != null) return false
        if ((entry["uriString"] as? JsonPrimitive)?.contentOrNull != null) return false
        if ((entry["fileName"] as? JsonPrimitive)?.contentOrNull != null) return false
        if (entry["linkPreview"] != null && entry["linkPreview"] !is JsonNull) return false
        if (((entry["fileSize"] as? JsonPrimitive)?.contentOrNull?.toLongOrNull() ?: -1L) > 0) return false
        if (((entry["durationMs"] as? JsonPrimitive)?.contentOrNull?.toLongOrNull() ?: -1L) > 0) return false
        // A clip past the store's own cap is trimmed there, never carried whole.
        if (text.length > MAX_TEXT_CHARS) return false
        // Markup past the store's hard byte cap is not carried either.
        val html = (entry["htmlText"] as? JsonPrimitive)?.contentOrNull
        if (html != null && html.toByteArray(Charsets.UTF_8).size > MAX_HTML_BYTES) return false
        // The store's decoder needs an id and a timestamp; a missing or wrongly
        // typed one would make the whole history file unreadable, so such an
        // item is dropped alone.
        val hasId = (entry["id"] as? JsonPrimitive)?.contentOrNull?.toLongOrNull() != null
        val hasTimestamp = (entry["timestamp"] as? JsonPrimitive)?.contentOrNull?.toLongOrNull() != null
        // The checks above read a few fields leniently, so a value of the
        // wrong type (`fileSize:"abc"`, `durationMs:"oops"`) still passes
        // them and then fails the store's strict decode, taking the whole
        // history with it. Decode this item alone with the store's serializer
        // and settings; only a shape the typed decoder accepts may travel.
        return hasId && hasTimestamp && !ClipSensitivity.looksSensitive(text) &&
            runCatching { ClipboardJson.decodeFromString<ClipItem>(entry.toString()) }.isSuccess
    }

    /**
     * Whether [item] is a local clip that must stay on this phone when a synced
     * bundle replaces the textual ones: clear, and not a text/HTML/link clip.
     * Image, file, folder and video clips never sync, so a sync must not delete
     * them; a sensitive clip is dropped instead, never carried forward.
     */
    fun isNonTextualClearItem(item: JsonElement): Boolean {
        val entry = item as? JsonObject ?: return false
        return !entry.rawSensitive() && entry.rawKind() !in TEXTUAL_KINDS
    }

    /**
     * [incoming] clips made unique by id against [stays], which keep their own.
     * An incoming id that collides with a local non-text clip, or with an
     * incoming clip already seen, is renumbered above the highest id in use.
     * This is the whole merge boundary, so settings code only calls it.
     */
    fun deconflictIds(
        incoming: List<JsonElement>,
        stays: List<JsonElement>,
    ): List<JsonElement> {
        val used = HashSet<Long>()
        stays.forEach { entry -> (entry as? JsonObject)?.clipId()?.let(used::add) }
        var next = (used.maxOrNull() ?: 0L) + 1L
        return incoming.map { entry ->
            val id = (entry as? JsonObject)?.clipId()
            if (id != null && used.add(id)) return@map entry
            var fresh = next
            while (!used.add(fresh)) fresh++
            next = fresh + 1L
            (entry as JsonObject).withClipId(fresh)
        } + stays
    }

    private fun JsonObject.clipId(): Long? =
        (this["id"] as? JsonPrimitive)?.contentOrNull?.toLongOrNull()

    private fun JsonObject.withClipId(id: Long): JsonObject =
        JsonObject(this + ("id" to JsonPrimitive(id)))

    private fun JsonObject.rawKind(): String =
        (this["kind"] as? JsonPrimitive)?.contentOrNull ?: ClipKind.TEXT.name

    private fun JsonObject.rawSensitive(): Boolean =
        (this["sensitive"] as? JsonPrimitive)?.booleanOrNull == true

    private fun emptyBundle(): JsonObject = buildJsonObject { put("items", JsonArray(emptyList())) }
}
