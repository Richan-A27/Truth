package com.truth.app.api

import android.content.Context
import android.net.Uri
import com.truth.app.BuildConfig

// Where the backend lives. Defaults to the build-time URLs; can be pointed
// at a laptop on the same Wi-Fi or hotspot from the app, since that address
// changes from network to network.
object ServerConfig {
    private const val PREFS = "server"
    private const val KEY_HOST = "host"
    private const val API_PORT = 8000
    private const val WEBSITE_PORT = 3000

    @Volatile
    private var host: String? = null

    fun load(context: Context) {
        host = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_HOST, null)
    }

    // Accepts "192.168.1.56", "192.168.1.56:8000" or a full URL; keeps just the host.
    fun setHost(context: Context, input: String) {
        val cleaned = input.trim().let { if ("://" in it) Uri.parse(it).host.orEmpty() else it.substringBefore(':').substringBefore('/') }
        host = cleaned.ifBlank { null }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_HOST, host).apply()
    }

    val customHost: String? get() = host

    val apiUrl: String get() = host?.let { "http://$it:$API_PORT" } ?: BuildConfig.TRUTH_API_URL

    val websiteUrl: String get() = host?.let { "http://$it:$WEBSITE_PORT" } ?: BuildConfig.TRUTH_WEBSITE_URL

    val displayAddress: String get() = Uri.parse(apiUrl).host ?: apiUrl
}
