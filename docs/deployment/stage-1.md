# Stage 1: single-host AWS deployment

This release hosts the ticket product on one EC2 instance and delegates bounded
Strands coordinator/specialist inference to AgentCore Runtime. It is not an SQS,
DynamoDB, or real BMS/CMMS deployment. Building telemetry, physical
repairs, and outbound resident messages remain simulated. Reasoning uses Strands
with Amazon Bedrock, not an OpenAI key.

## Components

- Caddy: HTTPS, reviewer authentication, built React UI, and reverse proxy.
- Operations service: loopback-only FastAPI plus three independent worker processes.
- Building world: independent continuously running sensor simulator; no automatic tickets.
- SQLite WAL: durable queue, versioned workflow state and domain records on encrypted EBS.
- AgentCore Runtime: isolated Strands inference sessions backed by Amazon Nova Pro on Bedrock.
- IAM instance role: temporary credentials for AgentCore and Systems Manager.
- systemd: service supervision and local journal logs. CloudWatch export is a later adapter.

## Provisioning and release

1. Create a small Linux EC2 host in the chosen subnet, encrypted storage, IMDSv2,
   and a dedicated instance role. Attach Systems Manager permissions. Use Standard
   CPU credit mode if avoiding surplus-credit charges is more important than burst capacity.
2. Render the scoped policies in `deploy/`, deploy `agentcore/main.py` with
   `scripts/deploy_agentcore.py`, and allow the EC2 role to invoke only that runtime.
   The US inference profile may route to its listed US regions. Test actual invocation:
   a model catalog entry does not prove access or entitlement.
3. Install Python 3.11 and its venv/pip packages, create the `buildingops` system
   user and `/var/lib/buildingops` owned by that user, and create a root-owned
   `/opt/buildingops/venv`. Install an official Caddy binary after checksum verification.
4. Run local tests, a Python 3.11 compile check, and `npm --prefix frontend run build`.
5. Run `scripts/deploy_stage1.py --instance INSTANCE_ID --profile PROFILE --host HOSTNAME`.
   It transfers only an allowlisted release using Systems Manager, checks SHA-256,
   installs dependencies, and starts supervised services. It does not seed tickets.
6. Open only ports 80/443 after explicit public-access approval. Keep SSH and port
   8000 blocked. A hostname and publicly trusted certificate are required before
   sharing reviewer credentials. The EC2 public IPv4 can change after stop/start;
   update DNS and certificate configuration if that happens.
7. Verify authenticated HTTPS, rejected unauthenticated requests, model invocation,
   live sensors, three case outcomes, queue recovery, and truthful dashboard metrics.

Reviewer credentials are generated on the server in
`/etc/buildingops/reviewer-credentials` (root-only). Never commit them or put them
in a deployment command. `application.env` contains cloud configuration but no
OpenAI key or static AWS credentials. Cloud mode rejects non-Bedrock providers.

## Operations

Service names:

- `buildingops@scripts.run_operations`
- `buildingops@backend.app.scheduling.local_simulator`
- `caddy`

Use Systems Manager to inspect `systemctl` status and `journalctl` logs. Use the
SQLite backup API for consistent backups, rather than copying a live WAL database.
The database is `/var/lib/buildingops/buildingops.db`. Retaining the EBS volume on
termination protects against accidental instance removal, but storage charges
continue and this is not a substitute for an off-host backup.

An install command succeeding is not acceptance: the services must stay healthy
and a real Bedrock-backed workflow must finish. Failed model calls are retried or
escalated, never presented as successful deterministic substitute execution.

## Public repository hygiene

Run `python scripts/public_release_check.py` and inspect the exact staged diff.
The check examines source and reachable Git history without printing matching
secret values. It is heuristic, not a guarantee of absence of private information.

Never stage `.env*` secrets, `.deployment/`, databases, videos/recordings, private
screenshots, AWS account-specific policies, or reviewer passwords. Generic
templates in `deploy/` are suitable for publication. Local deployment receipts
are kept in ignored `.deployment/` and recording artifacts in ignored `artifacts/`.

Before publishing, recheck the license, setup instructions, and reuse disclosure.
Public GitHub publication and Devpost submission are separate from EC2 installation.
