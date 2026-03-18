"""
Tests for Task 2.3: Switch AppSync from API Key to Cognito User Pools auth.
Validates: Requirement 2.7 (bugfix.md) — AppSync SHALL use Cognito User Pools authorization.
Preservation: AppSync syncOfflineTransactions must continue working (Req 3.7).

Uses AST inspection of infrastructure_stack.py (same approach as test_api_gateway_auth.py)
due to CDK synth dependency cycle.
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


class TestCognitoUserPoolCreated:
    """Verify Cognito User Pool and Client are created in CDK stack."""

    def test_cognito_import_present(self, source_code):
        """aws_cognito should be imported."""
        assert "aws_cognito as cognito" in source_code, \
            "Expected 'aws_cognito as cognito' import in infrastructure_stack.py"

    def test_user_pool_created(self, source_code):
        """A Cognito UserPool should be created."""
        assert "cognito.UserPool(" in source_code, \
            "Expected cognito.UserPool() call in infrastructure_stack.py"

    def test_user_pool_client_created(self, source_code):
        """A Cognito UserPool Client should be created."""
        assert "add_client(" in source_code, \
            "Expected user_pool.add_client() call in infrastructure_stack.py"

    def test_user_pool_id_output_exists(self, source_code):
        """The stack should output the Cognito User Pool ID."""
        assert "CognitoUserPoolId" in source_code, \
            "Expected CfnOutput for CognitoUserPoolId in infrastructure_stack.py"

    def test_user_pool_client_id_output_exists(self, source_code):
        """The stack should output the Cognito User Pool Client ID."""
        assert "CognitoUserPoolClientId" in source_code, \
            "Expected CfnOutput for CognitoUserPoolClientId in infrastructure_stack.py"


class TestAppSyncCognitoAuth:
    """Verify AppSync uses Cognito User Pools instead of API Key."""

    def test_appsync_uses_user_pool_auth_type(self, source_code):
        """AppSync authorization_type should be USER_POOL, not API_KEY."""
        assert "AuthorizationType.USER_POOL" in source_code, \
            "Expected AuthorizationType.USER_POOL in AppSync authorization_config"

    def test_appsync_does_not_use_api_key_auth(self, source_code):
        """AppSync should NOT use API_KEY authorization."""
        assert "AuthorizationType.API_KEY" not in source_code, \
            "AppSync should not use AuthorizationType.API_KEY anymore"

    def test_user_pool_config_present(self, source_code):
        """AppSync should have a user_pool_config referencing the Cognito User Pool."""
        assert "user_pool_config=appsync.UserPoolConfig(" in source_code, \
            "Expected UserPoolConfig in AppSync authorization_config"

    def test_graphql_api_key_output_updated(self, source_code):
        """The GraphQLAPIKey output should reflect Cognito auth (no longer a real API key)."""
        # The old output referenced graphql_api.api_key; it should no longer do so
        assert 'graphql_api.api_key' not in source_code, \
            "GraphQLAPIKey output should not reference graphql_api.api_key after switching to Cognito"
