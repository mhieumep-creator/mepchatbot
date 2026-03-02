"""
AutoCad.Getdata – Module lấy dữ liệu đối tượng từ AutoCAD.

Các hàm chính:
    get_line_data()       – Lấy thông tin Line
    get_polyline_data()   – Lấy thông tin Polyline (LW/2D/3D)
    get_mline_data()      – Lấy thông tin Mline
    get_block_data()      – Lấy thông tin Block (+ DynamicProps + Attributes)
    get_text_data()       – Lấy thông tin Text / MText
    get_leader_data()     – Lấy thông tin Leader / MLeader
    get_all_data()        – Quét chọn → tự phân loại tất cả loại trên

Tất cả hàm đều hỗ trợ:
    - object_ids: truyền ObjectID trực tiếp (không cần quét chọn)
    - layer_filter: lọc theo layer (str hoặc list[str])
"""

from AutoCad.Getdata.GetdataLine import get_line_data
from AutoCad.Getdata.GetdataPolyline import get_polyline_data
from AutoCad.Getdata.GetdataMline import get_mline_data
from AutoCad.Getdata.GetdataBlock import get_block_data
from AutoCad.Getdata.GetdataText import get_text_data
from AutoCad.Getdata.GetdataLeader import get_leader_data
from AutoCad.Getdata.GetdataAll import get_all_data
from AutoCad.Getdata.GetdataPickPoint import get_pick_point

__all__ = [
    "get_line_data",
    "get_polyline_data",
    "get_mline_data",
    "get_block_data",
    "get_text_data",
    "get_leader_data",
    "get_all_data",
    "get_pick_point",
]
