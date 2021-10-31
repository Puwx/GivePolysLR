import os
import arcpy
import pandas as pd

def getHullPoints(poly):
    #Check accuracy difference using something other than hullrectangle
    #Different with hullrectangle for alpha was a maximum of 20m - FROM and TO
    hull = poly.hullRectangle
    spt = hull.split()
    pts = []
    print(hull)
    for i in range(0,len(spt)-1,2):
        x = spt[i]
        y = spt[i+1]
        pts.append(arcpy.Point(x,y))
    return pts

def lrPolyPoints(inPolys,centerline,outLoc):
    sr = arcpy.Describe(inPolys).spatialReference
    getPts = []
    with arcpy.da.SearchCursor(inPolys,["OID@","SHAPE@"]) as sc:
        for row in sc:
            oid, hrPts = row[0], getHullPoints(row[1])
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
                                       radius_or_tolerance="500 meters",
                                       out_table=os.path.join(outLoc,"POLY_PTS.csv"))
    return os.path.join(outLoc,"POLY_PTS.csv")


    
if __name__ == "__main__":
    arcpy.env.overwriteOutput = True
    inPolys = arcpy.GetParameterAsText(0)
    polyFields = [f.name for f in arcpy.ListFields(inPolys)]
    centerline = arcpy.GetParameterAsText(1)
    outLoc = arcpy.GetParameterAsText(2)
    
    csvData = lrPolyPoints(inPolys,centerline,outLoc)
    df = pd.read_csv(csvData)
    df["FROM_KP"] = df["MEAS"]
    df["TO_KP"]   = df["MEAS"]
    gb = df.groupby("POLY_ID").agg({"FROM_KP":min,"TO_KP":max})
    kpDict = gb.to_dict("index")
    
    kpFields =  [{"field_name":"FROM_KP","field_type":"DOUBLE"},
                 {"field_name":"TO_KP","field_type":"DOUBLE"}]
    
    for f in kpFields:
        if f["field_name"] not in polyFields:
            arcpy.management.AddField(inPolys,f["field_name"],f["field_type"])
    
    with arcpy.da.UpdateCursor(inPolys,["OID@","FROM_KP","TO_KP"]) as uc:
        for row in uc:
            oid = row[0]
            if oid in kpDict:
                row[1] = kpDict[oid]["FROM_KP"]
                row[2] = kpDict[oid]["TO_KP"]
                uc.updateRow(row)

    arcpy.Delete_management(r"in_memory\POLY_PTS")
