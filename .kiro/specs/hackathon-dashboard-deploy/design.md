# Design Document: Hackathon Dashboard Deploy

## Overview

This design covers the remaining hackathon deliverables for Kisan-Setu: deploying the existing static dashboard to S3 via CDK, adding a Bedrock Converse API adapter with multi-model fallback, integrating it into the orchestrator, adding IAM permissions, implementing mock satellite NDVI data, and preparing hackathon submission artifacts.

The primary focus is the S3 static website deployment (Requirement 1), which provides the MVP link for hackathon evaluation. The existing dashboard in `kisan-setu-mvp/dashboard/` (index.html + app.js) already renders all panels — this design adds the infrastructure to serve it publicly.

The LLM adapter (Requirement 2) replaces the current `invoke_model` calls in the orchestrator with the Bedrock Converse API, providing a unified interface and automatic multi-model fallback. The orchestrator already has a tiered model routing system; the adapter formalizes the API layer.

## Architecture

```mermaid
graph TB
    subgraph "CDK Stack (infrastructure_stack.py)"
        S3B[S3 Dashboard Bucket<br/>Static Website Hosting]
        DEPLOY[s3_deployment.BucketDeployment<br/>Upload dashboard/ files]
        IAM[Lambda Execution Role<br/>+ bedrock:Converse]
    end

    subgraph "Lambda Functions"
        ORCH[Orchestrator Lambda]
        ADAPTER[LLM Adapter Module<br/>lambda/common/llm_adapter.py]
        SAT[Satellite Analyzer Lambda]
        MOCK[Satellite Mock Module<br/>lambda/satellite/satellite_mock.py]
    end

    subgraph "AWS Services"
        BEDROCK[Bedrock Converse API]
        DYNAMO[DynamoDB]
    end

    subgraph "Dashboard"
        HTML[index.html + app.js]
    end

    DEPLOY -->|uploads| S3B
    S3B -->|serves| HTML
    ORCH --> ADAPTER
    ADAPTER -->|converse()| BEDROCK
    ADAPTER -->|fallback chain| BEDROCK
    SAT --> MOCK
    MOCK -->|cache lookup| DYNAMO
    IAM -->|grants| ORCH
```

The architecture adds four components to the existing stack:

1. **S3 Dashboard Bucket** — New S3 bucket with static website hosting, public read policy, and CDK `BucketDeployment` to upload `dashboard/` contents. Outputs the URL as a CloudFormation output.
2. **LLM Adapter** — New shared module in `lambda/common/llm_adapter.py` wrapping Bedrock Converse API with ordered fallback (Claude Sonnet → Claude Haiku → Amazon Titan).
3. **Satellite Mock** — New module in `lambda/satellite/satellite_mock.py` providing deterministic NDVI data for demo coordinates, with 24-hour caching via coordinate hashing.
4. **IAM Update** — Adds `bedrock:Converse` action to the existing Lambda execution role policy.

## Components and Interfaces

### 1. S3 Dashboard Deployment (CDK)

**Location:** `kisan-setu-mvp/infrastructure_stack.py`

New CDK constructs added to `KisanSetuMVPStack.__init__`:

```python
from aws_cdk import aws_s3_deployment as s3_deployment, RemovalPolicy

# Dashboard S3 bucket with static website hosting
dashboard_bucket = s3.Bucket(
    self, "DashboardBucket",
    bucket_name=f"kisan-setu-dashboard-{account_id}",
    website_index_document="index.html",
    public_read_access=True,
    block_public_access=s3.BlockPublicAccess(
        block_public_acls=False,
        block_public_policy=False,
        ignore_public_acls=False,
        restrict_public_buckets=False
    ),
    removal_policy=RemovalPolicy.DESTROY,
    auto_delete_objects=True
)

# Upload dashboard files
s3_deployment.BucketDeployment(
    self, "DashboardDeployment",
    sources=[s3_deployment.Source.asset("dashboard")],
    destination_bucket=dashboard_bucket
)

# Output the dashboard URL
CfnOutput(
    self, "DashboardURL",
    value=dashboard_bucket.bucket_website_url,
    description="Dashboard website URL"
)
```

Key decisions:
- `RemovalPolicy.DESTROY` + `auto_delete_objects=True` — hackathon project, easy cleanup
- `public_read_access=True` with all `BlockPublicAccess` flags disabled — required for S3 static website hosting
- `BucketDeployment` handles idempotent uploads — re-deploying updates files without creating duplicate buckets (satisfies Req 1.6)
- Output name `DashboardURL` matches Requirement 1.4

### 2. LLM Adapter with Converse API

**Location:** `kisan-setu-mvp/lambda/common/llm_adapter.py`

```python
class LLMAdapter:
    """Unified Bedrock Converse API adapter with multi-model fallback."""

    FALLBACK_CHAIN = [
        "anthropic.claude-3-sonnet-20240229-v1:0",   # Primary
        "anthropic.claude-3-haiku-20240307-v1:0",     # Fallback 1
        "amazon.titan-text-express-v1"                 # Fallback 2
    ]

    def converse(
        self,
        prompt: str,
        system_prompt: str | None = None
    ) -> str:
        """
        Send prompt via Converse API with automatic fallback.

        Args:
            prompt: User message text
            system_prompt: Optional system prompt for model behavior

        Returns:
            Response text from the first successful model

        Raises:
            LLMAdapterError: When all models in fallback chain fail,
                             includes per-model error details
        """
```

Interface contract:
- `converse(prompt, system_prompt=None) -> str` — single entry point
- Formats requests using Converse API message structure (`role` + `content` fields)
- Iterates through `FALLBACK_CHAIN` on error/throttle
- Extracts text from Converse API response `output.message.content[0].text`
- Raises `LLMAdapterError` with all model errors when chain exhausted

### 3. Orchestrator Integration

**Location:** `kisan-setu-mvp/lambda/orchestrator/orchestrator.py`

Changes to `BedrockOrchestrator`:
- Replace `bedrock_runtime.invoke_model()` calls with `LLMAdapter.converse()`
- Pass `SYSTEM_PROMPT` as the `system_prompt` parameter
- Catch `LLMAdapterError` and return localized user-friendly error messages
- The existing `ModelRouter` tier logic can optionally be preserved by passing the selected model ID to the adapter, or simplified to use the adapter's built-in fallback chain

### 4. Satellite Mock Module

**Location:** `kisan-setu-mvp/lambda/satellite/satellite_mock.py`

```python
class SatelliteMock:
    """Mock NDVI data generator for hackathon demo."""

    MAHARASHTRA_BOUNDS = {
        "lat_min": 15.6, "lat_max": 22.1,
        "lon_min": 72.6, "lon_max": 80.9
    }

    def get_ndvi_data(
        self,
        latitude: float,
        longitude: float
    ) -> dict | None:
        """
        Generate deterministic mock NDVI data for given coordinates.

        Args:
            latitude: GPS latitude
            longitude: GPS longitude

        Returns:
            Dict with ndvi_value, crop_type, maturity_stage,
            health_status, estimated_yield — or None if outside
            supported region.
        """
```

Interface contract:
- Returns `None` for coordinates outside Maharashtra bounds (Req 5.4)
- NDVI values range 0.3–0.9, derived deterministically from coordinate hash (Req 5.1)
- Includes crop_type, maturity_stage, health_status, estimated_yield (Req 5.2)
- Same coordinates within 24 hours return identical values via hash-based seed + date component (Req 5.3)

### 5. IAM Permission Update

**Location:** `kisan-setu-mvp/infrastructure_stack.py`

Add `bedrock:Converse` to the existing Bedrock policy statement:

```python
lambda_role.add_to_policy(
    iam.PolicyStatement(
        actions=[
            "bedrock:InvokeModel",
            "bedrock:InvokeAgent",
            "bedrock:Retrieve",
            "bedrock:RetrieveAndGenerate",
            "bedrock:Converse"  # NEW
        ],
        resources=["*"]
    )
)
```

Uses the same `resources=["*"]` pattern as existing Bedrock permissions (Req 4.2).

### 6. Hackathon Submission Artifacts

**README.md** at repository root — structured with: project title/tagline, problem statement, architecture diagram (Mermaid), setup/deployment instructions, "5 Killer Features" section, live dashboard URL, demo video link, cost analysis ($50/month for 500+ farmers).

**Presentation outline** — 15 slides: problem → solution → architecture → 5 feature demos → impact/cost → future roadmap.

**Demo video script** — 5-minute walkthrough covering text query, image ledger, voice interaction, credit scoring, satellite NDVI via WhatsApp interactions.

## Data Models

### Dashboard Bucket Configuration

| Property | Value |
|---|---|
| Bucket Name | `kisan-setu-dashboard-{account_id}` |
| Website Index | `index.html` |
| Public Access | Enabled (all BlockPublicAccess flags false) |
| Removal Policy | DESTROY (hackathon lifecycle) |
| Contents | `dashboard/index.html`, `dashboard/app.js` |

### LLM Adapter Request (Converse API Format)

```json
{
  "modelId": "anthropic.claude-3-sonnet-20240229-v1:0",
  "messages": [
    {
      "role": "user",
      "content": [{ "text": "<prompt>" }]
    }
  ],
  "system": [{ "text": "<system_prompt>" }],
  "inferenceConfig": {
    "maxTokens": 1024
  }
}
```

### LLM Adapter Response (Converse API Format)

```json
{
  "output": {
    "message": {
      "role": "assistant",
      "content": [{ "text": "<response>" }]
    }
  },
  "usage": {
    "inputTokens": 150,
    "outputTokens": 300
  },
  "stopReason": "end_turn"
}
```

### LLMAdapterError

```python
class LLMAdapterError(Exception):
    """Raised when all models in fallback chain fail."""
    def __init__(self, errors: list[dict]):
        self.errors = errors  # [{"model": "...", "error": "..."}]
        super().__init__(f"All {len(errors)} models failed: {errors}")
```

### Satellite Mock Response

```json
{
  "ndvi_value": 0.72,
  "crop_type": "Onion",
  "maturity_stage": "mid",
  "health_status": "Healthy",
  "estimated_yield": "4500 kg/hectare",
  "coordinates": { "latitude": 19.75, "longitude": 75.71 },
  "generated_at": "2025-07-15T10:00:00Z",
  "data_source": "mock"
}
```

### CloudFormation Output

| Output Name | Value | Description |
|---|---|---|
| DashboardURL | `http://kisan-setu-dashboard-{id}.s3-website.ap-south-1.amazonaws.com` | Public dashboard URL |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Converse API request formatting

*For any* prompt string and optional system prompt, the LLM adapter SHALL produce a Converse API request containing a `messages` array with a `role: "user"` entry and `content` text matching the prompt, and SHALL include the `system` field if and only if a system prompt is provided.

**Validates: Requirements 2.4, 2.6**

### Property 2: Fallback on model failure

*For any* subset of models in the fallback chain that fail (but not all), the LLM adapter SHALL skip failed models and return the response from the first successful model in chain order.

**Validates: Requirements 2.2**

### Property 3: Exhausted fallback chain raises descriptive error

*For any* set of errors where all models in the fallback chain fail, the LLM adapter SHALL raise an `LLMAdapterError` whose `errors` list has exactly the same length as the fallback chain, with each entry containing the model ID and error message.

**Validates: Requirements 2.3**

### Property 4: Response text extraction

*For any* valid Converse API response containing `output.message.content[0].text`, the LLM adapter SHALL return exactly that text string, unmodified.

**Validates: Requirements 2.5**

### Property 5: Localized error response on adapter failure

*For any* supported language code (hi-IN, mr-IN, ta-IN, en), when the LLM adapter raises an exception, the orchestrator SHALL return a non-empty error message string in that language.

**Validates: Requirements 3.3**

### Property 6: Mock NDVI completeness and range for Maharashtra coordinates

*For any* GPS coordinates within Maharashtra bounds (lat 15.6–22.1, lon 72.6–80.9), the satellite mock SHALL return a response with `ndvi_value` in [0.3, 0.9] and all required fields present: `crop_type`, `maturity_stage`, `health_status`, and `estimated_yield`.

**Validates: Requirements 5.1, 5.2**

### Property 7: Mock NDVI consistency within 24 hours

*For any* GPS coordinates, calling the satellite mock twice with the same date SHALL return identical `ndvi_value`, `crop_type`, `maturity_stage`, `health_status`, and `estimated_yield`.

**Validates: Requirements 5.3**

### Property 8: Out-of-bounds coordinates return no data

*For any* GPS coordinates outside Maharashtra bounds (lat < 15.6 or lat > 22.1 or lon < 72.6 or lon > 80.9), the satellite mock SHALL return `None`.

**Validates: Requirements 5.4**

## Error Handling

### LLM Adapter Errors

| Error Scenario | Handling |
|---|---|
| Single model throttled/error | Retry with next model in fallback chain (Sonnet → Haiku → Titan) |
| All models fail | Raise `LLMAdapterError` with per-model error details |
| Network timeout | Treat as model failure, trigger fallback |
| Invalid response format | Treat as model failure, trigger fallback |

### Orchestrator Error Handling

| Error Scenario | Handling |
|---|---|
| `LLMAdapterError` raised | Return localized error message based on farmer's `language` field |
| Unknown language code | Default to English error message |

### Satellite Mock Error Handling

| Error Scenario | Handling |
|---|---|
| Coordinates outside Maharashtra | Return `None` (caller handles gracefully) |
| Invalid coordinate types | Raise `ValueError` |

### CDK Deployment Errors

| Error Scenario | Handling |
|---|---|
| Bucket name conflict | CDK uses account-specific naming (`kisan-setu-dashboard-{account_id}`) to avoid conflicts |
| Dashboard files missing | CDK `Source.asset("dashboard")` fails at synth time with clear error |

## Testing Strategy

### Property-Based Testing

**Library:** Hypothesis (already used in the project — see `tests/generators.py`)

**Configuration:** Minimum 100 iterations per property test (matches existing `kisan_setu` profile in `tests/generators.py`).

Each property test MUST be tagged with a comment referencing the design property:
```python
# Feature: hackathon-dashboard-deploy, Property 1: Converse API request formatting
```

Each correctness property above maps to exactly one property-based test:

| Property | Test File | What It Generates |
|---|---|---|
| Property 1 | `test_llm_adapter_properties.py` | Random prompt strings + optional system prompts |
| Property 2 | `test_llm_adapter_properties.py` | Random failure patterns across model chain |
| Property 3 | `test_llm_adapter_properties.py` | All-fail error combinations |
| Property 4 | `test_llm_adapter_properties.py` | Random Converse API response payloads |
| Property 5 | `test_orchestrator_error_properties.py` | Random language codes from supported set |
| Property 6 | `test_satellite_mock_properties.py` | Random Maharashtra GPS coordinates |
| Property 7 | `test_satellite_mock_properties.py` | Random GPS coordinates called twice |
| Property 8 | `test_satellite_mock_properties.py` | Random out-of-bounds GPS coordinates |

### Unit / Example Tests

Unit tests complement property tests for specific examples and CDK template verification:

| Test | What It Verifies |
|---|---|
| CDK template has S3 bucket with WebsiteConfiguration | Req 1.1 |
| CDK template has public read bucket policy | Req 1.2 |
| CDK template has BucketDeployment from dashboard/ | Req 1.3 |
| CDK template has DashboardURL output | Req 1.4 |
| CDK template has bedrock:Converse in IAM policy | Req 4.1, 4.2 |
| Orchestrator calls LLMAdapter.converse() | Req 3.1 |
| Orchestrator passes system prompt to adapter | Req 3.2 |
| LLM adapter calls bedrock_runtime.converse() | Req 2.1 |

### E2E Tests (Manual / CI)

Requirements 8.1–8.6 are verified via manual E2E testing against the deployed stack. These are not automated property tests but are documented in the test checklist for hackathon submission verification.
