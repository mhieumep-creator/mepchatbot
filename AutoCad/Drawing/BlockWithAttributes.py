"""
BlockWithAttributes.py – Chèn Block và thiết lập Attributes vào AutoCAD.

Hỗ trợ:
    - Chèn 1 hoặc nhiều block cùng lúc (batch)
    - Thiết lập giá trị Attributes (Tag → Value) sau khi chèn
    - Scale, Rotation, Layer cho từng block
    - Tạo layer mới nếu chưa tồn tại

Sử dụng:
    from AutoCad.Drawing.BlockWithAttributes import insert_blocks_with_attributes

    # Một block với attributes
    result = insert_blocks_with_attributes(
        blocks=[{
            "block_name": "TITLE_BLOCK",
            "insertion_point": [0, 0, 0],
            "layer": "ANNO",
            "attributes": {
                "PROJECT_NAME": "Chung cư ABC",
                "DRAWING_NO": "MEP-01",
                "SCALE": "1:100",
            }
        }]
    )

    # Nhiều block (batch)
    result = insert_blocks_with_attributes(
        blocks=[
            {
                "block_name": "ROOM_TAG",
                "insertion_point": [1000, 500, 0],
                "attributes": {"ROOM_NAME": "Phòng khách", "AREA": "25m²"},
            },
            {
                "block_name": "ROOM_TAG",
                "insertion_point": [3000, 500, 0],
                "attributes": {"ROOM_NAME": "Phòng ngủ", "AREA": "18m²"},
            },
        ]
    )
"""

from AutoCad.Drawing._drawing_common import (
    get_logger,
    com_session,
    connect_acad,
    ensure_layers_batch,
    parse_point,
    make_variant_point,
    make_error_result,
    make_no_pywin32_result,
    make_no_acad_result,
    regen,
)

logger = get_logger(__name__)


def insert_blocks_with_attributes(
    blocks: list[dict],
    create_layer_if_missing: bool = True,
) -> dict:
    """
    Chèn một hoặc nhiều Block và thiết lập Attributes vào AutoCAD.

    Args:
        blocks: Danh sách các block cần chèn. Mỗi phần tử là dict:
            {
                "block_name":       str,            # Tên block (đã có trong bản vẽ) hoặc đường dẫn .dwg
                "insertion_point":  [x, y, z],      # Toạ độ chèn  (z mặc định = 0)
                "x_scale":          float,          # Tỉ lệ X   (mặc định 1.0)
                "y_scale":          float,          # Tỉ lệ Y   (mặc định 1.0)
                "z_scale":          float,          # Tỉ lệ Z   (mặc định 1.0)
                "rotation":         float,          # Góc xoay (radian, mặc định 0.0)
                "layer":            str,            # Layer     (mặc định "0")
                "attributes":       {tag: value},   # Attributes: Tag → Value (tuỳ chọn)
            }
        create_layer_if_missing: Tự tạo layer nếu chưa tồn tại (mặc định True).

    Returns:
        Dict kết quả:
            {
                "success":  bool,
                "message":  str,
                "total":    int,
                "inserted": int,
                "failed":   int,
                "details":  [
                    {
                        "index":            int,
                        "ok":               bool,
                        "block_name":       str,
                        "object_id":        int | None,
                        "layer":            str | None,
                        "attributes_set":   list[str],     # Danh sách Tag đã gán thành công
                        "attributes_failed": list[dict],   # [{tag, value, error}, ...]
                        "error":            str | None,
                    },
                    ...
                ],
                "error": str | None,
            }
    """
    # ── Validate input ──────────────────────────────────────────────
    if not blocks:
        return make_error_result(
            "Danh sách block trống.", "EMPTY_BLOCKS_LIST",
            total=0, inserted=0, failed=0, details=[],
        )

    # ── Import COM ──────────────────────────────────────────────────
    try:
        import pythoncom  # noqa: F401
    except ImportError:
        return make_no_pywin32_result(
            total=len(blocks), inserted=0, failed=len(blocks), details=[],
        )

    # ── Chạy trong COM session ──────────────────────────────────────
    with com_session():
        return _insert_blocks_inner(blocks, create_layer_if_missing)


def _insert_blocks_inner(
    blocks: list[dict],
    create_layer_if_missing: bool,
) -> dict:
    """Logic chính — chạy sau khi COM đã được khởi tạo."""
    from pywintypes import com_error

    # ── 1. Kết nối AutoCAD ──────────────────────────────────────────
    try:
        acad, doc, model_space = connect_acad()
    except Exception as e:
        return make_no_acad_result(
            e, total=len(blocks), inserted=0, failed=len(blocks), details=[],
        )

    # ── 2. Thu thập các layer cần tạo trước ─────────────────────────
    layers_needed = {blk.get("layer", "0") for blk in blocks}
    ensure_layers_batch(doc, layers_needed, create_layer_if_missing)

    # ── 3. Chèn từng block (batch) ─────────────────────────────────
    details = []
    inserted = 0
    failed = 0

    for idx, blk_spec in enumerate(blocks):
        result = _insert_single_block(doc, model_space, blk_spec, idx)
        details.append(result)
        if result["ok"]:
            inserted += 1
        else:
            failed += 1

    # ── 4. Regen bản vẽ ─────────────────────────────────────────────
    regen(doc)

    # ── 5. Tổng hợp kết quả ────────────────────────────────────────
    total = len(blocks)
    all_ok = (failed == 0)

    if all_ok:
        msg = f"Đã chèn thành công {inserted}/{total} block (với Attributes)."
    elif inserted > 0:
        msg = f"Chèn block một phần: {inserted}/{total} thành công, {failed} thất bại."
    else:
        msg = f"Không thể chèn bất kỳ block nào ({total} thất bại)."

    logger.info(msg)

    return {
        "success": all_ok or inserted > 0,
        "message": msg,
        "total": total,
        "inserted": inserted,
        "failed": failed,
        "details": details,
        "error": None if all_ok else f"{failed}/{total} block thất bại.",
    }


def _insert_single_block(doc, model_space, blk_spec: dict, index: int) -> dict:
    """
    Chèn 1 block và thiết lập Attributes.

    Returns:
        {
            "index":             int,
            "ok":                bool,
            "block_name":        str,
            "object_id":         int | None,
            "layer":             str | None,
            "attributes_set":    list[str],
            "attributes_failed": list[dict],
            "error":             str | None,
        }
    """
    import pythoncom
    import win32com.client
    from pywintypes import com_error

    block_name = blk_spec.get("block_name", "")
    if not block_name:
        return _fail_result(index, "", "block_name không được để trống.")

    # ── Toạ độ chèn ────────────────────────────────────────────────
    raw_point = blk_spec.get("insertion_point", [0, 0, 0])
    try:
        pt = parse_point(raw_point)
    except Exception as e:
        return _fail_result(index, block_name, f"insertion_point không hợp lệ: {e}")

    insertion_point = make_variant_point(pt)

    # ── Scale & Rotation ────────────────────────────────────────────
    x_scale = float(blk_spec.get("x_scale", 1.0))
    y_scale = float(blk_spec.get("y_scale", 1.0))
    z_scale = float(blk_spec.get("z_scale", 1.0))
    rotation = float(blk_spec.get("rotation", 0.0))
    layer = blk_spec.get("layer", "0")

    # ── Chèn Block ──────────────────────────────────────────────────
    try:
        block_ref = model_space.InsertBlock(
            insertion_point,
            block_name,
            x_scale,
            y_scale,
            z_scale,
            rotation,
        )
        logger.info(
            f"[{index}] Đã chèn block '{block_name}' tại ({pt[0]}, {pt[1]}, {pt[2]})"
        )
    except com_error as e:
        return _fail_result(
            index, block_name,
            f"Lỗi COM khi chèn block: {e}"
        )
    except Exception as e:
        return _fail_result(index, block_name, f"Lỗi khi chèn block: {e}")

    # ── Đặt Layer ───────────────────────────────────────────────────
    try:
        if layer and layer != "0":
            block_ref.Layer = layer
    except com_error as e:
        logger.warning(f"[{index}] Không thể đặt layer '{layer}': {e}")

    # ── Lấy ObjectID ────────────────────────────────────────────────
    try:
        obj_id = int(block_ref.ObjectID)
    except Exception:
        obj_id = None

    # ── Thiết lập Attributes ────────────────────────────────────────
    attrs_spec = blk_spec.get("attributes", {})
    attrs_set = []
    attrs_failed = []

    if attrs_spec:
        attrs_set, attrs_failed = _set_attributes(
            block_ref, attrs_spec, index
        )

    return {
        "index": index,
        "ok": True,
        "block_name": block_name,
        "object_id": obj_id,
        "layer": layer,
        "attributes_set": attrs_set,
        "attributes_failed": attrs_failed,
        "error": None,
    }


def _set_attributes(
    block_ref, attrs_spec: dict, index: int
) -> tuple[list[str], list[dict]]:
    """
    Thiết lập Attributes cho một block reference.

    Tìm attribute theo Tag name (không phân biệt hoa thường)
    và gán giá trị TextString tương ứng.

    Returns:
        (attrs_set: list[str], attrs_failed: list[dict])
    """
    from pywintypes import com_error

    attrs_set = []
    attrs_failed = []

    # Kiểm tra block có Attributes không
    try:
        has_attrs = block_ref.HasAttributes
    except Exception:
        has_attrs = False

    if not has_attrs:
        logger.warning(f"[{index}] Block không có Attributes – bỏ qua.")
        for tag, value in attrs_spec.items():
            attrs_failed.append({
                "tag": tag,
                "value": value,
                "error": "Block không có Attributes",
            })
        return attrs_set, attrs_failed

    # Lấy danh sách Attributes
    try:
        attr_refs = block_ref.GetAttributes()
    except com_error as e:
        logger.error(f"[{index}] Lỗi khi lấy Attributes: {e}")
        for tag, value in attrs_spec.items():
            attrs_failed.append({
                "tag": tag,
                "value": value,
                "error": f"Không thể lấy Attributes: {e}",
            })
        return attrs_set, attrs_failed

    # Tạo map Tag (uppercase) → attribute object
    attr_map = {}
    try:
        for attr in attr_refs:
            try:
                tag_name = attr.TagString.upper()
                attr_map[tag_name] = attr
            except Exception:
                pass
    except Exception as e:
        logger.error(f"[{index}] Lỗi khi duyệt Attributes: {e}")

    # Gán giá trị từng attribute
    for tag, value in attrs_spec.items():
        tag_upper = tag.upper()
        if tag_upper not in attr_map:
            available = list(attr_map.keys())
            attrs_failed.append({
                "tag": tag,
                "value": value,
                "error": f"Tag '{tag}' không tồn tại. Các tag có sẵn: {available}",
            })
            continue

        attr_obj = attr_map[tag_upper]
        try:
            attr_obj.TextString = str(value)
            attrs_set.append(tag)
            logger.info(f"[{index}] Attribute '{tag}' = '{value}'")
        except com_error as e:
            attrs_failed.append({
                "tag": tag,
                "value": value,
                "error": f"Lỗi COM: {e}",
            })
            logger.error(f"[{index}] Lỗi gán Attribute '{tag}': {e}")
        except Exception as e:
            attrs_failed.append({
                "tag": tag,
                "value": value,
                "error": str(e),
            })
            logger.error(f"[{index}] Lỗi gán Attribute '{tag}': {e}")

    return attrs_set, attrs_failed


def _fail_result(index: int, block_name: str, error: str) -> dict:
    """Tạo dict kết quả lỗi cho 1 block."""
    return {
        "index": index,
        "ok": False,
        "block_name": block_name,
        "object_id": None,
        "layer": None,
        "attributes_set": [],
        "attributes_failed": [],
        "error": error,
    }


# ── Chạy trực tiếp để test ──────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    # Test: chèn block với attributes
    # Thay block_name bằng tên block thực có trong bản vẽ AutoCAD
    test_blocks = [
        {
            "block_name": "TITLE_BLOCK",
            "insertion_point": [0, 0, 0],
            "layer": "0",
            "attributes": {
                "PROJECT_NAME": "Test Project",
                "DRAWING_NO": "DWG-001",
            },
        },
    ]

    print("=" * 60)
    print(f"Test chèn {len(test_blocks)} block với Attributes")
    print("=" * 60)

    result = insert_blocks_with_attributes(test_blocks)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
