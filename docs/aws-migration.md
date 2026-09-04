# Local-to-AWS replacement map

The domain models, state machine, policy rules, action gateway, ticket service, workflow service, API schemas, and React UI remain unchanged. AWS work is adapter replacement at `backend/app/system.py`.

| Capability | Local implementation | AWS replacement | Contract preserved |
| --- | --- | --- | --- |
| Building-world event generation | Durable `BuildingSimulationService` + independent simulator process | EventBridge Scheduler + Lambda, IoT Core rules, or a synthetic test-event producer | simulation state + ticket intake boundary |
| Agent reasoning | `StrandsAgentRuntime` in API/worker process | Strands in Bedrock AgentCore Runtime | `AgentRuntime.decide → AgentDecision` |
| Durable tickets/audit | SQLite WAL tables | DynamoDB single table + conditional writes | `OperationsRepository` |
| Delayed/resumable jobs | Configurable SQLite leased-job worker pool | EventBridge Scheduler → SQS/Lambda, DLQ | `WorkflowJob` + `WorkflowService` |
| Knowledge | Versioned local JSON | S3 + OpenSearch or Bedrock Knowledge Bases | `KnowledgePort.search` |
| Telemetry and commands | Seeded building simulator | IoT SiteWise/TwinMaker + IoT Core command adapter | `BuildingPort` |
| Work orders | Local CMMS simulator | AgentCore Gateway or direct CMMS API | `WorkOrderPort` |
| Occupant updates | Ticket timeline event | SNS/SES/Amazon Connect | `NotificationPort` |
| Agent-live aggregation | `/api/operations/live` over durable ticket/event state | DynamoDB streams/materialized metrics + API Gateway | live-operations response schema |
| Live UI updates | Process-local SSE fanout + polling | API Gateway WebSocket + EventBridge/SNS | event envelope |
| API | Local FastAPI/Uvicorn | ECS Fargate or Lambda Web Adapter | OpenAPI routes and schemas |
| Web UI | Vite dev/static build | S3 + CloudFront or Amplify Hosting | `VITE_API_BASE` only |
| Tracing | Correlation IDs in event log | AgentCore observability + CloudWatch/OpenTelemetry | ticket/correlation IDs |
| Secrets | `.env` (ignored) | Secrets Manager/SSM + IAM roles | settings names, no embedded credentials |

## Migration order

1. Package only `StrandsAgentRuntime` for AgentCore and prove one typed invocation plus trace.
2. Replace the operations job delivery adapter with SQS/Lambda while retaining SQLite for a controlled split test.
3. Move building-world scheduling to EventBridge Scheduler and feed simulated or real IoT events through the same ticket-intake boundary.
4. Move persistence to DynamoDB and run the same lifecycle/idempotency tests.
5. Replace read tools, then write tools one at a time; rerun policy tests after every swap.
6. Host the API/UI last. Change environment configuration, not service logic.

The local `/api/system` endpoint identifies active adapters, preventing a demo from implying AWS components are active when they are not.
