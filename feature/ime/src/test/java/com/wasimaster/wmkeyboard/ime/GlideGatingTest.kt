package com.wasimaster.wmkeyboard.ime

import android.os.Looper
import android.view.View
import android.view.inputmethod.BaseInputConnection
import android.view.inputmethod.InputConnection
import com.wasimaster.wmkeyboard.core.gesture.GesturePoint
import com.wasimaster.wmkeyboard.core.gesture.GlideCase
import com.wasimaster.wmkeyboard.core.gesture.KeyCenter
import com.wasimaster.wmkeyboard.core.layout.KeyAction
import com.wasimaster.wmkeyboard.core.prediction.OctopusKind
import com.wasimaster.wmkeyboard.core.prediction.OctopusWord
import com.wasimaster.wmkeyboard.core.settings.KeyboardSettings
import com.wasimaster.wmkeyboard.ime.ui.GlideVerdict
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf

/**
 * Every reason [WMKeyboardService] refuses a glide, asserted from the field's
 * side: a refused stroke types nothing and retires its preview, while the rest
 * of the keyboard state stays exactly as it found it.
 *
 * The rules themselves are pure and tested as such (`GlideSpaceTest`,
 * `PossessiveFlickTest`, `OctopusFlickTest`). What is only true of the service
 * is that the gate is actually *in front of* the commit — `glideAllowed` and the
 * two early returns at the top of `onGesture`/`onGestureWords` are the whole of
 * it, and each one is a single line that a refactor can drop without any pure
 * test noticing. So each test here deletes nothing and asserts the negative
 * space: with the guard gone the stroke below commits `hello` into the field,
 * because an explicit [GlideVerdict.Word] survives a decode that finds nothing —
 * which is what makes a refusal provable in a harness with no dictionary in it.
 *
 * Two tripwires, in this order, because the glide scope carries no exception
 * handler and a throw inside the job is silent and looks exactly like a
 * refusal:
 *  - the recording [InputConnection], which is the one that would catch a
 *    committed word;
 *  - a live glide preview planted in the state before the stroke. A refusal
 *    retires it, and every path past the gate — commit, cancel, possessive —
 *    also clears it, so the assertion is that only the preview fields changed.
 *    That is what catches the two guards whose fall-through commits nothing
 *    even when deleted.
 *
 * Deliberately not covered: the typing-test branch of `glideAllowed`, where the
 * test's own switch overrules the field and the word never reaches it (there is
 * no field to assert on); the readiness watcher that sets
 * [KeyboardUiState.glideReady], which wants a loaded suggestion engine this
 * module cannot build; and `onGesturePreview`, which shares the same gate but
 * publishes nothing a refusal could be told apart by.
 *
 * `onCreate` is deliberately never called, for the reason `ServiceBootProbeTest`
 * gives: Robolectric has no shadow for `InputMethodService`.
 */
@RunWith(RobolectricTestRunner::class)
class GlideGatingTest {

    /** The word the verdict commits, so no decoder is needed. */
    private val word = "hello"

    /**
     * The state a glide runs from, with one gate open to the caller.
     *
     * The two arguments that are load-bearing rather than tidy live on
     * [glideReadyState], with the reason each one is there. What this adds is
     * the sentinel: a stroke that got past the gate clears all three preview
     * fields on its way through, whatever it goes on to type, so their survival
     * is the tripwire for the guards whose fall-through commits nothing even
     * when deleted.
     */
    private fun readyToGlide(
        glideReady: Boolean = true,
        settings: KeyboardSettings = KeyboardSettings(learnFromTyping = false),
        secureField: Boolean = false,
        fieldKind: FieldKind = FieldKind.TEXT,
    ) = glideReadyState(
        glideReady = glideReady,
        settings = settings,
        secureField = secureField,
        fieldKind = fieldKind,
        octopusGlide = octopusSentinel(SENTINEL, kind = OctopusKind.COMPLETION),
    ).copy(glideWord = SENTINEL, glideChoices = listOf(SENTINEL))

    /** Both tripwires, field first. [reason] names the gate under test. */
    private fun assertRefused(
        reason: String,
        editor: RecordingEditor,
        service: WMKeyboardService,
        seeded: KeyboardUiState,
    ) {
        assertEquals("$reason: the stroke reached the field", "", editor.typed)
        val retired = seeded.copy(
            glideWord = null,
            glideCase = GlideCase.None,
            glideCased = emptyMap(),
            glideExpansions = emptyMap(),
            glideChoices = emptyList(),
            glideCloseCall = false,
            glidePreviewSegment = NO_GLIDE_PREVIEW_SEGMENT,
            octopusGlide = emptyMap(),
            autocorrectWord = seeded.autocorrectWord
                ?.takeUnless { it.equals(seeded.glideWord, ignoreCase = true) },
        )
        assertEquals(
            "$reason: the stroke changed state beyond retiring its preview",
            retired,
            service.uiState.value,
        )
    }

    /**
     * Reddens if `!state.glideReady -> false` goes from `glideAllowed`.
     *
     * The gate that matters most to the tests around it: it is off by default,
     * so a service test that forgets to seed it never reaches the code it
     * believes it is exercising. Pinned here so that reading is at least
     * deliberate.
     */
    @Test
    fun `a keyboard whose word lists are not loaded refuses the stroke`() {
        val (service, editor, seeded) = glideKeyboard(readyToGlide(glideReady = false))

        service.onGesture(straightStroke(), glideKeyGrid(), GLIDE_KEY_WIDTH, GlideVerdict.Word(word))
        settle { editor.typed.isNotEmpty() }

        assertRefused("not ready", editor, service, seeded)
    }

    /** Reddens if `state.settings.gestureTyping &&` goes from `glideAllowed`. */
    @Test
    fun `gesture typing switched off refuses the stroke`() {
        val settings = KeyboardSettings(gestureTyping = false, learnFromTyping = false)
        val (service, editor, seeded) = glideKeyboard(readyToGlide(settings = settings))

        service.onGesture(straightStroke(), glideKeyGrid(), GLIDE_KEY_WIDTH, GlideVerdict.Word(word))
        settle { editor.typed.isNotEmpty() }

        assertRefused("gesture typing off", editor, service, seeded)
    }

    /** Reddens if `!secureField &&` goes from `KeyboardUiState.allowsGestureTyping`. */
    @Test
    fun `a password field refuses the stroke`() {
        val (service, editor, seeded) = glideKeyboard(readyToGlide(secureField = true))

        service.onGesture(straightStroke(), glideKeyGrid(), GLIDE_KEY_WIDTH, GlideVerdict.Word(word))
        settle { editor.typed.isNotEmpty() }

        assertRefused("password field", editor, service, seeded)
    }

    /**
     * The whole of `allowsGestureTyping`'s field test, both sides of it.
     *
     * Reddens on the URL half if `|| fieldKind == FieldKind.URI` goes (#37 —
     * an omnibox is a search box as much as an address box), and on the other
     * six kinds if the test is widened past `TEXT`/`URI` — an email address has
     * no dictionary words in it to decode, and a keypad has no letters at all.
     * The two allowed kinds are asserted in the same test as the refused ones
     * on purpose: without them the six refusals could be green for any reason
     * at all, including a harness that never types.
     */
    @Test
    fun `only plain text and URL fields take a glide`() {
        for (kind in FieldKind.entries) {
            val (service, editor, seeded) = glideKeyboard(readyToGlide(fieldKind = kind))

            service.onGesture(straightStroke(), glideKeyGrid(), GLIDE_KEY_WIDTH, GlideVerdict.Word(word))

            if (kind == FieldKind.TEXT || kind == FieldKind.URI) {
                // Blank rather than empty: the glide's own spacing commits
                // separately from the word, and only the word is the question.
                settle { editor.typed.isNotBlank() }
                assertEquals("$kind should glide", word, editor.typed.trim())
            } else {
                settle { editor.typed.isNotEmpty() }
                assertRefused("$kind", editor, service, seeded)
            }
        }
    }

    /**
     * The control for the two `onGestureWords` refusals below.
     *
     * They are absence claims about a second entry point, and the field-kind
     * control above only ever drives `onGesture`. Without this one, nothing in
     * the file shows that a chained stroke can reach the field at all — so
     * both refusals would be green on a harness that simply never types
     * through that door, which is the failure they exist to rule out.
     */
    @Test
    fun `a chained stroke does reach the field, so the two refusals below mean something`() {
        val (service, editor, _) = glideKeyboard(readyToGlide())

        service.onGestureWords(listOf(straightStroke()), glideKeyGrid(), GLIDE_KEY_WIDTH, GlideVerdict.Word(word))
        settle { editor.typed.isNotBlank() }

        assertEquals(word, editor.typed.trim())
    }

    /** Reddens if `if (keys.isEmpty()) return` goes from `onGesture`. */
    @Test
    fun `a stroke with no key grid under it is refused`() {
        val (service, editor, seeded) = glideKeyboard(readyToGlide())

        service.onGesture(straightStroke(), emptyList(), GLIDE_KEY_WIDTH, GlideVerdict.Word(word))
        settle { editor.typed.isNotEmpty() }

        assertRefused("no keys", editor, service, seeded)
    }

    /**
     * Reddens if `clearGlidePreview()` goes from `cancelGlide`.
     *
     * The one refusal that is not a no-op: dragging out of the picker and
     * lifting has to take the stroke's own previews down, or the floating word
     * stays over the keys after the finger has gone. So the sentinel is
     * asserted the other way round here — cleared, not surviving.
     *
     * That a cancel types nothing is NOT what this proves, and the name no
     * longer says it does. With no engine every decode is empty and a `Cancel`
     * carries no word to rescue it, so deleting the guard leaves the stroke
     * committing nothing either way. The empty field below is a tripwire — it
     * says the job did not somehow commit — and not the claim. Whether the
     * guard stops a real decode wants a dictionary, and belongs where there is
     * one.
     *
     * The cancel restores the strip, so this is the one test here that needs
     * `fieldNoSuggestions` — it keeps `refreshSuggestions` off the snippet
     * store, another `lateinit` of `onCreate`'s. [glideReadyState] carries it
     * for every test now, so nothing has to remember.
     */
    @Test
    fun `a cancelled pick takes the stroke's preview down`() {
        val (service, editor, _) = glideKeyboard(readyToGlide())

        service.onGesture(straightStroke(), glideKeyGrid(), GLIDE_KEY_WIDTH, GlideVerdict.Cancel)
        settle { editor.typed.isNotEmpty() }

        // Tripwire, not the claim — see the note above.
        assertEquals("a cancelled pick reached the field", "", editor.typed)
        val state = service.uiState.value
        assertNull("the floating word outlived the cancelled stroke", state.glideWord)
        assertEquals(emptyList<String>(), state.glideChoices)
        assertEquals(emptyMap<Int, OctopusWord>(), state.octopusGlide)
    }

    /**
     * Reddens if `segments.isEmpty() ||` goes from `onGestureWords`.
     *
     * The sentinel is the only tripwire that can catch this one, and it is why
     * there is a sentinel at all: with the guard deleted the job still commits
     * nothing, because there is no segment to commit — it just clears the
     * preview on its way to doing nothing, which the field cannot see.
     */
    @Test
    fun `a multi-word glide with no segments is refused`() {
        val (service, editor, seeded) = glideKeyboard(readyToGlide())

        service.onGestureWords(emptyList(), glideKeyGrid(), GLIDE_KEY_WIDTH, GlideVerdict.Word(word))
        settle { editor.typed.isNotEmpty() }

        assertRefused("no segments", editor, service, seeded)
    }

    /**
     * Reddens if `keys.isEmpty() ||` goes from `onGestureWords`: the pick
     * belongs to the last segment and survives its empty decode, so the word
     * would land in the field with no grid under the stroke at all.
     */
    @Test
    fun `a multi-word glide with no key grid under it is refused`() {
        val (service, editor, seeded) = glideKeyboard(readyToGlide())

        service.onGestureWords(listOf(straightStroke()), emptyList(), GLIDE_KEY_WIDTH, GlideVerdict.Word(word))
        settle { editor.typed.isNotEmpty() }

        assertRefused("no keys", editor, service, seeded)
    }

    private companion object {
        /** Planted in the preview fields, and looked for afterwards. */
        const val SENTINEL = "STALE"
    }
}
