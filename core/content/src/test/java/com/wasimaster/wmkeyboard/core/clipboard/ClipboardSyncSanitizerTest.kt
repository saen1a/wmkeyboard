package com.wasimaster.wmkeyboard.core.clipboard

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The sanitizer runs on raw JSON before the store decodes it, so every crafted
 * shape a bundle can carry is walked here: a single bad item must drop itself,
 * never the whole history.
 */
class ClipboardSyncSanitizerTest {

    private fun item(pairs: Map<String, JsonElement>): JsonObject = JsonObject(pairs)

    private fun baseText(
        id: Long = 1L,
        timestamp: Long = 1_000L,
        text: String = "hello",
        kind: String = "TEXT",
    ): Map<String, JsonElement> = mapOf(
        "id" to JsonPrimitive(id),
        "timestamp" to JsonPrimitive(timestamp),
        "text" to JsonPrimitive(text),
        "kind" to JsonPrimitive(kind),
    )

    private fun bundle(vararg items: JsonObject): JsonObject =
        JsonObject(mapOf("items" to JsonArray(items.toList())))

    private fun survivors(result: JsonObject): List<JsonObject> =
        result.getValue("items").jsonArray.map { it.jsonObject }

    @Test
    fun `benign text survives`() {
        val result = ClipboardSyncSanitizer.sanitize(bundle(item(baseText())))
        assertEquals(1, survivors(result).size)
        assertEquals("hello", survivors(result).single().getValue("text").let { (it as JsonPrimitive).content })
    }

    @Test
    fun `a sensitive item is dropped`() {
        val result = ClipboardSyncSanitizer.sanitize(
            bundle(item(baseText() + ("sensitive" to JsonPrimitive(true)))),
        )
        assertTrue(survivors(result).isEmpty())
    }

    @Test
    fun `non-textual kinds are dropped`() {
        for (kind in listOf("IMAGE", "FILE", "FOLDER", "VIDEO")) {
            val result = ClipboardSyncSanitizer.sanitize(
                bundle(item(baseText(kind = kind) + ("text" to JsonPrimitive("x")))),
            )
            assertTrue("kind $kind must be dropped", survivors(result).isEmpty())
        }
    }

    @Test
    fun `file metadata fields are dropped`() {
        val metadata = listOf(
            "imagePath" to JsonPrimitive("/data/secret.png"),
            "uriString" to JsonPrimitive("content://files/1"),
            "fileName" to JsonPrimitive("report.pdf"),
            "linkPreview" to JsonObject(mapOf("title" to JsonPrimitive("t"))),
            "fileSize" to JsonPrimitive(4_096L),
            "durationMs" to JsonPrimitive(64_000L),
        )
        for ((key, value) in metadata) {
            val result = ClipboardSyncSanitizer.sanitize(bundle(item(baseText() + (key to value))))
            assertTrue("$key must be dropped", survivors(result).isEmpty())
        }
    }

    @Test
    fun `negative file size and duration are allowed`() {
        val result = ClipboardSyncSanitizer.sanitize(
            bundle(item(baseText() + ("fileSize" to JsonPrimitive(-1L)) + ("durationMs" to JsonPrimitive(-1L)))),
        )
        assertEquals(1, survivors(result).size)
    }

    @Test
    fun `missing id or timestamp drops only that item`() {
        val noId = JsonObject(baseText().minus("id"))
        val noTimestamp = JsonObject(baseText().minus("timestamp"))
        val result = ClipboardSyncSanitizer.sanitize(bundle(item(noId), item(noTimestamp), item(baseText(id = 2L))))
        val kept = survivors(result)
        assertEquals(1, kept.size)
        assertEquals(2L, (kept.single().getValue("id") as JsonPrimitive).content.toLong())
    }

    @Test
    fun `oversized text is dropped`() {
        val tooLong = "x".repeat(ClipboardStore.HARD_MAX_TEXT_CHARS + 1)
        val result = ClipboardSyncSanitizer.sanitize(bundle(item(baseText(text = tooLong))))
        assertTrue(survivors(result).isEmpty())
    }

    @Test
    fun `a wrongly typed field drops only that item`() {
        val badFileSize = item(baseText(id = 10L) + ("fileSize" to JsonPrimitive("abc")))
        val badDuration = item(baseText(id = 11L) + ("durationMs" to JsonPrimitive("oops")))
        val badId = item(
            baseText().minus("id") + ("id" to JsonObject(mapOf("nested" to JsonPrimitive(1)))),
        )
        val survivor = item(baseText(id = 12L, text = "still here"))
        val kept = survivors(
            ClipboardSyncSanitizer.sanitize(bundle(badFileSize, badDuration, badId, survivor)),
        )
        assertEquals(1, kept.size)
        assertEquals("still here", (kept.single().getValue("text") as JsonPrimitive).content)
    }

    @Test
    fun `secret-shaped text is dropped`() {
        // A bare one-time code, and a generated-looking token.
        val otp = ClipboardSyncSanitizer.sanitize(bundle(item(baseText(text = "483920"))))
        assertTrue(survivors(otp).isEmpty())
        val token = ClipboardSyncSanitizer.sanitize(bundle(item(baseText(text = "Abc123!@#xyz"))))
        assertTrue(survivors(token).isEmpty())
    }

    @Test
    fun `a malformed element becomes an empty bundle`() {
        val fromString = ClipboardSyncSanitizer.sanitize(JsonPrimitive("not a bundle"))
        val fromMissing = ClipboardSyncSanitizer.sanitize(JsonObject(emptyMap()))
        assertTrue(survivors(fromString).isEmpty())
        assertTrue(survivors(fromMissing).isEmpty())
    }

    @Test
    fun `a non-textual clear item stays but a sensitive one does not`() {
        val image = item(baseText(kind = "IMAGE") + ("imagePath" to JsonPrimitive("/p.png")))
        val sensitive = item(baseText() + ("sensitive" to JsonPrimitive(true)))
        val text = item(baseText())
        assertTrue(ClipboardSyncSanitizer.isNonTextualClearItem(image))
        assertFalse(ClipboardSyncSanitizer.isNonTextualClearItem(sensitive))
        assertFalse(ClipboardSyncSanitizer.isNonTextualClearItem(text))
    }
}
