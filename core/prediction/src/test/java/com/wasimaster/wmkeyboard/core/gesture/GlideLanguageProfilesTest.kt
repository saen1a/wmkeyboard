package com.wasimaster.wmkeyboard.core.gesture

import org.junit.Assert.assertEquals
import org.junit.Test

/** The glide context blend is opt-in per language and list size (#1240). */
class GlideLanguageProfilesTest {

    @Test
    fun `english blends the small bundled list and leaves the large ones alone`() {
        val en = GlideLanguageProfiles.forLanguage("en")
        assertEquals(0.7, en.glideLmBlend, 0.0)
        assertEquals(3.0, en.glideLmBlendCap, 0.0)
        assertEquals(0.0, en.glideLmBlendLargeList, 0.0)
    }

    @Test
    fun `german keeps its measured blend on both list sizes`() {
        val de = GlideLanguageProfiles.forLanguage("de")
        assertEquals(0.5, de.glideLmBlend, 0.0)
        assertEquals(5.0, de.glideLmBlendCap, 0.0)
        assertEquals(0.5, de.glideLmBlendLargeList, 0.0)
        assertEquals(5.0, de.glideLmBlendCapLargeList, 0.0)
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
}
