package com.wasimaster.wmkeyboard.ime

/**
 * One inline suggestion reduced to the two fields the lane split reads: where
 * it came from and, within the platform lane, what kind of suggestion it is.
 *
 * Deliberately free of chip content: the classifier only decides which lane a
 * suggestion belongs to, and the keyboard never sees what a chip says.
 *
 * [source] mirrors [android.view.inputmethod.InlineSuggestionInfo]: the
 * platform source is [InlineSuggestionClassifier.SOURCE_PLATFORM]; every
 * other value, known or not, is treated as autofill.
 */
internal data class InlineSuggestionMeta(val source: Int, val type: String?)

/** The two strips an inline response is split across. */
internal enum class InlineLane { AUTOFILL, PLATFORM }

/**
 * Sorts an inline response into its two lanes and trims each to its budget.
 *
 * Pure on purpose: it takes only indices, source and type, so the lane and
 * budget rules can be tested without a platform [android.view.inputmethod.InlineSuggestion].
 * Returned index lists preserve input order; the platform lane is stably
 * reordered so plain replies come before action chips.
 */
internal object InlineSuggestionClassifier {
    /** Every value but [SOURCE_PLATFORM], including unknown ones. */
    const val SOURCE_AUTOFILL = 0

    /** Mirrors `InlineSuggestionInfo.SOURCE_PLATFORM` ("android:platform"). */
    const val SOURCE_PLATFORM = 1

    /** Mirrors `InlineSuggestionInfo.TYPE_ACTION`, the platform lane's tiebreak. */
    const val TYPE_ACTION = "android:autofill:action"

    fun classify(
        metas: List<InlineSuggestionMeta>,
        autofillBudget: Int,
        platformBudget: Int,
    ): Pair<List<Int>, List<Int>> {
        val autofill = mutableListOf<Int>()
        val platform = mutableListOf<Int>()
        metas.forEachIndexed { index, meta ->
            if (meta.source == SOURCE_PLATFORM) {
                platform += index
            } else {
                autofill += index
            }
        }
        // Stable, so replies keep the platform's own order among themselves.
        platform.sortBy { if (metas[it].type == TYPE_ACTION) 1 else 0 }
        return autofill.take(autofillBudget.coerceAtLeast(0)) to
            platform.take(platformBudget.coerceAtLeast(0))
    }
}
