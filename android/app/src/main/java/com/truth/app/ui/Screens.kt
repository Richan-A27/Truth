package com.truth.app.ui

import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.truth.app.api.ClaimResult
import com.truth.app.api.Evidence
import com.truth.app.api.ServerConfig
import com.truth.app.api.TruthApi
import com.truth.app.api.Verification
import com.truth.app.api.humanLabel
import com.truth.app.api.verdictForScore
import com.truth.app.input.InputResolver
import com.truth.app.input.VerifyInput
import com.truth.app.ui.theme.LabelCaps
import com.truth.app.ui.theme.TruthColors

private val cardShape = RoundedCornerShape(18.dp)

@Composable
private fun TruthCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = cardShape,
        colors = CardDefaults.cardColors(containerColor = TruthColors.Surface),
        border = BorderStroke(1.dp, TruthColors.Border),
    ) { Box(Modifier.padding(18.dp)) { content() } }
}

@Composable
fun TruthApp(state: VerifyState, onVerify: (VerifyInput) -> Unit, onReset: () -> Unit) {
    Box(Modifier.fillMaxSize().safeDrawingPadding()) {
        AnimatedContent(
            targetState = state,
            contentKey = { it::class },
            transitionSpec = { fadeIn() togetherWith fadeOut() },
            label = "screen",
        ) { s ->
            when (s) {
                VerifyState.Idle -> HomeScreen(onVerify)
                is VerifyState.Reading -> WorkingScreen(title = s.what, preview = null, onCancel = onReset)
                is VerifyState.Verifying -> WorkingScreen(title = "Checking the evidence", preview = s.preview, onCancel = onReset)
                is VerifyState.Done -> ResultScreen(s.preview, s.result, onBack = onReset)
                is VerifyState.Failed -> ErrorScreen(s.message, onBack = onReset)
            }
        }
    }
}

@Composable
private fun HomeScreen(onVerify: (VerifyInput) -> Unit) {
    var text by rememberSaveable { mutableStateOf("") }
    val clipboard = LocalClipboardManager.current
    val pickImage = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri: Uri? ->
        if (uri != null) onVerify(VerifyInput.Image(uri))
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).imePadding().padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        Spacer(Modifier.height(8.dp))
        Text("Truth", style = androidx.compose.material3.MaterialTheme.typography.headlineMedium, color = TruthColors.Ink)
        Text(
            "Paste a claim, a forwarded message or a link. Truth checks it against independent sources and shows you the evidence.",
            color = TruthColors.InkMuted,
            fontSize = 15.sp,
            lineHeight = 22.sp,
        )

        TruthCard {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it.take(TruthApi.MAX_CONTENT_CHARS) },
                    placeholder = { Text("e.g. The Eiffel Tower is located in Berlin, Germany.") },
                    modifier = Modifier.fillMaxWidth().heightIn(min = 120.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = TruthColors.Accent,
                        unfocusedBorderColor = TruthColors.Border,
                    ),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    TextButton(onClick = { clipboard.getText()?.text?.let { text = it.take(TruthApi.MAX_CONTENT_CHARS) } }) {
                        Text("Paste")
                    }
                    Spacer(Modifier.weight(1f))
                    Button(
                        onClick = { InputResolver.fromText(text)?.let(onVerify) },
                        enabled = text.isNotBlank(),
                        colors = ButtonDefaults.buttonColors(containerColor = TruthColors.Accent),
                    ) { Text("Verify") }
                }
            }
        }

        OutlinedButton(
            onClick = { pickImage.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
            modifier = Modifier.fillMaxWidth(),
            border = BorderStroke(1.dp, TruthColors.Border),
        ) { Text("Check a screenshot", color = TruthColors.Ink) }

        TruthCard {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("USE IT FROM ANY APP", style = LabelCaps, color = TruthColors.Accent)
                Tip("Select text", "In WhatsApp, Chrome or anywhere: select text, then tap “Verify with Truth” in the menu (under ⋮ if it's not shown).")
                Tip("Share", "Share a message, link or screenshot to Truth.")
            }
        }

        ServerRow()
    }
}

// Which computer the app sends checks to. Its address changes between
// networks (home Wi-Fi vs a phone hotspot), so it's editable here.
@Composable
private fun ServerRow() {
    val context = LocalContext.current
    var address by remember { mutableStateOf(ServerConfig.displayAddress) }
    var editing by remember { mutableStateOf(false) }

    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Server: $address", color = TruthColors.InkMuted, fontSize = 13.sp, modifier = Modifier.weight(1f))
        TextButton(onClick = { editing = true }) { Text("Change") }
    }

    if (editing) {
        var draft by remember { mutableStateOf(ServerConfig.customHost.orEmpty()) }
        AlertDialog(
            onDismissRequest = { editing = false },
            title = { Text("Truth server") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(
                        "The IP address of the computer running Truth, on the same Wi-Fi or hotspot as this phone. Leave empty to use the default.",
                        fontSize = 14.sp,
                        color = TruthColors.InkMuted,
                    )
                    OutlinedTextField(
                        value = draft,
                        onValueChange = { draft = it },
                        placeholder = { Text("e.g. 192.168.1.56") },
                        singleLine = true,
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    ServerConfig.setHost(context, draft)
                    address = ServerConfig.displayAddress
                    editing = false
                }) { Text("Save") }
            },
            dismissButton = { TextButton(onClick = { editing = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun Tip(title: String, body: String) {
    Column {
        Text(title, fontWeight = FontWeight.Medium, color = TruthColors.Ink, fontSize = 14.sp)
        Text(body, color = TruthColors.InkMuted, fontSize = 13.sp, lineHeight = 19.sp)
    }
}

@Composable
private fun WorkingScreen(title: String, preview: String?, onCancel: () -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(24.dp),
    ) {
        Spacer(Modifier.height(32.dp))
        SpinnerRing(72.dp)
        Text(title, style = androidx.compose.material3.MaterialTheme.typography.titleLarge, color = TruthColors.Ink)
        if (preview != null) {
            Text(
                "“$preview”",
                color = TruthColors.InkMuted,
                fontSize = 14.sp,
                lineHeight = 20.sp,
                maxLines = 4,
                overflow = TextOverflow.Ellipsis,
            )
            TruthCard { PipelineProgress() }
        }
        TextButton(onClick = onCancel) { Text("Cancel") }
    }
}

@Composable
private fun ErrorScreen(message: String, onBack: () -> Unit) {
    Column(
        Modifier.fillMaxSize().padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Couldn't check that", style = androidx.compose.material3.MaterialTheme.typography.titleLarge, color = TruthColors.Ink)
        Spacer(Modifier.height(10.dp))
        Text(message, color = TruthColors.InkMuted, fontSize = 15.sp, lineHeight = 22.sp)
        Spacer(Modifier.height(24.dp))
        Button(onClick = onBack, colors = ButtonDefaults.buttonColors(containerColor = TruthColors.Accent)) {
            Text("Try something else")
        }
    }
}

@Composable
private fun ResultScreen(preview: String, result: Verification, onBack: () -> Unit) {
    val context = LocalContext.current
    val verdict = verdictForScore(result.trustScore)
    var shown by remember { mutableStateOf(false) }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, contentDescription = "Back") }
            Spacer(Modifier.weight(1f))
            IconButton(onClick = { context.startActivity(shareIntent(preview, result)) }) {
                Icon(Icons.Default.Share, contentDescription = "Share verdict")
            }
        }

        TruthCard {
            Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                TrustGauge(result.trustScore, 120.dp)
                Spacer(Modifier.height(14.dp))
                VerdictPill(humanLabel(result.verdictLabel), verdict)
                Spacer(Modifier.height(14.dp))
                Text(
                    "“$preview”",
                    color = TruthColors.Ink,
                    fontSize = 15.sp,
                    lineHeight = 21.sp,
                    maxLines = 3,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        // the claim-level detail eases in after the headline verdict has landed
        androidx.compose.runtime.LaunchedEffect(Unit) { shown = true }
        AnimatedVisibility(visible = shown, enter = fadeIn() + slideInVertically { it / 6 }) {
            Column {
                if (result.claims.size != 1) {
                    Spacer(Modifier.height(14.dp))
                    Text(result.explanation, color = TruthColors.InkMuted, fontSize = 14.sp, lineHeight = 21.sp)
                }
                if (result.claims.isNotEmpty()) {
                    Spacer(Modifier.height(20.dp))
                    Text("CLAIM BY CLAIM", style = LabelCaps, color = TruthColors.InkMuted)
                    Spacer(Modifier.height(10.dp))
                    result.claims.forEachIndexed { i, claim ->
                        ClaimCard(claim, initiallyOpen = i == 0, onOpenSource = { url -> openUrl(context, url) })
                        Spacer(Modifier.height(10.dp))
                    }
                }
                Spacer(Modifier.height(6.dp))
                OutlinedButton(
                    onClick = { openUrl(context, TruthApi.reportUrl(result.runId)) },
                    modifier = Modifier.fillMaxWidth(),
                    border = BorderStroke(1.dp, TruthColors.Border),
                ) { Text("Open full report", color = TruthColors.Ink) }
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}

@Composable
private fun ClaimCard(claim: ClaimResult, initiallyOpen: Boolean, onOpenSource: (String) -> Unit) {
    var open by rememberSaveable { mutableStateOf(initiallyOpen) }
    TruthCard {
        Column {
            Row(
                Modifier.fillMaxWidth().clickable { open = !open },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TrustGauge(claim.trustScore, 48.dp)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(claim.text, color = TruthColors.Ink, fontSize = 14.sp, fontWeight = FontWeight.Medium, lineHeight = 20.sp)
                    Spacer(Modifier.height(6.dp))
                    VerdictPill(humanLabel(claim.verdictLabel), verdictForScore(claim.trustScore))
                }
                Icon(
                    if (open) Icons.Default.KeyboardArrowUp else Icons.Default.KeyboardArrowDown,
                    contentDescription = if (open) "Collapse" else "Expand",
                    tint = TruthColors.InkMuted,
                )
            }
            AnimatedVisibility(open) {
                Column {
                    Spacer(Modifier.height(14.dp))
                    HorizontalDivider(color = TruthColors.Border)
                    Spacer(Modifier.height(14.dp))
                    Text(claim.explanation, color = TruthColors.InkMuted, fontSize = 14.sp, lineHeight = 21.sp)
                    Spacer(Modifier.height(14.dp))
                    EvidenceBalance(claim.supporting.size, claim.contradicting.size, claim.neutralCount)
                    EvidenceGroup("SUPPORTING EVIDENCE", TruthColors.Success, claim.supporting, onOpenSource)
                    EvidenceGroup("CONTRADICTING EVIDENCE", TruthColors.Danger, claim.contradicting, onOpenSource)
                }
            }
        }
    }
}

@Composable
private fun EvidenceGroup(title: String, color: androidx.compose.ui.graphics.Color, items: List<Evidence>, onOpen: (String) -> Unit) {
    if (items.isEmpty()) return
    Spacer(Modifier.height(16.dp))
    Text(title, style = LabelCaps, color = color)
    items.forEach { ev ->
        Spacer(Modifier.height(8.dp))
        Card(
            modifier = Modifier.fillMaxWidth().clickable(enabled = ev.url.startsWith("http")) { onOpen(ev.url) },
            shape = RoundedCornerShape(12.dp),
            colors = CardDefaults.cardColors(containerColor = TruthColors.Bg),
            border = BorderStroke(1.dp, TruthColors.Border),
        ) {
            Column(Modifier.padding(12.dp)) {
                Row {
                    Text(ev.source.uppercase(), style = LabelCaps, color = TruthColors.InkMuted, modifier = Modifier.weight(1f))
                    Text("${(ev.confidence * 100).toInt()}%", fontSize = 11.sp, color = TruthColors.InkMuted)
                }
                Spacer(Modifier.height(4.dp))
                Text(ev.title, fontWeight = FontWeight.Medium, fontSize = 14.sp, color = TruthColors.Ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(ev.text, fontSize = 13.sp, lineHeight = 18.sp, color = TruthColors.InkMuted, maxLines = 3, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

private fun openUrl(context: android.content.Context, url: String) {
    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
}

// A short verdict to paste back into the chat the claim came from.
private fun shareIntent(preview: String, result: Verification): Intent {
    val quote = if (preview.length > 140) preview.take(140) + "…" else preview
    val text = "Truth check: “$quote”\n${humanLabel(result.verdictLabel)} (${result.trustScore}/100)\n${TruthApi.reportUrl(result.runId)}"
    return Intent.createChooser(
        Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text),
        "Share verdict",
    )
}
