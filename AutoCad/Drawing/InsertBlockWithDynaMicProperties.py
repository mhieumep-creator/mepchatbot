"""
InsertBlockWithDynaMicProperties.py – Chèn Block (có Dynamic Properties) vào AutoCAD.

Hỗ trợ:
    - Chèn 1 block tại 1 điểm
    - Chèn nhiều block cùng lúc (batch) tại nhiều điểm khác nhau
    - Thiết lập Dynamic Block Properties sau khi chèn
    - Tạo layer mới nếu chưa tồn tại

Sử dụng:
    from AutoCad.Drawing.InsertBlockWithDynaMicProperties import insert_blocks

    # Một block
    result = insert_blocks(
        blocks=[{
            "block_name": "Valve",
            "insertion_point": [100, 200, 0],
            "x_scale": 1.0,
            "y_scale": 1.0,
            "z_scale": 1.0,
            "rotation": 0.0,
            "layer": "M-PIPE",
            "dynamic_properties": {"Size": 50, "Type": "Gate"}
        }]
    )

    # Nhiều block (batch)
    result = insert_blocks(
        blocks=[
            {"block_name": "Valve",  "insertion_point": [0, 0, 0]},
            {"block_name": "Valve",  "insertion_point": [600, 0, 0]},
            {"block_name": "Elbow", "insertion_point": [600, 600, 0],
             "dynamic_properties": {"Angle": 90}},
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


def insert_blocks(
    blocks: list[dict],
    create_layer_if_missing: bool = True,
) -> dict:
    """
    Chèn một hoặc nhiều Block (có hỗ trợ Dynamic Properties) vào AutoCAD.

    Args:
        blocks: Danh sách các block cần chèn. Mỗi phần tử là dict:
            {
                "block_name":          str,            # Tên block (đã có trong bản vẽ) hoặc đường dẫn .dwg
                "insertion_point":     [x, y, z],      # Toạ độ chèn  (z mặc định = 0)
                "x_scale":             float,          # Tỉ lệ X   (mặc định 1.0)
                "y_scale":             float,          # Tỉ lệ Y   (mặc định 1.0)
                "z_scale":             float,          # Tỉ lệ Z   (mặc định 1.0)
                "rotation":            float,          # Góc xoay (radian, mặc định 0.0)
                "layer":               str,            # Layer     (mặc định "0")
                "dynamic_properties":  {name: value},  # Dynamic Properties (tuỳ chọn)
            }
        create_layer_if_missing: Tự tạo layer nếu chưa tồn tại (mặc định True).

    Returns:
        Dict kết quả:
            {
                "success": bool,
                "message": str,
                "total":    int,
                "inserted": int,
                "failed":   int,
                "details":  [
                    {
                        "index":    int,
                        "ok":       bool,
                        "block_name": str,
                        "object_id":  int | None,
                        "layer":      str | None,
                        "dynamic_properties_set": list[str],
                        "dynamic_properties_failed": list[dict],
                        "error":    str | None,
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
        msg = f"Đã chèn thành công {inserted}/{total} block."
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
    Chèn 1 block và thiết lập Dynamic Properties.

    Returns:
        {
            "index": int,
            "ok": bool,
            "block_name": str,
            "object_id": int | None,
            "layer": str | None,
            "dynamic_properties_set": list[str],
            "dynamic_properties_failed": list[dict],
            "error": str | None,
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

    # ── Dynamic Properties ──────────────────────────────────────────
    dyn_props_spec = blk_spec.get("dynamic_properties", {})
    props_set = []
    props_failed = []

    if dyn_props_spec:
        props_set, props_failed = _set_dynamic_properties(
            block_ref, dyn_props_spec, index
        )

    return {
        "index": index,
        "ok": True,
        "block_name": block_name,
        "object_id": obj_id,
        "layer": layer,
        "dynamic_properties_set": props_set,
        "dynamic_properties_failed": props_failed,
        "error": None,
    }


def _set_dynamic_properties(
    block_ref, dyn_props_spec: dict, index: int
) -> tuple[list[str], list[dict]]:
    """
    Thiết lập Dynamic Properties cho một block reference.

    Returns:
        (props_set: list[str], props_failed: list[dict])
    """
    from pywintypes import com_error

    props_set = []
    props_failed = []

    try:
        is_dynamic = block_ref.IsDynamicBlock
    except Exception:
        is_dynamic = False

    if not is_dynamic:
        logger.warning(f"[{index}] Block không phải Dynamic Block – bỏ qua dynamic properties.")
        for name, value in dyn_props_spec.items():
            props_failed.append({
                "name": name,
                "value": value,
                "error": "Block không phải Dynamic Block",
            })
        return props_set, props_failed

    # Lấy danh sách Dynamic Properties
    try:
        dyn_props = block_ref.GetDynamicBlockProperties()
    except com_error as e:
        logger.error(f"[{index}] Lỗi khi lấy Dynamic Properties: {e}")
        for name, value in dyn_props_spec.items():
            props_failed.append({
                "name": name,
                "value": value,
                "error": f"Không thể lấy Dynamic Properties: {e}",
            })
        return props_set, props_failed

    # Tạo map tên → property object
    prop_map = {}
    try:
        for prop in dyn_props:
            try:
                prop_map[prop.PropertyName] = prop
            except Exception:
                pass
    except Exception as e:
        logger.error(f"[{index}] Lỗi khi duyệt Dynamic Properties: {e}")

    # Thiết lập từng property
    for name, value in dyn_props_spec.items():
        if name not in prop_map:
            # Liệt kê các property có sẵn để debug
            available = list(prop_map.keys())
            props_failed.append({
                "name": name,
                "value": value,
                "error": f"Property '{name}' không tồn tại. Các property có sẵn: {available}",
            })
            continue

        prop = prop_map[name]
        try:
            # Kiểm tra AllowedValues nếu có
            try:
                allowed = list(prop.AllowedValues)
                if allowed and value not in allowed:
                    logger.warning(
                        f"[{index}] Property '{name}': giá trị {value} "
                        f"không nằm trong AllowedValues {allowed}, vẫn thử gán."
                    )
            except Exception:
                pass  # Không có AllowedValues constraint

            prop.Value = value
            props_set.append(name)
            logger.info(f"[{index}] Dynamic Property '{name}' = {value}")

        except com_error as e:
            props_failed.append({
                "name": name,
                "value": value,
                "error": f"Lỗi COM: {e}",
            })
            logger.error(f"[{index}] Lỗi gán Dynamic Property '{name}': {e}")
        except Exception as e:
            props_failed.append({
                "name": name,
                "value": value,
                "error": str(e),
            })
            logger.error(f"[{index}] Lỗi gán Dynamic Property '{name}': {e}")

    return props_set, props_failed


def _fail_result(index: int, block_name: str, error: str) -> dict:
    """Tạo dict kết quả lỗi cho 1 block."""
    return {
        "index": index,
        "ok": False,
        "block_name": block_name,
        "object_id": None,
        "layer": None,
        "dynamic_properties_set": [],
        "dynamic_properties_failed": [],
        "error": error,
    }


# ── Chạy trực tiếp để test ──────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    # Test: chèn block
    # Thay block_name bằng tên block thực có trong bản vẽ AutoCAD
    test_blocks = [
        {
            "block_name": "TestBlock",
            "insertion_point": [100, 100, 0],
            "x_scale": 1.0,
            "y_scale": 1.0,
            "z_scale": 1.0,
            "rotation": 0.0,
            "layer": "0",
            "dynamic_properties": {},
        },
    ]

    print("=" * 60)
    print(f"Test chèn {len(test_blocks)} block")
    print("=" * 60)

    result = insert_blocks(test_blocks)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
