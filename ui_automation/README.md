# MockAPI AI UI Automation

This module runs natural-language UI cases with Midscene.js and Playwright.

## Install

```powershell
cd ui_automation
npm install
npx playwright install chromium
```

Configure a multimodal model with Midscene variables before running a case:

```powershell
$env:MIDSCENE_MODEL_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:MIDSCENE_MODEL_API_KEY = "your-api-key"
$env:MIDSCENE_MODEL_NAME = "qwen3.7-plus"
$env:MIDSCENE_MODEL_FAMILY = "qwen3"
$env:MIDSCENE_MODEL_RETRY_COUNT = "4"
$env:MIDSCENE_MODEL_RETRY_INTERVAL = "5000"
```

The web console stores cases and starts the runner through the MockAPI backend.
The runner uses Chromium because Midscene web automation relies on Chromium/CDP
for some visual interaction paths. When the runner is inside a Linux container
without a display server, a case requesting a visible browser is automatically
executed headlessly.

Each run gets a private `MIDSCENE_RUN_DIR`, so concurrent runs cannot pick up
each other's artifacts. The backend copies the generated HTML report into its
protected report endpoint for both passing and failing runs, because the report
is the main debugging artifact when a step fails. Playwright also records the
full browser session as a `.webm` file under `MIDSCENE_RUN_DIR/videos`.
For transient model gateway overloads, configure `MIDSCENE_MODEL_RETRY_COUNT`
and `MIDSCENE_MODEL_RETRY_INTERVAL` to allow a longer backoff window.

## Writing cases

Prompts are Gherkin scenarios executed by `runGherkinScenario`:

- `Given` / `When` map to `aiAct`, `Then` maps to `aiAssert`, and `And` / `But`
  reuse the preceding keyword.
- Only one `Scenario:` per case. `Feature`, `Background`, `Scenario Outline`,
  `Examples`, data tables and placeholders are not supported.
- Each step is an isolated model call, so avoid pronouns like "click it" or
  vague checks like "verify the result". Name the target and the expected state
  in every step.
- Describe elements by what they look like and where they are rather than by
  business meaning, e.g. "the person icon in the top-right corner".
- Use the case's `context` field for page background and business rules instead
  of stuffing them into the scenario text.
