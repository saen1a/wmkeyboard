package com.wasimaster.wmkeyboard.core.util

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

class SnapshotFileTest {

    @get:Rule
    val temp = TemporaryFolder()

    private fun target(): File = File(temp.root, "learning/store.json")

    @Test
    fun writesTheTextAndLeavesNoPartFileBehind() {
        val file = SnapshotFile(target())
        assertTrue(file.write(file.ticket()) { "one" })
        assertEquals("one", target().readText())
        assertFalse(File(target().parentFile, "store.json.part").exists())
    }

    @Test
    fun anOlderSnapshotFinishingLastDoesNotOverwriteANewerOne() {
        val file = SnapshotFile(target())
        val older = file.ticket()
        val newer = file.ticket()
        assertTrue(file.write(newer) { "newer" })
        var encoded = false
        assertTrue(file.write(older) { encoded = true; "older" })
        assertEquals("newer", target().readText())
        assertFalse("a stale snapshot is not even encoded", encoded)
    }

    @Test
    fun aSecondLegacyWriteReplacesTheFileAndLeavesNoSideFiles() {
        val file = SnapshotFile(target())
        assertTrue(file.write(file.ticket()) { "first" })
        assertTrue(file.write(file.ticket()) { "second" })
        assertEquals("second", target().readText())
        val side = target().parentFile.listFiles { f ->
            f.name.endsWith(".part") || f.name.endsWith(".bak")
        }.orEmpty()
        assertEquals(0, side.size)
    }

    @Test
    fun deleteRetiresEverySnapshotDrawnBeforeIt() {
        val file = SnapshotFile(target())
        assertTrue(file.write(file.ticket()) { "kept" })
        val beforeClear = file.ticket()
        assertTrue(file.delete())
        assertTrue(file.write(beforeClear) { "stale" })
        assertFalse("the delete must stick", target().exists())
        assertTrue(file.write(file.ticket()) { "after" })
        assertEquals("after", target().readText())
    }

    @Test
    fun supersedeDropsWritesOfMemoryThatWasReloaded() {
        val file = SnapshotFile(target())
        assertTrue(file.write(file.ticket()) { "on disk" })
        val stale = file.ticket()
        file.supersede()
        assertTrue(file.write(stale) { "stale" })
        assertEquals("on disk", target().readText())
    }

    @Test
    fun aFailedWriteReportsFalseAndKeepsTheOldFile() {
        val file = SnapshotFile(target())
        assertTrue(file.write(file.ticket()) { "good" })
        assertFalse(file.write(file.ticket()) { error("encoding failed") })
        assertEquals("good", target().readText())
    }

    @Test
    fun twoWritersOnOnePathDoNotCollideInThePartFile() {
        val first = SnapshotFile(target())
        val second = SnapshotFile(target())
        val threads = listOf(
            Thread { repeat(20) { first.write(first.ticket()) { "first" } } },
            Thread { repeat(20) { second.write(second.ticket()) { "second" } } },
        )
        threads.forEach(Thread::start)
        threads.forEach(Thread::join)
        assertTrue(target().readText() in setOf("first", "second"))
        val parts = target().parentFile.listFiles { file -> file.name.endsWith(".part") }.orEmpty()
        assertEquals(0, parts.size)
    }

    @Test
    fun withLockIsReentrantAroundWriteAtomically() {
        val result = SnapshotFile.withLock(target()) {
            SnapshotFile.withLock(target()) {
                SnapshotFile.writeAtomically(target(), "inner")
                "ok"
            }
        }
        assertEquals("ok", result)
        assertEquals("inner", target().readText())
    }

    @Test
    fun anotherThreadsAtomicWriteWaitsForThePathLock() {
        val locked = CountDownLatch(1)
        val release = CountDownLatch(1)
        val writerDone = CountDownLatch(1)
        val holder = Thread {
            SnapshotFile.withLock(target()) {
                locked.countDown()
                release.await()
            }
        }
        val writer = Thread {
            locked.await()
            SnapshotFile.writeAtomically(target(), "external")
            writerDone.countDown()
        }
        holder.start()
        writer.start()
        assertTrue(locked.await(5, TimeUnit.SECONDS))
        // The external write is serialized behind the held path lock.
        assertFalse(writerDone.await(200, TimeUnit.MILLISECONDS))
        release.countDown()
        assertTrue(writerDone.await(5, TimeUnit.SECONDS))
        holder.join()
        writer.join()
        assertEquals("external", target().readText())
    }
}
