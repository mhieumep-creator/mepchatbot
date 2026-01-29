import win32com.client
from win32com.client import VARIANT
import pythoncom

def APoint(x, y, z=0):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (x, y, z))

def create_line_with_layer(start_point, end_point, layer_name):
    acad = win32com.client.Dispatch("AutoCAD.Application")
    acad.Visible = True

    doc = acad.ActiveDocument
    ms = doc.ModelSpace
    layers = doc.Layers

    # Kiểm tra layer tồn tại
    layer_exists = False
    for i in range(layers.Count):
        if layers.Item(i).Name.lower() == layer_name.lower():
            layer_exists = True
            break

    if not layer_exists:
        layers.Add(layer_name)

    sp = APoint(*start_point)
    ep = APoint(*end_point)

    line = ms.AddLine(sp, ep)
    line.Layer = layer_name

    return line, line.Handle
