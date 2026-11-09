package com.wasimaster.wmkeyboard.core.settings

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import com.wasimaster.wmkeyboard.core.util.SnapshotFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * A sync replaces the text clips but keeps local non-text clips. The combined
 * history must never carry two clips with one id, which is what the store
 * would otherwise collapse on load.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SyncedClipboardIdsTest {

    private fun clip(id: Long, text: String): JsonObject = buildJsonObject {
        put("id", JsonPrimitive(id))
        put("timestamp", JsonPrimitive(1_000L))
        put("text", JsonPrimitive(text))
        put("kind", JsonPrimitive("TEXT"))
    }

    private fun fileClip(id: Long, uri: String, name: String): JsonObject = buildJsonObject {
        put("id", JsonPrimitive(id))
        put("timestamp", JsonPrimitive(1_000L))
        put("text", JsonPrimitive(name))
        put("kind", JsonPrimitive("FILE"))
        put("uriString", JsonPrimitive(uri))
        put("fileName", JsonPrimitive(name))
        put("mimeType", JsonPrimitive("application/pdf"))
    }

    private fun idOf(entry: JsonObject): Long =
        entry.getValue("id").jsonPrimitive.content.toLong()

    private fun textOf(entry: JsonObject): String =
        entry.getValue("text").jsonPrimitive.content

    @Test
    fun `colliding incoming ids are renumbered and both clips stay`() = runBlocking {
        val context = RuntimeEnvironment.getApplication()
        val history = File(context.filesDir, "clipboard/history.json")
        history.parentFile?.mkdirs()
        // A local file clip owns id 1 and must keep it.
        history.writeText(
            buildJsonObject {
                put("version", JsonPrimitive(2))
                put("items", JsonArray(listOf(fileClip(id = 1, uri = "content://files/1", name = "report.pdf"))))
            }.toString(),
        )

        // The incoming text clips also carry id 1 (and each other's ids).
        val portable = buildJsonObject {
            put("items", JsonArray(listOf(clip(id = 1, text = "hello"), clip(id = 1, text = "world"))))
        }
        SettingsRepository(context).applySyncedClipboard(portable)

        val written = Json.parseToJsonElement(history.readText()).jsonObject
        val items = written.getValue("items").jsonArray.map { it.jsonObject }
        assertEquals(3, items.size)
        // Every id is unique: the local id is kept, incoming ones moved above.
        assertEquals(3, items.map(::idOf).toSet().size)
        assertEquals(1L, items.first { textOf(it) == "report.pdf" }.let(::idOf))
        assertEquals(setOf("hello", "world", "report.pdf"), items.map(::textOf).toSet())
        assertEquals(3L, items.map(::idOf).max())
    }

    @Test
    fun `a sync reads the history after it gets the path lock, so an external write is kept`() {
        val context = RuntimeEnvironment.getApplication()
        val history = File(context.filesDir, "clipboard/history.json")
        history.parentFile?.mkdirs()
        val repository = SettingsRepository(context)
        val portable = buildJsonObject {
            put("items", JsonArray(listOf(clip(id = 1, text = "hello"))))
        }

        val locked = CountDownLatch(1)
        val release = CountDownLatch(1)
        val applied = CountDownLatch(1)
        val holder = Thread {
            SnapshotFile.withLock(history) {
                locked.countDown()
                release.await()
            }
        }
        val applier = Thread {
            runBlocking { repository.applySyncedClipboard(portable) }
            applied.countDown()
        }
        holder.start()
        assertTrue(locked.await(5, TimeUnit.SECONDS))
        applier.start()
        // While the path lock is held, this test writes a non-text clip
        // straight to the history file without going through the store or the
        // lock. It models an uncoordinated external write, not an IME save; a
        // sync that read before taking the lock would miss it and overwrite it.
        history.writeText(
            buildJsonObject {
                put("version", JsonPrimitive(2))
                put("items", JsonArray(listOf(fileClip(id = 1, uri = "content://files/1", name = "report.pdf"))))
            }.toString(),
        )
        assertFalse("the sync must wait for the path lock", applied.await(200, TimeUnit.MILLISECONDS))
        release.countDown()
        assertTrue(applied.await(5, TimeUnit.SECONDS))
        holder.join()
        applier.join()

        val written = Json.parseToJsonElement(history.readText()).jsonObject
        val items = written.getValue("items").jsonArray.map { it.jsonObject }
        // The uncoordinated write made while the sync waited is read and preserved.
        assertEquals(2, items.size)
        assertEquals(setOf("hello", "report.pdf"), items.map(::textOf).toSet())
    }
}
