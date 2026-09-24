"""Persistence and process control for Midscene-based AI UI automation."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "web" / "data" / "ai_ui_cases.json"
REPORT_DIR = ROOT / "web" / "data" / "ai-ui-reports"
# The run directory is deleted when a run ends, so anything needed for a later
# post-mortem or SOP export has to be copied out of it first.
ARTIFACT_DIR = ROOT / "web" / "data" / "ai-ui-artifacts"
RUNNER_PATH = ROOT / "ui_automation" / "runner.mjs"
PACKAGE_PATH = ROOT / "ui_automation" / "package.json"
# A scenario drives a real browser through several model calls, so the ceiling is
# generous; without one a stalled run pins a thread and a Chromium forever.
RUN_TIMEOUT_SECONDS = max(60, int(os.getenv("AI_UI_RUN_TIMEOUT_SECONDS") or 1800))
# Each run launches its own Chromium on the backend host.
MAX_CONCURRENT_RUNS = max(1, int(os.getenv("AI_UI_MAX_CONCURRENT_RUNS") or 2))
MAX_RUN_RECORDS = 200
REPORT_RETENTION_SECONDS = 7 * 24 * 3600
OFFLINE_SIGNUP_URL_DICT = {
    "sit": "https://expressfinance-dpu-sit.dowsure.com/en/",
    "dev": "https://expressfinance-dpu-dev.dowsure.com/en/sign-up-step1",
    "uat": "https://expressfinance-uat.business.hsbc.com/zh-Hans/",
    "preprod": "https://expressfinance-preprod.business.hsbc.com/zh-Hans/sign-up",
    "reg": "https://expressfinance-dpu-reg.dowsure.com/en/",
}
AI_UI_CUSTOM_ENVIRONMENT = "custom"
AI_UI_ALLOWED_ACTIONS = {
    "click",
    "input",
    "select",
    "assert_visible",
    "assert_text",
    "assert_enabled",
    "assert_disabled",
}

_lock = threading.RLock()
_processes: dict[str, subprocess.Popen[str]] = {}
_runs: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _read_cases() -> list[dict[str, Any]]:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_PATH.exists():
        return []
    try:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []
    except (OSError, json.JSONDecodeError):
        log.exception("Failed to read AI UI cases")
        return []


def _write_cases(cases: list[dict[str, Any]]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = DATA_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(DATA_PATH)


def _infer_environment(url: str) -> str:
    normalized_url = url.strip().rstrip("/")
    for environment, target_url in OFFLINE_SIGNUP_URL_DICT.items():
        if normalized_url == target_url.rstrip("/"):
            return environment
    return AI_UI_CUSTOM_ENVIRONMENT


def _resolve_environment_and_url(payload: dict[str, Any]) -> tuple[str, str]:
    requested_environment = str(payload.get("environment") or "").strip().lower()
    requested_url = str(payload.get("url") or "").strip()
    environment = requested_environment or _infer_environment(requested_url)
    if environment == AI_UI_CUSTOM_ENVIRONMENT:
        url = requested_url
    elif environment in OFFLINE_SIGNUP_URL_DICT:
        url = OFFLINE_SIGNUP_URL_DICT[environment]
    else:
        raise ValueError("environment 必须是 sit、dev、uat、preprod、reg 或 custom")
    if not url:
        raise ValueError("目标 URL 不能为空")
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL 必须以 http:// 或 https:// 开头")
    return environment, url


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text or any(char in text for char in ":#{}[]&*!|>'\"%@`"):
        return json.dumps(text, ensure_ascii=False)
    return text


def _to_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(_to_yaml(child, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(child)}")
        return "\n".join(lines)
    if isinstance(value, list):
        lines: list[str] = []
        for child in value:
            if isinstance(child, dict):
                entries = list(child.items())
                if not entries:
                    lines.append(f"{prefix}- {{}}")
                    continue
                first_key, first_value = entries[0]
                if isinstance(first_value, (dict, list)):
                    lines.append(f"{prefix}- {first_key}:")
                    lines.append(_to_yaml(first_value, indent + 4))
                else:
                    lines.append(f"{prefix}- {first_key}: {_yaml_scalar(first_value)}")
                for key, nested_value in entries[1:]:
                    if isinstance(nested_value, (dict, list)):
                        lines.append(f"{prefix}  {key}:")
                        lines.append(_to_yaml(nested_value, indent + 4))
                    else:
                        lines.append(f"{prefix}  {key}: {_yaml_scalar(nested_value)}")
            else:
                lines.append(f"{prefix}- {_yaml_scalar(child)}")
        return "\n".join(lines)
    return f"{prefix}{_yaml_scalar(value)}"


def _normalize_generated_spec(raw: dict[str, Any], fallback_environment: str) -> dict[str, Any]:
    raw_safety = raw.get("safety") if isinstance(raw.get("safety"), dict) else {}
    allow_submit = bool(raw_safety.get("allow_submit", False))
    target_aliases = {
        "首页": "HSBC Express Finance homepage",
        "FundPark 美元产品": "the FundPark USD Line of Credit product",
        "手机号输入框": "手机号码",
        "获取验证码": "发送验证码",
        "验证码输入框": "the six verification code inputs",
        "安全设置页": "完成安全设置",
        "安全问题下拉选单": "安全问题 selector",
        "安全问题答案输入框": "安全问题答案",
        "密码输入框": "设置密码",
        "提交按钮": "submit button",
    }
    steps: list[dict[str, Any]] = []
    for raw_step in raw.get("steps") or []:
        if not isinstance(raw_step, dict):
            continue
        action = str(raw_step.get("action") or "").strip().lower()
        target = str(raw_step.get("target") or "").strip()
        if action not in AI_UI_ALLOWED_ACTIONS or not target:
            continue
        target = target_aliases.get(target, target)
        if not allow_submit and ("submit" in target.lower() or "提交" in target):
            continue
        step = {"action": action, "target": target}
        if raw_step.get("value") is not None:
            value = str(raw_step.get("value"))
            variable_match = re.fullmatch(r"\$\{\s*([A-Za-z0-9_]+)\s*\}", value)
            step["value"] = f"{{{{{variable_match.group(1).lower()}}}}}" if variable_match else value
        steps.append(step)
    if not steps:
        raise ValueError("AI 未生成有效步骤，请把页面、动作和断言描述得更具体")
    variables = raw.get("variables") if isinstance(raw.get("variables"), dict) else {}
    return {
        "name": str(raw.get("name") or "AI UI 自动化用例").strip(),
        "environment": str(raw.get("environment") or fallback_environment).strip().lower(),
        "variables": {str(key): str(value) for key, value in variables.items()},
        "steps": steps,
        "safety": {
            "allow_submit": allow_submit
        },
    }


def _spec_to_gherkin(spec: dict[str, Any]) -> str:
    lines = [f"Scenario: {spec['name']}"]
    action_started = False
    assertion_started = False
    for index, step in enumerate(spec["steps"]):
        action = step["action"]
        target = step["target"]
        value = step.get("value")
        if action == "click":
            text = f'I click the "{target}"'
        elif action == "input":
            text = f'I enter "{value or ""}" in the "{target}" field'
        elif action == "select":
            text = f'I select "{value or ""}" in the "{target}" selector'
        elif action == "assert_visible":
            text = f'the page should show "{target}"'
        elif action == "assert_text":
            text = f'the page should contain "{target}"'
        elif action == "assert_enabled":
            text = f'the "{target}" should be enabled'
        else:
            text = f'the "{target}" should be disabled'
        if index == 0:
            keyword = "Given"
        elif action in {"click", "input", "select"} and not action_started:
            keyword = "When"
            action_started = True
        elif action.startswith("assert_") and not assertion_started:
            keyword = "Then"
            assertion_started = True
        else:
            keyword = "And"
        lines.append(f"  {keyword} {text}")
    return "\n".join(lines)


def generate_case_spec(instruction: str, environment: str = "custom", context: str = "") -> dict[str, Any]:
    from web.services.ai_service import DPUAIService, _extract_json_payload

    service = DPUAIService()
    service._call_options = {}
    messages = [
        {
            "role": "system",
            "content": (
                "You convert a user's UI test description into JSON only. "
                "Do not execute tools and do not include markdown. "
                "Return exactly an object with name, environment, variables, steps, safety. "
                "Each step must use one action from click,input,select,assert_visible,assert_text,"
                "assert_enabled,assert_disabled. Each step needs target; input/select may have value. "
                "Use {{variable_name}} for values that belong in variables. "
                "Never create submit or destructive actions unless the user explicitly requests it. "
                "Use literal visible labels from the described page, not abstract targets such as "
                "homepage, email field, or form. For Chinese pages use the visible Chinese labels. "
                "For an assertion that a page is open, use a visible heading or page title."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Default environment: {environment}\n"
                f"Context: {context}\n"
                f"User description: {instruction}"
            ),
        },
    ]
    raw = _extract_json_payload(service._call_model(messages, temperature=0.1))
    spec = _normalize_generated_spec(raw, environment)
    spec["gherkin"] = _spec_to_gherkin(spec)
    spec["yaml"] = _to_yaml(spec)
    return spec


def list_cases(username: str) -> list[dict[str, Any]]:
    with _lock:
        return [item for item in _read_cases() if item.get("username") == username]


def save_case(username: str, payload: dict[str, Any], case_id: str | None = None) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    prompt = str(payload.get("prompt") or "").strip()
    if not name or not prompt:
        raise ValueError("name、prompt 不能为空")
    environment, url = _resolve_environment_and_url(payload)

    with _lock:
        cases = _read_cases()
        item = next((row for row in cases if row.get("id") == case_id and row.get("username") == username), None)
        if item is None:
            item = {
                "id": uuid.uuid4().hex,
                "username": username,
                "created_at": _now(),
            }
            cases.append(item)
        item.update({
            "name": name,
            "environment": environment,
            "url": url,
            "prompt": prompt,
            "context": str(payload.get("context") or "").strip(),
            "variables": payload.get("variables") if isinstance(payload.get("variables"), dict) else {},
            "structured_spec": payload.get("structured_spec") if isinstance(payload.get("structured_spec"), dict) else None,
            "headed": bool(payload.get("headed", False)),
            "viewport": {
                "width": max(800, int(payload.get("viewport", {}).get("width", 1440))),
                "height": max(600, int(payload.get("viewport", {}).get("height", 900))),
            },
            "updated_at": _now(),
        })
        for field in ("uat_api_bootstrap", "file_chooser_allowed_dir"):
            if field in payload:
                item[field] = payload[field]
        _write_cases(cases)
        return dict(item)


def delete_case(username: str, case_id: str) -> bool:
    with _lock:
        cases = _read_cases()
        kept = [row for row in cases if not (row.get("id") == case_id and row.get("username") == username)]
        if len(kept) == len(cases):
            return False
        _write_cases(kept)
        return True


def runtime_status() -> dict[str, Any]:
    node = shutil.which("node")
    node_modules = ROOT / "ui_automation" / "node_modules"
    playwright_test = node_modules / "@playwright" / "test"
    return {
        "node": bool(node),
        "node_path": node or "",
        "runner": RUNNER_PATH.exists(),
        "dependencies": (
            (node_modules / "@midscene" / "web").exists()
            and (node_modules / "playwright").exists()
            and playwright_test.exists()
        ),
        "configured": all(
            bool(os.getenv(name))
            for name in ("MIDSCENE_MODEL_API_KEY", "MIDSCENE_MODEL_BASE_URL", "MIDSCENE_MODEL_NAME")
        ),
        "environments": [
            {"value": environment, "label": environment.upper(), "url": url}
            for environment, url in OFFLINE_SIGNUP_URL_DICT.items()
        ] + [{"value": AI_UI_CUSTOM_ENVIRONMENT, "label": "自定义", "url": ""}],
        "install_command": "cd ui_automation; npm install; npx playwright install chromium",
    }


def list_runs(username: str) -> list[dict[str, Any]]:
    with _lock:
        return [dict(run) for run in _runs.values() if run.get("username") == username]


def get_run(username: str, run_id: str) -> dict[str, Any] | None:
    with _lock:
        run = _runs.get(run_id)
        return dict(run) if run and run.get("username") == username else None


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Kill the runner and the Chromium it launched.

    terminate() only signals Node, leaving the browser as an orphan on Windows.
    """
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=15,
            )
            return
        except (OSError, subprocess.SubprocessError):
            log.warning("taskkill failed for pid %s, falling back to kill()", process.pid)
    try:
        process.kill()
    except OSError:
        log.warning("Failed to kill runner pid %s", process.pid)


def _active_run_count() -> int:
    return sum(1 for process in _processes.values() if process.poll() is None)


def _trim_run_records() -> None:
    """Drop the oldest finished runs so a long-lived process stays bounded."""
    if len(_runs) <= MAX_RUN_RECORDS:
        return
    finished = [
        run_id
        for run_id, run in sorted(_runs.items(), key=lambda item: item[1].get("started_at") or "")
        if run_id not in _processes
    ]
    for run_id in finished[: len(_runs) - MAX_RUN_RECORDS]:
        run = _runs.pop(run_id, None)
        if not run:
            continue
        try:
            Path(str(run.get("report_file") or "")).unlink(missing_ok=True)
        except OSError:
            log.warning("Failed to remove report for evicted run %s", run_id)


def prune_orphan_reports() -> int:
    """Delete report files no live run can serve any more.

    Run records live in memory only, so after a restart every report on disk is
    unreachable through the API and would otherwise stay forever.
    """
    if not REPORT_DIR.is_dir():
        return 0
    cutoff = time.time() - REPORT_RETENTION_SECONDS
    removed = 0
    with _lock:
        known = {str(run.get("report_file") or "") for run in _runs.values()}
    for path in REPORT_DIR.glob("*.html"):
        if str(path) in known:
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            log.warning("Failed to prune report %s", path)
    # Run directories are removed when a run ends; anything left is from a crash.
    run_dirs = ROOT / "web" / "data" / "ai-ui-run-dirs"
    if run_dirs.is_dir():
        with _lock:
            live = set(_processes)
        for path in run_dirs.iterdir():
            if path.is_dir() and path.name not in live:
                shutil.rmtree(path, ignore_errors=True)
    return removed


def _collect_report(run: dict[str, Any], parsed: dict[str, Any], run_dir: Path) -> None:
    """Copy the Midscene HTML report into the protected location, pass or fail."""
    report_target = Path(run["report_file"])
    candidate = str(parsed.get("report_path") or "")
    source = Path(candidate) if candidate and Path(candidate).is_file() else None
    if source is None:
        reports = sorted(
            (path for path in (run_dir / "report").rglob("*.html") if path.is_file()),
            key=lambda path: path.stat().st_mtime,
        )
        source = reports[-1] if reports else None
    if source is not None:
        try:
            shutil.copy2(source, report_target)
        except OSError:
            log.exception("Failed to copy Midscene report %s", source)
    if report_target.is_file():
        parsed["report_url"] = f"/api/ai-ui/runs/{run['id']}/report"


def _collect_artifacts(run: dict[str, Any], run_dir: Path) -> None:
    """Keep the page dumps and videos a failed run needs for diagnosis.

    Without this the only surviving artifact is the HTML report, and the page
    snapshot that shows *why* a control was disabled is gone with the run dir.
    """
    target = ARTIFACT_DIR / run["id"]
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        log.exception("Failed to create artifact dir %s", target)
        return
    for path in sorted(run_dir.glob("*")):
        if path.is_file() and path.suffix in {".txt", ".html", ".json", ".png"}:
            try:
                shutil.copy2(path, target / path.name)
            except OSError:
                log.warning("Failed to keep artifact %s", path)
    videos = run_dir / "videos"
    if videos.is_dir():
        for path in sorted(videos.glob("*.webm")):
            try:
                shutil.copy2(path, target / f"video-{path.name}")
            except OSError:
                log.warning("Failed to keep video %s", path)
    run["artifact_dir"] = str(target)


# A Playwright/Node failure names its own API, so it is recognisable without the
# model. Checked before the business words because those words ("申请", "校验") also
# appear inside a locator string and used to make every timeout look like a
# business rejection.
_TECHNICAL_ERROR_TOKENS = (
    "locator.",
    "page.",
    "Timeout",
    "timeout",
    "waiting for",
    "net::",
    "ECONN",
    "Target closed",
    "Execution context was destroyed",
    "runner exited with code",
    "被终止",
)
_BUSINESS_ERROR_TOKENS = ("业务", "校验", "注册号", "系统维护", "以下项目有误", "不可用")


def _fallback_run_analysis(parsed: dict[str, Any], error: str = "") -> dict[str, Any]:
    status = parsed.get("status") or ("passed" if not error else "failed")
    raw_error = error or str(parsed.get("error") or "")
    technical = bool(raw_error) and any(token in raw_error for token in _TECHNICAL_ERROR_TOKENS)
    business = bool(raw_error) and not technical and any(token in raw_error for token in _BUSINESS_ERROR_TOKENS)
    if raw_error and not technical and not business:
        technical = True
    return {
        "status": status,
        "summary": "用例执行成功，未发现失败信息。" if status == "passed" else "用例执行失败，需要根据卡点信息处理。",
        "completed_steps": [],
        "business_blocker": business,
        "technical_blocker": technical,
        "blocker": raw_error[:2000],
        "suggestion": "查看 HTML 报告和 runner 错误信息。" if raw_error else "继续进行结果核验。",
        "source": "fallback",
    }


def _analyze_run_with_ai(run: dict[str, Any], parsed: dict[str, Any], stdout: str, stderr: str, run_dir: Path) -> dict[str, Any]:
    from web.services.ai_service import DPUAIService, _extract_json_payload

    error = str(parsed.get("error") or run.get("error") or "")
    evidence = {
        "run_status": parsed.get("status") or run.get("status"),
        "url": parsed.get("url"),
        "title": parsed.get("title"),
        "error": error[-6000:],
        "stderr": str(stderr or "")[-3000:],
        "stdout_tail": str(stdout or "")[-3000:],
        "page_text": "",
    }
    # The last page the run was looking at matters most, so the drawdown dumps are
    # listed too: a disabled control's reason only shows up in that page's text.
    for filename in (
        "business-page-filled.txt",
        "director-page.txt",
        "offer-page.txt",
        "drawdown-main-page.txt",
        "drawdown-page.txt",
        "drawdown-entry-missing.txt",
    ):
        path = run_dir / filename
        if path.is_file():
            evidence["page_text"] += f"\n[{filename}]\n{path.read_text(encoding='utf-8', errors='replace')[:5000]}"
    messages = [
        {
            "role": "system",
            "content": (
                "你是UI自动化测试结果分析器。只返回JSON对象，不要Markdown。"
                "字段必须包含summary、completed_steps、business_blocker、technical_blocker、"
                "blocker、suggestion。区分业务卡点和自动化/模型/网络技术卡点。"
                "completed_steps必须是字符串数组，business_blocker和technical_blocker必须是布尔值。"
            ),
        },
        {
            "role": "user",
            "content": f"请分析以下AI UI运行证据：\n{json.dumps(evidence, ensure_ascii=False)}",
        },
    ]
    try:
        service = DPUAIService()
        raw = service._call_model(messages, temperature=0.1)
        try:
            analysis = _extract_json_payload(raw)
        except Exception:
            cleaned = str(raw or "").strip()
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            analysis = json.loads(cleaned[start : end + 1])
        if not isinstance(analysis, dict):
            raise ValueError("AI解析结果不是对象")
        analysis["source"] = "ai"
        return analysis
    except Exception as exc:
        log.warning("AI UI result analysis failed: %s", exc)
        fallback = _fallback_run_analysis(parsed, error)
        fallback["analysis_error"] = str(exc)[:1000]
        return fallback


def _watch_run(run_id: str, process: subprocess.Popen[str], input_path: Path, run_dir: Path) -> None:
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=RUN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(process)
        stdout, stderr = process.communicate()
    parsed: dict[str, Any] = {}
    for line in reversed((stdout or "").strip().splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            parsed = payload
            break
    with _lock:
        run = _runs.get(run_id)
        if not run:
            return
        _collect_report(run, parsed, run_dir)
        _collect_artifacts(run, run_dir)
        analysis = _analyze_run_with_ai(run, parsed, stdout, stderr, run_dir)
        parsed["analysis"] = analysis
        if run["status"] == "stopped":
            run["result"] = parsed or None
        elif timed_out:
            run.update({
                "status": "failed",
                "error": f"执行超过 {RUN_TIMEOUT_SECONDS} 秒被终止",
                "result": parsed,
            })
        elif process.returncode == 0 and parsed.get("status") == "passed":
            run.update({"status": "passed", "result": parsed})
        else:
            error = (
                parsed.get("error")
                or stderr
                or stdout
                or f"runner exited with code {process.returncode}"
            )
            run.update({"status": "failed", "error": str(error)[-6000:], "result": parsed})
        run["finished_at"] = _now()
        _processes.pop(run_id, None)
        _trim_run_records()
    try:
        input_path.unlink(missing_ok=True)
    except OSError:
        log.warning("Failed to remove runner input %s", input_path)
    shutil.rmtree(run_dir, ignore_errors=True)


def start_run(username: str, case: dict[str, Any]) -> dict[str, Any]:
    status = runtime_status()
    if not status["node"]:
        raise RuntimeError("未找到 Node.js，请先安装 Node.js")
    if not status["dependencies"]:
        raise RuntimeError("Midscene 依赖未安装，请执行 ui_automation/README.md 中的安装命令")
    if not status["configured"]:
        raise RuntimeError(
            "视觉模型未配置完整，需要同时设置 MIDSCENE_MODEL_API_KEY、MIDSCENE_MODEL_BASE_URL、MIDSCENE_MODEL_NAME"
        )

    with _lock:
        if _active_run_count() >= MAX_CONCURRENT_RUNS:
            raise RuntimeError(
                f"当前已有 {MAX_CONCURRENT_RUNS} 个用例在执行，请等待其中一个结束后再启动"
            )

    run_id = uuid.uuid4().hex
    input_path = ROOT / "web" / "data" / f"ai-ui-run-{run_id}.json"
    report_path = ROOT / "web" / "data" / "ai-ui-reports" / f"{run_id}.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    # Each run gets its own Midscene output directory so concurrent runs never
    # pick up each other's report as "newest".
    run_dir = ROOT / "web" / "data" / "ai-ui-run-dirs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    input_path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    process = subprocess.Popen(
        [status["node_path"], str(RUNNER_PATH), str(input_path)],
        cwd=str(ROOT / "ui_automation"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, "MIDSCENE_RUN_DIR": str(run_dir)},
    )
    run = {
        "id": run_id,
        "case_id": case.get("id"),
        "case_name": case.get("name"),
        "environment": case.get("environment") or _infer_environment(str(case.get("url") or "")),
        "username": username,
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "result": None,
        "error": "",
        "report_file": str(report_path),
    }
    with _lock:
        _runs[run_id] = run
        _processes[run_id] = process
    threading.Thread(target=_watch_run, args=(run_id, process, input_path, run_dir), daemon=True).start()
    return dict(run)


def build_run_sop(username: str, run_id: str) -> Path | None:
    """Turn a run's report into a downloadable SOP pack (screenshots + videos)."""
    from web.services.ai_ui_sop import build_sop_archive

    run = get_run(username, run_id)
    if not run:
        return None
    report_file = Path(str(run.get("report_file") or ""))
    if not report_file.is_file():
        raise RuntimeError("Midscene 报告尚未生成，无法导出 SOP")
    artifacts = ARTIFACT_DIR / run_id
    archive = artifacts / f"sop-{run_id}.zip"
    build_sop_archive(
        report_file,
        artifacts / "sop",
        archive,
        title=str(run.get("case_name") or ""),
        extras=sorted(artifacts.glob("video-*.webm")),
    )
    return archive


def stop_run(username: str, run_id: str) -> dict[str, Any] | None:
    with _lock:
        run = _runs.get(run_id)
        process = _processes.get(run_id)
        if not run or run.get("username") != username:
            return None
        if process and process.poll() is None:
            _kill_process_tree(process)
            run["status"] = "stopped"
            run["finished_at"] = _now()
        return dict(run)
