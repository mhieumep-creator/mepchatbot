"""
Text.py – Tạo Text / MText trong AutoCAD (hỗ trợ batch).

Hỗ trợ:
    - Tạo Text (single-line text)
    - Tạo MText (multi-line text)
    - Batch: tạo nhiều text cùng lúc
    - Thiết lập Layer, Color, Height, Rotation, Style, Alignment

Sử dụng:
    from AutoCad.Drawing.Text import create_texts

    # Text đơn giản
    result = create_texts(texts=[
        {
            "content": "Hello AutoCAD",
            "insertion_point": [100, 200, 0],
            "height": 50,
        }
    ])

    # MText
    result = create_texts(texts=[
        {
            "content": "Dòng 1\\nDòng 2\\nDòng 3",
            "insertion_point": [100, 200, 0],
            "height": 50,
            "type": "mtext",
            "width": 500,
            "layer": "M-TEXT",
        }
    ])

    # Batch: nhiều text khác nhau
    result = create_texts(texts=[
        {"content": "Label A", "insertion_point": [0, 0, 0], "height": 30},
        {"content": "Label B", "insertion_point": [500, 0, 0], "height": 30,
         "color": 1, "rotation": 0.785},  # 45 độ
        {"content": "Ghi chú dài", "insertion_point": [1000, 0, 0],
         "height": 25, "type": "mtext", "width": 300},
    ])
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


def create_texts(
    texts: list[dict],
    create_layer_if_missing: bool = True,
) -> dict:
    """
    Tạo một hoặc nhiều Text / MText trong AutoCAD (batch).

    Args:
        texts: Danh sách text cần tạo. Mỗi phần tử là dict:
            {
                "content":          str,           # Nội dung text (bắt buộc)
                "insertion_point":  [x,y,z]|"x,y", # Toạ độ chèn (bắt buộc)
                "height":          float,          # Chiều cao text (mặc định 2.5)
                "type":            "text"|"mtext", # Loại text (mặc định "text")
                "width":           float | None,   # Chiều rộng MText (chỉ cho mtext)
                "layer":           str,            # Layer (mặc định "0")
                "color":           int | None,     # ACI color index (tuỳ chọn)
                "rotation":        float,          # Góc xoay (radian, mặc định 0.0)
                "style":           str | None,     # Text style name (tuỳ chọn)
            }
        create_layer_if_missing: Tự tạo layer nếu chưa tồn tại.

    Returns:
        Dict kết quả:
            {
                "success":  bool,
                "message":  str,
                "total":    int,
                "created":  int,
                "failed":   int,
                "details":  [{...}],
                "error":    str | None,
            }
    """
    if not texts:
        return make_error_result(
            "Danh sách text trống.", "EMPTY_TEXTS_LIST",
            total=0, created=0, failed=0, details=[],
        )

    try:
        import pythoncom  # noqa: F401
    except ImportError:
        return make_no_pywin32_result(
            total=len(texts), created=0, failed=len(texts), details=[],
        )

    with com_session():
        return _create_texts_inner(texts, create_layer_if_missing)


def _create_texts_inner(
    texts: list[dict],
    create_layer_if_missing: bool,
) -> dict:
    """Logic chính — chạy bên trong com_session."""
    from pywintypes import com_error

    # ── 1. Kết nối AutoCAD ──────────────────────────────────────────
    try:
        acad, doc, model_space = connect_acad()
    except Exception as e:
        return make_no_acad_result(
            e, total=len(texts), created=0, failed=len(texts), details=[],
        )

    # ── 2. Tạo trước các layer cần thiết ────────────────────────────
    layers_needed = {t.get("layer", "0") for t in texts}
    ensure_layers_batch(doc, layers_needed, create_layer_if_missing)

    # ── 3. Tạo từng text (batch) ────────────────────────────────────
    details = []
    created = 0
    failed = 0

    for idx, txt_spec in enumerate(texts):
        result = _create_single_text(doc, model_space, txt_spec, idx)
        details.append(result)
        if result["ok"]:
            created += 1
        else:
            failed += 1

    # ── 4. Regen ────────────────────────────────────────────────────
    regen(doc)

    # ── 5. Tổng hợp kết quả ────────────────────────────────────────
    total = len(texts)
    all_ok = (failed == 0)

    if all_ok:
        msg = f"Đã tạo thành công {created}/{total} text."
    elif created > 0:
        msg = f"Tạo text một phần: {created}/{total} thành công, {failed} thất bại."
    else:
        msg = f"Không thể tạo bất kỳ text nào ({total} thất bại)."

    logger.info(msg)

    return {
        "success": all_ok or created > 0,
        "message": msg,
        "total": total,
        "created": created,
        "failed": failed,
        "details": details,
        "error": None if all_ok else f"{failed}/{total} text thất bại.",
    }


def _create_single_text(doc, model_space, txt_spec: dict, index: int) -> dict:
    """
    Tạo 1 Text hoặc MText trong AutoCAD.

    Returns:
        {
            "index":     int,
            "ok":        bool,
            "object_id": int | None,
            "type":      str,
            "content":   str,
            "layer":     str | None,
            "error":     str | None,
        }
    """
    from pywintypes import com_error

    content = txt_spec.get("content", "")
    if not content:
        return _fail_text(index, error="content không được để trống.")

    text_type = txt_spec.get("type", "text").lower()
    if text_type not in ("text", "mtext"):
        return _fail_text(index, error=f"type '{text_type}' không hợp lệ. Dùng 'text' hoặc 'mtext'.")

    # ── Parse insertion point ───────────────────────────────────────
    try:
        pt = parse_point(txt_spec.get("insertion_point", [0, 0, 0]))
    except Exception as e:
        return _fail_text(index, error=f"insertion_point không hợp lệ: {e}")

    height = float(txt_spec.get("height", 2.5))
    layer = txt_spec.get("layer", "0")
    color = txt_spec.get("color")
    rotation = float(txt_spec.get("rotation", 0.0))
    style = txt_spec.get("style")

    insertion_var = make_variant_point(pt)

    try:
        if text_type == "mtext":
            text_obj = _create_mtext(
                model_space, insertion_var, content, height,
                txt_spec.get("width"), rotation
            )
        else:
            text_obj = _create_text(
                model_space, insertion_var, content, height, rotation
            )

        logger.info(
            f"[{index}] {text_type.upper()} '{content[:30]}...' tại "
            f"({pt[0]},{pt[1]},{pt[2]}) | height={height}"
        )
    except com_error as e:
        return _fail_text(index, error=f"Lỗi COM khi tạo {text_type}: {e}")
    except Exception as e:
        return _fail_text(index, error=f"Lỗi khi tạo {text_type}: {e}")

    # ── Layer ───────────────────────────────────────────────────────
    if layer and layer != "0":
        try:
            text_obj.Layer = layer
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt layer '{layer}': {e}")

    # ── Color ───────────────────────────────────────────────────────
    if color is not None:
        try:
            text_obj.Color = int(color)
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt color {color}: {e}")

    # ── Style ───────────────────────────────────────────────────────
    if style:
        try:
            text_obj.StyleName = style
        except Exception as e:
            logger.warning(f"[{index}] Không thể đặt style '{style}': {e}")

    # ── ObjectID ────────────────────────────────────────────────────
    try:
        obj_id = int(text_obj.ObjectID)
    except Exception:
        obj_id = None

    return {
        "index": index,
        "ok": True,
        "object_id": obj_id,
        "type": text_type,
        "content": content,
        "layer": layer,
        "error": None,
    }


def _create_text(model_space, insertion_var, content: str,
                 height: float, rotation: float):
    """Tạo single-line Text."""
    text_obj = model_space.AddText(content, insertion_var, height)
    if rotation != 0.0:
        text_obj.Rotation = rotation
    return text_obj


def _create_mtext(model_space, insertion_var, content: str,
                  height: float, width: float | None, rotation: float):
    """Tạo MText (multi-line)."""
    mtext_width = float(width) if width else 0.0
    text_obj = model_space.AddMText(insertion_var, mtext_width, content)
    text_obj.Height = height
    if rotation != 0.0:
        text_obj.Rotation = rotation
    return text_obj


def _fail_text(index: int, error: str = "") -> dict:
    """Tạo dict kết quả lỗi cho 1 text."""
    return {
        "index": index,
        "ok": False,
        "object_id": None,
        "type": None,
        "content": None,
        "layer": None,
        "error": error,
    }


# ── Chạy trực tiếp để test ──────────────────────────────────────────────────
if __name__ == "__main__":
    import json as _json

    test_texts = [
        {
            "content": "Test Text",
            "insertion_point": [0, 0, 0],
            "height": 50,
            "layer": "0",
        },
        {
            "content": "Test MText\nDòng 2\nDòng 3",
            "insertion_point": [500, 0, 0],
            "height": 30,
            "type": "mtext",
            "width": 300,
        },
    ]

    print("=" * 60)
    print(f"Test tạo {len(test_texts)} text")
    print("=" * 60)

    result = create_texts(test_texts)
    print(_json.dumps(result, indent=2, ensure_ascii=False))
