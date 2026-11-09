package com.wasimaster.wmkeyboard.app

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The clipboard and autofill work depends on a few configuration facts that no
 * unit test can otherwise see: the IME must run in the main process and before
 * first unlock, the input method must advertise inline suggestions, the
 * manifest must not ask for a network permission the target does not need, the
 * clipboard directory must stay out of every backup, and the SDK levels must be
 * the ones the rest of the build assumes.
 *
 * A pure file audit: it reads the source files the build consumes, not a device.
 */
class ClipboardManifestAuditTest {

    private val manifest = File("src/main/AndroidManifest.xml").readText()
    private val method = File("src/main/res/xml/method.xml").readText()
    private val dataRules = File("src/main/res/xml/data_extraction_rules.xml").readText()
    private val legacyRules = File("src/main/res/xml/backup_rules.xml").readText()
    private val appBuild = File("build.gradle.kts").readText()

    /**
     * The IME service's whole element, from `<service` to `</service>`, so the
     * attributes before `android:name` are audited too: `android:process` can
     * precede the name and must not slip past the check.
     */
    private val imeService: String =
        Regex(
            """<service\b[^>]*com\.wasimaster\.wmkeyboard\.ime\.WMKeyboardService[^>]*>[\s\S]*?</service>""",
        ).find(manifest)?.value.orEmpty()

    @Test
    fun `the ime service stays in the main process and is direct boot aware`() {
        assertTrue(imeService.isNotEmpty())
        assertTrue(imeService.contains("""android:directBootAware="true""""))
        assertFalse("the IME must not run in a private process", imeService.contains("android:process"))
        assertFalse("the IME must not be isolated", imeService.contains("isolatedProcess"))
    }

    @Test
    fun `the ime service requires the bind input method permission`() {
        assertTrue(imeService.isNotEmpty())
        assertTrue(
            imeService.contains("""android:permission="android.permission.BIND_INPUT_METHOD""""),
        )
    }

    @Test
    fun `the input method advertises inline suggestions`() {
        assertTrue(method.contains("""android:supportsInlineSuggestions="true""""))
    }

    @Test
    fun `no local network permission is declared while target is 36`() {
        assertTrue(
            "targetSdk must be 36",
            Regex("""targetSdk\s*=\s*36\b""").containsMatchIn(appBuild),
        )
        assertFalse(manifest.contains("ACCESS_LOCAL_NETWORK"))
    }

    @Test
    fun `both backup rule files exclude the clipboard directory`() {
        assertTrue(dataRules.contains("""path="clipboard""""))
        assertTrue(legacyRules.contains("""path="clipboard""""))
    }

    @Test
    fun `sdk levels match the build`() {
        assertTrue("targetSdk must be 36", Regex("""targetSdk\s*=\s*36\b""").containsMatchIn(appBuild))
        assertTrue("compileSdk must be 37", Regex("""release\(37\)""").containsMatchIn(appBuild))
    }
}
