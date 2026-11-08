package com.wasimaster.wmkeyboard.core.gesture

import com.wasimaster.wmkeyboard.core.prediction.CompositeWordSource
import com.wasimaster.wmkeyboard.core.prediction.PackedTrie
import org.junit.Assert.assertEquals
import org.junit.Test

/** The glide context blend is opt-in per language and list size (#1240). */
class GlideLanguageProfilesTest {

    @Test
    fun `english blends the small list with pieces and the large list from listed words`() {
        val en = GlideLanguageProfiles.forLanguage("en")
        assertEquals(0.7, en.glideLmBlend, 0.0)
        assertEquals(3.0, en.glideLmBlendCap, 0.0)
        assertEquals(true, en.glideLmSpellOov)
        assertEquals(0.5, en.glideLmBlendLargeList, 0.0)
        assertEquals(5.0, en.glideLmBlendCapLargeList, 0.0)
        assertEquals(false, en.glideLmSpellOovLargeList)
    }

    @Test
    fun `german keeps its measured blend on both list sizes`() {
        val de = GlideLanguageProfiles.forLanguage("de")
        assertEquals(0.5, de.glideLmBlend, 0.0)
        assertEquals(5.0, de.glideLmBlendCap, 0.0)
        assertEquals(0.5, de.glideLmBlendLargeList, 0.0)
        assertEquals(5.0, de.glideLmBlendCapLargeList, 0.0)
        assertEquals(true, de.glideLmSpellOovLargeList)
    }

    @Test
    fun `a language without a row has no glide blend until it is measured`() {
        val fr = GlideLanguageProfiles.forLanguage("fr")
        assertEquals(0.0, fr.glideLmBlend, 0.0)
        assertEquals(0.0, fr.glideLmBlendLargeList, 0.0)
    }

    @Test
    fun `the small list limit separates the bundled english list from AOSP`() {
        assertEquals(50_000, GlideLanguageProfiles.GLIDE_LM_BLEND_LIST_LIMIT)
    }

    @Test
    fun `a packed trie reports the word count the blend reads`() {
        val one = PackedTrie.of(listOf("one" to 1, "two" to 2))
        assertEquals(2, one.wordCount)
        val two = PackedTrie.of(listOf("two" to 2, "three" to 3))
        // The union sums its members; an overlap may count twice. The blend
        // only needs the size class, not a distinct word total.
        assertEquals(4, CompositeWordSource.of(listOf(one, two)).wordCount)
    }
}
