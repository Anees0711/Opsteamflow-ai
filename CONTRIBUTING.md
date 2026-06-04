# Contributing

The whole system runs offline. You do not need an API key to develop or test.

```bash
pip install -e ".[dev]"
pytest -q                 # must stay green; runs on the offline FakeClient
python scripts/eval_gate.py   # the regression gate CI runs
```

Rules of the road:

- New behaviour needs a test that runs offline.
- If you add a scorer, return the existing `Score` type so it is swappable.
- If you add a subsystem, it must map to a real failure mode and be importable
  on its own without a web framework.
- Keep `FakeClient` dumb. It exists to prove plumbing, never to fake quality.
