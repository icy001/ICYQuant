"""
OpenTelemetry Semantic Conventions.

Defines attribute keys following the
OpenTelemetry Semantic Conventions specification,
ensuring all instrumentations produce spans
that are compatible with observability
platforms like Jaeger, Tempo, Grafana,
and Datadog.

Reference: https://opentelemetry.io/docs/specs/semconv/
"""

from __future__ import annotations

# ── General ──
SERVICE_NAME = "service.name"
SERVICE_VERSION = "service.version"
SERVICE_INSTANCE_ID = "service.instance.id"
SERVICE_NAMESPACE = "service.namespace"
DEPLOYMENT_ENVIRONMENT = "deployment.environment"

# �─ Host ──
HOST_NAME = "host.name"
HOST_ARCH = "host.arch"
HOST_IP = "host.ip"

# ── Process ──
PROCESS_PID = "process.pid"
PROCESS_EXECUTABLE_NAME = "process.executable.name"
PROCESS_COMMAND = "process.command"

# ── Network ──
NET_PEER_NAME = "net.peer.name"
NET_PEER_PORT = "net.peer.port"
NET_HOST_NAME = "net.host.name"
NET_HOST_PORT = "net.host.port"
NET_PROTOCOL_NAME = "net.protocol.name"
NET_PROTOCOL_VERSION = "net.protocol.version"
NET_TRANSPORT = "net.transport"

# ── HTTP ──
HTTP_METHOD = "http.method"
HTTP_ROUTE = "http.route"
HTTP_STATUS_CODE = "http.status_code"
HTTP_FLAVOR = "http.flavor"
HTTP_USER_AGENT = "http.user_agent"
HTTP_REQUEST_CONTENT_LENGTH = "http.request_content_length"
HTTP_RESPONSE_CONTENT_LENGTH = "http.response_content_length"
HTTP_CLIENT_IP = "http.client_ip"
HTTP_SERVER_NAME = "http.server_name"
HTTP_TARGET = "http.target"
HTTP_URL = "http.url"

# ── HTTP Request/Response ──
HTTP_REQUEST_METHOD = "http.request.method"
HTTP_RESPONSE_STATUS_CODE = "http.response.status_code"
HTTP_REQUEST_METHOD_ORIGINAL = "http.request.method_original"

# ── URL ──
URL_FULL = "url.full"
URL_PATH = "url.path"
URL_QUERY = "url.query"
URL_SCHEME = "url.scheme"
URL_FRAGMENT = "url.fragment"
URL_DOMAIN = "url.domain"

# ── Server/Client Request ──
SERVER_REQUEST_ID = "server.request.id"
SERVER_SOCKET_ADDRESS = "server.socket.address"
SERVER_SOCKET_PORT = "server.socket.port"
CLIENT_SOCKET_ADDRESS = "client.socket.address"
CLIENT_SOCKET_PORT = "client.socket.port"

# ── Database ──
DB_SYSTEM = "db.system"
DB_NAME = "db.name"
DB_STATEMENT = "db.statement"
DB_OPERATION = "db.operation"
DB_USER = "db.user"
DB_CONNECTION_STRING = "db.connection_string"
DB_CONNECTION_POOL_NAME = "db.connection_pool.name"
DB_CONNECTION_POOL_SIZE = "db.connection_pool.size"
DB_CONNECTION_POOL_IDLE = "db.connection_pool.idle"
DB_CONNECTION_POOL_USED = "db.connection_pool.used"
DB_CONNECTION_POOL_MAX = "db.connection_pool.max"
DB_ROWS_RETURNED = "db.rows_returned"
DB_ROWS_AFFECTED = "db.rows_affected"
DB_RESPONSE_STATUS_CODE = "db.response.status_code"

# ── Database System Values ──
DB_SYSTEM_POSTGRESQL = "postgresql"
DB_SYSTEM_MYSQL = "mysql"
DB_SYSTEM_SQLITE = "sqlite"
DB_SYSTEM_REDIS = "redis"
DB_SYSTEM_MONGODB = "mongodb"
DB_SYSTEM_ELASTICSEARCH = "elasticsearch"
DB_SYSTEM_CASSANDRA = "cassandra"

# ── Messaging ──
MESSAGING_SYSTEM = "messaging.system"
MESSAGING_DESTINATION_NAME = "messaging.destination.name"
MESSAGING_DESTINATION_KIND = "messaging.destination.kind"
MESSAGING_OPERATION = "messaging.operation"
MESSAGING_MESSAGE_ID = "messaging.message.id"
MESSAGING_MESSAGE_BODY_SIZE = "messaging.message.body.size"
MESSAGING_MESSAGE_ATTRIBUTES = "messaging.message.attributes"
MESSAGING_KAFKA_PARTITION = "messaging.kafka.partition"
MESSAGING_KAFKA_OFFSET = "messaging.kafka.offset"
MESSAGING_KAFKA_OFFSET_OLDEST = "messaging.kafka.offset.oldest"
MESSAGING_KAFKA_OFFSET_LATEST = "messaging.kafka.offset.latest"
MESSAGING_KAFKA_MESSAGE_KEY = "messaging.kafka.message.key"
MESSAGING_KAFKA_TOMBSTONE = "messaging.kafka.tombstone"
MESSAGING_CONSUMER_GROUP = "messaging.consumer.group.name"
MESSAGING_CONVERSATION_ID = "messaging.message.conversation_id"

# ── Messaging System Values ──
MESSAGING_SYSTEM_KAFKA = "kafka"
MESSAGING_SYSTEM_RABBITMQ = "rabbitmq"
MESSAGING_SYSTEM_ACTIVEMQ = "activemq"
MESSAGING_SYSTEM_AZURE_SERVICE_BUS = "azureservicebus"
MESSAGING_SYSTEM_GCP_PUBSUB = "gcp_pubsub"

# ── RPC / gRPC ──
RPC_SYSTEM = "rpc.system"
RPC_SERVICE = "rpc.service"
RPC_METHOD = "rpc.method"
RPC_GRPC_STATUS_CODE = "rpc.grpc.status_code"
RPC_GRPC_STATUS_MESSAGE = "rpc.grpc.status_message"
RPC_GRPC_OWNER = "rpc.grpc.owner"
RPC_MESSAGE_TYPE = "rpc.message.type"
RPC_MESSAGE_ID = "rpc.message.id"
RPC_MESSAGE_COMPRESSED_SIZE = "rpc.message.compressed_size"
RPC_MESSAGE_UNCOMPRESSED_SIZE = "rpc.message.uncompressed_size"

# ── RPC System Values ──
RPC_SYSTEM_GRPC = "grpc"
RPC_SYSTEM_JSONRPC = "jsonrpc"
RPC_SYSTEM_DUBBO = "dubbo"

# ── Exception ──
EXCEPTION_TYPE = "exception.type"
EXCEPTION_MESSAGE = "exception.message"
EXCEPTION_STACKTRACE = "exception.stacktrace"
EXCEPTION_ESCAPED = "exception.escaped"

# ── Outcome ──
OUTCOME = "outcome"
OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"
OUTCOME_SKIPPED = "skipped"

# ── Feature Flag ──
FEATURE_FLAG_KEY = "feature_flag.key"
FEATURE_FLAG_PROVIDER_NAME = "feature_flag.provider_name"
FEATURE_FLAG_VARIANT = "feature_flag.variant"
FEATURE_FLAG_SET = "feature_flag.set"

# ── Gen AI ──
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GEN_AI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_TOP_P = "gen_ai.request.top_p"
GEN_AI_REQUEST_FREQUENCY_PENALTY = "gen_ai.request.frequency_penalty"
GEN_AI_REQUEST_PRESENCE_PENALTY = "gen_ai.request.presence_penalty"
GEN_AI_REQUEST_STOP_SEQUENCES = "gen_ai.request.stop_sequences"
GEN_AI_REQUEST_SEED = "gen_ai.request.seed"
GEN_AI_REQUEST_ENCODING_FORMATS = "gen_ai.request.encoding_formats"
GEN_AI_RESPONSE_ID = "gen_ai.response.id"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
GEN_AI_RESPONSE_FIRST_TOKEN_TIME = "gen_ai.response.first_token_time"
GEN_AI_RESPONSE_OUTPUT_TOKENS = "gen_ai.response.output_tokens"
GEN_AI_RESPONSE_INPUT_TOKENS = "gen_ai.response.input_tokens"

# ── Thread ──
THREAD_ID = "thread.id"
THREAD_NAME = "thread.name"
THREAD_SPAWN_ID = "thread.spawn_count"

# ── ICYQuant Business Attributes ──
ICY_STRATEGY_ID = "icyquant.strategy.id"
ICY_STRATEGY_NAME = "icyquant.strategy.name"
ICY_ORDER_ID = "icyquant.order.id"
ICY_ORDER_TYPE = "icyquant.order.type"
ICY_ORDER_STATUS = "icyquant.order.status"
ICY_ACCOUNT_ID = "icyquant.account.id"
ICY_ACCOUNT_TYPE = "icyquant.account.type"
ICY_USER_ID = "icyquant.user.id"
ICY_TENANT = "icyquant.tenant"
ICY_REGION = "icyquant.region"
ICY_SYMBOL = "icyquant.symbol"
ICY_EXCHANGE = "icyquant.exchange"
ICY_SOURCE = "icyquant.source"
ICY_SESSION_ID = "icyquant.session.id"
ICY_REQUEST_ID = "icyquant.request.id"
ICY_CORRELATION_ID = "icyquant.correlation.id"
ICY_OPERATION = "icyquant.operation"
ICY_COMPONENT = "icyquant.component"
ICY_TRADING_SESSION = "icyquant.trading_session"
ICY_ALGO_ID = "icyquant.algo.id"
ICY_RISK_LEVEL = "icyquant.risk.level"
ICY_LATENCY_MS = "icyquant.latency.ms"
ICY_RETRY_COUNT = "icyquant.retry.count"
ICY_ATTEMPT = "icyquant.attempt"


def get_semantic_attributes() -> dict:
    """
    Get all semantic attribute definitions.

    Returns:
        Dictionary of all semantic attribute keys.
    """

    return {
        "general": {
            "service.name": SERVICE_NAME,
            "service.version": SERVICE_VERSION,
            "service.instance.id": SERVICE_INSTANCE_ID,
            "service.namespace": SERVICE_NAMESPACE,
            "deployment.environment": DEPLOYMENT_ENVIRONMENT,
        },
        "network": {
            "net.peer.name": NET_PEER_NAME,
            "net.peer.port": NET_PEER_PORT,
            "net.host.name": NET_HOST_NAME,
            "net.host.port": NET_HOST_PORT,
        },
        "http": {
            "http.method": HTTP_METHOD,
            "http.route": HTTP_ROUTE,
            "http.status_code": HTTP_STATUS_CODE,
            "http.url": HTTP_URL,
            "http.target": HTTP_TARGET,
        },
        "database": {
            "db.system": DB_SYSTEM,
            "db.name": DB_NAME,
            "db.statement": DB_STATEMENT,
            "db.operation": DB_OPERATION,
            "db.user": DB_USER,
        },
        "messaging": {
            "messaging.system": MESSAGING_SYSTEM,
            "messaging.destination.name": MESSAGING_DESTINATION_NAME,
            "messaging.operation": MESSAGING_OPERATION,
            "messaging.message.id": MESSAGING_MESSAGE_ID,
        },
        "rpc": {
            "rpc.system": RPC_SYSTEM,
            "rpc.service": RPC_SERVICE,
            "rpc.method": RPC_METHOD,
            "rpc.grpc.status_code": RPC_GRPC_STATUS_CODE,
        },
        "exception": {
            "exception.type": EXCEPTION_TYPE,
            "exception.message": EXCEPTION_MESSAGE,
            "exception.stacktrace": EXCEPTION_STACKTRACE,
            "exception.escaped": EXCEPTION_ESCAPED,
        },
        "icyquant": {
            "icyquant.strategy.id": ICY_STRATEGY_ID,
            "icyquant.order.id": ICY_ORDER_ID,
            "icyquant.account.id": ICY_ACCOUNT_ID,
            "icyquant.user.id": ICY_USER_ID,
            "icyquant.tenant": ICY_TENANT,
            "icyquant.correlation.id": ICY_CORRELATION_ID,
        },
    }
