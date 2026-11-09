package com.wasimaster.wmkeyboard

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.View
import android.view.WindowManager
import android.view.autofill.AutofillManager
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.LinearLayout
import androidx.annotation.RequiresApi

/**
 * Debug-only login form the inline-autofill instrumentation test opens.
 *
 * It lives in the app's own package because `ActivityScenario` can only start
 * activities that resolve to the instrumentation process. Declared in the debug
 * manifest, never in a release build.
 */
@RequiresApi(Build.VERSION_CODES.R)
class InlineAutofillTestActivity : Activity() {

    private lateinit var usernameField: EditText
    private lateinit var passwordField: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        usernameField = EditText(this).apply {
            hint = "Username"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
            // Kept out of autofill until the IME is visible, so the first
            // focus does not start a fill session that predates the IME's
            // inline request.
            importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
            id = View.generateViewId()
        }
        passwordField = EditText(this).apply {
            hint = "Password"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
            importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_YES
            setAutofillHints(View.AUTOFILL_HINT_PASSWORD)
            id = R.id.fake_login_password
        }
        root.addView(usernameField)
        root.addView(passwordField)
        setContentView(root)
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE)
    }

    override fun onResume() {
        super.onResume()
        // Start on username so the IME can come up and register its inline
        // request before focus moves to the password field.
        usernameField.requestFocus()
    }

    /** Focuses the username field so the IME can start on a visible editor. */
    fun focusUsernameField() {
        usernameField.requestFocus()
    }

    /**
     * Forces the soft keyboard for the focused field. The emulator has a
     * hardware keyboard, which otherwise suppresses the IME window and with it
     * every inline suggestion request.
     */
    fun showLoginKeyboard() {
        val field = currentFocus ?: usernameField
        val imm = getSystemService(InputMethodManager::class.java) ?: return
        imm.showSoftInput(field, InputMethodManager.SHOW_FORCED)
    }

    /**
     * Cancels the autofill session that started before the IME window existed.
     * The next focus then starts a fresh session that carries the IME's inline
     * request.
     */
    fun cancelAutofillSession() {
        getSystemService(AutofillManager::class.java)?.cancel()
    }

    /**
     * Adds the username field to the next fill request now that the IME is
     * visible. The test then taps the password field, which starts the fill.
     */
    fun enableUsernameAutofill() {
        usernameField.importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_YES
        usernameField.setAutofillHints(View.AUTOFILL_HINT_USERNAME)
    }
}
