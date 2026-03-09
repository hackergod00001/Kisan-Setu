"""
Enhanced LLM Adapter with Bedrock Converse API, multi-model fallback, and resilience patterns.

Features:
- Circuit breaker pattern for failing models
- Exponential backoff retry logic
- Token usage tracking
- Configurable temperature and inference parameters
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class LLMAdapterError(Exception):
    """Raised when all models in the fallback chain fail."""

    def __init__(self, errors: list):
        self.errors = errors  # [{"model": "...", "error": "..."}]
        super().__init__(f"All {len(errors)} models failed: {errors}")


@dataclass
class CircuitBreaker:
    """Circuit breaker for model failure tracking."""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "closed"  # closed, open, half_open
    failure_threshold: int = 3
    timeout_seconds: int = 60

    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def record_success(self):
        """Record a success and reset the circuit."""
        self.failure_count = 0
        self.state = "closed"

    def can_attempt(self) -> bool:
        """Check if we can attempt to call this model."""
        if self.state == "closed":
            return True

        if self.state == "open":
            # Check if timeout has passed
            if self.last_failure_time and \
               (datetime.utcnow() - self.last_failure_time).seconds > self.timeout_seconds:
                self.state = "half_open"
                logger.info("Circuit breaker entering half-open state")
                return True
            return False

        # half_open state - allow one attempt
        return True


@dataclass
class ModelConfig:
    """Configuration for a model in the fallback chain."""
    model_id: str
    max_tokens: int = 1024
    temperature: float = 0.7
    top_p: float = 0.9
    retry_attempts: int = 2


class LLMAdapter:
    """
    Enhanced Bedrock Converse API adapter with:
    - Multi-model fallback
    - Circuit breaker pattern
    - Exponential backoff retry
    - Token usage tracking
    """

    # Diverse fallback chain with multiple model providers
    # Using APAC inference profile IDs for ap-south-1 region
    # Note: Claude APAC models require AWS Marketplace subscription.
    # Nova models are prioritized as they are available without Marketplace actions.
    DEFAULT_FALLBACK_CHAIN = [
        # Tier 1: AWS Nova Pro (multimodal, available without Marketplace subscription)
        ModelConfig(
            model_id="apac.amazon.nova-pro-v1:0",
            max_tokens=1024,
            temperature=0.7,
            retry_attempts=2
        ),
        # Tier 2: AWS Nova Lite (fast, cheap fallback)
        ModelConfig(
            model_id="apac.amazon.nova-lite-v1:0",
            max_tokens=1024,
            temperature=0.7,
            retry_attempts=2
        ),
        # Tier 3: Claude 3.7 Sonnet (if Marketplace subscription enabled)
        ModelConfig(
            model_id="apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
            max_tokens=1024,
            temperature=0.7,
            retry_attempts=1
        ),
        # Tier 4: Claude 3.5 Sonnet v2 (if Marketplace subscription enabled)
        ModelConfig(
            model_id="apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
            max_tokens=1024,
            temperature=0.7,
            retry_attempts=1
        ),
        # Tier 5: Claude 3 Haiku (if Marketplace subscription enabled)
        ModelConfig(
            model_id="apac.anthropic.claude-3-haiku-20240307-v1:0",
            max_tokens=1024,
            temperature=0.7,
            retry_attempts=1
        ),
    ]

    def __init__(
        self,
        bedrock_runtime=None,
        fallback_chain: Optional[List[ModelConfig]] = None
    ):
        self.bedrock_runtime = bedrock_runtime or boto3.client("bedrock-runtime")
        self.fallback_chain = fallback_chain or self.DEFAULT_FALLBACK_CHAIN

        # Circuit breakers per model
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            config.model_id: CircuitBreaker()
            for config in self.fallback_chain
        }

    def converse(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, int, int]:
        """
        Send prompt via Converse API with automatic fallback.

        Args:
            prompt: User message text
            system_prompt: Optional system prompt for model behavior
            max_tokens: Override max tokens for this request
            temperature: Override temperature for this request

        Returns:
            Tuple of (response_text, input_tokens, output_tokens)

        Raises:
            LLMAdapterError: When all models in fallback chain fail
        """
        errors = []

        for model_config in self.fallback_chain:
            model_id = model_config.model_id
            circuit_breaker = self.circuit_breakers[model_id]

            # Check circuit breaker
            if not circuit_breaker.can_attempt():
                logger.info(f"Skipping {model_id} - circuit breaker open")
                errors.append({
                    "model": model_id,
                    "error": "Circuit breaker open"
                })
                continue

            # Try this model with retries
            result = self._try_model_with_retry(
                model_config=model_config,
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

            if result["success"]:
                circuit_breaker.record_success()
                return (
                    result["response"],
                    result["input_tokens"],
                    result["output_tokens"]
                )
            else:
                circuit_breaker.record_failure()
                errors.append({
                    "model": model_id,
                    "error": result["error"]
                })

        raise LLMAdapterError(errors)

    def _try_model_with_retry(
        self,
        model_config: ModelConfig,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: Optional[int],
        temperature: Optional[float]
    ) -> Dict:
        """
        Try a model with exponential backoff retry.

        Returns:
            Dict with keys: success (bool), response (str), input_tokens (int),
            output_tokens (int), error (str)
        """
        model_id = model_config.model_id

        for attempt in range(model_config.retry_attempts + 1):
            try:
                # Build request
                kwargs = {
                    "modelId": model_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"text": prompt}],
                        }
                    ],
                    "inferenceConfig": {
                        "maxTokens": max_tokens or model_config.max_tokens,
                        "temperature": temperature or model_config.temperature,
                        "topP": model_config.top_p
                    },
                }

                if system_prompt:
                    kwargs["system"] = [{"text": system_prompt}]

                # Invoke model
                response = self.bedrock_runtime.converse(**kwargs)

                # Extract response
                response_text = response["output"]["message"]["content"][0]["text"]
                input_tokens = response.get("usage", {}).get("inputTokens", 0)
                output_tokens = response.get("usage", {}).get("outputTokens", 0)

                logger.info(
                    f"✅ {model_id} succeeded: {input_tokens} in / {output_tokens} out"
                )

                return {
                    "success": True,
                    "response": response_text,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "error": None
                }

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_msg = str(e)

                # Check if this is a retryable error
                is_retryable = error_code in [
                    "ThrottlingException",
                    "ModelTimeoutException",
                    "InternalServerException",
                    "ServiceUnavailableException"
                ]

                if is_retryable and attempt < model_config.retry_attempts:
                    # Exponential backoff: 1s, 2s, 4s
                    sleep_time = 2 ** attempt
                    logger.warning(
                        f"Retryable error for {model_id}: {error_code}. "
                        f"Retrying in {sleep_time}s (attempt {attempt + 1}/{model_config.retry_attempts})"
                    )
                    time.sleep(sleep_time)
                    continue

                # Non-retryable or max retries exceeded
                logger.warning(
                    f"Model {model_id} failed with {error_code}: {error_msg}"
                )
                return {
                    "success": False,
                    "response": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "error": error_msg
                }

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Model {model_id} failed: {error_msg}")

                # Retry on unexpected errors
                if attempt < model_config.retry_attempts:
                    sleep_time = 2 ** attempt
                    logger.warning(f"Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue

                return {
                    "success": False,
                    "response": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "error": error_msg
                }

        # Should not reach here, but just in case
        return {
            "success": False,
            "response": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": "Max retries exceeded"
        }

    def get_circuit_breaker_status(self) -> Dict[str, str]:
        """Get status of all circuit breakers for monitoring."""
        return {
            model_id: breaker.state
            for model_id, breaker in self.circuit_breakers.items()
        }

    def converse_with_image(
        self,
        prompt: str,
        image_data: bytes,
        image_format: str = "png",
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> Tuple[str, int, int]:
        """
        Send prompt with image via Converse API using multimodal models.

        Args:
            prompt: User message text about the image
            image_data: Raw image bytes
            image_format: Image format (png, jpeg, gif, webp)
            system_prompt: Optional system prompt
            max_tokens: Override max tokens
            temperature: Override temperature

        Returns:
            Tuple of (response_text, input_tokens, output_tokens)

        Raises:
            LLMAdapterError: When all multimodal models fail
        """
        errors = []

        # Multimodal-capable models (using APAC inference profiles)
        multimodal_chain = [
            ModelConfig(
                model_id="apac.anthropic.claude-3-7-sonnet-20250219-v1:0",
                max_tokens=max_tokens or 2048,
                temperature=temperature or 0.7,
                retry_attempts=2
            ),
            ModelConfig(
                model_id="apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
                max_tokens=max_tokens or 2048,
                temperature=temperature or 0.7,
                retry_attempts=2
            ),
            ModelConfig(
                model_id="apac.amazon.nova-pro-v1:0",
                max_tokens=max_tokens or 2048,
                temperature=temperature or 0.7,
                retry_attempts=2
            ),
            ModelConfig(
                model_id="apac.anthropic.claude-3-haiku-20240307-v1:0",
                max_tokens=max_tokens or 2048,
                temperature=temperature or 0.7,
                retry_attempts=2
            ),
            ModelConfig(
                model_id="apac.amazon.nova-lite-v1:0",
                max_tokens=max_tokens or 2048,
                temperature=temperature or 0.7,
                retry_attempts=2
            ),
        ]

        for model_config in multimodal_chain:
            model_id = model_config.model_id

            # Check circuit breaker (create if doesn't exist)
            if model_id not in self.circuit_breakers:
                self.circuit_breakers[model_id] = CircuitBreaker()

            circuit_breaker = self.circuit_breakers[model_id]

            if not circuit_breaker.can_attempt():
                logger.info(f"Skipping {model_id} - circuit breaker open")
                errors.append({
                    "model": model_id,
                    "error": "Circuit breaker open"
                })
                continue

            # Try with image
            result = self._try_model_with_image(
                model_config=model_config,
                prompt=prompt,
                image_data=image_data,
                image_format=image_format,
                system_prompt=system_prompt
            )

            if result["success"]:
                circuit_breaker.record_success()
                return (
                    result["response"],
                    result["input_tokens"],
                    result["output_tokens"]
                )
            else:
                circuit_breaker.record_failure()
                errors.append({
                    "model": model_id,
                    "error": result["error"]
                })

        raise LLMAdapterError(errors)

    def _try_model_with_image(
        self,
        model_config: ModelConfig,
        prompt: str,
        image_data: bytes,
        image_format: str,
        system_prompt: Optional[str]
    ) -> Dict:
        """
        Try a multimodal model with image input.

        Returns:
            Dict with keys: success, response, input_tokens, output_tokens, error
        """
        model_id = model_config.model_id

        for attempt in range(model_config.retry_attempts + 1):
            try:
                import base64

                # Encode image to base64
                image_base64 = base64.b64encode(image_data).decode('utf-8')

                # Build request with image
                kwargs = {
                    "modelId": model_id,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "image": {
                                        "format": image_format,
                                        "source": {
                                            "bytes": image_data
                                        }
                                    }
                                },
                                {
                                    "text": prompt
                                }
                            ],
                        }
                    ],
                    "inferenceConfig": {
                        "maxTokens": model_config.max_tokens,
                        "temperature": model_config.temperature,
                        "topP": model_config.top_p
                    },
                }

                if system_prompt:
                    kwargs["system"] = [{"text": system_prompt}]

                # Invoke model
                response = self.bedrock_runtime.converse(**kwargs)

                # Extract response
                response_text = response["output"]["message"]["content"][0]["text"]
                input_tokens = response.get("usage", {}).get("inputTokens", 0)
                output_tokens = response.get("usage", {}).get("outputTokens", 0)

                logger.info(
                    f"✅ {model_id} (multimodal) succeeded: {input_tokens} in / {output_tokens} out"
                )

                return {
                    "success": True,
                    "response": response_text,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "error": None
                }

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_msg = str(e)

                # Check if retryable
                is_retryable = error_code in [
                    "ThrottlingException",
                    "ModelTimeoutException",
                    "InternalServerException",
                    "ServiceUnavailableException"
                ]

                if is_retryable and attempt < model_config.retry_attempts:
                    sleep_time = 2 ** attempt
                    logger.warning(
                        f"Retryable error for {model_id}: {error_code}. "
                        f"Retrying in {sleep_time}s (attempt {attempt + 1}/{model_config.retry_attempts})"
                    )
                    time.sleep(sleep_time)
                    continue

                logger.warning(
                    f"Model {model_id} (multimodal) failed with {error_code}: {error_msg}"
                )
                return {
                    "success": False,
                    "response": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "error": error_msg
                }

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Model {model_id} (multimodal) failed: {error_msg}")

                if attempt < model_config.retry_attempts:
                    sleep_time = 2 ** attempt
                    logger.warning(f"Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue

                return {
                    "success": False,
                    "response": None,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "error": error_msg
                }

        return {
            "success": False,
            "response": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": "Max retries exceeded"
        }
