package com.wasimaster.wmkeyboard

import androidx.test.uiautomator.UiDevice

/**
 * Shell helpers shared by the emulator tests that switch the default IME and
 * restore the secure settings afterwards.
 */
object EmulatorImeHarness {

    const val IME_TIMEOUT_MS = 10_000L
    const val IME_SHOW_TIMEOUT_MS = 10_000L
    const val IME_POLL_MS = 250L

    fun shell(device: UiDevice, command: String): String = device.executeShellCommand(command)

    /** Waits until InputMethodManagerService reports [imeComponent] as current. */
    fun waitForIme(device: UiDevice, imeComponent: String): Boolean {
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
    fun waitForImeShown(device: UiDevice): Boolean {
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

    /** The secure settings the tests change and must put back. */
    data class SecureSettings(
        val defaultInputMethod: String,
        val autofillService: String,
        val enabledInputMethods: String,
        val showImeWithHardKeyboard: String,
    )

    fun captureSecureSettings(device: UiDevice): SecureSettings = SecureSettings(
        defaultInputMethod = shell(device, "settings get secure default_input_method").trim(),
        autofillService = shell(device, "settings get secure autofill_service").trim(),
        enabledInputMethods = shell(device, "settings get secure enabled_input_methods").trim(),
        showImeWithHardKeyboard = shell(device, "settings get secure show_ime_with_hard_keyboard").trim(),
    )

    fun restoreSecureSettings(device: UiDevice, settings: SecureSettings) {
        restoreSecureSetting(device, "default_input_method", settings.defaultInputMethod)
        restoreSecureSetting(device, "enabled_input_methods", settings.enabledInputMethods)
        restoreSecureSetting(device, "autofill_service", settings.autofillService)
        restoreSecureSetting(device, "show_ime_with_hard_keyboard", settings.showImeWithHardKeyboard)
    }

    private fun restoreSecureSetting(device: UiDevice, key: String, value: String) {
        if (value.isEmpty() || value == "null") {
            device.executeShellCommand("settings delete secure $key")
        } else {
            device.executeShellCommand("settings put secure $key $value")
        }
    }
}
