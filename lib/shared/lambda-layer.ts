import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';

export class CommonLambdaLayer extends Construct {
  public readonly layer: PythonLayerVersion;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.layer = new PythonLayerVersion(this, 'CommonLayer', {
      entry: 'src/layers/common',
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Common utilities and libraries for Lambda functions',
      layerVersionName: 'lambda-cicd-common-layer',
    });
  }
}