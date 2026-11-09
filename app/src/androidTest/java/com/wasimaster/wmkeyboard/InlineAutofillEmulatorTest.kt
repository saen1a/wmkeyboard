package com.wasimaster.wmkeyboard

import android.os.Build
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.filters.SdkSuppress
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.By
import androidx.test.uiautomator.UiDevice
import androidx.test.uiautomator.Until
import org.junit.Assert.assertTrue
import org.junit.Ignore
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Proves the inline-autofill chip plumbing on a device: the system binds the
 * app's debug fake autofill service, WM Keyboard becomes the IME, the login
 * form is focused and the service's deterministic chip is drawn.
 *
 * This is deliberately not a passkey test; it never asserts credential
 * behaviour, only that a fake dataset's chip reaches the keyboard's strip.
 */
@RunWith(AndroidJUnit4::class)
@SdkSuppress(minSdkVersion = Build.VERSION_CODES.R)
class InlineAutofillEmulatorTest {

    @Ignore("API 36 routes the password tap to the improved fill dialog and does not create a new AutofillSession with the IME inline spec; see T6 blocker")
    @Test
    fun fakeAutofillChipIsShown() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val device = UiDevice.getInstance(instrumentation)
        val appPackage = instrumentation.targetContext.packageName
        // InputMethodManagerService identifies an IME by the short component
        // form, not the fully qualified service class name.
        val imeComponent = "$appPackage/.ime.WMKeyboardService"
        // The fake service lives in the app's debug source set, so it runs in
        // the app process where the Kotlin runtime and androidx.autofill exist.
        val autofillComponent = "$appPackage/${FakeAutofillService::class.java.name}"

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
            shell(device, "settings put secure autofill_service $autofillComponent")
            device.waitForIdle()

            assertTrue("IME did not switch to $imeComponent", waitForIme(device, imeComponent))

            scenario = ActivityScenario.launch(InlineAutofillTestActivity::class.java)
            scenario.onActivity {
                it.focusUsernameField()
                it.showLoginKeyboard()
            }
            assertTrue("IME window did not become visible", waitForImeShown(device))
            device.waitForIdle()

            // The session that started before the IME is stale; cancel it and
            // add the username to the next fill request.
            scenario.onActivity { it.cancelAutofillSession() }
            device.waitForIdle()
            scenario.onActivity { it.enableUsernameAutofill() }
            device.waitForIdle()

            // A real tap makes the framework start a fresh autofill session
            // with the IME already visible and its inline request available.
            val passwordField = requireNotNull(
                device.wait(
                    Until.findObject(By.res(appPackage, "fake_login_password")),
                    CHIP_TIMEOUT_MS,
                ),
            ) { "password field 'fake_login_password' was not found" }
            passwordField.click()

            val chip = requireNotNull(device.wait(Until.findObject(By.text(CHIP_TITLE)), CHIP_TIMEOUT_MS)) {
                "chip '$CHIP_TITLE' did not appear; the fake autofill service may not be bound " +
                    "or the IME never requested inline suggestions"
            }
            val bounds = chip.visibleBounds
            assertTrue("chip '$CHIP_TITLE' was found but is not visible: $bounds", bounds.width() > 0 && bounds.height() > 0)
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
            if (device.executeShellCommand("dumpsys input_method").contains("mCurId=$imeComponent")) {
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
            val dump = device.executeShellCommand("dumpsys input_method")
            if (dump.contains("mInputShown=true") && dump.contains("mWindowVisible=true")) {
                return true
            }
            Thread.sleep(IME_POLL_MS)
        }
        return false
    }

    private fun restoreSecureSetting(device: UiDevice, key: String, value: String) {
        if (value.isEmpty() || value == "null") {
            device.executeShellCommand("settings delete secure $key")
        } else {
            device.executeShellCommand("settings put secure $key $value")
        }
    }

    private companion object {
        const val CHIP_TITLE = "Fake login"
        const val CHIP_TIMEOUT_MS = 20_000L
        const val IME_TIMEOUT_MS = 10_000L
        const val IME_SHOW_TIMEOUT_MS = 10_000L
        const val IME_POLL_MS = 250L
    }
}
