import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from AutoCad.Drawing.CreatLine import create_line
from AutoCad.Drawing.CreatCircle import create_circle

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
import anthropic

# 1. Khởi tạo MCP Server
mcp = FastMCP("Gemini-AutoCAD-Server")

# 2. Nạp biến môi trường từ file .env (nếu có)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "Key.env")
load_dotenv(ENV_PATH)


# --- Claude config ---
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY")
if not CLAUDE_API_KEY:
    raise RuntimeError(
        f"Missing CLAUDE_API_KEY environment variable for Claude client. "
        f"Expected it in environment or in .env at: {ENV_PATH}"
    )
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
CLAUDE_MODEL = "claude-haiku-4-5-20251001"  # Hoặc model phù hợp




# Tool gọi Claude AI
@mcp.tool()
async def ask_claude(prompt: str) -> str:
    """Sử dụng Claude AI để hỗ trợ các tác vụ AutoCAD/MEP."""
    try:
        response = claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        # anthropic 1.x: response.content, anthropic 2.x: response.completion
        return getattr(response, "content", getattr(response, "completion", str(response)))
    except Exception as e:
        return f"Lỗi khi gọi Claude: {str(e)}"


# Tool kiểm tra Claude
@mcp.tool()
async def hello_claude(name: str) -> str:
    """Công cụ mẫu để kiểm tra kết nối với Claude AI."""
    try:
        prompt = f"Viết một lời chào thân thiện cho {name}."
        response = claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        return getattr(response, "content", getattr(response, "completion", str(response)))
    except Exception as e:
        return f"Lỗi khi gọi Claude: {str(e)}"
    
# Tool tính tổng hai số
@mcp.tool()
async def sum_numbers(a: int, b: int) -> int:
    """Công cụ mẫu để tính tổng hai số."""
    return a + b


# Tool tạo đường thẳng trong AutoCAD
@mcp.tool()
async def create_line_tool(start_x: float, start_y: float, start_z: float, end_x: float, end_y: float, end_z: float, layer: str = "0") -> str:
    """
    Tạo một đoạn thẳng trong AutoCAD từ điểm (start_x, start_y, start_z) đến (end_x, end_y, end_z) trên layer chỉ định.
    Trả về handle của Line vừa tạo hoặc thông báo lỗi.
    """
    start_point = (start_x, start_y, start_z)
    end_point = (end_x, end_y, end_z)
    handle = create_line(start_point, end_point, layer)
    if handle:
        return f"Đã tạo Line với handle: {handle}"
    else:
        return "Lỗi khi tạo Line trong AutoCAD."

#Tools tạo đường tròn
@mcp.tool()
async def create_circle_tool(
    center_x: float,
    center_y: float, 
    center_z: float,
    radius: float,
    layer: str = "0"
) -> str:
    center_point = [center_x, center_y, center_z]  # Tạo list từ 3 tham số
    result = create_circle(center_point, radius, layer)

#Tools vẽ Mline
@mcp.tool()
async def create_mline_tool(
    points: list[tuple[float, float]] | list[tuple[float, float, float]],
    layer: str = "0",
    style: str = "Standard",
    scale: float = 1.0
) -> str:
    """
    Tạo Mline trong AutoCAD.
    points: list các tuple (x, y, z) hoặc (x, y)
    layer: tên layer
    style: tên style Mline
    scale: hệ số scale
    Trả về handle của Mline vừa tạo hoặc thông báo lỗi.
    """
    from AutoCad.Drawing.CreatMline import create_mline
    handle = create_mline(points, layer, style, scale)
    if handle:
        return f"Đã tạo Mline với handle: {handle}"
    else:
        return "Lỗi khi tạo Mline trong AutoCAD."

#Tools Lấy thông số đối tượng được quét
@mcp.tool()
async def GetdataObject_tool() -> str:
    from AutoCad.Drawing.GetdataObject import (
        connect_autocad,
        select_objects_from_user,
        get_block_attributes,
        get_block_dynamic_properties
    )
    import json

    try:
        acad, doc = connect_autocad()
        ss = select_objects_from_user(doc)

        result = []
        for entity in ss:
            obj_info = {
                "Handle": entity.Handle,
                "Type": entity.ObjectName,
                "Layer": entity.Layer
            }

            # ===== LẤY TỌA ĐỘ CHUNG =====
            if hasattr(entity, "StartPoint"):
                obj_info["StartPoint"] = list(entity.StartPoint)
            if hasattr(entity, "EndPoint"):
                obj_info["EndPoint"] = list(entity.EndPoint)
            if hasattr(entity, "Center"):
                obj_info["Center"] = list(entity.Center)
            if hasattr(entity, "InsertionPoint"):
                obj_info["InsertionPoint"] = list(entity.InsertionPoint)
            if hasattr(entity, "Coordinates"):
                obj_info["Coordinates"] = list(entity.Coordinates)

            # ===== BLOCK =====
            if entity.ObjectName == "AcDbBlockReference":
                obj_info["BlockName"] = entity.Name
                obj_info["Attributes"] = get_block_attributes(entity)
                obj_info["DynamicProperties"] = get_block_dynamic_properties(entity)

            result.append(obj_info)

        ss.Delete()
        return json.dumps(result, ensure_ascii=False, indent=4)

    except Exception as e:
        return f"Lỗi khi lấy dữ liệu đối tượng: {str(e)}"

    
if __name__ == "__main__":
    mcp.run()