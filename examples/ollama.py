"""Run the installable Ollama redaction example.

See ``pyveil.integrations.ollama`` for the reusable settings loader and
``ask_ollama`` function.
"""

from pyveil.integrations.ollama import main

if __name__ == "__main__":
    raise SystemExit(main())
