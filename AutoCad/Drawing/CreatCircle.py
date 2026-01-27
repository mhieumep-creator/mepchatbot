using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Colors;

public static class CadDraw
{
    public static string CreateCircle(
        double centerX,
        double centerY,
        double radius,
        string layerName = "0",
        short colorIndex = 256 // ByLayer
    )
    {
        Document doc = Application.DocumentManager.MdiActiveDocument;
        Database db = doc.Database;

        using (Transaction tr = db.TransactionManager.StartTransaction())
        {
            // 1. Mở BlockTable và ModelSpace
            BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
            BlockTableRecord ms =
                (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

            // 2. Đảm bảo Layer tồn tại
            LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            if (!lt.Has(layerName))
            {
                lt.UpgradeOpen();
                LayerTableRecord ltr = new LayerTableRecord
                {
                    Name = layerName
                };
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }

            // 3. Tạo Circle
            Circle circle = new Circle
            {
                Center = new Point3d(centerX, centerY, 0),
                Radius = radius,
                Layer = layerName,
                Color = Color.FromColorIndex(ColorMethod.ByAci, colorIndex)
            };

            // 4. Thêm vào ModelSpace
            ms.AppendEntity(circle);
            tr.AddNewlyCreatedDBObject(circle, true);

            // 5. Lấy Handle để AI dùng tiếp
            string handle = circle.Handle.ToString();

            tr.Commit();
            return handle;
        }
    }
}