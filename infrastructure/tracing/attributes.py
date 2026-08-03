"""
Span attribute helpers.

Provides helper functions for setting
span attributes following OpenTelemetry
Semantic Conventions, ensuring consistency
across all instrumentations.

Usage:
    from infrastructure.tracing.instrumentation.attributes import (
        set_http_attributes,
        set_db_attributes,
        set_messaging_attributes,
    )

    set_http_attributes(span, method="GET", route="/api/orders",
                       status_code=200, url="http://localhost/api/orders")
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .semantic import (
    # HTTP
    HTTP_METHOD,
    HTTP_ROUTE,
    HTTP_STATUS_CODE,
    HTTP_URL,
    HTTP_TARGET,
    HTTP_FLAVOR,
    HTTP_USER_AGENT,
    HTTP_REQUEST_CONTENT_LENGTH,
    HTTP_RESPONSE_CONTENT_LENGTH,
    HTTP_CLIENT_IP,
    HTTP_SERVER_NAME,
    HTTP_REQUEST_METHOD,
    HTTP_RESPONSE_STATUS_CODE,
    # URL
    URL_FULL,
    URL_PATH,
    URL_QUERY,
    URL_SCHEME,
    # Network
    NET_PEER_NAME,
    NET_PEER_PORT,
    NET_HOST_NAME,
    NET_HOST_PORT,
    NET_PROTOCOL_NAME,
    NET_TRANSPORT,
    # Database
    DB_SYSTEM,
    DB_NAME,
    DB_STATEMENT,
    DB_OPERATION,
    DB_USER,
    DB_CONNECTION_POOL_SIZE,
    DB_CONNECTION_POOL_IDLE,
    DB_CONNECTION_POOL_USED,
    DB_ROWS_RETURNED,
    DB_ROWS_AFFECTED,
    DB_RESPONSE_STATUS_CODE,
    # Messaging
    MESSAGING_SYSTEM,
    MESSAGING_DESTINATION_NAME,
    MESSAGING_DESTINATION_KIND,
    MESSAGING_OPERATION,
    MESSAGING_MESSAGE_ID,
    MESSAGING_MESSAGE_BODY_SIZE,
    MESSAGING_KAFKA_PARTITION,
    MESSAGING_KAFKA_OFFSET,
    MESSAGING_KAFKA_MESSAGE_KEY,
    MESSAGING_CONSUMER_GROUP,
    # RPC
    RPC_SYSTEM,
    RPC_SERVICE,
    RPC_METHOD,
    RPC_GRPC_STATUS_CODE,
    RPC_GRPC_STATUS_MESSAGE,
    # Exception
    EXCEPTION_TYPE,
    EXCEPTION_MESSAGE,
    EXCEPTION_STACKTRACE,
    EXCEPTION_ESCAPED,
    # Outcome
    OUTCOME,
    # ICYQuant
    ICY_STRATEGY_ID,
    ICY_ORDER_ID,
    ICY_ACCOUNT_ID,
    ICY_USER_ID,
    ICY_TENANT,
    ICY_REGION,
    ICY_SYMBOL,
    ICY_EXCHANGE,
    ICY_CORRELATION_ID,
    ICY_REQUEST_ID,
    ICY_OPERATION,
    ICY_COMPONENT,
    ICY_LATENCY_MS,
    ICY_RETRY_COUNT,
    ICY_ATTEMPT,
)


def set_http_server_attributes(
    span: Any,
    method: str,
    route: Optional[str] = None,
    status_code: Optional[int] = None,
    url: Optional[str] = None,
    target: Optional[str] = None,
    flavor: Optional[str] = None,
    user_agent: Optional[str] = None,
    request_content_length: Optional[int] = None,
    response_content_length: Optional[int] = None,
    client_ip: Optional[str] = None,
    server_name: Optional[str] = None,
) -> None:
    """
    Set HTTP server span attributes.

    Args:
        span: SpanModel instance.
        method: HTTP method (GET, POST, etc.).
        route: Request route pattern.
        status_code: Response status code.
        url: Full request URL.
        target: Request target path.
        flavor: HTTP version (1.1, 2.0).
        user_agent: User-Agent header value.
        request_content_length: Request body size.
        response_content_length: Response body size.
        client_ip: Client IP address.
        server_name: Server hostname.
    """

    attrs = {
        HTTP_METHOD: method,
    }

    if route:
        attrs[HTTP_ROUTE] = route
    if status_code is not None:
        attrs[HTTP_STATUS_CODE] = status_code
        attrs[OUTCOME] = (
            "success" if 200 <= status_code < 400 else "failure"
        )
    if url:
        attrs[HTTP_URL] = url
    if target:
        attrs[HTTP_TARGET] = target
    if flavor:
        attrs[HTTP_FLAVOR] = flavor
    if user_agent:
        attrs[HTTP_USER_AGENT] = user_agent
    if request_content_length is not None:
        attrs[HTTP_REQUEST_CONTENT_LENGTH] = request_content_length
    if response_content_length is not None:
        attrs[HTTP_RESPONSE_CONTENT_LENGTH] = response_content_length
    if client_ip:
        attrs[HTTP_CLIENT_IP] = client_ip
    if server_name:
        attrs[HTTP_SERVER_NAME] = server_name

    for key, value in attrs.items():
        span.add_attribute(key, value)


def set_http_client_attributes(
    span: Any,
    method: str,
    url: str,
    status_code: Optional[int] = None,
    target: Optional[str] = None,
    peer_name: Optional[str] = None,
    peer_port: Optional[int] = None,
    retry_count: int = 0,
) -> None:
    """
    Set HTTP client span attributes.

    Args:
        span: SpanModel instance.
        method: HTTP method.
        url: Request URL.
        status_code: Response status code.
        target: Request target path.
        peer_name: Remote hostname.
        peer_port: Remote port.
        retry_count: Number of retries.
    """

    attrs = {
        HTTP_METHOD: method,
        HTTP_URL: url,
    }

    if status_code is not None:
        attrs[HTTP_STATUS_CODE] = status_code
        attrs[OUTCOME] = (
            "success" if 200 <= status_code < 400 else "failure"
        )
    if target:
        attrs[HTTP_TARGET] = target
    if peer_name:
        attrs[NET_PEER_NAME] = peer_name
    if peer_port is not None:
        attrs[NET_PEER_PORT] = peer_port
    if retry_count > 0:
        attrs[ICY_RETRY_COUNT] = retry_count

    for key, value in attrs.items():
        span.add_attribute(key, value)


def set_db_attributes(
    span: Any,
    system: str,
    operation: str,
    name: Optional[str] = None,
    statement: Optional[str] = None,
    user: Optional[str] = None,
    rows_returned: Optional[int] = None,
    rows_affected: Optional[int] = None,
    status_code: Optional[str] = None,
) -> None:
    """
    Set database span attributes.

    Args:
        span: SpanModel instance.
        system: Database system (postgresql, mysql, redis).
        operation: Database operation (SELECT, INSERT, etc.).
        name: Database name.
        statement: SQL statement (sanitized).
        user: Database user.
        rows_returned: Number of rows returned.
        rows_affected: Number of rows affected.
        status_code: Database response status.
    """

    attrs = {
        DB_SYSTEM: system,
        DB_OPERATION: operation,
    }

    if name:
        attrs[DB_NAME] = name
    if statement:
        attrs[DB_STATEMENT] = statement
    if user:
        attrs[DB_USER] = user
    if rows_returned is not None:
        attrs[DB_ROWS_RETURNED] = rows_returned
    if rows_affected is not None:
        attrs[DB_ROWS_AFFECTED] = rows_affected
    if status_code:
        attrs[DB_RESPONSE_STATUS_CODE] = status_code

    for key, value in attrs.items():
        span.add_attribute(key, value)


def set_db_connection_pool_attributes(
    span: Any,
    pool_name: str,
    pool_size: int,
    pool_idle: int,
    pool_used: int,
) -> None:
    """
    Set database connection pool attributes.

    Args:
        span: SpanModel instance.
        pool_name: Connection pool name.
        pool_size: Total pool size.
        pool_idle: Idle connections.
        pool_used: Active connections.
    """

    span.add_attribute(DB_CONNECTION_POOL_SIZE, pool_size)
    span.add_attribute(DB_CONNECTION_POOL_IDLE, pool_idle)
    span.add_attribute(DB_CONNECTION_POOL_USED, pool_used)


def set_messaging_producer_attributes(
    span: Any,
    system: str,
    destination: str,
    operation: str = "send",
    message_id: Optional[str] = None,
    message_body_size: Optional[int] = None,
    kafka_partition: Optional[int] = None,
    kafka_offset: Optional[int] = None,
    kafka_message_key: Optional[str] = None,
) -> None:
    """
    Set messaging producer span attributes.

    Args:
        span: SpanModel instance.
        system: Messaging system (kafka, rabbitmq).
        destination: Topic/queue name.
        operation: Messaging operation.
        message_id: Message identifier.
        message_body_size: Message body size in bytes.
        kafka_partition: Kafka partition number.
        kafka_offset: Kafka offset.
        kafka_message_key: Kafka message key.
    """

    attrs = {
        MESSAGING_SYSTEM: system,
        MESSAGING_DESTINATION_NAME: destination,
        MESSAGING_OPERATION: operation,
    }

    if message_id:
        attrs[MESSAGING_MESSAGE_ID] = message_id
    if message_body_size is not None:
        attrs[MESSAGING_MESSAGE_BODY_SIZE] = message_body_size
    if kafka_partition is not None:
        attrs[MESSAGING_KAFKA_PARTITION] = kafka_partition
    if kafka_offset is not None:
        attrs[MESSAGING_KAFKA_OFFSET] = kafka_offset
    if kafka_message_key:
        attrs[MESSAGING_KAFKA_MESSAGE_KEY] = kafka_message_key

    for key, value in attrs.items():
        span.add_attribute(key, value)


def set_messaging_consumer_attributes(
    span: Any,
    system: str,
    destination: str,
    operation: str = "process",
    consumer_group: Optional[str] = None,
    message_id: Optional[str] = None,
    kafka_partition: Optional[int] = None,
    kafka_offset: Optional[int] = None,
) -> None:
    """
    Set messaging consumer span attributes.

    Args:
        span: SpanModel instance.
        system: Messaging system.
        destination: Topic/queue name.
        operation: Messaging operation.
        consumer_group: Consumer group name.
        message_id: Message identifier.
        kafka_partition: Kafka partition.
        kafka_offset: Kafka offset.
    """

    attrs = {
        MESSAGING_SYSTEM: system,
        MESSAGING_DESTINATION_NAME: destination,
        MESSAGING_OPERATION: operation,
    }

    if consumer_group:
        attrs[MESSAGING_CONSUMER_GROUP] = consumer_group
    if message_id:
        attrs[MESSAGING_MESSAGE_ID] = message_id
    if kafka_partition is not None:
        attrs[MESSAGING_KAFKA_PARTITION] = kafka_partition
    if kafka_offset is not None:
        attrs[MESSAGING_KAFKA_OFFSET] = kafka_offset

    for key, value in attrs.items():
        span.add_attribute(key, value)


def set_rpc_attributes(
    span: Any,
    system: str,
    service: str,
    method: str,
    status_code: Optional[int] = None,
    status_message: Optional[str] = None,
) -> None:
    """
    Set RPC/gRPC span attributes.

    Args:
        span: SpanModel instance.
        system: RPC system (grpc, jsonrpc).
        service: Service name.
        method: Method name.
        status_code: RPC status code.
        status_message: Status message.
    """

    span.add_attribute(RPC_SYSTEM, system)
    span.add_attribute(RPC_SERVICE, service)
    span.add_attribute(RPC_METHOD, method)

    if status_code is not None:
        span.add_attribute(RPC_GRPC_STATUS_CODE, status_code)
        span.add_attribute(
            OUTCOME, "success" if status_code == 0 else "failure"
        )
    if status_message:
        span.add_attribute(RPC_GRPC_STATUS_MESSAGE, status_message)


def set_exception_attributes(
    span: Any,
    exc: BaseException,
    escaped: bool = False,
) -> None:
    """
    Set exception span attributes.

    Args:
        span: SpanModel instance.
        exc: Exception instance.
        escaped: Whether the exception escaped the span.
    """

    span.add_attribute(EXCEPTION_TYPE, type(exc).__name__)
    span.add_attribute(EXCEPTION_MESSAGE, str(exc))
    span.add_attribute(EXCEPTION_ESCAPED, escaped)

    import traceback
    tb = traceback.format_exc()
    if tb:
        span.add_attribute(EXCEPTION_STACKTRACE, tb)


def set_business_attributes(
    span: Any,
    strategy_id: Optional[str] = None,
    order_id: Optional[str] = None,
    account_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tenant: Optional[str] = None,
    region: Optional[str] = None,
    symbol: Optional[str] = None,
    exchange: Optional[str] = None,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    operation: Optional[str] = None,
    component: Optional[str] = None,
) -> None:
    """
    Set ICYQuant business span attributes.

    Args:
        span: SpanModel instance.
        strategy_id: Strategy identifier.
        order_id: Order identifier.
        account_id: Account identifier.
        user_id: User identifier.
        tenant: Tenant name.
        region: Deployment region.
        symbol: Trading symbol.
        exchange: Exchange name.
        correlation_id: Correlation ID.
        request_id: Request ID.
        operation: Business operation.
        component: Component name.
    """

    attrs = {}

    if strategy_id:
        attrs[ICY_STRATEGY_ID] = strategy_id
    if order_id:
        attrs[ICY_ORDER_ID] = order_id
    if account_id:
        attrs[ICY_ACCOUNT_ID] = account_id
    if user_id:
        attrs[ICY_USER_ID] = user_id
    if tenant:
        attrs[ICY_TENANT] = tenant
    if region:
        attrs[ICY_REGION] = region
    if symbol:
        attrs[ICY_SYMBOL] = symbol
    if exchange:
        attrs[ICY_EXCHANGE] = exchange
    if correlation_id:
        attrs[ICY_CORRELATION_ID] = correlation_id
    if request_id:
        attrs[ICY_REQUEST_ID] = request_id
    if operation:
        attrs[ICY_OPERATION] = operation
    if component:
        attrs[ICY_COMPONENT] = component

    for key, value in attrs.items():
        span.add_attribute(key, value)


def set_latency_attributes(
    span: Any,
    latency_ms: float,
    retry_count: int = 0,
    attempt: int = 1,
) -> None:
    """
    Set latency and retry attributes.

    Args:
        span: SpanModel instance.
        latency_ms: Latency in milliseconds.
        retry_count: Number of retries.
        attempt: Current attempt number.
    """

    span.add_attribute(ICY_LATENCY_MS, latency_ms)
    if retry_count > 0:
        span.add_attribute(ICY_RETRY_COUNT, retry_count)
    if attempt > 1:
        span.add_attribute(ICY_ATTEMPT, attempt)


def set_network_attributes(
    span: Any,
    peer_name: Optional[str] = None,
    peer_port: Optional[int] = None,
    host_name: Optional[str] = None,
    host_port: Optional[int] = None,
    protocol_name: Optional[str] = None,
    transport: Optional[str] = None,
) -> None:
    """
    Set network span attributes.

    Args:
        span: SpanModel instance.
        peer_name: Remote hostname.
        peer_port: Remote port.
        host_name: Local hostname.
        host_port: Local port.
        protocol_name: Protocol name.
        transport: Transport type.
    """

    if peer_name:
        span.add_attribute(NET_PEER_NAME, peer_name)
    if peer_port is not None:
        span.add_attribute(NET_PEER_PORT, peer_port)
    if host_name:
        span.add_attribute(NET_HOST_NAME, host_name)
    if host_port is not None:
        span.add_attribute(NET_HOST_PORT, host_port)
    if protocol_name:
        span.add_attribute(NET_PROTOCOL_NAME, protocol_name)
    if transport:
        span.add_attribute(NET_TRANSPORT, transport)
