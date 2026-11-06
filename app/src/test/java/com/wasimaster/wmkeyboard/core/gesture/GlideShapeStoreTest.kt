package com.wasimaster.wmkeyboard.core.gesture

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/** [GlideShapeStore], how the user draws each word (issue #52). */
class GlideShapeStoreTest {

    @get:Rule
    val temp = TemporaryFolder()

    private fun file(): File = File(temp.root, "learning/glide_shapes.json")

    /** A shape whose every coordinate is [value], in quantised units. */
    private fun flat(value: Int): ByteArray = ByteArray(GlideShapeStore.POINTS) { value.toByte() }

    /** A shape [away] quantised units off [base] on every coordinate. */
    private fun near(base: ByteArray, away: Int): ByteArray = ByteArray(base.size) { (base[it] + away).toByte() }

    private val layout = 0x5e1fL

    @Test
    fun `a settled shape is kept and found`() {
        val store = GlideShapeStore(null)
        assertNull(store.forLayout(layout))
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        val source = store.forLayout(layout) ?: error("no source")
        assertEquals(0f, source.minDistance("Hello", flat(10)), 1e-6f)
        assertEquals(-1f, source.minDistance("help", flat(10)), 0f)
        assertNull(store.forLayout(layout + 1))
        assertEquals(1, store.countFor("hello"))
    }

    @Test
    fun `a nearby draw blends in and a far one is a new way of drawing the word`() {
        val store = GlideShapeStore(null)
        val base = flat(10)
        store.learn(GlideShapeSample(layout, base), "hello")
        // Two quantised units is a fifth of a key width: the same shape.
        store.learn(GlideShapeSample(layout, near(base, 2)), "hello")
        assertEquals(1, store.countFor("hello"))
        // Blended halfway: one unit off on both axes of every point.
        assertEquals(kotlin.math.sqrt(2f) / GlideShapeStore.QUANT, store.forLayout(layout)!!.minDistance("hello", base), 1e-6f)
        // Forty units is four key widths off: another shape.
        store.learn(GlideShapeSample(layout, near(base, 40)), "hello")
        assertEquals(2, store.countFor("hello"))
        // And a fourth distinct shape replaces the least accepted.
        store.learn(GlideShapeSample(layout, near(base, 80)), "hello")
        store.learn(GlideShapeSample(layout, near(base, -60)), "hello")
        assertEquals(GlideShapeStore.DEFAULT_SHAPES_PER_WORD, store.countFor("hello"))
    }

    @Test
    fun `a rejected shape goes once rejected more than accepted`() {
        val store = GlideShapeStore(null)
        val base = flat(10)
        store.learn(GlideShapeSample(layout, base), "hello")
        assertFalse(store.reject(layout, "hello", near(base, 100)))
        assertTrue(store.reject(layout, "hello", near(base, 1)))
        assertEquals(1, store.countFor("hello"))
        assertTrue(store.reject(layout, "hello", near(base, 1)))
        assertEquals(0, store.countFor("hello"))
        assertTrue(store.isEmpty())
    }

    @Test
    fun `words near a draw come nearest first`() {
        val store = GlideShapeStore(null)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.learn(GlideShapeSample(layout, flat(14)), "help")
        store.learn(GlideShapeSample(layout, flat(90)), "world")
        // A key width is QUANT units: hello sits 0.14 key widths off the draw,
        // help 0.42 and world nearly eleven.
        val near = store.forLayout(layout)!!.wordsNear(flat(11), radius = 0.5f, limit = 8)
        assertEquals(listOf("hello", "help"), near)
        assertEquals(listOf("hello"), store.forLayout(layout)!!.wordsNear(flat(11), radius = 0.5f, limit = 1))
    }

    @Test
    fun `forget takes every layout's shapes and the file survives a round trip`() {
        val store = GlideShapeStore(file())
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.learn(GlideShapeSample(layout + 1, flat(20)), "hello")
        store.learn(GlideShapeSample(layout, flat(30)), "world")
        store.save()
        val reopened = GlideShapeStore(file())
        assertEquals(2, reopened.countFor("hello"))
        assertEquals(0f, reopened.forLayout(layout + 1)!!.minDistance("hello", flat(20)), 1e-6f)
        assertTrue(reopened.forget("hello"))
        assertEquals(0, reopened.countFor("hello"))
        assertEquals(1, reopened.countFor("world"))
        assertFalse(reopened.forget("hello"))
    }

    @Test
    fun `a file from another version starts empty and clear deletes the file`() {
        file().parentFile?.mkdirs()
        file().writeText("""{"v":2,"tick":5,"layouts":{"5e1f":{"hello":{"t":5,"s":[{"p":"00","a":1,"r":0}]}}}}""")
        assertTrue(GlideShapeStore(file()).isEmpty())
        val store = GlideShapeStore(file())
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        assertTrue(file().exists())
        store.clear()
        assertFalse(file().exists())
        assertTrue(store.isEmpty())
    }

    @Test
    fun `a valid v2 JSON snapshot still loads`() {
        val points = flat(10).joinToString("") { "%02x".format(it) }
        file().parentFile?.mkdirs()
        file().writeText(
            """{"v":2,"tick":5,"layouts":{"5e1f":{"hello":{"t":5,"s":[{"p":"$points","a":1,"r":0}]}}}}""",
        )
        val store = GlideShapeStore(file())
        assertEquals(1, store.countFor("hello"))
        assertEquals(0f, store.forLayout(layout)!!.minDistance("hello", flat(10)), 1e-6f)
    }

    @Test
    fun `a word too long in UTF-8 bytes is skipped instead of blocking save`() {
        val points = flat(10).joinToString("") { "%02x".format(it) }
        // 200 UTF-16 units, 400 UTF-8 bytes: under the JSON code-unit cap but
        // over the binary word table's byte cap.
        val tooLong = "😀".repeat(100)
        val file = file()
        file.parentFile?.mkdirs()
        file.writeText(
            """{"layouts":{"5e1f":{"$tooLong":{"s":[{"p":"$points"}]},"hello":{"s":[{"p":"$points"}]}}}}""",
        )
        val store = GlideShapeStore(file)
        assertEquals(0, store.countFor(tooLong))
        assertEquals(1, store.countFor("hello"))

        store.learn(GlideShapeSample(layout, flat(20)), "world")
        store.save()
        val magic = file.readBytes().take(8).joinToString("") { "%02x".format(it) }
        assertEquals("574d4b5300000001", magic)
        val reopened = GlideShapeStore(file)
        assertEquals(1, reopened.countFor("hello"))
        assertEquals(1, reopened.countFor("world"))
    }

    @Test
    fun `a v064 JSON snapshot that omits encoded defaults imports and becomes binary`() {
        // 0.6.4 encoded with `Json { ignoreUnknownKeys = true }`, so `v`, `tick`,
        // `t`, `a` and `r` were omitted whenever they held their default. This
        // is the actual shape of a 0.6.4 store file, and it must load.
        val first = flat(10).joinToString("") { "%02x".format(it) }
        val second = flat(30).joinToString("") { "%02x".format(it) }
        val file = file()
        file.parentFile?.mkdirs()
        file.writeText(
            """{"layouts":{"5e1f":{"hello":{"s":[{"p":"$first","a":3,"r":1},{"p":"$second"}]}}}}""",
        )
        val store = GlideShapeStore(file, autoLoad = false)
        store.loadNow()
        assertEquals(2, store.countFor("hello"))
        val source = store.forLayout(layout) ?: error("no source")
        assertEquals(0f, source.shapeDistance("hello", 0, flat(10)), 1e-6f)
        assertEquals(0f, source.shapeDistance("hello", 1, flat(30)), 1e-6f)

        // A load alone does not rewrite the file; the next mutation saves it as
        // the binary runtime format.
        assertTrue(store.reject(layout, "hello", flat(10)))
        store.save()
        val magic = file.readBytes().take(8).joinToString("") { "%02x".format(it) }
        assertEquals("574d4b5300000001", magic)
        val reopened = GlideShapeStore(file)
        assertEquals(2, reopened.countFor("hello"))
        assertEquals(0f, reopened.forLayout(layout)!!.shapeDistance("hello", 1, flat(30)), 1e-6f)
    }

    @Test
    fun `an oversized JSON file trims to the cap instead of clearing`() {
        val points = flat(10).joinToString("") { "%02x".format(it) }
        val text = buildString {
            append("""{"v":2,"tick":10001,"layouts":{"5e1f":{""")
            for (i in 0..GlideShapeStore.MAX_WORDS) {
                if (i > 0) append(',')
                append(""""word$i":{"t":$i,"s":[{"p":"$points","a":1,"r":0}]}""")
            }
            append("}}}")
        }
        file().parentFile?.mkdirs()
        file().writeText(text)
        val store = GlideShapeStore(file())
        assertEquals(GlideShapeStore.MAX_WORDS, store.wordCount())
        assertEquals(0, store.countFor("word0"))
        assertEquals(1, store.countFor("word${GlideShapeStore.MAX_WORDS}"))
    }

    @Test
    fun `autoLoad false starts empty and loadNow fills the store`() {
        val points = flat(10).joinToString("") { "%02x".format(it) }
        file().parentFile?.mkdirs()
        file().writeText(
            """{"v":2,"tick":5,"layouts":{"5e1f":{"hello":{"t":5,"s":[{"p":"$points","a":1,"r":0}]}}}}""",
        )
        val store = GlideShapeStore(file(), autoLoad = false)
        assertTrue(store.isEmpty())
        assertNull(store.forLayout(layout))
        store.loadNow()
        assertEquals(1, store.countFor("hello"))
    }

    @Test
    fun `a truncated binary snapshot starts empty`() {
        file().parentFile?.mkdirs()
        file().writeBytes(byteArrayOf(0x57, 0x4d, 0x4b, 0x53, 0, 0, 0, 1))
        assertTrue(GlideShapeStore(file()).isEmpty())
    }

    @Test
    fun `a binary snapshot with a damaged payload is preserved as corrupt`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        val bytes = file.readBytes()
        assertTrue("a saved snapshot must have a payload", bytes.size > 40)
        bytes[bytes.size - 1] = (bytes.last().toInt() xor 0x01).toByte()
        file.writeBytes(bytes)
        val reopened = GlideShapeStore(file)
        assertTrue(reopened.isEmpty())
        val corrupt = File(file.parentFile, file.name + ".corrupt")
        assertTrue("a checksum failure must keep the bytes for diagnosis", corrupt.isFile)
        assertEquals(bytes.size.toLong(), corrupt.length())
    }

    @Test
    fun `a damaged header fails the digest`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        val bytes = file.readBytes()
        // Tick is header offset 24, inside the digest-covered range.
        bytes[24] = (bytes[24].toInt() xor 0x01).toByte()
        file.writeBytes(bytes)
        val reopened = GlideShapeStore(file)
        assertTrue(reopened.isEmpty())
        assertTrue(File(file.parentFile, file.name + ".corrupt").isFile)
    }

    @Test
    fun `an unsupported digest algorithm is preserved as corrupt`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        val bytes = file.readBytes()
        // Digest algorithm is header offset 16.
        bytes[16] = 2
        file.writeBytes(bytes)
        val reopened = GlideShapeStore(file)
        assertTrue(reopened.isEmpty())
        assertTrue(File(file.parentFile, file.name + ".corrupt").isFile)
    }

    @Test
    fun `a valid snapshot truncated by one byte is preserved as corrupt`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        val bytes = file.readBytes()
        file.writeBytes(bytes.copyOf(bytes.size - 1))
        val reopened = GlideShapeStore(file)
        assertTrue(reopened.isEmpty())
        assertTrue(File(file.parentFile, file.name + ".corrupt").isFile)
    }

    @Test
    fun `a good backup is used when the live file is damaged`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        store.learn(GlideShapeSample(layout, flat(20)), "world")
        store.save()
        val backup = File(file.parentFile, file.name + ".bak")
        assertTrue("the second save must keep one previous snapshot", backup.isFile)

        val bytes = file.readBytes()
        bytes[bytes.size - 1] = (bytes.last().toInt() xor 0x01).toByte()
        file.writeBytes(bytes)

        val reopened = GlideShapeStore(file)
        // The backup is the first save, so it has "hello" but not "world".
        assertEquals(1, reopened.countFor("hello"))
        assertEquals(0, reopened.countFor("world"))
        assertTrue(File(file.parentFile, file.name + ".corrupt").isFile)

        // The store is dirty after a backup recovery, so a save restores the
        // live file without rotating the damaged one over the backup.
        reopened.save()
        val afterSave = GlideShapeStore(file)
        assertEquals(1, afterSave.countFor("hello"))
        assertTrue(backup.isFile)
    }

    @Test
    fun `export uses the backup when the live file is damaged`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        store.learn(GlideShapeSample(layout, flat(20)), "world")
        store.save()
        val bytes = file.readBytes()
        bytes[bytes.size - 1] = (bytes.last().toInt() xor 0x01).toByte()
        file.writeBytes(bytes)

        val json = GlideShapeStore.exportJson(file) ?: error("no backup export")
        assertTrue(json.contains("hello"))
        assertFalse(json.contains("world"))
    }

    @Test
    fun `clear removes the live file, backup and corrupt copy`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        store.learn(GlideShapeSample(layout, flat(20)), "world")
        store.save()
        val parent = file.parentFile
        val backup = File(parent, file.name + ".bak")
        val corrupt = File(parent, file.name + ".corrupt")
        corrupt.writeText("old")
        assertTrue(backup.isFile)

        store.clear()
        assertFalse(file.exists())
        assertFalse(backup.exists())
        assertFalse(corrupt.exists())
    }

    @Test
    fun `an invalid shape backup is rejected without touching the store`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        store.learn(GlideShapeSample(layout, flat(20)), "world")
        store.save()
        val backup = File(file.parentFile, file.name + ".bak")
        val liveBefore = file.readBytes()
        val backupBefore = backup.readBytes()

        assertFalse(GlideShapeStore.importJson(file, """{"v":3,"layouts":{}}"""))
        assertTrue(liveBefore.contentEquals(file.readBytes()))
        assertTrue(backupBefore.contentEquals(backup.readBytes()))
        val stillThere = GlideShapeStore(file)
        assertEquals(1, stillThere.countFor("hello"))
        assertEquals(1, stillThere.countFor("world"))
    }

    @Test
    fun `importing JSON drops the old binary backup`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.learn(GlideShapeSample(layout, flat(10)), "hello")
        store.save()
        store.learn(GlideShapeSample(layout, flat(20)), "world")
        store.save()
        val backup = File(file.parentFile, file.name + ".bak")
        assertTrue(backup.isFile)

        val points = flat(30).joinToString("") { "%02x".format(it) }
        val text = """{"v":2,"tick":1,"layouts":{"5e1f":{"restored":{"t":1,"s":[{"p":"$points","a":1,"r":0}]}}}}"""
        assertTrue(GlideShapeStore.importJson(file, text))
        assertFalse(backup.exists())
        val restored = GlideShapeStore(file)
        assertEquals(1, restored.countFor("restored"))
        assertEquals(0, restored.countFor("hello"))
    }

    @Test
    fun `a newer binary version is preserved instead of being parsed as JSON`() {
        file().parentFile?.mkdirs()
        // Magic plus version 2; the payload is irrelevant because decode must
        // reject the version before reading it.
        val bytes = byteArrayOf(0x57, 0x4d, 0x4b, 0x53, 0, 0, 0, 2) + ByteArray(24)
        file().writeBytes(bytes)
        val store = GlideShapeStore(file())
        assertTrue(store.isEmpty())
        val corrupt = File(file().parentFile, file().name + ".corrupt")
        assertTrue("a newer binary file must be kept for diagnosis", corrupt.isFile)
        assertEquals(bytes.size.toLong(), corrupt.length())
        assertNull(GlideShapeStore.exportJson(file()))
    }

    @Test
    fun `past the cap the word left alone longest goes`() {
        val store = GlideShapeStore(null)
        store.learn(GlideShapeSample(layout, flat(1)), "first")
        for (i in 0 until GlideShapeStore.MAX_WORDS - 1) store.learn(GlideShapeSample(layout, flat(2)), "word$i")
        assertEquals(GlideShapeStore.MAX_WORDS, store.wordCount())
        // Touching "first" makes it the newest; the next word evicts word0.
        store.learn(GlideShapeSample(layout, flat(1)), "first")
        store.learn(GlideShapeSample(layout, flat(3)), "newest")
        assertEquals(GlideShapeStore.MAX_WORDS, store.wordCount())
        assertEquals(1, store.countFor("first"))
        assertEquals(0, store.countFor("word0"))
    }

    @Test
    fun `json and binary loads keep the same shapes under the limit`() {
        val file = file()
        val store = GlideShapeStore(file)
        store.setShapesPerWord(5)
        for (value in listOf(0, 40, 80, 120, -40)) store.learn(GlideShapeSample(layout, flat(value)), "can")
        store.setShapesPerWord(2)
        store.save()

        // The binary arena applies topShapeIndices...
        val binary = GlideShapeStore(file, autoLoad = false).also {
            it.setShapesPerWord(2)
            it.loadNow()
        }
        assertEquals(2, binary.countFor("can"))
        val binarySource = binary.forLayout(layout) ?: error("no source")
        assertEquals(0f, binarySource.shapeDistance("can", 0, flat(0)), 1e-6f)
        assertEquals(0f, binarySource.shapeDistance("can", 1, flat(40)), 1e-6f)
        assertEquals(-1f, binarySource.shapeDistance("can", 2, flat(0)), 0f)

        // ...and a JSON backup read through the fallback must keep the same two.
        val jsonText = GlideShapeStore.exportJson(file) ?: error("no backup")
        val jsonFile = File(temp.root, "restored.json")
        assertTrue(GlideShapeStore.importJson(jsonFile, jsonText))
        val fromJson = GlideShapeStore(jsonFile, autoLoad = false).also {
            it.setShapesPerWord(2)
            it.loadNow()
        }
        assertEquals(2, fromJson.countFor("can"))
        val jsonSource = fromJson.forLayout(layout) ?: error("no source")
        assertEquals(0f, jsonSource.shapeDistance("can", 0, flat(0)), 1e-6f)
        assertEquals(0f, jsonSource.shapeDistance("can", 1, flat(40)), 1e-6f)
        assertEquals(-1f, jsonSource.shapeDistance("can", 2, flat(0)), 0f)
    }

    @Test
    fun `the offset comparison agrees with the copied shape`() {
        val store = GlideShapeStore(null)
        val base = flat(10)
        store.learn(GlideShapeSample(layout, base), "hello")
        store.learn(GlideShapeSample(layout, near(base, 40)), "hello")
        val source = store.forLayout(layout) ?: error("no source")
        val drawn = near(base, 3)
        for (i in 0 until source.countFor("hello")) {
            assertEquals(
                GlideShapeStore.distance(source.shapesOf("hello")[i], drawn),
                source.shapeDistance("hello", i, drawn),
                1e-6f,
            )
        }
    }

    @Test
    fun `a hand that keeps moving away displaces the shape it used to draw`() {
        val store = GlideShapeStore(null)
        // One way of drawing the word, drawn until it is thoroughly established.
        val settled = flat(0)
        repeat(20) { store.learn(GlideShapeSample(layout, settled), "can") }
        assertEquals(1, store.countFor("can"))

        // The hand walks away from it, far enough each time that no two steps
        // merge, so every one arrives as a way of drawing the word in its own
        // right at a single acceptance. Before issue #213 that was unwinnable:
        // each step evicted the step before it while the twenty-deep shape sat
        // in its slot untouched, so the store could never be told the habit had
        // changed however long the user kept drawing the new way.
        for (step in 1..10) store.learn(GlideShapeSample(layout, flat(step * 8)), "can")

        val source = store.forLayout(layout) ?: error("no source")
        assertEquals(GlideShapeStore.DEFAULT_SHAPES_PER_WORD, store.countFor("can"))
        assertTrue(
            "the way the hand stopped drawing must have given up its slot",
            source.minDistance("can", settled) > 0f,
        )
        assertEquals("where the hand ended up must be stored", 0f, source.minDistance("can", flat(80)), 1e-6f)
    }

    @Test
    fun `a long-established shape still follows the hand that draws it`() {
        val drifted = flat(3)
        fun settledThenDrifted(depthCapped: Boolean): Float {
            val store = GlideShapeStore(null)
            // Sixty draws one way, then eight of a drift small enough to merge
            // rather than be kept apart.
            repeat(if (depthCapped) 60 else GlideShapeStore.BLEND_DEPTH, {
                store.learn(GlideShapeSample(layout, flat(0)), "can")
            })
            repeat(8) { store.learn(GlideShapeSample(layout, drifted), "can") }
            return (store.forLayout(layout) ?: error("no source")).minDistance("can", drifted)
        }
        // The point of the cap: how deep the shape already is must stop mattering
        // (issue #213). A mean sixty deep moves by a sixtieth, which is less than
        // the quantised unit the mean is kept in, so it never moves at all.
        assertEquals(
            "a shape drawn sixty times must follow the hand as readily as a new one",
            settledThenDrifted(depthCapped = false),
            settledThenDrifted(depthCapped = true),
            1e-6f,
        )
        assertTrue("and must actually have moved toward it", settledThenDrifted(true) < flatDistance(3))
    }

    @Test
    fun `the number of ways kept per word is the user's, and lowering it loses nothing until a new way arrives`() {
        val store = GlideShapeStore(null)
        store.setShapesPerWord(5)
        // One way drawn four times, then four more far enough apart to be kept apart.
        repeat(4) { store.learn(GlideShapeSample(layout, flat(0)), "can") }
        for (away in listOf(40, 80, -40, -80)) store.learn(GlideShapeSample(layout, flat(away)), "can")
        assertEquals(5, store.countFor("can"))

        // Lowered, the decoder reads only the most accepted...
        store.setShapesPerWord(2)
        assertEquals(2, store.countFor("can"))
        assertEquals(0f, store.forLayout(layout)!!.minDistance("can", flat(0)), 1e-6f)
        // ...and raised again before anything new is learned, the rest come back (#326).
        store.setShapesPerWord(5)
        assertEquals(5, store.countFor("can"))

        // A new way of drawing it under the lower limit is what finally drops them.
        store.setShapesPerWord(2)
        store.learn(GlideShapeSample(layout, flat(120)), "can")
        store.setShapesPerWord(5)
        assertEquals(2, store.countFor("can"))
        val source = store.forLayout(layout)!!
        assertEquals(0f, source.minDistance("can", flat(0)), 1e-6f)
        assertEquals(0f, source.minDistance("can", flat(120)), 1e-6f)

        // Clamped to what the store can keep.
        store.setShapesPerWord(0)
        assertEquals(1, store.countFor("can"))
    }

    /** How far [away] quantised units on every coordinate is, in the store's units. */
    private fun flatDistance(away: Int): Float = GlideShapeStore.distance(flat(0), flat(away))

    @Test
    fun `distance is the shape channel's mean point distance`() {
        val a = flat(0)
        val b = near(a, GlideShapeStore.QUANT.toInt())
        // One key width (QUANT units) on both axes is sqrt(2) key widths at every point.
        assertEquals(kotlin.math.sqrt(2f), GlideShapeStore.distance(a, b), 1e-5f)
        assertTrue(GlideShapeStore.distance(a, b, abortAbove = 0.5f) > 0.5f)
    }
}
