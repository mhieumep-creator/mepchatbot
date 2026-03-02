"""
GetdataLeader.py – Quét chọn và lấy thông tin Leader / MLeader trong AutoCAD.

Hỗ trợ: AcDbLeader (classic) và AcDbMLeader (multileader).

Thông tin trả về:
    - ObjectID, ObjectName, Layer
    - Vertices (đường dẫn)
    - TextString / Content
    - ArrowheadType / ArrowheadSize
    - ScaleFactor, Color

Sử dụng:
    from AutoCad.Getdata.GetdataLeader import get_leader_data

    result = get_leader_data()                                     # Quét chọn
    result = get_leader_data(object_ids=[...])                     # Theo ID
    result = get_leader_data(layer_filter="ANNO")                  # Lọc layer
"""

from AutoCad.Getdata._acad_common import (
    get_logger, com_session, connect_acad, collect_objects,
    make_no_pywin32_result, make_no_acad_result, make_no_selection_result,
    parse_point_3d, parse_flat_coords_3d, safe_get, convert_com_value,
)

logger = get_logger(__name__)

_LEADER_OBJECT_NAMES = {"AcDbLeader", "AcDbMLeader"}


def get_leader_data(
    object_ids: list[int] | None = None,
    layer_filter: str | list[str] | None = None,
) -> dict:
    """
    Lấy thông tin Leader / MLeader trong AutoCAD.

    Args:
        object_ids:   Danh sách ObjectID (tuỳ chọn). None → quét chọn.
        layer_filter: Lọc theo layer. None → không lọc.

    Returns:
        {
            "success": bool, "message": str, "total_selected": int,
            "leader_count": int, "leaders": [...], "error": str | None,
        }
    """
    try:
        import pythoncom
    except ImportError:
        return make_no_pywin32_result(leader_count=0, leaders=[])

    with com_session():
        return _get_leader_data_inner(object_ids, layer_filter)


def _get_leader_data_inner(object_ids, layer_filter) -> dict:
    from pywintypes import com_error

    try:
        acad, doc, ms = connect_acad()
    except com_error as e:
        return make_no_acad_result(e, leader_count=0, leaders=[])

    objects, total_selected = collect_objects(
        doc, object_ids, layer_filter, ss_prefix="LeaderGet"
    )

    if objects is None:
        return make_no_selection_result(
            total=total_selected, leader_count=0, leaders=[]
        )

    leaders_data = []
    for obj in objects:
        try:
            obj_name = obj.ObjectName
        except Exception:
            continue
        if obj_name not in _LEADER_OBJECT_NAMES:
            continue

        if obj_name == "AcDbLeader":
            info = _extract_leader_info(obj)
        else:
            info = _extract_mleader_info(obj)

        if info:
            leaders_data.append(info)

    leader_count = len(leaders_data)

    if leader_count == 0:
        msg = (
            f"Đã chọn {total_selected} đối tượng nhưng không có Leader/MLeader nào."
            if total_selected > 0
            else "Không có đối tượng nào được chọn."
        )
        return {
            "success": False, "message": msg,
            "total_selected": total_selected,
            "leader_count": 0, "leaders": [],
            "error": "NO_LEADER_FOUND",
        }

    msg = f"Đã lấy thông tin {leader_count} Leader (từ {total_selected} đối tượng được chọn)."
    logger.info(msg)

    return {
        "success": True, "message": msg,
        "total_selected": total_selected,
        "leader_count": leader_count,
        "leaders": leaders_data,
        "error": None,
    }


def _extract_leader_info(leader_obj) -> dict | None:
    """Trích xuất thông tin từ AcDbLeader (classic leader)."""
    try:
        obj_id = int(leader_obj.ObjectID)
        layer = str(leader_obj.Layer)

        # Vertices — lấy qua Coordinates (flat array)
        try:
            coords = list(leader_obj.Coordinates)
            vertices = parse_flat_coords_3d(coords)
        except Exception:
            vertices = []

        num_vertices = len(vertices)

        # StyleName
        style_name = str(safe_get(leader_obj, "StyleName", ""))

        # Type: 0=line, 1=spline
        try:
            leader_type = int(leader_obj.Type)
        except Exception:
            leader_type = 0

        # ArrowheadType
        try:
            arrowhead_type = int(leader_obj.ArrowheadType)
        except Exception:
            arrowhead_type = 0

        # ArrowheadSize
        arrowhead_size = float(safe_get(leader_obj, "ArrowheadSize", 0.0))

        # ScaleFactor
        scale_factor = float(safe_get(leader_obj, "ScaleFactor", 1.0))

        # Annotation (text nội dung liên kết — nếu có)
        annotation_text = ""
        try:
            annotation = leader_obj.Annotation
            if annotation:
                try:
                    annotation_text = str(annotation.TextString)
                except Exception:
                    annotation_text = str(safe_get(annotation, "TextOverride", ""))
        except Exception:
            pass

        # Color
        try:
            color = int(leader_obj.Color)
        except Exception:
            color = 256

        linetype = str(safe_get(leader_obj, "Linetype", "ByLayer"))

        logger.info(
            f"Leader ID={obj_id} | Layer={layer} | Vertices={num_vertices} | "
            f"Type={'Spline' if leader_type == 1 else 'Line'}"
        )

        return {
            "object_id": obj_id,
            "object_name": "AcDbLeader",
            "layer": layer,
            "num_vertices": num_vertices,
            "vertices": vertices,
            "leader_type": "spline" if leader_type == 1 else "line",
            "arrowhead_type": arrowhead_type,
            "arrowhead_size": arrowhead_size,
            "scale_factor": scale_factor,
            "style_name": style_name,
            "annotation_text": annotation_text,
            "linetype": linetype,
            "color": color,
        }

    except Exception as e:
        logger.error(f"Lỗi trích xuất Leader: {e}")
        return None


def _extract_mleader_info(mleader_obj) -> dict | None:
    """Trích xuất thông tin từ AcDbMLeader (multileader)."""
    try:
        obj_id = int(mleader_obj.ObjectID)
        layer = str(mleader_obj.Layer)

        # TextString (nội dung MLeader)
        text_string = str(safe_get(mleader_obj, "TextString", ""))

        # ContentType: 0=None, 1=BlockContent, 2=MTextContent
        try:
            content_type = int(mleader_obj.ContentType)
        except Exception:
            content_type = 2

        # LeaderType: 0=Invisible, 1=Straight, 2=Spline
        try:
            leader_type_val = int(mleader_obj.LeaderType)
        except Exception:
            leader_type_val = 1
        leader_type_map = {0: "invisible", 1: "straight", 2: "spline"}
        leader_type = leader_type_map.get(leader_type_val, "straight")

        # ArrowheadSize
        arrowhead_size = float(safe_get(mleader_obj, "ArrowheadSize", 0.0))

        # ScaleFactor
        scale_factor = float(safe_get(mleader_obj, "ScaleFactor", 1.0))

        # TextHeight
        text_height = float(safe_get(mleader_obj, "TextHeight", 0.0))

        # DoglegLength (đoạn ngang cuối)
        dogleg_length = float(safe_get(mleader_obj, "DoglegLength", 0.0))

        # LandingGap
        landing_gap = float(safe_get(mleader_obj, "LandingGap", 0.0))

        # StyleName
        style_name = str(safe_get(mleader_obj, "StyleName", ""))

        # Lấy vertices của leader lines
        # MLeader có thể có nhiều leader lines — lấy thông qua GetLeaderLineIndexes
        leader_lines_data = _extract_mleader_lines(mleader_obj, obj_id)

        # Block content (nếu ContentType == 1)
        block_name = ""
        if content_type == 1:
            try:
                block_name = str(mleader_obj.ContentBlockName)
            except Exception:
                block_name = ""

        # Color
        try:
            color = int(mleader_obj.Color)
        except Exception:
            color = 256

        linetype = str(safe_get(mleader_obj, "Linetype", "ByLayer"))

        content_type_map = {0: "none", 1: "block", 2: "mtext"}

        logger.info(
            f"MLeader ID={obj_id} | Layer={layer} | "
            f"Content='{text_string[:50]}' | Type={leader_type}"
        )

        return {
            "object_id": obj_id,
            "object_name": "AcDbMLeader",
            "layer": layer,
            "text_string": text_string,
            "content_type": content_type_map.get(content_type, "mtext"),
            "block_name": block_name,
            "leader_type": leader_type,
            "leader_lines": leader_lines_data,
            "arrowhead_size": arrowhead_size,
            "text_height": text_height,
            "scale_factor": scale_factor,
            "dogleg_length": dogleg_length,
            "landing_gap": landing_gap,
            "style_name": style_name,
            "linetype": linetype,
            "color": color,
        }

    except Exception as e:
        logger.error(f"Lỗi trích xuất MLeader: {e}")
        return None


def _extract_mleader_lines(mleader_obj, obj_id: int) -> list[dict]:
    """Trích xuất thông tin các leader lines của MLeader."""
    lines = []

    try:
        # GetLeaderCount
        leader_count = 0
        try:
            leader_count = int(mleader_obj.LeaderCount)
        except Exception:
            # Thử lấy qua method khác
            try:
                indexes = mleader_obj.GetLeaderLineIndexes(0)
                leader_count = len(indexes) if indexes else 0
            except Exception:
                pass

        if leader_count == 0:
            return lines

        # Với mỗi leader line, lấy vertices
        for i in range(leader_count):
            try:
                line_indexes = mleader_obj.GetLeaderLineIndexes(i)
                if not line_indexes:
                    continue
                for line_idx in line_indexes:
                    try:
                        vertex_count = mleader_obj.GetLeaderLineVertexCount(line_idx)
                        vertices = []
                        for v in range(vertex_count):
                            pt = mleader_obj.GetLeaderLineVertex(line_idx, v)
                            vertices.append(parse_point_3d(pt))
                        lines.append({
                            "leader_index": i,
                            "line_index": int(line_idx),
                            "vertices": vertices,
                        })
                    except Exception:
                        pass
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"[MLeader ID={obj_id}] Lỗi khi lấy leader lines: {e}")

    return lines


if __name__ == "__main__":
    import json as _json
    print("=" * 60)
    print("Test GetdataLeader — Quét chọn trên bản vẽ AutoCAD")
    print("=" * 60)
    result = get_leader_data()
    print(_json.dumps(result, indent=2, ensure_ascii=False))
