"""
GetdataLine.py – Quét chọn và lấy thông tin Line trong AutoCAD.

Thông tin trả về cho mỗi Line:
    - ObjectID, Layer, StartPoint, EndPoint
    - Length, Angle, Thickness
    - Delta (vector hướng [dx, dy, dz])
    - Linetype, Color

Sử dụng:
    from AutoCad.Getdata.GetdataLine import get_line_data

    result = get_line_data()                                       # Quét chọn
    result = get_line_data(object_ids=[...])                       # Theo ID
    result = get_line_data(layer_filter="M-PIPE")                  # Lọc layer
"""

import math

from AutoCad.Getdata._acad_common import (
    get_logger, com_session, connect_acad, collect_objects,
    make_no_pywin32_result, make_no_acad_result, make_no_selection_result,
    parse_point_3d, safe_get,
)

logger = get_logger(__name__)


def get_line_data(
    object_ids: list[int] | None = None,
    layer_filter: str | list[str] | None = None,
) -> dict:
    """
    Lấy thông tin Line trong AutoCAD.

    Args:
        object_ids:   Danh sách ObjectID (tuỳ chọn). None → quét chọn.
        layer_filter: Lọc theo layer. None → không lọc.

    Returns:
        {
            "success": bool, "message": str, "total_selected": int,
            "line_count": int, "lines": [...], "error": str | None,
        }
    """
    try:
        import pythoncom
    except ImportError:
        return make_no_pywin32_result(line_count=0, lines=[])

    with com_session():
        return _get_line_data_inner(object_ids, layer_filter)


def _get_line_data_inner(object_ids, layer_filter) -> dict:
    from pywintypes import com_error

    try:
        acad, doc, ms = connect_acad()
    except com_error as e:
        return make_no_acad_result(e, line_count=0, lines=[])

    objects, total_selected = collect_objects(
        doc, object_ids, layer_filter, ss_prefix="LineGet"
    )

    if objects is None:
        return make_no_selection_result(
            total=total_selected, line_count=0, lines=[]
        )

    lines_data = []
    for obj in objects:
        try:
            if obj.ObjectName != "AcDbLine":
                continue
        except Exception:
            continue
        info = _extract_line_info(obj)
        if info:
            lines_data.append(info)

    line_count = len(lines_data)

    if line_count == 0:
        msg = (
            f"Đã chọn {total_selected} đối tượng nhưng không có Line nào."
            if total_selected > 0
            else "Không có đối tượng nào được chọn."
        )
        return {
            "success": False, "message": msg,
            "total_selected": total_selected,
            "line_count": 0, "lines": [],
            "error": "NO_LINE_FOUND",
        }

    msg = f"Đã lấy thông tin {line_count} Line (từ {total_selected} đối tượng được chọn)."
    logger.info(msg)

    return {
        "success": True, "message": msg,
        "total_selected": total_selected,
        "line_count": line_count,
        "lines": lines_data,
        "error": None,
    }


def _extract_line_info(line_obj) -> dict | None:
    """Trích xuất thông tin từ một đối tượng Line."""
    try:
        obj_id = int(line_obj.ObjectID)
        layer = str(line_obj.Layer)

        start_point = parse_point_3d(line_obj.StartPoint)
        end_point = parse_point_3d(line_obj.EndPoint)

        length = float(line_obj.Length)

        # Angle
        try:
            angle = float(line_obj.Angle)
        except Exception:
            dx = end_point[0] - start_point[0]
            dy = end_point[1] - start_point[1]
            angle = math.atan2(dy, dx)

        # Thickness
        try:
            thickness = float(line_obj.Thickness)
        except Exception:
            thickness = 0.0

        # Delta (vector hướng)
        delta = [
            end_point[0] - start_point[0],
            end_point[1] - start_point[1],
            end_point[2] - start_point[2],
        ]

        linetype = str(safe_get(line_obj, "Linetype", "ByLayer"))
        try:
            color = int(line_obj.Color)
        except Exception:
            color = 256

        logger.info(
            f"Line ID={obj_id} | Layer={layer} | Length={length:.2f} | "
            f"Start={start_point} | End={end_point}"
        )

        return {
            "object_id": obj_id,
            "layer": layer,
            "start_point": start_point,
            "end_point": end_point,
            "length": length,
            "angle": angle,
            "thickness": thickness,
            "delta": delta,
            "linetype": linetype,
            "color": color,
        }

    except Exception as e:
        logger.error(f"Lỗi trích xuất Line: {e}")
        return None


if __name__ == "__main__":
    import json as _json
    print("=" * 60)
    print("Test GetdataLine — Quét chọn trên bản vẽ AutoCAD")
    print("=" * 60)
    result = get_line_data()
    print(_json.dumps(result, indent=2, ensure_ascii=False))
