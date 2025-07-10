import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { NagSuppressions } from 'cdk-nag';

// Import our constructs
import { CommonLambdaLayer } from './shared/lambda-layer';
import { DatabaseTables } from './constructs/database-tables';
import { UserManagementApi } from './constructs/user-management-api';
import { DataProcessorApi } from './constructs/data-processor-api';
import { NotificationService } from './constructs/notification-service';
import { HealthCheckApi } from './constructs/health-check-api';

export interface LambdaCicdCdkStackProps extends cdk.StackProps {
  environment?: string;
  logLevel?: string;
}

export class LambdaCicdCdkStack extends cdk.Stack {
  public readonly userManagementApi: UserManagementApi;
  public readonly dataProcessorApi: DataProcessorApi;
  public readonly notificationService: NotificationService;
  public readonly healthCheckApi: HealthCheckApi;

  constructor(scope: Construct, id: string, props?: LambdaCicdCdkStackProps) {
    super(scope, id, props);

    // Environment configuration
    const environment = props?.environment || 'dev';
    const logLevel = props?.logLevel || 'INFO';

    // Common Lambda Layer
    const commonLayer = new CommonLambdaLayer(this, 'CommonLayer');

    // Database Tables
    const databases = new DatabaseTables(this, 'DatabaseTables', {
      environment,
    });

    // User Management API
    this.userManagementApi = new UserManagementApi(this, 'UserManagementApi', {
      environment,
      logLevel,
      userTable: databases.userTable,
      commonLayer: commonLayer.layer,
    });

    // Data Processor API
    this.dataProcessorApi = new DataProcessorApi(this, 'DataProcessorApi', {
      environment,
      logLevel,
      processedDataTable: databases.processedDataTable,
      commonLayer: commonLayer.layer,
    });

    // Notification Service
    this.notificationService = new NotificationService(this, 'NotificationService', {
      environment,
      logLevel,
      notificationTable: databases.notificationTable,
      commonLayer: commonLayer.layer,
    });

    // Health Check API
    this.healthCheckApi = new HealthCheckApi(this, 'HealthCheckApi', {
      environment,
      logLevel,
    });

    // Stack outputs
    new cdk.CfnOutput(this, 'UserManagementApiUrl', {
      value: this.userManagementApi.api.url,
      description: 'User Management API Gateway URL',
    });

    new cdk.CfnOutput(this, 'DataProcessorApiUrl', {
      value: this.dataProcessorApi.api.url,
      description: 'Data Processor API Gateway URL',
    });

    new cdk.CfnOutput(this, 'NotificationApiUrl', {
      value: this.notificationService.api.url,
      description: 'Notification API Gateway URL',
    });

    new cdk.CfnOutput(this, 'HealthCheckApiUrl', {
      value: this.healthCheckApi.api.url,
      description: 'Health Check API Gateway URL',
    });

    new cdk.CfnOutput(this, 'DataBucketName', {
      value: this.dataProcessorApi.dataBucket.bucketName,
      description: 'S3 Data Bucket Name',
    });

    new cdk.CfnOutput(this, 'NotificationTopicArn', {
      value: this.notificationService.notificationTopic.topicArn,
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
