import os
import asyncio
import json
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
import anthropic
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from AutoCad.Drawing.Mline import create_mline_von, create_mline_von_ppr
from AutoCad.Drawing.ChangeLayer import change_layer
from AutoCad.Drawing.InsertBlockWithDynaMicProperties import insert_blocks
from AutoCad.Drawing.Lines import create_lines
from AutoCad.Drawing.Block import insert_blocks_by_name, insert_blocks_multi
from AutoCad.Drawing.Polyline import create_polylines
from AutoCad.Drawing.Text import create_texts
from AutoCad.Drawing.DeleteEntities import delete_entities
from AutoCad.Drawing.MoveEntities import move_entities, copy_entities
from AutoCad.Drawing.BlockWithAttributes import insert_blocks_with_attributes
from AutoCad.Getdata.GetdataMline import get_mline_data
from AutoCad.Getdata.GetdataLine import get_line_data
from AutoCad.Getdata.GetdataPolyline import get_polyline_data
from AutoCad.Getdata.GetdataBlock import get_block_data
from AutoCad.Getdata.GetdataText import get_text_data
from AutoCad.Getdata.GetdataLeader import get_leader_data
from AutoCad.Getdata.GetdataAll import get_all_data
from AutoCad.Getdata.GetdataPickPoint import get_pick_point

# 1. Nạp system prompt từ file JSON
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(CURRENT_DIR, "system_prompt.json")
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    SYSTEM_PROMPTS = json.load(f)

# 2. Khởi tạo MCP Server với instructions (system prompt cho Claude Desktop)
mcp = FastMCP(
    "Claude-AutoCAD-Server",
    instructions=SYSTEM_PROMPTS.get("mcp_server_instructions", ""),
)

# 2. Nạp biến môi trường từ file .env (nếu có)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "Key.env")
load_dotenv(ENV_PATH)


# 3. Lấy API key từ biến môi trường CLAUDE_API_KEY (không hardcode key trong code)
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
if not CLAUDE_API_KEY:
    raise RuntimeError(
        f"Missing CLAUDE_API_KEY environment variable for Claude client. "
        f"Expected it in environment or in .env at: {ENV_PATH}"
    )

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
MODEL_NAME = "claude-sonnet-4-5-20250929"  # Hoặc model Claude phù hợp


@mcp.tool()
async def ask_claude(prompt: str) -> str:
    """Sử dụng Claude (anthropic) để hỗ trợ các tác vụ AutoCAD/MEP."""
    try:
        system_prompt = SYSTEM_PROMPTS.get("ask_claude_system", "")
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text if response.content else "Không có phản hồi từ Claude."
    except Exception as e:
        return f"Lỗi khi gọi Claude: {str(e)}"


# ── Helper chung cho draw_mline_von / draw_mline_von_ppr ────────────────────
async def _draw_mline(
    action: str,
    create_fn,
    mlines: list[dict],
) -> str:
    """Ghi config vào ListMlines.json và gọi lệnh VON/VON_PPR."""
    try:
        result = await asyncio.to_thread(
            create_fn,
            mlines=mlines,
        )
        if result["success"]:
            return (
                f"Da tao Mline ({action}) thanh cong voi {len(mlines)} cau hinh | "
                f"Entity them: {result['entities_added']} "
                f"(truoc={result['entities_before']}, sau={result['entities_after']})"
            )
        else:
            return (
                f"Tao Mline ({action}) that bai: {result['message']} | "
                f"Loi: {result.get('error', 'Khong ro')}"
            )
    except Exception as e:
        return f"Loi khi tao Mline ({action}): {str(e)}"


@mcp.tool()
async def draw_mline_von(
    mlines: list[dict],
) -> str:
    """
    Ve Mline trong AutoCAD bang lenh tuy chinh "VON". Tao cac duong ong thoat nuoc trong ban ve Autocad.
    Ghi cau hinh vao ListMlines.json roi goi lenh VON. Addin AutoCAD se doc JSON va ve tu dong.

    Args:
        mlines: Danh sach cau hinh mline, moi phan tu la 1 dict:
            {
                "Layer": "M-PIPE",              # Ten layer (mac dinh "0")
                "Style": "STANDARD",            # MlineStyle (mac dinh "STANDARD")
                "Scale": 25.0,                  # MlScale - kich thuoc ong (mac dinh 25.0)
                "Justification": 1,             # Justification (mac dinh 1)
                "Points": [                     # Danh sach diem (it nhat 2)
                    {"X": 0.0, "Y": 0.0},
                    {"X": 1000.0, "Y": 0.0},
                    {"X": 1000.0, "Y": 500.0}
                ]
            }

        Points ho tro nhieu dang:
            - [{"X": 0, "Y": 0}, ...]       -> chuan
            - [[0, 0], [1000, 0], ...]       -> tu chuyen doi
            - ["0,0", "1000,0", ...]         -> tu chuyen doi

    Vi du:
        mlines = [
            {"Layer": "M-PIPE", "Scale": 25.0, "Points": [{"X": 0, "Y": 0}, {"X": 1000, "Y": 0}, {"X": 1000, "Y": 500}]},
            {"Layer": "M-PIPE", "Scale": 15.0, "Points": [{"X": 1000, "Y": 500}, {"X": 1000, "Y": 1500}]}
        ]

    Returns:
        Thong bao ket qua.
    """
    return await _draw_mline("VON", create_mline_von, mlines)


@mcp.tool()
async def draw_mline_von_ppr(
    mlines: list[dict],
) -> str:
    """
    Ve Mline trong AutoCAD bang lenh tuy chinh "VON_PPR". Tao cac duong ong cap nuoc trong ban ve Autocad.
    Ghi cau hinh vao ListMlines.json roi goi lenh VON_PPR. Addin AutoCAD se doc JSON va ve tu dong.

    Args:
        mlines: Danh sach cau hinh mline (cung format voi draw_mline_von).
            {
                "Layer": "M-PIPE",
                "Style": "STANDARD",
                "Scale": 25.0,
                "Justification": 1,
                "Points": [{"X": 0, "Y": 0}, {"X": 600, "Y": 0}]
            }

    Returns:
        Thong bao ket qua.
    """
    return await _draw_mline("VON_PPR", create_mline_von_ppr, mlines)


@mcp.tool()
async def change_object_layer(
    object_ids: list[int],
    new_layer: str,
    create_layer_if_missing: bool = True,
) -> str:
    """
    Thay doi Layer cua mot hoac nhieu doi tuong AutoCAD theo ObjectID.
    Ho tro batch: truyen nhieu ObjectID de doi layer cung luc.
    Tu tao layer moi neu chua ton tai (mac dinh).
    Args:
        object_ids:              Danh sach ObjectID (so nguyen) cua cac doi tuong.
        new_layer:               Ten layer moi can chuyen sang.
        create_layer_if_missing: Tu tao layer neu chua ton tai (mac dinh True).
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            change_layer,
            object_ids=object_ids,
            new_layer=new_layer,
            create_layer_if_missing=create_layer_if_missing,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    details_str += f"  ID {d['id']}: '{d['old_layer']}' -> '{new_layer}' OK\n"
                else:
                    details_str += f"  ID {d['id']}: THAT BAI - {d['error']}\n"
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Thanh cong: {result['changed']} | That bai: {result['failed']}\n"
                f"{details_str}"
            )
        else:
            return f"Doi layer that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi doi layer: {str(e)}"


@mcp.tool()
async def insert_block_with_dynamic_properties(
    blocks: list[dict],
    create_layer_if_missing: bool = True,
) -> str:
    """
    Chen mot hoac nhieu Block (co ho tro Dynamic Properties) vao AutoCAD.
    Ho tro batch: truyen nhieu block de chen cung luc tai nhieu diem khac nhau.
    Tu tao layer moi neu chua ton tai (mac dinh).

    Args:
        blocks: Danh sach cac block can chen. Moi phan tu la dict:
            {
                "block_name":          str,            # Ten block (da co trong ban ve) hoac duong dan .dwg
                "insertion_point":     [x, y, z],      # Toa do chen (z mac dinh = 0)
                "x_scale":             float,          # Ti le X   (mac dinh 1.0)
                "y_scale":             float,          # Ti le Y   (mac dinh 1.0)
                "z_scale":             float,          # Ti le Z   (mac dinh 1.0)
                "rotation":            float,          # Goc xoay (radian, mac dinh 0.0)
                "layer":               str,            # Layer     (mac dinh "0")
                "dynamic_properties":  {name: value},  # Dynamic Properties (tuy chon)
            }
        create_layer_if_missing: Tu tao layer neu chua ton tai (mac dinh True).
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            insert_blocks,
            blocks=blocks,
            create_layer_if_missing=create_layer_if_missing,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    dp_info = ""
                    if d["dynamic_properties_set"]:
                        dp_info = f" | DynProps set: {d['dynamic_properties_set']}"
                    if d["dynamic_properties_failed"]:
                        dp_info += f" | DynProps failed: {[p['name'] for p in d['dynamic_properties_failed']]}"
                    details_str += (
                        f"  [{d['index']}] '{d['block_name']}' OK"
                        f" | ObjectID={d['object_id']} | Layer={d['layer']}{dp_info}\n"
                    )
                else:
                    details_str += f"  [{d['index']}] '{d['block_name']}' THAT BAI - {d['error']}\n"
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Thanh cong: {result['inserted']} | That bai: {result['failed']}\n"
                f"{details_str}"
            )
        else:
            return f"Chen block that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi chen block: {str(e)}"


@mcp.tool()
async def draw_lines(
    lines: list[dict],
    create_layer_if_missing: bool = True,
) -> str:
    """
    Ve mot hoac nhieu Line trong AutoCAD (batch).
    Ho tro ve nhieu line doc lap cung luc voi cac layer, color, linetype khac nhau.

    Args:
        lines: Danh sach cac line can ve. Moi phan tu la dict:
            {
                "start":     [x, y, z] | "x,y,z",   # Diem dau  (z mac dinh 0)
                "end":       [x, y, z] | "x,y,z",   # Diem cuoi (z mac dinh 0)
                "layer":     str,                    # Layer (mac dinh "0")
                "color":     int | None,             # ACI color index (tuy chon)
                "linetype":  str | None,             # Ten linetype (tuy chon, VD: "DASHED")
            }
        create_layer_if_missing: Tu tao layer neu chua ton tai (mac dinh True).
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            create_lines,
            lines=lines,
            create_layer_if_missing=create_layer_if_missing,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    details_str += (
                        f"  [{d['index']}] ({d['start']}) -> ({d['end']})"
                        f" | ObjectID={d['object_id']} | Layer={d['layer']} OK\n"
                    )
                else:
                    details_str += f"  [{d['index']}] THAT BAI - {d['error']}\n"
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Thanh cong: {result['drawn']} | That bai: {result['failed']}\n"
                f"{details_str}"
            )
        else:
            return f"Ve line that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi ve line: {str(e)}"


@mcp.tool()
async def get_mline_info(
    object_ids: list[int] | None = None,
) -> str:
    """
    Lay thong tin Mline trong AutoCAD.
    Neu khong truyen object_ids → yeu cau nguoi dung quet chon tren ban ve.
    Chi loc nhung doi tuong la Mline.

    Thong tin tra ve: ObjectID, Layer, StartPoint, EndPoint, MlineScale, so dinh, toa do tat ca dinh.

    Args:
        object_ids: Danh sach ObjectID (tuy chon). Neu None → nguoi dung quet chon tren ban ve.
    Returns:
        Thong bao ket qua voi thong tin cac Mline.
    """
    try:
        result = await asyncio.to_thread(
            get_mline_data,
            object_ids=object_ids,
        )
        if result["success"]:
            details_str = ""
            for m in result.get("mlines", []):
                details_str += (
                    f"  ObjectID={m['object_id']} | Layer={m['layer']}"
                    f" | Scale={m['mline_scale']}"
                    f" | Start={m['start_point']} | End={m['end_point']}"
                    f" | Vertices={m['num_vertices']}\n"
                )
            return (
                f"{result['message']}\n"
                f"Tong chon: {result['total_selected']} | Mline: {result['mline_count']}\n"
                f"{details_str}"
            )
        else:
            return f"Khong lay duoc Mline: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi lay du lieu Mline: {str(e)}"


@mcp.tool()
async def insert_block_by_name(
    block_name: str,
    insertion_points: list[str],
    x_scale: float = 1.0,
    y_scale: float = 1.0,
    z_scale: float = 1.0,
    rotation: float = 0.0,
    layer: str = "0",
    create_layer_if_missing: bool = True,
) -> str:
    """
    Chen cung 1 block tai nhieu diem trong AutoCAD (batch).
    Toi uu: chi can truyen ten block 1 lan, danh sach cac diem chen.

    Args:
        block_name:        Ten block (da co trong ban ve) hoac duong dan .dwg.
        insertion_points:  Danh sach toa do, vd: ["0,0,0", "600,0,0", "600,600,0"]
        x_scale:           Ti le X (mac dinh 1.0).
        y_scale:           Ti le Y (mac dinh 1.0).
        z_scale:           Ti le Z (mac dinh 1.0).
        rotation:          Goc xoay radian (mac dinh 0.0).
        layer:             Layer (mac dinh "0").
        create_layer_if_missing: Tu tao layer neu chua ton tai.
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            insert_blocks_by_name,
            block_name=block_name,
            insertion_points=insertion_points,
            x_scale=x_scale,
            y_scale=y_scale,
            z_scale=z_scale,
            rotation=rotation,
            layer=layer,
            create_layer_if_missing=create_layer_if_missing,
        )
        return _format_insert_result(result)
    except Exception as e:
        return f"Loi khi chen block: {str(e)}"


@mcp.tool()
async def insert_multi_blocks(
    blocks: list[dict],
    create_layer_if_missing: bool = True,
) -> str:
    """
    Chen nhieu block khac ten vao AutoCAD cung luc (batch).
    Moi block co the co ten, vi tri, scale, rotation, layer khac nhau.

    Args:
        blocks: Danh sach block can chen. Moi phan tu:
            {
                "block_name":  str,            # Ten block hoac duong dan .dwg
                "point":       "x,y,z",        # Toa do chen
                "x_scale":     float,          # Mac dinh 1.0
                "y_scale":     float,          # Mac dinh 1.0
                "z_scale":     float,          # Mac dinh 1.0
                "rotation":    float,          # Radian, mac dinh 0.0
                "layer":       str,            # Mac dinh "0"
            }
        create_layer_if_missing: Tu tao layer neu chua ton tai.
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            insert_blocks_multi,
            blocks=blocks,
            create_layer_if_missing=create_layer_if_missing,
        )
        return _format_insert_result(result)
    except Exception as e:
        return f"Loi khi chen block: {str(e)}"


def _format_insert_result(result: dict) -> str:
    """Format ket qua insert block thanh chuoi."""
    if result["success"]:
        details_str = ""
        for d in result.get("details", []):
            if d["ok"]:
                details_str += (
                    f"  [{d['index']}] '{d['block_name']}' tai {d['point']}"
                    f" | ID={d['object_id']} | Layer={d['layer']} OK\n"
                )
            else:
                details_str += f"  [{d['index']}] '{d['block_name']}' THAT BAI - {d['error']}\n"
        return (
            f"{result['message']}\n"
            f"Tong: {result['total']} | Thanh cong: {result['inserted']} | That bai: {result['failed']}\n"
            f"{details_str}"
        )
    else:
        return f"Chen block that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"



@mcp.tool()
async def draw_polylines(
    polylines: list[dict],
    create_layer_if_missing: bool = True,
) -> str:
    """
    Ve mot hoac nhieu Polyline (LWPolyline) trong AutoCAD (batch).
    Ho tro closed, bulge (cung tron), layer, color, linetype, lineweight, width.

    Args:
        polylines: Danh sach polyline can ve. Moi phan tu la dict:
            {
                "vertices":   [[x,y], ...] | ["x,y", ...],  # Danh sach dinh (it nhat 2)
                "closed":     bool,                          # Dong polyline (mac dinh False)
                "layer":      str,                           # Layer (mac dinh "0")
                "color":      int | None,                    # ACI color index (tuy chon)
                "linetype":   str | None,                    # Ten linetype (tuy chon)
                "lineweight": int | None,                    # Lineweight (tuy chon)
                "width":      float | None,                  # Global width (tuy chon)
                "bulges":     {vertex_index: bulge_value},   # Cung tron (tuy chon)
            }
        create_layer_if_missing: Tu tao layer neu chua ton tai.
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            create_polylines,
            polylines=polylines,
            create_layer_if_missing=create_layer_if_missing,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    details_str += (
                        f"  [{d['index']}] {d['vertices']} dinh"
                        f" | closed={d['closed']}"
                        f" | ID={d['object_id']} | Layer={d['layer']} OK\n"
                    )
                else:
                    details_str += f"  [{d['index']}] THAT BAI - {d['error']}\n"
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Thanh cong: {result['drawn']} | That bai: {result['failed']}\n"
                f"{details_str}"
            )
        else:
            return f"Ve polyline that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi ve polyline: {str(e)}"


@mcp.tool()
async def draw_texts(
    texts: list[dict],
    create_layer_if_missing: bool = True,
) -> str:
    """
    Tao mot hoac nhieu Text / MText trong AutoCAD (batch).
    Ho tro text don dong (Text) va nhieu dong (MText).

    Args:
        texts: Danh sach text can tao. Moi phan tu la dict:
            {
                "content":          str,           # Noi dung text (bat buoc)
                "insertion_point":  [x,y,z]|"x,y", # Toa do chen (bat buoc)
                "height":           float,          # Chieu cao text (mac dinh 2.5)
                "type":             "text"|"mtext", # Loai text (mac dinh "text")
                "width":            float | None,   # Chieu rong MText (chi cho mtext)
                "layer":            str,            # Layer (mac dinh "0")
                "color":            int | None,     # ACI color index (tuy chon)
                "rotation":         float,          # Goc xoay radian (mac dinh 0.0)
                "style":            str | None,     # Text style name (tuy chon)
            }
        create_layer_if_missing: Tu tao layer neu chua ton tai.
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            create_texts,
            texts=texts,
            create_layer_if_missing=create_layer_if_missing,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    content_preview = (d.get("content") or "")[:40]
                    details_str += (
                        f"  [{d['index']}] {d['type'].upper()} '{content_preview}'"
                        f" | ID={d['object_id']} | Layer={d['layer']} OK\n"
                    )
                else:
                    details_str += f"  [{d['index']}] THAT BAI - {d['error']}\n"
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Thanh cong: {result['created']} | That bai: {result['failed']}\n"
                f"{details_str}"
            )
        else:
            return f"Tao text that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi tao text: {str(e)}"


@mcp.tool()
async def delete_objects(
    object_ids: list[int],
) -> str:
    """
    Xoa mot hoac nhieu doi tuong AutoCAD theo ObjectID (batch).

    Args:
        object_ids: Danh sach ObjectID (so nguyen) can xoa.
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            delete_entities,
            object_ids=object_ids,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    details_str += (
                        f"  ID={d['id']} | {d['object_name']} | Da xoa OK\n"
                    )
                else:
                    details_str += f"  ID={d['id']} | THAT BAI - {d['error']}\n"
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Da xoa: {result['deleted']} | That bai: {result['failed']}\n"
                f"{details_str}"
            )
        else:
            return f"Xoa that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi xoa doi tuong: {str(e)}"


@mcp.tool()
async def move_objects(
    object_ids: list[int],
    displacement: list[float],
) -> str:
    """
    Di chuyen mot hoac nhieu doi tuong AutoCAD theo vector dich chuyen.

    Args:
        object_ids:    Danh sach ObjectID can di chuyen.
        displacement:  Vector dich chuyen [dx, dy, dz], vd: [500, 300, 0].
    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            move_entities,
            object_ids=object_ids,
            displacement=displacement,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    details_str += f"  ID={d['id']} | {d['object_name']} | Da di chuyen OK\n"
                else:
                    details_str += f"  ID={d['id']} | THAT BAI - {d['error']}\n"
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Di chuyen: {result['moved']} | That bai: {result['failed']}\n"
                f"{details_str}"
            )
        else:
            return f"Di chuyen that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi di chuyen doi tuong: {str(e)}"


@mcp.tool()
async def copy_objects(
    object_ids: list[int],
    displacement: list[float],
) -> str:
    """
    Sao chep mot hoac nhieu doi tuong AutoCAD theo vector dich chuyen.
    Doi tuong goc giu nguyen, tao ban sao tai vi tri moi.

    Args:
        object_ids:    Danh sach ObjectID can sao chep.
        displacement:  Vector dich chuyen [dx, dy, dz], vd: [1000, 0, 0].
    Returns:
        Thong bao ket qua voi ObjectID cua ban sao moi.
    """
    try:
        result = await asyncio.to_thread(
            copy_entities,
            object_ids=object_ids,
            displacement=displacement,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    new_id = d.get("new_object_id", "N/A")
                    details_str += (
                        f"  ID={d['id']} | {d['object_name']}"
                        f" → New ID={new_id} | OK\n"
                    )
                else:
                    details_str += f"  ID={d['id']} | THAT BAI - {d['error']}\n"
            new_ids = result.get("new_object_ids", [])
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Sao chep: {result['copied']} | That bai: {result['failed']}\n"
                f"New ObjectIDs: {new_ids}\n"
                f"{details_str}"
            )
        else:
            return f"Sao chep that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi sao chep doi tuong: {str(e)}"


@mcp.tool()
async def insert_block_with_attributes(
    blocks: list[dict],
    create_layer_if_missing: bool = True,
) -> str:
    """
    Chen mot hoac nhieu Block va thiet lap Attributes vao AutoCAD.
    Attributes la cac truong thong tin gan kem block (Tag -> Value),
    vi du: ten phong, so ban ve, kich thuoc, ghi chu...

    Khac voi Dynamic Properties, Attributes la cac truong text co the
    chinh sua truc tiep va hien thi tren ban ve.

    Args:
        blocks: Danh sach cac block can chen. Moi phan tu la dict:
            {
                "block_name":       str,            # Ten block (da co trong ban ve) hoac duong dan .dwg
                "insertion_point":  [x, y, z],      # Toa do chen (z mac dinh = 0)
                "x_scale":          float,          # Ti le X   (mac dinh 1.0)
                "y_scale":          float,          # Ti le Y   (mac dinh 1.0)
                "z_scale":          float,          # Ti le Z   (mac dinh 1.0)
                "rotation":         float,          # Goc xoay (radian, mac dinh 0.0)
                "layer":            str,            # Layer     (mac dinh "0")
                "attributes":       {tag: value},   # Attributes: Tag -> Gia tri (tuy chon)
            }
        create_layer_if_missing: Tu tao layer neu chua ton tai (mac dinh True).

    Vi du:
        blocks = [
            {
                "block_name": "ROOM_TAG",
                "insertion_point": [1000, 500, 0],
                "attributes": {"ROOM_NAME": "Phong khach", "AREA": "25m2"}
            },
            {
                "block_name": "TITLE_BLOCK",
                "insertion_point": [0, 0, 0],
                "layer": "ANNO",
                "attributes": {"PROJECT": "Chung cu ABC", "DWG_NO": "MEP-01"}
            }
        ]

    Returns:
        Thong bao ket qua.
    """
    try:
        result = await asyncio.to_thread(
            insert_blocks_with_attributes,
            blocks=blocks,
            create_layer_if_missing=create_layer_if_missing,
        )
        if result["success"]:
            details_str = ""
            for d in result.get("details", []):
                if d["ok"]:
                    attr_info = ""
                    if d["attributes_set"]:
                        attr_info = f" | Attrs set: {d['attributes_set']}"
                    if d["attributes_failed"]:
                        failed_tags = [a['tag'] for a in d['attributes_failed']]
                        attr_info += f" | Attrs failed: {failed_tags}"
                    details_str += (
                        f"  [{d['index']}] '{d['block_name']}' OK"
                        f" | ObjectID={d['object_id']} | Layer={d['layer']}{attr_info}\n"
                    )
                else:
                    details_str += f"  [{d['index']}] '{d['block_name']}' THAT BAI - {d['error']}\n"
            return (
                f"{result['message']}\n"
                f"Tong: {result['total']} | Thanh cong: {result['inserted']} | That bai: {result['failed']}\n"
                f"{details_str}"
            )
        else:
            return f"Chen block that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi chen block voi attributes: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════
# GET DATA TOOLS
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
async def get_line_info(
    object_ids: list[int] | None = None,
    layer_filter: str | None = None,
) -> str:
    """
    Lay thong tin Line trong AutoCAD.
    Neu khong truyen object_ids → yeu cau nguoi dung quet chon tren ban ve.
    Chi loc nhung doi tuong la Line.

    Thong tin tra ve: ObjectID, Layer, StartPoint, EndPoint, Length, Angle,
    Thickness, Delta (vector huong), Linetype, Color.

    Args:
        object_ids:   Danh sach ObjectID (tuy chon). None → nguoi dung quet chon.
        layer_filter: Loc theo layer (tuy chon). None → khong loc.
    Returns:
        Thong bao ket qua voi thong tin cac Line.
    """
    try:
        result = await asyncio.to_thread(
            get_line_data,
            object_ids=object_ids,
            layer_filter=layer_filter,
        )
        if result["success"]:
            details_str = ""
            for l in result.get("lines", []):
                details_str += (
                    f"  ObjectID={l['object_id']} | Layer={l['layer']}"
                    f" | Length={l['length']:.2f} | Angle={l['angle']:.4f}"
                    f" | Start={l['start_point']} | End={l['end_point']}\n"
                )
            return (
                f"{result['message']}\n"
                f"Tong chon: {result['total_selected']} | Line: {result['line_count']}\n"
                f"{details_str}"
            )
        else:
            return f"Khong lay duoc Line: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi lay du lieu Line: {str(e)}"


@mcp.tool()
async def get_polyline_info(
    object_ids: list[int] | None = None,
    layer_filter: str | None = None,
) -> str:
    """
    Lay thong tin Polyline trong AutoCAD (LWPolyline, 2dPolyline, 3dPolyline).
    Neu khong truyen object_ids → yeu cau nguoi dung quet chon tren ban ve.

    Thong tin tra ve: ObjectID, ObjectName, Layer, StartPoint, EndPoint,
    Length, Closed, Area (neu closed), Vertices, Bulges, Width, Linetype, Color.

    Args:
        object_ids:   Danh sach ObjectID (tuy chon). None → nguoi dung quet chon.
        layer_filter: Loc theo layer (tuy chon). None → khong loc.
    Returns:
        Thong bao ket qua voi thong tin cac Polyline.
    """
    try:
        result = await asyncio.to_thread(
            get_polyline_data,
            object_ids=object_ids,
            layer_filter=layer_filter,
        )
        if result["success"]:
            details_str = ""
            for p in result.get("polylines", []):
                details_str += (
                    f"  ObjectID={p['object_id']} | Type={p['object_name']}"
                    f" | Layer={p['layer']} | Length={p['length']:.2f}"
                    f" | Closed={p['closed']} | Vertices={p['num_vertices']}\n"
                )
                # Hiển thị toạ độ từng điểm
                for pt in p.get("point_data", []):
                    details_str += (
                        f"    Point[{pt['index']}]: ({pt['x']:.4f}, {pt['y']:.4f}, {pt['z']:.4f})"
                        f" | Bulge={pt['bulge']:.4f}"
                        f" | Width=({pt['start_width']:.2f}, {pt['end_width']:.2f})\n"
                    )
            return (
                f"{result['message']}\n"
                f"Tong chon: {result['total_selected']} | Polyline: {result['polyline_count']}\n"
                f"{details_str}"
            )
        else:
            return f"Khong lay duoc Polyline: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi lay du lieu Polyline: {str(e)}"


@mcp.tool()
async def get_block_info(
    object_ids: list[int] | None = None,
    layer_filter: str | None = None,
) -> str:
    """
    Lay thong tin Block Reference trong AutoCAD.
    Ho tro Dynamic Block: lay toan bo DynamicProperties va Attributes.
    Neu khong truyen object_ids → yeu cau nguoi dung quet chon tren ban ve.

    Thong tin tra ve: ObjectID, BlockName, EffectiveName, Layer, InsertionPoint,
    Scale, Rotation, IsDynamicBlock, DynamicProperties (name/value/allowed_values),
    Attributes (tag/value/prompt), BoundingBox, Color, Linetype.

    Args:
        object_ids:   Danh sach ObjectID (tuy chon). None → nguoi dung quet chon.
        layer_filter: Loc theo layer (tuy chon). None → khong loc.
    Returns:
        Thong bao ket qua voi thong tin cac Block.
    """
    try:
        result = await asyncio.to_thread(
            get_block_data,
            object_ids=object_ids,
            layer_filter=layer_filter,
        )
        if result["success"]:
            details_str = ""
            for b in result.get("blocks", []):
                dp_names = [dp['name'] for dp in b.get('dynamic_properties', [])]
                attr_tags = [a['tag'] for a in b.get('attributes', [])]
                ins_pt = b.get('insertion_point', [0, 0, 0])
                details_str += (
                    f"  ObjectID={b['object_id']} | Name={b['block_name']}"
                    f" | EffName={b['effective_name']} | Layer={b['layer']}"
                    f" | InsertionPoint=({ins_pt[0]:.4f}, {ins_pt[1]:.4f}, {ins_pt[2]:.4f})"
                    f" | Scale=({b.get('x_scale',1)}, {b.get('y_scale',1)}, {b.get('z_scale',1)})"
                    f" | Rotation={b.get('rotation',0):.4f}"
                    f" | Dynamic={b['is_dynamic_block']}"
                    f" | DynProps={dp_names} | Attrs={attr_tags}\n"
                )
            return (
                f"{result['message']}\n"
                f"Tong chon: {result['total_selected']} | Block: {result['block_count']}\n"
                f"{details_str}"
            )
        else:
            return f"Khong lay duoc Block: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi lay du lieu Block: {str(e)}"


@mcp.tool()
async def get_text_info(
    object_ids: list[int] | None = None,
    layer_filter: str | None = None,
) -> str:
    """
    Lay thong tin Text va MText trong AutoCAD.
    Neu khong truyen object_ids → yeu cau nguoi dung quet chon tren ban ve.

    Thong tin tra ve: ObjectID, ObjectName (AcDbText/AcDbMText), Layer,
    TextString, InsertionPoint, Height, Rotation, StyleName, Color.
    MText them: Width, AttachmentPoint, LineSpacingFactor.

    Args:
        object_ids:   Danh sach ObjectID (tuy chon). None → nguoi dung quet chon.
        layer_filter: Loc theo layer (tuy chon). None → khong loc.
    Returns:
        Thong bao ket qua voi thong tin cac Text.
    """
    try:
        result = await asyncio.to_thread(
            get_text_data,
            object_ids=object_ids,
            layer_filter=layer_filter,
        )
        if result["success"]:
            details_str = ""
            for t in result.get("texts", []):
                content = t['text_string'][:80]
                details_str += (
                    f"  ObjectID={t['object_id']} | Type={t['object_name']}"
                    f" | Layer={t['layer']} | Height={t['height']}"
                    f" | Content='{content}'\n"
                )
            return (
                f"{result['message']}\n"
                f"Tong chon: {result['total_selected']} | Text: {result['text_count']}\n"
                f"{details_str}"
            )
        else:
            return f"Khong lay duoc Text: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi lay du lieu Text: {str(e)}"


@mcp.tool()
async def get_leader_info(
    object_ids: list[int] | None = None,
    layer_filter: str | None = None,
) -> str:
    """
    Lay thong tin Leader va MLeader trong AutoCAD.
    Neu khong truyen object_ids → yeu cau nguoi dung quet chon tren ban ve.

    Leader: ObjectID, Layer, Vertices, LeaderType, ArrowheadSize, AnnotationText.
    MLeader: ObjectID, Layer, TextString, ContentType, LeaderType, LeaderLines,
    ArrowheadSize, TextHeight, DoglegLength, StyleName.

    Args:
        object_ids:   Danh sach ObjectID (tuy chon). None → nguoi dung quet chon.
        layer_filter: Loc theo layer (tuy chon). None → khong loc.
    Returns:
        Thong bao ket qua voi thong tin cac Leader.
    """
    try:
        result = await asyncio.to_thread(
            get_leader_data,
            object_ids=object_ids,
            layer_filter=layer_filter,
        )
        if result["success"]:
            details_str = ""
            for ld in result.get("leaders", []):
                if ld['object_name'] == 'AcDbLeader':
                    details_str += (
                        f"  ObjectID={ld['object_id']} | Type=Leader"
                        f" | Layer={ld['layer']} | Vertices={ld['num_vertices']}"
                        f" | LeaderType={ld['leader_type']}\n"
                    )
                else:
                    content = ld.get('text_string', '')[:60]
                    details_str += (
                        f"  ObjectID={ld['object_id']} | Type=MLeader"
                        f" | Layer={ld['layer']} | LeaderType={ld['leader_type']}"
                        f" | Content='{content}'\n"
                    )
            return (
                f"{result['message']}\n"
                f"Tong chon: {result['total_selected']} | Leader: {result['leader_count']}\n"
                f"{details_str}"
            )
        else:
            return f"Khong lay duoc Leader: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi lay du lieu Leader: {str(e)}"


@mcp.tool()
async def get_all_selected_info(
    object_ids: list[int] | None = None,
    layer_filter: str | None = None,
) -> str:
    """
    Lay thong tin TAT CA doi tuong duoc chon trong AutoCAD.
    Tu dong phan loai: Line, Polyline, Mline, Block, Text/MText, Leader/MLeader.
    Day la tool tong hop, su dung khi khong biet truoc loai doi tuong.

    Neu khong truyen object_ids → yeu cau nguoi dung quet chon tren ban ve.
    Ket qua tra ve bao gom tat ca cac loai voi day du thong tin.

    Args:
        object_ids:   Danh sach ObjectID (tuy chon). None → nguoi dung quet chon.
        layer_filter: Loc theo layer (tuy chon). None → khong loc.
    Returns:
        Thong bao ket qua tom tat tat ca doi tuong.
    """
    try:
        result = await asyncio.to_thread(
            get_all_data,
            object_ids=object_ids,
            layer_filter=layer_filter,
        )
        if result["success"]:
            summary = result.get('summary', {})
            summary_str = (
                f"  Line: {summary.get('lines', 0)}"
                f" | Polyline: {summary.get('polylines', 0)}"
                f" | Mline: {summary.get('mlines', 0)}"
                f" | Block: {summary.get('blocks', 0)}"
                f" | Text: {summary.get('texts', 0)}"
                f" | Leader: {summary.get('leaders', 0)}"
                f" | Khac: {summary.get('unknown', 0)}"
            )

            details_parts = []

            # Lines
            for l in result.get('lines', []):
                details_parts.append(
                    f"  [Line] ID={l['object_id']} | Layer={l['layer']}"
                    f" | Length={l['length']:.2f}"
                    f" | Start={l['start_point']} → End={l['end_point']}"
                )
            # Polylines
            for p in result.get('polylines', []):
                details_parts.append(
                    f"  [Polyline] ID={p['object_id']} | Layer={p['layer']}"
                    f" | Length={p['length']:.2f} | Vertices={p['num_vertices']}"
                )
            # Mlines
            for m in result.get('mlines', []):
                details_parts.append(
                    f"  [Mline] ID={m['object_id']} | Layer={m['layer']}"
                    f" | Scale={m['mline_scale']} | Vertices={m['num_vertices']}"
                )
            # Blocks
            for b in result.get('blocks', []):
                dp_count = len(b.get('dynamic_properties', []))
                attr_count = len(b.get('attributes', []))
                ins_pt = b.get('insertion_point', [0, 0, 0])
                details_parts.append(
                    f"  [Block] ID={b['object_id']} | Name={b['block_name']}"
                    f" | Layer={b['layer']}"
                    f" | InsertionPoint=({ins_pt[0]:.4f}, {ins_pt[1]:.4f}, {ins_pt[2]:.4f})"
                    f" | Dynamic={b['is_dynamic_block']}"
                    f" | DynProps={dp_count} | Attrs={attr_count}"
                )
            # Texts
            for t in result.get('texts', []):
                content = t['text_string'][:60]
                details_parts.append(
                    f"  [Text] ID={t['object_id']} | Layer={t['layer']}"
                    f" | Content='{content}'"
                )
            # Leaders
            for ld in result.get('leaders', []):
                if ld['object_name'] == 'AcDbLeader':
                    details_parts.append(
                        f"  [Leader] ID={ld['object_id']} | Layer={ld['layer']}"
                        f" | Vertices={ld['num_vertices']}"
                    )
                else:
                    content = ld.get('text_string', '')[:60]
                    details_parts.append(
                        f"  [MLeader] ID={ld['object_id']} | Layer={ld['layer']}"
                        f" | Content='{content}'"
                    )
            # Unknown
            for u in result.get('unknown', []):
                details_parts.append(
                    f"  [Unknown] ID={u['object_id']} | Type={u['object_name']}"
                    f" | Layer={u['layer']}"
                )

            details_str = "\n".join(details_parts)

            return (
                f"{result['message']}\n"
                f"Tom tat: {summary_str}\n"
                f"{details_str}"
            )
        else:
            return f"Khong lay duoc du lieu: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi lay du lieu: {str(e)}"


@mcp.tool()
async def get_pick_point_info(
    num_points: int = 1,
    prompt: str | None = None,
) -> str:
    """
    Yeu cau nguoi dung pick diem tren ban ve AutoCAD va tra ve toa do.
    Dung de lay toa do chinh xac tu ban ve khi nguoi dung click chuot.

    Ho tro pick 1 diem, nhieu diem co dinh, hoac pick lien tuc (num_points=0)
    cho den khi nguoi dung nhan Enter/Escape.

    Args:
        num_points: So diem can pick. Mac dinh 1. Dat 0 de pick lien tuc.
        prompt:     Thong bao hien thi tren command line AutoCAD. Mac dinh tu dong.
    Returns:
        Thong bao ket qua voi toa do cac diem da pick.
    """
    try:
        result = await asyncio.to_thread(
            get_pick_point,
            num_points=num_points,
            prompt=prompt,
        )
        if result["success"]:
            details_str = ""
            for p in result.get("points", []):
                details_str += (
                    f"  Diem {p['index']+1}: ({p['x']:.4f}, {p['y']:.4f}, {p['z']:.4f})\n"
                )
            # Tạo danh sách tọa độ dạng chuỗi tiện dùng
            coords_list = [
                f"{p['x']:.4f},{p['y']:.4f},{p['z']:.4f}"
                for p in result.get("points", [])
            ]
            return (
                f"{result['message']}\n"
                f"So diem: {result['point_count']}\n"
                f"{details_str}"
                f"Toa do (dang chuoi): {coords_list}"
            )
        else:
            return f"Khong lay duoc diem: {result['message']} | Loi: {result.get('error', 'Khong ro')}"
    except Exception as e:
        return f"Loi khi pick diem: {str(e)}"


if __name__ == "__main__":
    mcp.run()