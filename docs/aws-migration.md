# Local-to-AWS replacement map

The domain models, state machine, policy rules, action gateway, ticket service, workflow service, API schemas, and React UI remain unchanged. AWS work is adapter replacement at `backend/app/system.py`.

| Capability | Local implementation | AWS replacement | Contract preserved |
| --- | --- | --- | --- |
| Building-world event generation | Durable `BuildingSimulationService` + independent simulator process | EventBridge Scheduler + Lambda, IoT Core rules, or a synthetic test-event producer | simulation state + ticket intake boundary |
| Agent reasoning | Strands + OpenAI Responses API in the Operations worker (`OpenAIStrandsRuntime`) | The same Strands agent in Bedrock AgentCore Runtime with a Bedrock model adapter | `AgentRuntime.decide → AgentDecision` |
| Durable tickets/audit | SQLite WAL tables | DynamoDB single table + conditional writes | `OperationsRepository` |
| Cross-service pub/sub | SQLite message and subscription-delivery tables with at-least-once delivery | EventBridge custom bus or SNS topics fan-out to SQS subscriptions | `MessageBusPort` + stable message envelope |
| Delayed/resumable jobs | Transactional SQLite workflow outbox + configurable subscriber worker pool | EventBridge Scheduler → EventBridge/SQS/Lambda | `WorkflowJob` + `WorkflowService` |
| Retry and dead letters | Leased delivery, exponential retry, terminal `dead_letter` state | SQS visibility timeout, redrive policy, and DLQ | delivery attempts + correlation/idempotency keys |
| Workflow checkpoints | Versioned `workflow_states` record for every ticket | DynamoDB workflow-state item with conditional version updates | `WorkflowState` |
| Knowledge | Versioned local JSON | S3 + OpenSearch or Bedrock Knowledge Bases | `KnowledgePort.search` |
| Telemetry and commands | 60-sensor live twin, rolling history, anomaly injection, and safe commands | IoT SiteWise/TwinMaker + IoT Core rules and command adapter | `BuildingPort` |
| Work orders | Local CMMS simulator | AgentCore Gateway or direct CMMS API | `WorkOrderPort` |
| Resident updates | Ticket timeline event | SNS/SES/Amazon Connect | `NotificationPort` |
| Agent-live aggregation | `/api/operations/live` over durable ticket/event state | DynamoDB streams/materialized metrics + API Gateway | live-operations response schema |
| Live UI updates | Process-local SSE fanout + polling | API Gateway WebSocket + EventBridge/SNS | event envelope |
| API | Local FastAPI/Uvicorn | ECS Fargate or Lambda Web Adapter | OpenAPI routes and schemas |
| Web UI | Vite dev/static build | S3 + CloudFront or Amplify Hosting | `VITE_API_BASE` only |
| Tracing | Correlation IDs in event log | AgentCore observability + CloudWatch/OpenTelemetry | ticket/correlation IDs |
| Secrets | `.env` (ignored) | Secrets Manager/SSM + IAM roles | settings names, no embedded credentials |

## Migration order

1. Package the same Strands tool loop for AgentCore, switch the model adapter from OpenAI Responses to Bedrock, and prove one typed invocation plus trace.
2. Replace `SQLiteDurablePubSub` with EventBridge/SNS plus SQS subscriptions while retaining SQLite ticket persistence for a controlled split test.
3. Move building-world scheduling to EventBridge Scheduler and feed simulated or real IoT events through the same ticket-intake boundary.
4. Move persistence to DynamoDB and run the same lifecycle/idempotency tests.
5. Replace read tools, then write tools one at a time; rerun policy tests after every swap.
6. Host the API/UI last. Change environment configuration, not service logic.

The local `/api/system` endpoint identifies active adapters, preventing a demo from implying AWS components are active when they are not.
