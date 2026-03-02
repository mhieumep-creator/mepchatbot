"""
DeleteEntities.py – Xoá đối tượng AutoCAD theo ObjectID (batch).

Hỗ trợ:
    - Xoá 1 đối tượng
    - Xoá nhiều đối tượng cùng lúc (batch)

Sử dụng:
    from AutoCad.Drawing.DeleteEntities import delete_entities

    # Xoá 1 đối tượng
    result = delete_entities(object_ids=[2130050560])

    # Xoá nhiều đối tượng
    result = delete_entities(object_ids=[2130050560, 2130050624, 2130050688])
"""

from AutoCad.Drawing._drawing_common import (
    get_logger,
    com_session,
    connect_acad,
    make_error_result,
    make_no_pywin32_result,
    make_no_acad_result,
    regen,
)

logger = get_logger(__name__)


def delete_entities(
    object_ids: list[int],
) -> dict:
    """
    Xoá một hoặc nhiều đối tượng AutoCAD theo ObjectID.

    Args:
        object_ids: Danh sách ObjectID (số nguyên) cần xoá.

    Returns:
        Dict kết quả:
            {
                "success":  bool,
                "message":  str,
                "total":    int,
                "deleted":  int,
                "failed":   int,
                "details":  [
                    {"id": int, "ok": bool, "object_name": str|None, "error": str|None},
                    ...
                ],
                "error":    str | None,
            }
    """
    if not object_ids:
        return make_error_result(
            "Danh sách ObjectID trống.", "EMPTY_OBJECT_IDS",
            total=0, deleted=0, failed=0, details=[],
        )

    try:
        import pythoncom  # noqa: F401
    except ImportError:
        return make_no_pywin32_result(
            total=len(object_ids), deleted=0, failed=len(object_ids), details=[],
        )

    with com_session():
        return _delete_inner(object_ids)


def _delete_inner(object_ids: list[int]) -> dict:
    """Logic chính — chạy bên trong com_session."""
    from pywintypes import com_error

    # ── 1. Kết nối AutoCAD ──────────────────────────────────────────
    try:
        acad, doc, model_space = connect_acad()
    except Exception as e:
        return make_no_acad_result(
            e, total=len(object_ids), deleted=0, failed=len(object_ids), details=[],
        )

    # ── 2. Xoá từng đối tượng ──────────────────────────────────────
    details = []
    deleted = 0
    failed = 0

    for obj_id in object_ids:
        result = _delete_single(doc, obj_id)
        details.append(result)
        if result["ok"]:
            deleted += 1
        else:
            failed += 1

    # ── 3. Regen ────────────────────────────────────────────────────
    regen(doc)

    # ── 4. Tổng hợp kết quả ────────────────────────────────────────
    total = len(object_ids)
    all_ok = (failed == 0)

    if all_ok:
        msg = f"Đã xoá thành công {deleted}/{total} đối tượng."
    elif deleted > 0:
        msg = f"Xoá một phần: {deleted}/{total} thành công, {failed} thất bại."
    else:
        msg = f"Không thể xoá bất kỳ đối tượng nào ({total} thất bại)."

    logger.info(msg)

    return {
        "success": all_ok or deleted > 0,
        "message": msg,
        "total": total,
        "deleted": deleted,
        "failed": failed,
        "details": details,
        "error": None if all_ok else f"{failed}/{total} đối tượng thất bại.",
    }


def _delete_single(doc, obj_id: int) -> dict:
    """
    Xoá 1 đối tượng theo ObjectID.

    Returns:
        {"id": int, "ok": bool, "object_name": str|None, "error": str|None}
    """
    from pywintypes import com_error

    try:
        obj = doc.ObjectIdToObject(obj_id)
        obj_name = obj.ObjectName
        obj.Delete()
        logger.info(f"ID {obj_id}: Đã xoá ({obj_name})")
        return {"id": obj_id, "ok": True, "object_name": obj_name, "error": None}

    except com_error as e:
        logger.error(f"ID {obj_id}: Lỗi COM — {e}")
        return {"id": obj_id, "ok": False, "object_name": None, "error": str(e)}
    except Exception as e:
        logger.error(f"ID {obj_id}: Lỗi — {e}")
        return {"id": obj_id, "ok": False, "object_name": None, "error": str(e)}


# ── Chạy trực tiếp để test ──────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    # Test: xoá đối tượng (thay bằng ObjectID thật)
    test_ids = [2130050560]

    print("=" * 60)
    print(f"Test xoá {len(test_ids)} đối tượng")
    print("=" * 60)

    result = delete_entities(test_ids)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
