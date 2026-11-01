package com.truth.app.api

// Mirrors the backend's VerificationResponse (app/schemas/verification.py),
// keeping only what the app displays.

data class Evidence(
    val source: String,
    val title: String,
    val url: String,
    val text: String,
    val confidence: Double,
)

data class ClaimResult(
    val text: String,
    val trustScore: Int,
    val verdictLabel: String,
    val explanation: String,
    val supporting: List<Evidence>,
    val contradicting: List<Evidence>,
    val neutralCount: Int,
)

data class Verification(
    val runId: String,
    val trustScore: Int,
    val verdictLabel: String,
    val explanation: String,
    val claims: List<ClaimResult>,
)

enum class Verdict { TRUE, FALSE, MIXED }

// Same buckets as the web app's gauge colours (TrustScoreGauge.tsx).
fun verdictForScore(score: Int): Verdict = when {
    score >= 65 -> Verdict.TRUE
    score <= 35 -> Verdict.FALSE
    else -> Verdict.MIXED
}

fun humanLabel(verdictLabel: String): String =
    verdictLabel.replace('_', ' ').replaceFirstChar { it.uppercase() }
