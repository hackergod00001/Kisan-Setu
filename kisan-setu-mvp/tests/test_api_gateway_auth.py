"""
Tests for Task 1.3: API Gateway authentication on /process, /credit, /knowledge endpoints.
Validates: Requirements 2.3 (bugfix.md) — unauthenticated requests to these endpoints should be rejected.
Preservation: /webhook endpoint must remain unauthenticated (Req 3.3).

Note: CDK synth-based assertions are not possible due to a pre-existing dependency cycle
(VoiceHandler <-> BedrockOrchestrator from Task 1.1). These tests validate the source code
directly via AST inspection to confirm the CDK constructs are correctly defined.
"""

import ast
import os
import pytest


INFRA_STACK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "infrastructure_stack.py"
)


@pytest.fixture(scope="module")
def source_code():
    """Read the infrastructure stack source code."""
    with open(INFRA_STACK_PATH, "r") as f:
        return f.read()


@pytest.fixture(scope="module")
def tree(source_code):
    """Parse the infrastructure stack into an AST."""
    return ast.parse(source_code)


def _find_add_method_calls(tree):
    """Find all .add_method() calls and extract their keyword arguments."""
    results = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "add_method"
        ):
            call = node.value
            # First positional arg is the HTTP method
            http_method = None
            if call.args and isinstance(call.args[0], ast.Constant):
                http_method = call.args[0].value

            # Check for api_key_required keyword
            api_key_required = None
            for kw in call.keywords:
                if kw.arg == "api_key_required":
                    if isinstance(kw.value, ast.Constant):
                        api_key_required = kw.value.value

            # Try to get the variable name (e.g., webhook, process, credit, knowledge)
            var_name = None
            if isinstance(node.value.func.value, ast.Attribute):
                # e.g., self.something.add_method
                pass
            elif isinstance(node.value.func.value, ast.Name):
                var_name = node.value.func.value.id

            results.append({
                "var_name": var_name,
                "http_method": http_method,
                "api_key_required": api_key_required,
            })
    return results


class TestApiGatewayAuth:
    """Verify API Gateway authentication is configured correctly in source code."""

    def test_process_endpoint_requires_api_key(self, tree):
        """The /process POST method should have api_key_required=True."""
        methods = _find_add_method_calls(tree)
        process_posts = [
            m for m in methods
            if m["var_name"] == "process" and m["http_method"] == "POST"
        ]
        assert len(process_posts) == 1, "Expected exactly one POST on 'process'"
        assert process_posts[0]["api_key_required"] is True, \
            "/process POST should have api_key_required=True"

    def test_credit_endpoint_requires_api_key(self, tree):
        """The /credit POST method should have api_key_required=True."""
        methods = _find_add_method_calls(tree)
        credit_posts = [
            m for m in methods
            if m["var_name"] == "credit" and m["http_method"] == "POST"
        ]
        assert len(credit_posts) == 1, "Expected exactly one POST on 'credit'"
        assert credit_posts[0]["api_key_required"] is True, \
            "/credit POST should have api_key_required=True"

    def test_knowledge_endpoint_requires_api_key(self, tree):
        """The /knowledge POST method should have api_key_required=True."""
        methods = _find_add_method_calls(tree)
        knowledge_posts = [
            m for m in methods
            if m["var_name"] == "knowledge" and m["http_method"] == "POST"
        ]
        assert len(knowledge_posts) == 1, "Expected exactly one POST on 'knowledge'"
        assert knowledge_posts[0]["api_key_required"] is True, \
            "/knowledge POST should have api_key_required=True"

    def test_webhook_post_does_not_require_api_key(self, tree):
        """The /webhook POST method should NOT have api_key_required=True."""
        methods = _find_add_method_calls(tree)
        webhook_posts = [
            m for m in methods
            if m["var_name"] == "webhook" and m["http_method"] == "POST"
        ]
        assert len(webhook_posts) == 1, "Expected exactly one POST on 'webhook'"
        assert webhook_posts[0]["api_key_required"] is not True, \
            "/webhook POST should NOT have api_key_required=True"

    def test_webhook_get_does_not_require_api_key(self, tree):
        """The /webhook GET method should NOT have api_key_required=True."""
        methods = _find_add_method_calls(tree)
        webhook_gets = [
            m for m in methods
            if m["var_name"] == "webhook" and m["http_method"] == "GET"
        ]
        assert len(webhook_gets) == 1, "Expected exactly one GET on 'webhook'"
        assert webhook_gets[0]["api_key_required"] is not True, \
            "/webhook GET should NOT have api_key_required=True"

    def test_exactly_three_endpoints_require_api_key(self, tree):
        """Exactly 3 add_method calls should have api_key_required=True."""
        methods = _find_add_method_calls(tree)
        api_key_methods = [m for m in methods if m["api_key_required"] is True]
        assert len(api_key_methods) == 3, \
            f"Expected 3 methods with api_key_required=True, found {len(api_key_methods)}"


class TestApiKeyAndUsagePlan:
    """Verify API key and usage plan constructs exist in source code."""

    def test_api_key_created(self, source_code):
        """An API key should be created via api.add_api_key()."""
        assert "add_api_key" in source_code, \
            "Expected api.add_api_key() call in infrastructure_stack.py"

    def test_usage_plan_created(self, source_code):
        """A usage plan should be created via api.add_usage_plan()."""
        assert "add_usage_plan" in source_code, \
            "Expected api.add_usage_plan() call in infrastructure_stack.py"

    def test_usage_plan_associated_with_api_stage(self, source_code):
        """The usage plan should be associated with the API deployment stage."""
        assert "add_api_stage" in source_code, \
            "Expected usage_plan.add_api_stage() call in infrastructure_stack.py"

    def test_api_key_associated_with_usage_plan(self, source_code):
        """The API key should be associated with the usage plan."""
        assert "usage_plan.add_api_key" in source_code, \
            "Expected usage_plan.add_api_key() call in infrastructure_stack.py"

    def test_api_key_output_exists(self, source_code):
        """The stack should output the API Key ID."""
        assert "APIKeyId" in source_code, \
            "Expected CfnOutput for APIKeyId in infrastructure_stack.py"
