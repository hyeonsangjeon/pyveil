# Measuring Adoption Without Tracking Users

pyveil has no runtime telemetry. GitHub traffic and PyPI downloads describe
discovery and distribution, not how many people actually use the library.

## Capture A Private Baseline

From a checkout, with the GitHub CLI authenticated as a repository maintainer:

```bash
python scripts/traffic_snapshot.py
```

This requests repository counts, views, clones, popular paths/referrers, and
PyPI Stats recent downloads. It writes timestamped JSON and a readable report
under `local.data/metrics/`, which is ignored by Git. No credentials are saved;
endpoint failures are recorded as unavailable, never as zero. A partial capture
exits with status 1 but preserves the sources that succeeded.

This is a manually run maintainer script, not part of the installed package.
It does not schedule itself, instrument examples, or send application data.

## Compare Like With Like

- Retain the dates actually returned by GitHub. Do not label a stale or partial
  window as today's usage. Traffic is limited to a rolling window, so save it
  before older observations disappear.
- Use aggregate unique counts from the API; do not add daily unique counts.
- Compare equal, non-overlapping windows. Record documentation changes,
  releases, and external sharing alongside each observation.
- Treat high clone counts from few unique cloners as possible repeated or
  automated activity, not evidence of successful installation.
- PyPI recent totals are upstream rolling buckets with no dates in the response.
  They cannot be used as a same-cohort conversion funnel with GitHub traffic.
- A cumulative star count is not a conversion rate. Star deltas need snapshots
  at both ends of the same interval.
- GitHub repository views do not include GitHub Pages visits. Empty referrers
  and a very small sample do not establish a cause for low discovery.

## Check The Next Step

Use `scripts/verify_first_run.py --version VERSION` for the published wheel or
`--wheel PATH` for a candidate. It tests the actual README Python example,
keyless checkout recipes, file processing, repeatability, and failure behavior
in an isolated environment. This proves the path is runnable, not that visitors
ran it. Capture voluntary integration questions and reproducible reports using
synthetic data; never ask users to upload sensitive prompts.

After a change, record what was shared and where. Do not interpret an increase
as the README's causal effect, promise star growth, or add automated promotion
and unsolicited messages to compensate for a small sample.
