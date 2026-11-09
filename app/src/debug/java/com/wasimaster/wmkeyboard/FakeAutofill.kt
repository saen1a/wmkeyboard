package com.wasimaster.wmkeyboard

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.app.assist.AssistStructure
import android.content.Intent
import android.os.Build
import android.os.CancellationSignal
import android.service.autofill.AutofillService
import android.service.autofill.Dataset
import android.service.autofill.FillCallback
import android.service.autofill.FillRequest
import android.service.autofill.FillResponse
import android.service.autofill.SaveCallback
import android.service.autofill.SaveRequest
import android.text.InputType
import android.view.View
import android.view.autofill.AutofillId
import android.view.autofill.AutofillValue
import androidx.annotation.RequiresApi
import androidx.autofill.inline.v1.InlineSuggestionUi

/**
 * Debug-only autofill service. It answers inline requests with one
 * deterministic dataset so the instrumentation test can prove that the IME's
 * inline chip plumbing works, without involving a password manager, a real
 * credential or any production autofill behaviour. Absent from release builds.
 */
@RequiresApi(Build.VERSION_CODES.R)
class FakeAutofillService : AutofillService() {

    @SuppressLint("RestrictedApi")
    @Suppress("UNUSED_PARAMETER", "DEPRECATION")
    override fun onFillRequest(
        request: FillRequest,
        cancellationSignal: CancellationSignal,
        callback: FillCallback,
    ) {
        val inlineRequest = request.inlineSuggestionsRequest
        val spec = inlineRequest?.inlinePresentationSpecs?.firstOrNull()
        val fields = credentialFields(request)
        if (spec == null || fields.isEmpty()) {
            callback.onSuccess(null)
            return
        }

        val dataset = Dataset.Builder()
            .setInlinePresentation(InlinePresentationFactory.create(this, spec))
        for ((id, value) in fields) {
            dataset.setValue(id, AutofillValue.forText(value))
        }
        callback.onSuccess(FillResponse.Builder().addDataset(dataset.build()).build())
    }

    @Suppress("UNUSED_PARAMETER")
    override fun onSaveRequest(request: SaveRequest, callback: SaveCallback) {
        // Nothing is saved: the fake values must never reach a real store.
        callback.onSuccess()
    }

    private fun credentialFields(request: FillRequest): List<Pair<AutofillId, String>> {
        val contexts = request.fillContexts
        val out = mutableListOf<Pair<AutofillId, String>>()
        if (contexts.isEmpty()) return out
        val structure = contexts.last().structure
        for (index in 0 until structure.windowNodeCount) {
            collectCredentials(structure.getWindowNodeAt(index).rootViewNode, out)
        }
        return out
    }

    private fun collectCredentials(
        node: AssistStructure.ViewNode,
        out: MutableList<Pair<AutofillId, String>>,
    ) {
        val id = node.autofillId
        if (id != null) {
            val hints = node.autofillHints.orEmpty()
            val hint = node.hint.orEmpty()
            val isPassword = hints.any { it == View.AUTOFILL_HINT_PASSWORD } ||
                node.inputType and InputType.TYPE_TEXT_VARIATION_PASSWORD != 0 ||
                hint.contains("password", ignoreCase = true)
            val isUsername = hints.any { it == View.AUTOFILL_HINT_USERNAME } ||
                hint.contains("user", ignoreCase = true)
            when {
                isPassword -> out += id to FAKE_PASSWORD
                isUsername -> out += id to FAKE_USERNAME
            }
        }
        for (index in 0 until node.childCount) {
            collectCredentials(node.getChildAt(index), out)
        }
    }

    private companion object {
        const val FAKE_USERNAME = "fake.user@example.com"
        const val FAKE_PASSWORD = "fake-password"
    }
}

/** Builds the slice a test chip renders, with a stable title the test waits for. */
@RequiresApi(Build.VERSION_CODES.R)
private object InlinePresentationFactory {

    @SuppressLint("RestrictedApi")
    fun create(
        service: FakeAutofillService,
        spec: android.widget.inline.InlinePresentationSpec,
    ): android.service.autofill.InlinePresentation {
        // The chip is never tapped by the test, so the pending intent only has
        // to be well formed; it names no specific activity.
        val intent = Intent(FAKE_CHIP_ACTION).setPackage(service.packageName)
        val pendingIntent = PendingIntent.getActivity(
            service,
            0,
            intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val slice = InlineSuggestionUi.newContentBuilder(pendingIntent)
            .setTitle(CHIP_TITLE)
            .setSubtitle("wmkeyboard test")
            .build()
            .slice
        return android.service.autofill.InlinePresentation(slice, spec, false)
    }

    const val CHIP_TITLE = "Fake login"
    const val FAKE_CHIP_ACTION = "com.wasimaster.wmkeyboard.action.FAKE_CHIP"
}
