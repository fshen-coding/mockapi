"""Turn a Midscene HTML report into a step-by-step SOP screenshot pack.

The report embeds one JPEG per recorded step as an inline base64 `midscene-image`
script tag, keyed by the screenshot id referenced from the run's `midscene_web_dump`
JSON. Extracting both gives an ordered, human-readable walkthrough of the run
without needing the browser or the original run directory.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# The bundled report player ships the same tag names inside its own JavaScript, so
# the real payload is identified by the attributes the generator writes on it.
_DUMP_RE = re.compile(
    r'<script\s+type="midscene_web_dump"[^>]*\sdata-group-id="[^"]*"[^>]*>(.*?)</script>',
    re.DOTALL,
)
_IMAGE_RE = re.compile(
    r'<script\s+type="midscene-image"\s+data-id="([^"]+)"\s*>\s*(data:image/([a-zA-Z0-9.+-]+);base64,([^<]*?))\s*</script>',
    re.DOTALL,
)
_LOG_PREFIX_RE = re.compile(r"^Log\s*-\s*")
_UNSAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def _slug(text: str, limit: int = 60) -> str:
    cleaned = _UNSAFE_NAME_RE.sub(" ", text).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:limit] or "step"


def _step_title(name: str) -> str:
    return _LOG_PREFIX_RE.sub("", str(name or "").strip()) or "未命名步骤"


def _timestamp(value: Any) -> str:
    try:
        milliseconds = int(value)
    except (TypeError, ValueError):
        return ""
    if milliseconds <= 0:
        return ""
    return datetime.fromtimestamp(milliseconds / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _parse_report(report_file: Path) -> tuple[dict[str, Any], dict[str, tuple[str, bytes]]]:
    html = report_file.read_text(encoding="utf-8", errors="replace")
    # Midscene appends one dump tag per recordToReport call rather than rewriting a
    # single one, so reading only the first tag would export just the opening step.
    dump: dict[str, Any] = {}
    executions: list[Any] = []
    for match in _DUMP_RE.finditer(html):
        try:
            # The generator escapes the JSON for HTML embedding; raw control
            # characters in step names would otherwise break strict parsing.
            fragment = json.loads(match.group(1), strict=False)
        except json.JSONDecodeError:
            continue
        if not isinstance(fragment, dict):
            continue
        if not dump:
            dump = fragment
        executions.extend(fragment.get("executions") or [])
    if not dump:
        raise ValueError("报告中未找到 midscene_web_dump 数据")
    dump["executions"] = executions
    images: dict[str, tuple[str, bytes]] = {}
    for image in _IMAGE_RE.finditer(html):
        try:
            images[image.group(1)] = (image.group(3).lower(), base64.b64decode(image.group(4)))
        except (ValueError, TypeError):
            continue
    return dump, images


def _collect_steps(dump: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for execution in dump.get("executions") or []:
        if not isinstance(execution, dict):
            continue
        shots: list[str] = []
        for task in execution.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            for record in task.get("recorder") or []:
                screenshot = (record or {}).get("screenshot") or {}
                shot_id = screenshot.get("id")
                if shot_id and shot_id not in shots:
                    shots.append(str(shot_id))
        steps.append(
            {
                "title": _step_title(execution.get("name")),
                "at": _timestamp(execution.get("logTime")),
                "screenshots": shots,
            }
        )
    steps.sort(key=lambda step: step["at"] or "")
    return steps


def build_sop(report_file: Path, out_dir: Path, *, title: str = "") -> dict[str, Any]:
    """Write `<out_dir>/screenshots/*.jpg` plus `sop.md` and `sop.html`."""
    dump, images = _parse_report(report_file)
    steps = _collect_steps(dump)
    if not steps:
        raise ValueError("报告中没有可导出的步骤")

    shots_dir = out_dir / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    for stale in shots_dir.glob("*"):
        stale.unlink(missing_ok=True)

    heading = title or str(dump.get("groupName") or report_file.stem)
    markdown = [f"# {heading} 操作步骤（SOP）", ""]
    body = []
    exported = 0
    for index, step in enumerate(steps, start=1):
        markdown.append(f"## {index}. {step['title']}")
        if step["at"]:
            markdown.append(f"- 时间：{step['at']}")
        cells = []
        for order, shot_id in enumerate(step["screenshots"]):
            payload = images.get(shot_id)
            if not payload:
                continue
            extension = "jpg" if payload[0] in {"jpeg", "jpg"} else payload[0]
            suffix = "" if order == 0 else f"-{order + 1}"
            filename = f"{index:02d}{suffix}-{_slug(step['title'])}.{extension}"
            (shots_dir / filename).write_bytes(payload[1])
            markdown.append("")
            markdown.append(f"![{step['title']}](screenshots/{filename})")
            cells.append(f'<img src="screenshots/{filename}" alt="{step["title"]}">')
            exported += 1
        markdown.append("")
        body.append(
            f'<section><h2>{index}. {step["title"]}</h2>'
            f'<p class="at">{step["at"]}</p>{"".join(cells)}</section>'
        )

    (out_dir / "sop.md").write_text("\n".join(markdown), encoding="utf-8")
    (out_dir / "sop.html").write_text(
        "<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\">"
        f"<title>{heading} SOP</title>"
        "<style>body{font-family:system-ui,sans-serif;margin:0 auto;padding:24px;max-width:1080px;"
        "background:#f7f8fa;color:#1f2329}h1{font-size:22px}section{background:#fff;border-radius:8px;"
        "padding:16px 20px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.08)}h2{font-size:16px;margin:0 0 4px}"
        ".at{color:#8a9099;font-size:12px;margin:0 0 12px}img{width:100%;border:1px solid #e5e6eb;border-radius:4px}"
        "</style>"
        f"<h1>{heading} 操作步骤（SOP）</h1>{''.join(body)}</html>",
        encoding="utf-8",
    )
    return {"steps": len(steps), "screenshots": exported, "dir": str(out_dir)}


def _find_ffmpeg() -> str:
    """Locate an ffmpeg binary, preferring the one Playwright already installs."""
    if binary := os.getenv("AI_UI_FFMPEG_PATH"):
        if Path(binary).is_file():
            return binary
    roots = [Path(os.getenv("PLAYWRIGHT_BROWSERS_PATH") or "/ms-playwright")]
    home = Path.home()
    roots += [home / "AppData" / "Local" / "ms-playwright", home / ".cache" / "ms-playwright"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("ffmpeg-*/ffmpeg*")):
            if path.is_file():
                return str(path)
    return shutil.which("ffmpeg") or ""


def extract_video_frames(video: Path, out_dir: Path, *, interval_seconds: float = 4.0) -> int:
    """Sample a run recording into stills so a reviewer needs no video player.

    Playwright's bundled ffmpeg is a minimal build with no filter support, so the
    rate has to come from `-r` rather than an `fps=` filtergraph.
    """
    ffmpeg = _find_ffmpeg()
    if not ffmpeg:
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    rate = 1 / max(interval_seconds, 0.1)
    result = subprocess.run(
        [ffmpeg, "-nostdin", "-y", "-i", str(video), "-r", f"{rate:.4f}", str(out_dir / "frame%03d.png")],
        capture_output=True,
        text=True,
        timeout=300,
    )
    frames = sorted(out_dir.glob("frame*.png"))
    if not frames:
        log.warning("ffmpeg produced no frames for %s: %s", video.name, result.stderr[-500:])
    return len(frames)


def build_sop_archive(
    report_file: Path,
    out_dir: Path,
    archive_file: Path,
    *,
    title: str = "",
    extras: list[Path] | None = None,
) -> dict[str, Any]:
    """Build the SOP pack and zip it, optionally bundling run videos alongside."""
    summary = build_sop(report_file, out_dir, title=title)
    archive_file.parent.mkdir(parents=True, exist_ok=True)
    videos = 0
    frames = 0
    # The report only holds one screenshot per recorded step, so everything the
    # browser did between two steps exists solely in the recording. Sampling it
    # into stills keeps that visible without needing a webm player.
    for extra in extras or []:
        if not extra.is_file():
            continue
        videos += 1
        frames += extract_video_frames(extra, out_dir / "video-frames" / extra.stem)
    with zipfile.ZipFile(archive_file, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(out_dir.rglob("*")):
            if path.is_file() and path != archive_file:
                bundle.write(path, path.relative_to(out_dir).as_posix())
        for extra in extras or []:
            if extra.is_file():
                bundle.write(extra, f"videos/{extra.name}")
    summary["videos"] = videos
    summary["frames"] = frames
    summary["archive"] = str(archive_file)
    return summary
