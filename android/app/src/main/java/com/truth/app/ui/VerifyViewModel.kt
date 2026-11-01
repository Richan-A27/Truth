package com.truth.app.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.truth.app.api.TruthApi
import com.truth.app.api.TruthApiException
import com.truth.app.api.Verification
import com.truth.app.input.LinkReader
import com.truth.app.input.ReadException
import com.truth.app.input.ScreenshotReader
import com.truth.app.input.VerifyInput
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

sealed interface VerifyState {
    data object Idle : VerifyState
    data class Reading(val what: String) : VerifyState
    data class Verifying(val preview: String) : VerifyState
    data class Done(val preview: String, val result: Verification) : VerifyState
    data class Failed(val message: String) : VerifyState
}

class VerifyViewModel(app: Application) : AndroidViewModel(app) {
    private val _state = MutableStateFlow<VerifyState>(VerifyState.Idle)
    val state: StateFlow<VerifyState> = _state

    private var job: Job? = null

    fun verify(input: VerifyInput) {
        job?.cancel()
        job = viewModelScope.launch {
            try {
                val (content, sourceUrl) = when (input) {
                    is VerifyInput.Text -> input.text to null
                    is VerifyInput.Link -> {
                        _state.value = VerifyState.Reading("Reading the article…")
                        LinkReader.read(input.url) to input.url
                    }
                    is VerifyInput.Image -> {
                        _state.value = VerifyState.Reading("Reading text from the screenshot…")
                        ScreenshotReader.read(getApplication(), input.uri) to null
                    }
                }
                if (content.trim().length < TruthApi.MIN_CONTENT_CHARS) {
                    _state.value = VerifyState.Failed(
                        if (input is VerifyInput.Image) "Couldn't find enough text in that image to check."
                        else "That's too short to check. Try at least a full sentence."
                    )
                    return@launch
                }
                val preview = content.trim().take(280)
                _state.value = VerifyState.Verifying(preview)
                _state.value = VerifyState.Done(preview, TruthApi.verify(content.trim(), sourceUrl))
            } catch (e: ReadException) {
                _state.value = VerifyState.Failed(e.message ?: "Couldn't read that.")
            } catch (e: TruthApiException) {
                _state.value = VerifyState.Failed(e.message ?: "Verification failed.")
            }
        }
    }

    fun reset() {
        job?.cancel()
        _state.value = VerifyState.Idle
    }
}
