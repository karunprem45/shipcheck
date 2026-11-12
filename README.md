# ShipCheck

An AI-assisted release-readiness gate for pull requests.

On every PR, ShipCheck:

1. Runs the test suite and a security scan (bandit).
2. Sends the diff to Claude with a fixed JSON schema and gets back review findings,
   suggested tests for changed functions, and a changelog draft. Bad JSON gets one retry
   with the error fed back; findings that point at files the PR did not touch are dropped.
3. Runs cheap rule checks (hard-coded secrets, TODOs) that still work when the LLM is down.
4. Merges everything into `evidence.json`.
5. A Go CLI reads the evidence plus a policy file and decides READY / NOT READY.
   A missing test or scan report counts as a failure, never a pass.
6. Posts one PR comment with the checklist and the review.

`metrics/prmetrics.py` computes engineering-productivity numbers from merged PRs:
median cycle time, median time to first review, and how many ShipCheck findings were accepted.

```
agent/     Python agent (diff parser, LLM client, schema validator, review workflow)
gate/      Go release-readiness gate + policy.json
metrics/   PR productivity metrics
.github/   CI: unit tests (pytest + go test), then the gate on PRs
```

## Run locally

```bash
cd agent && python -m unittest discover -s tests        # 11 tests, no API key needed
cd gate && go test ./...                                 # 8 tests
git diff main...HEAD > pr.diff
cd agent && python -m shipcheck_agent.cli --diff ../pr.diff --no-llm
cd gate && go run . -evidence ../agent/evidence.json -policy policy.json
```

Set `ANTHROPIC_API_KEY` (and optionally `SHIPCHECK_MODEL`) to turn on the AI review.
In GitHub, add the key as a repo secret named `ANTHROPIC_API_KEY`.

## Not measured yet

- Precision of AI findings on real PRs (label 30+ findings as useful / not useful)
- Share of suggested tests that get written
- Gate runtime per PR (read it from the Actions tab)

## CI triggers

- Push to `main`: unit tests only.
- Pull request: unit tests, then the readiness gate and a PR comment.
  Without the `ANTHROPIC_API_KEY` secret the gate still runs using static checks only.
