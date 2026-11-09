package com.wasimaster.wmkeyboard.core.gesture

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/**
 * A scale check for the shape store's on-disk round trip. It is deliberately
 * not a timing assertion: CI machines differ. The printed save/load numbers
 * are the baseline for storage-format changes.
 */
class GlideShapeStoreScaleTest {

    @get:Rule
    val temp = TemporaryFolder()

    private fun shape(value: Int): ByteArray = ByteArray(GlideShapeStore.POINTS) { value.toByte() }

    @Test
    fun `ten thousand words survive a save and reload`() {
        val file = File(temp.root, "glide_shapes.json")
        val store = GlideShapeStore(file)
        val layout = 0x5e1fL
        val learnStart = System.nanoTime()
        repeat(10_000) { i ->
            store.learn(GlideShapeSample(layout, shape((i % 200) - 100)), "word$i")
        }
        val learnMs = (System.nanoTime() - learnStart) / 1_000_000
        val saveStart = System.nanoTime()
        store.save()
        val saveMs = (System.nanoTime() - saveStart) / 1_000_000
        val bytes = file.length()
        val readStart = System.nanoTime()
        file.readBytes()
        val readMs = (System.nanoTime() - readStart) / 1_000_000
        val openStart = System.nanoTime()
        val reopened = GlideShapeStore(file, autoLoad = false)
        val openMs = (System.nanoTime() - openStart) / 1_000_000
        val loadStart = System.nanoTime()
        reopened.loadNow()
        val loadMs = (System.nanoTime() - loadStart) / 1_000_000
        val source = reopened.forLayout(layout) ?: error("nothing loaded")
        val lookupStart = System.nanoTime()
        var found = 0
        repeat(10_000) { i ->
            if (source.countFor("word$i") > 0) found++
        }
        val lookupUs = (System.nanoTime() - lookupStart) / 1_000
        // The no-copy comparison must agree with the materialised shape.
        val storedShape = source.shapesOf("word0").single()
        assertEquals(0f, GlideShapeStore.distance(storedShape, shape(-100)), 1e-6f)
        assertEquals(0f, source.shapeDistance("word0", 0, shape(-100)), 1e-6f)
        assertEquals(-1f, source.shapeDistance("word0", 1, shape(-100)), 0f)
        val lazyNearStart = System.nanoTime()
        source.wordsNear(shape(0), 0.35f, 8)
        val lazyNearUs = (System.nanoTime() - lazyNearStart) / 1_000

        val eager = GlideShapeStore(file, autoLoad = false)
        eager.loadNow()
        val eagerSource = eager.forLayout(layout) ?: error("nothing loaded")
        val indexStart = System.nanoTime()
        eager.buildStartIndex = true
        eager.prepareAllSeeding()
        val indexMs = (System.nanoTime() - indexStart) / 1_000_000
        val nearStart = System.nanoTime()
        val nearFirst = eagerSource.wordsNear(shape(0), 0.35f, 8)
        val nearFirstUs = (System.nanoTime() - nearStart) / 1_000
        val nearRepeatStart = System.nanoTime()
        repeat(100) { eagerSource.wordsNear(shape(0), 0.35f, 8) }
        val nearRepeatUs = (System.nanoTime() - nearRepeatStart) / 100 / 1_000
        println(
            "GlideShapeStore scale: learn=$learnMs ms save=$saveMs ms " +
                "open=$openMs ms read=$readMs ms load=$loadMs ms bytes=$bytes words=${reopened.wordCount()} " +
                "lookup=${lookupUs}us/${10_000} words lazyNear=$lazyNearUs us index=$indexMs ms " +
                "nearFirst=${nearFirstUs}us nearRepeat=${nearRepeatUs}us",
        )
        assertEquals(10_000, reopened.wordCount())
        assertEquals(10_000, found)
        assertEquals(1, reopened.countFor("word9999"))
        assertTrue(nearFirst.isNotEmpty())
    }
}
