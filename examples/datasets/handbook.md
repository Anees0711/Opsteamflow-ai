# Engineering Handbook (excerpt)

Our deployment process uses GitHub Actions. Every pull request runs the test
suite and the evaluation suite. A pull request cannot merge if the evaluation
pass rate drops below the committed threshold.

Secrets are stored in the platform secret manager, never in the repository.
Local development uses a deterministic offline model client so contributors do
not need an API key to run tests.

Incident response: the on-call engineer acknowledges within fifteen minutes.
Post-incident reviews are blameless and produced within three working days.
