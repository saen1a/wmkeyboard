package com.wasimaster.wmkeyboard.core.util

import android.os.Build
import java.io.File
import java.util.concurrent.atomic.AtomicLong

/**
 * The file behind one of the keyboard's learning stores, written whole, so
 * that the expensive half of a save — encoding and writing — can run on any
 * thread.
 *
 * A store's save used to be one synchronized block on the main thread: copy
 * the maps, encode them to JSON, truncate the file and write it. The keyboard
 * saves a dozen stores every time it hides, and the biggest of them, the
 * learned-words lexicon, runs to megabytes. Split in two, the store takes its
 * snapshot under its own lock and draws a [ticket] with it; the encoding and
 * the write happen here, outside that lock, and the service runs them off the
 * main thread.
 *
 * Two things that were free when every save ran on one thread have to be kept
 * by hand:
 *
 * - **Order.** Two saves of one store on two threads can finish the wrong way
 *   round, and the older snapshot would land last. Tickets are drawn under the
 *   store's lock, so their order is the order of the snapshots, and [write]
 *   drops any ticket older than the last one written.
 * - **Deletes.** A store that is cleared deletes its file. A write drawn
 *   before the clear must not bring the old data back afterwards, so [delete]
 *   and [supersede] retire every ticket drawn so far.
 *
 * Writes are atomic: the text goes to a sibling file first and is renamed over
 * the real one. The old save truncated the file before writing it, so a
 * process killed mid-write — an IME is killed often — left a half-written
 * lexicon, which fails to parse and loads as empty.
 */
class SnapshotFile(val file: File) {

    private val issued = AtomicLong()

    /** The newest ticket written or retired. Guarded by `this`. */
    private var landed = 0L

    /**
     * A place in the write order for a snapshot. Draw it under the same lock
     * the snapshot was taken under.
     */
    fun ticket(): Long = issued.incrementAndGet()

    /**
     * Writes [text] for [ticket], unless a newer snapshot already landed.
     * Returns false only when the write failed, so the store can stay dirty
     * and try again at its next save; a skipped write counts as done.
     */
    @Synchronized
    fun write(ticket: Long, text: () -> String): Boolean {
        if (ticket <= landed) return true
        val written = runCatching { writeAtomically(file, text()) }.isSuccess
        if (written) landed = ticket
        return written
    }

    /**
     * Deletes the file and retires every ticket drawn so far. Waits for a
     * write already under way, so that write cannot land after the delete.
     * Returns what [File.delete] did.
     */
    @Synchronized
    fun delete(): Boolean {
        landed = maxOf(landed, issued.get())
        return file.delete()
    }

    /**
     * Retires every ticket drawn so far, for a store that has just re-read its
     * file: those snapshots describe memory it has thrown away.
     */
    @Synchronized
    fun supersede() {
        landed = maxOf(landed, issued.get())
    }

    companion object {
        /** Serializes writers from different [SnapshotFile] instances per path. */
        private val writeLocks =
            java.util.concurrent.ConcurrentHashMap<String, java.util.concurrent.locks.ReentrantLock>()

        private fun lockFor(file: File): java.util.concurrent.locks.ReentrantLock =
            writeLocks.computeIfAbsent(file.absolutePath) { java.util.concurrent.locks.ReentrantLock() }

        /**
         * Runs [block] under the file's static per-path write lock. The lock is
         * reentrant, so [writeAtomically] may be called from inside it: the
         * clipboard store wraps its whole external-stamp check and write in it
         * and then writes through [SnapshotFile.write], while a sync or
         * ConfigBackup restore replaces the same file through
         * [writeAtomically], so the two cannot interleave.
         *
         * Lock order is always this path lock first, then a store's own lock.
         * A store must never take the path lock while holding its own.
         */
        fun <T> withLock(file: File, block: () -> T): T {
            val lock = lockFor(file)
            lock.lock()
            try {
                return block()
            } finally {
                lock.unlock()
            }
        }

        /**
         * Replaces [file] with [text] in one step: written to a unique sibling,
         * then renamed over it. On API 26+ that rename is atomic; on API 24/25
         * java.nio.file does not exist, so a plain rename with a delete-and-
         * retry fallback is used.
         */
        fun writeAtomically(file: File, text: String) {
            withLock(file) {
                file.parentFile?.mkdirs()
                // A unique sibling: the IME and a sync/ConfigBackup restore can
                // write the same history file from two instances. A shared
                // "history.json.part" let one writer truncate the other's part.
                val part = File(file.parentFile, file.name + "." + java.util.UUID.randomUUID() + ".part")
                part.writeText(text)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    replaceWithNio(part, file)
                } else {
                    replaceLegacy(part, file)
                }
            }
        }

        /** API 26+: a rename that replaces the target atomically where supported. */
        @Suppress("SwallowedException")
        private fun replaceWithNio(part: File, file: File) {
            // File.renameTo does not replace an existing file on Windows,
            // so the snapshot stayed in .part and the store loaded an
            // empty file. Files.move with REPLACE_EXISTING is portable.
            try {
                java.nio.file.Files.move(
                    part.toPath(),
                    file.toPath(),
                    java.nio.file.StandardCopyOption.REPLACE_EXISTING,
                    java.nio.file.StandardCopyOption.ATOMIC_MOVE,
                )
            } catch (atomicUnsupported: java.nio.file.AtomicMoveNotSupportedException) {
                java.nio.file.Files.move(
                    part.toPath(),
                    file.toPath(),
                    java.nio.file.StandardCopyOption.REPLACE_EXISTING,
                )
            } catch (failure: Throwable) {
                part.delete()
                throw failure
            }
        }

        /**
         * API 24/25: java.nio.file is API 26+, so rename without it. renameTo
         * may refuse to replace an existing target, so delete and retry once.
         */
        private fun replaceLegacy(part: File, file: File) {
            if (part.renameTo(file)) return
            if (file.delete() && part.renameTo(file)) return
            part.delete()
            throw java.io.IOException("Could not replace ${file.absolutePath}")
        }
    }
}
