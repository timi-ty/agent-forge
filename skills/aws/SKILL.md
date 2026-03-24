---
name: aws
description: Perform AWS operations via the CLI. Use when the user asks to manage AWS resources, services, infrastructure, or anything involving EC2, S3, Lambda, IAM, RDS, ECS, CloudFormation, Route53, CloudWatch, Lightsail, or other AWS services.
---

# AWS CLI Operations — Multi-Account

This skill manages multiple AWS accounts (static IAM keys and SAML SSO) with safe switching. An account registry at `~/.aws/account-registry.json` tracks all configured accounts and which one is active.

**CRITICAL**: Every `aws` command MUST be prefixed with `AWS_PROFILE=<profile>` using the active profile from the registry. Shell env vars do not persist between tool calls.

---

## Active Account Check (MANDATORY — run on EVERY invocation)

Before doing anything else, determine the active account and verify credentials:

```bash
python -c "
import json, pathlib
reg = json.loads(pathlib.Path.home().joinpath('.aws/account-registry.json').read_text())
acct = reg['accounts'][reg['active']]
print(f\"Active: {reg['active']} | {acct.get('description','')} | Account ID: {acct.get('account_id','unknown')} | Region: {acct.get('region','us-east-1')} | Auth: {acct['auth_method']}\")
print(f\"AWS_PROFILE={acct['aws_profile']}\")
"
```

Then verify credentials:

```bash
AWS_PROFILE=<profile> aws sts get-caller-identity --output json
```

- If creds work → show the banner to the user and proceed.
- If creds fail → run the Credential Refresh procedure for the account's `auth_method` (see the Credential Refresh section).

If `~/.aws/account-registry.json` does not exist → run First-Time Setup (the First-Time Setup section).

---

## Account Management

### List accounts

```bash
python -c "
import json, pathlib
reg = json.loads(pathlib.Path.home().joinpath('.aws/account-registry.json').read_text())
for name, acct in reg['accounts'].items():
    marker = ' (active)' if name == reg['active'] else ''
    print(f\"  {name}{marker} — {acct.get('description','')} [{acct['auth_method']}]\")
"
```

### Register a new account — static keys

1. Ask the user for: friendly name, description, AWS profile name, region, access key ID, secret access key.
2. Run `aws configure --profile <profile>` (or write to `~/.aws/credentials` directly).
3. Verify with `AWS_PROFILE=<profile> aws sts get-caller-identity`.
4. Capture the account ID from the response.
5. Add to registry:

```bash
python -c "
import json, pathlib
p = pathlib.Path.home() / '.aws/account-registry.json'
reg = json.loads(p.read_text())
reg['accounts']['<name>'] = {
    'description': '<desc>',
    'account_id': '<from_sts>',
    'aws_profile': '<profile>',
    'region': '<region>',
    'auth_method': 'static_keys'
}
p.write_text(json.dumps(reg, indent=2))
print('Added.')
"
```

### Register a new account — SAML SSO (saml2aws)

**Prerequisites**: `saml2aws` must be installed. Check with `saml2aws --version`. If missing, tell the user to install it: `choco install saml2aws -y` (Windows, elevated PowerShell) or `brew install saml2aws` (macOS). The agent cannot elevate privileges.

1. Ask the user for: friendly name, description, SAML IDP URL, AWS profile name, IAM role ARN, region, session duration (default 3600).
2. Create the storage state directory:

```bash
mkdir -p ~/.aws/saml2aws
```

3. Configure saml2aws. **Always use the Browser provider** — programmatic providers (KeyCloak, Okta, etc.) cannot handle MFA flows:

```bash
saml2aws configure \
  --idp-account=<name> \
  --idp-provider=Browser \
  --url="<idp_url>" \
  --username="<user_email>" \
  --profile=<aws_profile> \
  --role="<role_arn>" \
  --session-duration=<duration> \
  --mfa=Auto \
  --skip-prompt
```

4. First login — this opens a Chromium browser for the user to complete login + MFA:

```bash
saml2aws login --idp-account=<name> --profile=<aws_profile> --download-browser-driver --skip-prompt
```

The `--download-browser-driver` flag auto-installs Playwright Chromium on first use. The browser opens for the user to authenticate (enter credentials, complete MFA, select role if needed). After successful auth, saml2aws captures the SAML assertion and writes temporary credentials to `~/.aws/credentials` under the named profile.

5. Verify: `AWS_PROFILE=<aws_profile> aws sts get-caller-identity`.
6. Capture account ID and add to registry:

```bash
python -c "
import json, pathlib
p = pathlib.Path.home() / '.aws/account-registry.json'
reg = json.loads(p.read_text())
reg['accounts']['<name>'] = {
    'description': '<desc>',
    'account_id': '<from_sts>',
    'aws_profile': '<aws_profile>',
    'region': '<region>',
    'auth_method': 'saml2aws',
    'saml2aws_idp_account': '<name>',
    'idp_url': '<url>',
    'idp_provider': 'Browser',
    'role_arn': '<role_arn>',
    'session_duration': <duration>
}
p.write_text(json.dumps(reg, indent=2))
print('Added.')
"
```

### Remove an account

Remove from registry only. Do NOT delete AWS profiles or credentials files.

```bash
python -c "
import json, pathlib
p = pathlib.Path.home() / '.aws/account-registry.json'
reg = json.loads(p.read_text())
if '<name>' == reg['active']:
    print('ERROR: Cannot remove the active account. Switch first.')
else:
    del reg['accounts']['<name>']
    p.write_text(json.dumps(reg, indent=2))
    print('Removed.')
"
```

---

## Account Switching

When the user asks to switch accounts (e.g., "switch to dnn-dev", "use my personal account"):

1. Verify the target account exists in the registry.
2. Test credentials: `AWS_PROFILE=<target_profile> aws sts get-caller-identity`.
3. If expired → run the Credential Refresh procedure for the account's `auth_method` (see the Credential Refresh section).
4. Update registry:

```bash
python -c "
import json, pathlib
p = pathlib.Path.home() / '.aws/account-registry.json'
reg = json.loads(p.read_text())
reg['active'] = '<target_name>'
p.write_text(json.dumps(reg, indent=2))
print('Switched to <target_name>.')
"
```

5. Confirm by running `AWS_PROFILE=<target_profile> aws sts get-caller-identity`.

---

## Safety Rules

### Destructive operations require confirmation

Before running any of these, describe what will happen, **state which account is affected**, and ask the user to confirm:

- `terminate-instances`, `delete-*`, `remove-*`, `deregister-*`
- `drop`, `destroy`, `purge`
- Modifying security groups to open `0.0.0.0/0`
- Deleting IAM users, roles, or policies
- Emptying or deleting S3 buckets

### Cost-incurring operations require a warning

Before creating resources that cost money, state the expected cost impact and the target account:

- EC2 instances (mention instance type pricing)
- RDS instances, NAT Gateways, ELBs
- Data transfer, EBS volumes
- Example: "This will create a `t3.micro` instance (~$8.50/month in us-east-1) on account **personal** (851725607183). Proceed?"

### Cross-account safety

- Always include the active account name and ID in destructive/cost confirmations.
- If the user's request seems to target a different account than the active one (e.g., they mention "dev" resources but the active account is "personal"), warn them and ask if they want to switch first.

### Never expose secrets

Do not print access keys, secret keys, passwords, or tokens. Use `--query` to filter them out, or redact them.

---

## Credential Refresh

**Principle**: When credentials expire or fail, refresh them using the same method that was originally used to obtain them. This applies at invocation start (the mandatory Active Account Check) AND mid-operation if any `aws` command returns `ExpiredTokenException`, `ExpiredToken`, `RequestExpired`, or an `InvalidIdentityToken` error.

### Refresh by auth method

Read the active account's `auth_method` from the registry and follow the matching procedure:

#### `saml2aws`

Re-run the same login command used during initial registration — this opens the browser for the user to re-authenticate, exactly as they did the first time:

```bash
saml2aws login --idp-account=<saml2aws_idp_account> --profile=<aws_profile> --download-browser-driver --skip-prompt
```

After successful login, retry the command that failed. If `saml2aws` is not installed, tell the user to install it: `choco install saml2aws -y` (Windows, elevated PowerShell) or `brew install saml2aws` (macOS).

#### `static_keys`

Static IAM keys do not expire on a timer, but they can be rotated or revoked. When `sts get-caller-identity` fails for a static-keys account, re-run the same configuration command used during initial setup:

```bash
aws configure --profile <aws_profile>
```

Prompt the user to enter their new Access Key ID and Secret Access Key, then verify with `AWS_PROFILE=<profile> aws sts get-caller-identity`.

### Mid-operation expiry

If any `aws` command fails with a credential-expiry error during a multi-step operation:

1. Pause the operation.
2. Run the refresh procedure for the active account's `auth_method` (above).
3. Verify with `AWS_PROFILE=<profile> aws sts get-caller-identity`.
4. Retry the failed command and continue the operation.

---

## First-Time Setup

Auto-detected when `~/.aws/account-registry.json` does not exist:

1. Check if `~/.aws/credentials` has a `[default]` section.
2. If yes → run `aws sts get-caller-identity` to get the account ID.
3. Create the registry:

```bash
python -c "
import json, pathlib
p = pathlib.Path.home() / '.aws/account-registry.json'
p.write_text(json.dumps({
    'active': 'personal',
    'accounts': {
        'personal': {
            'description': 'Personal AWS account',
            'account_id': '<from_sts>',
            'aws_profile': 'default',
            'region': '<from aws configure get region>',
            'auth_method': 'static_keys'
        }
    }
}, indent=2))
print('Registry created with personal account.')
"
```

4. Ask if the user wants to add any SSO accounts.

---

## Output and Filtering

Default output is JSON. Use `--output table` for human-readable display, or `--query` for JMESPath filtering:

```bash
AWS_PROFILE=<profile> aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId,State.Name,InstanceType]' --output table
```

Use `--no-cli-pager` when output is long and you want it inline.

---

## Common Workflows

All commands below must be prefixed with `AWS_PROFILE=<active_profile>` from the registry.

### EC2

```bash
# List running instances
aws ec2 describe-instances --filters "Name=instance-state-name,Values=running" --query 'Reservations[*].Instances[*].[InstanceId,InstanceType,PublicIpAddress,Tags[?Key==`Name`].Value|[0]]' --output table

# Launch instance (confirm cost + account first)
aws ec2 run-instances --image-id ami-xxxxx --instance-type t3.micro --key-name MyKey --security-group-ids sg-xxxxx --subnet-id subnet-xxxxx --count 1

# Stop / start / terminate (confirm destructive ops + account)
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

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `AccessDenied` / `UnauthorizedAccess` | Missing IAM permission | Check policies via `aws iam list-attached-user-policies` or `aws iam list-attached-role-policies` |
| `ExpiredTokenException` / `ExpiredToken` / `RequestExpired` | Credentials expired | Run the Credential Refresh procedure for the account's `auth_method` (see the Credential Refresh section), then retry the command |
| `ThrottlingException` | API rate limit hit | Wait and retry with exponential backoff |
| `ResourceNotFoundException` | Resource doesn't exist or wrong region | Verify region with `--region` flag |
| `InvalidParameterValue` | Bad input | Check AWS docs for the correct parameter format |

## Multi-Region Operations

Use the region from the active account in the registry. For resources in other regions, pass `--region`:

```bash
AWS_PROFILE=<profile> aws ec2 describe-instances --region eu-west-1
```

For global services (IAM, Route53, CloudFront, S3 bucket creation), region doesn't matter.
