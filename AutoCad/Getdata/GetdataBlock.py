"""
GetdataBlock.py – Quét chọn và lấy thông tin Block Reference trong AutoCAD.

Thông tin trả về cho mỗi Block:
    - ObjectID, BlockName, EffectiveName, Layer
    - InsertionPoint, Scale (X/Y/Z), Rotation
    - IsDynamicBlock
    - Dynamic Properties (toàn bộ: name, value, allowed_values, read_only)
    - Attributes (toàn bộ: tag, value, prompt, invisible, constant, ...)
    - BoundingBox, Color, Linetype

Sử dụng:
    from AutoCad.Getdata.GetdataBlock import get_block_data

    result = get_block_data()                                      # Quét chọn
    result = get_block_data(object_ids=[...])                      # Theo ID
    result = get_block_data(layer_filter="M-EQUIP")                # Lọc layer
"""

from typing import Any

from AutoCad.Getdata._acad_common import (
    get_logger, com_session, connect_acad, collect_objects, convert_com_value,
    make_no_pywin32_result, make_no_acad_result, make_no_selection_result,
    parse_point_3d, safe_get,
)

logger = get_logger(__name__)


def get_block_data(
    object_ids: list[int] | None = None,
    layer_filter: str | list[str] | None = None,
) -> dict:
    """
    Lấy thông tin Block Reference trong AutoCAD.

    Args:
        object_ids:   Danh sách ObjectID (tuỳ chọn). None → quét chọn.
        layer_filter: Lọc theo layer. None → không lọc.

    Returns:
        {
            "success": bool, "message": str, "total_selected": int,
            "block_count": int, "blocks": [...], "error": str | None,
        }
    """
    try:
        import pythoncom
    except ImportError:
        return make_no_pywin32_result(block_count=0, blocks=[])

    with com_session():
        return _get_block_data_inner(object_ids, layer_filter)


def _get_block_data_inner(object_ids, layer_filter) -> dict:
    from pywintypes import com_error

    try:
        acad, doc, ms = connect_acad()
    except com_error as e:
        return make_no_acad_result(e, block_count=0, blocks=[])

    objects, total_selected = collect_objects(
        doc, object_ids, layer_filter, ss_prefix="BlockGet"
    )

    if objects is None:
        return make_no_selection_result(
            total=total_selected, block_count=0, blocks=[]
        )

    blocks_data = []
    for obj in objects:
        try:
            if obj.ObjectName != "AcDbBlockReference":
                continue
        except Exception:
            continue
        info = _extract_block_info(obj)
        if info:
            blocks_data.append(info)

    block_count = len(blocks_data)

    if block_count == 0:
        msg = (
            f"Đã chọn {total_selected} đối tượng nhưng không có Block Reference nào."
            if total_selected > 0
            else "Không có đối tượng nào được chọn."
        )
        return {
            "success": False, "message": msg,
            "total_selected": total_selected,
            "block_count": 0, "blocks": [],
            "error": "NO_BLOCK_FOUND",
        }

    msg = f"Đã lấy thông tin {block_count} Block (từ {total_selected} đối tượng được chọn)."
    logger.info(msg)

    return {
        "success": True, "message": msg,
        "total_selected": total_selected,
        "block_count": block_count,
        "blocks": blocks_data,
        "error": None,
    }


def _extract_block_info(block_ref) -> dict | None:
    """Trích xuất thông tin từ một đối tượng Block Reference."""
    try:
        obj_id = int(block_ref.ObjectID)
        layer = str(block_ref.Layer)
        block_name = str(block_ref.Name)

        try:
            effective_name = str(block_ref.EffectiveName)
        except Exception:
            effective_name = block_name

        # Insertion Point
        try:
            raw_pt = block_ref.InsertionPoint
            if raw_pt is not None:
                insertion_point = parse_point_3d(raw_pt)
            else:
                insertion_point = [0.0, 0.0, 0.0]
        except Exception:
            # Fallback: thử lấy từng tọa độ riêng lẻ
            try:
                ix = float(safe_get(block_ref, "InsertionPoint", (0.0, 0.0, 0.0))[0])
                iy = float(safe_get(block_ref, "InsertionPoint", (0.0, 0.0, 0.0))[1])
                iz = float(safe_get(block_ref, "InsertionPoint", (0.0, 0.0, 0.0))[2])
                insertion_point = [ix, iy, iz]
            except Exception:
                insertion_point = [0.0, 0.0, 0.0]
                logger.warning(f"[Block ID={obj_id}] Không lấy được InsertionPoint")

        # Scale
        x_scale = float(safe_get(block_ref, "XScaleFactor", 1.0))
        y_scale = float(safe_get(block_ref, "YScaleFactor", 1.0))
        z_scale = float(safe_get(block_ref, "ZScaleFactor", 1.0))

        # Rotation
        rotation = float(safe_get(block_ref, "Rotation", 0.0))

        # Color, Linetype
        try:
            color = int(block_ref.Color)
        except Exception:
            color = 256
        linetype = str(safe_get(block_ref, "Linetype", "ByLayer"))

        # IsDynamicBlock
        try:
            is_dynamic = bool(block_ref.IsDynamicBlock)
        except Exception:
            is_dynamic = False

        # BoundingBox
        bounding_box = _extract_bounding_box(block_ref)

        # Dynamic Properties
        dynamic_properties = _extract_dynamic_properties(block_ref, is_dynamic, obj_id)

        # Attributes
        attributes = _extract_attributes(block_ref, obj_id)

        logger.info(
            f"Block ID={obj_id} | Name={block_name} | EffName={effective_name} | "
            f"Layer={layer} | Dynamic={is_dynamic} | "
            f"DynProps={len(dynamic_properties)} | Attrs={len(attributes)}"
        )

        return {
            "object_id": obj_id,
            "block_name": block_name,
            "effective_name": effective_name,
            "layer": layer,
            "insertion_point": insertion_point,
            "x_scale": x_scale,
            "y_scale": y_scale,
            "z_scale": z_scale,
            "rotation": rotation,
            "is_dynamic_block": is_dynamic,
            "bounding_box": bounding_box,
            "dynamic_properties": dynamic_properties,
            "attributes": attributes,
            "color": color,
            "linetype": linetype,
        }

    except Exception as e:
        logger.error(f"Lỗi trích xuất Block: {e}")
        return None


def _extract_bounding_box(block_ref) -> dict | None:
    """Lấy BoundingBox (min, max) của Block Reference."""
    try:
        min_pt, max_pt = block_ref.GetBoundingBox()
        return {
            "min": parse_point_3d(min_pt),
            "max": parse_point_3d(max_pt),
        }
    except Exception:
        return None


def _extract_dynamic_properties(block_ref, is_dynamic: bool, obj_id: int) -> list[dict]:
    """Trích xuất toàn bộ Dynamic Properties."""
    from pywintypes import com_error

    properties = []
    if not is_dynamic:
        return properties

    try:
        dyn_props = block_ref.GetDynamicBlockProperties()
    except (com_error, Exception) as e:
        logger.warning(f"[Block ID={obj_id}] Không thể lấy Dynamic Properties: {e}")
        return properties

    try:
        for prop in dyn_props:
            info = _extract_single_dynamic_property(prop, obj_id)
            if info:
                properties.append(info)
    except Exception as e:
        logger.warning(f"[Block ID={obj_id}] Lỗi khi duyệt Dynamic Properties: {e}")

    return properties


def _extract_single_dynamic_property(prop, obj_id: int) -> dict | None:
    """Trích xuất thông tin một Dynamic Property."""
    try:
        name = str(prop.PropertyName)

        try:
            value = convert_com_value(prop.Value)
        except Exception:
            value = None

        try:
            raw_allowed = prop.AllowedValues
            allowed_values = (
                [convert_com_value(v) for v in raw_allowed]
                if raw_allowed else []
            )
        except Exception:
            allowed_values = []

        try:
            read_only = bool(prop.ReadOnly)
        except Exception:
            read_only = False

        return {
            "name": name,
            "value": value,
            "allowed_values": allowed_values,
            "read_only": read_only,
        }

    except Exception as e:
        logger.warning(f"[Block ID={obj_id}] Lỗi đọc Dynamic Property: {e}")
        return None


def _extract_attributes(block_ref, obj_id: int) -> list[dict]:
    """Trích xuất toàn bộ Attributes."""
    from pywintypes import com_error

    attributes = []

    try:
        has_attrs = bool(block_ref.HasAttributes)
    except Exception:
        has_attrs = False

    if not has_attrs:
        return attributes

    try:
        attr_refs = block_ref.GetAttributes()
    except (com_error, Exception) as e:
        logger.warning(f"[Block ID={obj_id}] Không thể lấy Attributes: {e}")
        return attributes

    try:
        for attr in attr_refs:
            info = _extract_single_attribute(attr, obj_id)
            if info:
                attributes.append(info)
    except Exception as e:
        logger.warning(f"[Block ID={obj_id}] Lỗi khi duyệt Attributes: {e}")

    return attributes


def _extract_single_attribute(attr, obj_id: int) -> dict | None:
    """Trích xuất thông tin một Attribute."""
    try:
        tag = str(safe_get(attr, "TagString", ""))
        text_string = str(safe_get(attr, "TextString", ""))
        prompt = str(safe_get(attr, "PromptString", ""))

        try:
            invisible = bool(attr.Invisible)
        except Exception:
            invisible = False

        try:
            constant = bool(attr.Constant)
        except Exception:
            constant = False

        height = float(safe_get(attr, "Height", 0.0))
        rotation = float(safe_get(attr, "Rotation", 0.0))

        try:
            insertion_point = parse_point_3d(attr.InsertionPoint)
        except Exception:
            insertion_point = [0.0, 0.0, 0.0]

        return {
            "tag": tag,
            "value": text_string,
            "prompt": prompt,
            "invisible": invisible,
            "constant": constant,
            "text_string": text_string,
            "height": height,
            "rotation": rotation,
            "insertion_point": insertion_point,
        }

    except Exception as e:
        logger.warning(f"[Block ID={obj_id}] Lỗi đọc Attribute: {e}")
        return None


if __name__ == "__main__":
    import json as _json
    print("=" * 60)
    print("Test GetdataBlock — Quét chọn trên bản vẽ AutoCAD")
    print("=" * 60)
    result = get_block_data()
    print(_json.dumps(result, indent=2, ensure_ascii=False))
