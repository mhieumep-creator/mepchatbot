"""
MoveEntities.py – Di chuyển / Sao chép đối tượng AutoCAD theo ObjectID.

Hỗ trợ:
    - Di chuyển 1 hoặc nhiều đối tượng (batch)
    - Sao chép 1 hoặc nhiều đối tượng (batch)
    - Sử dụng vector dịch chuyển (dx, dy, dz)

Sử dụng:
    from AutoCad.Drawing.MoveEntities import move_entities, copy_entities

    # Di chuyển 1 đối tượng
    result = move_entities(
        object_ids=[2130050560],
        displacement=[500, 300, 0],
    )

    # Di chuyển nhiều đối tượng cùng 1 vector
    result = move_entities(
        object_ids=[2130050560, 2130050624],
        displacement=[500, 300, 0],
    )

    # Sao chép đối tượng
    result = copy_entities(
        object_ids=[2130050560],
        displacement=[1000, 0, 0],
    )
"""

from AutoCad.Drawing._drawing_common import (
    get_logger,
    com_session,
    connect_acad,
    parse_point,
    make_variant_point,
    make_error_result,
    make_no_pywin32_result,
    make_no_acad_result,
    regen,
)

logger = get_logger(__name__)


def move_entities(
    object_ids: list[int],
    displacement: list | tuple | str,
) -> dict:
    """
    Di chuyển một hoặc nhiều đối tượng AutoCAD theo vector dịch chuyển.

    Args:
        object_ids:    Danh sách ObjectID cần di chuyển.
        displacement:  Vector dịch chuyển [dx, dy, dz] | "dx,dy,dz".

    Returns:
        Dict kết quả:
            {
                "success":  bool,
                "message":  str,
                "total":    int,
                "moved":    int,
                "failed":   int,
                "details":  [{...}],
                "error":    str | None,
            }
    """
    return _move_or_copy(object_ids, displacement, mode="move")


def copy_entities(
    object_ids: list[int],
    displacement: list | tuple | str,
) -> dict:
    """
    Sao chép một hoặc nhiều đối tượng AutoCAD theo vector dịch chuyển.

    Args:
        object_ids:    Danh sách ObjectID cần sao chép.
        displacement:  Vector dịch chuyển [dx, dy, dz] | "dx,dy,dz".

    Returns:
        Dict kết quả:
            {
                "success":  bool,
                "message":  str,
                "total":    int,
                "copied":   int,
                "failed":   int,
                "new_object_ids": list[int],
                "details":  [{...}],
                "error":    str | None,
            }
    """
    return _move_or_copy(object_ids, displacement, mode="copy")


def _move_or_copy(
    object_ids: list[int],
    displacement,
    mode: str,
) -> dict:
    """Logic chung cho Move và Copy."""
    action_vn = "di chuyển" if mode == "move" else "sao chép"
    count_key = "moved" if mode == "move" else "copied"

    if not object_ids:
        return make_error_result(
            "Danh sách ObjectID trống.", "EMPTY_OBJECT_IDS",
            total=0, **{count_key: 0}, failed=0, details=[],
        )

    # Parse displacement vector
    try:
        disp = parse_point(displacement)
    except Exception as e:
        return make_error_result(
            f"displacement không hợp lệ: {e}", "INVALID_DISPLACEMENT",
            total=len(object_ids), **{count_key: 0}, failed=len(object_ids), details=[],
        )

    try:
        import pythoncom  # noqa: F401
    except ImportError:
        return make_no_pywin32_result(
            total=len(object_ids), **{count_key: 0}, failed=len(object_ids), details=[],
        )

    with com_session():
        return _move_copy_inner(object_ids, disp, mode, action_vn, count_key)


def _move_copy_inner(
    object_ids: list[int],
    disp: tuple,
    mode: str,
    action_vn: str,
    count_key: str,
) -> dict:
    """Logic chính — chạy bên trong com_session."""
    from pywintypes import com_error

    # ── 1. Kết nối AutoCAD ──────────────────────────────────────────
    try:
        acad, doc, model_space = connect_acad()
    except Exception as e:
        return make_no_acad_result(
            e, total=len(object_ids), **{count_key: 0},
            failed=len(object_ids), details=[],
        )

    # ── 2. Tạo VARIANT points ──────────────────────────────────────
    origin = make_variant_point((0.0, 0.0, 0.0))
    dest = make_variant_point(disp)

    # ── 3. Xử lý từng đối tượng ────────────────────────────────────
    details = []
    success_count = 0
    failed = 0
    new_ids = []

    for obj_id in object_ids:
        result = _move_or_copy_single(doc, obj_id, origin, dest, mode)
        details.append(result)
        if result["ok"]:
            success_count += 1
            if mode == "copy" and result.get("new_object_id"):
                new_ids.append(result["new_object_id"])
        else:
            failed += 1

    # ── 4. Regen ────────────────────────────────────────────────────
    regen(doc)

    # ── 5. Tổng hợp kết quả ────────────────────────────────────────
    total = len(object_ids)
    all_ok = (failed == 0)

    if all_ok:
        msg = f"Đã {action_vn} thành công {success_count}/{total} đối tượng."
    elif success_count > 0:
        msg = (
            f"{action_vn.capitalize()} một phần: "
            f"{success_count}/{total} thành công, {failed} thất bại."
        )
    else:
        msg = f"Không thể {action_vn} bất kỳ đối tượng nào ({total} thất bại)."

    logger.info(msg)

    result_dict = {
        "success": all_ok or success_count > 0,
        "message": msg,
        "total": total,
        count_key: success_count,
        "failed": failed,
        "details": details,
        "error": None if all_ok else f"{failed}/{total} đối tượng thất bại.",
    }

    if mode == "copy":
        result_dict["new_object_ids"] = new_ids

    return result_dict


def _move_or_copy_single(doc, obj_id: int, origin, dest, mode: str) -> dict:
    """Di chuyển hoặc sao chép 1 đối tượng."""
    from pywintypes import com_error

    try:
        obj = doc.ObjectIdToObject(obj_id)
        obj_name = obj.ObjectName

        if mode == "move":
            obj.Move(origin, dest)
            logger.info(f"ID {obj_id}: Đã di chuyển ({obj_name})")
            return {
                "id": obj_id,
                "ok": True,
                "object_name": obj_name,
                "error": None,
            }
        else:  # copy
            new_obj = obj.Copy()
            new_obj.Move(origin, dest)
            try:
                new_id = int(new_obj.ObjectID)
            except Exception:
                new_id = None
            logger.info(f"ID {obj_id}: Đã sao chép ({obj_name}) → ID {new_id}")
            return {
                "id": obj_id,
                "ok": True,
                "object_name": obj_name,
                "new_object_id": new_id,
                "error": None,
            }

    except com_error as e:
        logger.error(f"ID {obj_id}: Lỗi COM — {e}")
        return {"id": obj_id, "ok": False, "object_name": None, "error": str(e)}
    except Exception as e:
        logger.error(f"ID {obj_id}: Lỗi — {e}")
        return {"id": obj_id, "ok": False, "object_name": None, "error": str(e)}


# ── Chạy trực tiếp để test ──────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    # Test move (thay bằng ObjectID thật)
    test_ids = [2130050560]
    test_disp = [500, 300, 0]

    print("=" * 60)
    print(f"Test move {len(test_ids)} đối tượng, displacement={test_disp}")
    print("=" * 60)

    result = move_entities(test_ids, test_disp)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
