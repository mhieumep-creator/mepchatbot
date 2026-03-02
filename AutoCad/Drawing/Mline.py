"""
Mline.py - Ve Mline trong AutoCAD thong qua lenh VON / VON_PPR.

Luong hoat dong:
    1. Nhan cau hinh Mline (points, scale, layer, style, justification)
    2. Ghi cau hinh vao file ListMlines.json
    3. Goi lenh VON hoac VON_PPR toi AutoCAD (khong truyen tham so)
    4. Addin AutoCAD se doc ListMlines.json va ve theo cau hinh

Su dung:
    from AutoCad.Drawing.Mline import create_mline_von, create_mline_von_ppr

    # Ong thoat nuoc (VON) - 1 duong
    result = create_mline_von(mlines=[{
        "Layer": "M-PIPE",
        "Scale": 25.0,
        "Points": [{"X": 0, "Y": 0}, {"X": 1000, "Y": 0}, {"X": 1000, "Y": 500}]
    }])

    # Ong cap nuoc (VON_PPR) - nhieu duong cung luc
    result = create_mline_von_ppr(mlines=[
        {
            "Layer": "M-PIPE", "Scale": 25.0,
            "Points": [{"X": 0, "Y": 0}, {"X": 1000, "Y": 0}]
        },
        {
            "Layer": "M-PIPE", "Scale": 15.0,
            "Points": [{"X": 1000, "Y": 0}, {"X": 1000, "Y": 800}]
        },
    ])
"""

import json
import os
import time
from typing import Union

from AutoCad.Drawing._drawing_common import (
    get_logger,
    com_session,
    make_error_result,
)

logger = get_logger(__name__)

# -- Duong dan file JSON cau hinh ----------------------------------------
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_JSON_PATH = os.path.join(_CURRENT_DIR, "Listjson", "ListMlines.Json")

# -- Lenh hop le ----------------------------------------------------------
_VALID_ACTIONS = frozenset({"VON", "VON_PPR"})


# =========================================================================
#  Ham tien ich noi bo
# =========================================================================

def _error_result(message: str, error: str, before: int = 0, after: int = 0) -> dict:
    """Tao dict ket qua loi chuan."""
    return make_error_result(
        message=message,
        error=error,
        entities_before=before,
        entities_after=after,
        entities_added=0,
    )


def _success_result(message: str, before: int, after: int) -> dict:
    """Tao dict ket qua thanh cong chuan."""
    return {
        "success": True,
        "message": message,
        "entities_before": before,
        "entities_after": after,
        "entities_added": after - before,
        "error": None,
    }


def _normalize_mlines(mlines: list[dict]) -> list[dict]:
    """
    Chuan hoa danh sach mline config ve dung format JSON can thiet.

    Moi mline dict can co:
        - Layer:         str   (mac dinh "0")
        - Style:         str   (mac dinh "STANDARD")
        - Scale:         float (mac dinh 25.0)
        - Justification: int   (mac dinh 1)
        - Points:        list[{"X": float, "Y": float}]

    Points ho tro nhieu dang dau vao:
        - [{"X": 0, "Y": 0}, ...]          -> chuan
        - [[0, 0], [1000, 0], ...]          -> chuyen doi
        - ["0,0", "1000,0", ...]            -> chuyen doi
    """
    result = []
    for spec in mlines:
        raw_points = spec.get("Points", spec.get("points", []))
        points = _normalize_points(raw_points)
        if points is None:
            raise ValueError(
                f"Points khong hop le: {raw_points}. "
                f"Can dang [{{'X': 0, 'Y': 0}}, ...] hoac [[0,0], ...] hoac ['0,0', ...]"
            )

        if len(points) < 2:
            raise ValueError(f"Can it nhat 2 diem, nhan duoc {len(points)}.")

        result.append({
            "Layer": spec.get("Layer", spec.get("layer", "0")),
            "Style": spec.get("Style", spec.get("style", spec.get("mlstyle", "STANDARD"))),
            "Scale": float(spec.get("Scale", spec.get("scale", spec.get("mlscale", 25.0)))),
            "Justification": int(spec.get("Justification", spec.get("justification", 1))),
            "Points": points,
        })

    return result


def _normalize_points(raw_points: list) -> list[dict] | None:
    """
    Chuyen doi points ve dang chuan [{"X": float, "Y": float}, ...].

    Ho tro:
        - [{"X": 0, "Y": 0}, ...]
        - [[0, 0], ...]
        - [(0, 0), ...]
        - ["0,0", ...]
    """
    result = []
    for pt in raw_points:
        try:
            if isinstance(pt, dict):
                x = float(pt.get("X", pt.get("x", 0)))
                y = float(pt.get("Y", pt.get("y", 0)))
                result.append({"X": x, "Y": y})
            elif isinstance(pt, (list, tuple)):
                if len(pt) < 2:
                    return None
                result.append({"X": float(pt[0]), "Y": float(pt[1])})
            elif isinstance(pt, str):
                coords = pt.replace(" ", "").split(",")
                if len(coords) < 2:
                    return None
                result.append({"X": float(coords[0]), "Y": float(coords[1])})
            else:
                return None
        except (ValueError, TypeError):
            return None
    return result


def _write_json(mlines_config: list[dict]) -> str:
    """
    Ghi cau hinh mlines vao file ListMlines.json.

    Returns:
        Duong dan file da ghi.

    Raises:
        IOError neu khong ghi duoc file.
    """
    # Dam bao thu muc ton tai
    os.makedirs(os.path.dirname(_JSON_PATH), exist_ok=True)

    with open(_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(mlines_config, f, indent=2, ensure_ascii=False)

    logger.info(f"Da ghi {len(mlines_config)} mline config vao {_JSON_PATH}")
    return _JSON_PATH


# =========================================================================
#  Goi AutoCAD - chi gui lenh VON hoac VON_PPR (khong truyen tham so)
# =========================================================================

def _execute_acad_command(action: str, total_mlines: int) -> dict:
    """
    Goi lenh VON hoac VON_PPR toi AutoCAD.
    Addin AutoCAD se tu doc ListMlines.json de lay cau hinh.

    Args:
        action:       "VON" hoac "VON_PPR"
        total_mlines: So luong mline trong JSON (de uoc luong wait time)

    Returns:
        Dict ket qua chuan.
    """
    try:
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
        from pywintypes import com_error  # noqa: F401
    except ImportError:
        return _error_result(
            "Thieu thu vien pywin32. Can cai: pip install pywin32",
            "ImportError: pywin32 not installed",
        )

    with com_session():
        return _execute_acad_command_inner(action, total_mlines)


def _execute_acad_command_inner(action: str, total_mlines: int) -> dict:
    """Logic gui lenh - chay ben trong com_session."""
    import win32com.client
    from pywintypes import com_error

    try:
        # 1. Ket noi AutoCAD
        try:
            acad = win32com.client.Dispatch("AutoCAD.Application")
            acad.Visible = True
            doc = acad.ActiveDocument
            logger.info(f"Da ket noi AutoCAD - Ban ve: {doc.Name}")
        except com_error as e:
            return _error_result(
                "Khong the ket noi AutoCAD. Hay dam bao AutoCAD dang mo.",
                str(e),
            )

        # 2. Huy lenh dang dang do
        try:
            doc.SendCommand("\x1b\x1b")
            time.sleep(0.2)
        except com_error:
            pass

        # 3. Dem entity truoc
        try:
            count_before = doc.ModelSpace.Count
        except com_error:
            count_before = -1
        logger.info(f"Entity truoc: {count_before}")

        # 4. Gui lenh - chi ten lenh, khong truyen tham so
        cmd = f"{action}\n"
        logger.info(f"Gui lenh: {action} (addin se doc ListMlines.json)")

        try:
            doc.SendCommand(cmd)
            logger.info("SendCommand hoan thanh.")
        except com_error as e:
            return _error_result(
                f"Loi COM khi gui lenh {action}.",
                str(e),
                before=count_before,
                after=count_before,
            )

        # 5. Cho addin xu ly - wait time ti le voi so mline
        wait = min(1.0 + 0.5 * total_mlines, 15.0)
        time.sleep(wait)

        # 6. Dem entity sau
        try:
            count_after = doc.ModelSpace.Count
        except com_error:
            count_after = -1
        logger.info(f"Entity sau: {count_after} (waited {wait:.2f}s)")

        # 7. Xac nhan ket qua
        added = count_after - count_before

        if added > 0:
            return _success_result(
                f"Da tao Mline ({action}) thanh cong! "
                f"Them {added} entity tu {total_mlines} mline config.",
                count_before,
                count_after,
            )
        elif added == 0 and count_before >= 0:
            return _error_result(
                f"Lenh {action} da gui nhung khong co entity moi. "
                f"Kiem tra addin AutoCAD va file ListMlines.json.",
                "NO_NEW_ENTITY",
                before=count_before,
                after=count_after,
            )
        else:
            return _success_result(
                f"Lenh {action} da gui voi {total_mlines} mline config "
                f"(khong the dem entity).",
                count_before,
                count_after,
            )

    except Exception as e:
        return _error_result(f"Loi khong xac dinh: {e}", str(e))


# =========================================================================
#  Logic chinh: Ghi JSON + Goi lenh
# =========================================================================

def _create_mline(action: str, mlines: list[dict]) -> dict:
    """
    Logic chung cho VON va VON_PPR:
        1. Chuan hoa va validate cau hinh
        2. Ghi vao ListMlines.json
        3. Goi lenh VON / VON_PPR toi AutoCAD

    Args:
        action: "VON" hoac "VON_PPR"
        mlines: Danh sach cau hinh mline

    Returns:
        Dict ket qua chuan.
    """
    if action not in _VALID_ACTIONS:
        return _error_result(
            f"Action '{action}' khong hop le. Dung 'VON' hoac 'VON_PPR'.",
            "INVALID_ACTION",
        )

    if not mlines:
        return _error_result(
            "Danh sach mlines rong.",
            "EMPTY_MLINES",
        )

    # 1. Chuan hoa config
    try:
        normalized = _normalize_mlines(mlines)
    except ValueError as e:
        return _error_result(str(e), "INVALID_CONFIG")

    # 2. Ghi file JSON
    try:
        json_path = _write_json(normalized)
        logger.info(f"Da ghi {len(normalized)} mline config vao {json_path}")
    except (IOError, OSError) as e:
        return _error_result(
            f"Khong the ghi file ListMlines.json: {e}",
            "JSON_WRITE_ERROR",
        )

    # 3. Goi lenh toi AutoCAD
    result = _execute_acad_command(action, len(normalized))

    if result["success"]:
        logger.info(result["message"])
    else:
        logger.error(result["message"])

    return result


# =========================================================================
#  Public API
# =========================================================================

def create_mline_von(mlines: list[dict]) -> dict:
    """
    Ve Mline ong thoat nuoc bang lenh "VON".

    Ghi cau hinh vao ListMlines.json roi goi lenh VON toi AutoCAD.
    Addin AutoCAD se doc JSON va ve tu dong.

    Args:
        mlines: Danh sach cau hinh mline, moi phan tu la dict:
            {
                "Layer": "M-PIPE",              # Ten layer (mac dinh "0")
                "Style": "STANDARD",            # MlineStyle (mac dinh "STANDARD")
                "Scale": 25.0,                  # MlScale (mac dinh 25.0)
                "Justification": 1,             # Justification (mac dinh 1)
                "Points": [                     # Danh sach diem (it nhat 2)
                    {"X": 0.0, "Y": 0.0},
                    {"X": 1000.0, "Y": 0.0},
                    {"X": 1000.0, "Y": 500.0}
                ]
            }

        Points ho tro nhieu dang:
            - [{"X": 0, "Y": 0}, ...]    -> chuan
            - [[0, 0], [1000, 0], ...]    -> tu chuyen doi
            - ["0,0", "1000,0", ...]      -> tu chuyen doi

    Returns:
        Dict ket qua chuan (success, message, entities_before/after/added, error).

    Vi du:
        result = create_mline_von(mlines=[{
            "Layer": "M-PIPE", "Scale": 50.0,
            "Points": [{"X": 0, "Y": 0}, {"X": 600, "Y": 0}, {"X": 600, "Y": 600}]
        }])
    """
    return _create_mline("VON", mlines)


def create_mline_von_ppr(mlines: list[dict]) -> dict:
    """
    Ve Mline ong cap nuoc bang lenh "VON_PPR".

    Ghi cau hinh vao ListMlines.json roi goi lenh VON_PPR toi AutoCAD.
    Addin AutoCAD se doc JSON va ve tu dong.

    Args:
        mlines: Danh sach cau hinh mline (cung format voi create_mline_von).

    Returns:
        Dict ket qua chuan.

    Vi du:
        result = create_mline_von_ppr(mlines=[{
            "Layer": "M-PIPE", "Scale": 25.0,
            "Points": [{"X": 0, "Y": 0}, {"X": 600, "Y": 0}]
        }])
    """
    return _create_mline("VON_PPR", mlines)


# -- Chay truc tiep de test -----------------------------------------------
if __name__ == "__main__":
    test_mlines = [
        {
            "Layer": "M-PIPE",
            "Style": "STANDARD",
            "Scale": 25.0,
            "Justification": 1,
            "Points": [
                {"X": 0.0, "Y": 0.0},
                {"X": 1000.0, "Y": 0.0},
                {"X": 1000.0, "Y": 500.0},
            ],
        },
        {
            "Layer": "M-PIPE",
            "Scale": 15.0,
            "Points": [
                {"X": 1000.0, "Y": 500.0},
                {"X": 1000.0, "Y": 1500.0},
                {"X": 2000.0, "Y": 1500.0},
            ],
        },
    ]

    print("=" * 60)
    print(f"Test tao Mline VON - {len(test_mlines)} mline config")
    print("=" * 60)

    result = create_mline_von(mlines=test_mlines)
    print(json.dumps(result, indent=2, ensure_ascii=False))
