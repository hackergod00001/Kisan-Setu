"""
Kisan-Setu MVP Infrastructure Stack
CDK Stack for 24-Hour Implementation
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    custom_resources as cr,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_dynamodb as dynamodb,
    aws_appsync as appsync,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
    aws_kms as kms,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cognito as cognito,
    CfnOutput
)
from constructs import Construct
import os

STACK_DIR = os.path.dirname(os.path.abspath(__file__))

class KisanSetuMVPStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, environment: str = "dev", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        account_id = self.account
        region = self.region

        # Environment-specific resource naming
        # - prod: Uses existing resource names (no prefix) for backward compatibility
        # - dev/staging: Uses prefixed names for isolation
        env_prefix = "" if environment == "prod" else f"{environment}-"

        # DynamoDB table name with environment prefix
        table_name = f"{env_prefix}KisanSetuData"

        # Reference existing DynamoDB table (prod) or create new table (dev/staging)
        if environment == "prod":
            # Production: Reference existing table
            # IMPORTANT — DynamoDB TTL Configuration:
            # TTL must be enabled on the 'KisanSetuData' table for the 'ttl'
            # attribute. This is required for automatic cleanup of old conversation
            # items written by the Orchestrator Lambda (see orchestrator.py).
            # Because the table is imported via from_table_name (not created by
            # this stack), TTL must be enabled manually:
            #
            #   aws dynamodb update-time-to-live --table-name KisanSetuData \
            #     --time-to-live-specification "Enabled=true, AttributeName=ttl"
            table = dynamodb.Table.from_table_name(
                self, "KisanSetuTable",
                table_name=table_name
            )
        else:
            # Dev/Staging: Create new table with CDK management
            table = dynamodb.Table(
                self, "KisanSetuTable",
                table_name=table_name,
                partition_key=dynamodb.Attribute(
                    name="PK",
                    type=dynamodb.AttributeType.STRING
                ),
                sort_key=dynamodb.Attribute(
                    name="SK",
                    type=dynamodb.AttributeType.STRING
                ),
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                time_to_live_attribute="ttl",  # Automatically enabled for new tables
                point_in_time_recovery=True,
                removal_policy=RemovalPolicy.DESTROY  # Safe to delete dev/staging tables
            )

            # Add GSI for querying by farmerPhone
            table.add_global_secondary_index(
                index_name="farmerPhone-index",
                partition_key=dynamodb.Attribute(
                    name="farmerPhone",
                    type=dynamodb.AttributeType.STRING
                )
            )
        
        # Enable Point-in-Time Recovery via AwsCustomResource (prod only)
        # (Dev/staging tables have PITR enabled declaratively above)
        if environment == "prod":
            cr.AwsCustomResource(self, "EnablePITR",
                on_create=cr.AwsSdkCall(
                    service="DynamoDB",
                    action="updateContinuousBackups",
                    parameters={
                        "TableName": table_name,
                        "PointInTimeRecoverySpecification": {
                            "PointInTimeRecoveryEnabled": True
                        }
                    },
                    physical_resource_id=cr.PhysicalResourceId.of(f"{table_name}-PITR"),
                ),
                policy=cr.AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:UpdateContinuousBackups", "dynamodb:DescribeContinuousBackups"],
                        resources=[f"arn:aws:dynamodb:{region}:{account_id}:table/{table_name}"]
                    )
                ])
            )

        # S3 bucket names with environment prefix
        raw_bucket_name = f"kisan-setu-{env_prefix}raw-{account_id}"
        processed_bucket_name = f"kisan-setu-{env_prefix}processed-{account_id}"
        archive_bucket_name = f"kisan-setu-{env_prefix}archive-{account_id}"

        # Reference existing S3 buckets (prod) or create new ones (dev/staging)
        if environment == "prod":
            raw_bucket = s3.Bucket.from_bucket_name(
                self, "RawBucket",
                bucket_name=raw_bucket_name
            )

            processed_bucket = s3.Bucket.from_bucket_name(
                self, "ProcessedBucket",
                bucket_name=processed_bucket_name
            )

            archive_bucket = s3.Bucket.from_bucket_name(
                self, "ArchiveBucket",
                bucket_name=archive_bucket_name
            )
        else:
            # Dev/Staging: Create new S3 buckets
            raw_bucket = s3.Bucket(
                self, "RawBucket",
                bucket_name=raw_bucket_name,
                encryption=s3.BucketEncryption.S3_MANAGED,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True  # Safe to delete dev/staging data
            )

            processed_bucket = s3.Bucket(
                self, "ProcessedBucket",
                bucket_name=processed_bucket_name,
                encryption=s3.BucketEncryption.S3_MANAGED,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True
            )

            archive_bucket = s3.Bucket(
                self, "ArchiveBucket",
                bucket_name=archive_bucket_name,
                encryption=s3.BucketEncryption.S3_MANAGED,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True
            )
        
        # SNS Topic for Critical Error Alerts
        alert_topic = sns.Topic(
            self, "CriticalAlertTopic",
            topic_name=f"kisan-setu-{env_prefix}critical-alerts",
            display_name=f"Kisan-Setu Critical Error Alerts ({environment})"
        )
        
        # SNS email subscription via CDK context parameter
        # Usage: cdk deploy -c alert_email=ops@example.com
        alert_email = self.node.try_get_context('alert_email')
        if alert_email:
            alert_topic.add_subscription(
                sns_subscriptions.EmailSubscription(alert_email)
            )
        
        # KMS Key for encrypting sensitive DynamoDB fields
        encryption_key = kms.Key(
            self, "SensitiveDataEncryptionKey",
            alias=f"kisan-setu/{env_prefix}sensitive-data",
            description=f"KMS key for encrypting sensitive DynamoDB fields ({environment})",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY if environment != "prod" else RemovalPolicy.RETAIN
        )

        # --- Common policy statement builders ---
        dynamodb_table_arn = f"arn:aws:dynamodb:{region}:{account_id}:table/{table_name}"
        dynamodb_index_arn = f"arn:aws:dynamodb:{region}:{account_id}:table/{table_name}/index/*"

        s3_bucket_arns = [
            raw_bucket.bucket_arn,
            processed_bucket.bucket_arn,
            archive_bucket.bucket_arn,
            f"{raw_bucket.bucket_arn}/*",
            f"{processed_bucket.bucket_arn}/*",
            f"{archive_bucket.bucket_arn}/*",
        ]

        s3_read_only_arns = [
            raw_bucket.bucket_arn,
            f"{raw_bucket.bucket_arn}/*",
        ]

        dynamodb_rw_policy = iam.PolicyStatement(
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:BatchGetItem",
                "dynamodb:BatchWriteItem",
            ],
            resources=[dynamodb_table_arn, dynamodb_index_arn],
        )

        sns_policy = iam.PolicyStatement(
            actions=["sns:Publish"],
            resources=[alert_topic.topic_arn],
        )

        kms_policy = iam.PolicyStatement(
            actions=["kms:GenerateDataKey", "kms:Decrypt", "kms:DescribeKey"],
            resources=[encryption_key.key_arn],
        )

        secrets_policy = iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
            resources=[f"arn:aws:secretsmanager:{region}:{account_id}:secret:kisan-setu/{env_prefix}*"],
        )

        lambda_invoke_policy = iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            resources=[f"arn:aws:lambda:{region}:{account_id}:function:*"],
        )

        s3_rw_policy = iam.PolicyStatement(
            actions=[
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
            ],
            resources=s3_bucket_arns,
        )

        s3_read_policy = iam.PolicyStatement(
            actions=["s3:GetObject", "s3:ListBucket"],
            resources=s3_read_only_arns,
        )

        # --- Per-function IAM roles ---

        # Router: DynamoDB R/W, S3 R/W, Lambda:Invoke, SecretsManager, SNS, KMS
        router_role = self._create_lambda_role("Router", [
            dynamodb_rw_policy, s3_rw_policy, lambda_invoke_policy,
            secrets_policy, sns_policy, kms_policy,
        ])

        # Orchestrator: DynamoDB R/W, S3 R, Lambda:Invoke, Bedrock Invoke/Converse, SecretsManager, SNS, KMS
        orchestrator_role = self._create_lambda_role("Orchestrator", [
            dynamodb_rw_policy, s3_read_policy, lambda_invoke_policy,
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:Converse"],
                resources=["*"],
            ),
            secrets_policy, sns_policy, kms_policy,
        ])

        # DocumentProcessor: DynamoDB R/W, S3 R/W, Textract, SecretsManager, SNS, KMS
        processor_role = self._create_lambda_role("DocumentProcessor", [
            dynamodb_rw_policy, s3_rw_policy,
            iam.PolicyStatement(
                actions=["textract:AnalyzeDocument", "textract:DetectDocumentText", "textract:StartDocumentAnalysis", "textract:GetDocumentAnalysis"],
                resources=["*"],
            ),
            secrets_policy, sns_policy, kms_policy,
        ])

        # VoiceHandler: DynamoDB R/W, S3 R/W, Lambda:Invoke, Transcribe, Polly, SecretsManager, SNS, KMS
        voice_role = self._create_lambda_role("VoiceHandler", [
            dynamodb_rw_policy, s3_rw_policy, lambda_invoke_policy,
            iam.PolicyStatement(
                actions=["transcribe:StartTranscriptionJob", "transcribe:GetTranscriptionJob"],
                resources=["*"],
            ),
            iam.PolicyStatement(
                actions=["polly:SynthesizeSpeech"],
                resources=["*"],
            ),
            secrets_policy, sns_policy, kms_policy,
        ])

        # CreditCalculator: DynamoDB R/W, SNS, KMS
        credit_role = self._create_lambda_role("CreditCalculator", [
            dynamodb_rw_policy, sns_policy, kms_policy,
        ])

        # SatelliteAnalyzer: DynamoDB R/W, S3 R/W, SageMaker Geospatial, SNS, KMS
        satellite_role = self._create_lambda_role("SatelliteAnalyzer", [
            dynamodb_rw_policy, s3_rw_policy,
            iam.PolicyStatement(
                actions=["sagemaker-geospatial:*", "sagemaker:InvokeEndpoint", "sagemaker:DescribeEndpoint"],
                resources=["*"],
            ),
            sns_policy, kms_policy,
        ])

        # KnowledgeBase: DynamoDB R/W, Bedrock Retrieve/Invoke, OpenSearch Serverless, SNS, KMS
        knowledge_role = self._create_lambda_role("KnowledgeBase", [
            dynamodb_rw_policy,
            iam.PolicyStatement(
                actions=["bedrock:Retrieve", "bedrock:RetrieveAndGenerate", "bedrock:InvokeModel"],
                resources=["*"],
            ),
            iam.PolicyStatement(
                actions=["aoss:APIAccessAll"],
                resources=["*"],
            ),
            sns_policy, kms_policy,
        ])

        # SyncHandler: DynamoDB R/W, SNS, KMS
        sync_role = self._create_lambda_role("SyncHandler", [
            dynamodb_rw_policy, sns_policy, kms_policy,
        ])

        # Common Library Lambda Layer (shared code for all Lambda functions)
        # Built with correct Python path structure: python/lib/python3.11/site-packages/common/
        common_layer = lambda_.LayerVersion(
            self, "CommonLibraryLayer",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "lambda/.layer-build")),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11, lambda_.Runtime.PYTHON_3_12],
            description=f"Shared common library for Kisan-Setu ({environment}): DynamoDBAccess, models, validation",
            layer_version_name=f"{env_prefix}kisan-setu-common"
        )

        # Geospatial Lambda Layer (rasterio, pyproj, numpy for real NDVI)
        geospatial_layer = lambda_.LayerVersion(
            self, "GeospatialLayer",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "layers/geospatial")),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="rasterio + pyproj + numpy for Sentinel-2 NDVI computation",
        )

        # Document Processor Lambda (create first so we can reference it)
        processor_lambda = lambda_.Function(
            self, "DocumentProcessor",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="processor.handler",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "lambda/processor")),
            role=processor_role,
            timeout=Duration.seconds(60),
            memory_size=1024,
            layers=[common_layer],
            environment={
                "DYNAMODB_TABLE": table_name,
                "S3_BUCKET_RAW": raw_bucket_name,
                "S3_BUCKET_PROCESSED": processed_bucket_name,
                "S3_BUCKET_ARCHIVE": archive_bucket_name,
                "REGION": region,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn,
                "WHATSAPP_SECRET_NAME": f"kisan-setu/{env_prefix}whatsapp/credentials",
                "KMS_KEY_ID": encryption_key.key_id
            }
        )

        # Voice Handler Lambda
        voice_lambda = lambda_.Function(
            self, "VoiceHandler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="voice.handler",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "lambda/voice")),
            role=voice_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            layers=[common_layer],
            environment={
                "DYNAMODB_TABLE": table_name,
                "S3_BUCKET_RAW": raw_bucket_name,
                "S3_BUCKET_PROCESSED": processed_bucket_name,
                "S3_BUCKET_ARCHIVE": archive_bucket_name,
                "REGION": region,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn,
                "WHATSAPP_SECRET_NAME": f"kisan-setu/{env_prefix}whatsapp/credentials",
                "KMS_KEY_ID": encryption_key.key_id
            }
        )

        # Credit Calculator Lambda
        credit_lambda = lambda_.Function(
            self, "CreditCalculator",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="credit.handler",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "lambda/credit")),
            role=credit_role,
            timeout=Duration.seconds(30),
            memory_size=512,
            layers=[common_layer],
            environment={
                "DYNAMODB_TABLE": table_name,
                "REGION": region,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn,
                "KMS_KEY_ID": encryption_key.key_id
            }
        )

        # Satellite Analyzer Lambda
        satellite_lambda = lambda_.Function(
            self, "SatelliteAnalyzer",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="satellite_analyzer.handler",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "lambda/satellite")),
            role=satellite_role,
            timeout=Duration.seconds(120),
            memory_size=2048,
            layers=[common_layer, geospatial_layer],
            environment={
                "DYNAMODB_TABLE": table_name,
                "S3_BUCKET_RAW": raw_bucket_name,
                "S3_BUCKET_PROCESSED": processed_bucket_name,
                "REGION": region,
                "SAGEMAKER_REGION": "us-west-2",
                "SENTINEL2_ARN": "arn:aws:sagemaker-geospatial:us-west-2:378778860802:raster-data-collection/public/nmqj48dcu3g7ayw8",
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn,
                "KMS_KEY_ID": encryption_key.key_id
            }
        )
        
        # Knowledge Base Lambda
        knowledge_lambda = lambda_.Function(
            self, "KnowledgeBase",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="knowledge_base.handler",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "lambda/knowledge")),
            role=knowledge_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            layers=[common_layer],
            environment={
                "REGION": region,
                "KNOWLEDGE_BASE_ID": "",  # REQUIRED: Set after running setup_knowledge_base.py — Lambda will fail-fast without this
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn,
                "KMS_KEY_ID": encryption_key.key_id,
                "DYNAMODB_TABLE": table_name
            }
        )
        
        # Bedrock Orchestrator Lambda — explicit function_name to break circular dependency with VoiceHandler
        orchestrator_function_name = f"{env_prefix}KisanSetu-BedrockOrchestrator"
        orchestrator_lambda = lambda_.Function(
            self, "BedrockOrchestrator",
            function_name=orchestrator_function_name,
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="orchestrator.handler",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "lambda/orchestrator")),
            role=orchestrator_role,
            timeout=Duration.seconds(180),
            memory_size=1024,
            layers=[common_layer],
            environment={
                "DYNAMODB_TABLE": table_name,
                "S3_BUCKET_RAW": raw_bucket_name,
                "REGION": region,
                "DOCUMENT_PROCESSOR_FUNCTION": processor_lambda.function_name,
                "VOICE_AGENT_FUNCTION": voice_lambda.function_name,
                "SATELLITE_ANALYZER_FUNCTION": satellite_lambda.function_name,
                "CREDIT_CALCULATOR_FUNCTION": credit_lambda.function_name,
                "KNOWLEDGE_BASE_FUNCTION": knowledge_lambda.function_name,
                "KNOWLEDGE_BASE_ID": "",  # REQUIRED: Set after running setup_knowledge_base.py
                "WHATSAPP_SECRET_NAME": f"kisan-setu/{env_prefix}whatsapp/credentials",
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn,
                "KMS_KEY_ID": encryption_key.key_id
            }
        )

        # Add BEDROCK_ORCHESTRATOR_FUNCTION to VoiceHandler using string to avoid circular dependency
        voice_lambda.add_environment(
            "BEDROCK_ORCHESTRATOR_FUNCTION", orchestrator_function_name
        )

        # Message Router Lambda
        router_lambda = lambda_.Function(
            self, "MessageRouter",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="router.handler",
            code=lambda_.Code.from_asset(os.path.join(STACK_DIR, "lambda/router")),
            role=router_role,
            timeout=Duration.seconds(30),
            memory_size=512,
            layers=[common_layer],
            environment={
                "DYNAMODB_TABLE": table_name,
                "S3_BUCKET_RAW": raw_bucket_name,
                "S3_BUCKET_PROCESSED": processed_bucket_name,
                "S3_BUCKET_ARCHIVE": archive_bucket_name,
                "REGION": region,
                "WHATSAPP_SECRET_NAME": f"kisan-setu/{env_prefix}whatsapp/credentials",
                "WEBHOOK_VERIFY_TOKEN": "kisan-setu-verify-2026",
                "PROCESSOR_FUNCTION_NAME": processor_lambda.function_name,
                "VOICE_AGENT_FUNCTION": voice_lambda.function_name,
                "CREDIT_CALCULATOR_FUNCTION": credit_lambda.function_name,
                "SATELLITE_ANALYZER_FUNCTION": satellite_lambda.function_name,
                "BEDROCK_ORCHESTRATOR_FUNCTION": orchestrator_lambda.function_name,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn,
                "KMS_KEY_ID": encryption_key.key_id
            }
        )

        # Provisioned concurrency for Router and Orchestrator (disabled for dev to avoid deployment issues)
        router_version = router_lambda.current_version
        router_alias = lambda_.Alias(self, "RouterAlias",
            alias_name="live",
            version=router_version,
            provisioned_concurrent_executions=2 if environment == "prod" else 0,
        )

        orchestrator_version = orchestrator_lambda.current_version
        orchestrator_alias = lambda_.Alias(self, "OrchestratorAlias",
            alias_name="live",
            version=orchestrator_version,
            provisioned_concurrent_executions=2 if environment == "prod" else 0,
        )

        # API Gateway
        api = apigw.RestApi(
            self, "KisanSetuAPI",
            rest_api_name=f"Kisan-Setu WhatsApp Webhook ({environment})",
            description="Webhook for WhatsApp Business API",
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200
            )
        )
        
        # /webhook endpoint for WhatsApp
        webhook = api.root.add_resource("webhook")
        webhook.add_method(
            "POST",
            apigw.LambdaIntegration(router_alias)
        )
        # GET method for webhook verification (Meta WhatsApp)
        webhook.add_method(
            "GET",
            apigw.LambdaIntegration(router_alias)
        )
        
        # /process endpoint for document processing
        process = api.root.add_resource("process")
        process.add_method(
            "POST",
            apigw.LambdaIntegration(processor_lambda),
            api_key_required=True
        )
        
        # /credit endpoint for credit score calculation
        credit = api.root.add_resource("credit")
        credit.add_method(
            "POST",
            apigw.LambdaIntegration(credit_lambda),
            api_key_required=True
        )
        
        # /knowledge endpoint for knowledge base queries
        knowledge = api.root.add_resource("knowledge")
        knowledge.add_method(
            "POST",
            apigw.LambdaIntegration(knowledge_lambda),
            api_key_required=True
        )

        # API Key for authenticated endpoints (/process, /credit, /knowledge)
        api_key = api.add_api_key(
            "KisanSetuApiKey",
            api_key_name=f"kisan-setu-{env_prefix}api-key",
            description="API key for Kisan-Setu authenticated endpoints"
        )

        # Usage plan to associate the API key with the API stage
        usage_plan = api.add_usage_plan(
            "KisanSetuUsagePlan",
            name=f"kisan-setu-{env_prefix}usage-plan",
            description="Usage plan for Kisan-Setu API",
            throttle=apigw.ThrottleSettings(
                rate_limit=100,
                burst_limit=200
            )
        )
        usage_plan.add_api_stage(stage=api.deployment_stage)
        usage_plan.add_api_key(api_key)

        # Cognito User Pool for AppSync authentication
        user_pool = cognito.UserPool(
            self, "KisanSetuUserPool",
            user_pool_name=f"kisan-setu-{env_prefix}user-pool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            removal_policy=RemovalPolicy.DESTROY
        )

        # Cognito User Pool Client for AppSync
        user_pool_client = user_pool.add_client(
            "KisanSetuUserPoolClient",
            user_pool_client_name=f"kisan-setu-{env_prefix}appsync-client",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True
            )
        )

        # AppSync GraphQL API for offline sync
        graphql_api = appsync.GraphqlApi(
            self, "KisanSetuGraphQLAPI",
            name=f"kisan-setu-{env_prefix}sync-api",
            definition=appsync.Definition.from_file(
                os.path.join(os.path.dirname(__file__), "schema.graphql")
            ),
            authorization_config=appsync.AuthorizationConfig(
                default_authorization=appsync.AuthorizationMode(
                    authorization_type=appsync.AuthorizationType.USER_POOL,
                    user_pool_config=appsync.UserPoolConfig(
                        user_pool=user_pool
                    )
                )
            ),
            xray_enabled=True
        )
        
        # DynamoDB data source for AppSync
        dynamodb_ds = appsync.DynamoDbDataSource(
            self, "KisanSetuDataSource",
            api=graphql_api,
            table=table,
            name="KisanSetuDataSource"
        )
        
        # Resolver for getFarmer query
        dynamodb_ds.create_resolver(
            "GetFarmerResolver",
            type_name="Query",
            field_name="getFarmer",
            request_mapping_template=appsync.MappingTemplate.from_string("""
{
  "version": "2017-02-28",
  "operation": "GetItem",
  "key": {
    "PK": $util.dynamodb.toDynamoDBJson("FARMER#$ctx.args.farmerId"),
    "SK": $util.dynamodb.toDynamoDBJson("METADATA")
  }
}
            """),
            response_mapping_template=appsync.MappingTemplate.from_string("""
#if($ctx.result)
  {
    "farmerId": "$ctx.result.farmerId",
    "name": "$ctx.result.name",
    "phone": "$ctx.result.phone",
    "fpoId": "$ctx.result.fpoId",
    "gpsCoords": $util.toJson($ctx.result.gpsCoords),
    "preferredLanguage": "$ctx.result.preferredLanguage",
    "joinDate": "$ctx.result.joinDate"
  }
#else
  null
#end
            """)
        )
        
        # Resolver for listTransactions query
        dynamodb_ds.create_resolver(
            "ListTransactionsResolver",
            type_name="Query",
            field_name="listTransactions",
            request_mapping_template=appsync.MappingTemplate.from_string("""
{
  "version": "2017-02-28",
  "operation": "Query",
  "query": {
    "expression": "PK = :pk AND begins_with(SK, :sk)",
    "expressionValues": {
      ":pk": $util.dynamodb.toDynamoDBJson("FARMER#$ctx.args.farmerId"),
      ":sk": $util.dynamodb.toDynamoDBJson("TXN#")
    }
  },
  "limit": $util.defaultIfNull($ctx.args.limit, 20),
  "scanIndexForward": false,
  #if($ctx.args.nextToken)
    "nextToken": "$ctx.args.nextToken"
  #end
}
            """),
            response_mapping_template=appsync.MappingTemplate.from_string("""
{
  "items": $util.toJson($ctx.result.items),
  "nextToken": $util.toJson($ctx.result.nextToken)
}
            """)
        )
        
        # Resolver for getCreditScore query
        dynamodb_ds.create_resolver(
            "GetCreditScoreResolver",
            type_name="Query",
            field_name="getCreditScore",
            request_mapping_template=appsync.MappingTemplate.from_string("""
{
  "version": "2017-02-28",
  "operation": "Query",
  "query": {
    "expression": "PK = :pk AND begins_with(SK, :sk)",
    "expressionValues": {
      ":pk": $util.dynamodb.toDynamoDBJson("FARMER#$ctx.args.farmerId"),
      ":sk": $util.dynamodb.toDynamoDBJson("SCORE#")
    }
  },
  "limit": 1,
  "scanIndexForward": false
}
            """),
            response_mapping_template=appsync.MappingTemplate.from_string("""
#if($ctx.result.items.size() > 0)
  $util.toJson($ctx.result.items[0])
#else
  null
#end
            """)
        )
        
        # Resolver for listFarmers query
        dynamodb_ds.create_resolver(
            "ListFarmersResolver",
            type_name="Query",
            field_name="listFarmers",
            request_mapping_template=appsync.MappingTemplate.from_string("""
{
  "version": "2017-02-28",
  "operation": "Query",
  "index": "GSI1",
  "query": {
    "expression": "fpoId = :fpoId",
    "expressionValues": {
      ":fpoId": $util.dynamodb.toDynamoDBJson($ctx.args.fpoId)
    }
  },
  "limit": $util.defaultIfNull($ctx.args.limit, 20),
  #if($ctx.args.nextToken)
    "nextToken": "$ctx.args.nextToken"
  #end
}
            """),
            response_mapping_template=appsync.MappingTemplate.from_string("""
{
  "items": $util.toJson($ctx.result.items),
  "nextToken": $util.toJson($ctx.result.nextToken)
}
            """)
        )
        
        # Resolver for createTransaction mutation
        dynamodb_ds.create_resolver(
            "CreateTransactionResolver",
            type_name="Mutation",
            field_name="createTransaction",
            request_mapping_template=appsync.MappingTemplate.from_string("""
{
  "version": "2017-02-28",
  "operation": "PutItem",
  "key": {
    "PK": $util.dynamodb.toDynamoDBJson("FARMER#$ctx.args.input.farmerId"),
    "SK": $util.dynamodb.toDynamoDBJson("TXN#$ctx.args.input.timestamp")
  },
  "attributeValues": {
    "transactionId": $util.dynamodb.toDynamoDBJson($ctx.args.input.transactionId),
    "farmerId": $util.dynamodb.toDynamoDBJson($ctx.args.input.farmerId),
    "fpoId": $util.dynamodb.toDynamoDBJson($ctx.args.input.fpoId),
    "quantity": $util.dynamodb.toDynamoDBJson($ctx.args.input.quantity),
    "cropType": $util.dynamodb.toDynamoDBJson($ctx.args.input.cropType),
    "qualityGrade": $util.dynamodb.toDynamoDBJson($ctx.args.input.qualityGrade),
    "moisture": $util.dynamodb.toDynamoDBJson($ctx.args.input.moisture),
    "price": $util.dynamodb.toDynamoDBJson($ctx.args.input.price),
    "timestamp": $util.dynamodb.toDynamoDBJson($ctx.args.input.timestamp),
    "syncStatus": $util.dynamodb.toDynamoDBJson($ctx.args.input.syncStatus),
    "version": $util.dynamodb.toDynamoDBJson($ctx.args.input.version),
    #if($ctx.args.input.ledgerImageUrl)
      "ledgerImageUrl": $util.dynamodb.toDynamoDBJson($ctx.args.input.ledgerImageUrl),
    #end
    "lastModified": $util.dynamodb.toDynamoDBJson($util.time.nowISO8601())
  },
  "condition": {
    "expression": "attribute_not_exists(PK) OR version < :newVersion",
    "expressionValues": {
      ":newVersion": $util.dynamodb.toDynamoDBJson($ctx.args.input.version)
    }
  }
}
            """),
            response_mapping_template=appsync.MappingTemplate.from_string("""
$util.toJson($ctx.result)
            """)
        )
        
        # Lambda data source for syncOfflineTransactions
        sync_lambda = lambda_.Function(
            self, "SyncHandler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="sync_handler.handler",
            code=lambda_.Code.from_asset(
                "lambda/sync",
                exclude=["__pycache__"]
            ),
            role=sync_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            layers=[common_layer],
            environment={
                "DYNAMODB_TABLE": table_name,
                "REGION": region,
                "KMS_KEY_ID": encryption_key.key_id,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn
            }
        )
        
        lambda_ds = appsync.LambdaDataSource(
            self, "SyncLambdaDataSource",
            api=graphql_api,
            lambda_function=sync_lambda,
            name="SyncLambdaDataSource"
        )
        
        # Resolver for syncOfflineTransactions mutation
        lambda_ds.create_resolver(
            "SyncOfflineTransactionsResolver",
            type_name="Mutation",
            field_name="syncOfflineTransactions"
        )
        
        # Resolver for updateTransaction mutation
        dynamodb_ds.create_resolver(
            "UpdateTransactionResolver",
            type_name="Mutation",
            field_name="updateTransaction",
            request_mapping_template=appsync.MappingTemplate.from_string("""
{
  "version": "2017-02-28",
  "operation": "UpdateItem",
  "key": {
    "PK": $util.dynamodb.toDynamoDBJson("FARMER#$ctx.args.input.farmerId"),
    "SK": $util.dynamodb.toDynamoDBJson("TXN#$ctx.args.input.timestamp")
  },
  "update": {
    "expression": "SET quantity = :quantity, cropType = :cropType, qualityGrade = :qualityGrade, moisture = :moisture, price = :price, syncStatus = :syncStatus, version = :version, lastModified = :lastModified",
    "expressionValues": {
      ":quantity": $util.dynamodb.toDynamoDBJson($ctx.args.input.quantity),
      ":cropType": $util.dynamodb.toDynamoDBJson($ctx.args.input.cropType),
      ":qualityGrade": $util.dynamodb.toDynamoDBJson($ctx.args.input.qualityGrade),
      ":moisture": $util.dynamodb.toDynamoDBJson($ctx.args.input.moisture),
      ":price": $util.dynamodb.toDynamoDBJson($ctx.args.input.price),
      ":syncStatus": $util.dynamodb.toDynamoDBJson($ctx.args.input.syncStatus),
      ":version": $util.dynamodb.toDynamoDBJson($ctx.args.input.version),
      ":lastModified": $util.dynamodb.toDynamoDBJson($util.time.nowISO8601()),
      ":expectedVersion": $util.dynamodb.toDynamoDBJson($ctx.args.input.version - 1)
    }
  },
  "condition": {
    "expression": "version = :expectedVersion",
    "expressionValues": {
      ":expectedVersion": $util.dynamodb.toDynamoDBJson($ctx.args.input.version - 1)
    }
  }
}
            """),
            response_mapping_template=appsync.MappingTemplate.from_string("""
$util.toJson($ctx.result)
            """)
        )
        
        # ── CloudWatch Alarms ──────────────────────────────────────────
        # 8 Lambda functions × 2 alarms (Errors + Throttles) + 2 API Gateway alarms = 18 total
        lambda_functions = {
            "Router": router_lambda,
            "Orchestrator": orchestrator_lambda,
            "DocumentProcessor": processor_lambda,
            "VoiceHandler": voice_lambda,
            "CreditCalculator": credit_lambda,
            "SatelliteAnalyzer": satellite_lambda,
            "KnowledgeBase": knowledge_lambda,
            "SyncHandler": sync_lambda,
        }

        for name, fn in lambda_functions.items():
            cloudwatch.Alarm(self, f"{name}ErrorAlarm",
                metric=fn.metric_errors(period=Duration.minutes(5)),
                threshold=0,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                evaluation_periods=1,
                alarm_name=f"kisan-setu-{env_prefix}{name}-errors",
            ).add_alarm_action(cw_actions.SnsAction(alert_topic))

            cloudwatch.Alarm(self, f"{name}ThrottleAlarm",
                metric=fn.metric_throttles(period=Duration.minutes(5)),
                threshold=0,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
                evaluation_periods=1,
                alarm_name=f"kisan-setu-{env_prefix}{name}-throttles",
            ).add_alarm_action(cw_actions.SnsAction(alert_topic))

        # API Gateway 5xx alarm
        cloudwatch.Alarm(self, "ApiGateway5xxAlarm",
            metric=api.metric_server_error(period=Duration.minutes(5)),
            threshold=0,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            alarm_name=f"kisan-setu-{env_prefix}api-5xx",
        ).add_alarm_action(cw_actions.SnsAction(alert_topic))

        # API Gateway p99 latency alarm
        cloudwatch.Alarm(self, "ApiGatewayLatencyAlarm",
            metric=api.metric_latency(period=Duration.minutes(5), statistic="p99"),
            threshold=10000,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            alarm_name=f"kisan-setu-{env_prefix}api-latency-p99",
        ).add_alarm_action(cw_actions.SnsAction(alert_topic))

        # Dashboard S3 bucket (private, served via CloudFront)
        dashboard_bucket = s3.Bucket(
            self, "DashboardBucket",
            bucket_name=f"kisan-setu-{env_prefix}dashboard-{account_id}" if environment != "prod" else f"kisan-setu-dashboard-{account_id}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # CloudFront Origin Access Identity for dashboard bucket
        dashboard_oai = cloudfront.OriginAccessIdentity(
            self, "DashboardOAI",
            comment="OAI for Kisan-Setu dashboard bucket"
        )
        dashboard_bucket.grant_read(dashboard_oai)

        # CloudFront distribution for dashboard
        dashboard_distribution = cloudfront.Distribution(
            self, "DashboardDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3Origin(
                    dashboard_bucket,
                    origin_access_identity=dashboard_oai
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS
            ),
            default_root_object="index.html"
        )

        # Upload dashboard files
        s3_deployment.BucketDeployment(
            self, "DashboardDeployment",
            sources=[s3_deployment.Source.asset("dashboard")],
            destination_bucket=dashboard_bucket,
            distribution=dashboard_distribution,
            distribution_paths=["/*"]
        )

        # Dashboard URL output (now via CloudFront)
        CfnOutput(
            self, "DashboardURL",
            value=f"https://{dashboard_distribution.distribution_domain_name}",
            description="Dashboard website URL (CloudFront)"
        )

        # Outputs
        CfnOutput(
            self, "APIGatewayURL",
            value=api.url,
            description="API Gateway endpoint URL"
        )
        
        CfnOutput(
            self, "WebhookURL",
            value=f"{api.url}webhook",
            description="WhatsApp webhook URL"
        )

        CfnOutput(
            self, "APIKeyId",
            value=api_key.key_id,
            description="API Key ID for authenticated endpoints"
        )
        
        CfnOutput(
            self, "MessageRouterFunction",
            value=router_lambda.function_name,
            description="Message Router Lambda function name"
        )
        
        CfnOutput(
            self, "DocumentProcessorFunction",
            value=processor_lambda.function_name,
            description="Document Processor Lambda function name"
        )
        
        CfnOutput(
            self, "BedrockOrchestratorFunction",
            value=orchestrator_lambda.function_name,
            description="Bedrock Orchestrator Lambda function name"
        )
        
        CfnOutput(
            self, "KnowledgeBaseFunction",
            value=knowledge_lambda.function_name,
            description="Knowledge Base Lambda function name"
        )
        
        CfnOutput(
            self, "GraphQLAPIURL",
            value=graphql_api.graphql_url,
            description="AppSync GraphQL API URL"
        )
        
        CfnOutput(
            self, "GraphQLAPIKey",
            value="N/A (Cognito User Pools auth)",
            description="AppSync auth switched to Cognito User Pools"
        )
        
        CfnOutput(
            self, "GraphQLAPIID",
            value=graphql_api.api_id,
            description="AppSync API ID"
        )

        CfnOutput(
            self, "CognitoUserPoolId",
            value=user_pool.user_pool_id,
            description="Cognito User Pool ID for AppSync auth"
        )

        CfnOutput(
            self, "CognitoUserPoolClientId",
            value=user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID for AppSync auth"
        )

        # Outputs
        # Generate unique export name per environment
        # prod: KisanSetuAlertTopicArn, dev: KisanSetuDevAlertTopicArn, staging: KisanSetuStagingAlertTopicArn
        env_suffix = environment.capitalize() if environment != "prod" else ""
        CfnOutput(
            self, "SNSAlertTopicArn",
            value=alert_topic.topic_arn,
            description=f"SNS Topic ARN for critical error alerts ({environment})",
            export_name=f"KisanSetu{env_suffix}AlertTopicArn"
        )

    def _create_lambda_role(self, name, extra_policies=None):
        """Create a Lambda execution role with basic execution policy plus extra policy statements."""
        role = iam.Role(
            self, f"{name}Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )
        for policy in (extra_policies or []):
            role.add_to_policy(policy)
        return role
