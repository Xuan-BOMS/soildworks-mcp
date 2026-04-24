from __future__ import annotations

import atexit
import csv
import ctypes
import io
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any
import winreg
from ctypes import wintypes

import pythoncom
import win32com.client
from mcp.server.fastmcp import FastMCP


SERVER_NAME = "solidworks"
SOLIDWORKS_PROG_ID = "SldWorks.Application"
REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_DLL = Path(
    os.environ.get(
        "SOLIDWORKS_MCP_BRIDGE_DLL",
        str(REPO_ROOT / "bridge" / "bin" / "Release" / "net8.0-windows" / "SolidWorksBridge.dll"),
    )
)
DEFAULT_PART_TEMPLATE = Path(
    os.environ.get(
        "SOLIDWORKS_MCP_TEMPLATE",
        r"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2023\templates\gb_part.prtdot",
    )
)

DOC_TYPE_BY_SUFFIX = {
    ".sldprt": 1,
    ".sldasm": 2,
    ".slddrw": 3,
}


mcp = FastMCP("SolidWorks MCP")

_bridge_lock = threading.Lock()
_bridge_process: subprocess.Popen[str] | None = None
_launch_timeout_seconds = 60.0
_launch_poll_interval_seconds = 0.5
_popup_guard_stop = threading.Event()
_popup_guard_thread: threading.Thread | None = None

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_is_window_visible = _user32.IsWindowVisible
_is_window_visible.argtypes = [wintypes.HWND]
_is_window_visible.restype = wintypes.BOOL
_get_window_text_length = _user32.GetWindowTextLengthW
_get_window_text_length.argtypes = [wintypes.HWND]
_get_window_text_length.restype = ctypes.c_int
_get_window_text = _user32.GetWindowTextW
_get_window_text.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_get_window_text.restype = ctypes.c_int
_get_class_name = _user32.GetClassNameW
_get_class_name.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_get_class_name.restype = ctypes.c_int
_show_window = _user32.ShowWindow
_show_window.argtypes = [wintypes.HWND, ctypes.c_int]
_show_window.restype = wintypes.BOOL
_set_foreground_window = _user32.SetForegroundWindow
_set_foreground_window.argtypes = [wintypes.HWND]
_set_foreground_window.restype = wintypes.BOOL
_get_window_rect = _user32.GetWindowRect

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_RESTORE = 9


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int),
        ("top", ctypes.c_int),
        ("right", ctypes.c_int),
        ("bottom", ctypes.c_int),
    ]


def _co_initialize() -> None:
    pythoncom.CoInitialize()


def _co_uninitialize() -> None:
    pythoncom.CoUninitialize()


def _window_text(hwnd: int) -> str:
    length = _get_window_text_length(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    _get_window_text(hwnd, buffer, length + 1)
    return buffer.value


def _window_class(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    _get_class_name(hwnd, buffer, 256)
    return buffer.value


def _enumerate_windows() -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []

    @_enum_windows_proc
    def callback(hwnd: int, _lparam: int) -> bool:
        if not _is_window_visible(hwnd):
            return True

        title = _window_text(hwnd)
        if not title:
            return True

        rect = RECT()
        _get_window_rect(hwnd, ctypes.byref(rect))
        windows.append(
            {
                "hwnd": hwnd,
                "title": title,
                "class": _window_class(hwnd),
                "rect": (rect.left, rect.top, rect.right, rect.bottom),
            }
        )
        return True

    _user32.EnumWindows(callback, 0)
    return windows


def _manage_solidworks_popups() -> None:
    main_window: dict[str, Any] | None = None
    hidden_dialog = False

    for window in _enumerate_windows():
        title = window["title"]
        left, top, right, bottom = window["rect"]
        width = right - left
        height = bottom - top

        if title.startswith("SOLIDWORKS Premium"):
            main_window = window
            continue

        if title == "splash" and width <= 600 and height <= 400:
            _show_window(window["hwnd"], SW_HIDE)
            continue

        if title == "SOLIDWORKS" and window["class"] == "#32770" and width <= 500 and height <= 250:
            _show_window(window["hwnd"], SW_HIDE)
            hidden_dialog = True

    if hidden_dialog and main_window is not None:
        _show_window(main_window["hwnd"], SW_RESTORE)
        _set_foreground_window(main_window["hwnd"])


def _popup_guard_loop() -> None:
    while not _popup_guard_stop.wait(1.0):
        try:
            _manage_solidworks_popups()
        except Exception:
            continue


def _ensure_popup_guard() -> None:
    global _popup_guard_thread
    if _popup_guard_thread is not None and _popup_guard_thread.is_alive():
        return

    _popup_guard_thread = threading.Thread(
        target=_popup_guard_loop,
        name="solidworks-popup-guard",
        daemon=True,
    )
    _popup_guard_thread.start()


def _get_app(create: bool = False):
    app = _try_get_active_app()
    if app is None and create:
        _launch_desktop_solidworks()
        app = _wait_for_active_app()
    if app is None:
        return None

    try:
        app.UserControl = True
    except Exception:
        pass
    return app


def _try_get_active_app():
    try:
        dispatch = pythoncom.GetActiveObject(SOLIDWORKS_PROG_ID)
    except pythoncom.com_error:
        return None
    return win32com.client.Dispatch(dispatch.QueryInterface(pythoncom.IID_IDispatch))


def _wait_for_active_app(timeout_seconds: float = _launch_timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        app = _try_get_active_app()
        if app is not None:
            return app
        time.sleep(_launch_poll_interval_seconds)
    raise TimeoutError("Timed out waiting for SolidWorks to register its COM automation object.")


def _resolve_solidworks_executable() -> str:
    clsid = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, rf"{SOLIDWORKS_PROG_ID}\CLSID").strip()
    local_server = winreg.QueryValue(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32").strip()
    if local_server.startswith('"'):
        closing_quote = local_server.find('"', 1)
        if closing_quote > 1:
            return local_server[1:closing_quote]
    exe_marker = local_server.lower().find(".exe")
    if exe_marker >= 0:
        return local_server[: exe_marker + 4]
    return local_server


def _launch_desktop_solidworks() -> None:
    executable = _resolve_solidworks_executable()
    os.startfile(executable)


def _is_running() -> bool:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe"],
        capture_output=True,
        text=True,
        check=False,
    )
    return "SLDWORKS.exe" in result.stdout


def _sldworks_pids() -> list[int]:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq SLDWORKS.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    reader = csv.reader(io.StringIO(result.stdout))
    pids: list[int] = []
    for row in reader:
        if len(row) < 2 or row[0] == "INFO:":
            continue
        try:
            pids.append(int(row[1]))
        except ValueError:
            continue
    return pids


def _bool_value(value: Any) -> bool:
    return bool(value)


def _value_or_call(value: Any) -> Any:
    return value() if callable(value) else value


def _mm_to_m(value_mm: float) -> float:
    return value_mm / 1000.0


def _to_mm(value: float, unit: str | None) -> float:
    normalized = (unit or "mm").strip().lower()
    if normalized == "cm":
        return value * 10.0
    if normalized == "m":
        return value * 1000.0
    return value


def _axis_positions(count: int, half_span_mm: float, offset_mm: float) -> list[float]:
    if count <= 0:
        raise ValueError("count must be positive")
    usable = half_span_mm - offset_mm
    if usable < 0:
        raise ValueError("offset exceeds half span")
    if count == 1:
        return [0.0]
    step = (usable * 2.0) / (count - 1)
    return [(-usable + index * step) for index in range(count)]


def _extract_triplet_mm(prompt: str) -> tuple[float, float, float] | None:
    triplet_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×by]{1,2}\s*(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×by]{1,2}\s*(\d+(?:\.\d+)?)\s*mm?",
        prompt,
        re.IGNORECASE,
    )
    if not triplet_match:
        return None
    return tuple(float(triplet_match.group(index)) for index in range(1, 4))


def _extract_value_with_unit(prompt: str, patterns: list[str], default_unit: str = "mm") -> float | None:
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if not match:
            continue
        value = float(match.group(1))
        unit = match.group(2) if match.lastindex and match.lastindex >= 2 else default_unit
        return _to_mm(value, unit)
    return None


def _extract_grid(prompt: str) -> tuple[int, int] | None:
    grid_match = re.search(r"(\d+)\s*(?:x|×|by)\s*(\d+)\s*grid", prompt, re.IGNORECASE)
    if not grid_match:
        grid_match = re.search(r"(\d+)\s*(?:x|×|by)\s*(\d+)", prompt, re.IGNORECASE)
    if not grid_match:
        return None
    return int(grid_match.group(1)), int(grid_match.group(2))


def _extract_first_mm(prompt: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _desktop_path() -> Path:
    return Path.home() / "Desktop"


def _default_part_save_path(base_name: str) -> Path:
    safe = re.sub(r'[<>:"/\\|?*]+', "_", base_name).strip() or "solidworks_part"
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return _desktop_path() / f"{safe}-{timestamp}.SLDPRT"


def _contains_any(prompt: str, keywords: list[str]) -> bool:
    lower = prompt.lower()
    return any(keyword.lower() in lower for keyword in keywords)


def _composite_result(step_results: dict[str, Any], **extra: Any) -> dict[str, Any]:
    def _step_ok(result: Any) -> bool:
        if isinstance(result, list):
            return all(_step_ok(item) for item in result)
        if isinstance(result, dict):
            if "ok" in result:
                return bool(result["ok"])
            if "opened" in result:
                return bool(result["opened"])
            if result.get("running") and isinstance(result.get("active_document"), dict):
                return bool(result["active_document"].get("has_document"))
            return result.get("ok", result.get("opened", False))
        return False

    ok = all(_step_ok(result) for result in step_results.values())
    response = {"ok": ok, "steps": step_results}
    response.update(extra)
    return response


def _shutdown_bridge() -> None:
    global _bridge_process
    if _bridge_process is None:
        return

    if _bridge_process.poll() is None:
        try:
            if _bridge_process.stdin:
                _bridge_process.stdin.close()
        except Exception:
            pass
        _bridge_process.terminate()
        try:
            _bridge_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _bridge_process.kill()
            _bridge_process.wait(timeout=5)

    _bridge_process = None


def _shutdown_popup_guard() -> None:
    _popup_guard_stop.set()


def _get_bridge_process() -> subprocess.Popen[str]:
    global _bridge_process
    if _bridge_process is not None and _bridge_process.poll() is None:
        return _bridge_process

    _shutdown_bridge()
    _bridge_process = subprocess.Popen(
        ["dotnet", str(BRIDGE_DLL), "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    return _bridge_process


atexit.register(_shutdown_bridge)
atexit.register(_shutdown_popup_guard)
_ensure_popup_guard()


def _run_bridge(command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if not BRIDGE_DLL.exists():
        return {
            "ok": False,
            "reason": "bridge_missing",
            "bridge_path": str(BRIDGE_DLL),
        }

    request = json.dumps({"command": command, "payload": payload or {}}, ensure_ascii=False)

    with _bridge_lock:
        process = _get_bridge_process()
        if process.stdin is None or process.stdout is None:
            _shutdown_bridge()
            return {
                "ok": False,
                "reason": "bridge_missing_stdio",
                "command": command,
            }

        try:
            process.stdin.write(request + "\n")
            process.stdin.flush()
            stdout = process.stdout.readline()
        except Exception as exc:
            _shutdown_bridge()
            return {
                "ok": False,
                "reason": "bridge_io_failed",
                "command": command,
                "detail": str(exc),
            }

        if not stdout:
            stderr = ""
            if process.stderr is not None:
                stderr = process.stderr.read().strip()
            returncode = process.poll()
            _shutdown_bridge()
            return {
                "ok": False,
                "reason": "bridge_command_failed",
                "command": command,
                "returncode": returncode,
                "stdout": "",
                "stderr": stderr,
            }

    stdout = stdout.strip()
    try:
        return json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "reason": "bridge_invalid_json",
            "command": command,
            "stdout": stdout,
            "stderr": "",
        }


def _doc_summary(doc: Any) -> dict[str, Any]:
    if doc is None:
        return {"has_document": False}

    title = _value_or_call(getattr(doc, "GetTitle", None))
    path_name = _value_or_call(getattr(doc, "GetPathName", None))
    doc_type = _value_or_call(getattr(doc, "GetType", None))
    return {
        "has_document": True,
        "title": title,
        "path": path_name,
        "doc_type": doc_type,
    }


@mcp.tool()
def ping() -> dict[str, str]:
    """Return a simple health response for the SolidWorks MCP server."""
    return {"server": SERVER_NAME, "status": "ok"}


@mcp.tool()
def solidworks_status() -> dict[str, Any]:
    """Return whether SolidWorks is running and basic app/document state."""
    _co_initialize()
    try:
        app = _get_app(create=False)
        if app is None:
            return {"running": False, "visible": False, "active_document": None}

        active_doc = getattr(app, "ActiveDoc", None)
        return {
            "running": True,
            "visible": _bool_value(getattr(app, "Visible", False)),
            "revision": _value_or_call(getattr(app, "RevisionNumber", None)),
            "active_document": _doc_summary(active_doc),
        }
    finally:
        _co_uninitialize()


@mcp.tool()
def launch_solidworks(visible: bool = True) -> dict[str, Any]:
    """Launch or attach to SolidWorks and optionally show its UI."""
    _co_initialize()
    try:
        app = _get_app(create=True)
        app.Visible = visible
        active_doc = getattr(app, "ActiveDoc", None)
        return {
            "running": True,
            "visible": _bool_value(getattr(app, "Visible", False)),
            "revision": _value_or_call(getattr(app, "RevisionNumber", None)),
            "active_document": _doc_summary(active_doc),
        }
    finally:
        _co_uninitialize()


@mcp.tool()
def close_solidworks(force: bool = True) -> dict[str, Any]:
    """Close the running SolidWorks instance if one is active."""
    _shutdown_bridge()
    pids = _sldworks_pids()
    if not pids:
        return {"closed": False, "reason": "not_running", "force": force}

    command = ["taskkill"]
    for pid in pids:
        command.extend(["/PID", str(pid)])
    command.append("/T")
    if force:
        command.append("/F")

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    time.sleep(1)
    remaining = _sldworks_pids()
    return {
        "closed": not remaining,
        "force": force,
        "requestedPids": pids,
        "remainingPids": remaining,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


@mcp.tool()
def active_document() -> dict[str, Any]:
    """Return metadata about the current active SolidWorks document."""
    _co_initialize()
    try:
        app = _get_app(create=False)
        if app is None:
            return {"running": False, "active_document": None}

        active_doc = getattr(app, "ActiveDoc", None)
        return {"running": True, "active_document": _doc_summary(active_doc)}
    finally:
        _co_uninitialize()


@mcp.tool()
def save_active_document(path: str | None = None, base_name: str = "solidworks-part") -> dict[str, Any]:
    """Save the active SolidWorks part to an explicit path or to the Desktop with a generated name."""
    resolved = Path(path).expanduser().resolve() if path else _default_part_save_path(base_name)
    if resolved.suffix.lower() != ".sldprt":
        resolved = resolved.with_suffix(".SLDPRT")
    resolved.parent.mkdir(parents=True, exist_ok=True)

    _co_initialize()
    try:
        app = _get_app(create=False)
        if app is None:
            return {"ok": False, "reason": "not_running", "path": str(resolved)}

        doc = getattr(app, "ActiveDoc", None)
        if doc is None:
            return {"ok": False, "reason": "no_active_document", "path": str(resolved)}

        errors = 0
        warnings = 0
        saved = False
        save_method = None

        try:
            saved = bool(doc.SaveAs3(str(resolved), 0, 2))
            save_method = "ModelDoc2.SaveAs3"
        except Exception:
            try:
                saved = bool(doc.Extension.SaveAs(str(resolved), 0, 2, None, errors, warnings))
                save_method = "ModelDocExtension.SaveAs"
            except Exception as exc:
                return {
                    "ok": False,
                    "reason": "save_failed",
                    "path": str(resolved),
                    "detail": str(exc),
                }

        return {
            "ok": saved or resolved.exists(),
            "path": str(resolved),
            "method": save_method,
            "savedFlag": saved,
            "exists": resolved.exists(),
            "active_document": _doc_summary(doc),
        }
    finally:
        _co_uninitialize()


@mcp.tool()
def open_document(path: str, visible: bool = True) -> dict[str, Any]:
    """Open a SolidWorks part, assembly, or drawing by file path."""
    resolved = Path(path).expanduser().resolve()
    suffix = resolved.suffix.lower()
    doc_type = DOC_TYPE_BY_SUFFIX.get(suffix)
    if doc_type is None:
        return {
            "opened": False,
            "reason": "unsupported_extension",
            "supported_extensions": sorted(DOC_TYPE_BY_SUFFIX),
        }

    if not resolved.exists():
        return {"opened": False, "reason": "file_not_found", "path": str(resolved)}

    _co_initialize()
    try:
        app = _get_app(create=True)
        app.Visible = visible
        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        doc = app.OpenDoc6(str(resolved), doc_type, 0, "", errors, warnings)
        return {
            "opened": doc is not None,
            "path": str(resolved),
            "visible": _bool_value(getattr(app, "Visible", False)),
            "errors": int(errors.value),
            "warnings": int(warnings.value),
            "active_document": _doc_summary(doc),
        }
    finally:
        _co_uninitialize()


@mcp.tool()
def new_part(template_path: str | None = None) -> dict[str, Any]:
    """Create a new SolidWorks part from a template."""
    payload: dict[str, Any] = {}
    if template_path:
        payload["templatePath"] = str(Path(template_path).expanduser().resolve())
    else:
        payload["templatePath"] = str(DEFAULT_PART_TEMPLATE)
    return _run_bridge("new_part", payload)


@mcp.tool()
def create_sketch_on_plane(plane: str = "front") -> dict[str, Any]:
    """Start editing a sketch on the given base plane."""
    return _run_bridge("create_sketch_on_plane", {"plane": plane})


@mcp.tool()
def create_center_rectangle(
    center_x: float,
    center_y: float,
    corner_x: float,
    corner_y: float,
    center_z: float = 0.0,
    corner_z: float = 0.0,
) -> dict[str, Any]:
    """Create a center rectangle in the current sketch."""
    return _run_bridge(
        "create_center_rectangle",
        {
            "centerX": center_x,
            "centerY": center_y,
            "centerZ": center_z,
            "cornerX": corner_x,
            "cornerY": corner_y,
            "cornerZ": corner_z,
        },
    )


@mcp.tool()
def create_circle(
    center_x: float,
    center_y: float,
    radius: float,
    center_z: float = 0.0,
) -> dict[str, Any]:
    """Create a circle in the current sketch."""
    return _run_bridge(
        "create_circle",
        {
            "centerX": center_x,
            "centerY": center_y,
            "centerZ": center_z,
            "radius": radius,
        },
    )


@mcp.tool()
def add_dimension(
    orientation: str,
    location_x: float,
    location_y: float,
    location_z: float = 0.0,
    segment_index: int = 0,
    entity_name: str | None = None,
    method: str = "macro",
) -> dict[str, Any]:
    """Add a sketch dimension using the in-process macro path or the direct diagnostic path."""
    payload: dict[str, Any] = {
        "orientation": orientation,
        "locationX": location_x,
        "locationY": location_y,
        "locationZ": location_z,
        "segmentIndex": segment_index,
        "method": method,
    }
    if entity_name:
        payload["entityName"] = entity_name
    return _run_bridge("add_dimension", payload)


@mcp.tool()
def extrude_boss(depth: float) -> dict[str, Any]:
    """Extrude the latest sketch as a boss feature."""
    return _run_bridge("extrude_boss", {"depth": depth})


@mcp.tool()
def run_macro(
    macro_path: str,
    module_name: str = "",
    procedure_name: str = "",
    options: int = 0,
) -> dict[str, Any]:
    """Compatibility stub kept to preserve the original MCP surface without invoking unstable macro loaders."""
    requested_path = str(Path(macro_path).expanduser())
    return {
        "ok": False,
        "reason": "run_macro_disabled_on_host",
        "macroPath": requested_path,
        "moduleName": module_name,
        "procedureName": procedure_name,
        "options": options,
        "recommendedMethod": "create_rectangular_block|create_plate_with_holes|design_from_prompt",
        "detail": (
            "SolidWorks macro execution is disabled on this host because the .NET/VSTA macro "
            "loader can raise a Microsoft .NET Framework dialog and terminate SolidWorks."
        ),
    }


@mcp.tool()
def create_rectangular_block(
    width_mm: float,
    height_mm: float,
    depth_mm: float,
    plane: str = "front",
    template_path: str | None = None,
) -> dict[str, Any]:
    """Create a rectangular block part from millimeter dimensions."""
    steps: dict[str, Any] = {}
    steps["new_part"] = new_part(template_path=template_path)
    if not steps["new_part"].get("ok"):
        return _composite_result(steps, widthMm=width_mm, heightMm=height_mm, depthMm=depth_mm)

    steps["create_sketch_on_plane"] = create_sketch_on_plane(plane=plane)
    if not steps["create_sketch_on_plane"].get("ok"):
        return _composite_result(steps, widthMm=width_mm, heightMm=height_mm, depthMm=depth_mm)

    steps["create_center_rectangle"] = create_center_rectangle(
        center_x=0.0,
        center_y=0.0,
        corner_x=_mm_to_m(width_mm / 2.0),
        corner_y=_mm_to_m(height_mm / 2.0),
    )
    if not steps["create_center_rectangle"].get("ok"):
        return _composite_result(steps, widthMm=width_mm, heightMm=height_mm, depthMm=depth_mm)

    steps["extrude_boss"] = extrude_boss(depth=_mm_to_m(depth_mm))
    steps["active_document"] = active_document()
    return _composite_result(steps, widthMm=width_mm, heightMm=height_mm, depthMm=depth_mm)


@mcp.tool()
def create_plate_with_holes(
    width_mm: float,
    height_mm: float,
    thickness_mm: float,
    hole_diameter_mm: float,
    offset_x_mm: float,
    offset_y_mm: float,
    rows: int = 2,
    columns: int = 2,
    plane: str = "front",
    template_path: str | None = None,
) -> dict[str, Any]:
    """Create a rectangular plate with an array of through holes in one sketch."""
    if rows <= 0 or columns <= 0:
        return {"ok": False, "reason": "invalid_hole_grid", "rows": rows, "columns": columns}

    try:
        x_positions_mm = _axis_positions(columns, width_mm / 2.0, offset_x_mm)
        y_positions_mm = _axis_positions(rows, height_mm / 2.0, offset_y_mm)
    except ValueError as exc:
        return {"ok": False, "reason": "invalid_hole_offsets", "detail": str(exc)}

    steps: dict[str, Any] = {}
    steps["new_part"] = new_part(template_path=template_path)
    if not steps["new_part"].get("ok"):
        return _composite_result(steps, holeCount=0)

    steps["create_sketch_on_plane"] = create_sketch_on_plane(plane=plane)
    if not steps["create_sketch_on_plane"].get("ok"):
        return _composite_result(steps, holeCount=0)

    steps["create_center_rectangle"] = create_center_rectangle(
        center_x=0.0,
        center_y=0.0,
        corner_x=_mm_to_m(width_mm / 2.0),
        corner_y=_mm_to_m(height_mm / 2.0),
    )
    if not steps["create_center_rectangle"].get("ok"):
        return _composite_result(steps, holeCount=0)

    hole_results: list[dict[str, Any]] = []
    radius_m = _mm_to_m(hole_diameter_mm / 2.0)
    for y_mm in y_positions_mm:
        for x_mm in x_positions_mm:
            circle_result = create_circle(
                center_x=_mm_to_m(x_mm),
                center_y=_mm_to_m(y_mm),
                radius=radius_m,
            )
            hole_results.append(circle_result)
            if not circle_result.get("ok"):
                steps["create_circles"] = hole_results
                return _composite_result(steps, holeCount=len(hole_results))

    steps["create_circles"] = hole_results
    steps["extrude_boss"] = extrude_boss(depth=_mm_to_m(thickness_mm))
    steps["active_document"] = active_document()
    return _composite_result(
        steps,
        holeCount=len(hole_results),
        widthMm=width_mm,
        heightMm=height_mm,
        thicknessMm=thickness_mm,
        holeDiameterMm=hole_diameter_mm,
        rows=rows,
        columns=columns,
    )


@mcp.tool()
def design_from_prompt(prompt: str) -> dict[str, Any]:
    """Interpret a narrow natural-language part request and dispatch to a stable high-level tool."""
    normalized = prompt.strip()
    if not normalized:
        return {"ok": False, "reason": "empty_prompt"}

    triplet = _extract_triplet_mm(normalized)
    if triplet is None:
        return {"ok": False, "reason": "dimensions_not_found", "prompt": prompt}

    width_mm, height_mm, depth_or_thickness_mm = triplet
    has_holes = _contains_any(normalized, ["hole", "holes", "孔", "drill", "through hole"])
    if has_holes:
        hole_diameter_mm = _extract_first_mm(
            normalized,
            [
                r"(?:diameter|dia\.?|直径)\s*(\d+(?:\.\d+)?)\s*mm?",
                r"m(\d+(?:\.\d+)?)",
            ],
        )
        if hole_diameter_mm is None:
            return {"ok": False, "reason": "hole_diameter_not_found", "prompt": prompt}

        grid = _extract_grid(normalized)
        if grid is None:
            hole_count_match = re.search(r"(\d+)\s*(?:holes|孔)", normalized, re.IGNORECASE)
            hole_count = int(hole_count_match.group(1)) if hole_count_match else 4
            grid = (2, 2) if hole_count == 4 else (hole_count, 1)

        offset_mm = _extract_first_mm(
            normalized,
            [
                r"(?:offset|edge offset|from the nearest .*? edges?|距边)\s*(\d+(?:\.\d+)?)\s*mm?",
                r"(\d+(?:\.\d+)?)\s*mm?\s*(?:from the nearest .*? edges?|edge offset|距边)",
            ],
        )
        if offset_mm is None:
            offset_mm = 10.0

        result = create_plate_with_holes(
            width_mm=width_mm,
            height_mm=height_mm,
            thickness_mm=depth_or_thickness_mm,
            hole_diameter_mm=hole_diameter_mm,
            offset_x_mm=offset_mm,
            offset_y_mm=offset_mm,
            rows=grid[0],
            columns=grid[1],
        )
        return {
            "ok": result.get("ok", False),
            "shape": "plate_with_holes",
            "parsed": {
                "widthMm": width_mm,
                "heightMm": height_mm,
                "thicknessMm": depth_or_thickness_mm,
                "holeDiameterMm": hole_diameter_mm,
                "rows": grid[0],
                "columns": grid[1],
                "offsetMm": offset_mm,
            },
            "result": result,
        }

    result = create_rectangular_block(
        width_mm=width_mm,
        height_mm=height_mm,
        depth_mm=depth_or_thickness_mm,
    )
    return {
        "ok": result.get("ok", False),
        "shape": "rectangular_block",
        "parsed": {
            "widthMm": width_mm,
            "heightMm": height_mm,
            "depthMm": depth_or_thickness_mm,
        },
        "result": result,
    }

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
