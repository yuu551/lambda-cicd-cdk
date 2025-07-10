import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { AwsSolutionsChecks, NagPackSuppression } from 'cdk-nag';

export class SecurityConfig {
  public static applyCdkNag(app: cdk.App): void {
    // Apply CDK Nag checks to all stacks
    cdk.Aspects.of(app).add(new AwsSolutionsChecks());
  }

  public static getCommonSuppressions(): NagPackSuppression[] {
    return [
      {
        id: 'AwsSolutions-IAM4',
        reason: 'AWS managed policies are used for Lambda execution roles with least privilege',
      },
      {
        id: 'AwsSolutions-IAM5',
        reason: 'Wildcard permissions required for Lambda to access DynamoDB tables and CloudWatch logs',
      },
    ];
  }
}