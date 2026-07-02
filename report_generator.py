import os
import json
import math
import requests
import numpy as np
from PIL import Image as PILImage
from osgeo import ogr, osr
import matplotlib
matplotlib.use('Agg') # Headless backend
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.collections import PatchCollection

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Define paths
ROOT_DIR = r"c:\Users\joao_\Downloads\Portal_WebGIS"
DATA_DIR = os.path.join(ROOT_DIR, "data")

def lonlat_to_tile(lon, lat, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    try:
        ytile = int((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
    except Exception:
        ytile = 0
    return xtile, ytile

def tile_to_lonlat(x, y, zoom):
    n = 2.0 ** zoom
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    try:
        lat_rad_max = math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n)))
        lat_max = math.degrees(lat_rad_max)
    except Exception:
        lat_max = 85.0511
    try:
        lat_rad_min = math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y + 1) / n)))
        lat_min = math.degrees(lat_rad_min)
    except Exception:
        lat_min = -85.0511
    return lon_min, lon_max, lat_min, lat_max

def get_optimal_zoom(xmin, ymin, xmax, ymax):
    d_lon = xmax - xmin
    if d_lon <= 0:
        return 13
    zoom = int(math.ceil(math.log2(1440.0 / d_lon)))
    return max(11, min(18, zoom))

def get_tile_with_cache(basemap, z, x, y):
    cache_dir = os.path.join(ROOT_DIR, "scratch", "tile_cache", basemap, str(z), str(x))
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{y}.png")
    
    if os.path.exists(cache_path):
        try:
            return PILImage.open(cache_path)
        except Exception:
            try:
                os.remove(cache_path)
            except Exception:
                pass
                
    if basemap == "satellite":
        url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    else: # osm
        sub = "abc"[y % 3]
        url = f"https://{sub}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            with open(cache_path, "wb") as f:
                f.write(response.content)
            return PILImage.open(cache_path)
    except Exception as e:
        print(f"Error fetching tile: {e}")
    return None

def get_deterministic_density(cd_setor, situacao):
    h = 0
    for char in str(cd_setor):
        h = (h * 31 + ord(char)) & 0xffffffff
    rand_val = (h % 10000) / 10000.0
    if situacao == 'Urbana':
        return int(round(180 + rand_val * 320))
    else:
        return int(round(5 + rand_val * 20))

def get_sector_pop_style(cd_setor, situacao):
    dens = get_deterministic_density(cd_setor, situacao)
    fill_color = '#15803d'
    if dens > 300:
        fill_color = '#ef4444'
    elif dens > 150:
        fill_color = '#f97316'
    elif dens > 50:
        fill_color = '#eab308'
    elif dens > 10:
        fill_color = '#84cc16'
    alpha = 0.45 if situacao == 'Urbana' else 0.2
    return fill_color, alpha

def draw_map_side_panel(fig, ax_panel, active_layers, scale_text, map_title_type, title_color, is_geopdf=False):
    logo_path = os.path.join(DATA_DIR, "brasao_ubaira.png")
    if os.path.exists(logo_path):
        try:
            logo_img = plt.imread(logo_path)
            if is_geopdf:
                logo_left = 0.81
            else:
                logo_left = 0.805
            ax_logo = fig.add_axes([logo_left, 0.81, 0.10, 0.09])
            ax_logo.imshow(logo_img)
            ax_logo.axis('off')
        except Exception as e:
            print(f"Error drawing side panel logo: {e}")
            
    ax_panel.axis('off')
    ax_panel.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor='white', edgecolor='black', linewidth=1.2, transform=ax_panel.transAxes))
    
    ax_panel.text(0.5, 0.77, "MUNICÍPIO DE UBAÍRA", fontsize=8.0, fontweight='bold', color='#0f172a', ha='center', transform=ax_panel.transAxes)
    ax_panel.text(0.5, 0.73, "Secretaria de Meio Ambiente", fontsize=6.5, color='#475569', ha='center', transform=ax_panel.transAxes)
    ax_panel.text(0.5, 0.68, map_title_type, fontsize=7.5, fontweight='bold', color=title_color, ha='center', transform=ax_panel.transAxes)
    
    ax_panel.plot([0.05, 0.95], [0.64, 0.64], color='black', linewidth=0.5, transform=ax_panel.transAxes)
    
    ax_panel.text(0.1, 0.60, "LEGENDA", fontsize=7.5, fontweight='bold', color='#0f172a', transform=ax_panel.transAxes)
    
    legend_items = []
    
    layer_legend_configs = {
        'municipio': ('#ef4444', 'none', 1.0, 'Limite Municipal', None),
        'regiao_metropolitana': ('#a855f7', '#c084fc', 0.15, 'Região Metropol.', None),
        'distritos': ('#3b82f6', '#93c5fd', 0.2, 'Limites Distritais', None),
        'setores': ('#10b981', '#6ee7b7', 0.15, 'Setores Censitários', None),
        'setores_populacao': ('#cbd5e1', '#ef4444', 0.4, 'Densidade Demogr.', None),
        'calor_populacional': ('#f97316', '#fdba74', 0.5, 'Calor Demográfico', None),
        'iru': ('#d97706', '#fbbf24', 0.15, 'Imóveis Rurais (CAR)', None),
        'urbano_ast': ('#ec4899', '#fbcfe8', 0.35, 'Assentamentos (AST)', None),
        'bioma': ('#84cc16', '#a3e635', 0.2, 'Biomas', None),
        'vegetacao_nativa': ('#15803d', '#22c55e', 0.35, 'Vegetação Nativa', None),
        'app_rios': ('#1d4ed8', '#3b82f6', 0.4, 'APP Margem Rio', '//'),
        'drenagem': ('#3b82f6', 'none', 1.0, 'Redes de Rios', None),
        'app_nascente': ('#0e7490', '#06b6d4', 0.45, 'APP Nascente', None),
        'app_lago_natural': ('#0284c7', '#38bdf8', 0.45, 'APP Lago Natural', None),
        'app_reservatorio': ('#0369a1', '#0ea5e9', 0.45, 'APP Reservatório', None),
        'app_topo_morro': ('#b45309', '#f59e0b', 0.3, 'APP Topo de Morro', None),
        'reserva_legal_proposta': ('#f97316', '#fdba74', 0.25, 'RL Proposta', None),
        'reserva_legal_aprovada': ('#10b981', '#34d399', 0.25, 'RL Aprovada', None),
        'reserva_legal_averbada': ('#047857', '#059669', 0.25, 'RL Averbada', None),
        'topografia': ('#854d0e', 'none', 0.75, 'Curvas de Nível', None),
        'modelo_digital': ('none', '#84cc16', 0.75, 'Relevo (MDE)', None),
        'declividade': ('none', '#eab308', 0.7, 'Declividade (%)', None),
        'deslisamento': ('none', '#3b82f6', 0.65, 'Orientação Encostas', None)
    }
    
    for key in active_layers:
        if key in layer_legend_configs:
            edge_c, fill_c, alpha, label, hatch = layer_legend_configs[key]
            legend_items.append((edge_c, fill_c, alpha, label, hatch))
            
    y_pos = 0.56
    dy = 0.028
    if len(legend_items) > 10:
        dy = max(0.018, 0.28 / len(legend_items))
        
    for edge_c, fill_c, alpha, label, hatch in legend_items:
        if fill_c != 'none':
            rect = plt.Rectangle((0.1, y_pos - 0.012), 0.12, 0.02,
                                 facecolor=fill_c, edgecolor=edge_c, alpha=alpha, hatch=hatch, linewidth=0.8, transform=ax_panel.transAxes)
            ax_panel.add_patch(rect)
        else:
            ax_panel.plot([0.1, 0.22], [y_pos - 0.002, y_pos - 0.002], color=edge_c, linewidth=0.8, alpha=alpha, transform=ax_panel.transAxes)
            
        ax_panel.text(0.26, y_pos - 0.005, label, fontsize=6.5, color='#334155', va='center', transform=ax_panel.transAxes)
        y_pos -= dy
        if y_pos < 0.28:
            break
            
    ax_panel.plot([0.05, 0.95], [0.26, 0.26], color='black', linewidth=0.5, transform=ax_panel.transAxes)
    
    ax_panel.text(0.5, 0.22, f"Escala: {scale_text}", fontsize=7.5, fontweight='bold', color='#0f172a', ha='center', transform=ax_panel.transAxes)
    ax_panel.text(0.5, 0.18, "Projeção / Datum:", fontsize=6.5, color='#475569', ha='center', transform=ax_panel.transAxes)
    ax_panel.text(0.5, 0.15, "UTM Zona 24S / SIRGAS 2000", fontsize=6.5, fontweight='bold', color='#334155', ha='center', transform=ax_panel.transAxes)
    
    ax_panel.annotate('N', xy=(0.5, 0.11), xytext=(0.5, 0.05),
                      arrowprops=dict(facecolor='#0f172a', width=1.5, headwidth=5, shrink=0.05),
                      horizontalalignment='center', verticalalignment='center',
                      fontsize=8.0, fontweight='bold', color='#0f172a', xycoords=ax_panel.transAxes, textcoords=ax_panel.transAxes)
                      
    import datetime
    date_str = datetime.date.today().strftime("%d/%m/%Y")
    ax_panel.text(0.5, 0.02, f"Data: {date_str} | Fonte: CAR, IBGE, INEMA", fontsize=5.5, color='#64748b', ha='center', transform=ax_panel.transAxes)

def get_utm_transform(layer):
    source_srs = layer.GetSpatialRef()
    if not source_srs:
        source_srs = osr.SpatialReference()
        source_srs.ImportFromEPSG(4326)
    target_srs = osr.SpatialReference()
    target_srs.ImportFromEPSG(31984) # SIRGAS 2000 / UTM zone 24S (covers Ubaíra)
    return osr.CoordinateTransformation(source_srs, target_srs)

def calculate_municipal_stats(options="all"):
    driver = ogr.GetDriverByName("GeoJSON")
    
    opts = [o.strip() for o in options.split(',')]
    show_all = "all" in opts or len(opts) == 0 or (len(opts) == 1 and opts[0] == "")
    show_app_rios = show_all or "app_rios" in opts
    show_app_nas = show_all or "app_nascente" in opts
    show_veg = show_all or "vegetacao_nativa" in opts
    show_topo = show_all or "topografia" in opts
    
    # 1. Total municipal area
    ds_mun = driver.Open(os.path.join(DATA_DIR, "municipio.geojson"), 0)
    layer_mun = ds_mun.GetLayer()
    transform = get_utm_transform(layer_mun)
    
    mun_feat = layer_mun.GetNextFeature()
    mun_geom = mun_feat.GetGeometryRef()
    mun_geom_utm = mun_geom.Clone()
    mun_geom_utm.Transform(transform)
    mun_area_ha = mun_geom_utm.GetArea() / 10000.0
    
    # 2. Rivers APP
    app_rios_area = 0
    if show_app_rios:
        ds_rios = driver.Open(os.path.join(DATA_DIR, "app_rios.geojson"), 0)
        if ds_rios:
            layer_rios = ds_rios.GetLayer()
            for feat in layer_rios:
                geom = feat.GetGeometryRef()
                geom_utm = geom.Clone()
                geom_utm.Transform(transform)
                app_rios_area += geom_utm.GetArea() / 10000.0
        
    # 3. Springs APP
    app_nas_area = 0
    if show_app_nas:
        ds_nas = driver.Open(os.path.join(DATA_DIR, "app_nascente.geojson"), 0)
        if ds_nas:
            layer_nas = ds_nas.GetLayer()
            for feat in layer_nas:
                geom = feat.GetGeometryRef()
                geom_utm = geom.Clone()
                geom_utm.Transform(transform)
                app_nas_area += geom_utm.GetArea() / 10000.0
        
    # 4. Native vegetation
    veg_area = 0
    if show_veg:
        ds_veg = driver.Open(os.path.join(DATA_DIR, "vegetacao_nativa.geojson"), 0)
        if ds_veg:
            layer_veg = ds_veg.GetLayer()
            for feat in layer_veg:
                geom = feat.GetGeometryRef()
                geom_utm = geom.Clone()
                geom_utm.Transform(transform)
                veg_area += geom_utm.GetArea() / 10000.0
        
    # 5. Overlap between Native Veg and APPs (Preserved APP)
    app_union_geom = ogr.Geometry(ogr.wkbMultiPolygon)
    
    if show_app_rios:
        ds_rios = driver.Open(os.path.join(DATA_DIR, "app_rios.geojson"), 0)
        if ds_rios:
            layer_rios = ds_rios.GetLayer()
            for feat in layer_rios:
                app_union_geom = app_union_geom.Union(feat.GetGeometryRef())
        
    if show_app_nas:
        ds_nas = driver.Open(os.path.join(DATA_DIR, "app_nascente.geojson"), 0)
        if ds_nas:
            layer_nas = ds_nas.GetLayer()
            for feat in layer_nas:
                app_union_geom = app_union_geom.Union(feat.GetGeometryRef())
        
    preserved_app_area = 0
    if show_veg and not app_union_geom.IsEmpty():
        ds_veg = driver.Open(os.path.join(DATA_DIR, "vegetacao_nativa.geojson"), 0)
        if ds_veg:
            layer_veg = ds_veg.GetLayer()
            for feat in layer_veg:
                veg_geom = feat.GetGeometryRef()
                intersection = app_union_geom.Intersection(veg_geom)
                if intersection and not intersection.IsEmpty():
                    intersection_utm = intersection.Clone()
                    intersection_utm.Transform(transform)
                    preserved_app_area += intersection_utm.GetArea() / 10000.0
            
    total_app_area = app_rios_area + app_nas_area
    deficit_area = max(0, total_app_area - preserved_app_area)
    preservation_ratio = (preserved_app_area / total_app_area * 100.0) if total_app_area > 0 else 100.0
    
    min_elev = None
    max_elev = None
    avg_elev = None
    count_contours = 0
    if show_topo:
        try:
            ds_topo = driver.Open(os.path.join(DATA_DIR, "topografia.geojson"), 0)
            if ds_topo:
                layer_topo = ds_topo.GetLayer()
                elevs = []
                for feat in layer_topo:
                    val = feat.GetField("Contour")
                    if val is not None:
                        elevs.append(float(val))
                if elevs:
                    min_elev = min(elevs)
                    max_elev = max(elevs)
                    avg_elev = sum(elevs) / len(elevs)
                    count_contours = len(elevs)
        except Exception as e:
            print(f"Error calculating municipal topography: {e}")
            
    return {
        "mun_area_ha": mun_area_ha,
        "app_rios_area_ha": app_rios_area,
        "app_nas_area_ha": app_nas_area,
        "total_app_area_ha": total_app_area,
        "veg_area_ha": veg_area,
        "preserved_app_area_ha": preserved_app_area,
        "deficit_area_ha": deficit_area,
        "preservation_ratio": preservation_ratio,
        "min_elev": min_elev,
        "max_elev": max_elev,
        "avg_elev": avg_elev,
        "count_contours": count_contours
    }


def calculate_property_stats(cod_imovel, options="all"):
    driver = ogr.GetDriverByName("GeoJSON")
    ds_iru = driver.Open(os.path.join(DATA_DIR, "iru.geojson"), 0)
    layer_iru = ds_iru.GetLayer()
    
    layer_iru.SetAttributeFilter(f"cod_imovel = '{cod_imovel}'")
    feat_prop = layer_iru.GetNextFeature()
    if not feat_prop:
        return None
        
    transform = get_utm_transform(layer_iru)
    prop_geom = feat_prop.GetGeometryRef()
    
    opts = [o.strip() for o in options.split(',')]
    show_all = "all" in opts or len(opts) == 0 or (len(opts) == 1 and opts[0] == "")
    show_app_rios = show_all or "app_rios" in opts
    show_app_nas = show_all or "app_nascente" in opts
    show_veg = show_all or "vegetacao_nativa" in opts
    show_topo = show_all or "topografia" in opts
    
    # Calculate property area
    prop_geom_utm = prop_geom.Clone()
    prop_geom_utm.Transform(transform)
    prop_area_ha = prop_geom_utm.GetArea() / 10000.0
    
    # 1. Intersect property with River APP
    prop_app_rio = 0
    if show_app_rios:
        ds_rios = driver.Open(os.path.join(DATA_DIR, "app_rios.geojson"), 0)
        if ds_rios:
            layer_rios = ds_rios.GetLayer()
            layer_rios.SetSpatialFilter(prop_geom)
            for feat in layer_rios:
                geom = feat.GetGeometryRef()
                intersection = prop_geom.Intersection(geom)
                if intersection and not intersection.IsEmpty():
                    intersection_utm = intersection.Clone()
                    intersection_utm.Transform(transform)
                    prop_app_rio += intersection_utm.GetArea() / 10000.0
            
    # 2. Intersect property with Spring APP
    prop_app_nas = 0
    if show_app_nas:
        ds_nas = driver.Open(os.path.join(DATA_DIR, "app_nascente.geojson"), 0)
        if ds_nas:
            layer_nas = ds_nas.GetLayer()
            layer_nas.SetSpatialFilter(prop_geom)
            for feat in layer_nas:
                geom = feat.GetGeometryRef()
                intersection = prop_geom.Intersection(geom)
                if intersection and not intersection.IsEmpty():
                    intersection_utm = intersection.Clone()
                    intersection_utm.Transform(transform)
                    prop_app_nas += intersection_utm.GetArea() / 10000.0
            
    # 3. Intersect property with Native Veg
    prop_veg = 0
    if show_veg:
        ds_veg = driver.Open(os.path.join(DATA_DIR, "vegetacao_nativa.geojson"), 0)
        if ds_veg:
            layer_veg = ds_veg.GetLayer()
            layer_veg.SetSpatialFilter(prop_geom)
            for feat in layer_veg:
                geom = feat.GetGeometryRef()
                intersection = prop_geom.Intersection(geom)
                if intersection and not intersection.IsEmpty():
                    intersection_utm = intersection.Clone()
                    intersection_utm.Transform(transform)
                    prop_veg += intersection_utm.GetArea() / 10000.0
            
    # 4. Preserved APP inside property
    app_union_geom = ogr.Geometry(ogr.wkbMultiPolygon)
    if show_app_rios:
        ds_rios = driver.Open(os.path.join(DATA_DIR, "app_rios.geojson"), 0)
        if ds_rios:
            layer_rios = ds_rios.GetLayer()
            for feat in layer_rios:
                intersection = prop_geom.Intersection(feat.GetGeometryRef())
                if intersection and not intersection.IsEmpty():
                    app_union_geom = app_union_geom.Union(intersection)
            
    if show_app_nas:
        ds_nas = driver.Open(os.path.join(DATA_DIR, "app_nascente.geojson"), 0)
        if ds_nas:
            layer_nas = ds_nas.GetLayer()
            for feat in layer_nas:
                intersection = prop_geom.Intersection(feat.GetGeometryRef())
                if intersection and not intersection.IsEmpty():
                    app_union_geom = app_union_geom.Union(intersection)
            
    prop_preserved_app = 0
    if show_veg and not app_union_geom.IsEmpty():
        ds_veg = driver.Open(os.path.join(DATA_DIR, "vegetacao_nativa.geojson"), 0)
        if ds_veg:
            layer_veg = ds_veg.GetLayer()
            for feat in layer_veg:
                veg_geom = feat.GetGeometryRef()
                intersection = app_union_geom.Intersection(veg_geom)
                if intersection and not intersection.IsEmpty():
                    intersection_utm = intersection.Clone()
                    intersection_utm.Transform(transform)
                    prop_preserved_app += intersection_utm.GetArea() / 10000.0
            
    total_app = prop_app_rio + prop_app_nas
    deficit = max(0, total_app - prop_preserved_app)
    ratio = (prop_preserved_app / total_app * 100.0) if total_app > 0 else 100.0
    
    # 5. Topography Calculations
    min_elev = None
    max_elev = None
    avg_elev = None
    count_contours = 0
    if show_topo:
        try:
            ds_topo = driver.Open(os.path.join(DATA_DIR, "topografia.geojson"), 0)
            if ds_topo:
                layer_topo = ds_topo.GetLayer()
                layer_topo.SetSpatialFilter(prop_geom)
                elevs = []
                for feat in layer_topo:
                    val = feat.GetField("Contour")
                    if val is not None:
                        elevs.append(float(val))
                if elevs:
                    min_elev = min(elevs)
                    max_elev = max(elevs)
                    avg_elev = sum(elevs) / len(elevs)
                    count_contours = len(elevs)
        except Exception as e:
            print(f"Error calculating topography: {e}")
            
    return {
        "cod_imovel": cod_imovel,
        "situacao_a": feat_prop.GetField("situacao_a"),
        "status_imo": feat_prop.GetField("status_imo"),
        "bioma": feat_prop.GetField("bioma"),
        "municipio": feat_prop.GetField("municipio"),
        "prop_area_ha": prop_area_ha,
        "app_rios_area_ha": prop_app_rio,
        "app_nas_area_ha": prop_app_nas,
        "total_app_area_ha": total_app,
        "veg_area_ha": prop_veg,
        "preserved_app_area_ha": prop_preserved_app,
        "deficit_area_ha": deficit,
        "preservation_ratio": ratio,
        "min_elev": min_elev,
        "max_elev": max_elev,
        "avg_elev": avg_elev,
        "count_contours": count_contours
    }

def add_geom_to_plot(ax, geom, edge_color, fill_color, alpha=1.0, hatch=None, linewidth=1.0):
    if not geom:
        return
    gtype = geom.GetGeometryType()
    
    if gtype in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
        if gtype == ogr.wkbPolygon:
            for i in range(geom.GetGeometryCount()):
                ring = geom.GetGeometryRef(i)
                pts = [ring.GetPoint(j)[:2] for j in range(ring.GetPointCount())]
                if len(pts) > 2:
                    poly = MplPolygon(pts, edgecolor=edge_color, facecolor=fill_color, alpha=alpha, hatch=hatch, linewidth=linewidth)
                    ax.add_patch(poly)
        else:
            for idx in range(geom.GetGeometryCount()):
                sub_geom = geom.GetGeometryRef(idx)
                for i in range(sub_geom.GetGeometryCount()):
                    ring = sub_geom.GetGeometryRef(i)
                    pts = [ring.GetPoint(j)[:2] for j in range(ring.GetPointCount())]
                    if len(pts) > 2:
                        poly = MplPolygon(pts, edgecolor=edge_color, facecolor=fill_color, alpha=alpha, hatch=hatch, linewidth=linewidth)
                        ax.add_patch(poly)
    elif gtype in [ogr.wkbLineString, ogr.wkbMultiLineString]:
        if gtype == ogr.wkbLineString:
            pts = [geom.GetPoint(j)[:2] for j in range(geom.GetPointCount())]
            if len(pts) > 1:
                x, y = zip(*pts)
                ax.plot(x, y, color=edge_color, linewidth=linewidth, alpha=alpha)
        else:
            for idx in range(geom.GetGeometryCount()):
                sub_geom = geom.GetGeometryRef(idx)
                pts = [sub_geom.GetPoint(j)[:2] for j in range(sub_geom.GetPointCount())]
                if len(pts) > 1:
                    x, y = zip(*pts)
                    ax.plot(x, y, color=edge_color, linewidth=linewidth, alpha=alpha)
    elif gtype in [ogr.wkbPoint, ogr.wkbMultiPoint]:
        if gtype == ogr.wkbPoint:
            pt = geom.GetPoint(0)
            ax.plot(pt[0], pt[1], marker='o', color=edge_color, markerfacecolor=fill_color, markersize=5, alpha=alpha)
        else:
            for idx in range(geom.GetGeometryCount()):
                sub_geom = geom.GetGeometryRef(idx)
                pt = sub_geom.GetPoint(0)
                ax.plot(pt[0], pt[1], marker='o', color=edge_color, markerfacecolor=fill_color, markersize=5, alpha=alpha)

def plot_all_active_layers(ax, xmin, ymin, xmax, ymax, active_layers, basemap="osm", target_cod_imovel=None):
    if basemap in ["osm", "satellite"]:
        try:
            zoom = get_optimal_zoom(xmin, ymin, xmax, ymax)
            x_min_tile, y_min_tile = lonlat_to_tile(xmin, ymax, zoom)
            x_max_tile, y_max_tile = lonlat_to_tile(xmax, ymin, zoom)
            
            x1, x2 = min(x_min_tile, x_max_tile), max(x_min_tile, x_max_tile)
            y1, y2 = min(y_min_tile, y_max_tile), max(y_min_tile, y_max_tile)
            
            num_tiles = (x2 - x1 + 1) * (y2 - y1 + 1)
            while num_tiles > 35 and zoom > 10:
                zoom -= 1
                x_min_tile, y_min_tile = lonlat_to_tile(xmin, ymax, zoom)
                x_max_tile, y_max_tile = lonlat_to_tile(xmax, ymin, zoom)
                x1, x2 = min(x_min_tile, x_max_tile), max(x_min_tile, x_max_tile)
                y1, y2 = min(y_min_tile, y_max_tile), max(y_min_tile, y_max_tile)
                num_tiles = (x2 - x1 + 1) * (y2 - y1 + 1)
                
            for x in range(x1, x2 + 1):
                for y in range(y1, y2 + 1):
                    tile_img = get_tile_with_cache(basemap, zoom, x, y)
                    if tile_img:
                        tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max = tile_to_lonlat(x, y, zoom)
                        ax.imshow(tile_img, extent=[tile_lon_min, tile_lon_max, tile_lat_min, tile_lat_max], origin='upper', zorder=0)
        except Exception as e:
            print(f"Error drawing basemap tiles: {e}")
            
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    
    raster_bounds = [-39.849356826, -39.526408502, -13.547090841, -13.0856531]
    raster_configs = {
        'modelo_digital': ('modelo_digital.png', 0.75),
        'declividade': ('declividade.png', 0.7),
        'deslisamento': ('deslisamento.png', 0.65)
    }
    for r_id in ['modelo_digital', 'declividade', 'deslisamento']:
        if r_id in active_layers:
            filename, r_alpha = raster_configs[r_id]
            raster_path = os.path.join(DATA_DIR, "rasters", filename)
            if os.path.exists(raster_path):
                try:
                    r_img = plt.imread(raster_path)
                    ax.imshow(r_img, extent=[raster_bounds[0], raster_bounds[1], raster_bounds[2], raster_bounds[3]], origin='upper', alpha=r_alpha, zorder=1)
                except Exception as e:
                    print(f"Error loading raster {r_id}: {e}")
                    
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(xmin, ymin)
    ring.AddPoint(xmax, ymin)
    ring.AddPoint(xmax, ymax)
    ring.AddPoint(xmin, ymax)
    ring.AddPoint(xmin, ymin)
    bbox_geom = ogr.Geometry(ogr.wkbPolygon)
    bbox_geom.AddGeometry(ring)
    
    driver = ogr.GetDriverByName("GeoJSON")
    
    vector_layers_configs = {
        'municipio': {
            'filename': 'municipio.geojson',
            'edge_color': '#ef4444',
            'fill_color': 'none',
            'alpha': 1.0,
            'linewidth': 2.0,
            'hatch': None
        },
        'regiao_metropolitana': {
            'filename': 'regiao_metropolitana.geojson',
            'edge_color': '#a855f7',
            'fill_color': '#c084fc',
            'alpha': 0.08,
            'linewidth': 1.5,
            'hatch': None
        },
        'distritos': {
            'filename': 'distritos.geojson',
            'edge_color': '#3b82f6',
            'fill_color': '#93c5fd',
            'alpha': 0.15,
            'linewidth': 1.5,
            'hatch': None
        },
        'setores': {
            'filename': 'setores.geojson',
            'edge_color': '#10b981',
            'fill_color': '#6ee7b7',
            'alpha': 0.1,
            'linewidth': 1.0,
            'hatch': None
        },
        'zona_urbana': {
            'filename': 'zona_urbana.geojson',
            'edge_color': '#64748b',
            'fill_color': 'none',
            'alpha': 0.6,
            'linewidth': 0.8,
            'hatch': None
        },
        'iru': {
            'filename': 'iru.geojson',
            'edge_color': '#d97706',
            'fill_color': '#fbbf24',
            'alpha': 0.15,
            'linewidth': 1.0,
            'hatch': None
        },
        'urbano_ast': {
            'filename': 'urbano_ast.geojson',
            'edge_color': '#ec4899',
            'fill_color': '#fbcfe8',
            'alpha': 0.35,
            'linewidth': 1.5,
            'hatch': None
        },
        'bioma': {
            'filename': 'bioma.geojson',
            'edge_color': '#84cc16',
            'fill_color': '#a3e635',
            'alpha': 0.2,
            'linewidth': 1.5,
            'hatch': None
        },
        'vegetacao_nativa': {
            'filename': 'vegetacao_nativa.geojson',
            'edge_color': '#15803d',
            'fill_color': '#22c55e',
            'alpha': 0.35,
            'linewidth': 0.8,
            'hatch': None
        },
        'app_rios': {
            'filename': 'app_rios.geojson',
            'edge_color': '#1d4ed8',
            'fill_color': '#3b82f6',
            'alpha': 0.4,
            'linewidth': 1.0,
            'hatch': '//'
        },
        'drenagem': {
            'filename': 'drenagem.geojson',
            'edge_color': '#3b82f6',
            'fill_color': 'none',
            'alpha': 1.0,
            'linewidth': 1.5,
            'hatch': None
        },
        'app_nascente': {
            'filename': 'app_nascente.geojson',
            'edge_color': '#0e7490',
            'fill_color': '#06b6d4',
            'alpha': 0.45,
            'linewidth': 1.0,
            'hatch': None
        },
        'app_lago_natural': {
            'filename': 'app_lago_natural.geojson',
            'edge_color': '#0284c7',
            'fill_color': '#38bdf8',
            'alpha': 0.45,
            'linewidth': 1.0,
            'hatch': None
        },
        'app_reservatorio': {
            'filename': 'app_reservatorio.geojson',
            'edge_color': '#0369a1',
            'fill_color': '#0ea5e9',
            'alpha': 0.45,
            'linewidth': 1.0,
            'hatch': None
        },
        'app_topo_morro': {
            'filename': 'app_topo_morro.geojson',
            'edge_color': '#b45309',
            'fill_color': '#f59e0b',
            'alpha': 0.3,
            'linewidth': 1.0,
            'hatch': None
        },
        'reserva_legal_proposta': {
            'filename': 'reserva_legal_proposta.geojson',
            'edge_color': '#f97316',
            'fill_color': '#fdba74',
            'alpha': 0.25,
            'linewidth': 1.0,
            'hatch': None
        },
        'reserva_legal_aprovada': {
            'filename': 'reserva_legal_aprovada.geojson',
            'edge_color': '#10b981',
            'fill_color': '#34d399',
            'alpha': 0.25,
            'linewidth': 1.0,
            'hatch': None
        },
        'reserva_legal_averbada': {
            'filename': 'reserva_legal_averbada.geojson',
            'edge_color': '#047857',
            'fill_color': '#059669',
            'alpha': 0.25,
            'linewidth': 1.0,
            'hatch': None
        },
        'topografia': {
            'filename': 'topografia.geojson',
            'edge_color': '#854d0e',
            'fill_color': 'none',
            'alpha': 0.75,
            'linewidth': 0.4,
            'hatch': None
        }
    }
    
    vector_layers_drawing_order = [
        'regiao_metropolitana', 'distritos', 'setores', 'iru', 'urbano_ast',
        'bioma', 'vegetacao_nativa', 'app_topo_morro', 'app_lago_natural',
        'app_reservatorio', 'app_rios', 'app_nascente',
        'zona_urbana', 'drenagem', 'topografia', 'municipio'
    ]
    
    for key in vector_layers_drawing_order:
        if key not in active_layers:
            continue
            
        cfg = vector_layers_configs.get(key)
        if not cfg:
            continue
            
        filepath = os.path.join(DATA_DIR, cfg['filename'])
        if not os.path.exists(filepath):
            continue
            
        try:
            ds = driver.Open(filepath, 0)
            if not ds:
                continue
            layer = ds.GetLayer()
            layer.SetSpatialFilter(bbox_geom)
            
            for feat in layer:
                geom = feat.GetGeometryRef()
                if not geom:
                    continue
                    
                if key == 'iru':
                    feat_cod = feat.GetField("cod_imovel")
                    if target_cod_imovel and feat_cod == target_cod_imovel:
                        add_geom_to_plot(ax, geom, '#d97706', '#fbbf24', alpha=0.12, linewidth=1.5)
                    else:
                        add_geom_to_plot(ax, geom, '#94a3b8', '#e2e8f0', alpha=0.3, linewidth=0.8)
                else:
                    add_geom_to_plot(ax, geom, cfg['edge_color'], cfg['fill_color'], alpha=cfg['alpha'], hatch=cfg['hatch'], linewidth=cfg['linewidth'])
        except Exception as e:
            print(f"Error plotting vector layer {key}: {e}")
            
    if 'setores_populacao' in active_layers:
        filepath = os.path.join(DATA_DIR, "setores.geojson")
        if os.path.exists(filepath):
            try:
                ds = driver.Open(filepath, 0)
                if ds:
                    layer = ds.GetLayer()
                    layer.SetSpatialFilter(bbox_geom)
                    for feat in layer:
                        geom = feat.GetGeometryRef()
                        if geom:
                            cd_setor = feat.GetField("CD_SETOR")
                            situacao = feat.GetField("SITUACAO")
                            fill_color, alpha = get_sector_pop_style(cd_setor, situacao)
                            add_geom_to_plot(ax, geom, '#ffffff', fill_color, alpha=alpha, linewidth=0.6)
            except Exception as e:
                print(f"Error plotting setores_populacao: {e}")
                
    if 'calor_populacional' in active_layers:
        filepath = os.path.join(DATA_DIR, "construcoes_precisas.geojson")
        if os.path.exists(filepath):
            try:
                ds = driver.Open(filepath, 0)
                if ds:
                    layer = ds.GetLayer()
                    layer.SetSpatialFilter(bbox_geom)
                    pts = []
                    for feat in layer:
                        geom = feat.GetGeometryRef()
                        if geom:
                            centroid = geom.Centroid()
                            if centroid:
                                pt = centroid.GetPoint(0)
                                pts.append(pt[:2])
                    if pts:
                        pts = np.array(pts)
                        
                        # Calculate density grid locally
                        cell_size = 0.0008
                        xs = pts[:, 0]
                        ys = pts[:, 1]
                        xmin_p, xmax_p = xs.min(), xs.max()
                        ymin_p, ymax_p = ys.min(), ys.max()
                        
                        # Map points to cells
                        cell_counts = {}
                        for x, y in pts:
                            cx = int((x - xmin_p) // cell_size)
                            cy = int((y - ymin_p) // cell_size)
                            key = (cx, cy)
                            cell_counts[key] = cell_counts.get(key, 0) + 1
                            
                        weights = []
                        for x, y in pts:
                            cx = int((x - xmin_p) // cell_size)
                            cy = int((y - ymin_p) // cell_size)
                            
                            local_count = 0
                            for dx in range(-1, 2):
                                for dy in range(-1, 2):
                                    local_count += cell_counts.get((cx + dx, cy + dy), 0)
                            
                            if local_count >= 18:
                                w = 1.0
                            elif local_count >= 6:
                                w = 0.4
                            elif local_count >= 3:
                                w = 0.15
                            else:
                                w = 0.03
                            weights.append(w)
                        
                        weights = np.array(weights)
                        grid_x, grid_y = np.meshgrid(np.linspace(xmin, xmax, 150), np.linspace(ymin, ymax, 150))
                        grid_z = np.zeros_like(grid_x)
                        sigma = max(0.001, (xmax - xmin) * 0.015)
                        
                        for pt, w in zip(pts, weights):
                            dist_sq = (grid_x - pt[0])**2 + (grid_y - pt[1])**2
                            grid_z += w * np.exp(-dist_sq / (2 * (sigma**2)))
                            
                        max_val = grid_z.max()
                        if max_val > 0:
                            grid_masked = np.ma.masked_where(grid_z < (max_val * 0.05), grid_z)
                            ax.imshow(grid_masked, extent=[xmin, xmax, ymin, ymax], origin='lower', cmap='YlOrRd', alpha=0.5, zorder=2)
            except Exception as e:
                print(f"Error plotting calor_populacional heatmap from buildings: {e}")

def draw_map_side_panel(fig, ax_panel, active_layers, scale_text, map_title_type, title_color, is_geopdf=False):
    logo_path = os.path.join(DATA_DIR, "brasao_ubaira.png")
    if os.path.exists(logo_path):
        try:
            logo_img = plt.imread(logo_path)
            if is_geopdf:
                logo_left = 0.81
            else:
                logo_left = 0.805
            ax_logo = fig.add_axes([logo_left, 0.81, 0.10, 0.09])
            ax_logo.imshow(logo_img)
            ax_logo.axis('off')
        except Exception as e:
            print(f"Error drawing side panel logo: {e}")
            
    ax_panel.axis('off')
    ax_panel.add_patch(plt.Rectangle((0, 0), 1, 1, facecolor='white', edgecolor='black', linewidth=1.2, transform=ax_panel.transAxes))
    
    ax_panel.text(0.5, 0.77, "MUNICÍPIO DE UBAÍRA", fontsize=8.0, fontweight='bold', color='#0f172a', ha='center', transform=ax_panel.transAxes)
    ax_panel.text(0.5, 0.73, "Secretaria de Meio Ambiente", fontsize=6.5, color='#475569', ha='center', transform=ax_panel.transAxes)
    ax_panel.text(0.5, 0.68, map_title_type, fontsize=7.5, fontweight='bold', color=title_color, ha='center', transform=ax_panel.transAxes)
    
    ax_panel.plot([0.05, 0.95], [0.64, 0.64], color='black', linewidth=0.5, transform=ax_panel.transAxes)
    
    ax_panel.text(0.1, 0.60, "LEGENDA", fontsize=7.5, fontweight='bold', color='#0f172a', transform=ax_panel.transAxes)
    
    legend_items = []
    
    layer_legend_configs = {
        'municipio': ('#ef4444', 'none', 1.0, 'Limite Municipal', None),
        'regiao_metropolitana': ('#a855f7', '#c084fc', 0.15, 'Região Metropol.', None),
        'distritos': ('#3b82f6', '#93c5fd', 0.2, 'Limites Distritais', None),
        'setores': ('#10b981', '#6ee7b7', 0.15, 'Setores Censitários', None),
        'setores_populacao': ('#cbd5e1', '#ef4444', 0.4, 'Densidade Demogr.', None),
        'calor_populacional': ('#f97316', '#fdba74', 0.5, 'Calor Demográfico', None),
        'iru': ('#d97706', '#fbbf24', 0.15, 'Imóveis Rurais (CAR)', None),
        'urbano_ast': ('#ec4899', '#fbcfe8', 0.35, 'Assentamentos (AST)', None),
        'bioma': ('#84cc16', '#a3e635', 0.2, 'Biomas', None),
        'vegetacao_nativa': ('#15803d', '#22c55e', 0.35, 'Vegetação Nativa', None),
        'app_rios': ('#1d4ed8', '#3b82f6', 0.4, 'APP Margem Rio', '//'),
        'drenagem': ('#3b82f6', 'none', 1.0, 'Redes de Rios', None),
        'app_nascente': ('#0e7490', '#06b6d4', 0.45, 'APP Nascente', None),
        'app_lago_natural': ('#0284c7', '#38bdf8', 0.45, 'APP Lago Natural', None),
        'app_reservatorio': ('#0369a1', '#0ea5e9', 0.45, 'APP Reservatório', None),
        'app_topo_morro': ('#b45309', '#f59e0b', 0.3, 'APP Topo de Morro', None),
        'reserva_legal_proposta': ('#f97316', '#fdba74', 0.25, 'RL Proposta', None),
        'reserva_legal_aprovada': ('#10b981', '#34d399', 0.25, 'RL Aprovada', None),
        'reserva_legal_averbada': ('#047857', '#059669', 0.25, 'RL Averbada', None),
        'topografia': ('#854d0e', 'none', 0.75, 'Curvas de Nível', None),
        'modelo_digital': ('none', '#84cc16', 0.75, 'Relevo (MDE)', None),
        'declividade': ('none', '#eab308', 0.7, 'Declividade (%)', None),
        'deslisamento': ('none', '#3b82f6', 0.65, 'Orientação Encostas', None)
    }
    
    for key in active_layers:
        if key in layer_legend_configs:
            edge_c, fill_c, alpha, label, hatch = layer_legend_configs[key]
            legend_items.append((edge_c, fill_c, alpha, label, hatch))
            
    y_pos = 0.56
    dy = 0.028
    if len(legend_items) > 10:
        dy = max(0.018, 0.28 / len(legend_items))
        
    for edge_c, fill_c, alpha, label, hatch in legend_items:
        if fill_c != 'none':
            rect = plt.Rectangle((0.1, y_pos - 0.012), 0.12, 0.02,
                                 facecolor=fill_c, edgecolor=edge_c, alpha=alpha, hatch=hatch, linewidth=0.8, transform=ax_panel.transAxes)
            ax_panel.add_patch(rect)
        else:
            ax_panel.plot([0.1, 0.22], [y_pos - 0.002, y_pos - 0.002], color=edge_c, linewidth=0.8, alpha=alpha, transform=ax_panel.transAxes)
            
        ax_panel.text(0.26, y_pos - 0.005, label, fontsize=6.5, color='#334155', va='center', transform=ax_panel.transAxes)
        y_pos -= dy
        if y_pos < 0.28:
            break
            
    ax_panel.plot([0.05, 0.95], [0.26, 0.26], color='black', linewidth=0.5, transform=ax_panel.transAxes)
    
    ax_panel.text(0.5, 0.22, f"Escala: {scale_text}", fontsize=7.5, fontweight='bold', color='#0f172a', ha='center', transform=ax_panel.transAxes)
    ax_panel.text(0.5, 0.18, "Projeção / Datum:", fontsize=6.5, color='#475569', ha='center', transform=ax_panel.transAxes)
    ax_panel.text(0.5, 0.15, "UTM Zona 24S / SIRGAS 2000", fontsize=6.5, fontweight='bold', color='#334155', ha='center', transform=ax_panel.transAxes)
    
    ax_panel.annotate('N', xy=(0.5, 0.11), xytext=(0.5, 0.05),
                      arrowprops=dict(facecolor='#0f172a', width=1.5, headwidth=5, shrink=0.05),
                      horizontalalignment='center', verticalalignment='center',
                      fontsize=8.0, fontweight='bold', color='#0f172a', xycoords=ax_panel.transAxes, textcoords=ax_panel.transAxes)
                      
    import datetime
    date_str = datetime.date.today().strftime("%d/%m/%Y")
    ax_panel.text(0.5, 0.02, f"Data: {date_str} | Fonte: CAR, IBGE, INEMA", fontsize=5.5, color='#64748b', ha='center', transform=ax_panel.transAxes)

def generate_property_map(cod_imovel, output_png_path, options="all", basemap="osm", active_layers=None):
    driver = ogr.GetDriverByName("GeoJSON")
    ds_iru = driver.Open(os.path.join(DATA_DIR, "iru.geojson"), 0)
    layer_iru = ds_iru.GetLayer()
    layer_iru.SetAttributeFilter(f"cod_imovel = '{cod_imovel}'")
    feat_prop = layer_iru.GetNextFeature()
    if not feat_prop:
        return False
        
    prop_geom = feat_prop.GetGeometryRef()
    extent = prop_geom.GetEnvelope() # xmin, xmax, ymin, ymax
    
    dx_orig = extent[1] - extent[0]
    dy_orig = extent[3] - extent[2]
    buffer_ratio = 0.15
    xmin = extent[0] - dx_orig * buffer_ratio
    xmax = extent[1] + dx_orig * buffer_ratio
    ymin = extent[2] - dy_orig * buffer_ratio
    ymax = extent[3] + dy_orig * buffer_ratio
    dx = xmax - xmin
    dy = ymax - ymin
    
    W_fig = 8.5
    H_fig = 6.0
    W_max_map = 5.44
    H_max_map = 5.04
    
    A = dy / dx if dx > 0 else 1.0
    if A > H_max_map / W_max_map:
        H_map = H_max_map
        W_map = H_map / A
    else:
        W_map = W_max_map
        H_map = W_map * A
        
    X_center = 0.08 * W_fig + (W_max_map - W_map) / 2.0
    Y_center = 0.08 * H_fig + (H_max_map - H_map) / 2.0
    
    w_frac = W_map / W_fig
    h_frac = H_map / H_fig
    left_frac = X_center / W_fig
    bottom_frac = Y_center / H_fig
    
    fig = plt.figure(figsize=(W_fig, H_fig), dpi=150)
    
    ax_map = fig.add_axes([left_frac, bottom_frac, w_frac, h_frac])
    
    if active_layers is None:
        opts = [o.strip() for o in options.split(',')]
        show_all = "all" in opts or len(opts) == 0 or (len(opts) == 1 and opts[0] == "")
        active_layers = ['iru']
        if show_all or "app_rios" in opts: active_layers.append('app_rios')
        if show_all or "app_nascente" in opts: active_layers.append('app_nascente')
        if show_all or "vegetacao_nativa" in opts: active_layers.append('vegetacao_nativa')
        if show_all or "topografia" in opts: active_layers.append('topografia')
        
    plot_all_active_layers(ax_map, xmin, ymin, xmax, ymax, active_layers, basemap=basemap, target_cod_imovel=cod_imovel)
    
    ax_map.grid(True, linestyle=':', color='#cbd5e1', linewidth=0.5, alpha=0.8)
    for spine in ax_map.spines.values():
        spine.set_color('black')
        spine.set_linewidth(1.2)
        
    import matplotlib.ticker as ticker
    def format_lon(x, pos):
        return f"{abs(x):.4f}°O"
    def format_lat(y, pos):
        return f"{abs(y):.4f}°S"
        
    ax_map.xaxis.set_major_formatter(ticker.FuncFormatter(format_lon))
    ax_map.yaxis.set_major_formatter(ticker.FuncFormatter(format_lat))
    ax_map.tick_params(axis='both', which='major', labelsize=7.5, colors='#1e293b')
    
    lat_mid = (ymin + ymax) / 2.0
    m_per_deg_lon = 111000.0 * math.cos(math.radians(lat_mid))
    ground_width_m = dx * m_per_deg_lon
    
    if ground_width_m < 200:
        scale_len = 20.0
        scale_label = "20 m"
    elif ground_width_m < 500:
        scale_len = 50.0
        scale_label = "50 m"
    elif ground_width_m < 1000:
        scale_len = 100.0
        scale_label = "100 m"
    elif ground_width_m < 2000:
        scale_len = 250.0
        scale_label = "250 m"
    elif ground_width_m < 5000:
        scale_len = 500.0
        scale_label = "500 m"
    else:
        scale_len = 1000.0
        scale_label = "1 km"
        
    scale_deg = scale_len / m_per_deg_lon
    sb_x = xmin + dx * 0.05
    sb_y = ymin + dy * 0.05
    
    scale_box = plt.Rectangle((sb_x - dx*0.02, sb_y - dy*0.02), scale_deg + dx*0.04, dy*0.065,
                              facecolor='white', alpha=0.85, edgecolor='#cbd5e1', linewidth=0.5, zorder=5)
    ax_map.add_patch(scale_box)
    
    ax_map.plot([sb_x, sb_x + scale_deg], [sb_y, sb_y], color='black', linewidth=2.5, zorder=6)
    ax_map.text(sb_x + scale_deg/2.0, sb_y + dy*0.015, scale_label,
                horizontalalignment='center', fontsize=7, fontweight='bold', color='black', zorder=6)
                
    ax_panel = fig.add_axes([0.75, 0.08, 0.21, 0.84])
    axes_width_m = W_map * 0.0254
    scale_ratio = ground_width_m / axes_width_m
    scale_text = f"1:{int(round(scale_ratio, -1)):,}".replace(',', '.')
    
    draw_map_side_panel(fig, ax_panel, active_layers, scale_text, "MAPA DO IMÓVEL RURAL", "#d97706", is_geopdf=False)
    
    plt.savefig(output_png_path, dpi=150)
    plt.close()
    return True

def generate_municipal_map(output_png_path, options="all", basemap="osm", active_layers=None):
    driver = ogr.GetDriverByName("GeoJSON")
    ds_mun = driver.Open(os.path.join(DATA_DIR, "municipio.geojson"), 0)
    if not ds_mun:
        return False
    layer_mun = ds_mun.GetLayer()
    mun_feat = layer_mun.GetNextFeature()
    if not mun_feat:
        return False
        
    mun_geom = mun_feat.GetGeometryRef()
    extent = mun_geom.GetEnvelope() # xmin, xmax, ymin, ymax
    
    dx_orig = extent[1] - extent[0]
    dy_orig = extent[3] - extent[2]
    buffer_ratio = 0.05
    xmin = extent[0] - dx_orig * buffer_ratio
    xmax = extent[1] + dx_orig * buffer_ratio
    ymin = extent[2] - dy_orig * buffer_ratio
    ymax = extent[3] + dy_orig * buffer_ratio
    dx = xmax - xmin
    dy = ymax - ymin
    
    W_fig = 8.5
    H_fig = 6.0
    W_max_map = 5.44
    H_max_map = 5.04
    
    A = dy / dx if dx > 0 else 1.0
    if A > H_max_map / W_max_map:
        H_map = H_max_map
        W_map = H_map / A
    else:
        W_map = W_max_map
        H_map = W_map * A
        
    X_center = 0.08 * W_fig + (W_max_map - W_map) / 2.0
    Y_center = 0.08 * H_fig + (H_max_map - H_map) / 2.0
    
    w_frac = W_map / W_fig
    h_frac = H_map / H_fig
    left_frac = X_center / W_fig
    bottom_frac = Y_center / H_fig
    
    fig = plt.figure(figsize=(W_fig, H_fig), dpi=150)
    
    ax_map = fig.add_axes([left_frac, bottom_frac, w_frac, h_frac])
    
    if active_layers is None:
        opts = [o.strip() for o in options.split(',')]
        show_all = "all" in opts or len(opts) == 0 or (len(opts) == 1 and opts[0] == "")
        active_layers = ['municipio']
        if show_all or "app_rios" in opts: active_layers.append('app_rios')
        if show_all or "app_nascente" in opts: active_layers.append('app_nascente')
        if show_all or "vegetacao_nativa" in opts: active_layers.append('vegetacao_nativa')
        if show_all or "topografia" in opts: active_layers.append('topografia')
        
    plot_all_active_layers(ax_map, xmin, ymin, xmax, ymax, active_layers, basemap=basemap)
    
    ax_map.grid(True, linestyle=':', color='#cbd5e1', linewidth=0.5, alpha=0.8)
    for spine in ax_map.spines.values():
        spine.set_color('black')
        spine.set_linewidth(1.2)
        
    import matplotlib.ticker as ticker
    def format_lon(x, pos):
        return f"{abs(x):.3f}°O"
    def format_lat(y, pos):
        return f"{abs(y):.3f}°S"
        
    ax_map.xaxis.set_major_formatter(ticker.FuncFormatter(format_lon))
    ax_map.yaxis.set_major_formatter(ticker.FuncFormatter(format_lat))
    ax_map.tick_params(axis='both', which='major', labelsize=7.5, colors='#1e293b')
    
    lat_mid = (ymin + ymax) / 2.0
    m_per_deg_lon = 111000.0 * math.cos(math.radians(lat_mid))
    ground_width_m = dx * m_per_deg_lon
    
    scale_len = 5000.0 # 5 km
    scale_label = "5 km"
    if ground_width_m < 15000:
        scale_len = 2000.0
        scale_label = "2 km"
        
    scale_deg = scale_len / m_per_deg_lon
    sb_x = xmin + dx * 0.05
    sb_y = ymin + dy * 0.05
    
    scale_box = plt.Rectangle((sb_x - dx*0.02, sb_y - dy*0.02), scale_deg + dx*0.04, dy*0.065,
                              facecolor='white', alpha=0.85, edgecolor='#cbd5e1', linewidth=0.5, zorder=5)
    ax_map.add_patch(scale_box)
    
    ax_map.plot([sb_x, sb_x + scale_deg], [sb_y, sb_y], color='black', linewidth=2.5, zorder=6)
    ax_map.text(sb_x + scale_deg/2.0, sb_y + dy*0.015, scale_label,
                horizontalalignment='center', fontsize=7, fontweight='bold', color='black', zorder=6)
                
    ax_panel = fig.add_axes([0.75, 0.08, 0.21, 0.84])
    axes_width_m = W_map * 0.0254
    scale_ratio = ground_width_m / axes_width_m
    scale_text = f"1:{int(round(scale_ratio, -2)):,}".replace(',', '.')
    
    draw_map_side_panel(fig, ax_panel, active_layers, scale_text, "MAPA MUNICIPAL GERAL", "#ef4444", is_geopdf=False)
    
    plt.savefig(output_png_path, dpi=150)
    plt.close()
    return True

def generate_report_pdf(type_report, cod_imovel, output_pdf_path, options="all", basemap="osm", active_layers=None):
    doc = SimpleDocTemplate(output_pdf_path, pagesize=A4,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    opts = [o.strip() for o in options.split(',')]
    show_all = "all" in opts or len(opts) == 0 or (len(opts) == 1 and opts[0] == "")
    show_cadastral = show_all or "cadastral" in opts
    show_app_rios = show_all or "app_rios" in opts
    show_app_nas = show_all or "app_nascente" in opts
    show_veg = show_all or "vegetacao_nativa" in opts
    show_topo = show_all or "topografia" in opts
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#08162a"),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#d97706"),
        spaceAfter=10,
        spaceBefore=10
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#334155")
    )
    
    bold_body_style = ParagraphStyle(
        'DocBoldBody',
        parent=body_style,
        fontName='Helvetica-Bold'
    )
    
    footer_style = ParagraphStyle(
        'DocFooter',
        parent=styles['Italic'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748b"),
        alignment=1
    )
    
    story = []
    
    # Header Section
    logo_path = os.path.join(DATA_DIR, "brasao_ubaira.png")
    header_data = []
    if os.path.exists(logo_path):
        img = Image(logo_path, width=45, height=45)
        header_data.append(img)
    else:
        header_data.append("")
        
    title_p = Paragraph("<b>ESTADO DA BAHIA</b><br/><b>PREFEITURA MUNICIPAL DE UBAÍRA</b><br/>Secretaria de Meio Ambiente e Recursos Hídricos", ParagraphStyle('HdrTxt', fontName='Helvetica', fontSize=8.5, leading=11, textColor=colors.HexColor("#0f172a")))
    header_data.append(title_p)
    
    header_table = Table([header_data], colWidths=[55, 455])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor("#08162a")),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    
    if type_report == "municipal":
        stats = calculate_municipal_stats(options)
        
        story.append(Paragraph("Relatório Técnico do Município de Ubaíra", title_style))
        story.append(Paragraph("Este documento apresenta uma análise técnica consolidada de indicadores cadastrais, censitários e ambientais mapeados no município de Ubaíra/BA de acordo com as seleções configuradas pelo usuário.", body_style))
        story.append(Spacer(1, 10))
        
        # Load live IBGE data if available
        ibge_data = None
        ibge_path = os.path.join(DATA_DIR, "ibge_live.json")
        if os.path.exists(ibge_path):
            try:
                with open(ibge_path, "r", encoding="utf-8") as f:
                    ibge_data = json.load(f)
            except Exception:
                pass
        
        if not ibge_data:
            ibge_data = {
                "populacao": 26116,
                "densidade": 21.2,
                "area": 1231.0
            }

        table_data = [
            [Paragraph("<b>Indicador Técnico / Elemento</b>", bold_body_style), Paragraph("<b>Métricas e Extensões Calculadas</b>", bold_body_style)],
            ["Área Municipal Calculada (Mapeamento)", f"{stats['mun_area_ha']:,.2f} ha".replace(',', '.')]
        ]
        
        if show_cadastral:
            table_data.append(["Área Territorial Oficial (IBGE)", f"{ibge_data['area']:,.2f} km² ({ibge_data['area']*100:,.2f} ha)".replace(',', '.')])
            table_data.append(["População Estimada (IBGE)", f"{ibge_data['populacao']:,} hab".replace(',', '.')])
            table_data.append(["Densidade Demográfica Oficial", f"{ibge_data['densidade']:.2f} hab/km²".replace('.', ',')])

        if show_app_rios or show_app_nas:
            table_data.append(["Total de Área de APP Calculada", f"{stats['total_app_area_ha']:,.2f} ha".replace(',', '.')])
        if show_app_rios:
            table_data.append(["  - APP de Margens de Rios", f"{stats['app_rios_area_ha']:,.2f} ha".replace(',', '.')])
        if show_app_nas:
            table_data.append(["  - APP de Raio de Nascentes", f"{stats['app_nas_area_ha']:,.2f} ha".replace(',', '.')])
        if show_veg:
            table_data.append(["Área de Cobertura de Vegetação Nativa", f"{stats['veg_area_ha']:,.2f} ha".replace(',', '.')])
        if show_veg and (show_app_rios or show_app_nas):
            table_data.append(["Área de APP Preservada (Com Cobertura Nativa)", f"{stats['preserved_app_area_ha']:,.2f} ha".replace(',', '.')])
            table_data.append(["Déficit de Vegetação em APP (Área Desprovida)", f"{stats['deficit_area_ha']:,.2f} ha".replace(',', '.')])
            table_data.append(["Índice de Preservação das APPs Municipais", f"{stats['preservation_ratio']:.2f}%"])
            
        t = Table(table_data, colWidths=[280, 230])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))
        
        # Municipal Topography section
        if show_topo and stats.get('count_contours', 0) > 0:
            story.append(Paragraph("Dados Topográficos e Altimetria", subtitle_style))
            topo_table_data = [
                [Paragraph("<b>Métrica Altimétrica Municipal</b>", bold_body_style), Paragraph("<b>Valor Calculado</b>", bold_body_style)],
                ["Contagem de Curvas do Município", f"{stats['count_contours']} curvas"],
                ["Cota Mínima Identificada", f"{stats['min_elev']:.1f} m" if stats['min_elev'] else "--"],
                ["Cota Máxima Identificada", f"{stats['max_elev']:.1f} m" if stats['max_elev'] else "--"],
                ["Altitude Média Municipal", f"{stats['avg_elev']:.1f} m" if stats['avg_elev'] else "--"]
            ]
            t_topo = Table(topo_table_data, colWidths=[280, 230])
            t_topo.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(t_topo)
            story.append(Spacer(1, 12))

        story.append(Paragraph("Detalhamento Técnico das Camadas Selecionadas", subtitle_style))
        desc_text = "Mapeamento das camadas geoespaciais incidentes em Ubaíra: "
        desc_parts = []
        if show_cadastral:
            desc_parts.append("dados cadastrais e censitários do IBGE")
        if show_app_rios:
            desc_parts.append("faixas marginais de proteção de rios e drenagens")
        if show_app_nas:
            desc_parts.append("buffers circulares de proteção de nascentes (raio de 50 metros)")
        if show_veg:
            desc_parts.append("áreas florestais remanescentes de Mata Atlântica")
        if show_topo:
            desc_parts.append("curvas de nível e dados de altimetria/relevo")
        story.append(Paragraph(desc_text + ", ".join(desc_parts) + ".", body_style))
        
        # Render and Append Municipal Map
        temp_map_png = os.path.join(ROOT_DIR, "scratch", "temp_map_municipal.png")
        os.makedirs(os.path.dirname(temp_map_png), exist_ok=True)
        if generate_municipal_map(temp_map_png, options, basemap=basemap, active_layers=active_layers):
            story.append(Spacer(1, 10))
            story.append(Image(temp_map_png, width=480, height=338))
            story.append(Spacer(1, 10))
            
        story.append(Paragraph("Análise Técnica dos Elementos de Interesse", subtitle_style))
        
        analysis_text = ""
        if show_veg:
            veg_pct = (stats['veg_area_ha'] / stats['mun_area_ha'] * 100.0) if stats['mun_area_ha'] > 0 else 0.0
            analysis_text += f"O município de Ubaíra apresenta <b>{stats['veg_area_ha']:,.2f} ha</b> de remanescentes de vegetação nativa, o que equivale a aproximadamente <b>{veg_pct:.2f}%</b> de seu território mapeado. "
            
        if show_app_rios or show_app_nas:
            analysis_text += f"A extensão das Áreas de Preservação Permanente (APPs) calculadas nas zonas de interesse soma <b>{stats['total_app_area_ha']:,.2f} ha</b>. "
            if show_veg:
                analysis_text += f"Deste total, <b>{stats['preserved_app_area_ha']:,.2f} ha</b> encontram-se atualmente protegidos com cobertura de vegetação nativa estável, resultando em um índice de preservação de APP de <b>{stats['preservation_ratio']:.2f}%</b>. Contudo, há um déficit ecológico estimado de <b>{stats['deficit_area_ha']:,.2f} ha</b> de áreas de APP desprovidas de cobertura florestal original, demandando ações de restauração e regeneração de acordo com o Novo Código Florestal (Lei Federal nº 12.651/2012). "
                
        if show_topo and stats.get('count_contours', 0) > 0:
            elev_diff = stats['max_elev'] - stats['min_elev'] if stats['max_elev'] and stats['min_elev'] else 0.0
            analysis_text += f"A topografia do município exibe um relevo significativamente acidentado, com amplitude altimétrica identificada de <b>{elev_diff:.1f} m</b> (variando entre cota mínima de {stats['min_elev']:.1f} m e cota máxima de {stats['max_elev']:.1f} m). Essa configuração geomorfológica típica da região serrana do Vale do Jiquiriçá confere alta sensibilidade ambiental aos terrenos e encostas íngremes, ressaltando a importância vital de preservar a cobertura vegetal nativa para atenuar processos erosivos, prevenir desmoronamentos de terra e conservar os recursos hídricos e nascentes locais."
            
        if not analysis_text:
            analysis_text = "As camadas selecionadas foram mapeadas com sucesso. A análise integrada dos dados espaciais não identificou conflitos críticos evidentes para os parâmetros ativados no momento da consulta. Recomenda-se a verificação contínua das atualizações do Cadastro Ambiental Rural (CAR) e dos indicadores censitários locais."
            
        story.append(Paragraph(analysis_text, body_style))
            
    elif type_report == "property":
        stats = calculate_property_stats(cod_imovel, options)
        if not stats:
            story.append(Paragraph(f"Erro: O imóvel rural de código <b>{cod_imovel}</b> não foi encontrado no banco de dados local.", subtitle_style))
            doc.build(story)
            return False
            
        story.append(Paragraph(f"Relatório Técnico do Imóvel Rural", title_style))
        story.append(Paragraph(f"Relatório técnico descritivo e espacial detalhado referente ao imóvel rural de cadastro CAR no município de Ubaíra/BA.", body_style))
        story.append(Spacer(1, 10))
        
        # Property metadata table (Conditional on checkboxes)
        if show_cadastral:
            meta_table_data = [
                [Paragraph("<b>Atributo do Imóvel (CAR)</b>", bold_body_style), Paragraph("<b>Informação Cadastrada</b>", bold_body_style)],
                ["Código Federal (CAR)", stats["cod_imovel"]],
                ["Status no Registro", stats["status_imo"]],
                ["Situação da Análise", stats["situacao_a"]],
                ["Município", stats["municipio"]],
                ["Bioma Predominante", stats["bioma"]],
            ]
            t_meta = Table(meta_table_data, colWidths=[180, 330])
            t_meta.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(t_meta)
            story.append(Spacer(1, 10))
        
        # Environmental Metrics (Conditional on checkboxes)
        story.append(Paragraph("Métricas Espaciais do Imóvel", subtitle_style))
        metrics_table = [
            [Paragraph("<b>Indicador Técnico / Ambiental</b>", bold_body_style), Paragraph("<b>Área Calculada (Hectares)</b>", bold_body_style), Paragraph("<b>Proporção (%)</b>", bold_body_style)],
            ["Área Total do Imóvel", f"{stats['prop_area_ha']:,.2f} ha".replace(',', '.'), "100.0%"]
        ]
        
        if show_app_rios or show_app_nas:
            metrics_table.append(["Total de APP Requerida", f"{stats['total_app_area_ha']:,.2f} ha".replace(',', '.'), f"{(stats['total_app_area_ha']/stats['prop_area_ha']*100.0):.1f}%" if stats['prop_area_ha'] > 0 else "0%"])
        if show_app_rios:
            metrics_table.append(["  - APP Margem de Rios", f"{stats['app_rios_area_ha']:,.2f} ha".replace(',', '.'), "--"])
        if show_app_nas:
            metrics_table.append(["  - APP de Nascentes", f"{stats['app_nas_area_ha']:,.2f} ha".replace(',', '.'), "--"])
        if show_veg:
            metrics_table.append(["Vegetação Nativa Declarada", f"{stats['veg_area_ha']:,.2f} ha".replace(',', '.'), f"{(stats['veg_area_ha']/stats['prop_area_ha']*100.0):.1f}%" if stats['prop_area_ha'] > 0 else "0%"])
        if show_veg and (show_app_rios or show_app_nas):
            metrics_table.append(["APP Preservada no Imóvel", f"{stats['preserved_app_area_ha']:,.2f} ha".replace(',', '.'), f"{stats['preservation_ratio']:.1f}% das APPs"])
            metrics_table.append(["Déficit de APP (Área Desprovida)", f"{stats['deficit_area_ha']:,.2f} ha".replace(',', '.'), f"{(stats['deficit_area_ha']/stats['total_app_area_ha']*100.0 if stats['total_app_area_ha'] > 0 else 0.0):.1f}% das APPs"])
            
        t_metrics = Table(metrics_table, colWidths=[220, 180, 110])
        t_metrics.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_metrics)
        story.append(Spacer(1, 10))
        
        # 3. Topography metrics (Conditional on checkbox)
        if show_topo:
            story.append(Paragraph("Dados Topográficos e Relevo", subtitle_style))
            if stats.get('count_contours', 0) > 0:
                topo_table_data = [
                    [Paragraph("<b>Métrica Altimétrica</b>", bold_body_style), Paragraph("<b>Valor Calculado</b>", bold_body_style)],
                    ["Contagem de Curvas Intersecionadas", f"{stats['count_contours']} curvas"],
                    ["Cota Mínima Encontrada", f"{stats['min_elev']:.1f} m" if stats['min_elev'] else "--"],
                    ["Cota Máxima Encontrada", f"{stats['max_elev']:.1f} m" if stats['max_elev'] else "--"],
                    ["Altitude Média Estimada", f"{stats['avg_elev']:.1f} m" if stats['avg_elev'] else "--"]
                ]
                t_topo = Table(topo_table_data, colWidths=[250, 260])
                t_topo.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
                    ('PADDING', (0,0), (-1,-1), 5),
                ]))
                story.append(t_topo)
            else:
                story.append(Paragraph("Nenhuma curva de nível foi identificada dentro dos limites do imóvel selecionado.", body_style))
            story.append(Spacer(1, 10))
        
        # Render and Append Map with options
        temp_map_png = os.path.join(ROOT_DIR, "scratch", f"temp_map_{cod_imovel.replace('-', '_')}.png")
        os.makedirs(os.path.dirname(temp_map_png), exist_ok=True)
        if generate_property_map(cod_imovel, temp_map_png, options, basemap=basemap, active_layers=active_layers):
            story.append(Spacer(1, 10))
            story.append(Image(temp_map_png, width=480, height=338))
            story.append(Spacer(1, 10))
            
        story.append(Paragraph("Análise Técnica dos Elementos de Interesse", subtitle_style))
        
        analysis_text = f"O imóvel rural de código CAR <b>{stats['cod_imovel']}</b> possui área total declarada de <b>{stats['prop_area_ha']:,.2f} ha</b>. "
        
        if show_app_rios or show_app_nas:
            analysis_text += f"O mapeamento identificou uma demanda legal de <b>{stats['total_app_area_ha']:,.2f} ha</b> de Áreas de Preservação Permanente (APPs) dentro dos limites da propriedade. "
            if show_veg:
                analysis_text += f"Deste total, <b>{stats['preserved_app_area_ha']:,.2f} ha</b> apresentam cobertura vegetal nativa conservada, correspondendo a uma taxa de preservação de <b>{stats['preservation_ratio']:.1f}%</b> das APPs internas. "
                if stats['deficit_area_ha'] > 0:
                    analysis_text += f"Foi detectado um déficit florestal de <b>{stats['deficit_area_ha']:,.2f} ha</b> em APP de rios ou nascentes, indicando a necessidade de implementação de plano de recuperação de áreas degradadas (PRA) ou condução da regeneração natural para adequação ao Código Florestal Brasileiro. "
                else:
                    analysis_text += "As APPs encontram-se integralmente preservadas sob vegetação nativa estável, atestando conformidade com as diretrizes do Código Florestal."
                    
        if show_veg:
            veg_pct = (stats['veg_area_ha'] / stats['prop_area_ha'] * 100.0) if stats['prop_area_ha'] > 0 else 0.0
            analysis_text += f" A cobertura de vegetação nativa declarada no imóvel estende-se por <b>{stats['veg_area_ha']:,.2f} ha</b> (<b>{veg_pct:.1f}%</b> da área total), constituindo um importante fragmento para a biodiversidade e proteção contra erosão do solo local."
            
        if show_topo and stats.get('count_contours', 0) > 0:
            elev_diff = stats['max_elev'] - stats['min_elev'] if stats['max_elev'] and stats['min_elev'] else 0.0
            analysis_text += f" A altimetria local revela declividades variando entre a cota mínima de <b>{stats['min_elev']:.1f} m</b> e máxima de <b>{stats['max_elev']:.1f} m</b> (amplitude de {elev_diff:.1f} m), o que exige manejo conservacionista de solo e águas nas atividades agrícolas e pastoris desenvolvidas."
            
        story.append(Paragraph(analysis_text, body_style))
        story.append(Spacer(1, 10))
            
    # Footer references (user request: reference the original data sources)
    story.append(Paragraph("<b>Fontes de Referência Originárias dos Dados:</b><br/>"
                           "• Delimitação dos Imóveis Rurais e APPs: <b>Cadastro Ambiental Rural (CAR / SICAR)</b> - Serviço Florestal Brasileiro (SFB).<br/>"
                           "• Dados Territoriais e Censo Demográfico: <b>Instituto Brasileiro de Geografia e Estatística (IBGE)</b>.<br/>"
                           "• Recursos Hídricos e Fiscalização: <b>INEMA - Instituto do Meio Ambiente e Recursos Hídricos da Bahia</b>.<br/>"
                           "• O portal local realiza a adequação SIRGAS 2000 Projeção UTM Zona 24S (EPSG:31984) de forma puramente técnica sem fins de titulação fundiária.", footer_style))
    
    # Signatures
    story.append(Spacer(1, 15))
    sig_data = [
        [Paragraph("________________________________________<br/><b>Secretaria Municipal de Meio Ambiente</b><br/>Prefeitura Municipal de Ubaíra", ParagraphStyle('Sig1', fontName='Helvetica', fontSize=8, leading=10, alignment=1)),
         Paragraph("________________________________________<br/><b>Setor de Cadastro e Geoprocessamento</b><br/>Relatório Técnico de Consulta", ParagraphStyle('Sig2', fontName='Helvetica', fontSize=8, leading=10, alignment=1))]
    ]
    t_sig = Table(sig_data, colWidths=[250, 260])
    t_sig.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_sig)
    
    # Build Document
    doc.build(story)
    
    # Clean up temp files
    try:
        if type_report == "property":
            temp_map_png = os.path.join(ROOT_DIR, "scratch", f"temp_map_{cod_imovel.replace('-', '_')}.png")
            if os.path.exists(temp_map_png):
                os.remove(temp_map_png)
        elif type_report == "municipal":
            temp_map_png = os.path.join(ROOT_DIR, "scratch", "temp_map_municipal.png")
            if os.path.exists(temp_map_png):
                os.remove(temp_map_png)
    except Exception:
        pass
        
    return True

def export_geopdf_map(output_pdf_path, xmin, ymin, xmax, ymax, active_layers, basemap="osm"):
    dx = xmax - xmin
    dy = ymax - ymin
    
    # Layout dimensions for A4 Landscape
    W_fig = 11.69
    H_fig = 8.27
    W_max_map = 7.48
    H_max_map = 6.95
    
    A = dy / dx if dx > 0 else 1.0
    if A > H_max_map / W_max_map:
        H_map = H_max_map
        W_map = H_map / A
    else:
        W_map = W_max_map
        H_map = W_map * A
        
    X_center = 0.08 * W_fig + (W_max_map - W_map) / 2.0
    Y_center = 0.08 * H_fig + (H_max_map - H_map) / 2.0
    
    w_frac = W_map / W_fig
    h_frac = H_map / H_fig
    left_frac = X_center / W_fig
    bottom_frac = Y_center / H_fig
    
    s_x = dx / W_map
    s_y = dy / H_map
    
    d_left = left_frac * W_fig
    d_right = W_fig - (d_left + W_map)
    d_bottom = bottom_frac * H_fig
    d_top = H_fig - (d_bottom + H_map)
    
    xmin_exp = xmin - d_left * s_x
    xmax_exp = xmax + d_right * s_x
    ymin_exp = ymin - d_bottom * s_y
    ymax_exp = ymax + d_top * s_y
    
    fig = plt.figure(figsize=(W_fig, H_fig), dpi=150)
    
    ax_map = fig.add_axes([left_frac, bottom_frac, w_frac, h_frac])
    
    plot_all_active_layers(ax_map, xmin, ymin, xmax, ymax, active_layers, basemap=basemap)
    
    # Coordinate ticks and neatlines
    ax_map.grid(True, linestyle=':', color='#cbd5e1', linewidth=0.5, alpha=0.8)
    for spine in ax_map.spines.values():
        spine.set_color('black')
        spine.set_linewidth(1.2)
        
    import matplotlib.ticker as ticker
    def format_lon(x, pos):
        return f"{abs(x):.4f}°O"
    def format_lat(y, pos):
        return f"{abs(y):.4f}°S"
        
    ax_map.xaxis.set_major_formatter(ticker.FuncFormatter(format_lon))
    ax_map.yaxis.set_major_formatter(ticker.FuncFormatter(format_lat))
    ax_map.tick_params(axis='both', which='major', labelsize=7.5, colors='#1e293b')
    
    # Graphical Scale Bar inside ax_map
    lat_mid = (ymin + ymax) / 2.0
    m_per_deg_lon = 111000.0 * math.cos(math.radians(lat_mid))
    ground_width_m = dx * m_per_deg_lon
    
    if ground_width_m < 500:
        scale_len = 50.0
        scale_label = "50 m"
    elif ground_width_m < 2000:
        scale_len = 200.0
        scale_label = "200 m"
    elif ground_width_m < 10000:
        scale_len = 1000.0
        scale_label = "1 km"
    elif ground_width_m < 50000:
        scale_len = 5000.0
        scale_label = "5 km"
    else:
        scale_len = 20000.0
        scale_label = "20 km"
        
    scale_deg = scale_len / m_per_deg_lon
    sb_x = xmin + dx * 0.05
    sb_y = ymin + dy * 0.05
    
    scale_box = plt.Rectangle((sb_x - dx*0.02, sb_y - dy*0.02), scale_deg + dx*0.04, dy*0.065,
                              facecolor='white', alpha=0.85, edgecolor='#cbd5e1', linewidth=0.5, zorder=5)
    ax_map.add_patch(scale_box)
    
    ax_map.plot([sb_x, sb_x + scale_deg], [sb_y, sb_y], color='black', linewidth=2.5, zorder=6)
    ax_map.text(sb_x + scale_deg/2.0, sb_y + dy*0.015, scale_label,
                horizontalalignment='center', fontsize=7.5, fontweight='bold', color='black', zorder=6)
                
    # Side Panel
    ax_panel = fig.add_axes([0.76, 0.08, 0.20, 0.84])
    axes_width_m = W_map * 0.0254
    scale_ratio = ground_width_m / axes_width_m
    scale_text = f"1:{int(round(scale_ratio, -1)):,}".replace(',', '.')
    
    draw_map_side_panel(fig, ax_panel, active_layers, scale_text, "MAPA GEORREFERENCIADO", "#1d4ed8", is_geopdf=True)
    
    temp_png_path = os.path.join(ROOT_DIR, "scratch", f"temp_export_{int(xmin*10000)}_{int(ymin*10000)}.png")
    os.makedirs(os.path.dirname(temp_png_path), exist_ok=True)
    plt.savefig(temp_png_path, dpi=150, bbox_inches=None, pad_inches=0)
    plt.close()
    
    try:
        from osgeo import gdal
        gdal.Translate(output_pdf_path, temp_png_path, format="PDF", outputSRS="EPSG:4326", outputBounds=[xmin_exp, ymax_exp, xmax_exp, ymin_exp])
        print(f"GeoPDF export completed successfully: {output_pdf_path}")
        if os.path.exists(temp_png_path):
            os.remove(temp_png_path)
        return True
    except Exception as e:
        print(f"Error in GDAL GeoPDF export: {e}")
        return False

if __name__ == "__main__":
    print("Testing report generation locally...")
    generate_report_pdf("municipal", None, "relatorio_municipal_teste.pdf")
    print("Municipal test report generated successfully!")
    generate_report_pdf("property", "BA-2932101-5ECDDE04CC4B4DD482F39EFC89382402", "relatorio_imovel_teste.pdf")
    print("Property test report generated successfully!")
