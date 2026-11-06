package com.wasimaster.wmkeyboard.core.gesture

import com.wasimaster.wmkeyboard.core.prediction.WordKey
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.charset.CodingErrorAction
import java.security.MessageDigest

/**
 * Runtime shape snapshot, format v1 (`WMKS`), all integers big-endian.
 *
 * Header, 80 bytes: magic, version, header size, flags, digest algorithm,
 * reserved, snapshot tick, layout count, reserved, payload length and a
 * SHA-256 digest. The digest covers every header byte except the digest field
 * itself, plus the whole payload, so tick, counts and lengths are covered too.
 *
 * Then one 24-byte directory entry per layout: key, word count, table offset,
 * arena offset, arena size. A word table holds `uint16` UTF-8 length, the
 * folded [WordKey] bytes, word tick, shape offset inside the layout's arena,
 * and `uint16` shape count. An arena holds that many records of `uint32`
 * accepted, `uint32` rejected and 96 point bytes. Table and arena offsets are
 * absolute; shape offsets are relative to their arena.
 *
 * SHA-256 is the corruption detector, not an authenticator: it detects
 * accidental damage and casual modification, but a writer who can replace the
 * file can recompute it. v1 is app-private storage protected by Android's
 * file-based encryption, so a keyed MAC was deliberately not added; see the
 * security audit in the contribution bundle.
 *
 * A file from a newer version keeps this magic and is rejected by
 * [BinaryCodec.decode], never parsed as JSON.
 */
internal class BinaryShapeData(
    val points: ByteArray,
    val accepted: Int,
    val rejected: Int,
)

internal class BinaryWordData(
    val display: String,
    val tick: Long,
    val shapes: List<BinaryShapeData>,
)

/**
 * The flat, allocation-light decode layout. No per-word or per-shape objects:
 * the arena offsets are ints and the point bytes stay in [BinarySnapshot.bytes].
 */
internal class BinaryLayout(
    val words: Array<String>,
    val wordTicks: LongArray,
    val shapeStart: IntArray,
    val shapeCount: IntArray,
    val shapePointsOffset: IntArray,
    val shapeAccepted: IntArray,
    val shapeRejected: IntArray,
)

internal class BinarySnapshot(
    val tick: Long,
    val bytes: ByteArray,
    val layouts: Map<Long, BinaryLayout>,
)

internal object BinaryCodec {
    private const val MAGIC = 0x574d4b53 // WMKS
    private const val VERSION = 1
    private const val HEADER = 80
    private const val DIRECTORY_ENTRY = 24
    private const val SHAPE_RECORD = 8 + GlideShapeStore.POINTS
    private const val DIGEST_ALGORITHM_SHA256 = 1
    private const val DIGEST_SIZE = 32
    private const val DIGEST_OFFSET = 48
    private const val FLAGS_NONE = 0

    /**
     * Whether [bytes] starts with the WMKS magic, whatever version follows.
     * A file from a newer binary version must still take the binary path: it
     * is then preserved as `.corrupt` and never parsed as JSON, and [decode]
     * names the unsupported version. Checking the version here would send a
     * future file to the JSON fallback, which would silently discard it.
     */
    fun isBinary(bytes: ByteArray): Boolean =
        bytes.size >= 4 &&
            bytes[0] == 0x57.toByte() && bytes[1] == 0x4d.toByte() &&
            bytes[2] == 0x4b.toByte() && bytes[3] == 0x53.toByte()

    fun encode(tick: Long, layouts: Map<Long, Map<String, BinaryWordData>>): ByteArray {
        require(tick >= 0) { "bad tick" }
        data class EncodedWord(val word: BinaryWordData, val display: ByteArray)
        data class Section(
            val key: Long,
            val words: List<EncodedWord>,
            val tableSize: Int,
            val arenaSize: Int,
        )

        // Canonical order: sorted layouts and words. The decoder does not
        // depend on it, but it makes the same store encode to the same bytes
        // and keeps tests and diffs stable.
        val sections = ArrayList<Section>(layouts.size)
        for ((layoutKey, words) in layouts.entries.sortedBy { it.key }) {
            var tableSize = 0
            var arenaSize = 0
            val encoded = ArrayList<EncodedWord>(words.size)
            for ((display, word) in words.entries.sortedBy { it.key }) {
                val displayBytes = display.toByteArray(Charsets.UTF_8)
                require(displayBytes.size in 1..GlideShapeStore.MAX_WORD_LENGTH) { "bad word" }
                require(word.tick in 0..tick) { "bad word tick" }
                require(word.shapes.size in 0..GlideShapeStore.MAX_SHAPES_PER_WORD) { "bad shape count" }
                encoded += EncodedWord(word, displayBytes)
                tableSize += 2 + displayBytes.size + 8 + 4 + 2
                arenaSize += word.shapes.size * SHAPE_RECORD
            }
            sections += Section(layoutKey, encoded, tableSize, arenaSize)
        }

        val totalLong = HEADER.toLong() + DIRECTORY_ENTRY.toLong() * sections.size +
            sections.sumOf { it.tableSize.toLong() + it.arenaSize.toLong() }
        require(totalLong <= Int.MAX_VALUE) { "snapshot too large" }
        val total = totalLong.toInt()
        val tableOffsets = IntArray(sections.size)
        val arenaOffsets = IntArray(sections.size)
        var cursor = HEADER + DIRECTORY_ENTRY * sections.size
        for (i in sections.indices) {
            tableOffsets[i] = cursor
            cursor += sections[i].tableSize
        }
        for (i in sections.indices) {
            arenaOffsets[i] = cursor
            cursor += sections[i].arenaSize
        }
        require(cursor == total) { "bad layout size" }

        val out = ByteBuffer.allocate(total).order(ByteOrder.BIG_ENDIAN)
        out.putInt(MAGIC)
        out.putInt(VERSION)
        out.putInt(HEADER)
        out.putInt(FLAGS_NONE)
        out.putInt(DIGEST_ALGORITHM_SHA256)
        out.putInt(0) // reserved
        out.putLong(tick)
        out.putInt(sections.size)
        out.putInt(0) // reserved
        out.putLong((total - HEADER).toLong())
        // The 32 digest bytes are already zero; digestOf ignores them.

        for (i in sections.indices) {
            val section = sections[i]
            out.position(HEADER + i * DIRECTORY_ENTRY)
            out.putLong(section.key)
            out.putInt(section.words.size)
            out.putInt(tableOffsets[i])
            out.putInt(arenaOffsets[i])
            out.putInt(section.arenaSize)
        }

        for (i in sections.indices) {
            val section = sections[i]
            var tableAt = tableOffsets[i]
            var shapeOffset = 0
            for (word in section.words) {
                val display = word.display
                out.position(tableAt)
                out.putShort(display.size.toShort())
                out.put(display)
                out.putLong(word.word.tick)
                out.putInt(shapeOffset)
                out.putShort(word.word.shapes.size.toShort())
                tableAt += 2 + display.size + 8 + 4 + 2
                shapeOffset += word.word.shapes.size * SHAPE_RECORD
            }

            var arenaAt = arenaOffsets[i]
            for (word in section.words) {
                out.position(arenaAt)
                for (shape in word.word.shapes) {
                    require(shape.points.size == GlideShapeStore.POINTS) { "bad shape" }
                    require(shape.accepted > 0 && shape.rejected >= 0) { "bad shape counts" }
                    out.putInt(shape.accepted)
                    out.putInt(shape.rejected)
                    out.put(shape.points)
                    arenaAt += SHAPE_RECORD
                }
            }
        }

        out.position(DIGEST_OFFSET)
        out.put(digestOf(out.array(), HEADER))
        return out.array()
    }

    fun decode(bytes: ByteArray): BinarySnapshot {
        require(bytes.size >= HEADER) { "short header" }
        val data = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN)
        require(data.int == MAGIC) { "not WMKS" }
        require(data.int == VERSION) { "not binary v1" }
        val headerSize = data.int
        require(headerSize in HEADER..bytes.size) { "bad header size" }
        val flags = data.int
        require(flags == FLAGS_NONE) { "unsupported flags" }
        val algorithm = data.int
        require(algorithm == DIGEST_ALGORITHM_SHA256) { "unsupported digest" }
        data.int // reserved
        val tick = data.long
        require(tick >= 0) { "bad tick" }
        val layoutCount = data.int
        require(layoutCount in 0..GlideShapeStore.MAX_LAYOUTS) { "bad layout count" }
        data.int // reserved
        val payloadLength = data.long
        require(payloadLength == (bytes.size - headerSize).toLong()) { "bad payload length" }
        val storedDigest = ByteArray(DIGEST_SIZE)
        data.get(storedDigest)
        require(MessageDigest.isEqual(storedDigest, digestOf(bytes, headerSize))) {
            "bad digest"
        }
        require(headerSize.toLong() + layoutCount.toLong() * DIRECTORY_ENTRY <= bytes.size) {
            "bad directory"
        }

        val layouts = HashMap<Long, BinaryLayout>(layoutCount)
        val table = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN)
        val shapeBuffer = ByteBuffer.wrap(bytes).order(ByteOrder.BIG_ENDIAN)
        var totalWords = 0
        repeat(layoutCount) { i ->
            data.position(headerSize + i * DIRECTORY_ENTRY)
            val layoutKey = data.long
            val wordCount = data.int
            val tableOffset = data.int
            val arenaOffset = data.int
            val arenaSize = data.int
            require(wordCount in 0..GlideShapeStore.MAX_WORDS) { "bad word count" }
            require(tableOffset in headerSize..bytes.size) { "bad table" }
            require(arenaOffset in headerSize..bytes.size) { "bad arena" }
            require(arenaSize >= 0 && arenaOffset.toLong() + arenaSize <= bytes.size) {
                "bad arena size"
            }
            require(totalWords.toLong() + wordCount <= GlideShapeStore.MAX_WORDS) { "too many words" }

            table.position(tableOffset)
            val words = arrayOfNulls<String>(wordCount)
            val wordTicks = LongArray(wordCount)
            val shapeStart = IntArray(wordCount)
            val shapeCount = IntArray(wordCount)
            val pointsOffsets = ArrayList<Int>(wordCount)
            val accepted = ArrayList<Int>(wordCount)
            val rejected = ArrayList<Int>(wordCount)
            val seenWords = HashSet<String>(wordCount * 2)
            repeat(wordCount) { w ->
                val length = table.short.toInt() and 0xffff
                require(length in 1..GlideShapeStore.MAX_WORD_LENGTH) { "bad word" }
                val wordAt = table.position()
                val display = decodeUtf8(bytes, wordAt, length)
                table.position(wordAt + length)
                require(display.isNotEmpty() && WordKey.of(display) == display) { "bad word key" }
                require(seenWords.add(display)) { "duplicate word" }
                words[w] = display
                wordTicks[w] = table.long
                require(wordTicks[w] in 0..tick) { "bad word tick" }
                val shapeOffset = table.int
                val count = table.short.toInt() and 0xffff
                require(count in 0..GlideShapeStore.MAX_SHAPES_PER_WORD) { "bad shape count" }
                require(
                    shapeOffset >= 0 &&
                        shapeOffset.toLong() + count.toLong() * SHAPE_RECORD <= arenaSize,
                ) { "bad shape range" }
                shapeStart[w] = pointsOffsets.size
                shapeCount[w] = count
                repeat(count) { j ->
                    val record = arenaOffset + shapeOffset + j * SHAPE_RECORD
                    shapeBuffer.position(record)
                    val acceptedCount = shapeBuffer.int
                    val rejectedCount = shapeBuffer.int
                    require(acceptedCount > 0 && rejectedCount >= 0) { "bad shape counts" }
                    accepted += acceptedCount
                    rejected += rejectedCount
                    pointsOffsets += record + 8
                }
                totalWords++
            }
            require(layouts.put(
                layoutKey,
                BinaryLayout(
                    words.requireNoNulls(),
                    wordTicks,
                    shapeStart,
                    shapeCount,
                    pointsOffsets.toIntArray(),
                    accepted.toIntArray(),
                    rejected.toIntArray(),
                ),
            ) == null) { "duplicate layout" }
        }
        return BinarySnapshot(tick, bytes, layouts)
    }

    /**
     * SHA-256 over every header byte outside the digest field, plus the whole
     * payload. Extension bytes between [DIGEST_OFFSET] + 32 and [headerSize]
     * are covered, so a future header cannot hide data from the digest.
     */
    /** Strict UTF-8: a malformed byte sequence is corruption, not a replacement. */
    private fun decodeUtf8(bytes: ByteArray, offset: Int, length: Int): String =
        Charsets.UTF_8.newDecoder()
            .onMalformedInput(CodingErrorAction.REPORT)
            .onUnmappableCharacter(CodingErrorAction.REPORT)
            .decode(ByteBuffer.wrap(bytes, offset, length))
            .toString()

    private fun digestOf(bytes: ByteArray, headerSize: Int): ByteArray {
        val digest = MessageDigest.getInstance("SHA-256")
        digest.update(bytes, 0, DIGEST_OFFSET)
        digest.update(bytes, DIGEST_OFFSET + DIGEST_SIZE, headerSize - (DIGEST_OFFSET + DIGEST_SIZE))
        digest.update(bytes, headerSize, bytes.size - headerSize)
        return digest.digest()
    }
}

/** The immutable decode view over a binary v1 layout. */
internal class BinaryArenaLayout(
    private val bytes: ByteArray,
    private val layout: BinaryLayout,
    private val shapeLimit: Int,
    eagerIndex: Boolean,
) : GlideShapeSource {
    private val byWord = HashMap<String, Int>(layout.words.size * 2)
    private val wordStart = IntArray(layout.words.size)
    private val wordShapes = IntArray(layout.words.size)
    private val shapePoints = ArrayList<Int>()
    private val shapeWord = ArrayList<Int>()

    init {
        for (i in layout.words.indices) {
            byWord[layout.words[i]] = i
            wordStart[i] = shapePoints.size
            val start = layout.shapeStart[i]
            val count = layout.shapeCount[i]
            val kept = GlideShapeStore.topShapeIndices(
                layout.shapeAccepted,
                layout.shapeRejected,
                start,
                count,
                shapeLimit,
            )
            wordShapes[i] = kept.size
            for (shape in kept) {
                shapeWord += i
                shapePoints += layout.shapePointsOffset[shape]
            }
        }
    }

    private val byStart: Map<Int, IntArray> by lazy(LazyThreadSafetyMode.PUBLICATION) {
        val counts = HashMap<Int, Int>()
        shapePoints.forEach { offset ->
            val cell = GlideShapeStore.cellOf(bytes, offset)
            counts[cell] = (counts[cell] ?: 0) + 1
        }
        val out = HashMap<Int, IntArray>(counts.size)
        val fill = HashMap<Int, Int>()
        shapePoints.forEachIndexed { index, offset ->
            val cell = GlideShapeStore.cellOf(bytes, offset)
            val at = fill[cell] ?: 0
            val bucket = out.getOrPut(cell) { IntArray(counts.getValue(cell)) }
            bucket[at] = index
            fill[cell] = at + 1
        }
        out
    }

    init {
        if (eagerIndex) byStart
    }

    override fun wordCount(): Int = layout.words.size

    override fun countFor(word: String): Int {
        val at = byWord[WordKey.of(word)]
        if (at == null) return 0
        return wordShapes[at]
    }

    override fun minDistance(word: String, drawn: ByteArray): Float {
        val at = byWord[WordKey.of(word)]
        if (at == null) return -1f
        var best = Float.MAX_VALUE
        val start = wordStart[at]
        repeat(wordShapes[at]) { i ->
            best = minOf(best, GlideShapeStore.distanceAt(bytes, shapePoints[start + i], drawn, best))
        }
        return if (best == Float.MAX_VALUE) -1f else best
    }

    override fun shapesOf(word: String): List<ByteArray> {
        val at = byWord[WordKey.of(word)]
        if (at == null) return emptyList()
        val start = wordStart[at]
        return List(wordShapes[at]) { i -> copyShape(bytes, shapePoints[start + i]) }
    }

    /** Compares at the arena offset, so a caller that only needs distance copies nothing. */
    override fun shapeDistance(word: String, index: Int, drawn: ByteArray): Float {
        val at = byWord[WordKey.of(word)]
        if (at == null) return -1f
        if (index !in 0 until wordShapes[at]) return -1f
        return GlideShapeStore.distanceAt(bytes, shapePoints[wordStart[at] + index], drawn)
    }

    override fun wordsNear(drawn: ByteArray, radius: Float, limit: Int): List<String> {
        if (limit <= 0 || shapePoints.isEmpty()) return emptyList()
        val found = ArrayList<Pair<String, Float>>()
        val x = Math.floorDiv(drawn[0].toInt(), GlideShapeStore.CELL)
        val y = Math.floorDiv(drawn[1].toInt(), GlideShapeStore.CELL)
        var total = 0
        for (dx in -1..1) for (dy in -1..1) total += byStart[GlideShapeStore.cellKey(x + dx, y + dy)]?.size ?: 0
        if (total == 0) {
            for (i in shapePoints.indices) consider(i, drawn, radius, found)
        } else {
            for (dx in -1..1) {
                for (dy in -1..1) {
                    val bucket = byStart[GlideShapeStore.cellKey(x + dx, y + dy)] ?: continue
                    for (i in bucket) consider(i, drawn, radius, found)
                }
            }
        }
        found.sortWith(compareBy({ it.second }, { it.first }))
        return found.take(limit).map { it.first }
    }

    override fun prepareWordsNear() {
        byStart
    }

    private fun consider(i: Int, drawn: ByteArray, radius: Float, found: ArrayList<Pair<String, Float>>) {
        val d = GlideShapeStore.distanceAt(bytes, shapePoints[i], drawn, radius)
        if (d > radius) return
        val word = layout.words[shapeWord[i]]
        val at = found.indexOfFirst { it.first == word }
        if (at < 0) found.add(word to d) else if (d < found[at].second) found[at] = word to d
    }

    private companion object {
        fun copyShape(bytes: ByteArray, offset: Int): ByteArray {
            val out = ByteArray(GlideShapeStore.POINTS)
            System.arraycopy(bytes, offset, out, 0, out.size)
            return out
        }
    }
}
