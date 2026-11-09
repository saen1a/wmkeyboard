package com.wasimaster.wmkeyboard.core.util

import android.os.Build
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.atomic.AtomicLong

/**
 * The file behind one of the keyboard's learning stores, written whole, so
 * that the expensive half of a save - encoding and writing - can run on any
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
 * - Order. Two saves of one store on two threads can finish the wrong way
 *   round, and the older snapshot would land last. Tickets are drawn under the
 *   store's lock, so their order is the order of the snapshots, and [write]
 *   drops any ticket older than the last one written.
 * - Deletes. A store that is cleared deletes its file. A write drawn before
 *   the clear must not bring the old data back afterwards, so [delete] and
 *   [supersede] retire every ticket drawn so far.
 *
 * Writes are atomic: the text goes to a sibling file first and is renamed over
 * the real one. The old save truncated the file before writing it, so a
 * process killed mid-write - an IME is killed often - left a half-written
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
    fun write(ticket: Long, text: () -> String): Boolean =
        writeBytes(ticket) { text().toByteArray() }

    /**
     * The same ordering and atomic rename as [write], for a binary snapshot.
     * With [keepBackup] the previous live file is rotated to `.bak` first, so
     * a later read can recover a good snapshot when the live file is damaged.
     */
    @Synchronized
    fun writeBytes(ticket: Long, keepBackup: Boolean = false, bytes: () -> ByteArray): Boolean {
        if (ticket <= landed) return true
        val written = runCatching { writeAtomically(file, bytes(), keepBackup) }.isSuccess
        if (written) landed = ticket
        return written
    }

    /**
     * Deletes the live file, its `.bak` and any `.part` and retires every
     * ticket drawn so far. Waits for a write already under way, so that write
     * cannot land after the delete. Returns what [File.delete] did.
     *
     * The backup must go too: a delete that leaves `.bak` behind would let the
     * next load restore the data the user just cleared.
     */
    @Synchronized
    fun delete(): Boolean {
        landed = maxOf(landed, issued.get())
        return deleteWithSidecars(file)
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
         * Deletes [file] and the `.bak`, `.part` and `.corrupt` siblings a
         * binary snapshot can leave behind. A caller that has no open
         * [SnapshotFile] (the settings bulk-delete paths) uses this so a
         * user-requested delete cannot be undone by a recovery copy.
         */
        fun deleteWithSidecars(file: File): Boolean {
            val parent = file.parentFile
            if (parent != null) {
                File(parent, file.name + ".bak").delete()
                File(parent, file.name + ".part").delete()
                File(parent, file.name + ".corrupt").delete()
                parent.listFiles { candidate ->
                    candidate.name.startsWith(file.name + ".") && candidate.name.endsWith(".part")
                }.orEmpty().forEach { it.delete() }
            }
            return file.delete()
        }

        /**
         * Replaces [file] with [text] in one step: written to a sibling, then
         * renamed over it, which on Android's file systems is atomic.
         */
        fun writeAtomically(file: File, text: String) {
            writeAtomically(file, text.toByteArray())
        }

        /**
         * The one replacement path. The part is fsync'd before the rename, so
         * a crash cannot leave a half-written live file. With [keepBackup] the
         * current live file becomes `.bak` first; a failure to rotate it only
         * costs the extra copy, never the new snapshot.
         */
        fun writeAtomically(file: File, bytes: ByteArray, keepBackup: Boolean = false) {
            withLock(file) {
                file.parentFile?.mkdirs()
                val parent = file.parentFile
                val part = File(parent, file.name + "." + java.util.UUID.randomUUID() + ".part")
                FileOutputStream(part).use { out ->
                    out.write(bytes)
                    out.fd.sync()
                }
                if (keepBackup && file.isFile) {
                    val backup = File(parent, file.name + ".bak")
                    backup.delete()
                    // If this fails the new snapshot still replaces the live file;
                    // only the one-generation recovery copy is lost.
                    file.renameTo(backup)
                }
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
         * may refuse to replace an existing target, so move the old file aside,
         * rename the part in, and put the original back if that fails. The old
         * file is never deleted before the replacement succeeds.
         */
        private fun replaceLegacy(part: File, file: File) {
            if (part.renameTo(file)) return
            if (!file.exists()) {
                part.delete()
                throw java.io.IOException("Could not replace ${file.absolutePath}")
            }
            // Preserve the original until the replacement has landed.
            val backup = File(file.parentFile, file.name + "." + java.util.UUID.randomUUID() + ".bak")
            if (!file.renameTo(backup)) {
                part.delete()
                throw java.io.IOException("Could not replace ${file.absolutePath}")
            }
            if (part.renameTo(file)) {
                backup.delete()
                return
            }
            // The replacement failed: restore the original we moved aside.
            // If even that rename fails, leave the backup file in place rather
            // than losing the store's data.
            backup.renameTo(file)
            part.delete()
            throw java.io.IOException("Could not replace ${file.absolutePath}")
        }
    }
}
