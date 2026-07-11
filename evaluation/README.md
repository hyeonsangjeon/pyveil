# Reproducible detector evaluation

This directory contains a **synthetic regression corpus** for the built-in pyveil
detectors. It answers a narrow, reproducible question:

> Does this version detect the documented supported shapes, preserve negative
> examples, remove the labeled synthetic values, and keep raw findings empty?

It is not a real-world benchmark for unknown PII, broad semantic recall, language
coverage, or compliance.

```bash
python -m pip install -e .
python evaluation/evaluate.py --check
python evaluation/evaluate.py --benchmark
python evaluation/evaluate.py --json
```

`--check` fails on any expected/actual finding mismatch, labeled-value leak,
non-empty `Finding.raw`, or mutation of a negative case. CI runs this gate on
every change.

The optional benchmark is a machine-dependent latency diagnostic and is not a
service-level objective.
