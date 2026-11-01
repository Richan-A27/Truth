package com.truth.app.input

import android.content.Context
import android.net.Uri
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import org.jsoup.Jsoup

class ReadException(message: String) : Exception(message)

object LinkReader {
    // The headline and opening paragraphs carry an article's main claims.
    // Sending the whole thing turned one Wikipedia link into 13+ claims, each
    // a full retrieval pass plus LLM calls - slow, and enough to hit the LLM
    // provider's rate limit in one request.
    private const val MAX_CHARS = 1500
    private const val MIN_PARAGRAPH_CHARS = 60

    // The headline plus the article's substantial paragraphs. Short <p>s are
    // mostly captions, bylines and cookie notices, so they're skipped.
    suspend fun read(url: String): String = withContext(Dispatchers.IO) {
        val doc = try {
            Jsoup.connect(url)
                .userAgent("Mozilla/5.0 (Linux; Android 14) TruthApp/0.1")
                .timeout(15_000)
                .followRedirects(true)
                .get()
        } catch (e: Exception) {
            throw ReadException("Couldn't open that link.")
        }
        val headline = doc.selectFirst("meta[property=og:title]")?.attr("content")?.takeIf { it.isNotBlank() }
            ?: doc.title()
        val root = doc.selectFirst("article") ?: doc.body()
        val paragraphs = root.select("p").map { it.text().trim() }.filter { it.length >= MIN_PARAGRAPH_CHARS }
        val text = (listOf(headline) + paragraphs).filter { it.isNotBlank() }.joinToString("\n\n")
        if (paragraphs.isEmpty() && headline.isBlank()) throw ReadException("Couldn't find any article text at that link.")
        text.take(MAX_CHARS)
    }
}

object ScreenshotReader {
    // On-device OCR (ML Kit's bundled Latin model): the image never leaves
    // the phone, only the text read from it is sent for verification.
    suspend fun read(context: Context, uri: Uri): String {
        val image = try {
            InputImage.fromFilePath(context, uri)
        } catch (e: Exception) {
            throw ReadException("Couldn't open that image.")
        }
        val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
        try {
            val result = recognizer.process(image).await()
            // blocks come back in reading order; joining lines with spaces
            // turns a screenshot's hard-wrapped text back into sentences
            return result.textBlocks.joinToString("\n\n") { block -> block.lines.joinToString(" ") { it.text } }.trim()
        } catch (e: Exception) {
            throw ReadException("Couldn't read text from that image.")
        } finally {
            recognizer.close()
        }
    }
}
