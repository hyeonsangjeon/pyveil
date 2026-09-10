# Reproducible file runs

`pyveil run` reads a real UTF-8 file, executes the installed redaction engine,
and writes the result plus a receipt. It does not call a model, return a canned
answer, or silently fall back to a demo.

## Start with your file

Use a new working directory. On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pyveil==0.3.0
python -m pyveil init --input /path/to/request.json --input-format json
python -m pyveil run
```

On Windows PowerShell, use the environment's executable directly:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install pyveil==0.3.0
.\.venv\Scripts\python -m pyveil init --input C:\path\to\request.json --input-format json
.\.venv\Scripts\python -m pyveil run
```

If you do not yet have an input, replace `init --input ...` with
`init --example`. This creates `input.example.json` containing labeled synthetic
data. The subsequent `run` still reads the file and performs real redaction.
Use `input_format: "text"` for a log, prompt, or Markdown file; JSON mode requires
an object or array and rejects malformed, duplicate-key, and non-finite JSON.

Do not run `init` again to repeat an execution. Run `pyveil run` again.
`init` refuses to overwrite the config, key, or example input.

## The executable ledger

The generated `pyveil.json` contains:

```json
{
  "schema_version": 1,
  "pyveil_version": "0.3.0",
  "input": "input.example.json",
  "input_format": "json",
  "input_origin": "synthetic",
  "output_dir": ".pyveil-runs",
  "scope": "local/files",
  "channel": "prompt.input",
  "level": "HIGH",
  "max_input_chars": 1000000,
  "actions": {},
  "secret_file": ".pyveil.key"
}
```

All fields are checked; unknown keys and duplicate JSON keys are errors.
`input_origin` is your provenance label: `synthetic` for fabricated examples or
`user-provided` for your own data. It is not a detector judgment about that data.

Paths are relative to the config directory. For example, from another directory,
`pyveil run /work/job/pyveil.json` still reads `/work/job/input.example.json`.
No `.env` file is auto-loaded and `PYVEIL_SCOPE` does not override this config.
The core does not make network requests or load provider SDKs.

The package version is pinned deliberately. A mismatch fails before input is
processed. Install that version, or update the pin after reviewing the changelog.
Keep the input and the private key with the config when reproducing a job;
the config contains references, not copies of sensitive data.

## Secrets

By default, `init` creates `.pyveil.key` with 32 random bytes encoded as hex and
owner-only file permissions on POSIX. It is never replaced on a subsequent run.
Losing or changing it changes placeholders; pyveil refuses a missing key instead
of generating a new one silently.

For a deployment with a secret manager, initialize with a named environment
variable instead:

```bash
python -m pyveil init --input input.json --secret-env PYVEIL_SECRET
```

Then provide `PYVEIL_SECRET` through your secret manager before running. The JSON
contains only `"secret_env": "PYVEIL_SECRET"`, not the value. Exactly one of
`secret_env` or `secret_file` is allowed.

Keep `.pyveil.key` and `.pyveil-runs/` out of version control. This repository
ignores those names; add equivalent rules in your own repository. On Windows,
restrict access with the account/directory ACLs; POSIX `0600` is not a Windows
ACL guarantee. Configuration can be shared after reviewing paths and scope;
raw input and keys must remain private. Outputs need human review before sharing,
especially when using `LOW`, `PASS`, or formats the detectors do not recognize.

## Policy really runs

`channel` must be one of the public `Channel` values. `level` is `HIGH` or `LOW`.
An empty `actions` object keeps the default policy, including credential blocking
on `tool.call.arguments`. Optional overrides use public entity names:

```json
"actions": {"EMAIL": "REDACT", "API_KEY": "BLOCK"}
```

To exercise a real failure, change the tutorial config's `channel` to
`tool.call.arguments` and run it again. The authorization value is blocked,
the command exits `2`, and **no new output directory is published**.

`PASS` deliberately leaves a matched value visible and is counted separately
from redaction. `LOW` retains partial shape. Prefer `HIGH` and no `PASS`
exceptions at agent or external boundaries. Custom regex/known-value rules
remain available through the Python API, not this small run schema.

## Output and receipt

Each success creates a new private `.pyveil-runs/<run-id>/` with:

| File | Meaning |
| --- | --- |
| `redacted.json` or `redacted.txt` | Actual processed data; the source is never overwritten |
| `receipt.json` | Version, config hash, input keyed digest, output hash, counts, timing, and provenance |

Both files are written to a staging directory before the completed run becomes
visible. Failed validation, blocking, or processing writes no completed output.
If the machine stops while writing, a private `.pending-*` directory can remain;
it is not a successful run and can be removed after confirming no run is active.

The receipt includes `execution.kind: "local-file-redaction"`,
`execution.measured: true`, the explicit input origin, and `provider_called: false`.
`processing_seconds` measures config loading through output serialization, not
installation or the final disk write. The external five-minute check measures
installation through persisted output separately.

`config_sha256` hashes the UTF-8 config file; `output_sha256` hashes exactly the
written output bytes. `input_hmac_sha256` is keyed to avoid publishing a plain
hash of potentially guessable raw input. `key_id` lets you detect a key change
without disclosing the key. Receipts omit raw inputs, secret values, original
paths, finding paths, and placeholder values. They are not compliance evidence.

Run twice with the same input, config, key, and version: output bytes and
output hashes match, but run IDs and measured timings do not. Re-running on
already-redacted output is a different operation and is not promised to be
byte-idempotent.

## Troubleshooting

| Exit | Condition | What to do |
| --- | --- | --- |
| `0` | Both output and receipt were published | Open the paths printed by the command |
| `1` | Input missing/invalid UTF-8/invalid JSON, or output I/O failed | Check config-relative paths, JSON format, permissions, and disk space |
| `2` | Invalid config, version mismatch, missing/private-key permission issue, size limit, or policy block | Correct the named setting; do not bypass a block with the raw input |

`pyveil test-config pyveil.json` checks schema and version only, with no writes.
`pyveil run` checks the referenced input and secret too. No argument default
can silently turn a failed run into a demo or report success.

If `python -m pyveil` imports an old source directory, leave that directory or
use `python -I -m pyveil`. The installed-wheel check always uses an isolated
interpreter outside the checkout.

## Reproduce the five-minute check

From a checkout, using only the project's existing Python tooling:

```bash
python -m pip install -e ".[dev]"
python -m build
python scripts/verify_first_run.py --wheel dist/pyveil-0.3.0-py3-none-any.whl
python scripts/verify_first_run.py --version 0.3.0
```

Each check creates a fresh virtual environment and uses the installed package
outside the checkout. It includes installation, config/key/input creation,
two real file runs, byte/hash/shape comparisons, and rejection/block checks.
The process fails if those operations exceed 300 seconds. The wheel check
installs offline; the version check downloads the pinned release from PyPI
without pip's cache. Neither includes building the wheel or installing Python.

These checks prove a small local workload on the recorded machine. They do not
prove arbitrary-file PII recall, every platform's installation time, or a live
LLM response. For live model calls see the existing
[Ollama guide](integrations/ollama.md); server installation, model download,
and inference are separate and are not hidden inside the five-minute claim.

## Migrating from 0.2.x

The old root `pyveil.yaml` was a reference schema. Core CLI commands never
loaded it, and its validator could accept commented-out fields. Version 0.3
replaces that path with strict executable JSON; `init old.yaml` and
`test-config old.yaml` now fail with migration guidance.

Create a new JSON ledger and choose its channel/actions explicitly. There is
no automatic translation of unused detector toggles. `redact`, `scan`,
`Veil`, and provider-specific YAML/`.env` loaders retain their interfaces.
