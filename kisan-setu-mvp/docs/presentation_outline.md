# 🌾 Kisan Setu — Hackathon Presentation Outline

> 15-slide deck for AWS AI Hackathon 2025

---

## Slide 1: Title

- **Kisan Setu (किसान सेतु) — Farmer's Bridge**
- AI-powered WhatsApp assistant for India's 100M+ smallholder farmers
- AWS AI Hackathon 2025
- Contributor: Upmanyu Jha — Machine Learning Engineer

---

## Slide 2: The Problem

- 100M+ Indian smallholder farmers are locked out of formal credit
- No digital records — transactions on handwritten ledgers
- No credit history — banks can't assess cash-only farmers
- Language barriers — regional languages, not English
- Result: 30–60% interest rates from informal moneylenders

---

## Slide 3: The Scale

- India's agriculture: ~18% of GDP, 42% of workforce
- 86% of farmers are smallholders (< 2 hectares)
- $350B+ annual agricultural output with minimal digital infrastructure
- WhatsApp already used by 500M+ Indians — the one app farmers have
- Massive untapped market for AI-driven financial inclusion

---

## Slide 4: Our Solution

- **Kisan Setu** turns WhatsApp into a full-service agricultural banking assistant
- No app downloads, no literacy requirements, no new hardware
- Farmers send text, photos, or voice messages in their own language
- AI responds with digitized records, credit scores, crop health insights
- Entirely serverless on AWS — scales from 1 to 1M farmers

---

## Slide 5: How It Works

- Farmer sends message via WhatsApp → API Gateway webhook
- Lambda Router classifies message type (text / image / voice)
- Routes to specialized processor (Bedrock / Textract / Transcribe)
- AI processes query → stores results in DynamoDB
- Response sent back via WhatsApp in farmer's language
- Real-time dashboard via AppSync shows all activity

---

## Slide 6: Feature 1 — Smart Ledger Digitization

- Farmer photographs handwritten ledger → sends via WhatsApp
- Amazon Textract extracts crop name, quantity, price, date
- Handles any orientation, any handwriting quality
- Structured data stored in DynamoDB — building a digital financial history
- First step toward a verifiable credit identity

---

## Slide 7: Feature 2 — Multilingual AI Assistant

- Text queries in Hindi, Marathi, Tamil, or English
- Amazon Bedrock with Claude via Converse API
- Multi-model fallback: Claude Sonnet → Haiku → Amazon Titan
- Agricultural advice, market prices, government scheme information
- System prompt tuned for Kisan Setu agricultural persona

---

## Slide 8: Feature 3 — Voice-First Interaction

- Farmer sends voice message in any supported language
- Amazon Transcribe converts speech to text (30+ languages)
- AI processes the query through Bedrock orchestrator
- Amazon Polly generates voice response in farmer's language
- Critical for low-literacy users — no reading or typing required

---

## Slide 9: Feature 4 — AI Credit Scoring

- Digitized ledger history + transaction patterns analyzed by ML model
- Generates creditworthiness score for farmers with zero formal credit history
- Gives farmers a verifiable financial identity for the first time
- Enables banks and microfinance institutions to assess risk
- Potential to unlock billions in agricultural credit

---

## Slide 10: Feature 5 — Satellite Crop Health

- Farmer shares GPS coordinates of their farm
- SageMaker analyzes NDVI satellite imagery for that location
- Returns: crop type, maturity stage, health status, yield estimate
- Enables remote crop monitoring for lenders and insurers
- Reduces need for physical field visits — saves time and cost

---

## Slide 11: Architecture Deep Dive

- **Bedrock** — AI reasoning (Converse API, multi-model fallback)
- **Textract** — Handwritten ledger OCR
- **Transcribe + Polly** — Voice pipeline (speech-to-text, text-to-speech)
- **SageMaker** — Satellite NDVI crop health analysis
- **Lambda + API Gateway + AppSync** — Serverless compute, webhooks, real-time GraphQL
- **DynamoDB + S3** — Data storage, document storage, dashboard hosting
- Fully serverless — zero idle cost, auto-scaling, pay-per-use

---

## Slide 12: Live Demo

- Dashboard URL: S3-hosted static website (deployed via CDK)
- Live panels: message feed, credit score charts, satellite NDVI map, ledger preview
- WhatsApp interaction walkthrough:
  - Text query → AI response in Hindi
  - Photo of ledger → structured data extraction
  - Voice message → voice response in farmer's language

---

## Slide 13: Cost Analysis

- **Total: ~$32–50/month** for 500+ farmers
- **< $0.10 per farmer per month** (< ₹8)
- Breakdown: Lambda $5–8, Bedrock $15–20, Textract $5–8, Transcribe $2–4, Polly $1–2, DynamoDB $2–4, S3 $1–2, API Gateway $1–2
- Key optimizations: Lambda reserved concurrency, Bedrock response caching, DynamoDB on-demand pricing
- 100x cheaper than traditional banking infrastructure

---

## Slide 14: Impact & Roadmap

- **Target:** 100M+ smallholder farmers across India
- **Near-term:** Government API integrations (PM-KISAN, eNAM, soil health cards)
- **Mid-term:** Partnership with microfinance institutions for credit disbursement
- **Long-term:** Expand to Southeast Asia, Sub-Saharan Africa — 500M+ farmers globally
- **Scale plan:** Multi-region AWS deployment, language expansion, offline-first sync

---

## Slide 15: Thank You / Q&A

- **Kisan Setu (किसान सेतु)** — Bridging farmers to financial services
- Contributor: Upmanyu Jha — Machine Learning Engineer
- GitHub: [Repository Link]
- Live Dashboard: [Dashboard URL]
- Demo Video: [Video Link]
- Built with ❤️ for AWS AI Hackathon 2025 🇮🇳
