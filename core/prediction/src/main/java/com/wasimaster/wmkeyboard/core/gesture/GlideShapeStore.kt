package com.wasimaster.wmkeyboard.core.gesture

import com.wasimaster.wmkeyboard.core.util.SnapshotFile
import com.wasimaster.wmkeyboard.core.prediction.WordKey
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.File
import java.util.PriorityQueue
import kotlin.math.abs
import kotlin.math.roundToInt
import kotlin.math.sqrt

/**
 * What the decoder asks of learned shapes: one layout's worth, read-only,
 * safe to read on the decode thread while the keyboard's thread learns.
 */
interface GlideShapeSource {
    /**
     * How far [drawn] sits from the nearest shape stored for [word], as a
     * mean distance in key widths, or -1 when the word has none here.
     */
    fun minDistance(word: String, drawn: ByteArray): Float

    /**
     * The shapes stored for [word], in key-width coordinates times
     * [GlideShapeStore.QUANT], empty when it has none here. The decoder's
     * shape channel compares them after taking their position and size out,
     * the way it does the drawn stroke.
     */
    fun shapesOf(word: String): List<ByteArray>

    /**
     * How far shape [index] of [word] sits from [drawn], as [minDistance]
     * measures it, or -1 when that shape does not exist here. The binary
     * arena compares at the shape's offset, so this is the no-copy path for
     * callers that only need a comparison; [shapesOf] stays for the JNI
     * boundary, which needs owned `byte[][]` elements.
     */
    fun shapeDistance(word: String, index: Int, drawn: ByteArray): Float {
        val stored = shapesOf(word)
        if (index !in stored.indices) return -1f
        return GlideShapeStore.distance(stored[index], drawn)
    }

    /** Words with a stored shape within [radius] of [drawn], nearest first, at most [limit] of them. */
    fun wordsNear(drawn: ByteArray, radius: Float, limit: Int): List<String>

    /** The number of usable shapes for [word] in this view. */
    fun countFor(word: String): Int = 0

    /** The number of words in this view. */
    fun wordCount(): Int = 0

    /**
     * Builds the start-cell index [wordsNear] uses. Call it on the thread
     * that owns the store after a publish when shape seeding is on, so the
     * first seeded decode does not pay the one-time scan.
     */
    fun prepareWordsNear() {}
}

/**
 * One kept glide's shape, as the learning buffer carries it from commit to
 * settle: the grid it was drawn on and the stroke as [GlideBeam.sampleShape]
 * keeps it.
 */
class GlideShapeSample(val layoutKey: Long, val shape: ByteArray)

/**
 * How this user draws each word (issue #52): a few shapes per word, learned
 * from the glides they keep, for the decoder's shape channel to compare a
 * stroke against beside the word's ideal path.
 *
 * The ideal path through a word's key centres is what the shape channel has
 * to go on, and a real hand never draws it: it cuts corners its own way,
 * overshoots one key and undershoots the next, and does so the same way
 * every time. Swype kept the user's own strokes for exactly this reason. A
 * shape here is a stroke resampled the way the decoder resamples one, kept
 * in key-width coordinates so where it starts still counts for merging and
 * seeding, and quantised to a byte a coordinate, so a word's whole record is
 * a few hundred bytes. The shape channel normalises it like the drawn
 * stroke — centred, scaled to unit spread — before comparing the two.
 *
 * **Graduated, never taken at commit.** A shape is attached to the word in
 * the learning buffer and lands here only when the word settles: a glide the
 * user backspaces or replaces off the strip teaches nothing, and one they
 * read past and left alone does. A shape is also only kept for a word the
 * lexicon has, so nothing that is not yet a learned word is written down.
 *
 * **Keyed by grid, then word.** The same word on QWERTY and AZERTY is two
 * shapes, and so is the same word in portrait and landscape, whose row pitch
 * differs in key widths; two layouts with the same geometry share. The key
 * is a fingerprint of the keys as drawn, before the hand model moves them.
 *
 * **Accept and reject counts per shape.** A settle finds the nearest stored
 * shape of the word: within [MERGE_RADIUS] it blends in and counts an
 * acceptance, further off it is a new way of drawing the word and is added,
 * up to the user's limit ([setShapesPerWord], three unless they moved it),
 * the least-accepted making room. A glide the user undoes or replaces marks
 * the shape that matched it rejected, and a shape rejected more often than
 * accepted goes.
 *
 * Bounded at [MAX_WORDS] words across every layout, the longest untouched
 * evicted. Persisted as the compact binary v1 arena in the learning directory
 * beside the lexicon, with a read-only fallback for the JSON v2 backup file;
 * the file name is historical. Memory-only until the
 * device is unlocked, like every store there. Reads take a published
 * immutable snapshot, rebuilt for the changed layout on every learn or
 * reject.
 */
class GlideShapeStore(
    private val storageFile: File?,
    autoLoad: Boolean = true,
) {

    private class Shape(var points: ByteArray, var accepted: Int, var rejected: Int)

    private class Entry(var tick: Long, val shapes: ArrayList<Shape>)

    /** One word's place in the eviction order: oldest tick first, then scan order. */
    private class EvictionCandidate(val tick: Long, val order: Int, val layoutKey: Long, val word: String)

    @Serializable
    private data class StoredShape(val p: String, val a: Int = 1, val r: Int = 0)

    @Serializable
    private data class StoredWord(val t: Long = 0L, val s: List<StoredShape> = emptyList())

    @Serializable
    private data class Snapshot(
        val v: Int = VERSION,
        val tick: Long = 0L,
        val layouts: Map<String, Map<String, StoredWord>> = emptyMap(),
    )

    /** A decoded file, before it becomes the live mutable layout map. */
    private class SnapshotData(
        val tick: Long,
        val layouts: HashMap<Long, HashMap<String, Entry>>,
        val published: HashMap<Long, LayoutShapes> = HashMap(),
    )

    /** One layout's shapes as the decoder reads them: flat arrays, never mutated. */
    private class LayoutShapes(
        private val words: Array<String>,
        private val shapes: Array<ByteArray>,
        private val byWord: HashMap<String, IntArray>,
        eagerStartIndex: Boolean = false,
    ) : GlideShapeSource {

        /**
         * Shape indices by the key-sized cell each shape starts in, in
         * index order within a cell: what [wordsNear] scans instead of
         * every shape (issue #966 §5.4).
         *
         * The seeding scan ran over every stored shape on every decode,
         * previews included: 66 µs on a real store of 3,131 shapes and
         * 2.6 ms at the store's ceiling, up to 45 % of a decode. A shape
         * within the seeding radius of the drawn stroke almost always
         * starts where the stroke starts, since the store keeps shapes in
         * key widths and the radius is a third of one, so the scan takes
         * the 3×3 cells around the stroke's first point and nothing else:
         * 9.4 % of the shapes, 5.5× faster, and the same first word on all
         * 3,131 real queries. It is approximate in theory, since the mean
         * distance lets a far first point hide behind forty-seven near
         * ones; a stroke whose cells hold nothing falls back to the full
         * scan, so an empty answer is never the index's doing.
         */
        private val byStart: Map<Int, IntArray> by lazy(LazyThreadSafetyMode.PUBLICATION) {
            GlideShapeSeeding.bucketByStart(shapes.size) { GlideShapeStore.cellOf(shapes[it]) }
        }

        init {
            // When seeding is enabled, build on the publishing thread instead
            // of making the first seeded decode pay the scan.
            if (eagerStartIndex) byStart
        }

        override fun minDistance(word: String, drawn: ByteArray): Float {
            val indices = byWord[WordKey.of(word)] ?: return -1f
            var best = Float.MAX_VALUE
            for (i in indices) {
                val d = distance(shapes[i], drawn, best)
                if (d < best) best = d
            }
            return if (best == Float.MAX_VALUE) -1f else best
        }

        override fun shapesOf(word: String): List<ByteArray> {
            val indices = byWord[WordKey.of(word)] ?: return emptyList()
            return indices.map { shapes[it] }
        }

        override fun shapeDistance(word: String, index: Int, drawn: ByteArray): Float {
            val indices = byWord[WordKey.of(word)] ?: return -1f
            if (index !in indices.indices) return -1f
            return distance(shapes[indices[index]], drawn)
        }

        override fun prepareWordsNear() {
            byStart
        }

        override fun countFor(word: String): Int = byWord[WordKey.of(word)]?.size ?: 0

        override fun wordCount(): Int = byWord.size

        override fun wordsNear(drawn: ByteArray, radius: Float, limit: Int): List<String> =
            GlideShapeSeeding.wordsNear(
                count = shapes.size,
                drawn = drawn,
                radius = radius,
                limit = limit,
                byStart = byStart,
                wordAt = { words[it] },
                distanceOf = { i, stroke, bound -> distance(shapes[i], stroke, bound) },
            )
    }

    /** Builds the decode view in the same pass that decodes the mutable entries. */
    private class SurfaceBuilder(
        private val shapeLimit: Int,
        private val eagerStartIndex: Boolean,
    ) {
        private val words = ArrayList<String>()
        private val shapes = ArrayList<ByteArray>()
        private val byWord = HashMap<String, IntArray>()

        fun add(word: String, stored: List<Shape>) {
            val kept = readable(stored, shapeLimit)
            if (kept.isEmpty()) return
            val indices = IntArray(kept.size)
            for ((i, shape) in kept.withIndex()) {
                indices[i] = shapes.size
                words.add(word)
                shapes.add(shape.points)
            }
            byWord[word] = indices
        }

        fun build(): LayoutShapes = LayoutShapes(
            words.toTypedArray(),
            shapes.toTypedArray(),
            byWord,
            eagerStartIndex,
        )
    }

    private val layouts = HashMap<Long, HashMap<String, Entry>>()
    private var tick = 0L
    private var dirty = false

    /**
     * True when the live file was missing or failed its digest and the store
     * came from `.bak`. The next save must not rotate that unusable live file
     * over the good backup.
     */
    private var primaryUnusable = false
    private val snapshotFile = storageFile?.let(::SnapshotFile)

    @Volatile
    private var published: Map<Long, GlideShapeSource> = emptyMap()

    /** The binary bytes when the file was loaded without materializing live shapes. */
    private var arena: BinarySnapshot? = null
    private var materialized = true

    /**
     * Whether the next published view builds the start-cell index eagerly.
     * The service sets this from the shape-seeding setting.
     */
    @Volatile
    var buildStartIndex: Boolean = false

    /** Builds the start-cell index for every published layout, on this thread. */
    @Synchronized
    fun prepareAllSeeding() {
        if (!buildStartIndex) return
        published.values.forEach { it.prepareWordsNear() }
    }

    /** How many ways of drawing one word are kept apart. See [setShapesPerWord]. */
    private var shapeLimit = DEFAULT_SHAPES_PER_WORD

    @Volatile
    private var loaded = false

    init {
        if (autoLoad) load()
    }

    /**
     * Loads the file on the calling thread if it is not loaded yet. The IME
     * constructs the store with `autoLoad = false` and calls this from a
     * background scope, so startup does not wait for the shape snapshot.
     */
    @Synchronized
    fun loadNow() {
        if (loaded) return
        load()
    }

    /** The shapes stored for one layout, for the decoder; null when it has none. */
    fun forLayout(layoutKey: Long): GlideShapeSource? = published[layoutKey]

    /**
     * How many ways of drawing one word to keep apart (#326), clamped to
     * 1..[MAX_SHAPES_PER_WORD].
     *
     * Lowering it takes the least-accepted extras away from the decoder at
     * once, but drops them from the store only when that word next learns a
     * new way of being drawn. Until then raising it again brings them back,
     * so a slider dragged down and up again, or a settings emit that arrives
     * with the default before the user's value, loses nothing.
     */
    @Synchronized
    fun setShapesPerWord(limit: Int) {
        val clamped = limit.coerceIn(1, MAX_SHAPES_PER_WORD)
        if (clamped == shapeLimit) return
        shapeLimit = clamped
        if (loaded) {
            materialize()
            publish()
        }
    }

    /**
     * A settled glide of [word] drawn as [sample]: blends into the nearest
     * stored shape of the word when there is one within [MERGE_RADIUS], else
     * is kept as a new one.
     */
    @Synchronized
    fun learn(sample: GlideShapeSample, word: String) {
        if (!loaded) loadNow()
        materialize()
        val key = WordKey.of(word)
        if (key.isEmpty() || sample.shape.size != POINTS) return
        // The binary word table counts UTF-8 bytes, not UTF-16 units. Reject
        // what it cannot store here, so a pathological key cannot make every
        // later save fail.
        if (key.toByteArray(Charsets.UTF_8).size > MAX_WORD_LENGTH) return
        tick++
        val words = layouts.getOrPut(sample.layoutKey) { HashMap() }
        val entry = words.getOrPut(key) { Entry(tick, ArrayList(shapeLimit)) }
        entry.tick = tick
        val nearest = nearest(entry, sample.shape)
        if (nearest != null && distance(nearest.points, sample.shape, MERGE_RADIUS) <= MERGE_RADIUS) {
            blend(nearest, sample.shape)
            nearest.accepted++
        } else {
            if (entry.shapes.size >= shapeLimit) {
                // A new way of drawing a word always arrives at one acceptance,
                // so a plain count leaves an established shape unbeatable: it
                // evicts each newcomer in turn, and a hand that has changed can
                // never say so (issue #213). Every sighting of something new
                // ages what is already here instead. A shape still in use keeps
                // its lead by being accepted again; one the user has stopped
                // drawing halves away and gives up the slot in a few sightings.
                for (shape in entry.shapes) shape.accepted = (shape.accepted + 1) / 2
                // More than one goes when the limit was lowered since this word
                // last learned something new.
                while (entry.shapes.size >= shapeLimit) {
                    entry.shapes.remove(entry.shapes.minByOrNull { it.accepted - it.rejected })
                }
            }
            entry.shapes.add(Shape(sample.shape.copyOf(), 1, 0))
        }
        val evicted = evict()
        if (evicted) {
            settleAll()
        } else {
            settle(sample.layoutKey)
        }
    }

    /**
     * A glide read as [word] and drawn as [drawn] was undone or replaced: the
     * stored shape that matched it, if one did within [REJECT_RADIUS], counts
     * a rejection, and goes once rejected more often than accepted. True
     * when a shape was marked.
     */
    @Synchronized
    fun reject(layoutKey: Long, word: String, drawn: ByteArray): Boolean {
        if (!loaded) loadNow()
        materialize()
        val words = layouts[layoutKey] ?: return false
        val key = WordKey.of(word)
        val entry = words[key] ?: return false
        val nearest = nearest(entry, drawn) ?: return false
        if (distance(nearest.points, drawn, REJECT_RADIUS) > REJECT_RADIUS) return false
        tick++
        entry.tick = tick
        nearest.rejected++
        if (nearest.rejected > nearest.accepted) entry.shapes.remove(nearest)
        if (entry.shapes.isEmpty()) words.remove(key)
        if (words.isEmpty()) layouts.remove(layoutKey)
        settle(layoutKey)
        return true
    }

    /** Drops every shape of [word], on every layout. True when there were any. */
    @Synchronized
    fun forget(word: String): Boolean {
        if (!loaded) loadNow()
        materialize()
        val key = WordKey.of(word)
        var any = false
        val iterator = layouts.entries.iterator()
        while (iterator.hasNext()) {
            val words = iterator.next().value
            if (words.remove(key) != null) any = true
            if (words.isEmpty()) iterator.remove()
        }
        if (any) settleAll()
        return any
    }

    /** How many shapes [word] has that the decoder reads, across every layout. */
    @Synchronized
    fun countFor(word: String): Int = published.values.sumOf { it.countFor(word) }

    @Synchronized
    fun wordCount(): Int = published.values.sumOf { it.wordCount() }

    @Synchronized
    fun isEmpty(): Boolean = published.values.all { it.wordCount() == 0 }

    fun save() {
        if (!loaded) loadNow()
        val file = snapshotFile ?: return
        var keepBackup = false
        val (ticket, snapshotTick, snapshotLayouts) = synchronized(this) {
            if (!dirty) return
            if (!materialized) materialize()
            dirty = false
            keepBackup = !primaryUnusable
            val data = layouts.entries.associate { (layoutKey, words) ->
                layoutKey to words.entries.associate { (word, entry) ->
                    word to BinaryWordData(
                        entry.tick,
                        entry.shapes.map { BinaryShapeData(it.points, it.accepted, it.rejected) },
                    )
                }
            }
            Triple(file.ticket(), tick, data)
        }
        // Encoded and written outside the lock, so the store stays usable while
        // the file goes to disk. A failed write makes the store dirty again, so
        // the next save retries rather than assuming it landed.
        val written = file.writeBytes(ticket, keepBackup) {
            BinaryCodec.encode(snapshotTick, snapshotLayouts)
        }
        if (written) {
            synchronized(this) { primaryUnusable = false }
        } else {
            markUnsaved()
        }
    }

    /**
     * Builds the mutable learning map from the binary arena. Only the first write
     * after a fast load pays this; decode reads the arena directly.
     */
    private fun materialize() {
        if (materialized) return
        val snapshot = arena
        if (snapshot == null) {
            materialized = true
            return
        }
        layouts.clear()
        for ((layoutKey, layout) in snapshot.layouts) {
            val words = HashMap<String, Entry>(layout.words.size * 2)
            for (i in layout.words.indices) {
                val start = layout.shapeStart[i]
                val count = layout.shapeCount[i]
                val shapes = ArrayList<Shape>(count)
                for (j in 0 until count) {
                    val at = start + j
                    val points = ByteArray(POINTS)
                    System.arraycopy(snapshot.bytes, layout.shapePointsOffset[at], points, 0, POINTS)
                    shapes.add(Shape(points, layout.shapeAccepted[at], layout.shapeRejected[at]))
                }
                if (shapes.isNotEmpty()) words[layout.words[i]] = Entry(layout.wordTicks[i], shapes)
            }
            if (words.isNotEmpty()) layouts[layoutKey] = words
        }
        materialized = true
    }

    @Synchronized
    private fun markUnsaved() {
        dirty = true
    }

    /** Re-reads the file after the settings app deleted or replaced it. */
    @Synchronized
    fun reload() {
        snapshotFile?.supersede()
        layouts.clear()
        arena = null
        materialized = true
        tick = 0L
        load()
        dirty = false
    }

    @Synchronized
    fun clear() {
        if (!loaded) loadNow()
        layouts.clear()
        arena = null
        materialized = true
        tick = 0L
        published = emptyMap()
        // The delete is the write; stay dirty only if it failed, so the next
        // save overwrites the stale file with the empty snapshot.
        dirty = snapshotFile?.delete() == false
    }

    private fun nearest(entry: Entry, drawn: ByteArray): Shape? {
        var best: Shape? = null
        var bestDistance = Float.MAX_VALUE
        for (shape in entry.shapes) {
            val d = distance(shape.points, drawn, bestDistance)
            if (d < bestDistance) {
                bestDistance = d
                best = shape
            }
        }
        return best
    }

    /**
     * Running mean in the quantised space, the shape's acceptances deep — but
     * never deeper than [BLEND_DEPTH], and rounded rather than truncated.
     *
     * Two things were wrong with the plain mean (issue #213). It freezes: at
     * fifty acceptances a new stroke moves the stored shape by a fiftieth, so a
     * word drawn often enough stops following the hand this store exists to
     * follow. And `toInt()` truncates *toward zero*, so every coordinate that
     * failed to move a whole quantised unit fell back toward the origin instead
     * of staying put — a slow pull on every stored shape, in the one direction
     * the normalisation has already centred them on.
     *
     * Capping the depth turns the tail into an exponential mean, which keeps
     * converging while a habit holds and still comes across when it changes.
     * The cap has to be shallow because the mean is kept in whole quantised
     * units: a step of half the weight or less rounds away to nothing, so a
     * depth of `n` cannot track a drift finer than about `n / 2` units. At four
     * that floor is an eighth of a key width, comfortably inside
     * [MERGE_RADIUS], which is the resolution the merge decision works at
     * anyway.
     */
    private fun blend(shape: Shape, drawn: ByteArray) {
        val depth = minOf(shape.accepted, BLEND_DEPTH)
        val weight = depth + 1
        // Replace the array instead of writing through it: a published
        // LayoutShapes may still hold the old reference, and its readers must
        // never see a half-blended shape.
        val next = ByteArray(POINTS)
        for (i in 0 until POINTS) {
            val mixed = (shape.points[i] * depth + drawn[i]).toFloat() / weight
            next[i] = mixed.roundToInt().coerceIn(-QUANT_LIMIT, QUANT_LIMIT).toByte()
        }
        shape.points = next
    }

    /**
     * Past [MAX_WORDS] the words left alone longest make room. True when any
     * went.
     *
     * One pass with a bounded heap of the [MAX_WORDS] overflow, rather than
     * rescanning every word once per eviction. Ties keep the earlier scan
     * position, which is the word the old repeated minimum chose within its
     * iteration order.
     */
    private fun evict(): Boolean {
        val total = layouts.values.sumOf { it.size }
        if (total <= MAX_WORDS) return false
        val excess = total - MAX_WORDS
        val newestFirst = compareByDescending<EvictionCandidate> { it.tick }.thenByDescending { it.order }
        val oldestFirst = compareBy<EvictionCandidate> { it.tick }.thenBy { it.order }
        // Keeps the `excess` oldest entries; the newest kept sits on top, so
        // a candidate older than it can replace it.
        val heap = PriorityQueue(excess, newestFirst)
        var order = 0
        for ((layoutKey, words) in layouts) {
            for ((word, entry) in words) {
                val candidate = EvictionCandidate(entry.tick, order++, layoutKey, word)
                if (heap.size < excess) {
                    heap.add(candidate)
                } else if (oldestFirst.compare(candidate, heap.peek()) < 0) {
                    heap.poll()
                    heap.add(candidate)
                }
            }
        }
        var any = false
        for (candidate in heap) {
            val words = layouts[candidate.layoutKey] ?: continue
            if (words.remove(candidate.word) == null) continue
            any = true
            if (words.isEmpty()) layouts.remove(candidate.layoutKey)
        }
        return any
    }

    private fun settle(layoutKey: Long) {
        publish(layoutKey)
        dirty = true
    }

    private fun settleAll() {
        publish()
        dirty = true
    }

    private fun publish() {
        published = if (layouts.isEmpty()) {
            emptyMap()
        } else {
            layouts.entries.associate { (layoutKey, words) -> layoutKey to layoutShapes(words) }
        }
    }

    /**
     * Rebuilds one layout's immutable view after a change, instead of every
     * layout. A settled word normally touches one layout, and a store with
     * several layouts used to copy every shape in all of them.
     */
    private fun publish(layoutKey: Long) {
        val words = layouts[layoutKey]
        val next = HashMap(published)
        if (words.isNullOrEmpty()) {
            next.remove(layoutKey)
        } else {
            next[layoutKey] = layoutShapes(words)
        }
        published = next
    }

    private fun layoutShapes(words: Map<String, Entry>): LayoutShapes {
        val wordList = ArrayList<String>()
        val shapeList = ArrayList<ByteArray>()
        val byWord = HashMap<String, IntArray>(words.size * 2)
        for ((word, entry) in words) {
            val kept = readable(entry.shapes)
            val indices = IntArray(kept.size)
            for ((i, shape) in kept.withIndex()) {
                indices[i] = shapeList.size
                wordList.add(word)
                // Shape.points is never mutated in place; blend() replaces it.
                // A published view may safely share the array.
                shapeList.add(shape.points)
            }
            byWord[word] = indices
        }
        return LayoutShapes(
            wordList.toTypedArray(),
            shapeList.toTypedArray(),
            byWord,
            eagerStartIndex = buildStartIndex,
        )
    }

    /** The [shapeLimit] most-accepted of [shapes], or all of them when they fit. */
    private fun readable(shapes: List<Shape>): List<Shape> = readable(shapes, shapeLimit)

    private sealed interface Loaded {
        class Binary(val bytes: ByteArray, val snapshot: BinarySnapshot) : Loaded
        class Json(val data: SnapshotData) : Loaded
    }

    private fun load() {
        dirty = false
        primaryUnusable = false
        layouts.clear()
        tick = 0L
        arena = null
        published = emptyMap()
        val file = storageFile ?: run {
            loaded = true
            return
        }
        val backup = File(file.parentFile, file.name + ".bak")
        val primary = decodeFile(file)
        val fromBackup = primary == null
        val decoded = primary ?: decodeFile(backup)
        if (decoded == null) {
            // Neither copy is usable. Keep the live file for diagnosis and
            // never let the next save rotate it over a backup we just rejected.
            if (file.isFile) preserveCorrupt(file)
            backup.delete()
            primaryUnusable = true
            materialized = true
            loaded = true
            return
        }
        if (fromBackup) {
            // The live file was missing or failed its digest. Keep the evidence
            // and make the next save replace it without rotating it over the
            // good backup.
            if (file.isFile) preserveCorrupt(file)
            primaryUnusable = true
            dirty = true
        }
        when (decoded) {
            is Loaded.Binary -> {
                arena = decoded.snapshot
                materialized = false
                tick = decoded.snapshot.tick
                published = decoded.snapshot.layouts.entries.associate { (key, layout) ->
                    key to BinaryArenaLayout(decoded.bytes, layout, shapeLimit, buildStartIndex)
                }
            }
            is Loaded.Json -> {
                arena = null
                materialized = true
                tick = decoded.data.tick
                layouts.putAll(decoded.data.layouts)
                val evicted = evict()
                if (evicted) publish() else published = decoded.data.published
            }
        }
        loaded = true
    }

    private fun decodeFile(file: File): Loaded? {
        val bytes = readSnapshot(file) ?: return null
        return if (BinaryCodec.isBinary(bytes)) {
            runCatching { BinaryCodec.decode(bytes) }.getOrNull()?.let { Loaded.Binary(bytes, it) }
        } else {
            runCatching { decodeJson(bytes.decodeToString(), shapeLimit, buildStartIndex) }
                .getOrNull()?.let { Loaded.Json(it) }
        }
    }

    private fun readSnapshot(file: File): ByteArray? {
        if (!file.isFile || file.length() > MAX_FILE_BYTES) return null
        return runCatching { file.readBytes() }.getOrNull()
    }

    private fun preserveCorrupt(file: File) {
        if (file.length() > MAX_FILE_BYTES) return
        runCatching {
            file.parentFile?.let { parent ->
                file.copyTo(File(parent, file.name + ".corrupt"), overwrite = true)
            }
        }
    }

    companion object {
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
        }

        /**
         * The [limit] best of [shapes], by the same policy [topShapeIndices]
         * applies to the binary arena. Keeping one selector here means a JSON
         * load and a binary load cannot pick different shapes for a word.
         */
        private fun readable(shapes: List<Shape>, limit: Int): List<Shape> {
            if (shapes.size <= limit) return shapes
            return topIndices(shapes.size, limit) { shapes[it].accepted - shapes[it].rejected }
                .map { shapes[it] }
        }

        /**
         * The [limit] best indices in `0 until count`, by descending [rank],
         * ties keeping the lower index. It is a repeated first-maximum over
         * indices, not a sort of objects, so the mutable store and the flat
         * arena run exactly the same selection. Keeping the lower index on a
         * tie is the order a stable descending sort gives, which is what the
         * JSON path chose before the two were unified.
         */
        private inline fun topIndices(count: Int, limit: Int, rank: (Int) -> Int): IntArray {
            if (count <= limit) return IntArray(count) { it }
            val keep = minOf(limit, count)
            val out = IntArray(keep)
            val used = BooleanArray(count)
            for (i in 0 until keep) {
                var best = -1
                for (j in 0 until count) {
                    if (used[j]) continue
                    if (best < 0 || rank(j) > rank(best)) best = j
                }
                used[best] = true
                out[i] = best
            }
            return out
        }

        /** The v2 JSON snapshot version, still read as a fallback. */
        private const val VERSION = 2

        /**
         * A snapshot beyond this is not a real shape file. The valid maximum
         * (10,000 words × 20 shapes × 104 bytes) is about 21 MB; 64 MB leaves
         * room for future format growth without letting a hostile file make
         * the reader allocate without bound.
         */
        private const val MAX_FILE_BYTES = 64L * 1024 * 1024

        internal const val MAX_LAYOUTS = 10000
        internal const val MAX_WORD_LENGTH = 256

        /** Words kept across every layout; the longest untouched goes first. */
        const val MAX_WORDS = 10000

        /** A file beyond this is treated as corrupt, not merely over the soft cap. */
        private const val HARD_WORD_LIMIT = MAX_WORDS * 4

        /** Ways of drawing one word that are kept apart, unless the user sets another number. */
        const val DEFAULT_SHAPES_PER_WORD = 3

        /**
         * Most ways of drawing one word the user can ask to keep (#326). Set
         * high on purpose, so a backup can show how many a hand really uses.
         * A full store at this is 10000 words of about 2 KB each.
         */
        const val MAX_SHAPES_PER_WORD = 20

        /**
         * Deepest the running mean behind a stored shape ever gets: past this
         * many acceptances a shape keeps following the hand at a fixed rate
         * rather than settling for good. See [blend].
         */
        const val BLEND_DEPTH = 4

        /** A settled shape this close to a stored one is the same way of drawing the word, and blends in (in key widths). */
        const val MERGE_RADIUS = 0.35f

        /** An undone stroke this close to a stored shape is the one that shape read wrongly (in key widths). */
        const val REJECT_RADIUS = 0.60f

        /** Coordinates per shape: x then y for each of the decoder's samples. */
        const val POINTS = 2 * GlideWorkspace.SHAPE_POINTS

        /** Quantisation: a key-width coordinate times this, rounded to a byte. */
        const val QUANT = 10f

        internal const val CELL = 10
        internal const val CELL_BITS = 16
        internal const val CELL_MASK = 0xFFFF

        private const val QUANT_LIMIT = 127

        /**
         * Mean distance between two shapes, in the shape channel's units — a
         * coordinate is `QUANT` bytes to the key width of spread. Stops
         * counting once the running mean can no longer come in under
         * [abortAbove], and answers something above it then.
         *
         * The root per point is the cost of this, and the seeding scan
         * ([GlideShapeSource.wordsNear]) takes it against each shape in the
         * 3×3 start cells, or every shape when those cells hold nothing, on
         * every decode, previews included (issue #966). So a cut-off is
         * first tried without any: each point's larger axis difference is
         * never more than its distance, and a shape whose sum of those
         * alone passes the limit is over it whatever the roots would have
         * said. The answer is the same as before for every shape, nearer
         * ones included, which then take the exact pass as they always did.
         */
        fun distance(a: ByteArray, b: ByteArray, abortAbove: Float = Float.MAX_VALUE): Float =
            distanceAt(a, 0, b, abortAbove)

        /** The same distance when [source] starts at [offset], without copying the shape. */
        fun distanceAt(
            source: ByteArray,
            offset: Int,
            b: ByteArray,
            abortAbove: Float = Float.MAX_VALUE,
        ): Float {
            val n = GlideWorkspace.SHAPE_POINTS
            val limit = abortAbove * n * QUANT
            if (abortAbove < Float.MAX_VALUE) {
                var bound = 0
                for (j in 0 until n) {
                    val dx = abs(source[offset + 2 * j] - b[2 * j])
                    val dy = abs(source[offset + 2 * j + 1] - b[2 * j + 1])
                    bound += if (dx > dy) dx else dy
                    if (bound > limit) return abortAbove + 1f
                }
            }
            var sum = 0f
            for (j in 0 until n) {
                val dx = (source[offset + 2 * j] - b[2 * j]).toFloat()
                val dy = (source[offset + 2 * j + 1] - b[2 * j + 1]).toFloat()
                sum += sqrt(dx * dx + dy * dy)
                if (sum > limit) return abortAbove + 1f
            }
            return sum / (n * QUANT)
        }

        /** The [limit] best shape indices by accepted minus rejected, without boxing or sorting. */
        internal fun topShapeIndices(
            accepted: IntArray,
            rejected: IntArray,
            start: Int,
            count: Int,
            limit: Int,
        ): IntArray {
            val local = topIndices(count, limit) { accepted[start + it] - rejected[start + it] }
            return IntArray(local.size) { start + local[it] }
        }

        internal fun cellKey(cx: Int, cy: Int): Int = (cx shl CELL_BITS) or (cy and CELL_MASK)

        internal fun cellOf(shape: ByteArray): Int =
            cellKey(Math.floorDiv(shape[0].toInt(), CELL), Math.floorDiv(shape[1].toInt(), CELL))

        internal fun cellOf(bytes: ByteArray, offset: Int): Int =
            cellKey(Math.floorDiv(bytes[offset].toInt(), CELL), Math.floorDiv(bytes[offset + 1].toInt(), CELL))

        /**
         * The v2 JSON form of a store file, for the settings backup/export.
         * A binary runtime file is converted back to the format older builds
         * can read; a file that is already JSON is returned unchanged.
         */
        fun exportJson(file: File): String? = runCatching {
            val bytes = validSnapshotBytes(file) ?: return@runCatching null
            if (BinaryCodec.isBinary(bytes)) {
                val data = BinaryCodec.decode(bytes)
                return@runCatching json.encodeToString(
                    Snapshot(
                        VERSION,
                        data.tick,
                        data.layouts.entries.associate { (layoutKey, layout) ->
                            java.lang.Long.toHexString(layoutKey) to layout.words.indices.associate { i ->
                                val start = layout.shapeStart[i]
                                val count = layout.shapeCount[i]
                                layout.words[i] to StoredWord(
                                    layout.wordTicks[i],
                                    (0 until count).map { j ->
                                        val at = start + j
                                        val offset = layout.shapePointsOffset[at]
                                        StoredShape(
                                            hexAt(data.bytes, offset, POINTS),
                                            layout.shapeAccepted[at],
                                            layout.shapeRejected[at],
                                        )
                                    },
                                )
                            }
                        },
                    ),
                )
            }
            bytes.decodeToString().takeIf { it.isNotBlank() }
        }.getOrNull()

        /** The live file when it verifies, else the one-generation `.bak`. */
        private fun validSnapshotBytes(file: File): ByteArray? {
            val primary = readSnapshotBytes(file)
            if (primary != null && isSnapshot(primary)) return primary
            val backup = File(file.parentFile, file.name + ".bak")
            val backupBytes = readSnapshotBytes(backup)
            if (backupBytes != null && isSnapshot(backupBytes)) return backupBytes
            return null
        }

        private fun readSnapshotBytes(file: File): ByteArray? {
            if (!file.isFile || file.length() > MAX_FILE_BYTES) return null
            return runCatching { file.readBytes() }.getOrNull()
        }

        private fun isSnapshot(bytes: ByteArray): Boolean =
            if (BinaryCodec.isBinary(bytes)) {
                runCatching { BinaryCodec.decode(bytes) }.isSuccess
            } else {
                runCatching {
                    json.decodeFromString<Snapshot>(bytes.decodeToString()).v == VERSION
                }.getOrDefault(false)
            }

        /**
         * Restores a backup as v2 JSON; the next store save converts it to
         * binary. The text is decoded before anything is replaced, so a
         * malformed or unsupported backup leaves the live store and its
         * recovery copies untouched. A successful restore drops those copies
         * because the JSON is now the source of truth.
         */
        fun importJson(file: File, text: String): Boolean = runCatching {
            decodeJson(text, DEFAULT_SHAPES_PER_WORD, false) ?: return false
            com.wasimaster.wmkeyboard.core.util.SnapshotFile.writeAtomically(file, text)
            File(file.parentFile, file.name + ".bak").delete()
            File(file.parentFile, file.name + ".corrupt").delete()
            true
        }.getOrDefault(false)

        private fun decodeJson(
            text: String,
            shapeLimit: Int,
            eagerStartIndex: Boolean,
        ): SnapshotData? {
            val snapshot = json.decodeFromString<Snapshot>(text)
            // 0.6.4 encoded with defaults off, so its files omit `v` (and any
            // other field at its default). Kotlinx fills the default first, so
            // a 0.6.4 JSON file reaches this check as version 2.
            if (snapshot.v != VERSION) return null
            require(snapshot.layouts.size <= MAX_LAYOUTS) { "too many layouts" }
            val tick = snapshot.tick.coerceAtLeast(0L)
            var totalWords = 0
            val layouts = HashMap<Long, HashMap<String, Entry>>(snapshot.layouts.size)
            val published = HashMap<Long, LayoutShapes>(snapshot.layouts.size)
            for ((layoutHex, words) in snapshot.layouts) {
                val layoutKey = java.lang.Long.parseUnsignedLong(layoutHex, 16)
                val entries = HashMap<String, Entry>(words.size * 2)
                val surface = SurfaceBuilder(shapeLimit, eagerStartIndex)
                for ((word, stored) in words) {
                    if (word.length !in 1..MAX_WORD_LENGTH) continue
                    val key = WordKey.of(word)
                    // The binary table stores UTF-8 bytes; a word under the
                    // UTF-16 cap can still be too long in bytes (emoji, many
                    // combining marks). Skip it now rather than fail a save.
                    if (key.isEmpty() || key.toByteArray(Charsets.UTF_8).size > MAX_WORD_LENGTH) continue
                    val shapes = ArrayList<Shape>(minOf(stored.s.size, MAX_SHAPES_PER_WORD))
                    for (s in stored.s) {
                        val points = s.p.fromHex() ?: continue
                        if (points.size != POINTS || s.a <= 0) continue
                        shapes.add(Shape(points, s.a, s.r.coerceAtLeast(0)))
                        if (shapes.size >= MAX_SHAPES_PER_WORD) break
                    }
                    if (shapes.isNotEmpty()) {
                        require(totalWords < HARD_WORD_LIMIT) { "too many words" }
                        totalWords++
                        entries[key] = Entry(stored.t.coerceIn(0L, tick), shapes)
                        surface.add(key, shapes)
                    }
                }
                if (entries.isNotEmpty()) {
                    layouts[layoutKey] = entries
                    published[layoutKey] = surface.build()
                }
            }
            return SnapshotData(tick, layouts, published)
        }

        private fun hexAt(bytes: ByteArray, offset: Int, size: Int): String {
            val out = CharArray(size * 2)
            val digits = "0123456789abcdef"
            for (i in 0 until size) {
                val value = bytes[offset + i].toInt() and 0xff
                out[2 * i] = digits[value ushr 4]
                out[2 * i + 1] = digits[value and 0x0f]
            }
            return String(out)
        }

        private fun String.fromHex(): ByteArray? {
            if (length % 2 != 0 || any { it !in "0123456789abcdefABCDEF" }) return null
            return ByteArray(length / 2) { i -> substring(2 * i, 2 * i + 2).toInt(16).toByte() }
        }
    }
}
