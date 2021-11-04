import os
import arcpy
import pandas as pd

def lrPolyPoints(inPolys,centerline,outLoc):
    """
    -Takes a polygon, gets the vertices of the polygon (points)
     references those points to a centerline that is also provided
    -Returns the path to a CSV file that is the linear location of those points referenced to the provided centerline
        - The POLY_ID field is used to then join the points back to the polygon that they were derived from using the other functions.
    """
    sr = arcpy.Describe(inPolys).spatialReference
    getPolyPts = lambda poly: [pt for part in poly for pt in part]
    getPts = []
    with arcpy.da.SearchCursor(inPolys,["OID@","SHAPE@"]) as sc:
        for row in sc:
            oid, hrPts = row[0], getPolyPts(row[1])
            for hp in hrPts:
                getPts.append([oid,hp])
    arcpy.management.CreateFeatureclass("in_memory","POLY_PTS","POINT",spatial_reference=sr)
    arcpy.management.AddField(r"in_memory/POLY_PTS","POLY_ID","LONG")
    with arcpy.da.InsertCursor(r"in_memory/POLY_PTS",["POLY_ID","SHAPE@"]) as ic:
        for pt in getPts:
            ic.insertRow(pt)
    clID = [f.name for f in arcpy.ListFields(centerline) if not f.required][0]
    arcpy.AddMessage(clID)
    arcpy.LocateFeaturesAlongRoutes_lr(in_features=r"in_memory/POLY_PTS",
                                       in_routes=centerline,
                                       route_id_field=clID,
                                       radius_or_tolerance="2000 meters",
                                       out_table=os.path.join(outLoc,"POLY_PTS.csv"))
    return os.path.join(outLoc,"POLY_PTS.csv")

def procCSV(csv_path):
    """
    Processes the CSV file created by lrPolyPoints
        - Adds the FROM and TO fields and groups by the polygon id
        - Returns a dictionary containing the TO and FROM with the ObjectID/Polygon ID as the key and the FROM/TO values as values
    """
    df = pd.read_csv(csv_path)
    df["PYT_FROM"] = df["MEAS"]
    df["PYT_TO"]   = df["MEAS"]
    gb = df.groupby("POLY_ID").agg({"PYT_FROM":min,"PYT_TO":max})
    kpDict = gb.to_dict("index")
    return kpDict

if __name__ == "__main__":
    arcpy.env.overwriteOutput = True
    inPolys = arcpy.GetParameterAsText(0)
    polyFields = [f.name for f in arcpy.ListFields(inPolys)]
    arcpy.AddMessage(polyFields)
    centerline = arcpy.GetParameterAsText(1)
    outLoc = arcpy.GetParameterAsText(2)
    
    csvData = lrPolyPoints(inPolys,centerline,outLoc)
    kpDict = procCSV(csvData)
    
    kpFields =  [{"field_name":"PYT_FROM","field_type":"DOUBLE"},
                 {"field_name":"PYT_TO","field_type":"DOUBLE"}]
    
    for f in kpFields:
        if f["field_name"] not in polyFields:
            arcpy.management.AddField(inPolys,f["field_name"],f["field_type"])
    
    with arcpy.da.UpdateCursor(inPolys,["OID@","PYT_FROM","PYT_TO"]) as uc:
        for row in uc:
            arcpy.AddMessage("UPDATING ROW")
            oid = row[0]
            if oid in kpDict:
                row[1] = kpDict[oid]["PYT_FROM"]
                row[2] = kpDict[oid]["PYT_TO"]
                uc.updateRow(row)

    arcpy.Delete_management(r"in_memory\POLY_PTS")
