
import os
import numpy as np
import geopandas as gpd
import osmnx as ox
import networkx as nx

# ==================
# === PARAMETERS ===

VARIABLES_GPKG_PATH = "data/VARIABLES_NEW.gpkg"
PARK_LAYER = "VARIABLES_base"

#PBF_PATH = r"C:\Users\lisajos\PycharmProjects\park_proj\data\OSM_network_data\sweden-260319.osm.pbf"
PBF_PATH = r"C:\Users\lisajos\PycharmProjects\park_proj\data\OSM_network_data\BBBike_extract_only_stockholm\stockholm.osm"

OUTPUT_PATH = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\network_analysis"
os.makedirs(OUTPUT_PATH, exist_ok=True)

NETWORK_GRAPHML = f"{OUTPUT_PATH}\\walk_network.graphml"
SERVICE_AREAS_GPKG = f"{OUTPUT_PATH}\\service_area_of_parks.gpkg"

TIME_CUTOFF = 600         # 600 sec = 10 min
WALK_SPEED_KPH = 5
EDGE_BUFFER = 25
BOUNDARY_SAMPLE_DISTANCE = 50

# ==================
# === LOAD PARKS ===

parks = gpd.read_file(VARIABLES_GPKG_PATH, layer=PARK_LAYER)

if parks.crs is None:
    parks = parks.set_crs(epsg=3006)

parks_3006 = parks.to_crs(epsg=3006)
parks_wgs = parks.to_crs(epsg=4326)

# ==========================
# === STUDY AREA ===

study_area_3006 = parks_3006.union_all().buffer(2000)

study_area_poly = gpd.GeoSeries(
    [study_area_3006], crs=3006
).to_crs(epsg=4326).iloc[0]

# ==========================
# === LOAD OR BUILD GRAPH ===

if os.path.exists(NETWORK_GRAPHML):
    print("Loading saved network...")
    G = ox.load_graphml(NETWORK_GRAPHML)

else:
    print("Building graph from PBF (this may take a few minutes)...")

    # --- Load full graph from file (no filtering yet) ---
    G = ox.graph_from_xml(PBF_PATH)

    print("Converting graph to GeoDataFrames...")
    nodes, edges = ox.graph_to_gdfs(G)

    print("Filtering walkable edges...")

    # Keep only walkable road types
    walkable = edges[
        edges["highway"].isin([
            "footway", "path", "pedestrian", "living_street",
            "residential", "service", "track", "unclassified",
            "cycleway"
        ])
    ].copy()

    print(f"Edges before filtering: {len(edges)}")
    print(f"Edges after filtering: {len(walkable)}")

    ###########################
    # --- FIX: convert list attributes to strings ---
    def clean_attributes(df):
        for col in df.columns:
            df[col] = df[col].apply(
                lambda x: x[0] if isinstance(x, list) else x
            )
        return df


    walkable = clean_attributes(walkable)
    nodes = clean_attributes(nodes)
    ###########################

    # --- Rebuild graph from filtered edges ---
    G = ox.graph_from_gdfs(nodes, walkable)

    print("Simplifying graph...")
    G = ox.simplify_graph(G)

    print("Clipping to study area...")
    G = ox.truncate.truncate_graph_polygon(G, study_area_poly)

    print("Saving graph...")
    ox.save_graphml(G, NETWORK_GRAPHML)

print("Final graph size:")
print("Nodes:", len(G.nodes))
print("Edges:", len(G.edges))

# =============================
# === ADD TRAVEL TIME ===

for u, v, k, data in G.edges(keys=True, data=True):
    data["speed_kph"] = WALK_SPEED_KPH
    data["travel_time"] = data["length"] / (WALK_SPEED_KPH * 1000 / 3600)

# ===========================================
# === SAMPLE BOUNDARY POINTS ===

def sample_boundary(geom, spacing):
    length = geom.length
    distances = np.arange(0, length, spacing)
    return [geom.interpolate(d) for d in distances]

# =============================================
# === FAST ISOCHRONE FUNCTION ===

def make_isochrone(G, points, time_cutoff):
    nodes = []

    for pt in points:
        try:
            node, dist = ox.distance.nearest_nodes(
                G, pt.x, pt.y, return_dist=True
            )

            if dist < 150:
                nodes.append(node)

        except:
            continue

    nodes = list(set(nodes))

    if not nodes:
        return None

    lengths = nx.multi_source_dijkstra_path_length(
        G,
        sources=nodes,
        cutoff=time_cutoff,
        weight="travel_time"
    )

    reachable_nodes = list(lengths.keys())

    if not reachable_nodes:
        return None

    subgraph = G.subgraph(reachable_nodes).copy()
    subgraph = ox.convert.to_undirected(subgraph)

    edges = ox.graph_to_gdfs(subgraph, nodes=False)
    edges_proj = edges.to_crs(epsg=3006)

    polygon = edges_proj.buffer(EDGE_BUFFER).union_all()

    polygon = gpd.GeoSeries([polygon], crs=3006).to_crs(epsg=4326).iloc[0]

    return polygon

# =======================================
# === GENERATE SERVICE AREAS ===

service_geoms = []

for idx, row in parks_3006.iterrows():
    print(f"Processing park {idx + 1}/{len(parks_3006)}")

    try:
        boundary = row.geometry.boundary
        points_3006 = sample_boundary(boundary, BOUNDARY_SAMPLE_DISTANCE)

        if not points_3006:
            service_geoms.append(None)
            continue

        points_wgs = gpd.GeoSeries(points_3006, crs=3006).to_crs(epsg=4326)

        iso = make_isochrone(G, points_wgs, TIME_CUTOFF)
        service_geoms.append(iso)

    except Exception as e:
        print(f"Error processing park {idx}: {e}")
        service_geoms.append(None)

# ==============
# === OUTPUT ===

service_areas = gpd.GeoDataFrame(
    parks.drop(columns="geometry"),
    geometry=service_geoms,
    crs="EPSG:4326"
)

service_areas = service_areas[
    service_areas.geometry.notnull() & ~service_areas.geometry.is_empty
]

service_areas = service_areas.to_crs(epsg=3006)

service_areas.to_file(SERVICE_AREAS_GPKG, layer="service_areas", driver="GPKG")


# Building graph from PBF (this may take a few minutes)...
# Converting graph to GeoDataFrames...
# Filtering walkable edges...
# Edges before filtering: 2393210
# Edges after filtering: 761140
# Simplifying graph...
# Clipping to study area...
# Saving graph...
# Final graph size:
# Nodes: 226447
# Edges: 307367
# Processing park 1/1082
# Processing park 2/1082
# Processing park 3/1082
# Processing park 4/1082
# Processing park 5/1082
# Processing park 6/1082
# Processing park 7/1082
# Processing park 8/1082
# Processing park 9/1082
# Processing park 10/1082
# Processing park 11/1082
# Processing park 12/1082
# Processing park 13/1082
# Processing park 14/1082
# Processing park 15/1082
# Processing park 16/1082
# Processing park 17/1082
# Processing park 18/1082
# Processing park 19/1082
# Processing park 20/1082
# Processing park 21/1082
# Processing park 22/1082
# Processing park 23/1082
# Processing park 24/1082
# Processing park 25/1082
# Processing park 26/1082
# Processing park 27/1082
# Processing park 28/1082
# Processing park 29/1082
# Processing park 30/1082
# Processing park 31/1082
# Processing park 32/1082
# Processing park 33/1082
# Processing park 34/1082
# Processing park 35/1082
# Processing park 36/1082
# Processing park 37/1082
# Processing park 38/1082
# Processing park 39/1082
# Processing park 40/1082
# Processing park 41/1082
# Processing park 42/1082
# Processing park 43/1082
# Processing park 44/1082
# Processing park 45/1082
# Processing park 46/1082
# Processing park 47/1082
# Processing park 48/1082
# Processing park 49/1082
# Processing park 50/1082
# Processing park 51/1082
# Processing park 52/1082
# Processing park 53/1082
# Processing park 54/1082
# Processing park 55/1082
# Processing park 56/1082
# Processing park 57/1082
# Processing park 58/1082
# Processing park 59/1082
# Processing park 60/1082
# Processing park 61/1082
# Processing park 62/1082
# Processing park 63/1082
# Processing park 64/1082
# Processing park 65/1082
# Processing park 66/1082
# Processing park 67/1082
# Processing park 68/1082
# Processing park 69/1082
# Processing park 70/1082
# Processing park 71/1082
# Processing park 72/1082
# Processing park 73/1082
# Processing park 74/1082
# Processing park 75/1082
# Processing park 76/1082
# Processing park 77/1082
# Processing park 78/1082
# Processing park 79/1082
# Processing park 80/1082
# Processing park 81/1082
# Processing park 82/1082
# Processing park 83/1082
# Processing park 84/1082
# Processing park 85/1082
# Processing park 86/1082
# Processing park 87/1082
# Processing park 88/1082
# Processing park 89/1082
# Processing park 90/1082
# Processing park 91/1082
# Processing park 92/1082
# Processing park 93/1082
# Processing park 94/1082
# Processing park 95/1082
# Processing park 96/1082
# Processing park 97/1082
# Processing park 98/1082
# Processing park 99/1082
# Processing park 100/1082
# Processing park 101/1082
# Processing park 102/1082
# Processing park 103/1082
# Processing park 104/1082
# Processing park 105/1082
# Processing park 106/1082
# Processing park 107/1082
# Processing park 108/1082
# Processing park 109/1082
# Processing park 110/1082
# Processing park 111/1082
# Processing park 112/1082
# Processing park 113/1082
# Processing park 114/1082
# Processing park 115/1082
# Processing park 116/1082
# Processing park 117/1082
# Processing park 118/1082
# Processing park 119/1082
# Processing park 120/1082
# Processing park 121/1082
# Processing park 122/1082
# Processing park 123/1082
# Processing park 124/1082
# Processing park 125/1082
# Processing park 126/1082
# Processing park 127/1082
# Processing park 128/1082
# Processing park 129/1082
# Processing park 130/1082
# Processing park 131/1082
# Processing park 132/1082
# Processing park 133/1082
# Processing park 134/1082
# Processing park 135/1082
# Processing park 136/1082
# Processing park 137/1082
# Processing park 138/1082
# Processing park 139/1082
# Processing park 140/1082
# Processing park 141/1082
# Processing park 142/1082
# Processing park 143/1082
# Processing park 144/1082
# Processing park 145/1082
# Processing park 146/1082
# Processing park 147/1082
# Processing park 148/1082
# Processing park 149/1082
# Processing park 150/1082
# Processing park 151/1082
# Processing park 152/1082
# Processing park 153/1082
# Processing park 154/1082
# Processing park 155/1082
# Processing park 156/1082
# Processing park 157/1082
# Processing park 158/1082
# Processing park 159/1082
# Processing park 160/1082
# Processing park 161/1082
# Processing park 162/1082
# Processing park 163/1082
# Processing park 164/1082
# Processing park 165/1082
# Processing park 166/1082
# Processing park 167/1082
# Processing park 168/1082
# Processing park 169/1082
# Processing park 170/1082
# Processing park 171/1082
# Processing park 172/1082
# Processing park 173/1082
# Processing park 174/1082
# Processing park 175/1082
# Processing park 176/1082
# Processing park 177/1082
# Processing park 178/1082
# Processing park 179/1082
# Processing park 180/1082
# Processing park 181/1082
# Processing park 182/1082
# Processing park 183/1082
# Processing park 184/1082
# Processing park 185/1082
# Processing park 186/1082
# Processing park 187/1082
# Processing park 188/1082
# Processing park 189/1082
# Processing park 190/1082
# Processing park 191/1082
# Processing park 192/1082
# Processing park 193/1082
# Processing park 194/1082
# Processing park 195/1082
# Processing park 196/1082
# Processing park 197/1082
# Processing park 198/1082
# Processing park 199/1082
# Processing park 200/1082
# Processing park 201/1082
# Processing park 202/1082
# Processing park 203/1082
# Processing park 204/1082
# Processing park 205/1082
# Processing park 206/1082
# Processing park 207/1082
# Processing park 208/1082
# Processing park 209/1082
# Processing park 210/1082
# Processing park 211/1082
# Processing park 212/1082
# Processing park 213/1082
# Processing park 214/1082
# Processing park 215/1082
# Processing park 216/1082
# Processing park 217/1082
# Processing park 218/1082
# Processing park 219/1082
# Processing park 220/1082
# Processing park 221/1082
# Processing park 222/1082
# Processing park 223/1082
# Processing park 224/1082
# Processing park 225/1082
# Processing park 226/1082
# Processing park 227/1082
# Processing park 228/1082
# Processing park 229/1082
# Processing park 230/1082
# Processing park 231/1082
# Processing park 232/1082
# Processing park 233/1082
# Processing park 234/1082
# Processing park 235/1082
# Processing park 236/1082
# Processing park 237/1082
# Processing park 238/1082
# Processing park 239/1082
# Processing park 240/1082
# Processing park 241/1082
# Processing park 242/1082
# Processing park 243/1082
# Processing park 244/1082
# Processing park 245/1082
# Processing park 246/1082
# Processing park 247/1082
# Processing park 248/1082
# Processing park 249/1082
# Processing park 250/1082
# Processing park 251/1082
# Error processing park 250: Graph contains no edges.
# Processing park 252/1082
# Error processing park 251: Graph contains no edges.
# Processing park 253/1082
# Processing park 254/1082
# Processing park 255/1082
# Processing park 256/1082
# Processing park 257/1082
# Processing park 258/1082
# Processing park 259/1082
# Processing park 260/1082
# Processing park 261/1082
# Processing park 262/1082
# Processing park 263/1082
# Processing park 264/1082
# Processing park 265/1082
# Processing park 266/1082
# Processing park 267/1082
# Processing park 268/1082
# Processing park 269/1082
# Processing park 270/1082
# Processing park 271/1082
# Processing park 272/1082
# Processing park 273/1082
# Processing park 274/1082
# Processing park 275/1082
# Processing park 276/1082
# Processing park 277/1082
# Processing park 278/1082
# Processing park 279/1082
# Processing park 280/1082
# Processing park 281/1082
# Processing park 282/1082
# Processing park 283/1082
# Processing park 284/1082
# Processing park 285/1082
# Processing park 286/1082
# Processing park 287/1082
# Processing park 288/1082
# Processing park 289/1082
# Processing park 290/1082
# Error processing park 289: Graph contains no edges.
# Processing park 291/1082
# Error processing park 290: Graph contains no edges.
# Processing park 292/1082
# Processing park 293/1082
# Processing park 294/1082
# Processing park 295/1082
# Error processing park 294: Graph contains no edges.
# Processing park 296/1082
# Processing park 297/1082
# Error processing park 296: Graph contains no edges.
# Processing park 298/1082
# Processing park 299/1082
# Processing park 300/1082
# Processing park 301/1082
# Processing park 302/1082
# Processing park 303/1082
# Processing park 304/1082
# Processing park 305/1082
# Processing park 306/1082
# Processing park 307/1082
# Processing park 308/1082
# Processing park 309/1082
# Processing park 310/1082
# Error processing park 309: Graph contains no edges.
# Processing park 311/1082
# Error processing park 310: Graph contains no edges.
# Processing park 312/1082
# Processing park 313/1082
# Processing park 314/1082
# Processing park 315/1082
# Processing park 316/1082
# Processing park 317/1082
# Processing park 318/1082
# Processing park 319/1082
# Processing park 320/1082
# Processing park 321/1082
# Processing park 322/1082
# Processing park 323/1082
# Processing park 324/1082
# Processing park 325/1082
# Processing park 326/1082
# Processing park 327/1082
# Processing park 328/1082
# Processing park 329/1082
# Processing park 330/1082
# Error processing park 329: Graph contains no edges.
# Processing park 331/1082
# Processing park 332/1082
# Processing park 333/1082
# Processing park 334/1082
# Processing park 335/1082
# Processing park 336/1082
# Processing park 337/1082
# Processing park 338/1082
# Error processing park 337: Graph contains no edges.
# Processing park 339/1082
# Processing park 340/1082
# Processing park 341/1082
# Error processing park 340: Graph contains no edges.
# Processing park 342/1082
# Processing park 343/1082
# Processing park 344/1082
# Processing park 345/1082
# Processing park 346/1082
# Processing park 347/1082
# Processing park 348/1082
# Error processing park 347: Graph contains no edges.
# Processing park 349/1082
# Processing park 350/1082
# Processing park 351/1082
# Processing park 352/1082
# Processing park 353/1082
# Processing park 354/1082
# Processing park 355/1082
# Processing park 356/1082
# Processing park 357/1082
# Processing park 358/1082
# Processing park 359/1082
# Processing park 360/1082
# Processing park 361/1082
# Processing park 362/1082
# Processing park 363/1082
# Processing park 364/1082
# Processing park 365/1082
# Processing park 366/1082
# Processing park 367/1082
# Processing park 368/1082
# Processing park 369/1082
# Processing park 370/1082
# Processing park 371/1082
# Processing park 372/1082
# Processing park 373/1082
# Processing park 374/1082
# Processing park 375/1082
# Processing park 376/1082
# Processing park 377/1082
# Processing park 378/1082
# Processing park 379/1082
# Processing park 380/1082
# Processing park 381/1082
# Processing park 382/1082
# Processing park 383/1082
# Processing park 384/1082
# Processing park 385/1082
# Processing park 386/1082
# Processing park 387/1082
# Processing park 388/1082
# Processing park 389/1082
# Processing park 390/1082
# Processing park 391/1082
# Processing park 392/1082
# Processing park 393/1082
# Processing park 394/1082
# Processing park 395/1082
# Processing park 396/1082
# Processing park 397/1082
# Processing park 398/1082
# Processing park 399/1082
# Processing park 400/1082
# Processing park 401/1082
# Processing park 402/1082
# Processing park 403/1082
# Processing park 404/1082
# Processing park 405/1082
# Error processing park 404: Graph contains no edges.
# Processing park 406/1082
# Processing park 407/1082
# Error processing park 406: Graph contains no edges.
# Processing park 408/1082
# Processing park 409/1082
# Processing park 410/1082
# Processing park 411/1082
# Processing park 412/1082
# Processing park 413/1082
# Processing park 414/1082
# Processing park 415/1082
# Processing park 416/1082
# Processing park 417/1082
# Processing park 418/1082
# Processing park 419/1082
# Error processing park 418: Graph contains no edges.
# Processing park 420/1082
# Processing park 421/1082
# Processing park 422/1082
# Processing park 423/1082
# Processing park 424/1082
# Processing park 425/1082
# Processing park 426/1082
# Processing park 427/1082
# Processing park 428/1082
# Processing park 429/1082
# Processing park 430/1082
# Processing park 431/1082
# Processing park 432/1082
# Processing park 433/1082
# Processing park 434/1082
# Processing park 435/1082
# Processing park 436/1082
# Error processing park 435: Graph contains no edges.
# Processing park 437/1082
# Processing park 438/1082
# Processing park 439/1082
# Processing park 440/1082
# Processing park 441/1082
# Processing park 442/1082
# Processing park 443/1082
# Processing park 444/1082
# Processing park 445/1082
# Processing park 446/1082
# Processing park 447/1082
# Processing park 448/1082
# Processing park 449/1082
# Processing park 450/1082
# Processing park 451/1082
# Processing park 452/1082
# Processing park 453/1082
# Error processing park 452: Graph contains no edges.
# Processing park 454/1082
# Processing park 455/1082
# Processing park 456/1082
# Processing park 457/1082
# Error processing park 456: Graph contains no edges.
# Processing park 458/1082
# Processing park 459/1082
# Processing park 460/1082
# Processing park 461/1082
# Processing park 462/1082
# Processing park 463/1082
# Processing park 464/1082
# Processing park 465/1082
# Processing park 466/1082
# Processing park 467/1082
# Processing park 468/1082
# Processing park 469/1082
# Processing park 470/1082
# Processing park 471/1082
# Processing park 472/1082
# Processing park 473/1082
# Processing park 474/1082
# Processing park 475/1082
# Processing park 476/1082
# Processing park 477/1082
# Processing park 478/1082
# Processing park 479/1082
# Processing park 480/1082
# Processing park 481/1082
# Processing park 482/1082
# Processing park 483/1082
# Processing park 484/1082
# Processing park 485/1082
# Error processing park 484: Graph contains no edges.
# Processing park 486/1082
# Processing park 487/1082
# Processing park 488/1082
# Processing park 489/1082
# Processing park 490/1082
# Processing park 491/1082
# Processing park 492/1082
# Processing park 493/1082
# Processing park 494/1082
# Processing park 495/1082
# Processing park 496/1082
# Processing park 497/1082
# Processing park 498/1082
# Processing park 499/1082
# Processing park 500/1082
# Processing park 501/1082
# Processing park 502/1082
# Processing park 503/1082
# Processing park 504/1082
# Error processing park 503: Graph contains no edges.
# Processing park 505/1082
# Processing park 506/1082
# Processing park 507/1082
# Processing park 508/1082
# Processing park 509/1082
# Processing park 510/1082
# Processing park 511/1082
# Processing park 512/1082
# Processing park 513/1082
# Processing park 514/1082
# Processing park 515/1082
# Processing park 516/1082
# Processing park 517/1082
# Processing park 518/1082
# Processing park 519/1082
# Processing park 520/1082
# Processing park 521/1082
# Processing park 522/1082
# Processing park 523/1082
# Processing park 524/1082
# Processing park 525/1082
# Processing park 526/1082
# Processing park 527/1082
# Processing park 528/1082
# Processing park 529/1082
# Processing park 530/1082
# Processing park 531/1082
# Processing park 532/1082
# Processing park 533/1082
# Processing park 534/1082
# Processing park 535/1082
# Processing park 536/1082
# Processing park 537/1082
# Processing park 538/1082
# Processing park 539/1082
# Processing park 540/1082
# Processing park 541/1082
# Processing park 542/1082
# Processing park 543/1082
# Processing park 544/1082
# Processing park 545/1082
# Processing park 546/1082
# Processing park 547/1082
# Processing park 548/1082
# Processing park 549/1082
# Processing park 550/1082
# Processing park 551/1082
# Error processing park 550: Graph contains no edges.
# Processing park 552/1082
# Processing park 553/1082
# Processing park 554/1082
# Processing park 555/1082
# Processing park 556/1082
# Processing park 557/1082
# Processing park 558/1082
# Processing park 559/1082
# Processing park 560/1082
# Processing park 561/1082
# Processing park 562/1082
# Processing park 563/1082
# Processing park 564/1082
# Processing park 565/1082
# Processing park 566/1082
# Processing park 567/1082
# Processing park 568/1082
# Processing park 569/1082
# Processing park 570/1082
# Processing park 571/1082
# Processing park 572/1082
# Processing park 573/1082
# Processing park 574/1082
# Processing park 575/1082
# Processing park 576/1082
# Processing park 577/1082
# Processing park 578/1082
# Processing park 579/1082
# Processing park 580/1082
# Processing park 581/1082
# Processing park 582/1082
# Processing park 583/1082
# Processing park 584/1082
# Processing park 585/1082
# Processing park 586/1082
# Processing park 587/1082
# Processing park 588/1082
# Processing park 589/1082
# Processing park 590/1082
# Error processing park 589: Graph contains no edges.
# Processing park 591/1082
# Processing park 592/1082
# Processing park 593/1082
# Processing park 594/1082
# Processing park 595/1082
# Processing park 596/1082
# Processing park 597/1082
# Processing park 598/1082
# Processing park 599/1082
# Processing park 600/1082
# Processing park 601/1082
# Processing park 602/1082
# Processing park 603/1082
# Processing park 604/1082
# Processing park 605/1082
# Processing park 606/1082
# Processing park 607/1082
# Processing park 608/1082
# Processing park 609/1082
# Processing park 610/1082
# Processing park 611/1082
# Processing park 612/1082
# Processing park 613/1082
# Processing park 614/1082
# Processing park 615/1082
# Processing park 616/1082
# Processing park 617/1082
# Error processing park 616: Graph contains no edges.
# Processing park 618/1082
# Processing park 619/1082
# Processing park 620/1082
# Processing park 621/1082
# Processing park 622/1082
# Processing park 623/1082
# Processing park 624/1082
# Processing park 625/1082
# Processing park 626/1082
# Processing park 627/1082
# Processing park 628/1082
# Processing park 629/1082
# Processing park 630/1082
# Processing park 631/1082
# Processing park 632/1082
# Processing park 633/1082
# Processing park 634/1082
# Processing park 635/1082
# Processing park 636/1082
# Processing park 637/1082
# Processing park 638/1082
# Processing park 639/1082
# Processing park 640/1082
# Processing park 641/1082
# Processing park 642/1082
# Processing park 643/1082
# Processing park 644/1082
# Processing park 645/1082
# Error processing park 644: Graph contains no edges.
# Processing park 646/1082
# Processing park 647/1082
# Processing park 648/1082
# Processing park 649/1082
# Processing park 650/1082
# Processing park 651/1082
# Processing park 652/1082
# Processing park 653/1082
# Processing park 654/1082
# Processing park 655/1082
# Processing park 656/1082
# Processing park 657/1082
# Processing park 658/1082
# Processing park 659/1082
# Processing park 660/1082
# Processing park 661/1082
# Processing park 662/1082
# Processing park 663/1082
# Processing park 664/1082
# Processing park 665/1082
# Processing park 666/1082
# Processing park 667/1082
# Processing park 668/1082
# Processing park 669/1082
# Processing park 670/1082
# Processing park 671/1082
# Processing park 672/1082
# Processing park 673/1082
# Processing park 674/1082
# Processing park 675/1082
# Processing park 676/1082
# Processing park 677/1082
# Processing park 678/1082
# Processing park 679/1082
# Processing park 680/1082
# Processing park 681/1082
# Processing park 682/1082
# Processing park 683/1082
# Processing park 684/1082
# Processing park 685/1082
# Processing park 686/1082
# Processing park 687/1082
# Processing park 688/1082
# Processing park 689/1082
# Processing park 690/1082
# Processing park 691/1082
# Processing park 692/1082
# Processing park 693/1082
# Processing park 694/1082
# Processing park 695/1082
# Processing park 696/1082
# Processing park 697/1082
# Processing park 698/1082
# Processing park 699/1082
# Processing park 700/1082
# Processing park 701/1082
# Processing park 702/1082
# Processing park 703/1082
# Processing park 704/1082
# Processing park 705/1082
# Processing park 706/1082
# Processing park 707/1082
# Processing park 708/1082
# Processing park 709/1082
# Error processing park 708: Graph contains no edges.
# Processing park 710/1082
# Processing park 711/1082
# Processing park 712/1082
# Processing park 713/1082
# Processing park 714/1082
# Processing park 715/1082
# Processing park 716/1082
# Processing park 717/1082
# Processing park 718/1082
# Processing park 719/1082
# Processing park 720/1082
# Processing park 721/1082
# Processing park 722/1082
# Processing park 723/1082
# Processing park 724/1082
# Processing park 725/1082
# Processing park 726/1082
# Processing park 727/1082
# Processing park 728/1082
# Processing park 729/1082
# Processing park 730/1082
# Processing park 731/1082
# Processing park 732/1082
# Processing park 733/1082
# Processing park 734/1082
# Processing park 735/1082
# Processing park 736/1082
# Processing park 737/1082
# Processing park 738/1082
# Processing park 739/1082
# Processing park 740/1082
# Processing park 741/1082
# Processing park 742/1082
# Processing park 743/1082
# Processing park 744/1082
# Error processing park 743: Graph contains no edges.
# Processing park 745/1082
# Processing park 746/1082
# Processing park 747/1082
# Processing park 748/1082
# Processing park 749/1082
# Processing park 750/1082
# Error processing park 749: Graph contains no edges.
# Processing park 751/1082
# Processing park 752/1082
# Processing park 753/1082
# Processing park 754/1082
# Processing park 755/1082
# Processing park 756/1082
# Processing park 757/1082
# Processing park 758/1082
# Processing park 759/1082
# Processing park 760/1082
# Processing park 761/1082
# Processing park 762/1082
# Processing park 763/1082
# Processing park 764/1082
# Processing park 765/1082
# Processing park 766/1082
# Processing park 767/1082
# Processing park 768/1082
# Error processing park 767: Graph contains no edges.
# Processing park 769/1082
# Processing park 770/1082
# Processing park 771/1082
# Processing park 772/1082
# Processing park 773/1082
# Processing park 774/1082
# Processing park 775/1082
# Processing park 776/1082
# Processing park 777/1082
# Processing park 778/1082
# Processing park 779/1082
# Processing park 780/1082
# Processing park 781/1082
# Processing park 782/1082
# Processing park 783/1082
# Processing park 784/1082
# Error processing park 783: Graph contains no edges.
# Processing park 785/1082
# Processing park 786/1082
# Processing park 787/1082
# Processing park 788/1082
# Processing park 789/1082
# Processing park 790/1082
# Processing park 791/1082
# Processing park 792/1082
# Processing park 793/1082
# Processing park 794/1082
# Processing park 795/1082
# Processing park 796/1082
# Processing park 797/1082
# Processing park 798/1082
# Processing park 799/1082
# Processing park 800/1082
# Processing park 801/1082
# Processing park 802/1082
# Processing park 803/1082
# Processing park 804/1082
# Processing park 805/1082
# Processing park 806/1082
# Processing park 807/1082
# Processing park 808/1082
# Processing park 809/1082
# Processing park 810/1082
# Processing park 811/1082
# Processing park 812/1082
# Processing park 813/1082
# Processing park 814/1082
# Processing park 815/1082
# Processing park 816/1082
# Processing park 817/1082
# Processing park 818/1082
# Processing park 819/1082
# Processing park 820/1082
# Processing park 821/1082
# Processing park 822/1082
# Processing park 823/1082
# Processing park 824/1082
# Processing park 825/1082
# Processing park 826/1082
# Processing park 827/1082
# Processing park 828/1082
# Processing park 829/1082
# Processing park 830/1082
# Processing park 831/1082
# Error processing park 830: Graph contains no edges.
# Processing park 832/1082
# Processing park 833/1082
# Processing park 834/1082
# Processing park 835/1082
# Processing park 836/1082
# Processing park 837/1082
# Processing park 838/1082
# Processing park 839/1082
# Processing park 840/1082
# Processing park 841/1082
# Error processing park 840: Graph contains no edges.
# Processing park 842/1082
# Processing park 843/1082
# Processing park 844/1082
# Processing park 845/1082
# Processing park 846/1082
# Processing park 847/1082
# Processing park 848/1082
# Processing park 849/1082
# Processing park 850/1082
# Processing park 851/1082
# Processing park 852/1082
# Processing park 853/1082
# Processing park 854/1082
# Processing park 855/1082
# Processing park 856/1082
# Processing park 857/1082
# Processing park 858/1082
# Processing park 859/1082
# Processing park 860/1082
# Processing park 861/1082
# Processing park 862/1082
# Processing park 863/1082
# Processing park 864/1082
# Processing park 865/1082
# Processing park 866/1082
# Processing park 867/1082
# Processing park 868/1082
# Processing park 869/1082
# Processing park 870/1082
# Processing park 871/1082
# Processing park 872/1082
# Processing park 873/1082
# Processing park 874/1082
# Processing park 875/1082
# Processing park 876/1082
# Processing park 877/1082
# Processing park 878/1082
# Processing park 879/1082
# Processing park 880/1082
# Processing park 881/1082
# Processing park 882/1082
# Processing park 883/1082
# Processing park 884/1082
# Processing park 885/1082
# Processing park 886/1082
# Processing park 887/1082
# Processing park 888/1082
# Processing park 889/1082
# Processing park 890/1082
# Processing park 891/1082
# Processing park 892/1082
# Processing park 893/1082
# Processing park 894/1082
# Processing park 895/1082
# Processing park 896/1082
# Processing park 897/1082
# Processing park 898/1082
# Processing park 899/1082
# Processing park 900/1082
# Processing park 901/1082
# Processing park 902/1082
# Processing park 903/1082
# Processing park 904/1082
# Processing park 905/1082
# Processing park 906/1082
# Processing park 907/1082
# Processing park 908/1082
# Processing park 909/1082
# Processing park 910/1082
# Processing park 911/1082
# Processing park 912/1082
# Processing park 913/1082
# Processing park 914/1082
# Processing park 915/1082
# Processing park 916/1082
# Processing park 917/1082
# Processing park 918/1082
# Processing park 919/1082
# Processing park 920/1082
# Processing park 921/1082
# Processing park 922/1082
# Processing park 923/1082
# Processing park 924/1082
# Processing park 925/1082
# Processing park 926/1082
# Processing park 927/1082
# Processing park 928/1082
# Processing park 929/1082
# Processing park 930/1082
# Processing park 931/1082
# Processing park 932/1082
# Processing park 933/1082
# Processing park 934/1082
# Processing park 935/1082
# Processing park 936/1082
# Error processing park 935: Graph contains no edges.
# Processing park 937/1082
# Processing park 938/1082
# Processing park 939/1082
# Processing park 940/1082
# Processing park 941/1082
# Processing park 942/1082
# Processing park 943/1082
# Processing park 944/1082
# Processing park 945/1082
# Processing park 946/1082
# Processing park 947/1082
# Processing park 948/1082
# Processing park 949/1082
# Processing park 950/1082
# Processing park 951/1082
# Processing park 952/1082
# Processing park 953/1082
# Processing park 954/1082
# Processing park 955/1082
# Processing park 956/1082
# Processing park 957/1082
# Processing park 958/1082
# Error processing park 957: Graph contains no edges.
# Processing park 959/1082
# Processing park 960/1082
# Processing park 961/1082
# Processing park 962/1082
# Processing park 963/1082
# Processing park 964/1082
# Error processing park 963: Graph contains no edges.
# Processing park 965/1082
# Processing park 966/1082
# Processing park 967/1082
# Processing park 968/1082
# Processing park 969/1082
# Processing park 970/1082
# Processing park 971/1082
# Processing park 972/1082
# Error processing park 971: Graph contains no edges.
# Processing park 973/1082
# Processing park 974/1082
# Processing park 975/1082
# Processing park 976/1082
# Processing park 977/1082
# Processing park 978/1082
# Processing park 979/1082
# Processing park 980/1082
# Processing park 981/1082
# Processing park 982/1082
# Processing park 983/1082
# Processing park 984/1082
# Processing park 985/1082
# Processing park 986/1082
# Processing park 987/1082
# Processing park 988/1082
# Processing park 989/1082
# Processing park 990/1082
# Processing park 991/1082
# Processing park 992/1082
# Processing park 993/1082
# Processing park 994/1082
# Processing park 995/1082
# Processing park 996/1082
# Processing park 997/1082
# Processing park 998/1082
# Processing park 999/1082
# Processing park 1000/1082
# Processing park 1001/1082
# Processing park 1002/1082
# Processing park 1003/1082
# Error processing park 1002: Graph contains no edges.
# Processing park 1004/1082
# Processing park 1005/1082
# Processing park 1006/1082
# Processing park 1007/1082
# Processing park 1008/1082
# Processing park 1009/1082
# Processing park 1010/1082
# Processing park 1011/1082
# Processing park 1012/1082
# Processing park 1013/1082
# Processing park 1014/1082
# Processing park 1015/1082
# Processing park 1016/1082
# Processing park 1017/1082
# Processing park 1018/1082
# Error processing park 1017: Graph contains no edges.
# Processing park 1019/1082
# Processing park 1020/1082
# Processing park 1021/1082
# Processing park 1022/1082
# Processing park 1023/1082
# Processing park 1024/1082
# Processing park 1025/1082
# Processing park 1026/1082
# Processing park 1027/1082
# Processing park 1028/1082
# Processing park 1029/1082
# Processing park 1030/1082
# Processing park 1031/1082
# Processing park 1032/1082
# Error processing park 1031: Graph contains no edges.
# Processing park 1033/1082
# Processing park 1034/1082
# Processing park 1035/1082
# Processing park 1036/1082
# Processing park 1037/1082
# Processing park 1038/1082
# Processing park 1039/1082
# Processing park 1040/1082
# Processing park 1041/1082
# Processing park 1042/1082
# Processing park 1043/1082
# Processing park 1044/1082
# Processing park 1045/1082
# Processing park 1046/1082
# Processing park 1047/1082
# Processing park 1048/1082
# Processing park 1049/1082
# Processing park 1050/1082
# Processing park 1051/1082
# Error processing park 1050: Graph contains no edges.
# Processing park 1052/1082
# Processing park 1053/1082
# Processing park 1054/1082
# Processing park 1055/1082
# Processing park 1056/1082
# Processing park 1057/1082
# Processing park 1058/1082
# Processing park 1059/1082
# Processing park 1060/1082
# Processing park 1061/1082
# Processing park 1062/1082
# Processing park 1063/1082
# Processing park 1064/1082
# Processing park 1065/1082
# Processing park 1066/1082
# Processing park 1067/1082
# Processing park 1068/1082
# Processing park 1069/1082
# Processing park 1070/1082
# Processing park 1071/1082
# Processing park 1072/1082
# Processing park 1073/1082
# Processing park 1074/1082
# Processing park 1075/1082
# Processing park 1076/1082
# Processing park 1077/1082
# Processing park 1078/1082
# Processing park 1079/1082
# Processing park 1080/1082
# Processing park 1081/1082
# Processing park 1082/1082
#
# Process finished with exit code 0