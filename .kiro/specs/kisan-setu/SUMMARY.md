> **Note:** This is a historical spec document representing the original design intent. The implementation evolved beyond this spec. See `kisan-setu-mvp/README.md` for current architecture, including the 5-model APAC inference profile fallback chain and live FPO admin dashboard.

# Kisan-Setu - Executive Summary

## Quick Overview

**Kisan-Setu** is the "Chief Intelligence Officer" for Farmer Producer Organizations (FPOs) - a voice-first, AI-powered operating system that digitizes rural agriculture operations through WhatsApp, requiring zero typing and zero new apps.

## The Problem

Rural farmers in India cannot access institutional credit because they lack digital credit histories. Existing agri-tech apps require manual data entry, leading to low adoption (<5%) among semi-literate farmers.

## Our Solution

A "Zero-UI" operating system that passively digitizes FPO operations by:
- Converting photos of handwritten ledgers into structured banking data
- Using voice interactions in local dialects (Hindi/Marathi/Tamil)
- Predicting crop yields from satellite imagery
- Generating alternative credit scores for farmers

## Key Differentiators

| Feature | Competitors (DeHaat, etc.) | Kisan-Setu |
|---------|---------------------------|------------|
| Interface | Mobile app with forms | WhatsApp (already installed) |
| Data entry | Manual typing required | Photo + voice (zero typing) |
| Language | English/Hindi text | Voice in 3+ dialects |
| Technology | Simple chatbots (RAG) | AWS Bedrock Agents (reasoning) |
| Credit scoring | Not available | Automated from digital twin |

## Core Features

### 1. Handwritten Ledger Digitization
- **Technology:** Amazon Textract Queries
- **Input:** Photo of crumpled Hindi receipt
- **Output:** Structured JSON (quantity, moisture, price, date)
- **Why it matters:** Banks need structured data, not paper trails

### 2. Multilingual Voice Interface
- **Technology:** Amazon Transcribe + Polly
- **Languages:** Hindi, Marathi, Tamil (with dialects)
- **Why it matters:** 60% of farmers are semi-literate

### 3. Satellite Yield Prediction
- **Technology:** Amazon SageMaker Geospatial (Sentinel-2)
- **Output:** NDVI-based crop maturity and yield estimates
- **Why it matters:** Plan logistics before harvest

### 4. Automated Credit Scoring
- **Formula:** 0-100 score based on 5 components
- **Why it matters:** Makes farmers bankable to institutions

### 5. Offline-First Sync
- **Technology:** AWS AppSync
- **Why it matters:** Works in low-connectivity rural areas

## Credit Scoring Formula

**Total Score = 100 points**

```
Supply Consistency (30 pts)
├── Delivery Frequency (10)
├── Schedule Adherence (10)
└── Fulfillment Rate (10)

Quality Metrics (25 pts)
├── Moisture Consistency (10)
├── Grade Consistency (10)
└── Rejection Rate (5)

Transaction History (20 pts)
├── Volume Score (7)
├── Relationship Length (7)
└── Success Rate (6)

Financial Behavior (15 pts)
├── Payment Timeliness (10)
└── Outstanding Dues (5)

Operational Transparency (10 pts)
├── Digitization Frequency (5)
└── Documentation Completeness (5)
```

**Example:** A farmer with 87/100 score is eligible for standard loans up to 50% of annual volume value.

## AWS Architecture

### Services Used

| Layer | Service | Purpose |
|-------|---------|---------|
| Interface | WhatsApp Business API | User interaction |
| Gateway | API Gateway + AppSync | Request routing, offline sync |
| Compute | AWS Lambda | Serverless processing |
| AI/ML | AWS Bedrock (Claude 3.5) | Intelligent orchestration |
| Vision | Amazon Textract Queries | Handwriting extraction |
| Voice | Transcribe + Polly | Speech processing |
| Geospatial | SageMaker Geospatial | Satellite analysis |
| Storage | DynamoDB + S3 | Data persistence |
| Monitoring | CloudWatch + X-Ray | Observability |

### Data Strategy

**Data Sources:**
- WhatsApp messages (text, voice, images)
- Handwritten ledger photos
- GPS coordinates
- Sentinel-2 satellite imagery

**Storage:**
- **DynamoDB:** Single-table design for structured data (farmers, transactions, scores)
- **S3:** Unstructured data (images, audio, satellite imagery)
- **AppSync:** Offline-first sync for tablets

**Processing:**
```
Raw Data → Validation → AI Processing → Structuring → Storage
           (Lambda)    (Textract/      (Bedrock)    (DynamoDB/S3)
                       Transcribe/
                       SageMaker)
```

## Cost Optimization

**Target:** <$50/month per FPO (serving 500+ farmers)

### Cost Breakdown

| Service | Monthly Cost |
|---------|--------------|
| DynamoDB | $3 |
| S3 | $2 |
| Lambda | $5 |
| Bedrock | $15 |
| Textract | $10 |
| Transcribe | $8 |
| SageMaker Geospatial | $5 |
| AppSync | $2 |
| **Total** | **$50** |

### Optimization Strategies

1. **Bedrock Knowledge Bases:** Store FPO guidelines to reduce long-context prompting (40% cost reduction)
2. **SageMaker Spot Instances:** Use Spot for training (90% cost reduction)
3. **Request Batching:** Batch similar AI requests (15% cost reduction)
4. **Caching:** Cache satellite imagery for 24 hours (30% reduction in API calls)
5. **DynamoDB On-Demand:** Pay only for actual usage (no over-provisioning)

## 24-Hour Implementation Goal

**Objective:** Deploy a working WhatsApp bot that digitizes handwritten Hindi ledgers.

**Success Criteria:**
- ✅ Receive photo via WhatsApp
- ✅ Extract quantity, moisture, price from Hindi ledger
- ✅ Store structured data in DynamoDB
- ✅ Send JSON response via WhatsApp
- ✅ End-to-end latency <15 seconds

**Timeline:**
- Hours 0-4: Infrastructure setup (CDK, DynamoDB, S3)
- Hours 4-8: Lambda functions (router, processor)
- Hours 8-12: Textract integration and testing
- Hours 12-16: Bedrock Agent configuration
- Hours 16-20: WhatsApp integration
- Hours 20-24: End-to-end testing

**Deployment:**
```bash
# 1. Create AWS resources
aws s3 mb s3://kisan-setu-raw
aws dynamodb create-table --table-name KisanSetuData ...

# 2. Deploy CDK stack
cdk deploy

# 3. Configure WhatsApp webhook
# Set webhook URL in Meta Developer Console

# 4. Test
# Send photo via WhatsApp → Receive JSON response
```

## Social Impact

### Financial Inclusion
By digitizing the "first mile" of agriculture, we generate the data banks need to lend to farmers who lack traditional credit histories.

### Sustainability
Satellite-driven advice prevents fertilizer overuse and optimizes harvest timing, reducing waste.

### Scalability
Built on AWS serverless patterns, the solution can scale from 1 FPO to 1000+ FPOs without infrastructure changes.

## Market Opportunity

- **Target:** 10,000+ FPOs in India
- **Farmers per FPO:** 500-1000
- **Total addressable market:** 5-10 million farmers
- **Revenue model:** $50/month per FPO = $500K-$1M MRR at scale

## Competitive Advantage

### Technical Moat
1. **Deep AWS Integration:** Bedrock Agents (not just RAG chatbots)
2. **Textract Queries:** Natural language questions to documents (not standard OCR)
3. **SageMaker Geospatial:** Orbital analysis for yield prediction
4. **Zero-UI Design:** No app installation, no typing

### Operational Moat
1. **Network Effects:** More farmers → better credit models
2. **Data Moat:** Proprietary transaction histories
3. **First-Mover:** First to digitize "Kaccha" records at scale

## Use Case Flow

### Current State (Competitors)
```
Farmer → Opens app → Types data → Submits form → Gets response
         (Friction)   (Literacy)  (Time)
```

### Kisan-Setu Flow
```
Farmer → Takes photo → Sends via WhatsApp → Gets structured data
         (Natural)     (Already installed)   (Instant)
```

### The Transformation

**Input:** Crumpled, handwritten Hindi receipt (unstructured reality)  
↓  
**Process:** AWS Bedrock Agent + Textract Queries  
↓  
**Output:** Neat JSON/Excel table (bankable data)

## Key Metrics

### Technical Metrics
- Latency: <15 seconds end-to-end
- Accuracy: >85% field extraction confidence
- Uptime: 99.9% availability
- Cost: <$50/month per FPO

### Business Metrics
- Adoption: >80% of farmers in pilot FPO
- Credit access: 50% increase in loan approvals
- Efficiency: 10x faster than manual data entry
- Retention: >90% monthly active users

## Roadmap

### Phase 1 (Month 1) - MVP
- WhatsApp integration
- Ledger digitization
- Basic credit scoring

### Phase 2 (Months 2-3)
- Voice interface
- Satellite yield prediction
- Offline tablet mode

### Phase 3 (Months 4-6)
- Multi-FPO support
- Analytics dashboard
- Bank integrations

### Phase 4 (Months 7-12)
- Market price integration
- Weather alerts
- Procurement recommendations

## Why AWS?

1. **Bedrock Agents:** Advanced reasoning and tool orchestration (not just RAG)
2. **Textract Queries:** Ask natural language questions to documents
3. **SageMaker Geospatial:** Built-in satellite data access
4. **Serverless:** Pay-as-you-go, no infrastructure management
5. **India Region:** Data residency in ap-south-1 (Mumbai)
6. **Scalability:** Auto-scaling from 1 to 10,000 FPOs

## Team Requirements

- **Backend:** Python, AWS CDK, Lambda, DynamoDB
- **AI/ML:** Bedrock, Textract, SageMaker, Transcribe
- **Integration:** WhatsApp Business API, REST APIs
- **DevOps:** CI/CD, CloudWatch, X-Ray

## Questions & Answers

**Q: Why WhatsApp instead of a mobile app?**  
A: 500M+ Indians already use WhatsApp. Zero installation friction, zero learning curve.

**Q: How accurate is handwriting recognition?**  
A: Textract Queries achieves 85-95% accuracy on Hindi/Marathi scripts. Low-confidence fields are flagged for review.

**Q: What if there's no internet?**  
A: Offline tablet mode with AppSync syncs data when connectivity returns.

**Q: How do you ensure data privacy?**  
A: All data stored in India (ap-south-1), encrypted at rest (KMS), GDPR-compliant deletion.

**Q: Can this scale to other crops/regions?**  
A: Yes, the architecture is crop-agnostic and language-agnostic (add new languages via Transcribe).

## Call to Action

**For AWS Credits Application:**

1. **What's your data strategy?**
   - Sources: WhatsApp messages, ledger photos, GPS, satellite imagery
   - Storage: DynamoDB (structured), S3 (unstructured), AppSync (offline sync)
   - Processing: Lambda → Textract/Transcribe/SageMaker → Bedrock → Storage

2. **What's your 24-hour goal?**
   - Deploy WhatsApp bot that digitizes Hindi ledgers
   - Demonstrate core value: unstructured → structured data
   - Prove technical feasibility and cost-efficiency

3. **Why should AWS support this?**
   - Showcases advanced AWS services (Bedrock Agents, Textract Queries, SageMaker Geospatial)
   - Addresses UN SDG #1 (No Poverty) and #2 (Zero Hunger)
   - Potential to impact 5-10 million farmers
   - Replicable model for emerging markets globally

---

**Contact:** [Your Name]  
**Email:** [Your Email]  
**GitHub:** [Repository Link]  
**Demo:** [Video/Screenshots]
