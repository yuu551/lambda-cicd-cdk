#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { LambdaCicdCdkStack } from '../lib/lambda-cicd-cdk-stack';

const app = new cdk.App();

// Get environment configuration from context or environment variables
const environment = app.node.tryGetContext('environment') || process.env.ENVIRONMENT || 'dev';
const logLevel = app.node.tryGetContext('logLevel') || process.env.LOG_LEVEL || 'INFO';

// Create different stacks for different environments
const stackName = `LambdaCicdCdk-${environment}`;

new LambdaCicdCdkStack(app, stackName, {
  environment,
  logLevel,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  description: `Lambda CICD Sample Stack - ${environment} environment`,
  tags: {
    Project: 'LambdaCICDSample',
    Environment: environment,
    ManagedBy: 'CDK',
  },
});