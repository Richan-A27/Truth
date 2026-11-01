package com.truth.app.api

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class TruthApiException(message: String) : Exception(message)

object TruthApi {
    // Matches the backend's minimum (app/pipeline/stage1_input.py).
    const val MIN_CONTENT_CHARS = 10
    // Matches the web app's limit (web/app/api/verify/route.ts).
    const val MAX_CONTENT_CHARS = 5000

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        // a multi-claim article runs several LLM and model passes server-side
        .readTimeout(120, TimeUnit.SECONDS)
        .build()

    suspend fun verify(content: String, sourceUrl: String? = null): Verification = withContext(Dispatchers.IO) {
        val body = JSONObject()
            .put("content", content.take(MAX_CONTENT_CHARS))
            .apply { if (sourceUrl != null) put("source_url", sourceUrl) }
            .toString()
            .toRequestBody("application/json".toMediaType())
        val request = Request.Builder().url("${ServerConfig.apiUrl}/verify").post(body).build()

        val response = try {
            client.newCall(request).execute()
        } catch (e: IOException) {
            throw TruthApiException(
                "Couldn't reach the Truth server at ${ServerConfig.displayAddress}. Check that it's running and that " +
                    "your phone is on the same Wi-Fi or hotspot, or change the server address on the home screen."
            )
        }
        response.use {
            val text = it.body?.string().orEmpty()
            val json = runCatching { JSONObject(text) }.getOrNull()
            // a 5xx detail is an internal error string (e.g. an upstream
            // provider's raw HTTP error), not something to show a user
            if (it.code >= 500) throw TruthApiException("The verification service had a problem. Try again in a minute.")
            if (!it.isSuccessful || json == null) throw TruthApiException(describeError(json))
            parseVerification(json)
        }
    }

    fun reportUrl(runId: String) = "${ServerConfig.websiteUrl}/result/$runId"

    // FastAPI sends `detail` as a string for raised errors, or a list of
    // {msg} objects for request-validation errors.
    private fun describeError(json: JSONObject?): String {
        val detail = json?.opt("detail")
        return when (detail) {
            is String -> detail
            is JSONArray -> (0 until detail.length()).mapNotNull { detail.optJSONObject(it)?.optString("msg") }
                .filter { m -> m.isNotBlank() }
                .joinToString("; ")
                .ifBlank { null }
            else -> null
        } ?: "The verification service couldn't check this right now."
    }

    private fun parseVerification(json: JSONObject) = Verification(
        runId = json.getString("run_id"),
        trustScore = json.getDouble("trust_score").toInt(),
        verdictLabel = json.getString("verdict_label"),
        explanation = json.optString("explanation"),
        claims = json.optJSONArray("claims").objects().map(::parseClaim),
    )

    private fun parseClaim(json: JSONObject) = ClaimResult(
        text = json.getJSONObject("claim").getString("text"),
        trustScore = json.getDouble("trust_score").toInt(),
        verdictLabel = json.getString("verdict_label"),
        explanation = json.optString("explanation"),
        supporting = json.optJSONArray("supporting_evidence").objects().map(::parseEvidence),
        contradicting = json.optJSONArray("contradicting_evidence").objects().map(::parseEvidence),
        neutralCount = json.optJSONObject("breakdown")?.optInt("neutral_count") ?: 0,
    )

    private fun parseEvidence(verdict: JSONObject): Evidence {
        val ev = verdict.getJSONObject("evidence")
        return Evidence(
            source = ev.optString("source").replace('_', ' '),
            title = ev.optString("title"),
            url = ev.optString("url"),
            text = ev.optString("representative_paragraph").ifBlank { ev.optString("snippet") },
            confidence = verdict.optDouble("confidence", 0.0),
        )
    }

    private fun JSONArray?.objects(): List<JSONObject> =
        if (this == null) emptyList() else (0 until length()).mapNotNull { optJSONObject(it) }
}
