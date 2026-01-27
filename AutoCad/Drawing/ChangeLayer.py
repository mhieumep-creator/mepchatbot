using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Runtime;
using Autodesk.AutoCAD.Colors;

public static class CadUtils
{
    public static bool ChangeLayerByHandle(string handleString, string newLayerName)
    {
        Document doc = Application.DocumentManager.MdiActiveDocument;
        Database db = doc.Database;

        using (Transaction tr = db.TransactionManager.StartTransaction())
        {
            try
            {
                // 1. Parse handle
                Handle h = Handle.FromString(handleString);

                // 2. Get ObjectId from Handle
                ObjectId id = db.GetObjectId(false, h, 0);

                if (id == ObjectId.Null || !id.IsValid)
                    return false;

                // 3. Open object for write
                Entity ent = tr.GetObject(id, OpenMode.ForWrite) as Entity;
                if (ent == null) return false;

                // 4. Ensure layer exists
                LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
                if (!lt.Has(newLayerName))
                {
                    lt.UpgradeOpen();
                    LayerTableRecord ltr = new LayerTableRecord();
                    ltr.Name = newLayerName;
                    lt.Add(ltr);
                    tr.AddNewlyCreatedDBObject(ltr, true);
                }

                // 5. Change layer
                ent.Layer = newLayerName;

                tr.Commit();
                return true;
            }
            catch
            {
                tr.Abort();
                return false;
            }
        }
    }
}