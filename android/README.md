# Truth for Android

Check a claim wherever you meet it on your phone.

- **Select text in any app** (WhatsApp, Chrome, X…) → **Verify with Truth** in the selection menu (under ⋮ if it isn't shown directly).
- **Share → Truth** for a message, a link (the article's headline and opening paragraphs are read on the phone), or a screenshot (text is read on the phone with ML Kit; the image itself is never uploaded).
- Or open the app and paste text / pick a screenshot.

Results show the trust score, verdict, an evidence balance bar, each claim's supporting and contradicting sources, a link to the full report on the website, and a share button that sends a short verdict back to the chat.

## Build and run

Needs JDK 17 and the Android SDK (compileSdk 35).

```bash
cd android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The backend must be running (`uvicorn app.main:app --port 8000` from the repo root). By default the app talks to `http://10.0.2.2:8000`, which is your computer as seen from the Android emulator.

For a real phone or a deployed backend, override the URLs at build time:

```bash
./gradlew assembleDebug -PtruthApiUrl=https://api.example.com -PtruthWebsiteUrl=https://example.com
```

Plain HTTP is only allowed to the emulator's host address (see `res/xml/network_security_config.xml`); anything else must be HTTPS.
