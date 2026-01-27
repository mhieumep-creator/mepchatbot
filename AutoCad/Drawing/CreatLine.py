using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;

public static class CadDraw
{
    public static ObjectId CreateLine(Point3d startPoint, Point3d endPoint, string layer = "0")
    {
        Document doc = Application.DocumentManager.MdiActiveDocument;
        Database db = doc.Database;

        using (Transaction tr = db.TransactionManager.StartTransaction())
        {
            // Open ModelSpace
            BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
            BlockTableRecord ms =
                (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

            // Ensure layer exists
            LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            if (!lt.Has(layer))
            {
                lt.UpgradeOpen();
                LayerTableRecord ltr = new LayerTableRecord();
                ltr.Name = layer;
                lt.Add(ltr);
                tr.AddNewlyCreatedDBObject(ltr, true);
            }

            // Create line
            Line line = new Line(startPoint, endPoint);
            line.Layer = layer;

            ObjectId id = ms.AppendEntity(line);
            tr.AddNewlyCreatedDBObject(line, true);

            tr.Commit();
            return id;
        }
    }
}