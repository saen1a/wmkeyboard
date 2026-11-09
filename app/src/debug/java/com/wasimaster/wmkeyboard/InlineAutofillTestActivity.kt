package com.wasimaster.wmkeyboard

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.View
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.EditText
import android.widget.LinearLayout
import androidx.annotation.RequiresApi

/**
 * Debug-only host for the inline-autofill instrumentation test.
 *
 * With [EXTRA_LOGIN_FORM] false it shows a warm-up field with autofill disabled,
 * so the IME can be brought up without starting an autofill session. With the
 * extra true it shows the username/password form and focuses the password field
 * on resume, so a fresh autofill session starts while the IME is already
 * visible. Declared in the debug manifest, never in a release build.
 */
@RequiresApi(Build.VERSION_CODES.R)
class InlineAutofillTestActivity : Activity() {

    private lateinit var focusedField: EditText

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val loginForm = intent.getBooleanExtra(EXTRA_LOGIN_FORM, false)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }

        focusedField = if (loginForm) {
            val usernameField = EditText(this).apply {
                hint = "Username"
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS
                importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_YES
                setAutofillHints(View.AUTOFILL_HINT_USERNAME)
                id = View.generateViewId()
            }
            val passwordField = EditText(this).apply {
                hint = "Password"
                inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
                importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_YES
                setAutofillHints(View.AUTOFILL_HINT_PASSWORD)
                id = R.id.fake_login_password
            }
            root.addView(usernameField)
            root.addView(passwordField)
            passwordField
        } else {
            EditText(this).apply {
                hint = "Warm-up"
                inputType = InputType.TYPE_CLASS_TEXT
                importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
                id = View.generateViewId()
            }.also { root.addView(it) }
        }

        setContentView(root)
        window.setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE)
    }

    override fun onResume() {
        super.onResume()
        focusedField.requestFocus()
    }

    /**
     * Forces the soft keyboard for the focused field. The emulator has a
     * hardware keyboard, which otherwise suppresses the IME window and with it
     * every inline suggestion request.
     */
    fun showLoginKeyboard() {
        val field = currentFocus ?: focusedField
        val imm = getSystemService(InputMethodManager::class.java) ?: return
        imm.showSoftInput(field, InputMethodManager.SHOW_FORCED)
    }

    companion object {
        const val EXTRA_LOGIN_FORM = "extra_login_form"
    }
}
