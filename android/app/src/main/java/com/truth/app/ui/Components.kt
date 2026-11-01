package com.truth.app.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.truth.app.api.Verdict
import com.truth.app.api.verdictForScore
import com.truth.app.ui.theme.TruthColors
import kotlinx.coroutines.delay

fun colorFor(verdict: Verdict): Color = when (verdict) {
    Verdict.TRUE -> TruthColors.Success
    Verdict.FALSE -> TruthColors.Danger
    Verdict.MIXED -> TruthColors.Neutral
}

// The trust-score ring from the web app: sweeps in from empty while the
// number counts up to the score.
@Composable
fun TrustGauge(score: Int, size: Dp, modifier: Modifier = Modifier) {
    val progress = remember(score) { Animatable(0f) }
    LaunchedEffect(score) {
        progress.animateTo(score.coerceIn(0, 100) / 100f, tween(1100, easing = FastOutSlowInEasing))
    }
    val color = colorFor(verdictForScore(score))
    Box(
        modifier.size(size).semantics { contentDescription = "Trust score $score out of 100" },
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(size)) {
            val stroke = this.size.minDimension * 0.09f
            drawArc(TruthColors.Border, 0f, 360f, false, style = Stroke(stroke))
            drawArc(color, -90f, 360f * progress.value, false, style = Stroke(stroke, cap = StrokeCap.Round))
        }
        Text(
            text = (progress.value * 100).toInt().toString(),
            fontFamily = FontFamily.Serif,
            fontWeight = FontWeight.SemiBold,
            fontSize = (size.value * 0.3f).sp,
            color = TruthColors.Ink,
        )
    }
}

@Composable
fun SpinnerRing(size: Dp) {
    val rotation by rememberInfiniteTransition(label = "spin").animateFloat(
        0f, 360f, infiniteRepeatable(tween(1100, easing = LinearEasing)), label = "rotation",
    )
    Canvas(Modifier.size(size).rotate(rotation)) {
        val stroke = this.size.minDimension * 0.09f
        drawArc(TruthColors.Border, 0f, 360f, false, style = Stroke(stroke))
        drawArc(TruthColors.Accent, -90f, 80f, false, style = Stroke(stroke, cap = StrokeCap.Round))
    }
}

@Composable
fun VerdictPill(label: String, verdict: Verdict) {
    val color = colorFor(verdict)
    Text(
        text = label,
        color = color,
        fontSize = 12.sp,
        fontWeight = FontWeight.SemiBold,
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.1f))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    )
}

// Supporting / contradicting / off-topic as one proportional bar.
@Composable
fun EvidenceBalance(supporting: Int, contradicting: Int, neutral: Int) {
    val total = supporting + contradicting + neutral
    if (total == 0) return
    val segments = listOf(
        Triple(supporting, TruthColors.Success, "supporting"),
        Triple(contradicting, TruthColors.Danger, "contradicting"),
        Triple(neutral, TruthColors.Neutral.copy(alpha = 0.4f), "off-topic"),
    )
    val grow = remember { Animatable(0f) }
    LaunchedEffect(Unit) { grow.animateTo(1f, tween(700, easing = FastOutSlowInEasing)) }
    Column {
        Row(
            Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(50)).background(TruthColors.Border),
        ) {
            segments.filter { it.first > 0 }.forEach { (count, color, _) ->
                Box(Modifier.weight(count.toFloat()).fillMaxHeight().alpha(grow.value).background(color))
            }
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            segments.forEach { (count, color, label) ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(8.dp).clip(CircleShape).background(color))
                    Spacer(Modifier.width(5.dp))
                    Text("$count $label", fontSize = 12.sp, color = TruthColors.InkMuted)
                }
            }
        }
    }
}

// The pipeline's phases ticking along while a request is in flight. The
// backend doesn't stream progress, so this paces itself on typical timings
// and holds on the last step - same approach as the web app.
private val PIPELINE_STEPS = listOf(
    "Extracting claims" to 900L,
    "Searching Wikipedia and Google News" to 2400L,
    "Ranking the evidence" to 1500L,
    "Checking each source against the claim" to 1800L,
    "Scoring and writing the explanation" to Long.MAX_VALUE,
)

@Composable
fun PipelineProgress() {
    var active by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (active < PIPELINE_STEPS.lastIndex) {
            delay(PIPELINE_STEPS[active].second)
            active++
        }
    }
    val pulse by rememberInfiniteTransition(label = "pulse").animateFloat(
        0.4f, 1f, infiniteRepeatable(tween(600), RepeatMode.Reverse), label = "pulse",
    )
    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
        PIPELINE_STEPS.forEachIndexed { i, (label, _) ->
            val done = i < active
            val current = i == active
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.alpha(if (i <= active) 1f else 0.4f)) {
                Box(
                    Modifier
                        .size(22.dp)
                        .clip(CircleShape)
                        .then(
                            if (done) Modifier.background(TruthColors.Accent)
                            else Modifier.border(1.5.dp, if (current) TruthColors.Accent else TruthColors.Border, CircleShape)
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    when {
                        done -> Icon(Icons.Default.Check, null, tint = Color.White, modifier = Modifier.size(14.dp))
                        current -> Box(Modifier.size(9.dp).alpha(pulse).clip(CircleShape).background(TruthColors.Accent))
                        else -> Box(Modifier.size(9.dp).clip(CircleShape).background(TruthColors.Border))
                    }
                }
                Spacer(Modifier.width(12.dp))
                Text(
                    text = if (current) "$label…" else label,
                    fontSize = 15.sp,
                    fontWeight = if (current) FontWeight.Medium else FontWeight.Normal,
                    color = if (i <= active) TruthColors.Ink else TruthColors.InkMuted,
                )
            }
        }
    }
}
