package com.wasimaster.wmkeyboard

import android.content.Intent
import android.os.Build
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.SdkSuppress
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * T7: proves the IME window carries
 * [android.view.WindowManager.LayoutParams.FLAG_SECURE] (`0x2000`) while a
 * password field has focus, so screenshots and screen recording cannot see it.
 *
 * The check reads the window's `fl=` attribute out of `dumpsys window windows`.
 * On API 36 the system prints the symbolic flag name `SECURE` (the name of
 * `0x2000`) rather than a raw hex value; both spellings are accepted here. This
 * is a device test, not a JVM one: the decision itself is covered by
 * `SecureWindowTest`.
 */
@RunWith(AndroidJUnit4::class)
@SdkSuppress(minSdkVersion = Build.VERSION_CODES.R)
class SecureWindowEmulatorTest {

    @Test
    fun imeWindowIsSecureForPasswordField() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val device = UiDevice.getInstance(instrumentation)
        val appPackage = instrumentation.targetContext.packageName
        // InputMethodManagerService identifies an IME by the short component
        // form, not the fully qualified service class name.
        val imeComponent = "$appPackage/.ime.WMKeyboardService"

        val previousIme = shell(device, "settings get secure default_input_method").trim()
        val previousAutofill = shell(device, "settings get secure autofill_service").trim()
        val previousEnabledImes = shell(device, "settings get secure enabled_input_methods").trim()
        val previousHardwareKeyboard = shell(device, "settings get secure show_ime_with_hard_keyboard").trim()

        var scenario: ActivityScenario<InlineAutofillTestActivity>? = null
        try {
            // The emulator has a hardware keyboard, which suppresses the soft
            // IME window by default.
            shell(device, "settings put secure show_ime_with_hard_keyboard 1")
            shell(device, "ime enable $imeComponent")
            shell(device, "settings put secure default_input_method $imeComponent")
            device.waitForIdle()

            assertTrue("IME did not switch to $imeComponent", waitForIme(device, imeComponent))

            // The login form focuses its password field on resume, so the soft
            // keyboard is drawn over a secure field.
            val loginIntent = Intent(
                instrumentation.targetContext,
                InlineAutofillTestActivity::class.java,
            ).apply {
                putExtra(InlineAutofillTestActivity.EXTRA_LOGIN_FORM, true)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
            }
            scenario = ActivityScenario.launch(loginIntent)
            scenario.onActivity { it.showLoginKeyboard() }

            assertTrue("IME window did not become visible", waitForImeShown(device))
            device.waitForIdle()

            // The flag is applied from the state collector after the secure
            // field is reported, so poll the window dump rather than assume the
            // first dump lands after that update.
            val deadline = System.currentTimeMillis() + SECURE_FLAG_TIMEOUT_MS
            var excerpt = "no dumpsys window output captured"
            var secure = false
            while (System.currentTimeMillis() < deadline) {
                val dump = shell(device, "dumpsys window windows")
                val section = imeWindowSection(dump, appPackage)
                if (section == null) {
                    excerpt = "no InputMethod window for package $appPackage; window headers:\n" +
                        windowHeaders(dump)
                } else {
                    excerpt = flagsExcerpt(section)
                    secure = hasSecureFlag(section)
                    if (secure) break
                }
                Thread.sleep(IME_POLL_MS)
            }
            assertTrue(
                "IME window for $appPackage does not report FLAG_SECURE (0x2000 / SECURE); " +
                    "observed attributes:\n$excerpt",
                secure,
            )
        } finally {
            runCatching { scenario?.close() }
            restoreSecureSetting(device, "default_input_method", previousIme)
            restoreSecureSetting(device, "enabled_input_methods", previousEnabledImes)
            restoreSecureSetting(device, "autofill_service", previousAutofill)
            restoreSecureSetting(device, "show_ime_with_hard_keyboard", previousHardwareKeyboard)
        }
    }

    private fun shell(device: UiDevice, command: String): String = device.executeShellCommand(command)

    /** Waits until InputMethodManagerService reports [imeComponent] as current. */
    private fun waitForIme(device: UiDevice, imeComponent: String): Boolean {
        val deadline = System.currentTimeMillis() + IME_TIMEOUT_MS
        while (System.currentTimeMillis() < deadline) {
            if (shell(device, "dumpsys input_method").contains("mCurId=$imeComponent")) {
                return true
            }
            Thread.sleep(IME_POLL_MS)
        }
        return false
    }

    /** Waits until InputMethodManagerService reports the IME window as shown. */
    private fun waitForImeShown(device: UiDevice): Boolean {
        val deadline = System.currentTimeMillis() + IME_SHOW_TIMEOUT_MS
        while (System.currentTimeMillis() < deadline) {
            val dump = shell(device, "dumpsys input_method")
            if (dump.contains("mInputShown=true") && dump.contains("mWindowVisible=true")) {
                return true
            }
            Thread.sleep(IME_POLL_MS)
        }
        return false
    }

    /**
     * The window's title is the generic `InputMethod`, so the IME window of
     * [appPackage] is identified by `mIsImWindow=true` plus its owning package.
     */
    private fun imeWindowSection(dump: String, appPackage: String): String? {
        val sections = windowSections(dump)
        return sections.firstOrNull { it.contains("mIsImWindow=true") && it.contains("package=$appPackage") }
            ?: sections.firstOrNull { it.contains(WINDOW_TITLE) }
    }

    private fun windowSections(dump: String): List<String> {
        val sections = mutableListOf<String>()
        val current = StringBuilder()
        for (line in dump.lineSequence()) {
            if (WINDOW_HEADER.containsMatchIn(line) && current.isNotEmpty()) {
                sections += current.toString()
                current.clear()
            }
            current.appendLine(line)
        }
        if (current.isNotEmpty()) sections += current.toString()
        return sections
    }

    /**
     * True when the window's `fl=` attribute names [FLAG_SECURE_NAME] (the
     * symbolic form of `0x2000` on API 36) or carries `0x2000` in a numeric
     * flags value.
     */
    private fun hasSecureFlag(section: String): Boolean {
        val rawFlags = FLAGS_PATTERN.find(section)?.groupValues?.get(1) ?: return false
        return rawFlags.trim().split(WHITESPACE).any { token ->
            token == FLAG_SECURE_NAME ||
                token == "FLAG_SECURE" ||
                (token.startsWith("0x", ignoreCase = true) &&
                    runCatching { token.substring(2).toLong(16) and FLAG_SECURE_VALUE_RAW != 0L }
                        .getOrDefault(false))
        }
    }

    private fun flagsExcerpt(section: String): String {
        val header = section.lineSequence().firstOrNull()?.trim().orEmpty()
        val flags = section.lineSequence().firstOrNull { it.contains("fl=") }?.trim()
            ?: "<no fl= attribute in window section>"
        return "$header\n$flags"
    }

    private fun windowHeaders(dump: String): String =
        dump.lineSequence()
            .filter { WINDOW_HEADER.containsMatchIn(it) }
            .take(MAX_HEADERS)
            .joinToString("\n")

    private fun restoreSecureSetting(device: UiDevice, key: String, value: String) {
        if (value.isEmpty() || value == "null") {
            device.executeShellCommand("settings delete secure $key")
        } else {
            device.executeShellCommand("settings put secure $key $value")
        }
    }

    private companion object {
        const val WINDOW_TITLE = "WMKeyboardService"
        const val FLAG_SECURE_NAME = "SECURE"
        const val FLAG_SECURE_VALUE_RAW = 0x2000L
        const val IME_TIMEOUT_MS = 10_000L
        const val IME_SHOW_TIMEOUT_MS = 10_000L
        const val SECURE_FLAG_TIMEOUT_MS = 10_000L
        const val IME_POLL_MS = 250L
        const val MAX_HEADERS = 20
        val WINDOW_HEADER = Regex("""^\s*Window #\d+ """)
        val FLAGS_PATTERN = Regex("""\bfl=([^\n}]*)""")
        val WHITESPACE = Regex("""\s+""")
    }
}
