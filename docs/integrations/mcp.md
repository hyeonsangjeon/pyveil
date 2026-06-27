# MCP Integration

pyveil should run before MCP tool results or resources become model context.

## Tool Results

```python
from pyveil import Veil
from pyveil.integrations import redact_tool_result

veil = Veil.high(secret=b"tenant-secret", scope="tenant/session")

async def get_customer(customer_id: str):
    raw = await crm.fetch_customer(customer_id)
    return redact_tool_result(raw, veil=veil)
```

## Resources

```python
from pyveil import Veil
from pyveil.integrations import redact_resource

veil = Veil.high(secret=b"tenant-secret")

async def read_customer_resource(uri: str):
    raw_resource = await crm_resource(uri)
    return redact_resource(raw_resource, veil=veil)
```

## Policy

Use `HIGH` for MCP content by default. MCP resources may include files, logs, database records, API responses, and other sensitive context.

```python
safe = veil.redact_data(raw_resource, channel="mcp.resource.content")
```

Do not expose a reversible unmasking tool to the model.
