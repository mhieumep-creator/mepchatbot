"""
_drawing_common.py – Module dùng chung cho tất cả các hàm Drawing AutoCAD.

Cung cấp:
    - Encoding fix cho Windows console
    - Logger factory
    - COM initialization context manager
    - Kết nối AutoCAD
    - Ensure layer exists
    - Load linetype
    - Parse point (2D/3D)
    - Hàm tạo kết quả lỗi / thành công chuẩn
"""

import sys
import io
import logging
from typing import Any
from contextlib import contextmanager


# ── Fix encoding cho Windows console ────────────────────────────────────────
def setup_encoding():
    """Fix stdout/stderr encoding thành UTF-8 trên Windows."""
    if sys.stdout.encoding != "utf-8":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
    if sys.stderr.encoding != "utf-8":
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )


setup_encoding()


# ── Logger factory ──────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    """Tạo logger chuẩn với StreamHandler → stderr."""
    _logger = logging.getLogger(name)
    if not _logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    return _logger


logger = get_logger("drawing_common")


# ── COM context manager ────────────────────────────────────────────────────
@contextmanager
def com_session():
    """
    Context manager: CoInitialize → yield → CoUninitialize.

    Sử dụng:
        with com_session():
            acad, doc, ms = connect_acad()
            ...
    """
    import pythoncom

    try:
        pythoncom.CoInitialize()
        logger.info("COM initialized (STA).")
    except Exception as e:
        logger.warning(f"CoInitialize warning: {e}")

    try:
        yield
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


# ── Kết nối AutoCAD ─────────────────────────────────────────────────────────
def connect_acad():
    """
    Kết nối tới AutoCAD đang chạy.

    Returns:
        (acad, doc, model_space)

    Raises:
        Exception nếu không kết nối được.
    """
    import win32com.client

    acad = win32com.client.Dispatch("AutoCAD.Application")
    acad.Visible = True
    doc = acad.ActiveDocument
    model_space = doc.ModelSpace
    logger.info(f"Đã kết nối AutoCAD – Bản vẽ: {doc.Name}")
    return acad, doc, model_space


# ── Ensure layer exists ────────────────────────────────────────────────────
def ensure_layer_exists(doc, layer_name: str, create_if_missing: bool = True) -> bool:
    """
    Kiểm tra layer có tồn tại hay không.
    Nếu chưa có và create_if_missing=True → tạo mới.

    Returns:
        True nếu layer tồn tại (hoặc đã tạo thành công).
    """
    from pywintypes import com_error

    try:
        doc.Layers.Item(layer_name)
        return True
    except com_error:
        if create_if_missing:
            try:
                doc.Layers.Add(layer_name)
                logger.info(f"Đã tạo layer mới: '{layer_name}'.")
                return True
            except com_error as e:
                logger.error(f"Không thể tạo layer '{layer_name}': {e}")
                return False
        return False


def ensure_layers_batch(doc, layer_names: set[str], create_if_missing: bool = True):
    """Tạo trước tất cả layer cần thiết (loại bỏ '0' và '')."""
    for name in layer_names - {"0", ""}:
        ensure_layer_exists(doc, name, create_if_missing)


# ── Load linetype ───────────────────────────────────────────────────────────
def load_linetype(doc, linetype_name: str):
    """Load linetype từ acad.lin / acadiso.lin nếu chưa có."""
    from pywintypes import com_error

    try:
        doc.Linetypes.Item(linetype_name)
        return  # Đã tồn tại
    except com_error:
        pass

    for lt_file in ("acad.lin", "acadiso.lin"):
        try:
            doc.Linetypes.Load(linetype_name, lt_file)
            logger.info(f"Đã load linetype '{linetype_name}' từ {lt_file}.")
            return
        except com_error:
            continue

    logger.warning(
        f"Không tìm thấy linetype '{linetype_name}' trong acad.lin / acadiso.lin."
    )


# ── Parse point ─────────────────────────────────────────────────────────────
def parse_point(raw) -> tuple[float, float, float]:
    """
    Chuyển đổi toạ độ đầu vào thành tuple (x, y, z).

    Hỗ trợ:
        - [x, y]   hoặc  [x, y, z]
        - (x, y)   hoặc  (x, y, z)
        - "x,y"    hoặc  "x,y,z"
        - None → ValueError

    Returns:
        (x, y, z) — z mặc định 0.0 nếu input chỉ có 2 thành phần.
    """
    if raw is None:
        raise ValueError("Toạ độ không được để trống.")
    if isinstance(raw, str):
        parts = [float(p.strip()) for p in raw.split(",")]
    elif isinstance(raw, (list, tuple)):
        parts = [float(p) for p in raw]
    else:
        raise ValueError(f"Kiểu dữ liệu không hỗ trợ: {type(raw)}")

    if len(parts) == 2:
        return (parts[0], parts[1], 0.0)
    elif len(parts) == 3:
        return (parts[0], parts[1], parts[2])
    else:
        raise ValueError(f"Cần 2 hoặc 3 toạ độ, nhận được {len(parts)}.")


def make_variant_point(pt: tuple[float, float, float]):
    """Tạo COM VARIANT point từ tuple (x, y, z)."""
    import pythoncom
    import win32com.client

    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8, pt
    )


# ── Kết quả lỗi / thành công chuẩn ─────────────────────────────────────────
def make_error_result(message: str, error: str, **extra) -> dict:
    """Tạo dict kết quả lỗi chuẩn."""
    result = {
        "success": False,
        "message": message,
        "error": error,
    }
    result.update(extra)
    return result


def make_no_pywin32_result(**extra) -> dict:
    """Kết quả lỗi khi thiếu pywin32."""
    return make_error_result(
        message="Thiếu thư viện pywin32. Cần cài: pip install pywin32",
        error="ImportError: pywin32 not installed",
        **extra,
    )


def make_no_acad_result(error, **extra) -> dict:
    """Kết quả lỗi khi không kết nối được AutoCAD."""
    return make_error_result(
        message="Không thể kết nối AutoCAD. Hãy đảm bảo AutoCAD đang mở.",
        error=str(error),
        **extra,
    )


def make_empty_result(message: str, error_code: str, **extra) -> dict:
    """Kết quả trả về khi input trống."""
    return make_error_result(
        message=message,
        error=error_code,
        **extra,
    )


# ── Regen bản vẽ ────────────────────────────────────────────────────────────
def regen(doc):
    """Regen bản vẽ (acAllViewports = 1)."""
    try:
        doc.Regen(1)
    except Exception:
        pass
