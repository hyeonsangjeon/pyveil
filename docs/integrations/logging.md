# Logging Integration

Install pyveil before logs leave the process.

```python
import logging

from pyveil import Veil
from pyveil.integrations import PyVeilLogFilter

veil = Veil.high(secret=b"log-secret", scope="service/run")

handler = logging.StreamHandler()
handler.addFilter(PyVeilLogFilter(veil, channel="log.record"))

logger = logging.getLogger("app")
logger.addHandler(handler)
logger.warning("user email is alice@example.com")
```

## Notes

- Use `HIGH` for logs sent outside the runtime.
- Use `LOW` only when a human needs a legacy-style masked preview.
- Frameworks may log request bodies or exceptions before filters run; install filters as early as possible.
