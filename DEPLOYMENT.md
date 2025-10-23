# AWS App Runner Deployment Guide

This guide covers deploying the Phish Setlist Maker API to AWS App Runner.

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured: `aws configure`
3. **Docker** installed locally (for testing)
4. **ML Feature Files** in `data/analytics/features/` directory

## Quick Start (Local Testing)

Test the Docker setup locally before deploying:

```bash
# Build and run with Docker Compose (includes local Postgres)
docker-compose up --build

# Or test just the API container
docker build -t phish-setlist-maker .
docker run -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host/db" \
  phish-setlist-maker

# Visit http://localhost:8000/docs
```

## Option 1: Deploy to AWS App Runner (Recommended)

### Step 1: Set Up AWS RDS Database

```bash
# Create a Postgres database
aws rds create-db-instance \
  --db-instance-identifier phish-setlist-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16.1 \
  --master-username phish \
  --master-user-password YOUR_SECURE_PASSWORD \
  --allocated-storage 20 \
  --publicly-accessible \
  --backup-retention-period 7

# Get the endpoint once created (takes ~10 minutes)
aws rds describe-db-instances \
  --db-instance-identifier phish-setlist-db \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text
```

### Step 2: Upload ML Features to S3 (Optional)

If features are large, store them in S3 instead of bundling in the image:

```bash
# Create S3 bucket
aws s3 mb s3://phish-setlist-features

# Upload feature files
aws s3 sync data/analytics/features/ s3://phish-setlist-features/

# Update Dockerfile to download from S3 at startup
```

### Step 3: Push Docker Image to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name phish-setlist-maker

# Get login credentials
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build and tag image
docker build -t phish-setlist-maker .
docker tag phish-setlist-maker:latest \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/phish-setlist-maker:latest

# Push to ECR
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/phish-setlist-maker:latest
```

### Step 4: Create App Runner Service

Using the AWS Console (easiest):

1. Go to **AWS App Runner** console
2. Click **Create service**
3. Choose **Container registry** → **Amazon ECR**
4. Select your image: `phish-setlist-maker:latest`
5. Set **Port**: `8000`
6. Add environment variable:
   - `DATABASE_URL`: `postgresql://phish:PASSWORD@RDS_ENDPOINT:5432/phish`
7. Configure auto-scaling (optional):
   - Min: 1, Max: 3
   - Concurrency: 100
8. Click **Create & deploy**

Or use AWS CLI:

```bash
aws apprunner create-service \
  --service-name phish-setlist-maker \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/phish-setlist-maker:latest",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "DATABASE_URL": "postgresql://phish:PASSWORD@RDS_ENDPOINT:5432/phish"
        }
      },
      "ImageRepositoryType": "ECR"
    },
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{
    "Cpu": "1 vCPU",
    "Memory": "2 GB"
  }'
```

### Step 5: Access Your API

```bash
# Get the service URL
aws apprunner list-services

# Your API will be at: https://xxxxx.us-east-1.awsapprunner.com
# API docs: https://xxxxx.us-east-1.awsapprunner.com/docs
# Generate: https://xxxxx.us-east-1.awsapprunner.com/generate
```

## Option 2: Deploy to Elastic Beanstalk

```bash
# Initialize EB app
eb init -p docker phish-setlist-maker

# Create environment
eb create phish-setlist-prod --instance-type t3.micro

# Set environment variables
eb setenv DATABASE_URL="postgresql://user:pass@rds-endpoint:5432/phish"

# Deploy
eb deploy

# Open in browser
eb open
```

## Option 3: Deploy to ECS Fargate

See `docs/deployment/ecs-fargate.md` for detailed instructions.

## Environment Variables

Required environment variables for production:

```bash
DATABASE_URL=postgresql://user:password@host:port/database
PYTHONPATH=/app/src
```

Optional:

```bash
LOG_LEVEL=info
AWS_REGION=us-east-1
```

## Database Setup

After deploying, you need to populate your RDS database:

```bash
# Connect to RDS
psql postgresql://phish:PASSWORD@RDS_ENDPOINT:5432/phish

# Import your schema and data
\i path/to/your/dump.sql
```

## Monitoring & Logs

### App Runner Logs

```bash
# View logs
aws logs tail /aws/apprunner/phish-setlist-maker --follow

# Or use CloudWatch console
```

### Health Check

App Runner automatically monitors `/health` endpoint.

## Costs (Approximate)

- **App Runner**: $5-10/month (1 instance, light traffic)
- **RDS db.t3.micro**: $15/month
- **ECR Storage**: $0.10/GB/month (~$0.50 for this app)
- **Total**: ~$20-25/month

## Troubleshooting

### Container won't start
- Check CloudWatch logs
- Verify `DATABASE_URL` is correct
- Ensure ML feature files are included in image or mounted

### Database connection issues
- Check RDS security group allows inbound from App Runner
- Verify credentials in `DATABASE_URL`
- Ensure RDS is publicly accessible OR use VPC connector

### ML features missing
- Verify `data/analytics/features/*.parquet` are in the image
- Check file paths in application logs

## Updating the Deployment

```bash
# Rebuild and push new image
docker build -t phish-setlist-maker .
docker tag phish-setlist-maker:latest \
  YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/phish-setlist-maker:latest
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/phish-setlist-maker:latest

# App Runner will auto-deploy if enabled, or trigger manually:
aws apprunner start-deployment --service-arn YOUR_SERVICE_ARN
```

## Security Best Practices

1. **Never commit** `DATABASE_URL` or credentials to git
2. Use **AWS Secrets Manager** for database passwords
3. Enable **VPC connector** for RDS (not publicly accessible)
4. Use **IAM roles** instead of environment variables where possible
5. Enable **WAF** on App Runner for production

## Next Steps

- Set up custom domain with Route 53
- Configure HTTPS certificate
- Add CloudWatch alarms for errors
- Set up CI/CD with GitHub Actions
- Enable auto-scaling based on traffic
