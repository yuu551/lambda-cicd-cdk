import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { NagSuppressions } from 'cdk-nag';

export interface HealthCheckApiProps {
  environment: string;
  logLevel: string;
}

export class HealthCheckApi extends Construct {
  public readonly lambdaFunction: lambda.Function;
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: HealthCheckApiProps) {
    super(scope, id);

    // Lambda Function
    this.lambdaFunction = new lambda.Function(this, 'HealthCheckFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      code: lambda.Code.fromAsset('src/health_check'),
      handler: 'health_check.lambda_handler',
      timeout: cdk.Duration.seconds(30),
      memorySize: 256, // Lower memory for health check
      architecture: lambda.Architecture.X86_64,
      environment: {
        ENVIRONMENT: props.environment,
        LOG_LEVEL: props.logLevel,
      },
      tracing: lambda.Tracing.ACTIVE,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // API Gateway
    this.api = new apigateway.RestApi(this, 'HealthCheckApi', {
      restApiName: `${props.environment}-health-check-api`,
      description: 'Health Check API',
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
    });

    // Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(this.lambdaFunction);

    // API Routes
    const healthResource = this.api.root.addResource('health');
    healthResource.addMethod('GET', lambdaIntegration);

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
          reason: 'Lambda needs wildcard permissions for CloudWatch logs',
        },
      ]
    );

    NagSuppressions.addResourceSuppressions(
      this.api,
      [
        {
          id: 'AwsSolutions-APIG2',
          reason: 'Request validation is not required for health check endpoint',
        },
        {
          id: 'AwsSolutions-APIG4',
          reason: 'Authorization is not required for public health check endpoint',
        },
        {
          id: 'AwsSolutions-COG4',
          reason: 'Cognito is not required for health check endpoint',
        },
      ]
    );
  }
}