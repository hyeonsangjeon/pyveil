"""Run the installable Azure OpenAI redaction example.

See ``pyveil.integrations.azure_openai`` for the reusable settings loader and
``ask_azure_openai`` function.
"""

from pyveil.integrations.azure_openai import main

if __name__ == "__main__":
    raise SystemExit(main())
