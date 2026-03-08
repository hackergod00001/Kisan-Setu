"""
Integration test configuration for Kisan-Setu.

This module provides configuration for integration tests that use real AWS services
or LocalStack for testing.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AWSConfig:
    """AWS service configuration for integration tests."""
    
    region: str
    endpoint_url: Optional[str]
    access_key_id: Optional[str]
    secret_access_key: Optional[str]
    
    @classmethod
    def from_env(cls) -> 'AWSConfig':
        """Create configuration from environment variables."""
        # For Real AWS, don't set credentials - let boto3 use default credential chain
        use_real_aws = os.getenv('USE_REAL_AWS', 'false').lower() == 'true'
        
        if use_real_aws:
            # Use None for credentials to let boto3 use default credential chain
            return cls(
                region=os.getenv('AWS_DEFAULT_REGION', 'ap-south-1'),
                endpoint_url=os.getenv('AWS_ENDPOINT_URL'),
                access_key_id=None,
                secret_access_key=None
            )
        else:
            # For LocalStack, use test credentials
            return cls(
                region=os.getenv('AWS_DEFAULT_REGION', 'ap-south-1'),
                endpoint_url=os.getenv('AWS_ENDPOINT_URL'),
                access_key_id=os.getenv('AWS_ACCESS_KEY_ID', 'test'),
                secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY', 'test')
            )
    
    def to_boto3_config(self) -> Dict[str, Any]:
        """Convert to boto3 client configuration."""
        config = {
            'region_name': self.region
        }
        
        # Only set credentials if they are provided (not None)
        if self.access_key_id is not None:
            config['aws_access_key_id'] = self.access_key_id
        if self.secret_access_key is not None:
            config['aws_secret_access_key'] = self.secret_access_key
            
        if self.endpoint_url:
            config['endpoint_url'] = self.endpoint_url
        return config


@dataclass
class DynamoDBConfig:
    """DynamoDB configuration for integration tests."""
    
    table_name: str
    endpoint_url: Optional[str]
    
    @classmethod
    def from_env(cls) -> 'DynamoDBConfig':
        """Create configuration from environment variables."""
        return cls(
            table_name=os.getenv('DYNAMODB_TABLE_NAME', 'KisanSetuData'),
            endpoint_url=os.getenv('DYNAMODB_ENDPOINT', 'http://localhost:8000')
        )


@dataclass
class LocalStackConfig:
    """LocalStack configuration for integration tests."""
    
    endpoint_url: str
    services: list
    
    @classmethod
    def default(cls) -> 'LocalStackConfig':
        """Create default LocalStack configuration."""
        return cls(
            endpoint_url='http://localhost:4566',
            services=['dynamodb', 's3', 'lambda', 'apigateway', 'sns', 'sqs']
        )
    
    def is_available(self) -> bool:
        """Check if LocalStack is available."""
        import requests
        try:
            response = requests.get(f"{self.endpoint_url}/_localstack/health", timeout=2)
            return response.status_code == 200
        except Exception:
            return False


@dataclass
class TestEnvironment:
    """Test environment configuration."""
    
    use_localstack: bool
    use_real_aws: bool
    aws_config: AWSConfig
    dynamodb_config: DynamoDBConfig
    localstack_config: Optional[LocalStackConfig]
    
    @classmethod
    def from_env(cls) -> 'TestEnvironment':
        """Create test environment from environment variables."""
        use_localstack = os.getenv('USE_LOCALSTACK', 'true').lower() == 'true'
        use_real_aws = os.getenv('USE_REAL_AWS', 'false').lower() == 'true'
        
        localstack_config = LocalStackConfig.default() if use_localstack else None
        
        return cls(
            use_localstack=use_localstack,
            use_real_aws=use_real_aws,
            aws_config=AWSConfig.from_env(),
            dynamodb_config=DynamoDBConfig.from_env(),
            localstack_config=localstack_config
        )
    
    def get_boto3_config(self) -> Dict[str, Any]:
        """Get boto3 configuration based on environment."""
        config = self.aws_config.to_boto3_config()
        
        if self.use_localstack and self.localstack_config:
            config['endpoint_url'] = self.localstack_config.endpoint_url
        
        return config
    
    def get_dynamodb_config(self) -> Dict[str, Any]:
        """Get DynamoDB configuration based on environment."""
        config = self.aws_config.to_boto3_config()
        
        if self.use_localstack:
            config['endpoint_url'] = self.dynamodb_config.endpoint_url
        
        return config


# ============================================================================
# Integration Test Fixtures
# ============================================================================

def setup_dynamodb_table(dynamodb_client, table_name: str = 'KisanSetuData'):
    """
    Set up DynamoDB table for integration tests.
    
    Args:
        dynamodb_client: Boto3 DynamoDB client
        table_name: Name of table to create
    """
    try:
        # Check if table exists
        dynamodb_client.describe_table(TableName=table_name)
        print(f"Table {table_name} already exists")
        return
    except dynamodb_client.exceptions.ResourceNotFoundException:
        pass
    
    # Create table
    dynamodb_client.create_table(
        TableName=table_name,
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'},
            {'AttributeName': 'fpo_id', 'AttributeType': 'S'},
            {'AttributeName': 'timestamp', 'AttributeType': 'S'},
            {'AttributeName': 'sync_status', 'AttributeType': 'S'}
        ],
        KeySchema=[
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'GSI1',
                'KeySchema': [
                    {'AttributeName': 'fpo_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'SK', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            },
            {
                'IndexName': 'GSI2',
                'KeySchema': [
                    {'AttributeName': 'fpo_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            },
            {
                'IndexName': 'GSI3',
                'KeySchema': [
                    {'AttributeName': 'sync_status', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ],
        BillingMode='PAY_PER_REQUEST'
    )
    
    # Wait for table to be created
    waiter = dynamodb_client.get_waiter('table_exists')
    waiter.wait(TableName=table_name)
    print(f"Table {table_name} created successfully")


def cleanup_dynamodb_table(dynamodb_client, table_name: str = 'KisanSetuData'):
    """
    Clean up DynamoDB table after integration tests.
    
    Args:
        dynamodb_client: Boto3 DynamoDB client
        table_name: Name of table to delete
    """
    try:
        dynamodb_client.delete_table(TableName=table_name)
        print(f"Table {table_name} deleted successfully")
    except Exception as e:
        print(f"Error deleting table {table_name}: {e}")


def setup_s3_buckets(s3_client, buckets: list):
    """
    Set up S3 buckets for integration tests.
    
    Args:
        s3_client: Boto3 S3 client
        buckets: List of bucket names to create
    """
    for bucket in buckets:
        try:
            s3_client.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={'LocationConstraint': 'ap-south-1'}
            )
            print(f"Bucket {bucket} created successfully")
        except s3_client.exceptions.BucketAlreadyOwnedByYou:
            print(f"Bucket {bucket} already exists")
        except Exception as e:
            print(f"Error creating bucket {bucket}: {e}")


def cleanup_s3_buckets(s3_client, buckets: list):
    """
    Clean up S3 buckets after integration tests.
    
    Args:
        s3_client: Boto3 S3 client
        buckets: List of bucket names to delete
    """
    for bucket in buckets:
        try:
            # Delete all objects first
            response = s3_client.list_objects_v2(Bucket=bucket)
            if 'Contents' in response:
                objects = [{'Key': obj['Key']} for obj in response['Contents']]
                s3_client.delete_objects(Bucket=bucket, Delete={'Objects': objects})
            
            # Delete bucket
            s3_client.delete_bucket(Bucket=bucket)
            print(f"Bucket {bucket} deleted successfully")
        except Exception as e:
            print(f"Error deleting bucket {bucket}: {e}")


# ============================================================================
# Integration Test Helpers
# ============================================================================

def skip_if_no_aws():
    """Decorator to skip test if AWS is not available."""
    import pytest
    
    env = TestEnvironment.from_env()
    
    if not env.use_real_aws and not env.use_localstack:
        return pytest.mark.skip(reason="AWS or LocalStack not available")
    
    if env.use_localstack and env.localstack_config:
        if not env.localstack_config.is_available():
            return pytest.mark.skip(reason="LocalStack not available")
    
    return lambda func: func


def skip_if_no_localstack():
    """Decorator to skip test if LocalStack is not available."""
    import pytest
    
    env = TestEnvironment.from_env()
    
    if not env.use_localstack:
        return pytest.mark.skip(reason="LocalStack not enabled")
    
    if env.localstack_config and not env.localstack_config.is_available():
        return pytest.mark.skip(reason="LocalStack not available")
    
    return lambda func: func


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == '__main__':
    # Print current test environment configuration
    env = TestEnvironment.from_env()
    
    print("Test Environment Configuration:")
    print("="*60)
    print(f"Use LocalStack: {env.use_localstack}")
    print(f"Use Real AWS: {env.use_real_aws}")
    print(f"AWS Region: {env.aws_config.region}")
    print(f"AWS Endpoint: {env.aws_config.endpoint_url or 'Default'}")
    print(f"DynamoDB Table: {env.dynamodb_config.table_name}")
    print(f"DynamoDB Endpoint: {env.dynamodb_config.endpoint_url}")
    
    if env.localstack_config:
        print(f"\nLocalStack Configuration:")
        print(f"Endpoint: {env.localstack_config.endpoint_url}")
        print(f"Services: {', '.join(env.localstack_config.services)}")
        print(f"Available: {env.localstack_config.is_available()}")
