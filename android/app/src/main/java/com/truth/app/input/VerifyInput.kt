package com.truth.app.input

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.util.Patterns

// What the user handed us, before it becomes plain text for the backend.
sealed interface VerifyInput {
    data class Text(val text: String) : VerifyInput
    data class Link(val url: String) : VerifyInput
    data class Image(val uri: Uri) : VerifyInput
}

object InputResolver {
    // A shared link with little else around it ("check this out https://...")
    // means "verify that article"; a long message that happens to contain a
    // link is verified as the message itself.
    private const val MAX_TEXT_AROUND_LINK = 40

    fun fromIntent(intent: Intent?): VerifyInput? {
        intent ?: return null
        return when (intent.action) {
            Intent.ACTION_PROCESS_TEXT ->
                intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)?.toString()?.let(::fromText)
            Intent.ACTION_SEND -> when {
                intent.type?.startsWith("image/") == true -> streamUri(intent)?.let { VerifyInput.Image(it) }
                else -> intent.getStringExtra(Intent.EXTRA_TEXT)?.let(::fromText)
            }
            else -> null
        }
    }

    fun fromText(raw: String): VerifyInput? {
        val text = raw.trim()
        if (text.isEmpty()) return null
        val matcher = Patterns.WEB_URL.matcher(text)
        if (matcher.find()) {
            val url = matcher.group()
            val rest = text.removeRange(matcher.start(), matcher.end()).trim()
            if (rest.length <= MAX_TEXT_AROUND_LINK && url.startsWith("http")) return VerifyInput.Link(url)
        }
        return VerifyInput.Text(text)
    }

    @Suppress("DEPRECATION")
    private fun streamUri(intent: Intent): Uri? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            intent.getParcelableExtra(Intent.EXTRA_STREAM)
        }
}
