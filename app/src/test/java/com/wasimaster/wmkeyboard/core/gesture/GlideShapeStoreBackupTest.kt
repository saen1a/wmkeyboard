package com.wasimaster.wmkeyboard.core.gesture

import java.io.File
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * The backup path must stay in the v2 JSON format older builds understand,
 * even though the runtime store is binary.
 */
class GlideShapeStoreBackupTest {

    @get:Rule
    val temp = TemporaryFolder()

    private val layout = 0x5e1fL

    private fun shape(value: Int): ByteArray = ByteArray(GlideShapeStore.POINTS) { value.toByte() }

    @Test
    fun `a binary store exports v2 JSON and imports back`() {
        val file = File(temp.root, "glide_shapes.json")
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, shape(-40)), "hello")
        store.save()

        val backup = GlideShapeStore.exportJson(file) ?: error("no backup")
        val parsed = Json.parseToJsonElement(backup).jsonObject
        assertEquals(2, parsed["v"]!!.jsonPrimitive.int)
        assertEquals(1, parsed["layouts"]!!.jsonObject.size)
        assertTrue(parsed["layouts"]!!.jsonObject["5e1f"]!!.jsonObject.containsKey("hello"))

        val restoredFile = File(temp.root, "restored.json")
        assertTrue(GlideShapeStore.importJson(restoredFile, backup))
        val restored = GlideShapeStore(restoredFile)
        assertEquals(1, restored.countFor("hello"))
        assertEquals(0f, restored.forLayout(layout)!!.minDistance("hello", shape(-40)), 1e-6f)
    }

    @Test
    fun `a JSON store exports unchanged`() {
        val file = File(temp.root, "old.json")
        val points = shape(12).joinToString("") { "%02x".format(it) }
        val text =
            """{"v":2,"tick":3,"layouts":{"5e1f":{"hello":{"t":3,"s":[{"p":"$points","a":1,"r":0}]}}}}"""
        file.writeText(text)
        assertEquals(text, GlideShapeStore.exportJson(file))
    }

    @Test
    fun `a v064 JSON backup imports and stays v064 readable`() {
        // 0.6.4 omitted every default, including the `v` field itself. A bundle
        // made there embeds this text verbatim; import must accept it and a
        // later export must hand it back in a 0.6.4 build's format.
        val points = shape(12).joinToString("") { "%02x".format(it) }
        val text = """{"tick":3,"layouts":{"5e1f":{"hello":{"t":3,"s":[{"p":"$points"}]}}}}"""
        val file = File(temp.root, "from-0.6.4.json")
        assertTrue(GlideShapeStore.importJson(file, text))
        assertEquals(text, GlideShapeStore.exportJson(file))
        val restored = GlideShapeStore(file)
        assertEquals(1, restored.countFor("hello"))
        assertEquals(0f, restored.forLayout(layout)!!.shapeDistance("hello", 0, shape(12)), 1e-6f)
    }
}
