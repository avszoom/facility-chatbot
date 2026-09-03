"""AWS tool adapter boundaries.

- `S3KnowledgeProvider`: S3/OpenSearch/Bedrock Knowledge Bases
- `SiteWiseBuildingProvider`: IoT SiteWise or TwinMaker reads and guarded commands
- `SnsNotificationProvider`: SNS/SES/Amazon Connect notifications
- `GatewayWorkOrderProvider`: AgentCore Gateway backed CMMS operation

Each implementation must satisfy the protocols in `backend.app.tools.ports`.
"""
