package com.wasimaster.wmkeyboard

import android.content.Intent
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
 * Intended to prove the inline-autofill chip plumbing on a device: the system
 * binds the app's debug fake autofill service, WM Keyboard becomes the IME, the
 * login form is focused and the service's deterministic chip is drawn.
 *
 * The only test is `@Ignore`d while T6 is blocked, so this class currently
 * proves nothing; it becomes a runnable proof only when that test is enabled.
 *
 * This is deliberately not a passkey test; it never asserts credential
 * behaviour, only that a fake dataset's chip reaches the keyboard's strip.
 */
@RunWith(AndroidJUnit4::class)
@SdkSuppress(minSdkVersion = Build.VERSION_CODES.R)
class InlineAutofillEmulatorTest {
    @Ignore("T6 blocked; see .kilo/orchestrator/clipboard-test-matrix-plan.md")
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

        val previous = EmulatorImeHarness.captureSecureSettings(device)

        var warmUp: ActivityScenario<InlineAutofillTestActivity>? = null
        var login: ActivityScenario<InlineAutofillTestActivity>? = null
        try {
            // The emulator has a hardware keyboard, which suppresses the soft
            // IME window by default.
            EmulatorImeHarness.shell(device, "settings put secure show_ime_with_hard_keyboard 1")
            EmulatorImeHarness.shell(device, "ime enable $imeComponent")
            EmulatorImeHarness.shell(device, "settings put secure default_input_method $imeComponent")
            EmulatorImeHarness.shell(device, "settings put secure autofill_service $autofillComponent")
            device.waitForIdle()

            assertTrue(
                "IME did not switch to $imeComponent",
                EmulatorImeHarness.waitForIme(device, imeComponent),
            )

            // Warm-up form: autofill is disabled on its field, so bringing the
            // IME up here does not start an autofill session.
            warmUp = ActivityScenario.launch(InlineAutofillTestActivity::class.java)
            warmUp.onActivity { it.showLoginKeyboard() }
            assertTrue("IME window did not become visible", EmulatorImeHarness.waitForImeShown(device))
            device.waitForIdle()

            // Fresh task with the login form. Its password field is focused on
            // resume, so autofill starts only now, with the IME already up.
            val loginIntent = Intent(
                instrumentation.targetContext,
                InlineAutofillTestActivity::class.java,
            ).apply {
                putExtra(InlineAutofillTestActivity.EXTRA_LOGIN_FORM, true)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
            }
            login = ActivityScenario.launch(loginIntent)

            val chip =
                requireNotNull(device.wait(Until.findObject(By.text(CHIP_TITLE)), CHIP_TIMEOUT_MS)) {
                    "chip '$CHIP_TITLE' did not appear; the fake autofill service may not be bound " +
                        "or the IME never requested inline suggestions"
                }
            val bounds = chip.visibleBounds
            assertTrue(
                "chip '$CHIP_TITLE' was found but is not visible: $bounds",
                bounds.width() > 0 && bounds.height() > 0,
            )
        } finally {
            runCatching { login?.close() }
            runCatching { warmUp?.close() }
            EmulatorImeHarness.restoreSecureSettings(device, previous)
        }
    }

    private companion object {
        const val CHIP_TITLE = "Fake login"
        const val CHIP_TIMEOUT_MS = 20_000L
    }
}
