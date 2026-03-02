"""
GetdataAll.py – Quét chọn và lấy thông tin TẤT CẢ đối tượng trong AutoCAD.

Tự động phân loại: Line, Polyline, Mline, Block, Text/MText, Leader/MLeader.
Trả về dict chứa tất cả loại, giúp AI không cần biết trước loại đối tượng.

Sử dụng:
    from AutoCad.Getdata.GetdataAll import get_all_data

    result = get_all_data()                                        # Quét chọn
    result = get_all_data(object_ids=[...])                        # Theo ID
    result = get_all_data(layer_filter="M-PIPE")                   # Lọc layer
"""

from AutoCad.Getdata._acad_common import (
    get_logger, com_session, connect_acad, collect_objects,
    make_no_pywin32_result, make_no_acad_result, make_no_selection_result,
)

# Import các hàm extract riêng lẻ
from AutoCad.Getdata.GetdataLine import _extract_line_info
from AutoCad.Getdata.GetdataPolyline import _extract_polyline_info, _POLYLINE_OBJECT_NAMES
from AutoCad.Getdata.GetdataMline import _extract_mline_info
from AutoCad.Getdata.GetdataBlock import _extract_block_info
from AutoCad.Getdata.GetdataText import _extract_text_info, _TEXT_OBJECT_NAMES
from AutoCad.Getdata.GetdataLeader import (
    _extract_leader_info, _extract_mleader_info, _LEADER_OBJECT_NAMES,
)

logger = get_logger(__name__)


def get_all_data(
    object_ids: list[int] | None = None,
    layer_filter: str | list[str] | None = None,
) -> dict:
    """
    Lấy thông tin TẤT CẢ đối tượng được chọn, tự động phân loại.

    Args:
        object_ids:   Danh sách ObjectID (tuỳ chọn). None → quét chọn.
        layer_filter: Lọc theo layer. None → không lọc.

    Returns:
        {
            "success":        bool,
            "message":        str,
            "total_selected": int,
            "summary": {
                "lines":      int,
                "polylines":  int,
                "mlines":     int,
                "blocks":     int,
                "texts":      int,
                "leaders":    int,
                "unknown":    int,
            },
            "lines":      [...],
            "polylines":  [...],
            "mlines":     [...],
            "blocks":     [...],
            "texts":      [...],
            "leaders":    [...],
            "unknown":    [{"object_id": int, "object_name": str, "layer": str}, ...],
            "error": str | None,
        }
    """
    try:
        import pythoncom
    except ImportError:
        return make_no_pywin32_result(
            summary={}, lines=[], polylines=[], mlines=[],
            blocks=[], texts=[], leaders=[], unknown=[],
        )

    with com_session():
        return _get_all_data_inner(object_ids, layer_filter)


def _get_all_data_inner(object_ids, layer_filter) -> dict:
    from pywintypes import com_error

    try:
        acad, doc, ms = connect_acad()
    except com_error as e:
        return make_no_acad_result(
            e, summary={}, lines=[], polylines=[], mlines=[],
            blocks=[], texts=[], leaders=[], unknown=[],
        )

    objects, total_selected = collect_objects(
        doc, object_ids, layer_filter, ss_prefix="AllGet"
    )

    if objects is None:
        return make_no_selection_result(
            total=total_selected,
            summary={}, lines=[], polylines=[], mlines=[],
            blocks=[], texts=[], leaders=[], unknown=[],
        )

    # Phân loại và extract
    lines = []
    polylines = []
    mlines = []
    blocks = []
    texts = []
    leaders = []
    unknown = []

    for obj in objects:
        try:
            obj_name = obj.ObjectName
        except Exception:
            continue

        info = None

        if obj_name == "AcDbLine":
            info = _extract_line_info(obj)
            if info:
                lines.append(info)

        elif obj_name in _POLYLINE_OBJECT_NAMES:
            info = _extract_polyline_info(obj, obj_name)
            if info:
                polylines.append(info)

        elif obj_name == "AcDbMline":
            info = _extract_mline_info(obj)
            if info:
                mlines.append(info)

        elif obj_name == "AcDbBlockReference":
            info = _extract_block_info(obj)
            if info:
                blocks.append(info)

        elif obj_name in _TEXT_OBJECT_NAMES:
            info = _extract_text_info(obj, obj_name)
            if info:
                texts.append(info)

        elif obj_name == "AcDbLeader":
            info = _extract_leader_info(obj)
            if info:
                leaders.append(info)

        elif obj_name == "AcDbMLeader":
            info = _extract_mleader_info(obj)
            if info:
                leaders.append(info)

        else:
            # Đối tượng không nhận diện — vẫn ghi nhận
            try:
                unk_info = {
                    "object_id": int(obj.ObjectID),
                    "object_name": obj_name,
                    "layer": str(obj.Layer),
                }
                unknown.append(unk_info)
            except Exception:
                pass

    total_extracted = (
        len(lines) + len(polylines) + len(mlines) + len(blocks)
        + len(texts) + len(leaders)
    )

    summary = {
        "lines": len(lines),
        "polylines": len(polylines),
        "mlines": len(mlines),
        "blocks": len(blocks),
        "texts": len(texts),
        "leaders": len(leaders),
        "unknown": len(unknown),
    }

    if total_extracted == 0 and len(unknown) == 0:
        msg = (
            f"Đã chọn {total_selected} đối tượng nhưng không trích xuất được dữ liệu."
            if total_selected > 0
            else "Không có đối tượng nào được chọn."
        )
        return {
            "success": False, "message": msg,
            "total_selected": total_selected,
            "summary": summary,
            "lines": [], "polylines": [], "mlines": [],
            "blocks": [], "texts": [], "leaders": [],
            "unknown": [],
            "error": "NO_DATA_EXTRACTED",
        }

    # Tạo message tóm tắt
    parts = []
    if lines:
        parts.append(f"{len(lines)} Line")
    if polylines:
        parts.append(f"{len(polylines)} Polyline")
    if mlines:
        parts.append(f"{len(mlines)} Mline")
    if blocks:
        parts.append(f"{len(blocks)} Block")
    if texts:
        parts.append(f"{len(texts)} Text")
    if leaders:
        parts.append(f"{len(leaders)} Leader")
    if unknown:
        parts.append(f"{len(unknown)} khác")

    msg = (
        f"Đã lấy thông tin {total_extracted} đối tượng "
        f"(từ {total_selected} được chọn): {', '.join(parts)}."
    )
    logger.info(msg)

    return {
        "success": True, "message": msg,
        "total_selected": total_selected,
        "summary": summary,
        "lines": lines,
        "polylines": polylines,
        "mlines": mlines,
        "blocks": blocks,
        "texts": texts,
        "leaders": leaders,
        "unknown": unknown,
        "error": None,
    }


if __name__ == "__main__":
    import json as _json
    print("=" * 60)
    print("Test GetdataAll — Quét chọn trên bản vẽ AutoCAD")
    print("Hãy chuyển sang AutoCAD và quét chọn bất kỳ đối tượng nào.")
    print("=" * 60)
    result = get_all_data()
    print(_json.dumps(result, indent=2, ensure_ascii=False))
