"""
_acad_common.py – Module dùng chung cho tất cả các hàm Getdata AutoCAD.

Cung cấp:
    - Encoding fix cho Windows console
    - Logger factory
    - COM initialization context manager
    - Kết nối AutoCAD
    - SelectOnScreen
    - Lấy object theo ObjectID
    - Lọc theo Layer
    - Hàm tạo kết quả lỗi chuẩn
    - Chuyển đổi giá trị COM
"""

import sys
import io
import logging
import time
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
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = get_logger("acad_common")


# ── COM context manager ────────────────────────────────────────────────────
@contextmanager
def com_session():
    """
    Context manager: CoInitialize → yield → CoUninitialize.

    Sử dụng:
        with com_session():
            acad, doc = connect_acad()
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
        (acad, doc, model_space) hoặc raise Exception nếu không kết nối được.
    """
    import win32com.client

    acad = win32com.client.Dispatch("AutoCAD.Application")
    acad.Visible = True
    doc = acad.ActiveDocument
    model_space = doc.ModelSpace
    logger.info(f"Đã kết nối AutoCAD – Bản vẽ: {doc.Name}")
    return acad, doc, model_space


# ── SelectOnScreen ──────────────────────────────────────────────────────────
def select_on_screen(doc, prefix: str = "GetData") -> tuple[list | None, int]:
    """
    Yêu cầu người dùng quét chọn trên bản vẽ (SelectOnScreen).

    Args:
        doc: AutoCAD Document COM object.
        prefix: Tiền tố cho tên SelectionSet (tránh trùng).

    Returns:
        (danh_sách_object, tổng_số_chọn) hoặc (None, 0) nếu huỷ.
    """
    from pywintypes import com_error

    ss_name = f"_{prefix}_{int(time.time())}"

    try:
        # Xoá SelectionSet cũ nếu trùng tên
        try:
            old_ss = doc.SelectionSets.Item(ss_name)
            old_ss.Delete()
        except com_error:
            pass

        ss = doc.SelectionSets.Add(ss_name)
        logger.info("Đang chờ người dùng quét chọn trên bản vẽ...")

        ss.SelectOnScreen()

        count = ss.Count
        logger.info(f"Người dùng đã chọn {count} đối tượng.")

        if count == 0:
            ss.Delete()
            return None, 0

        objects = []
        for i in range(count):
            try:
                objects.append(ss.Item(i))
            except Exception:
                pass

        try:
            ss.Delete()
        except Exception:
            pass

        return objects, count

    except com_error as e:
        logger.error(f"Lỗi khi SelectOnScreen: {e}")
        try:
            ss.Delete()
        except Exception:
            pass
        return None, 0


# ── Lấy object theo ObjectID ───────────────────────────────────────────────
def get_objects_by_ids(doc, object_ids: list[int]) -> list | None:
    """
    Lấy danh sách đối tượng COM từ ObjectID.

    Returns:
        Danh sách objects hoặc None nếu không tìm thấy object nào.
    """
    from pywintypes import com_error

    objects = []
    for obj_id in object_ids:
        try:
            obj = doc.ObjectIdToObject(obj_id)
            objects.append(obj)
        except com_error as e:
            logger.warning(f"Không tìm thấy ObjectID {obj_id}: {e}")
        except Exception as e:
            logger.warning(f"Lỗi lấy ObjectID {obj_id}: {e}")

    return objects if objects else None


# ── Lọc theo Layer ──────────────────────────────────────────────────────────
def filter_by_layer(objects: list, layer_filter: str | list[str] | None) -> list:
    """
    Lọc danh sách objects theo layer.

    Args:
        objects: Danh sách COM objects.
        layer_filter: Tên layer (str), danh sách layer (list[str]),
                      hoặc None (không lọc).

    Returns:
        Danh sách objects sau khi lọc.
    """
    if layer_filter is None:
        return objects

    if isinstance(layer_filter, str):
        layer_filter = [layer_filter]

    # Chuẩn hoá về uppercase để so sánh
    layer_set = {l.upper() for l in layer_filter}

    filtered = []
    for obj in objects:
        try:
            obj_layer = str(obj.Layer).upper()
            if obj_layer in layer_set:
                filtered.append(obj)
        except Exception:
            pass

    return filtered


# ── Collect objects (luồng chung) ───────────────────────────────────────────
def collect_objects(
    doc,
    object_ids: list[int] | None,
    layer_filter: str | list[str] | None,
    ss_prefix: str = "GetData",
) -> tuple[list | None, int]:
    """
    Thu thập objects: từ ObjectID hoặc SelectOnScreen, rồi lọc layer.

    Returns:
        (objects, total_selected) — objects=None nếu không có gì.
    """
    if object_ids is not None:
        objects = get_objects_by_ids(doc, object_ids)
        total_selected = len(object_ids)
    else:
        objects, total_selected = select_on_screen(doc, prefix=ss_prefix)

    if objects is None:
        return None, 0

    # Lọc layer
    if layer_filter:
        objects = filter_by_layer(objects, layer_filter)
        if not objects:
            return None, total_selected

    return objects, total_selected


# ── Chuyển đổi giá trị COM ──────────────────────────────────────────────────
def convert_com_value(val) -> Any:
    """
    Chuyển đổi giá trị COM sang kiểu Python thuần.
    Xử lý: tuple, bytes, số, chuỗi, v.v.
    """
    if val is None:
        return None
    if isinstance(val, (int, float, str, bool)):
        return val
    if isinstance(val, (tuple, list)):
        return [convert_com_value(v) for v in val]
    if isinstance(val, bytes):
        try:
            return val.decode("utf-8")
        except Exception:
            return str(val)
    try:
        return str(val)
    except Exception:
        return repr(val)


# ── Hàm tạo kết quả lỗi chuẩn ─────────────────────────────────────────────
def make_error_result(
    message: str,
    error: str,
    total: int = 0,
    **extra_fields,
) -> dict:
    """Tạo dict kết quả lỗi chuẩn."""
    result = {
        "success": False,
        "message": message,
        "total_selected": total,
        "error": error,
    }
    result.update(extra_fields)
    return result


def make_no_pywin32_result(total: int = 0, **extra_fields) -> dict:
    """Kết quả lỗi khi thiếu pywin32."""
    return make_error_result(
        message="Thiếu thư viện pywin32. Cần cài: pip install pywin32",
        error="ImportError: pywin32 not installed",
        total=total,
        **extra_fields,
    )


def make_no_acad_result(error, total: int = 0, **extra_fields) -> dict:
    """Kết quả lỗi khi không kết nối được AutoCAD."""
    return make_error_result(
        message="Không thể kết nối AutoCAD. Hãy đảm bảo AutoCAD đang mở.",
        error=str(error),
        total=total,
        **extra_fields,
    )


def make_no_selection_result(total: int = 0, **extra_fields) -> dict:
    """Kết quả khi người dùng không chọn gì."""
    return make_error_result(
        message="Người dùng đã huỷ lựa chọn hoặc không chọn đối tượng nào.",
        error="NO_SELECTION",
        total=total,
        **extra_fields,
    )


# ── Parse point / coords helpers ────────────────────────────────────────────
def parse_point_3d(raw) -> list[float]:
    """Chuyển đổi raw COM point thành [x, y, z]."""
    pt = list(raw)
    return [float(pt[0]), float(pt[1]), float(pt[2]) if len(pt) > 2 else 0.0]


def parse_flat_coords_3d(coords: list | tuple) -> list[list[float]]:
    """Parse flat array [x0,y0,z0, x1,y1,z1, ...] → [[x,y,z], ...]"""
    coords = list(coords)
    vertices = []
    for i in range(0, len(coords), 3):
        vertices.append([
            float(coords[i]),
            float(coords[i + 1]),
            float(coords[i + 2]),
        ])
    return vertices


def parse_flat_coords_2d(coords: list | tuple) -> list[list[float]]:
    """Parse flat array [x0,y0, x1,y1, ...] → [[x,y,0], ...]"""
    coords = list(coords)
    vertices = []
    for i in range(0, len(coords), 2):
        vertices.append([
            float(coords[i]),
            float(coords[i + 1]),
            0.0,
        ])
    return vertices


# ── Safe property reader ────────────────────────────────────────────────────
def safe_get(obj, prop: str, default=None):
    """Đọc property COM an toàn, trả về default nếu lỗi."""
    try:
        return getattr(obj, prop)
    except Exception:
        return default
