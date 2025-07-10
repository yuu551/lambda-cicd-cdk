import * as cdk from 'aws-cdk-lib';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';
import { NagSuppressions } from 'cdk-nag';

export interface DatabaseTablesProps {
  environment: string;
}

export class DatabaseTables extends Construct {
  public readonly userTable: dynamodb.Table;
  public readonly processedDataTable: dynamodb.Table;
  public readonly notificationTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props: DatabaseTablesProps) {
    super(scope, id);

    // User Table
    this.userTable = new dynamodb.Table(this, 'UserTable', {
      tableName: `${props.environment}-users`,
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For demo purposes
    });

    // Processed Data Table
    this.processedDataTable = new dynamodb.Table(this, 'ProcessedDataTable', {
      tableName: `${props.environment}-processed-data`,
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For demo purposes
    });

    // Notification Table
    this.notificationTable = new dynamodb.Table(this, 'NotificationTable', {
      tableName: `${props.environment}-notifications`,
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
      pointInTimeRecovery: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For demo purposes
    });

    // CDK Nag suppressions
    NagSuppressions.addResourceSuppressions(
      [this.userTable, this.processedDataTable, this.notificationTable],
      [
        {
          id: 'AwsSolutions-DDB3',
          reason: 'Point-in-time recovery is enabled for backup and restore capabilities',
        },
      ]
    );
  }
}