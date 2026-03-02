"""
GetdataText.py – Quét chọn và lấy thông tin Text trong AutoCAD.

Hỗ trợ: AcDbText (single-line) và AcDbMText (multi-line).

Thông tin trả về:
    - ObjectID, ObjectName, Layer
    - TextString (nội dung), InsertionPoint
    - Height, Rotation, Width
    - StyleName, Alignment
    - Color

Sử dụng:
    from AutoCad.Getdata.GetdataText import get_text_data

    result = get_text_data()                                       # Quét chọn
    result = get_text_data(object_ids=[...])                       # Theo ID
    result = get_text_data(layer_filter="ANNO")                    # Lọc layer
"""

from AutoCad.Getdata._acad_common import (
    get_logger, com_session, connect_acad, collect_objects,
    make_no_pywin32_result, make_no_acad_result, make_no_selection_result,
    parse_point_3d, safe_get,
)

logger = get_logger(__name__)

_TEXT_OBJECT_NAMES = {"AcDbText", "AcDbMText"}


def get_text_data(
    object_ids: list[int] | None = None,
    layer_filter: str | list[str] | None = None,
) -> dict:
    """
    Lấy thông tin Text / MText trong AutoCAD.

    Args:
        object_ids:   Danh sách ObjectID (tuỳ chọn). None → quét chọn.
        layer_filter: Lọc theo layer. None → không lọc.

    Returns:
        {
            "success": bool, "message": str, "total_selected": int,
            "text_count": int, "texts": [...], "error": str | None,
        }
    """
    try:
        import pythoncom
    except ImportError:
        return make_no_pywin32_result(text_count=0, texts=[])

    with com_session():
        return _get_text_data_inner(object_ids, layer_filter)


def _get_text_data_inner(object_ids, layer_filter) -> dict:
    from pywintypes import com_error

    try:
        acad, doc, ms = connect_acad()
    except com_error as e:
        return make_no_acad_result(e, text_count=0, texts=[])

    objects, total_selected = collect_objects(
        doc, object_ids, layer_filter, ss_prefix="TextGet"
    )

    if objects is None:
        return make_no_selection_result(
            total=total_selected, text_count=0, texts=[]
        )

    texts_data = []
    for obj in objects:
        try:
            obj_name = obj.ObjectName
        except Exception:
            continue
        if obj_name not in _TEXT_OBJECT_NAMES:
            continue
        info = _extract_text_info(obj, obj_name)
        if info:
            texts_data.append(info)

    text_count = len(texts_data)

    if text_count == 0:
        msg = (
            f"Đã chọn {total_selected} đối tượng nhưng không có Text/MText nào."
            if total_selected > 0
            else "Không có đối tượng nào được chọn."
        )
        return {
            "success": False, "message": msg,
            "total_selected": total_selected,
            "text_count": 0, "texts": [],
            "error": "NO_TEXT_FOUND",
        }

    msg = f"Đã lấy thông tin {text_count} Text (từ {total_selected} đối tượng được chọn)."
    logger.info(msg)

    return {
        "success": True, "message": msg,
        "total_selected": total_selected,
        "text_count": text_count,
        "texts": texts_data,
        "error": None,
    }


def _extract_text_info(text_obj, obj_name: str) -> dict | None:
    """Trích xuất thông tin từ một đối tượng Text hoặc MText."""
    try:
        obj_id = int(text_obj.ObjectID)
        layer = str(text_obj.Layer)

        # TextString
        text_string = str(safe_get(text_obj, "TextString", ""))

        # InsertionPoint
        try:
            insertion_point = parse_point_3d(text_obj.InsertionPoint)
        except Exception:
            insertion_point = [0.0, 0.0, 0.0]

        # Height
        height = float(safe_get(text_obj, "Height", 0.0))

        # Rotation
        rotation = float(safe_get(text_obj, "Rotation", 0.0))

        # Color
        try:
            color = int(text_obj.Color)
        except Exception:
            color = 256

        # StyleName
        style_name = str(safe_get(text_obj, "StyleName", ""))

        if obj_name == "AcDbText":
            return _extract_dbtext(text_obj, obj_id, layer, text_string,
                                   insertion_point, height, rotation, color,
                                   style_name)
        else:  # AcDbMText
            return _extract_mtext(text_obj, obj_id, layer, text_string,
                                  insertion_point, height, rotation, color,
                                  style_name)

    except Exception as e:
        logger.error(f"Lỗi trích xuất Text: {e}")
        return None


def _extract_dbtext(text_obj, obj_id, layer, text_string,
                    insertion_point, height, rotation, color,
                    style_name) -> dict:
    """Trích xuất thông tin AcDbText (single-line text)."""

    # Alignment
    try:
        alignment = int(text_obj.Alignment)
    except Exception:
        alignment = 0

    # TextAlignmentPoint (điểm căn chỉnh thứ 2, khác InsertionPoint khi alignment != 0)
    try:
        align_point = parse_point_3d(text_obj.TextAlignmentPoint)
    except Exception:
        align_point = insertion_point

    # ScaleFactor (chiều rộng ký tự)
    scale_factor = float(safe_get(text_obj, "ScaleFactor", 1.0))

    # ObliqueAngle (góc nghiêng)
    oblique_angle = float(safe_get(text_obj, "ObliqueAngle", 0.0))

    # Thickness
    thickness = float(safe_get(text_obj, "Thickness", 0.0))

    logger.info(
        f"Text ID={obj_id} | Layer={layer} | Content='{text_string[:50]}' | "
        f"Height={height}"
    )

    return {
        "object_id": obj_id,
        "object_name": "AcDbText",
        "layer": layer,
        "text_string": text_string,
        "insertion_point": insertion_point,
        "alignment_point": align_point,
        "height": height,
        "rotation": rotation,
        "scale_factor": scale_factor,
        "oblique_angle": oblique_angle,
        "thickness": thickness,
        "alignment": alignment,
        "style_name": style_name,
        "color": color,
    }


def _extract_mtext(text_obj, obj_id, layer, text_string,
                   insertion_point, height, rotation, color,
                   style_name) -> dict:
    """Trích xuất thông tin AcDbMText (multi-line text)."""

    # Width (chiều rộng khung MText)
    width = float(safe_get(text_obj, "Width", 0.0))

    # AttachmentPoint (vị trí neo: TopLeft=1, MiddleCenter=5, ...)
    try:
        attachment_point = int(text_obj.AttachmentPoint)
    except Exception:
        attachment_point = 1

    # DrawingDirection
    try:
        drawing_direction = int(text_obj.DrawingDirection)
    except Exception:
        drawing_direction = 1  # LeftToRight

    # LineSpacingFactor
    line_spacing_factor = float(safe_get(text_obj, "LineSpacingFactor", 1.0))

    # BackgroundFill (có fill nền không)
    try:
        background_fill = bool(text_obj.BackgroundFill)
    except Exception:
        background_fill = False

    logger.info(
        f"MText ID={obj_id} | Layer={layer} | Content='{text_string[:50]}' | "
        f"Height={height} | Width={width}"
    )

    return {
        "object_id": obj_id,
        "object_name": "AcDbMText",
        "layer": layer,
        "text_string": text_string,
        "insertion_point": insertion_point,
        "height": height,
        "width": width,
        "rotation": rotation,
        "attachment_point": attachment_point,
        "drawing_direction": drawing_direction,
        "line_spacing_factor": line_spacing_factor,
        "background_fill": background_fill,
        "style_name": style_name,
        "color": color,
    }


if __name__ == "__main__":
    import json as _json
    print("=" * 60)
    print("Test GetdataText — Quét chọn trên bản vẽ AutoCAD")
    print("=" * 60)
    result = get_text_data()
    print(_json.dumps(result, indent=2, ensure_ascii=False))
