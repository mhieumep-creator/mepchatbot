"""
Block.py – Chèn Block theo tên vào AutoCAD (batch).

Đơn giản hơn InsertBlockWithDynaMicProperties (không cần Dynamic Properties).
Tối ưu: chèn nhiều block cùng lúc, hỗ trợ block từ file .dwg bên ngoài.

Sử dụng:
    from AutoCad.Drawing.Block import insert_blocks_by_name

    # Một block
    result = insert_blocks_by_name(
        block_name="Valve",
        insertion_points=[[100, 200, 0]],
    )

    # Nhiều block cùng tên tại nhiều vị trí (batch)
    result = insert_blocks_by_name(
        block_name="Valve",
        insertion_points=[[0,0,0], [600,0,0], [600,600,0], "1200,0"],
        layer="M-PIPE",
        x_scale=1.0,
        rotation=1.5708,
    )

    # Nhiều block khác tên → dùng insert_blocks_multi
    result = insert_blocks_multi(blocks=[
        {"block_name": "Valve",  "point": [0,0,0],   "layer": "M-PIPE"},
        {"block_name": "Elbow", "point": [600,0,0], "layer": "M-DUCT", "rotation": 1.5708},
        {"block_name": "Tee",   "point": "1200,0",  "x_scale": 2.0},
    ])
"""

from AutoCad.Drawing._drawing_common import (
    get_logger,
    com_session,
    connect_acad,
    ensure_layers_batch,
    ensure_layer_exists,
    parse_point,
    make_variant_point,
    make_error_result,
    make_no_pywin32_result,
    make_no_acad_result,
    regen,
)

logger = get_logger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
#  API 1: insert_blocks_by_name — cùng tên block, nhiều điểm
# ═════════════════════════════════════════════════════════════════════════════

def insert_blocks_by_name(
    block_name: str,
    insertion_points: list,
    x_scale: float = 1.0,
    y_scale: float = 1.0,
    z_scale: float = 1.0,
    rotation: float = 0.0,
    layer: str = "0",
    create_layer_if_missing: bool = True,
) -> dict:
    """
    Chèn cùng 1 block tại nhiều điểm (batch).

    Args:
        block_name:        Tên block (đã có trong bản vẽ) hoặc đường dẫn .dwg.
        insertion_points:  Danh sách toạ độ: [[x,y,z], "x,y", ...].
        x_scale:           Tỉ lệ X (mặc định 1.0).
        y_scale:           Tỉ lệ Y (mặc định 1.0).
        z_scale:           Tỉ lệ Z (mặc định 1.0).
        rotation:          Góc xoay radian (mặc định 0.0).
        layer:             Layer (mặc định "0").
        create_layer_if_missing: Tự tạo layer nếu chưa có.

    Returns:
        {
            "success": bool, "message": str,
            "total": int, "inserted": int, "failed": int,
            "details": [{...}], "error": str|None,
        }
    """
    # Chuyển thành format multi
    blocks = []
    for pt in insertion_points:
        blocks.append({
            "block_name": block_name,
            "point": pt,
            "x_scale": x_scale,
            "y_scale": y_scale,
            "z_scale": z_scale,
            "rotation": rotation,
            "layer": layer,
        })

    return insert_blocks_multi(
        blocks=blocks,
        create_layer_if_missing=create_layer_if_missing,
    )


# ═════════════════════════════════════════════════════════════════════════════
#  API 2: insert_blocks_multi — nhiều block khác tên, khác tham số
# ═════════════════════════════════════════════════════════════════════════════

def insert_blocks_multi(
    blocks: list[dict],
    create_layer_if_missing: bool = True,
) -> dict:
    """
    Chèn nhiều block (có thể khác tên) vào AutoCAD (batch).

    Args:
        blocks: Danh sách block cần chèn. Mỗi phần tử:
            {
                "block_name":  str,            # Tên block hoặc đường dẫn .dwg
                "point":       [x,y,z]|"x,y",  # Toạ độ chèn
                "x_scale":     float,          # Mặc định 1.0
                "y_scale":     float,          # Mặc định 1.0
                "z_scale":     float,          # Mặc định 1.0
                "rotation":    float,          # Radian, mặc định 0.0
                "layer":       str,            # Mặc định "0"
            }
        create_layer_if_missing: Tự tạo layer nếu chưa có.

    Returns:
        Dict kết quả (xem insert_blocks_by_name).
    """
    if not blocks:
        return _empty_result("Danh sách block trống.", "EMPTY_BLOCKS")

    # Validate block_name
    for i, b in enumerate(blocks):
        if not b.get("block_name", "").strip():
            return _empty_result(
                f"Block #{i}: block_name không được để trống.", "EMPTY_BLOCK_NAME"
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
        return _insert_multi_inner(blocks, create_layer_if_missing)


def _insert_multi_inner(
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

    # ── 2. Tạo trước các layer cần thiết ────────────────────────────
    layers_needed = {b.get("layer", "0") for b in blocks}
    ensure_layers_batch(doc, layers_needed, create_layer_if_missing)

    # ── 3. Chèn từng block ──────────────────────────────────────────
    details = []
    inserted = 0
    failed = 0

    for idx, blk in enumerate(blocks):
        res = _insert_one(doc, model_space, blk, idx)
        details.append(res)
        if res["ok"]:
            inserted += 1
        else:
            failed += 1

    # ── 4. Regen ────────────────────────────────────────────────────
    regen(doc)

    # ── 5. Tổng hợp ────────────────────────────────────────────────
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


def _insert_one(doc, model_space, blk: dict, index: int) -> dict:
    """Chèn 1 block."""
    from pywintypes import com_error

    block_name = blk["block_name"].strip()

    # Parse point
    try:
        pt = parse_point(blk.get("point", [0, 0, 0]))
    except Exception as e:
        return _fail(index, block_name, f"point không hợp lệ: {e}")

    insertion_point = make_variant_point(pt)

    x_scale = float(blk.get("x_scale", 1.0))
    y_scale = float(blk.get("y_scale", 1.0))
    z_scale = float(blk.get("z_scale", 1.0))
    rotation = float(blk.get("rotation", 0.0))
    layer = blk.get("layer", "0")

    # ── Chèn block ──────────────────────────────────────────────────
    try:
        block_ref = model_space.InsertBlock(
            insertion_point, block_name,
            x_scale, y_scale, z_scale, rotation,
        )
    except com_error as e:
        return _fail(index, block_name, f"Lỗi COM: {e}")
    except Exception as e:
        return _fail(index, block_name, str(e))

    # ── Layer ───────────────────────────────────────────────────────
    if layer and layer != "0":
        try:
            block_ref.Layer = layer
        except Exception as e:
            logger.warning(f"[{index}] Không đặt được layer '{layer}': {e}")

    # ── ObjectID ────────────────────────────────────────────────────
    try:
        obj_id = int(block_ref.ObjectID)
    except Exception:
        obj_id = None

    logger.info(
        f"[{index}] '{block_name}' tại ({pt[0]},{pt[1]},{pt[2]}) "
        f"| Scale=({x_scale},{y_scale},{z_scale}) | Rot={rotation} "
        f"| Layer={layer} | ID={obj_id}"
    )

    return {
        "index": index,
        "ok": True,
        "block_name": block_name,
        "object_id": obj_id,
        "point": list(pt),
        "layer": layer,
        "error": None,
    }


# ── Hàm tiện ích ────────────────────────────────────────────────────────────


def _fail(index: int, block_name: str, error: str) -> dict:
    return {
        "index": index, "ok": False,
        "block_name": block_name, "object_id": None,
        "point": [], "layer": None, "error": error,
    }


def _empty_result(msg: str, code: str) -> dict:
    return make_error_result(
        message=msg, error=code,
        total=0, inserted=0, failed=0, details=[],
    )


# ── Test ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    # Test 1: cùng block, nhiều điểm
    print("=" * 60)
    print("Test insert_blocks_by_name")
    result = insert_blocks_by_name(
        block_name="TestBlock",
        insertion_points=[[0, 0, 0], [500, 0, 0], "1000,0"],
        layer="0",
    )
    print(_json.dumps(result, indent=2, ensure_ascii=False))

    # Test 2: nhiều block khác tên
    print("\n" + "=" * 60)
    print("Test insert_blocks_multi")
    result2 = insert_blocks_multi(blocks=[
        {"block_name": "TestBlock", "point": [0, 500, 0]},
        {"block_name": "TestBlock", "point": [500, 500, 0], "rotation": 1.5708},
    ])
    print(_json.dumps(result2, indent=2, ensure_ascii=False))
