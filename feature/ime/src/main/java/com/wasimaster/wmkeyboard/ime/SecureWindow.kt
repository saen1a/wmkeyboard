package com.wasimaster.wmkeyboard.ime

/**
 * Whether the IME window must carry [android.view.WindowManager.LayoutParams.FLAG_SECURE].
 *
 * True for a password field, while incognito is on, and while the clipboard
 * panel is holding a secret. Pure so the decision can be tested without a
 * Window: the service only applies it.
 */
internal fun shouldSecureWindow(
    secureField: Boolean,
    incognitoOn: Boolean,
    panel: PanelMode,
    hasSensitive: Boolean,
): Boolean = secureField ||
    incognitoOn ||
    (panel == PanelMode.CLIPBOARD && hasSensitive)
