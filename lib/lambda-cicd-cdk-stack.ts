import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as sns from 'aws-cdk-lib/aws-sns';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { Construct } from 'constructs';
import { NagSuppressions } from 'cdk-nag';

export interface LambdaCicdCdkStackProps extends cdk.StackProps {
  environment?: string;
  logLevel?: string;
}

export class LambdaCicdCdkStack extends cdk.Stack {
  public readonly userManagementApi: apigateway.RestApi;
  public readonly dataProcessorApi: apigateway.RestApi;
  public readonly notificationApi: apigateway.RestApi;
  public readonly healthCheckApi: apigateway.RestApi;

  constructor(scope: Construct, id: string, props?: LambdaCicdCdkStackProps) {
    super(scope, id, props);

    // Environment configuration
    const environment = props?.environment || 'dev';
    const logLevel = props?.logLevel || 'INFO';

    // DynamoDB Tables
    const userTable = new dynamodb.Table(this, 'UserTable', {
      tableName: `${environment}-users`,
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
    });

    const processedDataTable = new dynamodb.Table(this, 'ProcessedDataTable', {
      tableName: `${environment}-processed-data`,
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
    });

    const notificationTable = new dynamodb.Table(this, 'NotificationTable', {
      tableName: `${environment}-notifications`,
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
    });

    // S3 Bucket for data processing
    const dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: `${environment}-data-bucket-${this.account}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
    });

    // SNS Topic for notifications
    const notificationTopic = new sns.Topic(this, 'NotificationTopic', {
      topicName: `${environment}-notifications`,
    });

    // Common Lambda Layer
    const commonLayer = new lambda.LayerVersion(this, 'CommonLayer', {
      code: lambda.Code.fromAsset('src/layers/common'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_9],
      description: 'Common utilities for Lambda functions',
    });

    // Lambda Functions
    const userManagementFunction = new PythonFunction(this, 'UserManagementFunction', {
      entry: 'src/user_management',
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'lambda_handler',
      layers: [commonLayer],
      environment: {
        ENVIRONMENT: environment,
        LOG_LEVEL: logLevel,
        USER_TABLE_NAME: userTable.tableName,
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    const dataProcessorFunction = new PythonFunction(this, 'DataProcessorFunction', {
      entry: 'src/data_processor',
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'lambda_handler',
      layers: [commonLayer],
      environment: {
        ENVIRONMENT: environment,
        LOG_LEVEL: logLevel,
        PROCESSED_DATA_TABLE_NAME: processedDataTable.tableName,
        DATA_BUCKET_NAME: dataBucket.bucketName,
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    const notificationFunction = new PythonFunction(this, 'NotificationFunction', {
      entry: 'src/notification',
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'lambda_handler',
      layers: [commonLayer],
      environment: {
        ENVIRONMENT: environment,
        LOG_LEVEL: logLevel,
        NOTIFICATION_TABLE_NAME: notificationTable.tableName,
        SNS_TOPIC_ARN: notificationTopic.topicArn,
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    const healthCheckFunction = new PythonFunction(this, 'HealthCheckFunction', {
      entry: 'src/health_check',
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'lambda_handler',
      environment: {
        ENVIRONMENT: environment,
        LOG_LEVEL: logLevel,
      },
      tracing: lambda.Tracing.ACTIVE,
    });

    // Grant permissions
    userTable.grantReadWriteData(userManagementFunction);
    processedDataTable.grantReadWriteData(dataProcessorFunction);
    notificationTable.grantReadWriteData(notificationFunction);
    dataBucket.grantReadWrite(dataProcessorFunction);
    notificationTopic.grantPublish(notificationFunction);

    // API Gateways
    this.userManagementApi = new apigateway.RestApi(this, 'UserManagementApi', {
      restApiName: `${environment}-user-management-api`,
      description: 'User Management Service API',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
    });

    this.dataProcessorApi = new apigateway.RestApi(this, 'DataProcessorApi', {
      restApiName: `${environment}-data-processor-api`,
      description: 'Data Processing Service API',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
    });

    this.notificationApi = new apigateway.RestApi(this, 'NotificationApi', {
      restApiName: `${environment}-notification-api`,
      description: 'Notification Service API',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
    });

    this.healthCheckApi = new apigateway.RestApi(this, 'HealthCheckApi', {
      restApiName: `${environment}-health-check-api`,
      description: 'Health Check Service API',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
    });

    // API Gateway Integrations
    const userManagementIntegration = new apigateway.LambdaIntegration(userManagementFunction);
    const dataProcessorIntegration = new apigateway.LambdaIntegration(dataProcessorFunction);
    const notificationIntegration = new apigateway.LambdaIntegration(notificationFunction);
    const healthCheckIntegration = new apigateway.LambdaIntegration(healthCheckFunction);

    // User Management API Routes
    const usersResource = this.userManagementApi.root.addResource('users');
    usersResource.addMethod('GET', userManagementIntegration);
    usersResource.addMethod('POST', userManagementIntegration);
    const userResource = usersResource.addResource('{id}');
    userResource.addMethod('GET', userManagementIntegration);

    // Data Processor API Routes
    const processResource = this.dataProcessorApi.root.addResource('process');
    processResource.addMethod('POST', dataProcessorIntegration);

    // Notification API Routes
    const notifyResource = this.notificationApi.root.addResource('notify');
    notifyResource.addMethod('POST', notificationIntegration);

    // Health Check API Routes
    const healthResource = this.healthCheckApi.root.addResource('health');
    healthResource.addMethod('GET', healthCheckIntegration);

    // Stack outputs
    new cdk.CfnOutput(this, 'UserManagementApiUrl', {
      value: this.userManagementApi.url,
      description: 'User Management API Gateway URL',
    });

    new cdk.CfnOutput(this, 'DataProcessorApiUrl', {
      value: this.dataProcessorApi.url,
      description: 'Data Processor API Gateway URL',
    });

    new cdk.CfnOutput(this, 'NotificationApiUrl', {
      value: this.notificationApi.url,
      description: 'Notification API Gateway URL',
    });

    new cdk.CfnOutput(this, 'HealthCheckApiUrl', {
      value: this.healthCheckApi.url,
      description: 'Health Check API Gateway URL',
    });

    new cdk.CfnOutput(this, 'DataBucketName', {
      value: dataBucket.bucketName,
      description: 'S3 Data Bucket Name',
    });

    new cdk.CfnOutput(this, 'NotificationTopicArn', {
      value: notificationTopic.topicArn,
      description: 'SNS Notification Topic ARN',
    });

    // CDK Nag suppressions for the stack
    NagSuppressions.addStackSuppressions(this, [
      {
        id: 'AwsSolutions-IAM4',
        reason: 'AWS managed policies are used appropriately for Lambda execution roles',
      },
      {
        id: 'AwsSolutions-IAM5',
        reason: 'Wildcard permissions are required for Lambda functions to access AWS services',
      },
    ]);

    // Add tags to all resources
    cdk.Tags.of(this).add('Project', 'LambdaCICDSample');
    cdk.Tags.of(this).add('Environment', environment);
    cdk.Tags.of(this).add('ManagedBy', 'CDK');
  }
}