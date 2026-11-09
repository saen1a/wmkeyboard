package com.wasimaster.wmkeyboard.ime

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The FLAG_SECURE decision, without a Window: the service only applies what
 * this predicate decides.
 */
class SecureWindowTest {

    @Test
    fun `a password field is secure`() {
        assertTrue(shouldSecureWindow(secureField = true, incognitoOn = false, PanelMode.NONE, false))
    }

    @Test
    fun `incognito is secure`() {
        assertTrue(shouldSecureWindow(secureField = false, incognitoOn = true, PanelMode.NONE, false))
    }

    @Test
    fun `the clipboard panel holding a secret is secure`() {
        assertTrue(
            shouldSecureWindow(
                secureField = false,
                incognitoOn = false,
                panel = PanelMode.CLIPBOARD,
                hasSensitive = true,
            ),
        )
    }

    @Test
    fun `a clear field on no panel is not secure`() {
        assertFalse(shouldSecureWindow(secureField = false, incognitoOn = false, PanelMode.NONE, false))
    }

    @Test
    fun `a clear clipboard panel is not secure`() {
        assertFalse(
            shouldSecureWindow(
                secureField = false,
                incognitoOn = false,
                panel = PanelMode.CLIPBOARD,
                hasSensitive = false,
            ),
        )
    }

    @Test
    fun `a secret does not secure an unrelated panel`() {
        assertFalse(
            shouldSecureWindow(
                secureField = false,
                incognitoOn = false,
                panel = PanelMode.EMOJI,
                hasSensitive = true,
            ),
        )
    }
}
