import win32com.client
import pythoncom
import json
import math
import sys
# =====================================================
# CONNECT AUTOCAD (FIX INVISIBLE WINDOW)
# =====================================================
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        # Nếu không reconfigure được thì vẫn tiếp tục, chỉ có thể bị lỗi hiển thị ký tự
        pass
def connect_autocad():
    pythoncom.CoInitialize()
    acad = win32com.client.Dispatch("AutoCAD.Application")

    # 🔥 BẮT BUỘC HIỆN AUTOCAD
    acad.Visible = True
    acad.WindowState = 3  # acMax

    doc = acad.ActiveDocument
    doc.Utility.Prompt("\n[MCP] AutoCAD đã sẵn sàng để quét chọn...\n")
    return acad, doc

# =====================================================
# CLEAR OLD SELECTION SET
# =====================================================
def clear_selection_sets(doc, name="MCP_SELECTION"):
    for ss in doc.SelectionSets:
        if ss.Name == name:
            ss.Delete()

# =====================================================
# USER SELECT OBJECTS
# =====================================================
def select_objects_from_user(doc):
    clear_selection_sets(doc)
    ss = doc.SelectionSets.Add("MCP_SELECTION")
    doc.Utility.Prompt("\n👉 Quét chọn nhiều đối tượng rồi nhấn Enter...\n")
    ss.SelectOnScreen()
    return ss

# =====================================================
# BLOCK ATTRIBUTES
# =====================================================
def get_block_attributes(block):
    attrs = []
    if block.HasAttributes:
        for att in block.GetAttributes():
            attrs.append({
                "Tag": att.TagString,
                "Text": att.TextString,
                "Position": list(att.InsertionPoint),
                "Height": att.Height,
                "Rotation": att.Rotation,
                "Layer": att.Layer
            })
    return attrs

# =====================================================
# BLOCK DYNAMIC PROPERTIES
# =====================================================
def get_block_dynamic_properties(block):
    dyns = []
    try:
        if block.IsDynamicBlock:
            props = block.GetDynamicBlockProperties()
            for p in props:
                dyns.append({
                    "Name": p.PropertyName,
                    "Value": p.Value,
                    "UnitsType": getattr(p, "UnitsType", None),
                    "ReadOnly": p.ReadOnly
                })
    except:
        pass
    return dyns

# =====================================================
# GET TECHNICAL INFO
# =====================================================
def get_technical_info(ent):
    obj_type = ent.ObjectName

    info = {
        "ObjectName": obj_type,
        "Handle": ent.Handle,
        "Layer": ent.Layer,
        "Color": ent.Color
    }

    try:
        # ---------- LINE ----------
        if obj_type == "AcDbLine":
            info.update({
                "StartPoint": list(ent.StartPoint),
                "EndPoint": list(ent.EndPoint),
                "Length": ent.Length
            })

        # ---------- CIRCLE ----------
        elif obj_type == "AcDbCircle":
            info.update({
                "Center": list(ent.Center),
                "Radius": ent.Radius,
                "Diameter": ent.Radius * 2,
                "Area": math.pi * ent.Radius ** 2
            })

        # ---------- ARC ----------
        elif obj_type == "AcDbArc":
            info.update({
                "Center": list(ent.Center),
                "Radius": ent.Radius,
                "StartAngle": ent.StartAngle,
                "EndAngle": ent.EndAngle,
                "ArcLength": ent.ArcLength
            })

        # ---------- POLYLINE ----------
        elif obj_type == "AcDbPolyline":
            info.update({
                "NumberOfVertices": ent.NumberOfVertices,
                "Coordinates": list(ent.Coordinates),
                "Length": ent.Length,
                "Closed": ent.Closed,
                "Area": ent.Area if ent.Closed else 0
            })

        # ---------- BLOCK ----------
        elif obj_type == "AcDbBlockReference":
            info.update({
                "BlockName": ent.Name,
                "InsertionPoint": list(ent.InsertionPoint),
                "Scale": [ent.XScaleFactor, ent.YScaleFactor, ent.ZScaleFactor],
                "Rotation": ent.Rotation,
                "IsDynamic": ent.IsDynamicBlock,
                "Attributes": get_block_attributes(ent),
                "DynamicProperties": get_block_dynamic_properties(ent)
            })

        # ---------- TEXT ----------
        elif obj_type == "AcDbText":
            info.update({
                "Text": ent.TextString,
                "InsertionPoint": list(ent.InsertionPoint),
                "Height": ent.Height,
                "Rotation": ent.Rotation
            })

        # ---------- MTEXT ----------
        elif obj_type == "AcDbMText":
            info.update({
                "Text": ent.Contents,
                "InsertionPoint": list(ent.InsertionPoint),
                "Height": ent.Height,
                "Width": ent.Width
            })

        # ---------- DIMENSION ----------
        elif "Dimension" in obj_type:
            info.update({
                "Text": ent.TextOverride,
                "Measurement": ent.Measurement
            })

        # ---------- OTHER ----------
        else:
            info["Note"] = "Chưa định nghĩa chi tiết loại đối tượng này"

    except Exception as e:
        info["Error"] = str(e)

    return info

# =====================================================
# MAIN SCAN FUNCTION
# =====================================================
def scan_selected_entities():
    acad, doc = connect_autocad()
    ss = select_objects_from_user(doc)

    results = []
    for ent in ss:
        results.append(get_technical_info(ent))

    return {
        "Count": len(results),
        "Entities": results
    }

# =====================================================
# TEST RUN
# =====================================================
if __name__ == "__main__":
    data = scan_selected_entities()
    print(json.dumps(data, indent=4, ensure_ascii=False))
