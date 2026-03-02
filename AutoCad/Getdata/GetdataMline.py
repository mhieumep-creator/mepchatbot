"""
GetdataMline.py – Quét chọn và lấy thông tin Mline trong AutoCAD.

Thông tin trả về cho mỗi Mline:
    - ObjectID, Layer, StartPoint, EndPoint
    - MlineScale, MlineStyle
    - Linetype, Color
    - Vertices (tất cả đỉnh)

Sử dụng:
    from AutoCad.Getdata.GetdataMline import get_mline_data

    result = get_mline_data()                                          # Quét chọn
    result = get_mline_data(object_ids=[...])                          # Theo ID
    result = get_mline_data(layer_filter="M-PIPE")                     # Lọc layer
    result = get_mline_data(layer_filter=["M-PIPE", "M-VENT"])         # Nhiều layer
"""

from AutoCad.Getdata._acad_common import (
    get_logger, com_session, connect_acad, collect_objects,
    make_no_pywin32_result, make_no_acad_result, make_no_selection_result,
    parse_flat_coords_3d, safe_get,
)

logger = get_logger(__name__)


def get_mline_data(
    object_ids: list[int] | None = None,
    layer_filter: str | list[str] | None = None,
) -> dict:
    """
    Lấy thông tin Mline trong AutoCAD.

    Args:
        object_ids:   Danh sách ObjectID (tuỳ chọn). None → quét chọn.
        layer_filter: Lọc theo layer (str hoặc list[str]). None → không lọc.

    Returns:
        {
            "success": bool, "message": str, "total_selected": int,
            "mline_count": int, "mlines": [...], "error": str | None,
        }
    """
    try:
        import pythoncom
    except ImportError:
        return make_no_pywin32_result(mline_count=0, mlines=[])

    with com_session():
        return _get_mline_data_inner(object_ids, layer_filter)


def _get_mline_data_inner(object_ids, layer_filter) -> dict:
    from pywintypes import com_error

    try:
        acad, doc, ms = connect_acad()
    except com_error as e:
        return make_no_acad_result(e, mline_count=0, mlines=[])

    objects, total_selected = collect_objects(
        doc, object_ids, layer_filter, ss_prefix="MlineGet"
    )

    if objects is None:
        return make_no_selection_result(
            total=total_selected, mline_count=0, mlines=[]
        )

    mlines_data = []
    for obj in objects:
        try:
            if obj.ObjectName != "AcDbMline":
                continue
        except Exception:
            continue
        info = _extract_mline_info(obj)
        if info:
            mlines_data.append(info)

    mline_count = len(mlines_data)

    if mline_count == 0:
        msg = (
            f"Đã chọn {total_selected} đối tượng nhưng không có Mline nào."
            if total_selected > 0
            else "Không có đối tượng nào được chọn."
        )
        return {
            "success": False, "message": msg,
            "total_selected": total_selected,
            "mline_count": 0, "mlines": [],
            "error": "NO_MLINE_FOUND",
        }

    msg = f"Đã lấy thông tin {mline_count} Mline (từ {total_selected} đối tượng được chọn)."
    logger.info(msg)

    return {
        "success": True, "message": msg,
        "total_selected": total_selected,
        "mline_count": mline_count,
        "mlines": mlines_data,
        "error": None,
    }


def _extract_mline_info(mline_obj) -> dict | None:
    """Trích xuất thông tin từ một đối tượng Mline."""
    try:
        obj_id = int(mline_obj.ObjectID)
        layer = str(mline_obj.Layer)
        mline_scale = float(mline_obj.MLineScale)

        mline_style = str(safe_get(mline_obj, "StyleName", ""))
        linetype = str(safe_get(mline_obj, "Linetype", "ByLayer"))
        try:
            color = int(mline_obj.Color)
        except Exception:
            color = 256

        coords = list(mline_obj.Coordinates)
        vertices = parse_flat_coords_3d(coords)
        num_vertices = len(vertices)

        if num_vertices == 0:
            logger.warning(f"Mline ObjectID={obj_id} không có đỉnh nào.")
            return None

        start_point = vertices[0]
        end_point = vertices[-1]

        logger.info(
            f"Mline ID={obj_id} | Layer={layer} | Scale={mline_scale} | "
            f"Start={start_point} | End={end_point} | Vertices={num_vertices}"
        )

        return {
            "object_id": obj_id,
            "layer": layer,
            "start_point": start_point,
            "end_point": end_point,
            "mline_scale": mline_scale,
            "mline_style": mline_style,
            "num_vertices": num_vertices,
            "vertices": vertices,
            "linetype": linetype,
            "color": color,
        }

    except Exception as e:
        logger.error(f"Lỗi trích xuất Mline: {e}")
        return None


if __name__ == "__main__":
    import json as _json
    print("=" * 60)
    print("Test GetdataMline — Quét chọn trên bản vẽ AutoCAD")
    print("=" * 60)
    result = get_mline_data()
    print(_json.dumps(result, indent=2, ensure_ascii=False))
