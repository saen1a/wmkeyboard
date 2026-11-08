package com.wasimaster.wmkeyboard.core.gesture

/**
 * The glide decoder's weights by language (issue #966).
 *
 * [GlideBeam.Tuning]'s defaults were fitted on English swipes and ship
 * unchanged for every language, and two of them are a property of the
 * language and its word list rather than of the hand: how much a word's
 * frequency counts against the stroke's shape ([GlideBeam.Tuning.freqWeight]),
 * and how dearly a detour between two keys is charged
 * ([GlideBeam.Tuning.gapWeight]). German's useful words are rare in any list
 * (its compounds sit at a median rank of 20,714 in a 150k list, against 369
 * for the English words people swipe), so a frequency weight fitted on
 * English outvotes the shape for German. Measured on 2,588 real German
 * swipes (FUTO swipe.futo.org, Wikipedia sentences) and 10,908 more
 * (HeliBoard's gesture data, rare words), success per swipe:
 *
 *     shipped                     71.41 %   21.95 %
 *     freqWeight 0.5              73.69 %   30.46 %
 *     freqWeight 0.5, gap 2.0     74.27 %   32.51 %
 *
 * and the same profile on 2,129 English strokes costs 81.49 % -> 80.41 %.
 * No one value wins both, which is what makes it a language's setting and
 * not a new default. The profile sits on top of whatever the user has moved
 * in Advanced tuning: it touches only the weights no setting reaches,
 * so the radii and the marks stay theirs.
 *
 * The third weight is [GlideBeam.Tuning.joinCost], the compound reading
 * (issue #966 §5.2): a German list misses 36 % of the 15-letter-plus words
 * people swipe, and the decoder reads those as two or three listed words
 * in a row, each join charged this much, every part at least
 * [GlideBeam.Tuning.joinMinPart] letters, and each part joined past
 * charged [GlideBeam.Tuning.joinPartPenalty] on its own frequency. Off
 * (infinite) everywhere but German. On the same 2,588 swipes:
 *
 *     freqWeight 0.5, gap 2.0                  74.15 %
 *     + joinCost 3.0, no guard                 70.63 %
 *     + joinCost 8.0, 4 letters, penalty 0.1   74.61 %
 *
 * Start with German; the compounding languages (Finnish, Dutch, Swedish,
 * Norwegian) are the next candidates, one harness run each
 * (`native/wm-engine/examples/glide_beam_eval`, `COLS` set to the layout's
 * columns). A language with no row here decodes with the defaults, and the
 * English output is unchanged to the bit.
 *
 * The glide context blend is opt-in as well
 * ([Profile.glideLmBlend]): the default is zero, German keeps its measured
 * 0.5/5.0 with pieces on both list sizes, and English uses 0.7/3.0 with
 * pieces on the small bundled list and 0.5/5.0 on listed candidates only
 * above [GLIDE_LM_BLEND_LIST_LIMIT]. A language without a measured row keeps
 * the decoder order.
 */
object GlideLanguageProfiles {

    /**
     * The context model's weight on a stroke, for a language without its own:
     * fitted on 2,294 German swipes against a corpus bigram (#966), the cap where
     * 2 to 3 nats was asked for.
     */
    const val DEFAULT_LM_BLEND = 0.7
    const val DEFAULT_LM_BLEND_CAP = 3.0

    /**
     * A word list longer than this counts as large for the glide's context
     * blend. The English model reads positive on the 17k bundled list with
     * pieces, and positive on the 160k AOSP list **only** when it scores
     * listed candidates alone; with pieces on the large list it reads
     * negative. The two list sizes are not interchangeable.
     */
    const val GLIDE_LM_BLEND_LIST_LIMIT = 50_000

    /** The weights a profile moves; everything else stays as the caller tuned it. */
    class Profile(
        val freqWeight: Double,
        val gapWeight: Float,
        val joinCost: Double,
        val joinMinPart: Int,
        val joinPartPenalty: Double,
        /** Decoder nats per nat the context model prefers a stroke's candidate over the first it can read. */
        val lmBlend: Double = DEFAULT_LM_BLEND,
        /** The most [lmBlend] moves a candidate either way. */
        val lmBlendCap: Double = DEFAULT_LM_BLEND_CAP,
        /**
         * [lmBlend] for the glide path only: typing's strip is a different
         * evidence problem. Zero keeps the glide blend off, which is the safe
         * default until a language and a list size have been measured.
         */
        val glideLmBlend: Double = 0.0,
        val glideLmBlendCap: Double = lmBlendCap,
        /**
         * The same two for a list above [GLIDE_LM_BLEND_LIST_LIMIT]. English
         * reads positive on the small bundled list and negative on the large
         * AOSP and counted lists, so its large value is zero.
         */
        val glideLmBlendLargeList: Double = 0.0,
        val glideLmBlendCapLargeList: Double = glideLmBlendCap,
        /**
         * Whether the glide blend spells an unlisted candidate through its
         * pieces. German's compounds need it; an English large list gains
         * more from scoring its listed candidates alone (0.8074 against
         * 0.8055 top-1, with no piece pass at all).
         */
        val glideLmSpellOov: Boolean = true,
        val glideLmSpellOovLargeList: Boolean = false,
    ) {
        /** [tuning] with this profile's weights on it, or [tuning] itself when it already carries them. */
        fun applyTo(tuning: GlideBeam.Tuning): GlideBeam.Tuning =
            if (tuning.freqWeight == freqWeight && tuning.gapWeight == gapWeight &&
                tuning.joinCost == joinCost && tuning.joinMinPart == joinMinPart &&
                tuning.joinPartPenalty == joinPartPenalty
            ) {
                tuning
            } else {
                tuning.copy(
                    freqWeight = freqWeight, gapWeight = gapWeight, joinCost = joinCost,
                    joinMinPart = joinMinPart, joinPartPenalty = joinPartPenalty,
                )
            }
    }

    /** The shipped weights, which every language without a row of its own decodes with. */
    val DEFAULT = Profile(
        GlideBeam.Tuning.DEFAULT.freqWeight,
        GlideBeam.Tuning.DEFAULT.gapWeight,
        GlideBeam.Tuning.DEFAULT.joinCost,
        GlideBeam.Tuning.DEFAULT.joinMinPart,
        GlideBeam.Tuning.DEFAULT.joinPartPenalty,
    )

    /**
     * German: shape over frequency, since its targets are rare in every
     * list (see the class note), and compounds read from their parts of
     * four letters or more, a common part paying for its join. Measured on
     * FUTO's German strokes only; HeliBoard's were not re-run. The context
     * blend is the one #1016 measured with unlisted candidates spelled: 76.04 %
     * to 77.40 % top-1 on the 150k list.
     */
    val GERMAN = Profile(
        // 0.5 above was fitted on a counted list, and German downloads AOSP's,
        // whose top words sit further apart (#1051). On that list, the same 2,588
        // swipes: 0.5 gives 80.49 %, 0.75 gives 81.22 %, 1.0 gives 80.60 %, and
        // `das` reads `das` 32 times of 33 rather than 30.
        freqWeight = 0.75,
        gapWeight = 2.0f,
        joinCost = 8.0,
        joinMinPart = 4,
        joinPartPenalty = 0.1,
        lmBlend = 0.5,
        lmBlendCap = 5.0,
        glideLmBlend = 0.5,
        glideLmBlendLargeList = 0.5,
        glideLmSpellOovLargeList = true,
    )

    /**
     * English: the decoder defaults are its fit, and the context model's small
     * list result is the one the reference model measured (+4.9 top-1 at
     * 0.7/3.0 on the 17k bundled list). On the 26,523-stroke public English
     * set over the 160k AOSP list, spelling unlisted candidates reads 79.57 %
     * against 80.55 % without it; scoring listed candidates only reads
     * 80.74 % with top-4 unchanged at 88.50 %, at no piece pass.
     */
    val ENGLISH = Profile(
        freqWeight = GlideBeam.Tuning.DEFAULT.freqWeight,
        gapWeight = GlideBeam.Tuning.DEFAULT.gapWeight,
        joinCost = GlideBeam.Tuning.DEFAULT.joinCost,
        joinMinPart = GlideBeam.Tuning.DEFAULT.joinMinPart,
        joinPartPenalty = GlideBeam.Tuning.DEFAULT.joinPartPenalty,
        lmBlend = DEFAULT_LM_BLEND,
        lmBlendCap = DEFAULT_LM_BLEND_CAP,
        glideLmBlend = 0.7,
        glideLmBlendCap = 3.0,
        glideLmBlendLargeList = 0.5,
        glideLmBlendCapLargeList = 5.0,
        glideLmSpellOovLargeList = false,
    )

    private val BY_LANGUAGE: Map<String, Profile> = mapOf(
        "de" to GERMAN,
        "en" to ENGLISH,
    )

    /**
     * The profile for [languageId], a registry id such as `de` or `de-DE`;
     * [DEFAULT] for a language with none, and for a blank or null id.
     */
    fun forLanguage(languageId: String?): Profile = BY_LANGUAGE[base(languageId)] ?: DEFAULT

    /**
     * [tuning] as the decoder should run it for [languageId]. With other
     * languages' lists [mixed] in, the shipped weights: the profiles were
     * measured on one list alone, and halving frequency lets rare English
     * words take German strokes (#1051).
     */
    fun tune(tuning: GlideBeam.Tuning, languageId: String?, mixed: Boolean = false): GlideBeam.Tuning =
        (if (mixed) DEFAULT else forLanguage(languageId)).applyTo(tuning)

    /** The language subtag of a registry id: `de-DE` and `de-Runr` are German spelled two ways. */
    private fun base(languageId: String?): String =
        languageId.orEmpty().substringBefore('-').substringBefore('_').lowercase()
}
