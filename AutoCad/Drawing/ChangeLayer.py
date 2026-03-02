"""
ChangeLayer.py – Thay đổi Layer của đối tượng AutoCAD theo ObjectID.

Hỗ trợ:
    - Thay đổi 1 đối tượng
    - Thay đổi nhiều đối tượng cùng lúc (batch)
    - Tự tạo layer mới nếu chưa tồn tại

Sử dụng:
    from AutoCad.Drawing.ChangeLayer import change_layer

    # Một đối tượng
    result = change_layer(object_ids=[2130050560], new_layer="M-PIPE")

    # Nhiều đối tượng
    result = change_layer(
        object_ids=[2130050560, 2130050624, 2130050688],
        new_layer="M-DUCT"
    )
"""

from AutoCad.Drawing._drawing_common import (
    get_logger,
    com_session,
    connect_acad,
    ensure_layer_exists,
    make_error_result,
    make_no_pywin32_result,
    make_no_acad_result,
)

logger = get_logger(__name__)


def change_layer(
    object_ids: list[int],
    new_layer: str,
    create_layer_if_missing: bool = True,
) -> dict:
    """
    Thay đổi Layer của một hoặc nhiều đối tượng AutoCAD theo ObjectID.

    Args:
        object_ids:              Danh sách ObjectID (số nguyên) của các đối tượng cần đổi layer.
        new_layer:               Tên layer mới.
        create_layer_if_missing: Tự tạo layer nếu chưa tồn tại (mặc định True).

    Returns:
        Dict kết quả:
            {
                "success": bool,
                "message": str,
                "total": int,           # Tổng số ID yêu cầu
                "changed": int,         # Số đối tượng đã đổi thành công
                "failed": int,          # Số đối tượng thất bại
                "details": [            # Chi tiết từng đối tượng
                    {"id": int, "ok": bool, "old_layer": str, "error": str|None},
                    ...
                ],
                "error": str | None
            }

    Ví dụ:
        result = change_layer([2130050560, 2130050624], "M-PIPE")
        if result["success"]:
            print(f"Đã đổi {result['changed']}/{result['total']} đối tượng")
    """
    # ── Validate input ──────────────────────────────────────────────
    if not object_ids:
        return make_error_result(
            "Danh sách ObjectID trống.", "EMPTY_OBJECT_IDS",
            total=0, changed=0, failed=0, details=[],
        )

    if not new_layer or not new_layer.strip():
        return make_error_result(
            "Tên layer không được để trống.", "EMPTY_LAYER_NAME",
            total=len(object_ids), changed=0, failed=len(object_ids), details=[],
        )

    new_layer = new_layer.strip()

    # ── Import COM ──────────────────────────────────────────────────
    try:
        import pythoncom  # noqa: F401
    except ImportError:
        return make_no_pywin32_result(
            total=len(object_ids), changed=0, failed=len(object_ids), details=[],
        )

    # ── Chạy trong COM session ──────────────────────────────────────
    with com_session():
        return _change_layer_inner(object_ids, new_layer, create_layer_if_missing)


def _change_layer_inner(
    object_ids: list[int],
    new_layer: str,
    create_layer_if_missing: bool,
) -> dict:
    """Logic chính — chạy sau khi COM đã được khởi tạo."""
    from pywintypes import com_error

    # ── 1. Kết nối AutoCAD ──────────────────────────────────────────
    try:
        acad, doc, model_space = connect_acad()
    except Exception as e:
        return make_no_acad_result(
            e, total=len(object_ids), changed=0, failed=len(object_ids), details=[],
        )

    # ── 2. Kiểm tra / tạo layer ────────────────────────────────────
    layer_exists = ensure_layer_exists(doc, new_layer, create_layer_if_missing)
    if not layer_exists:
        return make_error_result(
            f"Layer '{new_layer}' không tồn tại và không được phép tạo mới.",
            f"LAYER_NOT_FOUND: {new_layer}",
            total=len(object_ids), changed=0, failed=len(object_ids), details=[],
        )

    # ── 3. Đổi layer cho từng đối tượng (batch) ────────────────────
    details = []
    changed = 0
    failed = 0

    for obj_id in object_ids:
        result = _change_single_object_layer(doc, obj_id, new_layer)
        details.append(result)
        if result["ok"]:
            changed += 1
        else:
            failed += 1

    # ── 4. Tổng hợp kết quả ────────────────────────────────────────
    total = len(object_ids)
    all_ok = (failed == 0)

    if all_ok:
        msg = f"Đã đổi layer thành '{new_layer}' cho {changed}/{total} đối tượng."
    elif changed > 0:
        msg = f"Đổi layer một phần: {changed}/{total} thành công, {failed} thất bại."
    else:
        msg = f"Không thể đổi layer cho bất kỳ đối tượng nào ({total} thất bại)."

    logger.info(msg)

    return {
        "success": all_ok or changed > 0,
        "message": msg,
        "total": total,
        "changed": changed,
        "failed": failed,
        "details": details,
        "error": None if all_ok else f"{failed}/{total} đối tượng thất bại.",
    }


def _change_single_object_layer(doc, obj_id: int, new_layer: str) -> dict:
    """
    Đổi layer cho 1 đối tượng theo ObjectID.

    Returns:
        {"id": int, "ok": bool, "old_layer": str|None, "error": str|None}
    """
    from pywintypes import com_error

    try:
        # ObjectIdToObject: lấy đối tượng COM từ ObjectID (int)
        obj = doc.ObjectIdToObject(obj_id)
        old_layer = obj.Layer
        obj.Layer = new_layer
        logger.info(f"ID {obj_id}: '{old_layer}' → '{new_layer}' ({obj.ObjectName})")
        return {"id": obj_id, "ok": True, "old_layer": old_layer, "error": None}

    except com_error as e:
        logger.error(f"ID {obj_id}: Lỗi COM — {e}")
        return {"id": obj_id, "ok": False, "old_layer": None, "error": str(e)}
    except Exception as e:
        logger.error(f"ID {obj_id}: Lỗi — {e}")
        return {"id": obj_id, "ok": False, "old_layer": None, "error": str(e)}


# ── Chạy trực tiếp để test ──────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    # Test: đổi layer cho các đối tượng
    # Thay object_ids bằng ID thực từ AutoCAD
    test_ids = [2130050560]  # ← Thay bằng ID thật
    test_layer = "M-TEST"

    print("=" * 60)
    print(f"Test đổi layer cho {len(test_ids)} đối tượng → '{test_layer}'")
    print("=" * 60)

    result = change_layer(test_ids, test_layer)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
