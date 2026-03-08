# 🎬 Kisan Setu — 5-Minute Demo Video Script

> AWS AI Hackathon 2025 — Demo recording walkthrough
>
> **Total runtime:** 5:00
> **Setup:** Split-screen — WhatsApp (phone/emulator) on left, Kisan Setu dashboard on right
> **Presenter:** Narrates over screen recording

---

## 0:00–0:30 — Introduction

### What the presenter does
1. Open the Kisan Setu dashboard in a browser (S3-hosted URL)
2. Show all four panels: message feed, credit score chart, satellite NDVI map, ledger preview
3. Briefly hover over each panel so judges can see the layout

### What appears on screen
- Dashboard loads with live panels — message feed shows recent interactions, credit chart displays sample scores, satellite map shows Maharashtra region, ledger preview area is ready
- Dashboard URL visible in browser address bar

### Talking points
> "This is Kisan Setu — Farmer's Bridge. India has over 100 million smallholder farmers locked out of formal credit because they have no digital records, no credit history, and they speak regional languages — not English."
>
> "We built an AI-powered WhatsApp assistant that turns the one app farmers already have into a full-service agricultural banking tool. Everything you see here runs serverless on AWS — Bedrock, Textract, Transcribe, Polly, SageMaker, Lambda, DynamoDB, and S3."
>
> "Let me show you the five killer features."

---

## 0:30–1:30 — Feature 1: Text Query (Multilingual AI Assistant)

### What the presenter does
1. Open WhatsApp chat with the Kisan Setu bot number
2. Type and send a Hindi text message:
   ```
   मेरे टमाटर के पत्ते पीले हो रहे हैं, क्या करूं?
   ```
   _(Translation: "My tomato leaves are turning yellow, what should I do?")_
3. Wait for the AI response (5–10 seconds)
4. Switch to dashboard — show the message appearing in the live message feed panel

### What appears on screen
- **WhatsApp:** Bot responds in Hindi with agricultural advice about tomato leaf yellowing — mentions possible causes (nitrogen deficiency, overwatering, pest infection) and recommended actions
- **Dashboard:** Message feed panel updates in real-time showing the incoming query and AI response with timestamp, language tag (hi-IN), and message type (text)

### Talking points
> "Feature one — multilingual AI assistant. I'm sending a Hindi message asking about my tomato plants. The message hits API Gateway, Lambda routes it to our Bedrock orchestrator, which uses the Converse API with Claude."
>
> "Notice the response comes back in Hindi — the farmer's own language. We have multi-model fallback built in: Claude Sonnet, then Haiku, then Amazon Titan. If one model is throttled, the system automatically tries the next."
>
> "On the dashboard, you can see this conversation appearing in real-time via AppSync."

---

## 1:30–2:30 — Feature 2: Ledger Digitization (Image Processing)

### What the presenter does
1. In WhatsApp, tap the attachment icon and select a photo of a handwritten ledger
   - Use a pre-prepared image showing entries like:
     ```
     टमाटर  25 kg  ₹800   15/07
     प्याज   40 kg  ₹1200  15/07
     गेहूं   100 kg ₹2500  14/07
     ```
2. Send the photo to the Kisan Setu bot
3. Wait for the response (10–15 seconds)
4. Switch to dashboard — show the ledger preview panel updating with extracted data

### What appears on screen
- **WhatsApp:** Bot responds with a structured summary:
  ```
  📋 आपकी बही से निकाला गया डेटा:
  1. टमाटर — 25 kg — ₹800 — 15 जुलाई
  2. प्याज — 40 kg — ₹1200 — 15 जुलाई
  3. गेहूं — 100 kg — ₹2500 — 14 जुलाई
  कुल: ₹4,500
  ```
- **Dashboard:** Ledger preview panel shows the extracted table with crop name, quantity, price, and date columns

### Talking points
> "Feature two — smart ledger digitization. Farmers keep handwritten records on paper. I'm sending a photo of a typical ledger page."
>
> "Amazon Textract extracts the crop names, quantities, prices, and dates — even from messy handwriting. The structured data gets stored in DynamoDB, building a digital financial history for this farmer."
>
> "This is the foundation for everything else. Without digital records, there's no credit scoring, no financial identity. Textract handles any orientation, any handwriting quality."

---

## 2:30–3:30 — Feature 3: Voice Interaction

### What the presenter does
1. In WhatsApp, hold the microphone button and record a voice message in Hindi:
   > "मेरी फसल के लिए कौन सी सरकारी योजना उपलब्ध है?"
   >
   > _(Translation: "What government schemes are available for my crops?")_
2. Send the voice message
3. Wait for the response (10–15 seconds)
4. Play the voice response that comes back in WhatsApp
5. Switch to dashboard — show the message feed with transcription text

### What appears on screen
- **WhatsApp:** Bot sends back a voice message (audio note) in Hindi describing relevant government schemes (PM-KISAN, crop insurance, soil health card)
- **WhatsApp:** Also sends a text transcript of the response below the audio
- **Dashboard:** Message feed shows the interaction with type tagged as "voice", includes the transcribed input text

### Talking points
> "Feature three — voice-first interaction. This is critical. Many farmers have low literacy — they can't type or read easily. So they just talk."
>
> "I'm recording a Hindi voice message asking about government schemes. Amazon Transcribe converts the speech to text, Bedrock processes the query, and Amazon Polly generates a voice response back in Hindi."
>
> "The entire pipeline — speech to text to AI to speech — happens in under 15 seconds. No reading, no typing required. This is how you reach the last mile."

---

## 3:30–4:15 — Feature 4: Credit Scoring

### What the presenter does
1. In WhatsApp, type and send:
   ```
   मेरा क्रेडिट स्कोर क्या है?
   ```
   _(Translation: "What is my credit score?")_
2. Wait for the response (5–10 seconds)
3. Switch to dashboard — show the credit score chart panel with the farmer's score

### What appears on screen
- **WhatsApp:** Bot responds with a credit score summary:
  ```
  📊 आपका किसान क्रेडिट स्कोर: 72/100

  आधार:
  • बही रिकॉर्ड: 15 लेनदेन (पिछले 30 दिन)
  • नियमित बिक्री पैटर्न: ✅
  • फसल विविधता: 3 फसलें
  • अनुमानित मासिक आय: ₹12,000–15,000

  यह स्कोर माइक्रोफाइनेंस ऋण के लिए योग्य है।
  ```
- **Dashboard:** Credit score chart updates showing this farmer's score of 72 on the gauge, with a history trend line

### Talking points
> "Feature four — AI credit scoring. Remember those digitized ledger entries? The system analyzes transaction patterns — frequency, crop diversity, revenue consistency — and generates a creditworthiness score."
>
> "This farmer has a score of 72 out of 100 based on 15 transactions over the past month. For the first time, a farmer with zero formal credit history has a verifiable financial identity."
>
> "Banks and microfinance institutions can use this score to assess risk. This could unlock billions in agricultural credit across India."

---

## 4:15–4:45 — Feature 5: Satellite NDVI (Crop Health)

### What the presenter does
1. In WhatsApp, tap the attachment icon → Location → share a GPS pin in Maharashtra
   - Use coordinates: 19.75°N, 75.71°E (Marathwada region)
2. Send the location to the Kisan Setu bot
3. Wait for the response (5–10 seconds)
4. Switch to dashboard — show the satellite NDVI map panel highlighting the location

### What appears on screen
- **WhatsApp:** Bot responds with crop health data:
  ```
  🛰️ उपग्रह फसल स्वास्थ्य रिपोर्ट:

  📍 स्थान: 19.75°N, 75.71°E
  🌱 फसल: प्याज (Onion)
  📈 NDVI: 0.72 — स्वस्थ
  🌿 परिपक्वता: मध्य चरण
  📦 अनुमानित उपज: 4,500 kg/हेक्टेयर

  आपकी फसल अच्छी स्थिति में है!
  ```
- **Dashboard:** Satellite NDVI map zooms to the shared location, shows a color-coded health overlay (green = healthy)

### Talking points
> "Feature five — satellite crop health monitoring. The farmer shares their farm's GPS location. SageMaker analyzes NDVI satellite imagery for that exact spot."
>
> "We get back crop type, maturity stage, health status, and yield estimate. NDVI of 0.72 means healthy vegetation. This enables remote crop monitoring for lenders and insurers — no physical field visits needed."
>
> "On the dashboard, you can see the location plotted on the satellite map with the health overlay."

---

## 4:45–5:00 — Closing

### What the presenter does
1. Switch to the full dashboard view showing all panels populated with data from the demo
2. Slowly scroll or pan across the dashboard to show the complete picture

### What appears on screen
- Dashboard with all panels active: message feed showing all 5 interactions, credit score chart with the farmer's score, satellite NDVI map with the plotted location, ledger preview with extracted data

### Talking points
> "That's Kisan Setu — five AI-powered features, all through WhatsApp, all serverless on AWS."
>
> "We're turning handwritten ledgers into digital records, giving farmers a credit identity for the first time, and monitoring crop health from space. All in the farmer's own language, including voice."
>
> "The entire system costs under $50 a month for 500+ farmers — less than 10 cents per farmer. That's 100x cheaper than traditional banking infrastructure."
>
> "Thank you. Kisan Setu — bridging farmers to financial services."

---

## Pre-Recording Checklist

- [ ] Kisan Setu WhatsApp bot is running and responsive
- [ ] Dashboard is deployed and accessible via S3 URL
- [ ] Prepare handwritten ledger photo (clear, with 3–5 entries in Hindi)
- [ ] Test all 5 interactions end-to-end before recording
- [ ] Screen recording software configured for split-screen (WhatsApp + Dashboard)
- [ ] Audio recording setup tested (clear narration, no background noise)
- [ ] GPS location pin ready for Maharashtra coordinates (19.75, 75.71)
- [ ] WhatsApp chat history cleared for a clean demo start

## Timing Summary

| Segment | Duration | Feature |
|---|---|---|
| 0:00–0:30 | 30s | Introduction — dashboard overview, problem statement |
| 0:30–1:30 | 60s | Text Query — Hindi message, AI response, multi-model fallback |
| 1:30–2:30 | 60s | Ledger Digitization — photo of handwritten ledger, Textract extraction |
| 2:30–3:30 | 60s | Voice Interaction — voice message, Transcribe + Polly pipeline |
| 3:30–4:15 | 45s | Credit Scoring — score from transaction history, financial identity |
| 4:15–4:45 | 30s | Satellite NDVI — GPS location, crop health report |
| 4:45–5:00 | 15s | Closing — full dashboard, impact summary, cost |
