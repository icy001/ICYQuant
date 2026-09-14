"""Pydantic request/response schemas for the API gateway.

The API never returns internal domain objects directly (§12): every
response is an explicit model, so a domain refactor cannot silently
break a consumer.
"""
