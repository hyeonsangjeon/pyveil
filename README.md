# veil 🎭

A Python library for masking sensitive data (PII) - emails, phones, names, and more

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Overview

Veil helps protect sensitive information by detecting and masking various types of personally identifiable information (PII) in text data. Whether you're handling logs, user data, or any text containing sensitive information, Veil provides flexible and easy-to-use tools to protect privacy.

## Features

- 🔒 **Multiple PII Types**: Emails, phone numbers, credit cards, SSNs, IP addresses, names
- 🎨 **Flexible Strategies**: Partial, full, or token-based masking
- 🔧 **Customizable**: Add your own patterns and configure masking behavior
- ⚡ **Easy to Use**: Simple API for quick integration
- 🌍 **Format Preservation**: Maintains readability while protecting data

## Installation

```bash
pip install veil
```

## Quick Start

```python
from veil import mask_text

# Simple usage
text = "Contact me at john@example.com or call (555) 123-4567"
masked = mask_text(text)
print(masked)
# Output: Contact me at jo***@*******.com or call (***) ***-4567
```

## Usage Examples

### Basic Masking

```python
from veil import Masker, PIIPattern
from veil.masker import MaskingStrategy

# Create a masker instance
masker = Masker(strategy=MaskingStrategy.PARTIAL)

text = "Email: admin@company.com, Phone: 555-9876, Card: 4532-1488-0343-6467"
masked = masker.mask(text)
print(masked)
```

### Different Masking Strategies

```python
# Partial masking (default) - shows context
masker = Masker(strategy=MaskingStrategy.PARTIAL)
print(masker.mask("test@example.com"))  # te***@*******.com

# Full masking - complete privacy
masker = Masker(strategy=MaskingStrategy.FULL)
print(masker.mask("test@example.com"))  # ******************

# Token masking - for analytics
masker = Masker(strategy=MaskingStrategy.TOKEN)
print(masker.mask("test@example.com"))  # [EMAIL]
```

### Selective Masking

```python
# Mask only specific PII types
masker = Masker()
text = "Email: test@example.com, Phone: 555-1234, IP: 192.168.1.1"

# Only mask emails
print(masker.mask(text, pii_types=[PIIPattern.EMAIL]))

# Only mask phone numbers
print(masker.mask(text, pii_types=[PIIPattern.PHONE]))
```

### Custom Patterns

```python
# Add custom patterns for domain-specific data
masker = Masker()
masker.add_custom_pattern("employee_id", r"EMP-\d{6}")

text = "Employee EMP-123456 reported an issue"
print(masker.mask(text))  # Employee EM******** reported an issue
```

## Supported PII Types

| Type | Example | Masked (Partial) |
|------|---------|------------------|
| Email | john@example.com | jo***@*******.com |
| Phone (US) | (555) 123-4567 | (***) ***-4567 |
| Credit Card | 4532-1488-0343-6467 | ************6467 |
| SSN | 123-45-6789 | ***-**-**** |
| IP Address | 192.168.1.1 | 19*.***.*.* |

## Documentation

For detailed documentation, see the [docs](docs/README.md) directory.

For more examples, check out the [examples](examples/basic_usage.py) directory.

## Development

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/veil.git
cd veil

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=veil --cov-report=html

# Run specific test file
pytest tests/test_masker.py
```

### Code Quality

```bash
# Format code
black veil tests

# Lint code
ruff check veil tests

# Type checking
mypy veil
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Hyeon Sang Jeon

## Acknowledgments

- Inspired by the need for better PII protection in data processing pipelines
- Built with privacy and compliance in mind (GDPR, CCPA, etc.)
