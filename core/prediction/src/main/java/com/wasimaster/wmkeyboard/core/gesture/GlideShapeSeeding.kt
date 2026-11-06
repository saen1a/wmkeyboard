package com.wasimaster.wmkeyboard.core.gesture

/**
 * The one start-cell bucketing and nearest-word policy shared by the JSON and
 * binary shape views. Keeping it in one place means a stored shape seeds the
 * same way whichever runtime file it came from.
 */
internal object GlideShapeSeeding {

    /** Shape indices by the key-sized cell each shape starts in, in index order. */
    fun bucketByStart(count: Int, cellAt: (Int) -> Int): Map<Int, IntArray> {
        val counts = HashMap<Int, Int>()
        for (i in 0 until count) {
            val cell = cellAt(i)
            counts[cell] = (counts[cell] ?: 0) + 1
        }
        val out = HashMap<Int, IntArray>(counts.size * 2)
        val filled = HashMap<Int, Int>(counts.size * 2)
        for (i in 0 until count) {
            val cell = cellAt(i)
            val bucket = out.getOrPut(cell) { IntArray(counts.getValue(cell)) }
            val at = filled[cell] ?: 0
            bucket[at] = i
            filled[cell] = at + 1
        }
        return out
    }

    /**
     * The words with a shape within [radius] of [drawn], nearest first, at
     * most [limit]. The 3×3 start-cell scan falls back to every shape when
     * those cells hold nothing, so an empty answer is never the index's doing.
     * Equal distances sort by word, independent of map iteration order.
     */
    fun wordsNear(
        count: Int,
        drawn: ByteArray,
        radius: Float,
        limit: Int,
        byStart: Map<Int, IntArray>,
        wordAt: (Int) -> String,
        distanceOf: (Int, ByteArray, Float) -> Float,
    ): List<String> {
        if (limit <= 0 || count == 0) return emptyList()
        val found = ArrayList<Pair<String, Float>>()
        val cx = Math.floorDiv(drawn[0].toInt(), GlideShapeStore.CELL)
        val cy = Math.floorDiv(drawn[1].toInt(), GlideShapeStore.CELL)
        var total = 0
        for (dx in -1..1) for (dy in -1..1) {
            total += byStart[GlideShapeStore.cellKey(cx + dx, cy + dy)]?.size ?: 0
        }
        if (total == 0) {
            for (i in 0 until count) consider(i, drawn, radius, found, wordAt, distanceOf)
        } else {
            for (dx in -1..1) {
                for (dy in -1..1) {
                    val bucket = byStart[GlideShapeStore.cellKey(cx + dx, cy + dy)] ?: continue
                    for (i in bucket) consider(i, drawn, radius, found, wordAt, distanceOf)
                }
            }
        }
        found.sortWith(compareBy({ it.second }, { it.first }))
        return found.take(limit).map { it.first }
    }

    /** Files shape [i] under its word when it sits within [radius], keeping the word's nearest. */
    private fun consider(
        i: Int,
        drawn: ByteArray,
        radius: Float,
        found: ArrayList<Pair<String, Float>>,
        wordAt: (Int) -> String,
        distanceOf: (Int, ByteArray, Float) -> Float,
    ) {
        val d = distanceOf(i, drawn, radius)
        if (d > radius) return
        val word = wordAt(i)
        val at = found.indexOfFirst { it.first == word }
        if (at < 0) found.add(word to d) else if (d < found[at].second) found[at] = word to d
    }
}
