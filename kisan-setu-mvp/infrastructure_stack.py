"""
Kisan-Setu MVP Infrastructure Stack
CDK Stack for 24-Hour Implementation
"""

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_dynamodb as dynamodb,
    aws_appsync as appsync,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
    CfnOutput
)
from constructs import Construct
import os

class KisanSetuMVPStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        account_id = self.account
        region = self.region
        
        # Reference existing DynamoDB table
        table = dynamodb.Table.from_table_name(
            self, "KisanSetuTable",
            table_name="KisanSetuData"
        )
        
        # Reference existing S3 buckets
        raw_bucket = s3.Bucket.from_bucket_name(
            self, "RawBucket",
            bucket_name=f"kisan-setu-raw-{account_id}"
        )
        
        processed_bucket = s3.Bucket.from_bucket_name(
            self, "ProcessedBucket",
            bucket_name=f"kisan-setu-processed-{account_id}"
        )
        
        archive_bucket = s3.Bucket.from_bucket_name(
            self, "ArchiveBucket",
            bucket_name=f"kisan-setu-archive-{account_id}"
        )
        
        # SNS Topic for Critical Error Alerts
        alert_topic = sns.Topic(
            self, "CriticalAlertTopic",
            topic_name="kisan-setu-critical-alerts",
            display_name="Kisan-Setu Critical Error Alerts"
        )
        
        # Add email subscription (replace with actual admin email)
        # alert_topic.add_subscription(
        #     sns_subscriptions.EmailSubscription("admin@example.com")
        # )
        
        # IAM role for Lambda functions
        lambda_role = iam.Role(
            self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonTextractFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonDynamoDBFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonS3FullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonTranscribeFullAccess"
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "AmazonPollyFullAccess"
                )
            ]
        )
        
        # Add Bedrock permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeAgent",
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate",
                    "bedrock:Converse"
                ],
                resources=["*"]
            )
        )
        
        # Add OpenSearch Serverless permissions for Knowledge Base
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "aoss:APIAccessAll"
                ],
                resources=["*"]
            )
        )
        
        # Add SageMaker Geospatial permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sagemaker-geospatial:*",
                    "sagemaker:InvokeEndpoint",
                    "sagemaker:DescribeEndpoint"
                ],
                resources=["*"]
            )
        )
        
        # Add Lambda invoke permissions (for router to call other Lambdas)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=["lambda:InvokeFunction"],
                resources=[f"arn:aws:lambda:{region}:{account_id}:function:*"]
            )
        )
        
        # Add Secrets Manager permissions (for WhatsApp credentials)
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret"
                ],
                resources=[f"arn:aws:secretsmanager:{region}:{account_id}:secret:kisan-setu/*"]
            )
        )
        
        # Add SNS permissions for critical alerts
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sns:Publish"
                ],
                resources=[alert_topic.topic_arn]
            )
        )
        
        # Document Processor Lambda (create first so we can reference it)
        processor_lambda = lambda_.Function(
            self, "DocumentProcessor",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="processor.handler",
            code=lambda_.Code.from_asset("lambda/processor"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "S3_BUCKET_RAW": f"kisan-setu-raw-{account_id}",
                "S3_BUCKET_PROCESSED": f"kisan-setu-processed-{account_id}",
                "S3_BUCKET_ARCHIVE": f"kisan-setu-archive-{account_id}",
                "REGION": region,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn
            }
        )
        
        # Voice Handler Lambda
        voice_lambda = lambda_.Function(
            self, "VoiceHandler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="voice.handler",
            code=lambda_.Code.from_asset("lambda/voice"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "S3_BUCKET_RAW": f"kisan-setu-raw-{account_id}",
                "S3_BUCKET_PROCESSED": f"kisan-setu-processed-{account_id}",
                "S3_BUCKET_ARCHIVE": f"kisan-setu-archive-{account_id}",
                "REGION": region,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn
            }
        )
        
        # Credit Calculator Lambda
        credit_lambda = lambda_.Function(
            self, "CreditCalculator",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="credit.handler",
            code=lambda_.Code.from_asset("lambda/credit"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "REGION": region
            }
        )
        
        # Satellite Analyzer Lambda
        satellite_lambda = lambda_.Function(
            self, "SatelliteAnalyzer",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="satellite_analyzer.handler",
            code=lambda_.Code.from_asset("lambda/satellite"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "S3_BUCKET_RAW": f"kisan-setu-raw-{account_id}",
                "REGION": region,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn
            }
        )
        
        # Knowledge Base Lambda
        knowledge_lambda = lambda_.Function(
            self, "KnowledgeBase",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="knowledge_base.handler",
            code=lambda_.Code.from_asset("lambda/knowledge"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "REGION": region,
                "KNOWLEDGE_BASE_ID": ""  # Will be set after running setup_knowledge_base.py
            }
        )
        
        # Bedrock Orchestrator Lambda
        orchestrator_lambda = lambda_.Function(
            self, "BedrockOrchestrator",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="orchestrator.handler",
            code=lambda_.Code.from_asset("lambda/orchestrator"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=1024,
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "S3_BUCKET_RAW": f"kisan-setu-raw-{account_id}",
                "REGION": region,
                "BEDROCK_AGENT_ID": "UUQPVM0ULJ",
                "BEDROCK_AGENT_ALIAS_ID": "A2TGFPMFXZ",
                "DOCUMENT_PROCESSOR_FUNCTION": processor_lambda.function_name,
                "VOICE_AGENT_FUNCTION": voice_lambda.function_name,
                "SATELLITE_ANALYZER_FUNCTION": satellite_lambda.function_name,
                "CREDIT_CALCULATOR_FUNCTION": credit_lambda.function_name,
                "KNOWLEDGE_BASE_FUNCTION": knowledge_lambda.function_name,
                "KNOWLEDGE_BASE_ID": ""  # Will be set after running setup_knowledge_base.py
            }
        )
        
        # Message Router Lambda
        router_lambda = lambda_.Function(
            self, "MessageRouter",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="router.handler",
            code=lambda_.Code.from_asset("lambda/router"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "S3_BUCKET_RAW": f"kisan-setu-raw-{account_id}",
                "S3_BUCKET_PROCESSED": f"kisan-setu-processed-{account_id}",
                "S3_BUCKET_ARCHIVE": f"kisan-setu-archive-{account_id}",
                "REGION": region,
                "WHATSAPP_SECRET_NAME": "kisan-setu/whatsapp/credentials",
                "WEBHOOK_VERIFY_TOKEN": "kisan-setu-verify-2026",
                "PROCESSOR_FUNCTION_NAME": processor_lambda.function_name,
                "VOICE_AGENT_FUNCTION": voice_lambda.function_name,
                "BEDROCK_ORCHESTRATOR_FUNCTION": orchestrator_lambda.function_name,
                "CREDIT_CALCULATOR_FUNCTION": credit_lambda.function_name,
                "SATELLITE_ANALYZER_FUNCTION": satellite_lambda.function_name,
                "SNS_ALERT_TOPIC_ARN": alert_topic.topic_arn
            }
        )
        
        # API Gateway
        api = apigw.RestApi(
            self, "KisanSetuAPI",
            rest_api_name="Kisan-Setu WhatsApp Webhook",
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
            apigw.LambdaIntegration(router_lambda)
        )
        # GET method for webhook verification (Meta WhatsApp)
        webhook.add_method(
            "GET",
            apigw.LambdaIntegration(router_lambda)
        )
        
        # /process endpoint for document processing
        process = api.root.add_resource("process")
        process.add_method(
            "POST",
            apigw.LambdaIntegration(processor_lambda)
        )
        
        # /credit endpoint for credit score calculation
        credit = api.root.add_resource("credit")
        credit.add_method(
            "POST",
            apigw.LambdaIntegration(credit_lambda)
        )
        
        # /knowledge endpoint for knowledge base queries
        knowledge = api.root.add_resource("knowledge")
        knowledge.add_method(
            "POST",
            apigw.LambdaIntegration(knowledge_lambda)
        )
        
        # AppSync GraphQL API for offline sync
        graphql_api = appsync.GraphqlApi(
            self, "KisanSetuGraphQLAPI",
            name="kisan-setu-sync-api",
            definition=appsync.Definition.from_file(
                os.path.join(os.path.dirname(__file__), "schema.graphql")
            ),
            authorization_config=appsync.AuthorizationConfig(
                default_authorization=appsync.AuthorizationMode(
                    authorization_type=appsync.AuthorizationType.API_KEY
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
            code=lambda_.Code.from_asset("lambda/sync"),
            role=lambda_role,
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "DYNAMODB_TABLE": "KisanSetuData",
                "REGION": region
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

        # Dashboard URL output
        CfnOutput(
            self, "DashboardURL",
            value=dashboard_bucket.bucket_website_url,
            description="Dashboard website URL"
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
            value=graphql_api.api_key or "N/A",
            description="AppSync API Key"
        )
        
        CfnOutput(
            self, "GraphQLAPIID",
            value=graphql_api.api_id,
            description="AppSync API ID"
        )

        # Outputs
        CfnOutput(
            self, "SNSAlertTopicArn",
            value=alert_topic.topic_arn,
            description="SNS Topic ARN for critical error alerts",
            export_name="KisanSetuAlertTopicArn"
        )
