package com.wasimaster.wmkeyboard.ime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The inline-suggestion lane split is a pure contract: source decides the
 * lane, type only breaks a tie inside the platform lane, and each lane is
 * trimmed to its own budget. These tests use [InlineSuggestionMeta] only —
 * no platform [android.view.inputmethod.InlineSuggestion] and no chip content.
 */
class InlineSuggestionClassifierTest {

    private fun autofill(type: String? = null) =
        InlineSuggestionMeta(InlineSuggestionClassifier.SOURCE_AUTOFILL, type)

    private fun platform(type: String? = null) =
        InlineSuggestionMeta(InlineSuggestionClassifier.SOURCE_PLATFORM, type)

    @Test
    fun `zero budgets keep nothing in either lane`() {
        val (autofill, platform) = InlineSuggestionClassifier.classify(
            listOf(autofill(), platform()),
            autofillBudget = 0,
            platformBudget = 0,
        )
        assertTrue(autofill.isEmpty())
        assertTrue(platform.isEmpty())
    }

    @Test
    fun `autofill suggestions keep the manager's order`() {
        val metas = listOf(autofill(), platform(), autofill(), autofill())
        val (autofill, _) = InlineSuggestionClassifier.classify(metas, 6, 3)
        assertEquals(listOf(0, 2, 3), autofill)
    }

    @Test
    fun `platform actions sort after plain replies and keep reply order`() {
        val metas = listOf(
            platform(InlineSuggestionClassifier.TYPE_ACTION),
            platform(),
            platform(InlineSuggestionClassifier.TYPE_ACTION),
            platform(),
        )
        val (_, platform) = InlineSuggestionClassifier.classify(metas, 6, 4)
        assertEquals(listOf(1, 3, 0, 2), platform)
    }

    @Test
    fun `each lane is capped to its own budget`() {
        val metas = List(7) { autofill() } + List(4) { platform() }
        val (autofill, platform) = InlineSuggestionClassifier.classify(
            metas,
            autofillBudget = 6,
            platformBudget = 3,
        )
        assertEquals(InlineAutofill.MAX_AUTOFILL_CHIPS, autofill.size)
        assertEquals(InlineAutofill.MAX_PLATFORM_CHIPS, platform.size)
        assertEquals(6, autofill.size)
        assertEquals(3, platform.size)
    }

    @Test
    fun `an unknown source is treated as autofill`() {
        val metas = listOf(InlineSuggestionMeta(source = 99, type = null))
        val (autofill, platform) = InlineSuggestionClassifier.classify(metas, 6, 3)
        assertEquals(listOf(0), autofill)
        assertTrue(platform.isEmpty())
    }

    @Test
    fun `the two lanes together cover every input index exactly once`() {
        val metas = listOf(autofill(), platform(), autofill())
        val (autofill, platform) = InlineSuggestionClassifier.classify(metas, 6, 3)
        val all = autofill + platform
        assertEquals(metas.indices.toList(), all.sorted())
        assertTrue(all.all { it in metas.indices })
    }
}
