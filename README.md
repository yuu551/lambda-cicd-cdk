# Lambda CI/CD with AWS CDK

AWS CDKを使用したサーバーレスアプリケーションのCI/CDサンプルプロジェクトです。

## 📁 プロジェクト構成

```
lambda-cicd-cdk/
├── lib/
│   ├── lambda-cicd-cdk-stack.ts      # メインスタック
│   ├── constructs/                   # カスタムConstructs
│   │   ├── user-management-api.ts    # ユーザー管理API
│   │   ├── data-processor-api.ts     # データ処理API + S3
│   │   ├── notification-service.ts   # 通知サービス + SNS
│   │   ├── health-check-api.ts       # ヘルスチェックAPI
│   │   └── database-tables.ts        # DynamoDB テーブル群
│   └── shared/
│       ├── lambda-layer.ts           # 共通Lambda Layer
│       └── security-config.ts        # CDK Nag セキュリティ設定
├── src/                              # Pythonソースコード
│   ├── user_management/              # ユーザー管理Lambda
│   ├── data_processor/               # データ処理Lambda
│   ├── notification/                 # 通知Lambda
│   ├── health_check/                 # ヘルスチェックLambda
│   └── layers/common/                # 共通ライブラリ
├── test/
│   ├── python/                       # Pythonテスト
│   │   ├── test_user_management.py
│   │   ├── test_data_processor.py
│   │   ├── test_notification.py
│   │   └── test_health_check.py
│   └── lambda-cicd-cdk.test.ts       # CDKテスト
├── .github/workflows/
│   └── cicd.yml                      # GitHub Actions CI/CD
├── cdk.json                          # CDK設定
└── package.json                      # TypeScript依存関係
```

## 🚀 機能

### Lambda関数
1. **User Management API** - ユーザー管理
   - ユーザー作成 (POST /users)
   - ユーザー取得 (GET /users/{id})
   - ユーザー一覧 (GET /users)

2. **Data Processor API** - データ処理
   - API経由でのデータ処理 (POST /process)
   - S3オブジェクト作成時の自動処理

3. **Notification Service** - 通知サービス
   - Email/SMS通知 (POST /notify)
   - SNSトピック経由の通知処理

4. **Health Check API** - ヘルスチェック
   - システム状態確認 (GET /health)

### ベストプラクティス実装
- **セキュリティ**: CDK Nag統合でセキュリティルール自動チェック
- **型安全性**: TypeScriptによるインフラ定義
- **テスト**: 包括的なPythonテストスイート
- **CI/CD**: GitHub Actions による自動デプロイ
- **モニタリング**: X-Ray分散トレーシング、CloudWatch Logs
- **IAM**: 最小権限の原則

## 🛠️ 前提条件

- [Node.js](https://nodejs.org/) 18以上
- [AWS CLI](https://aws.amazon.com/cli/) がインストールされ、設定されている
- [AWS CDK](https://docs.aws.amazon.com/cdk/latest/guide/getting_started.html) がインストールされている
- [Python](https://www.python.org/) 3.9以上
- [Docker](https://www.docker.com/) (ローカルテスト用)

## 🔧 ローカル開発環境の設定

### 1. プロジェクトのクローンと依存関係のインストール

```bash
# リポジトリをクローン
git clone <repository-url>
cd lambda-cicd-cdk

# Node.js依存関係をインストール
npm install

# Python テスト依存関係をインストール
cd test/python
pip install -r requirements.txt
cd ../..
```

### 2. CDK Bootstrap（初回のみ）

```bash
# AWSアカウントでCDKを初期化
npx cdk bootstrap
```

### 3. ビルドと検証

```bash
# TypeScriptコンパイル
npm run build

# CDKテンプレート生成（CDK Nagチェック付き）
npx cdk synth

# TypeScriptテスト実行
npm test
```

### 4. Pythonテスト実行

```bash
cd test/python

# 個別テスト実行
python -m pytest test_user_management.py -v
python -m pytest test_data_processor.py -v
python -m pytest test_notification.py -v
python -m pytest test_health_check.py -v

# 全テスト実行（カバレッジ付き）
python -m pytest -v --cov=../../src --cov-report=html
```

## 🚀 デプロイ方法

### 開発環境

```bash
# 開発環境にデプロイ
npx cdk deploy LambdaCicdCdk-dev \
  --context environment=dev \
  --context logLevel=DEBUG
```

### 本番環境

```bash
# 本番環境にデプロイ
npx cdk deploy LambdaCicdCdk-prod \
  --context environment=prod \
  --context logLevel=INFO
```

### 環境固有のデプロイ

```bash
# 環境変数を使用
export ENVIRONMENT=staging
export LOG_LEVEL=INFO
npx cdk deploy LambdaCicdCdk-staging
```

## 🐙 CI/CD設定

### GitHub Actions

このプロジェクトは GitHub Actions による CI/CD パイプラインを含んでいます。

#### 必要な設定

1. **GitHub Environments**: `development`, `production`
2. **GitHub Secrets**: 各環境に `AWS_ROLE_ARN` を設定
3. **AWS OIDC Provider**: GitHubからのアクセス用

#### ワークフロー

- `develop` ブランチ → 開発環境へ自動デプロイ
- `main` ブランチ → 本番環境へ自動デプロイ
- Pull Request → テスト実行 + セキュリティスキャン

### AWS OIDC設定

```bash
# OIDC Providerを作成（一度のみ）
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com
```

## 🧪 テスト

### 単体テスト

```bash
# Python Lambda関数テスト
cd test/python
python -m pytest -v

# CDKスタックテスト
npm test
```

### 統合テスト

```bash
# デプロイ後のAPI URLを取得
export USER_API_URL=$(aws cloudformation describe-stacks \
  --stack-name LambdaCicdCdk-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`UserManagementApiUrl`].OutputValue' \
  --output text)

# APIテスト
curl -X POST ${USER_API_URL}users \
  -H "Content-Type: application/json" \
  -d '{"name": "Test User", "email": "test@example.com"}'

curl ${USER_API_URL}users
```

## 📊 モニタリング

デプロイ後は以下のAWSサービスでモニタリングできます:

- **CloudWatch Logs**: Lambda関数のログ
- **CloudWatch Metrics**: パフォーマンス指標
- **X-Ray**: 分散トレーシング（有効化済み）
- **CloudFormation**: スタック状態

### ログ確認

```bash
# 特定の関数のログを確認
aws logs tail /aws/lambda/LambdaCicdCdk-dev-UserManagementApiUserManagementFunction --follow

# CDKを使用したログ確認
npx cdk logs LambdaCicdCdk-dev/UserManagementApi/UserManagementFunction --follow
```

## 🛡️ セキュリティ

### CDK Nag

すべてのリソースにCDK Nagセキュリティチェックを適用:

```bash
# セキュリティチェック実行
npm run build
npx cdk synth > /dev/null
```

### セキュリティ機能

- Lambda関数は最小権限IAMロール
- DynamoDB暗号化有効
- S3バケット暗号化 + パブリックアクセスブロック
- API Gateway CORS設定
- X-Ray分散トレーシング

## 🔧 CDKコマンド

```bash
# TypeScriptコンパイル
npm run build

# ファイル変更監視
npm run watch

# テスト実行
npm test

# CloudFormationテンプレート生成
npx cdk synth

# デプロイ前差分確認
npx cdk diff

# デプロイ
npx cdk deploy

# スタック削除
npx cdk destroy
```

## 🔧 トラブルシューティング

### よくある問題

1. **CDK Bootstrap未実行**
   ```bash
   npx cdk bootstrap
   ```

2. **Python依存関係エラー**
   ```bash
   cd test/python
   pip install -r requirements.txt
   ```

3. **CDK Nag警告**
   ```bash
   # 警告を確認
   npx cdk synth --quiet
   ```

4. **Lambda Layer ビルドエラー**
   ```bash
   # レイヤーディレクトリの確認
   ls -la src/layers/common/
   ```

### デバッグ

```bash
# 詳細ログでデプロイ
npx cdk deploy --verbose

# CloudFormationイベント確認
aws cloudformation describe-stack-events --stack-name LambdaCicdCdk-dev
```

## 📝 ライセンス

このプロジェクトはMIT License の下で公開されています。

## 🤝 貢献

1. このリポジトリをフォーク
2. 新しいブランチを作成 (`git checkout -b feature/new-feature`)
3. 変更をコミット (`git commit -am 'Add new feature'`)
4. ブランチにプッシュ (`git push origin feature/new-feature`)
5. プルリクエストを作成

## 📚 参考資料

- [AWS CDK デベロッパーガイド](https://docs.aws.amazon.com/cdk/latest/guide/)
- [CDK Nag セキュリティチェック](https://github.com/cdklabs/cdk-nag)
- [AWS Lambda 開発者ガイド](https://docs.aws.amazon.com/lambda/latest/dg/)
- [GitHub Actions でのCDKデプロイ](https://docs.aws.amazon.com/cdk/latest/guide/deploying.html)
