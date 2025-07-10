import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as snsSubscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { NagSuppressions } from 'cdk-nag';

export interface NotificationServiceProps {
  environment: string;
  logLevel: string;
  notificationTable: dynamodb.Table;
  commonLayer: lambda.LayerVersion;
}

export class NotificationService extends Construct {
  public readonly lambdaFunction: lambda.Function;
  public readonly api: apigateway.RestApi;
  public readonly notificationTopic: sns.Topic;

  constructor(scope: Construct, id: string, props: NotificationServiceProps) {
    super(scope, id);

    // SNS Topic
    this.notificationTopic = new sns.Topic(this, 'NotificationTopic', {
      topicName: `${props.environment}-notifications`,
      displayName: 'Notification Topic',
    });

    // Lambda Function
    this.lambdaFunction = new lambda.Function(this, 'NotificationFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      code: lambda.Code.fromAsset('src/notification'),
      handler: 'notification.lambda_handler',
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      architecture: lambda.Architecture.X86_64,
      layers: [props.commonLayer],
      environment: {
        ENVIRONMENT: props.environment,
        LOG_LEVEL: props.logLevel,
        NOTIFICATION_TABLE_NAME: props.notificationTable.tableName,
        SNS_TOPIC_ARN: this.notificationTopic.topicArn,
      },
      tracing: lambda.Tracing.ACTIVE,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant permissions
    props.notificationTable.grantReadWriteData(this.lambdaFunction);
    this.notificationTopic.grantPublish(this.lambdaFunction);

    // SNS Subscription to Lambda
    this.notificationTopic.addSubscription(
      new snsSubscriptions.LambdaSubscription(this.lambdaFunction)
    );

    // CloudWatch Log Group for API Gateway
    const apiLogGroup = new logs.LogGroup(this, 'NotificationApiLogs', {
      logGroupName: `/aws/apigateway/${props.environment}-notification-api`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // API Gateway
    this.api = new apigateway.RestApi(this, 'NotificationApi', {
      restApiName: `${props.environment}-notification-api`,
      description: 'Notification Service API',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
        ],
      },
      cloudWatchRole: true,
      deployOptions: {
        accessLogDestination: new apigateway.LogGroupLogDestination(apiLogGroup),
        accessLogFormat: apigateway.AccessLogFormat.jsonWithStandardFields(),
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
      },
    });

    // Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(this.lambdaFunction);

    // API Routes
    const notifyResource = this.api.root.addResource('notify');
    notifyResource.addMethod('POST', lambdaIntegration);

    // CDK Nag suppressions
    NagSuppressions.addResourceSuppressions(
      this.lambdaFunction,
      [
        {
          id: 'AwsSolutions-IAM4',
          reason: 'Lambda execution role uses AWS managed policies with least privilege',
        },
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Lambda needs wildcard permissions for CloudWatch logs, DynamoDB, and SNS operations',
        },
      ]
    );

    NagSuppressions.addResourceSuppressions(
      this.api,
      [
        {
          id: 'AwsSolutions-APIG2',
          reason: 'Request validation is handled by Lambda function logic',
        },
        {
          id: 'AwsSolutions-APIG4',
          reason: 'Authorization is handled by application logic for this demo',
        },
        {
          id: 'AwsSolutions-COG4',
          reason: 'Cognito is not required for this demo API',
        },
        {
          id: 'AwsSolutions-APIG3',
          reason: 'WAF is not required for this demo API',
        },
      ]
    );

    NagSuppressions.addResourceSuppressions(
      this.notificationTopic,
      [
        {
          id: 'AwsSolutions-SNS2',
          reason: 'SNS topic encryption is not required for this demo',
        },
        {
          id: 'AwsSolutions-SNS3',
          reason: 'SNS topic does not require SSL-only policy for this demo',
        },
      ]
    );
  }
}