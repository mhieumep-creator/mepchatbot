"""
GetdataPolyline.py – Quét chọn và lấy thông tin Polyline trong AutoCAD.

Hỗ trợ: LWPolyline (2D), 2dPolyline, 3dPolyline.

Thông tin trả về cho mỗi Polyline:
    - ObjectID, ObjectName, Layer
    - StartPoint, EndPoint, Length, Closed
    - Area (nếu closed), Vertices, Bulges
    - ConstantWidth, Width mỗi segment
    - Linetype, Color

Sử dụng:
    from AutoCad.Getdata.GetdataPolyline import get_polyline_data

    result = get_polyline_data()                                      # Quét chọn
    result = get_polyline_data(object_ids=[...])                      # Theo ID
    result = get_polyline_data(layer_filter="M-PIPE")                 # Lọc layer
"""

from AutoCad.Getdata._acad_common import (
    get_logger, com_session, connect_acad, collect_objects,
    make_no_pywin32_result, make_no_acad_result, make_no_selection_result,
    parse_flat_coords_2d, parse_flat_coords_3d, safe_get,
)

logger = get_logger(__name__)

_POLYLINE_OBJECT_NAMES = {"AcDbPolyline", "AcDb2dPolyline", "AcDb3dPolyline"}


def get_polyline_data(
    object_ids: list[int] | None = None,
    layer_filter: str | list[str] | None = None,
) -> dict:
    """
    Lấy thông tin Polyline trong AutoCAD.

    Args:
        object_ids:   Danh sách ObjectID (tuỳ chọn). None → quét chọn.
        layer_filter: Lọc theo layer. None → không lọc.

    Returns:
        {
            "success": bool, "message": str, "total_selected": int,
            "polyline_count": int, "polylines": [...], "error": str | None,
        }
    """
    try:
        import pythoncom
    except ImportError:
        return make_no_pywin32_result(polyline_count=0, polylines=[])

    with com_session():
        return _get_polyline_data_inner(object_ids, layer_filter)


def _get_polyline_data_inner(object_ids, layer_filter) -> dict:
    from pywintypes import com_error

    try:
        acad, doc, ms = connect_acad()
    except com_error as e:
        return make_no_acad_result(e, polyline_count=0, polylines=[])

    objects, total_selected = collect_objects(
        doc, object_ids, layer_filter, ss_prefix="PolylineGet"
    )

    if objects is None:
        return make_no_selection_result(
            total=total_selected, polyline_count=0, polylines=[]
        )

    polylines_data = []
    for obj in objects:
        try:
            obj_name = obj.ObjectName
        except Exception:
            continue
        if obj_name not in _POLYLINE_OBJECT_NAMES:
            continue
        info = _extract_polyline_info(obj, obj_name)
        if info:
            polylines_data.append(info)

    polyline_count = len(polylines_data)

    if polyline_count == 0:
        msg = (
            f"Đã chọn {total_selected} đối tượng nhưng không có Polyline nào."
            if total_selected > 0
            else "Không có đối tượng nào được chọn."
        )
        return {
            "success": False, "message": msg,
            "total_selected": total_selected,
            "polyline_count": 0, "polylines": [],
            "error": "NO_POLYLINE_FOUND",
        }

    msg = f"Đã lấy thông tin {polyline_count} Polyline (từ {total_selected} đối tượng được chọn)."
    logger.info(msg)

    return {
        "success": True, "message": msg,
        "total_selected": total_selected,
        "polyline_count": polyline_count,
        "polylines": polylines_data,
        "error": None,
    }


def _extract_polyline_info(pl_obj, obj_name: str) -> dict | None:
    """Trích xuất thông tin từ một đối tượng Polyline."""
    try:
        obj_id = int(pl_obj.ObjectID)
        layer = str(pl_obj.Layer)

        # Properties chung
        try:
            length = float(pl_obj.Length)
        except Exception:
            length = 0.0

        try:
            closed = bool(pl_obj.Closed)
        except Exception:
            closed = False

        linetype = str(safe_get(pl_obj, "Linetype", "ByLayer"))
        try:
            color = int(pl_obj.Color)
        except Exception:
            color = 256

        # Vertices, Bulges, Width
        vertices = []
        bulges = []
        segment_widths = []
        constant_width = None
        area = None

        if obj_name == "AcDbPolyline":
            # LWPolyline – Coordinates trả về flat [x0,y0, x1,y1, ...]
            coords = list(pl_obj.Coordinates)
            vertices = parse_flat_coords_2d(coords)

            # Elevation → cập nhật Z cho tất cả vertices
            elevation = 0.0
            try:
                elevation = float(pl_obj.Elevation)
                for v in vertices:
                    v[2] = elevation
            except Exception:
                pass

            num_verts = len(vertices)
            for i in range(num_verts):
                # Bulge
                try:
                    bulges.append(float(pl_obj.GetBulge(i)))
                except Exception:
                    bulges.append(0.0)

                # Width per segment: (startWidth, endWidth)
                try:
                    width_result = pl_obj.GetWidth(i)
                    sw = float(width_result[0])
                    ew = float(width_result[1])
                except Exception:
                    sw, ew = 0.0, 0.0
                segment_widths.append({"start_width": sw, "end_width": ew})

            try:
                constant_width = float(pl_obj.ConstantWidth)
            except Exception:
                constant_width = None

            # Tạo danh sách điểm chi tiết (point_data) — gộp toạ độ + bulge + width
            point_data = []
            for i in range(num_verts):
                point_data.append({
                    "index": i,
                    "x": vertices[i][0],
                    "y": vertices[i][1],
                    "z": vertices[i][2],
                    "bulge": bulges[i] if i < len(bulges) else 0.0,
                    "start_width": segment_widths[i]["start_width"] if i < len(segment_widths) else 0.0,
                    "end_width": segment_widths[i]["end_width"] if i < len(segment_widths) else 0.0,
                })

        elif obj_name in ("AcDb2dPolyline", "AcDb3dPolyline"):
            # Heavy polyline – Coordinates trả về flat [x0,y0,z0, x1,y1,z1, ...]
            coords = list(pl_obj.Coordinates)
            vertices = parse_flat_coords_3d(coords)

            # Tạo point_data cho 2D/3D polyline
            point_data = []
            for i, v in enumerate(vertices):
                point_data.append({
                    "index": i,
                    "x": v[0],
                    "y": v[1],
                    "z": v[2],
                    "bulge": 0.0,
                    "start_width": 0.0,
                    "end_width": 0.0,
                })

        num_vertices = len(vertices)
        if num_vertices == 0:
            logger.warning(f"Polyline ObjectID={obj_id} không có đỉnh nào.")
            return None

        start_point = vertices[0]
        end_point = vertices[-1]

        # Area (chỉ khi closed)
        if closed:
            try:
                area = float(pl_obj.Area)
            except Exception:
                area = None

        logger.info(
            f"Polyline ID={obj_id} | Type={obj_name} | Layer={layer} | "
            f"Length={length:.2f} | Closed={closed} | Vertices={num_vertices}"
        )

        return {
            "object_id": obj_id,
            "object_name": obj_name,
            "layer": layer,
            "start_point": start_point,
            "end_point": end_point,
            "length": length,
            "closed": closed,
            "area": area,
            "num_vertices": num_vertices,
            "vertices": vertices,
            "point_data": point_data,
            "bulges": bulges,
            "segment_widths": segment_widths,
            "constant_width": constant_width,
            "linetype": linetype,
            "color": color,
        }

    except Exception as e:
        logger.error(f"Lỗi trích xuất Polyline: {e}")
        return None


if __name__ == "__main__":
    import json as _json
    print("=" * 60)
    print("Test GetdataPolyline — Quét chọn trên bản vẽ AutoCAD")
    print("=" * 60)
    result = get_polyline_data()
    print(_json.dumps(result, indent=2, ensure_ascii=False))
