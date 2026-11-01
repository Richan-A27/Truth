package com.truth.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.truth.app.api.ServerConfig
import com.truth.app.input.InputResolver
import com.truth.app.ui.TruthApp
import com.truth.app.ui.VerifyViewModel
import com.truth.app.ui.theme.TruthTheme

// One activity for every way in: the launcher, "Verify with Truth" in another
// app's text-selection menu (PROCESS_TEXT), and Share -> Truth (SEND).
class MainActivity : ComponentActivity() {
    private val viewModel: VerifyViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        ServerConfig.load(this)
        // only on a fresh launch - after rotation the view model already holds
        // the in-flight or finished verification
        if (savedInstanceState == null) handle(intent)
        setContent {
            TruthTheme {
                val state by viewModel.state.collectAsStateWithLifecycle()
                TruthApp(state = state, onVerify = viewModel::verify, onReset = viewModel::reset)
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handle(intent)
    }

    private fun handle(intent: Intent?) {
        InputResolver.fromIntent(intent)?.let(viewModel::verify)
    }
}
