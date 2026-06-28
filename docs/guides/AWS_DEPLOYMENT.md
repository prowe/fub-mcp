# AWS Lambda Deployment Guide

Deploy the Follow Up Boss MCP Server as an AWS Lambda function accessible via
a **Lambda URL** endpoint.  No API credentials are stored in the cloud
infrastructure — every request supplies the Follow Up Boss API key as a query
parameter.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Authentication Model](#authentication-model)
4. [Quick Start](#quick-start)
5. [Step-by-Step Deployment](#step-by-step-deployment)
6. [Calling the Endpoint](#calling-the-endpoint)
7. [MCP Client Configuration](#mcp-client-configuration)
8. [Environment & Configuration](#environment--configuration)
9. [Updating the Function](#updating-the-function)
10. [Tear Down](#tear-down)
11. [Troubleshooting](#troubleshooting)
12. [Security Considerations](#security-considerations)

---

## Architecture Overview

```
MCP Client / curl
      │
      │  HTTPS POST  ?fub_api_key=<key>
      ▼
┌─────────────────────────────┐
│  Lambda URL  (public HTTPS) │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  AWS Lambda  (arm64/py3.12) │
│  lambda_handler.py          │
│  ├─ extracts fub_api_key    │
│  ├─ validates key present   │
│  └─ dispatches JSON-RPC     │
└──────────────┬──────────────┘
               │
               ▼
     Follow Up Boss API v1
```

* **No secrets in Lambda** – the FUB API key is never stored in the function
  environment or CloudFormation parameters.
* **Per-request key** – every caller supplies their own key; the Lambda can
  serve multiple FUB accounts simultaneously.
* **Stateless** – each invocation is independent; caching is in-process only
  and does not persist across cold starts.

---

## Prerequisites

| Tool | Minimum version | Install |
|------|-----------------|---------|
| Python | 3.9+ | [python.org](https://www.python.org/) |
| AWS CLI | 2.x | [aws.amazon.com/cli](https://aws.amazon.com/cli/) |
| AWS SAM CLI | 1.100+ | [docs.aws.amazon.com/serverless-application-model](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) |
| Docker | any recent | Required by `sam build` for consistent Lambda packaging |

You also need:

* An AWS account with sufficient IAM permissions to create Lambda functions,
  IAM roles, and CloudFormation stacks.
* A **Follow Up Boss API key** from
  [docs.followupboss.com](https://docs.followupboss.com/reference/getting-started).

---

## Authentication Model

The Lambda function uses a **zero-secrets deployment** model:

```
https://<lambda-url>/?fub_api_key=<YOUR_FOLLOW_UP_BOSS_API_KEY>
```

* The `fub_api_key` query parameter is **required on every request**.
* If it is absent the function returns `HTTP 401`.
* The key is used only within that single Lambda invocation to authenticate
  against the Follow Up Boss API; it is never logged or persisted.

> **Tip – keep your key out of shell history**  
> Store it in an environment variable locally:
> ```bash
> export FUB_API_KEY="your_key_here"
> curl -X POST "${LAMBDA_URL}?fub_api_key=${FUB_API_KEY}" ...
> ```

---

## Quick Start

```bash
# 1. Clone (if not already done)
git clone https://github.com/prowe/fub-mcp.git
cd fub-mcp

# 2. Build
sam build

# 3. Deploy (guided – answers prompts once; settings saved to samconfig.toml)
sam deploy --guided

# 4. Note the Lambda URL printed in Outputs, then test
LAMBDA_URL="<paste URL from deploy output>"
curl -s -X POST "${LAMBDA_URL}?fub_api_key=${FUB_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq .
```

---

## Step-by-Step Deployment

### 1  Configure AWS credentials

```bash
aws configure          # or use aws sso login / environment variables
aws sts get-caller-identity   # verify
```

### 2  Build the deployment package

```bash
sam build
```

SAM builds a self-contained Lambda zip under `.aws-sam/build/`.  It installs
all Python dependencies from `requirements.txt` into the package.

### 3  (First time) Deploy with guided mode

```bash
sam deploy --guided
```

You will be prompted for:

| Prompt | Suggested value |
|--------|-----------------|
| Stack Name | `fub-mcp` |
| AWS Region | `us-east-1` (or your preference) |
| Confirm changes before deploy | `Y` |
| Allow SAM CLI IAM role creation | `Y` |
| Disable rollback | `N` |
| Save arguments to samconfig.toml | `Y` |

Answers are saved to `samconfig.toml` so subsequent deploys only need
`sam deploy`.

### 4  Capture the Lambda URL

After a successful deploy, the URL appears in the **Outputs** section:

```
Outputs
-------
Key   FubMcpFunctionUrl
Value https://xxxxxxxxxxxxxxxx.lambda-url.us-east-1.on.aws/
```

Save it for use in the next section.

---

## Calling the Endpoint

Every request is an HTTP `POST` to the Lambda URL with:

* `fub_api_key=<key>` query parameter
* `Content-Type: application/json` header
* A JSON-RPC 2.0 body

### List available tools

```bash
curl -X POST "${LAMBDA_URL}?fub_api_key=${FUB_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Initialize / negotiate capabilities

```bash
curl -X POST "${LAMBDA_URL}?fub_api_key=${FUB_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "clientInfo": {"name": "my-client", "version": "1.0"}
    }
  }'
```

### Call a tool — list contacts

```bash
curl -X POST "${LAMBDA_URL}?fub_api_key=${FUB_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "get_people",
      "arguments": {"limit": 10}
    }
  }'
```

### Call a tool — create a contact

```bash
curl -X POST "${LAMBDA_URL}?fub_api_key=${FUB_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "create_person",
      "arguments": {
        "firstName": "Jane",
        "lastName": "Doe",
        "email": "jane.doe@example.com"
      }
    }
  }'
```

---

## MCP Client Configuration

To use this Lambda URL as an MCP server in an AI assistant, configure the
client to send HTTP requests instead of using stdio.  The exact configuration
varies by client.

### Generic HTTP MCP client

```json
{
  "mcpServers": {
    "follow-up-boss": {
      "url": "https://<your-lambda-url>/?fub_api_key=<YOUR_KEY>",
      "transport": "http"
    }
  }
}
```

---

## Environment & Configuration

The Lambda function honours the following **optional** environment variables.
Set them in the `Globals.Function.Environment.Variables` section of
`template.yaml` if needed.

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHONUNBUFFERED` | `1` | Already set; ensures logs stream to CloudWatch immediately |
| `RATE_LIMIT_DELAY_MS` | `50` | Milliseconds between Follow Up Boss API calls |
| `ENABLE_CACHING` | `True` | Enable in-process response caching |
| `CACHE_MAX_SIZE` | `1000` | Maximum cached entries per invocation |

> **Note** – `FUB_API_KEY` is intentionally absent from the Lambda environment.
> It must be supplied as the `fub_api_key` query parameter on every request.

---

## Updating the Function

After modifying code or dependencies:

```bash
sam build && sam deploy
```

SAM will show a changeset diff before applying changes.

---

## Tear Down

To remove all AWS resources created by this stack:

```bash
sam delete --stack-name fub-mcp
```

This deletes the Lambda function, IAM role, and Lambda URL.

---

## Troubleshooting

### `HTTP 401 – Missing required query parameter 'fub_api_key'`

The request URL must include `?fub_api_key=<your_key>`.

### `HTTP 400 – Invalid JSON body`

Verify the request body is valid JSON-RPC 2.0 and that the
`Content-Type: application/json` header is present.

### Tool returns an authentication error from Follow Up Boss

The provided `fub_api_key` was rejected by the Follow Up Boss API.  Verify
the key is correct and has not been revoked.

### Cold-start latency

The first invocation after a period of inactivity incurs a cold start
(~1–3 s for this function).  Subsequent invocations reuse the warm container
and are typically under 500 ms for lightweight tool calls.

### CloudWatch Logs

All function output is available in CloudWatch Logs:

```bash
sam logs --name FubMcpFunction --stack-name fub-mcp --tail
```

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| API key in URL (logged by load balancers / proxies) | Use HTTPS (enforced by Lambda URL); consider passing the key via a short-lived pre-signed URL or store it client-side only |
| Public Lambda URL | The `fub_api_key` is the only auth; treat it like a password |
| Additional access control | Set `AuthType: AWS_IAM` in `template.yaml` `FunctionUrlConfig` to require AWS SigV4 signatures in addition to the FUB key |
| Key rotation | Rotate your Follow Up Boss API key in the FUB dashboard; no Lambda redeployment is needed |
| CloudWatch log retention | By default Lambda logs are kept indefinitely; add a `LogGroup` resource with `RetentionInDays` if needed |
