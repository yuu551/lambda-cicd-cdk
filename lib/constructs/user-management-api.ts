import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import { NagSuppressions } from 'cdk-nag';

export interface UserManagementApiProps {
  environment: string;
  logLevel: string;
  userTable: dynamodb.Table;
  commonLayer: lambda.LayerVersion;
}

export class UserManagementApi extends Construct {
  public readonly lambdaFunction: lambda.Function;
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: UserManagementApiProps) {
    super(scope, id);

    // Lambda Function
    this.lambdaFunction = new lambda.Function(this, 'UserManagementFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      code: lambda.Code.fromAsset('src/user_management'),
      handler: 'user_management.lambda_handler',
      timeout: cdk.Duration.seconds(30),
      memorySize: 512,
      architecture: lambda.Architecture.X86_64,
      layers: [props.commonLayer],
      environment: {
        ENVIRONMENT: props.environment,
        LOG_LEVEL: props.logLevel,
        USER_TABLE_NAME: props.userTable.tableName,
      },
      tracing: lambda.Tracing.ACTIVE,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // Grant DynamoDB permissions
    props.userTable.grantReadWriteData(this.lambdaFunction);

    // API Gateway
    this.api = new apigateway.RestApi(this, 'UserManagementApi', {
      restApiName: `${props.environment}-user-management-api`,
      description: 'User Management API',
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
    const usersResource = this.api.root.addResource('users');
    
    // POST /users - Create user
    usersResource.addMethod('POST', lambdaIntegration);
    
    // GET /users - List users
    usersResource.addMethod('GET', lambdaIntegration);
    
    // GET /users/{id} - Get user by ID
    const userIdResource = usersResource.addResource('{id}');
    userIdResource.addMethod('GET', lambdaIntegration);

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
          reason: 'Lambda needs wildcard permissions for CloudWatch logs and DynamoDB table operations',
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
      ]
    );
  }
}