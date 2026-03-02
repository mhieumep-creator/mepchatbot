"""
HTOOLS-AI – Giao diện Web cho MCP AutoCAD Server
=================================================
Ứng dụng Streamlit kết nối Claude API với các tool AutoCAD MEP.
Cho phép chat với AI để vẽ, lấy dữ liệu từ AutoCAD qua giao diện web.

Chạy:
    streamlit run app.py
"""

import streamlit as st
import os
import sys
import json
import asyncio
from dotenv import load_dotenv

# ── Đảm bảo import được các module AutoCAD ──
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

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

import anthropic

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

# ── Cấu hình trang ──
st.set_page_config(
    page_title="HTOOLS-AI | AutoCAD MEP",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load system prompt ──
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(CURRENT_DIR, "MCPServer", "system_prompt.json")
try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPTS = json.load(f)
except FileNotFoundError:
    SYSTEM_PROMPTS = {}

SYSTEM_PROMPT = SYSTEM_PROMPTS.get(
    "mcp_server_instructions",
    "Bạn là trợ lý AutoCAD MEP chuyên nghiệp, hỗ trợ vẽ và lấy dữ liệu trong AutoCAD.",
)

MODEL_NAME = "claude-sonnet-4-5-20250929"

# ═══════════════════════════════════════════════════════════════
# TOOL DEFINITIONS (Claude API format + auto-convert to Gemini)
# ═══════════════════════════════════════════════════════════════

TOOLS = [
    # ── DRAWING TOOLS ──
    {
        "name": "draw_mline_von",
        "description": "Ve Mline trong AutoCAD bang lenh VON. Tao duong ong thoat nuoc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mlines": {
                    "type": "array",
                    "description": "Danh sach mline, moi phan tu: {Layer, Style, Scale, Justification, Points: [{X,Y},..]}",
                    "items": {"type": "object"},
                },
            },
            "required": ["mlines"],
        },
    },
    {
        "name": "draw_mline_von_ppr",
        "description": "Ve Mline trong AutoCAD bang lenh VON_PPR. Tao duong ong cap nuoc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mlines": {
                    "type": "array",
                    "description": "Danh sach mline (cung format voi draw_mline_von).",
                    "items": {"type": "object"},
                },
            },
            "required": ["mlines"],
        },
    },
    {
        "name": "draw_lines",
        "description": "Ve mot hoac nhieu Line trong AutoCAD (batch). Moi line co start, end, layer, color, linetype.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "array",
                    "description": "Danh sach line: [{start:[x,y,z], end:[x,y,z], layer:str, color:int, linetype:str}]",
                    "items": {"type": "object"},
                },
                "create_layer_if_missing": {"type": "boolean", "default": True},
            },
            "required": ["lines"],
        },
    },
    {
        "name": "draw_polylines",
        "description": "Ve mot hoac nhieu Polyline (LWPolyline) trong AutoCAD. Ho tro closed, bulge, layer, width.",
        "input_schema": {
            "type": "object",
            "properties": {
                "polylines": {
                    "type": "array",
                    "description": "Danh sach polyline: [{vertices:[[x,y],...], closed:bool, layer:str, ...}]",
                    "items": {"type": "object"},
                },
                "create_layer_if_missing": {"type": "boolean", "default": True},
            },
            "required": ["polylines"],
        },
    },
    {
        "name": "draw_texts",
        "description": "Tao Text / MText trong AutoCAD. Ho tro text don dong va nhieu dong.",
        "input_schema": {
            "type": "object",
            "properties": {
                "texts": {
                    "type": "array",
                    "description": "Danh sach text: [{content:str, insertion_point:[x,y,z], height:float, type:'text'|'mtext', layer:str}]",
                    "items": {"type": "object"},
                },
                "create_layer_if_missing": {"type": "boolean", "default": True},
            },
            "required": ["texts"],
        },
    },
    {
        "name": "change_object_layer",
        "description": "Doi layer cua doi tuong AutoCAD theo ObjectID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}, "description": "Danh sach ObjectID"},
                "new_layer": {"type": "string", "description": "Ten layer moi"},
                "create_layer_if_missing": {"type": "boolean", "default": True},
            },
            "required": ["object_ids", "new_layer"],
        },
    },
    {
        "name": "insert_block_with_dynamic_properties",
        "description": "Chen block co Dynamic Properties vao AutoCAD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "blocks": {
                    "type": "array",
                    "description": "Danh sach block: [{block_name, insertion_point, x_scale, y_scale, rotation, layer, dynamic_properties:{}}]",
                    "items": {"type": "object"},
                },
                "create_layer_if_missing": {"type": "boolean", "default": True},
            },
            "required": ["blocks"],
        },
    },
    {
        "name": "insert_block_by_name",
        "description": "Chen cung 1 block tai nhieu diem trong AutoCAD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "block_name": {"type": "string"},
                "insertion_points": {"type": "array", "items": {"type": "string"}, "description": "VD: ['0,0,0', '600,0,0']"},
                "x_scale": {"type": "number", "default": 1.0},
                "y_scale": {"type": "number", "default": 1.0},
                "z_scale": {"type": "number", "default": 1.0},
                "rotation": {"type": "number", "default": 0.0},
                "layer": {"type": "string", "default": "0"},
                "create_layer_if_missing": {"type": "boolean", "default": True},
            },
            "required": ["block_name", "insertion_points"],
        },
    },
    {
        "name": "insert_multi_blocks",
        "description": "Chen nhieu block khac ten vao AutoCAD cung luc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "blocks": {
                    "type": "array",
                    "description": "Danh sach: [{block_name, point:'x,y,z', x_scale, y_scale, rotation, layer}]",
                    "items": {"type": "object"},
                },
                "create_layer_if_missing": {"type": "boolean", "default": True},
            },
            "required": ["blocks"],
        },
    },
    {
        "name": "insert_block_with_attributes",
        "description": "Chen block va thiet lap Attributes (tag -> value) vao AutoCAD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "blocks": {
                    "type": "array",
                    "description": "Danh sach: [{block_name, insertion_point, layer, attributes:{tag:value}}]",
                    "items": {"type": "object"},
                },
                "create_layer_if_missing": {"type": "boolean", "default": True},
            },
            "required": ["blocks"],
        },
    },
    {
        "name": "delete_objects",
        "description": "Xoa doi tuong AutoCAD theo ObjectID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["object_ids"],
        },
    },
    {
        "name": "move_objects",
        "description": "Di chuyen doi tuong AutoCAD theo vector dich chuyen [dx, dy, dz].",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
                "displacement": {"type": "array", "items": {"type": "number"}, "description": "[dx, dy, dz]"},
            },
            "required": ["object_ids", "displacement"],
        },
    },
    {
        "name": "copy_objects",
        "description": "Sao chep doi tuong AutoCAD theo vector dich chuyen.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
                "displacement": {"type": "array", "items": {"type": "number"}, "description": "[dx, dy, dz]"},
            },
            "required": ["object_ids", "displacement"],
        },
    },
    # ── GET DATA TOOLS ──
    {
        "name": "get_line_info",
        "description": "Lay thong tin Line trong AutoCAD. Neu khong truyen object_ids → nguoi dung quet chon tren ban ve.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}, "description": "Danh sach ObjectID (tuy chon)"},
                "layer_filter": {"type": "string", "description": "Loc theo layer (tuy chon)"},
            },
        },
    },
    {
        "name": "get_polyline_info",
        "description": "Lay thong tin Polyline trong AutoCAD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
                "layer_filter": {"type": "string"},
            },
        },
    },
    {
        "name": "get_mline_info",
        "description": "Lay thong tin Mline trong AutoCAD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
            },
        },
    },
    {
        "name": "get_block_info",
        "description": "Lay thong tin Block (+ DynamicProperties + Attributes) trong AutoCAD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
                "layer_filter": {"type": "string"},
            },
        },
    },
    {
        "name": "get_text_info",
        "description": "Lay thong tin Text / MText trong AutoCAD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
                "layer_filter": {"type": "string"},
            },
        },
    },
    {
        "name": "get_leader_info",
        "description": "Lay thong tin Leader / MLeader trong AutoCAD.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
                "layer_filter": {"type": "string"},
            },
        },
    },
    {
        "name": "get_all_selected_info",
        "description": "Lay TAT CA doi tuong duoc chon trong AutoCAD. Tu phan loai Line, Polyline, Mline, Block, Text, Leader.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_ids": {"type": "array", "items": {"type": "integer"}},
                "layer_filter": {"type": "string"},
            },
        },
    },
    {
        "name": "get_pick_point_info",
        "description": "Yeu cau nguoi dung pick diem tren ban ve AutoCAD va tra ve toa do. Dat num_points=0 de pick lien tuc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "num_points": {"type": "integer", "default": 1, "description": "So diem can pick. 0 = pick lien tuc."},
                "prompt": {"type": "string", "description": "Thong bao hien thi tren command line AutoCAD."},
            },
        },
    },
]


# ── Chuyển đổi tool sang Gemini format ──
def _build_gemini_tools():
    """Chuyển đổi Claude tool definitions sang Gemini function declarations."""
    declarations = []
    for tool in TOOLS:
        declarations.append({
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        })
    return [{"function_declarations": declarations}]

GEMINI_TOOLS = _build_gemini_tools()


# ═══════════════════════════════════════════════════════════════
# TOOL EXECUTOR – Gọi hàm AutoCAD tương ứng
# ═══════════════════════════════════════════════════════════════

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Thực thi tool AutoCAD và trả về kết quả dạng text."""
    try:
        if tool_name == "draw_mline_von":
            result = create_mline_von(mlines=tool_input["mlines"])
            return _format_mline_result("VON", result, tool_input["mlines"])

        elif tool_name == "draw_mline_von_ppr":
            result = create_mline_von_ppr(mlines=tool_input["mlines"])
            return _format_mline_result("VON_PPR", result, tool_input["mlines"])

        elif tool_name == "draw_lines":
            result = create_lines(
                lines=tool_input["lines"],
                create_layer_if_missing=tool_input.get("create_layer_if_missing", True),
            )
            return _format_generic_result(result, "ve line")

        elif tool_name == "draw_polylines":
            result = create_polylines(
                polylines=tool_input["polylines"],
                create_layer_if_missing=tool_input.get("create_layer_if_missing", True),
            )
            return _format_generic_result(result, "ve polyline")

        elif tool_name == "draw_texts":
            result = create_texts(
                texts=tool_input["texts"],
                create_layer_if_missing=tool_input.get("create_layer_if_missing", True),
            )
            return _format_generic_result(result, "tao text")

        elif tool_name == "change_object_layer":
            result = change_layer(
                object_ids=tool_input["object_ids"],
                new_layer=tool_input["new_layer"],
                create_layer_if_missing=tool_input.get("create_layer_if_missing", True),
            )
            return _format_generic_result(result, "doi layer")

        elif tool_name == "insert_block_with_dynamic_properties":
            result = insert_blocks(
                blocks=tool_input["blocks"],
                create_layer_if_missing=tool_input.get("create_layer_if_missing", True),
            )
            return _format_generic_result(result, "chen block (dynamic)")

        elif tool_name == "insert_block_by_name":
            result = insert_blocks_by_name(
                block_name=tool_input["block_name"],
                insertion_points=tool_input["insertion_points"],
                x_scale=tool_input.get("x_scale", 1.0),
                y_scale=tool_input.get("y_scale", 1.0),
                z_scale=tool_input.get("z_scale", 1.0),
                rotation=tool_input.get("rotation", 0.0),
                layer=tool_input.get("layer", "0"),
                create_layer_if_missing=tool_input.get("create_layer_if_missing", True),
            )
            return _format_generic_result(result, "chen block")

        elif tool_name == "insert_multi_blocks":
            result = insert_blocks_multi(
                blocks=tool_input["blocks"],
                create_layer_if_missing=tool_input.get("create_layer_if_missing", True),
            )
            return _format_generic_result(result, "chen multi block")

        elif tool_name == "insert_block_with_attributes":
            result = insert_blocks_with_attributes(
                blocks=tool_input["blocks"],
                create_layer_if_missing=tool_input.get("create_layer_if_missing", True),
            )
            return _format_generic_result(result, "chen block (attributes)")

        elif tool_name == "delete_objects":
            result = delete_entities(object_ids=tool_input["object_ids"])
            return _format_generic_result(result, "xoa doi tuong")

        elif tool_name == "move_objects":
            result = move_entities(
                object_ids=tool_input["object_ids"],
                displacement=tool_input["displacement"],
            )
            return _format_generic_result(result, "di chuyen")

        elif tool_name == "copy_objects":
            result = copy_entities(
                object_ids=tool_input["object_ids"],
                displacement=tool_input["displacement"],
            )
            return _format_generic_result(result, "sao chep")

        elif tool_name == "get_line_info":
            result = get_line_data(
                object_ids=tool_input.get("object_ids"),
                layer_filter=tool_input.get("layer_filter"),
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif tool_name == "get_polyline_info":
            result = get_polyline_data(
                object_ids=tool_input.get("object_ids"),
                layer_filter=tool_input.get("layer_filter"),
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif tool_name == "get_mline_info":
            result = get_mline_data(
                object_ids=tool_input.get("object_ids"),
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif tool_name == "get_block_info":
            result = get_block_data(
                object_ids=tool_input.get("object_ids"),
                layer_filter=tool_input.get("layer_filter"),
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif tool_name == "get_text_info":
            result = get_text_data(
                object_ids=tool_input.get("object_ids"),
                layer_filter=tool_input.get("layer_filter"),
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif tool_name == "get_leader_info":
            result = get_leader_data(
                object_ids=tool_input.get("object_ids"),
                layer_filter=tool_input.get("layer_filter"),
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif tool_name == "get_all_selected_info":
            result = get_all_data(
                object_ids=tool_input.get("object_ids"),
                layer_filter=tool_input.get("layer_filter"),
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        elif tool_name == "get_pick_point_info":
            result = get_pick_point(
                num_points=tool_input.get("num_points", 1),
                prompt=tool_input.get("prompt"),
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        else:
            return f"Tool '{tool_name}' khong duoc ho tro."

    except Exception as e:
        return f"Loi khi thuc thi tool '{tool_name}': {str(e)}"


def _format_mline_result(action: str, result: dict, mlines: list) -> str:
    if result["success"]:
        return (
            f"Da tao Mline ({action}) thanh cong voi {len(mlines)} cau hinh | "
            f"Entity them: {result['entities_added']} "
            f"(truoc={result['entities_before']}, sau={result['entities_after']})"
        )
    return f"Tao Mline ({action}) that bai: {result['message']} | Loi: {result.get('error', 'Khong ro')}"


def _format_generic_result(result: dict, action_label: str) -> str:
    if result.get("success"):
        return f"{result.get('message', f'{action_label} thanh cong.')} | {json.dumps({k: v for k, v in result.items() if k != 'details'}, ensure_ascii=False)}"
    return f"{action_label} that bai: {result.get('message', 'Khong ro')} | Loi: {result.get('error', 'N/A')}"


# ═══════════════════════════════════════════════════════════════
# CLAUDE API CHAT LOOP (with tool use)
# ═══════════════════════════════════════════════════════════════

def chat_with_claude(client: anthropic.Anthropic, messages: list, model: str) -> tuple[str, list]:
    """
    Gửi tin nhắn đến Claude, xử lý tool_use loop, trả về (reply_text, tool_logs).
    tool_logs: danh sách {tool_name, input, output} để hiển thị.
    """
    tool_logs = []
    max_iterations = 10  # Giới hạn vòng lặp tool

    for _ in range(max_iterations):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Thu thập text blocks và tool_use blocks
        text_parts = []
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append(block)

        # Nếu không có tool_use → trả về text
        if response.stop_reason == "end_of_turn" or not tool_uses:
            return "\n".join(text_parts), tool_logs

        # Có tool_use → thực thi từng tool
        # Thêm assistant message vào history
        messages.append({"role": "assistant", "content": response.content})

        # Thực thi tools và tạo tool_result
        tool_results = []
        for tool_use in tool_uses:
            tool_output = execute_tool(tool_use.name, tool_use.input)
            tool_logs.append({
                "tool_name": tool_use.name,
                "input": tool_use.input,
                "output": tool_output,
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": tool_output,
            })

        # Thêm tool results vào history
        messages.append({"role": "user", "content": tool_results})

    # Nếu hết vòng lặp
    return "\n".join(text_parts) if text_parts else "Đã hoàn thành (vượt quá số vòng tool).", tool_logs


# ═══════════════════════════════════════════════════════════════
# GEMINI API CHAT LOOP (with tool use)
# ═══════════════════════════════════════════════════════════════

def chat_with_gemini(api_key: str, messages: list, model_name: str) -> tuple[str, list]:
    """
    Gửi tin nhắn đến Gemini, xử lý function_call loop, trả về (reply_text, tool_logs).
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=SYSTEM_PROMPT,
        tools=GEMINI_TOOLS,
    )

    # Chuyển đổi message history sang Gemini format
    gemini_history = []
    for msg in messages[:-1]:  # Tất cả trừ tin nhắn cuối
        if isinstance(msg.get("content"), str):
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=gemini_history)
    tool_logs = []
    last_message = messages[-1]["content"]

    response = chat.send_message(last_message)

    for _ in range(10):  # Max iterations
        # Tìm function calls trong response
        function_calls = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call.name:
                function_calls.append(part)

        if not function_calls:
            break

        # Thực thi tools
        function_responses = []
        for fc_part in function_calls:
            fc = fc_part.function_call
            tool_input = dict(fc.args) if fc.args else {}
            tool_output = execute_tool(fc.name, tool_input)
            tool_logs.append({
                "tool_name": fc.name,
                "input": tool_input,
                "output": tool_output,
            })
            function_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": tool_output},
                    )
                )
            )

        # Gửi kết quả tool về Gemini
        response = chat.send_message(function_responses)

    # Lấy text cuối cùng
    try:
        text = response.text
    except Exception:
        text_parts = []
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'text') and part.text:
                text_parts.append(part.text)
        text = "\n".join(text_parts) if text_parts else "Đã hoàn thành."

    return text, tool_logs


# ═══════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════

# ── Custom CSS – Deep Blue Theme ──
st.markdown("""
<style>
    /* ── Nền tổng ── */
    .stApp {
        background: linear-gradient(170deg, #050d1a 0%, #0a1628 40%, #0d1f3c 100%);
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #06101f 0%, #0b1a30 100%) !important;
        border-right: 1px solid #1a3a6a;
    }
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #7ab8ff !important;
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] label {
        color: #c0d6f0 !important;
    }

    /* ── Header card ── */
    .main-header {
        background: linear-gradient(135deg, #0d2247 0%, #153575 50%, #1a4090 100%);
        border: 1px solid #2a5aaa;
        border-radius: 14px;
        padding: 28px 32px;
        margin-bottom: 24px;
        box-shadow: 0 4px 24px rgba(30, 90, 200, 0.15);
    }
    .main-header h1 {
        color: #ffffff !important;
        font-size: 28px;
        margin: 0 0 6px 0;
        text-shadow: 0 2px 8px rgba(70, 150, 255, 0.3);
    }
    .main-header p {
        color: #9ec5f0 !important;
        font-size: 15px;
        margin: 0;
    }

    /* ── Chat bubbles ── */
    .stChatMessage { border-radius: 14px !important; }
    div[data-testid="stChatMessage"]:has(img[alt="user"]) {
        background: linear-gradient(135deg, #102a52 0%, #163d6e 100%) !important;
        border: 1px solid #1e4f8f;
    }
    div[data-testid="stChatMessage"]:has(img[alt="assistant"]) {
        background: linear-gradient(135deg, #0c1a30 0%, #111f3a 100%) !important;
        border: 1px solid #1a3060;
    }
    .stChatMessage p, .stChatMessage li, .stChatMessage span {
        color: #e0eaf8 !important;
    }

    /* ── Chat input ── */
    .stChatInput > div {
        background: #0d1f3c !important;
        border: 1px solid #2a5aaa !important;
        border-radius: 12px !important;
    }
    .stChatInput textarea {
        color: #e8edf5 !important;
    }
    .stChatInput textarea::placeholder {
        color: #5a7da8 !important;
    }

    /* ── Tool log ── */
    .tool-log {
        background: linear-gradient(135deg, #081428 0%, #0e1e38 100%);
        color: #c0d6f0;
        padding: 14px 16px;
        border-radius: 10px;
        border: 1px solid #1a3a6a;
        font-family: 'Cascadia Code', 'Fira Code', monospace;
        font-size: 13px;
        margin: 6px 0;
        overflow-x: auto;
    }
    .tool-name { color: #4da6ff; font-weight: 700; font-size: 14px; }
    .tool-ok { color: #5ce07a; }
    .tool-err { color: #ff6b8a; }

    /* ── Buttons ── */
    .stButton > button {
        background: linear-gradient(135deg, #1a4090 0%, #2558b0 100%) !important;
        color: #ffffff !important;
        border: 1px solid #3070cc !important;
        border-radius: 10px !important;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2558b0 0%, #3070cc 100%) !important;
        box-shadow: 0 4px 16px rgba(40, 100, 220, 0.3);
    }

    /* ── Inputs ── */
    .stTextInput > div > div {
        background: #0b1a30 !important;
        border: 1px solid #1e4070 !important;
        border-radius: 8px !important;
    }
    .stSelectbox > div > div {
        background: #0b1a30 !important;
        border: 1px solid #1e4070 !important;
    }

    /* ── Alert/Info ── */
    .stAlert {
        background: #0d1f3c !important;
        border: 1px solid #1e4f8f !important;
        color: #9ec5f0 !important;
        border-radius: 10px;
    }

    /* ── Divider ── */
    hr { border-color: #1a3060 !important; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #0a1628; }
    ::-webkit-scrollbar-thumb { background: #1e4070; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #2a5aaa; }

    .sidebar-info { font-size: 12px; color: #4a6a90 !important; text-align: center; }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──
with st.sidebar:
    st.markdown("## 🏗️ HTOOLS-AI")
    st.caption("AutoCAD MEP Assistant")
    st.divider()

    # Provider selection
    st.markdown("### 🔌 AI Provider")
    provider = st.radio(
        "Chọn nhà cung cấp AI",
        options=["Claude (Anthropic)", "Gemini (Google)"],
        index=0,
        horizontal=True,
        help="Chọn Claude hoặc Gemini để sử dụng.",
    )
    is_claude = provider.startswith("Claude")

    st.divider()

    # API Key
    st.markdown("### 🔑 API Key")

    # Tải từ .env nếu có
    env_path = os.path.join(_PROJECT_ROOT, "Key.env")
    env_claude_key = ""
    env_gemini_key = ""
    if os.path.exists(env_path):
        load_dotenv(env_path)
        env_claude_key = os.environ.get("CLAUDE_API_KEY", "")
        env_gemini_key = os.environ.get("GEMINI_API_KEY", "")

    if is_claude:
        api_key_input = st.text_input(
            "Claude API Key",
            value=env_claude_key,
            type="password",
            placeholder="sk-ant-api03-...",
            help="Nhập API key từ Anthropic Console.",
        )
    else:
        if not HAS_GEMINI:
            st.error("❌ Chưa cài `google-generativeai`. Chạy: `pip install google-generativeai`")
        api_key_input = st.text_input(
            "Gemini API Key",
            value=env_gemini_key,
            type="password",
            placeholder="AIza...",
            help="Nhập API key từ Google AI Studio.",
        )

    # Model selection
    st.markdown("### 🤖 Model")
    if is_claude:
        model_choice = st.selectbox(
            "Chọn model",
            options=[
                "claude-sonnet-4-5-20250929",
                "claude-sonnet-4-20250514",
                "claude-haiku-4-20250414",
            ],
            index=0,
            help="Chọn model Claude.",
        )
    else:
        model_choice = st.selectbox(
            "Chọn model",
            options=[
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
            ],
            index=0,
            help="Chọn model Gemini.",
        )

    st.divider()

    # Tool list
    with st.expander("🔧 Danh sách Tools", expanded=False):
        st.markdown("**VẼ (Drawing):**")
        drawing_tools = [
            "draw_mline_von", "draw_mline_von_ppr", "draw_lines",
            "draw_polylines", "draw_texts", "change_object_layer",
            "insert_block_by_name", "insert_multi_blocks",
            "insert_block_with_dynamic_properties",
            "insert_block_with_attributes",
            "delete_objects", "move_objects", "copy_objects",
        ]
        for t in drawing_tools:
            st.markdown(f"- `{t}`")

        st.markdown("**LẤY DỮ LIỆU (Getdata):**")
        getdata_tools = [
            "get_line_info", "get_polyline_info", "get_mline_info",
            "get_block_info", "get_text_info", "get_leader_info",
            "get_all_selected_info", "get_pick_point_info",
        ]
        for t in getdata_tools:
            st.markdown(f"- `{t}`")

    st.divider()

    # Clear chat
    if st.button("🗑️ Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.display_messages = []
        st.rerun()

    st.divider()
    st.markdown(
        '<p class="sidebar-info">Phiên bản 1.0 • MCP AutoCAD Server</p>',
        unsafe_allow_html=True,
    )


# ── Session State ──
if "messages" not in st.session_state:
    st.session_state.messages = []       # Claude API messages (full history)
if "display_messages" not in st.session_state:
    st.session_state.display_messages = []  # Hiển thị trên UI [{role, content, tool_logs}]


# ── Header ──
st.markdown("""
<div class="main-header">
    <h1>🏗️ HTOOLS-AI — AutoCAD MEP Assistant</h1>
    <p>Chat với AI để vẽ và lấy dữ liệu từ AutoCAD • Nhập lệnh bằng tiếng Việt tự nhiên</p>
</div>
""", unsafe_allow_html=True)

# ── Kiểm tra API Key ──
if not api_key_input:
    provider_name = "Claude" if is_claude else "Gemini"
    st.info(f"👈 Vui lòng nhập **{provider_name} API Key** ở sidebar để bắt đầu.")
    st.stop()

if not is_claude and not HAS_GEMINI:
    st.error("❌ Thư viện `google-generativeai` chưa được cài. Chạy: `pip install google-generativeai`")
    st.stop()

# Khởi tạo client (chỉ Claude cần client object)
client = None
if is_claude:
    try:
        client = anthropic.Anthropic(api_key=api_key_input)
    except Exception as e:
        st.error(f"❌ Không thể khởi tạo Anthropic client: {e}")
        st.stop()


# ── Hiển thị lịch sử chat ──
for msg in st.session_state.display_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Hiển thị tool logs nếu có
        if msg.get("tool_logs"):
            with st.expander(f"🔧 Tools đã sử dụng ({len(msg['tool_logs'])})", expanded=False):
                for log in msg["tool_logs"]:
                    st.markdown(f'<div class="tool-log"><span class="tool-name">⚡ {log["tool_name"]}</span></div>', unsafe_allow_html=True)
                    st.json(log["input"], expanded=False)
                    output_preview = log["output"][:500]
                    if len(log["output"]) > 500:
                        output_preview += "..."
                    st.code(output_preview, language="text")


# ── Chat Input ──
if prompt := st.chat_input("Ví dụ: Vẽ ống thoát nước từ (0,0) đến (1000,0), mlscale 25..."):
    # Hiển thị tin nhắn user
    st.session_state.display_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Thêm vào Claude API messages
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Gọi AI API
    with st.chat_message("assistant"):
        with st.spinner("🤖 Đang xử lý..."):
            try:
                if is_claude:
                    reply_text, tool_logs = chat_with_claude(
                        client=client,
                        messages=st.session_state.messages,
                        model=model_choice,
                    )
                else:
                    reply_text, tool_logs = chat_with_gemini(
                        api_key=api_key_input,
                        messages=st.session_state.messages,
                        model_name=model_choice,
                    )

                # Hiển thị kết quả
                st.markdown(reply_text)

                # Hiển thị tool logs
                if tool_logs:
                    with st.expander(f"🔧 Tools đã sử dụng ({len(tool_logs)})", expanded=False):
                        for log in tool_logs:
                            st.markdown(f'<div class="tool-log"><span class="tool-name">⚡ {log["tool_name"]}</span></div>', unsafe_allow_html=True)
                            st.json(log["input"], expanded=False)
                            output_preview = log["output"][:500]
                            if len(log["output"]) > 500:
                                output_preview += "..."
                            st.code(output_preview, language="text")

                # Lưu vào history
                st.session_state.messages.append({"role": "assistant", "content": reply_text})
                st.session_state.display_messages.append({
                    "role": "assistant",
                    "content": reply_text,
                    "tool_logs": tool_logs,
                })

            except anthropic.AuthenticationError:
                st.error("❌ API Key không hợp lệ. Vui lòng kiểm tra lại.")
            except anthropic.RateLimitError:
                st.error("⏳ Đã vượt quá giới hạn API. Vui lòng thử lại sau.")
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")
