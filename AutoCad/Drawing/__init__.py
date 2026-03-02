"""
AutoCad.Drawing – Module vẽ đối tượng trong AutoCAD.

Các hàm chính:
    create_lines()              – Vẽ Line (batch)
    create_mline_von()          – Vẽ Mline bằng lệnh VON (ống thoát nước)
    create_mline_von_ppr()      – Vẽ Mline bằng lệnh VON_PPR (ống cấp nước)
    change_layer()              – Đổi layer đối tượng theo ObjectID
    insert_blocks()             – Chèn block (có Dynamic Properties)
    insert_blocks_by_name()     – Chèn cùng block tại nhiều điểm
    insert_blocks_multi()       – Chèn nhiều block khác tên
    create_polylines()          – Vẽ Polyline (batch)
    create_texts()              – Tạo Text / MText (batch)
    delete_entities()           – Xoá đối tượng theo ObjectID
    move_entities()             – Di chuyển đối tượng theo ObjectID
    copy_entities()             – Copy đối tượng theo ObjectID
"""

from AutoCad.Drawing.Lines import create_lines
from AutoCad.Drawing.Mline import (
    create_mline_von,
    create_mline_von_ppr,
)
from AutoCad.Drawing.ChangeLayer import change_layer
from AutoCad.Drawing.InsertBlockWithDynaMicProperties import insert_blocks
from AutoCad.Drawing.Block import insert_blocks_by_name, insert_blocks_multi
from AutoCad.Drawing.Polyline import create_polylines
from AutoCad.Drawing.Text import create_texts
from AutoCad.Drawing.DeleteEntities import delete_entities
from AutoCad.Drawing.MoveEntities import move_entities, copy_entities
from AutoCad.Drawing.BlockWithAttributes import insert_blocks_with_attributes

__all__ = [
    "create_lines",
    "create_mline_von",
    "create_mline_von_ppr",
    "change_layer",
    "insert_blocks",
    "insert_blocks_by_name",
    "insert_blocks_multi",
    "insert_blocks_with_attributes",
    "create_polylines",
    "create_texts",
    "delete_entities",
    "move_entities",
    "copy_entities",
]
