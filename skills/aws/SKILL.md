---
name: aws-cli
description: Perform AWS operations via the CLI. Use when the user asks to manage AWS resources, services, infrastructure, or anything involving EC2, S3, Lambda, IAM, RDS, ECS, CloudFormation, Route53, CloudWatch, Lightsail, or other AWS services.
---

# AWS CLI Operations

Run AWS commands via the Shell tool. The active profile is determined by `$AWS_PROFILE` or the `[default]` section in `~/.aws/credentials`. No `--profile` flag is needed unless the user specifies a non-default profile.

## Authentication

On first use, verify credentials are configured:

```bash
aws sts get-caller-identity
```

If this fails with `Unable to locate credentials`, walk the user through setup:

```bash
aws configure
```

This prompts for Access Key ID, Secret Access Key, default region, and output format. Credentials are stored in `~/.aws/credentials` and config in `~/.aws/config`.

To check the active region:

```bash
aws configure get region
```

If the user has multiple profiles, they can switch with `--profile <name>` or by setting `AWS_PROFILE`.

## Output and Filtering

Default output is JSON. Use `--output table` for human-readable display, or `--query` for JMESPath filtering:

```bash
aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,State.Name,InstanceType]' --output table
```

Use `--no-cli-pager` when output is long and you want it inline.

## Safety Rules

1. **Destructive operations require confirmation.** Before running any of these, describe what will happen and ask the user to confirm:
   - `terminate-instances`, `delete-*`, `remove-*`, `deregister-*`
   - `drop`, `destroy`, `purge`
   - Modifying security groups to open `0.0.0.0/0`
   - Deleting IAM users, roles, or policies
   - Emptying or deleting S3 buckets

2. **Cost-incurring operations require a warning.** Before creating resources that cost money, state the expected cost impact:
   - EC2 instances (mention instance type pricing)
   - RDS instances, NAT Gateways, ELBs
   - Data transfer, EBS volumes
   - "This will create a `t3.micro` instance (~$8.50/month in us-east-1). Proceed?"

3. **Never expose secrets.** Do not print access keys, secret keys, passwords, or tokens in output shown to the user. Use `--query` to filter them out, or redact them.

## Common Workflows

### EC2

```bash
# List running instances
aws ec2 describe-instances --filters "Name=instance-state-name,Values=running" --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,PublicIpAddress,Tags[?Key==`Name`].Value|[0]]' --output table

# Launch instance (confirm cost first)
aws ec2 run-instances --image-id ami-xxxxx --instance-type t3.micro --key-name MyKey --security-group-ids sg-xxxxx --subnet-id subnet-xxxxx --count 1

# Stop / start / terminate (confirm destructive ops)
aws ec2 stop-instances --instance-ids i-xxxxx
aws ec2 start-instances --instance-ids i-xxxxx
aws ec2 terminate-instances --instance-ids i-xxxxx
```

### S3

```bash
# List buckets
aws s3 ls

# Sync local directory to bucket
aws s3 sync ./local-dir s3://bucket-name/prefix

# Copy file
aws s3 cp file.txt s3://bucket-name/

# Presigned URL (1 hour)
aws s3 presign s3://bucket-name/file.txt --expires-in 3600
```

### IAM

```bash
# List users
aws iam list-users --output table

# List attached policies for a user
aws iam list-attached-user-policies --user-name <username>

# Create a new role
aws iam create-role --role-name MyRole --assume-role-policy-document file://trust-policy.json
```

### Lambda

```bash
# List functions
aws lambda list-functions --query 'Functions[*].[FunctionName,Runtime,LastModified]' --output table

# Invoke function
aws lambda invoke --function-name my-function --payload '{"key":"value"}' response.json

# Update function code
aws lambda update-function-code --function-name my-function --zip-file fileb://function.zip
```

### CloudFormation

```bash
# List stacks
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --output table

# Deploy stack
aws cloudformation deploy --template-file template.yaml --stack-name my-stack --capabilities CAPABILITY_IAM

# Delete stack (confirm first)
aws cloudformation delete-stack --stack-name my-stack
```

### RDS

```bash
# List DB instances
aws rds describe-db-instances --query 'DBInstances[*].[DBInstanceIdentifier,Engine,DBInstanceStatus,Endpoint.Address]' --output table
```

### Route53

```bash
# List hosted zones
aws route53 list-hosted-zones --output table

# List records in a zone
aws route53 list-resource-record-sets --hosted-zone-id Z1234567890
```

### CloudWatch

```bash
# List alarms
aws cloudwatch describe-alarms --state-value ALARM --output table

# Get metrics
aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name CPUUtilization --dimensions Name=InstanceId,Value=i-xxxxx --start-time 2024-01-01T00:00:00Z --end-time 2024-01-02T00:00:00Z --period 3600 --statistics Average
```

### Lightsail

```bash
# List instances
aws lightsail get-instances --query 'instances[*].[name,state.name,publicIpAddress,blueprintId]' --output table

# Get instance details
aws lightsail get-instance --instance-name MyInstance
```

### ECS

```bash
# List clusters
aws ecs list-clusters

# List services in a cluster
aws ecs list-services --cluster my-cluster

# Describe service
aws ecs describe-services --cluster my-cluster --services my-service
```

### Secrets Manager

```bash
# List secrets
aws secretsmanager list-secrets --query 'SecretList[*].[Name,LastChangedDate]' --output table

# Get secret value (be careful with output)
aws secretsmanager get-secret-value --secret-id my-secret --query 'SecretString' --output text
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `AccessDenied` / `UnauthorizedAccess` | Missing IAM permission | Check the policies attached to the active IAM identity via `aws iam list-attached-user-policies` or `aws iam list-attached-role-policies` |
| `ExpiredTokenException` | Credentials expired or rotated | Run `aws sts get-caller-identity` to check; re-run `aws configure` if needed |
| `ThrottlingException` | API rate limit hit | Wait and retry with exponential backoff |
| `ResourceNotFoundException` | Resource doesn't exist or wrong region | Verify region with `--region` flag |
| `InvalidParameterValue` | Bad input | Check AWS docs for the correct parameter format |

## Multi-Region Operations

Use the default region from `~/.aws/config`. For resources in other regions, pass `--region`:

```bash
aws ec2 describe-instances --region eu-west-1
```

For global services (IAM, Route53, CloudFront, S3 bucket creation), region doesn't matter.
