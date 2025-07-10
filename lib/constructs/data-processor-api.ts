import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { NagSuppressions } from 'cdk-nag';

export interface DataProcessorApiProps {
  environment: string;
  logLevel: string;
  processedDataTable: dynamodb.Table;
  commonLayer: lambda.LayerVersion;
}

export class DataProcessorApi extends Construct {
  public readonly lambdaFunction: lambda.Function;
  public readonly api: apigateway.RestApi;
  public readonly dataBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: DataProcessorApiProps) {
    super(scope, id);

    // S3 Bucket for data processing
    this.dataBucket = new s3.Bucket(this, 'DataBucket', {
      bucketName: `${props.environment}-data-processor-${cdk.Aws.ACCOUNT_ID}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For demo purposes
      autoDeleteObjects: true, // For demo purposes
      enforceSSL: true,
    });

    // Lambda Function
    this.lambdaFunction = new lambda.Function(this, 'DataProcessorFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      code: lambda.Code.fromAsset('src/data_processor'),
      handler: 'data_processor.lambda_handler',
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      architecture: lambda.Architecture.X86_64,
      layers: [props.commonLayer],
      environment: {
        ENVIRONMENT: props.environment,
        LOG_LEVEL: props.logLevel,
        PROCESSED_DATA_TABLE_NAME: props.processedDataTable.tableName,
        DATA_BUCKET_NAME: this.dataBucket.bucketName,
      },
      tracing: lambda.Tracing.ACTIVE,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant permissions
    props.processedDataTable.grantReadWriteData(this.lambdaFunction);
    this.dataBucket.grantReadWrite(this.lambdaFunction);

    // S3 Event Notification
    this.dataBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(this.lambdaFunction),
      { prefix: 'uploads/' }
    );

    // CloudWatch Log Group for API Gateway
    const apiLogGroup = new logs.LogGroup(this, 'DataProcessorApiLogs', {
      logGroupName: `/aws/apigateway/${props.environment}-data-processor-api`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // API Gateway
    this.api = new apigateway.RestApi(this, 'DataProcessorApi', {
      restApiName: `${props.environment}-data-processor-api`,
      description: 'Data Processor API',
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
    const processResource = this.api.root.addResource('process');
    processResource.addMethod('POST', lambdaIntegration);

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
          reason: 'Lambda needs wildcard permissions for CloudWatch logs, DynamoDB, and S3 operations',
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
      this.dataBucket,
      [
        {
          id: 'AwsSolutions-S1',
          reason: 'Access logging is not required for this demo bucket',
        },
      ]
    );
  }
}