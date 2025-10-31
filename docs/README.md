# Veil Documentation

## Overview

Veil is a Python library designed to mask sensitive personally identifiable information (PII) in text data. It helps protect privacy by detecting and masking various types of sensitive information including emails, phone numbers, credit cards, SSNs, IP addresses, and names.

## Installation

```bash
pip install veil
```

## Quick Start

```python
from veil import mask_text

# Simple usage
text = "Contact me at john@example.com or call 555-1234"
masked = mask_text(text)
print(masked)
# Output: Contact me at jo***@*******.com or call ***-1234
```

## Features

- **Multiple PII Types**: Supports email, phone, credit card, SSN, IP address, and name detection
- **Flexible Masking Strategies**: Choose from partial, full, or token-based masking
- **Custom Patterns**: Add your own patterns for domain-specific PII
- **Format Preservation**: Maintains readability while protecting sensitive data
- **Easy Integration**: Simple API for quick implementation

## Supported PII Types

| Type | Example | Masked (Partial) |
|------|---------|------------------|
| Email | john@example.com | jo***@*******.com |
| Phone (US) | (555) 123-4567 | (***) ***-4567 |
| Credit Card | 4532-1488-0343-6467 | ************6467 |
| SSN | 123-45-6789 | ***-**-6789 |
| IP Address | 192.168.1.1 | 19*.***.*.* |
| Name | John Smith | Jo** Sm*** |

## Masking Strategies

### Partial Masking (Default)
Shows part of the data for context while masking the sensitive portion.

```python
from veil import Masker
from veil.masker import MaskingStrategy

masker = Masker(strategy=MaskingStrategy.PARTIAL)
result = masker.mask("Email: test@example.com")
# Output: Email: te***@*******.com
```

### Full Masking
Completely masks all sensitive data.

```python
masker = Masker(strategy=MaskingStrategy.FULL)
result = masker.mask("Email: test@example.com")
# Output: Email: ******************
```

### Token Masking
Replaces sensitive data with labeled tokens.

```python
masker = Masker(strategy=MaskingStrategy.TOKEN)
result = masker.mask("Email: test@example.com")
# Output: Email: [EMAIL]
```

## Advanced Usage

### Selective PII Masking

Mask only specific types of PII:

```python
from veil import Masker, PIIPattern

masker = Masker()
text = "Email: test@example.com, Phone: 555-1234"

# Mask only emails
result = masker.mask(text, pii_types=[PIIPattern.EMAIL])
# Output: Email: te***@*******.com, Phone: 555-1234
```

### Custom Patterns

Add your own patterns for domain-specific data:

```python
masker = Masker()
masker.add_custom_pattern("employee_id", r"EMP-\d{6}")

text = "Employee ID: EMP-123456"
result = masker.mask(text)
# Output: Employee ID: EM********
```

### Custom Mask Character

Use a different character for masking:

```python
masker = Masker(mask_char="#")
result = masker.mask("Email: test@example.com")
# Output: Email: te###@#######.com
```

## API Reference

### `mask_text(text, pii_types=None, strategy='partial', mask_char='*')`

Convenience function for quick masking.

**Parameters:**
- `text` (str): Text to mask
- `pii_types` (List[PIIPattern], optional): List of PII types to mask
- `strategy` (str): Masking strategy ('partial', 'full', or 'token')
- `mask_char` (str): Character to use for masking

**Returns:** Masked text (str)

### `Masker` Class

Main class for PII masking with configurable options.

#### Constructor

```python
Masker(strategy='partial', mask_char='*', custom_patterns=None)
```

**Parameters:**
- `strategy` (str): Default masking strategy
- `mask_char` (str): Character to use for masking
- `custom_patterns` (Dict[str, Pattern], optional): Custom regex patterns

#### Methods

##### `mask(text, pii_types=None, strategy=None)`

Mask PII in the given text.

**Parameters:**
- `text` (str): Text to mask
- `pii_types` (List[PIIPattern], optional): List of PII types to mask
- `strategy` (str, optional): Override default strategy

**Returns:** Masked text (str)

##### `add_custom_pattern(name, pattern)`

Add a custom detection pattern.

**Parameters:**
- `name` (str): Name for the pattern
- `pattern` (str or Pattern): Regex pattern

## Best Practices

1. **Choose Appropriate Strategy**: Use partial masking for logs where context is needed, full masking for maximum privacy, and tokens for analytics.

2. **Test Thoroughly**: Verify masking with diverse input formats, especially for international data.

3. **Handle Edge Cases**: Be aware that pattern matching may not catch all variations of PII.

4. **Performance Considerations**: For large-scale processing, consider batch operations and pattern optimization.

5. **Security**: Remember that masking is not encryption - masked data cannot be recovered.

## Examples

See the [examples](../examples/) directory for more comprehensive examples:
- `basic_usage.py`: Complete examples demonstrating all features

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - see LICENSE file for details.
