import os
import json
import numpy as np
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

def add_geom_to_plot(ax, geom, edge_color, fill_color, alpha=1.0, hatch=None):
    if geom.GetGeometryType() in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
        for i in range(geom.GetGeometryCount()):
            ring = geom.GetGeometryRef(i)
            if ring.GetGeometryType() == ogr.wkbLinearRing:
                points = [ring.GetPoint(j)[:2] for j in range(ring.GetPointCount())]
                poly = MplPolygon(points, edgecolor=edge_color, facecolor=fill_color, alpha=alpha, hatch=hatch)
                ax.add_patch(poly)
            else:
                for k in range(ring.GetGeometryCount()):
                    sub_ring = ring.GetGeometryRef(k)
                    points = [sub_ring.GetPoint(j)[:2] for j in range(sub_ring.GetPointCount())]
                    poly = MplPolygon(points, edgecolor=edge_color, facecolor=fill_color, alpha=alpha, hatch=hatch)
                    ax.add_patch(poly)

def generate_property_map(cod_imovel, output_png_path, options="all"):
    driver = ogr.GetDriverByName("GeoJSON")
    ds_iru = driver.Open(os.path.join(DATA_DIR, "iru.geojson"), 0)
    layer_iru = ds_iru.GetLayer()
    layer_iru.SetAttributeFilter(f"cod_imovel = '{cod_imovel}'")
    feat_prop = layer_iru.GetNextFeature()
    if not feat_prop:
        return False
        
    opts = [o.strip() for o in options.split(',')]
    show_all = "all" in opts or len(opts) == 0 or (len(opts) == 1 and opts[0] == "")
    show_app_rios = show_all or "app_rios" in opts
    show_app_nas = show_all or "app_nascente" in opts
    show_veg = show_all or "vegetacao_nativa" in opts
    show_topo = show_all or "topografia" in opts
    
    prop_geom = feat_prop.GetGeometryRef()
    extent = prop_geom.GetEnvelope() # xmin, xmax, ymin, ymax
    
    fig, ax = plt.subplots(figsize=(6, 5), dpi=150)
    ax.set_aspect('equal')
    
    # 1. Plot context properties
    layer_iru.ResetReading()
    layer_iru.SetAttributeFilter(None)
    layer_iru.SetSpatialFilter(prop_geom)
    for feat in layer_iru:
        if feat.GetField("cod_imovel") != cod_imovel:
            add_geom_to_plot(ax, feat.GetGeometryRef(), '#94a3b8', '#e2e8f0', alpha=0.3)
            
    # 2. Plot Topography (contour lines inside property envelope)
    if show_topo:
        try:
            ds_topo = driver.Open(os.path.join(DATA_DIR, "topografia.geojson"), 0)
            if ds_topo:
                layer_topo = ds_topo.GetLayer()
                layer_topo.SetSpatialFilter(prop_geom)
                for feat in layer_topo:
                    geom = feat.GetGeometryRef()
                    intersection = prop_geom.Intersection(geom)
                    if intersection and not intersection.IsEmpty():
                        geom_type = intersection.GetGeometryType()
                        if geom_type in [ogr.wkbLineString, ogr.wkbMultiLineString]:
                            for i in range(intersection.GetGeometryCount()):
                                line = intersection.GetGeometryRef(i)
                                if line.GetGeometryType() == ogr.wkbLineString:
                                    pts = [line.GetPoint(j)[:2] for j in range(line.GetPointCount())]
                                    if len(pts) > 1:
                                        x, y = zip(*pts)
                                        ax.plot(x, y, color='#cbd5e1', linewidth=0.5, alpha=0.6)
                                else:
                                    for k in range(line.GetGeometryCount()):
                                        sub_line = line.GetGeometryRef(k)
                                        pts = [sub_line.GetPoint(j)[:2] for j in range(sub_line.GetPointCount())]
                                        if len(pts) > 1:
                                            x, y = zip(*pts)
                                            ax.plot(x, y, color='#cbd5e1', linewidth=0.5, alpha=0.6)
        except Exception as e:
            print(f"Error drawing topography contours on map: {e}")
            
    # 3. Plot property boundary
    add_geom_to_plot(ax, prop_geom, '#d97706', '#fbbf24', alpha=0.12)
    
    # 4. Plot Native Veg
    if show_veg:
        ds_veg = driver.Open(os.path.join(DATA_DIR, "vegetacao_nativa.geojson"), 0)
        if ds_veg:
            layer_veg = ds_veg.GetLayer()
            layer_veg.SetSpatialFilter(prop_geom)
            for feat in layer_veg:
                intersection = prop_geom.Intersection(feat.GetGeometryRef())
                if intersection and not intersection.IsEmpty():
                    add_geom_to_plot(ax, intersection, '#15803d', '#22c55e', alpha=0.35)
            
    # 5. Plot River APP
    if show_app_rios:
        ds_rios = driver.Open(os.path.join(DATA_DIR, "app_rios.geojson"), 0)
        if ds_rios:
            layer_rios = ds_rios.GetLayer()
            layer_rios.SetSpatialFilter(prop_geom)
            for feat in layer_rios:
                intersection = prop_geom.Intersection(feat.GetGeometryRef())
                if intersection and not intersection.IsEmpty():
                    add_geom_to_plot(ax, intersection, '#1d4ed8', '#3b82f6', alpha=0.4, hatch='//')
            
    # 6. Plot Spring APP
    if show_app_nas:
        ds_nas = driver.Open(os.path.join(DATA_DIR, "app_nascente.geojson"), 0)
        if ds_nas:
            layer_nas = ds_nas.GetLayer()
            layer_nas.SetSpatialFilter(prop_geom)
            for feat in layer_nas:
                intersection = prop_geom.Intersection(feat.GetGeometryRef())
                if intersection and not intersection.IsEmpty():
                    add_geom_to_plot(ax, intersection, '#0e7490', '#06b6d4', alpha=0.45)
            
    # Crop to bounds with buffer
    dx = extent[1] - extent[0]
    dy = extent[3] - extent[2]
    ax.set_xlim(extent[0] - dx*0.15, extent[1] + dx*0.15)
    ax.set_ylim(extent[2] - dy*0.15, extent[3] + dy*0.15)
    
    ax.set_title("Delimitação e Áreas Ambientais do Imóvel", fontsize=10, fontweight='bold', color='#1e293b')
    ax.grid(True, linestyle='--', alpha=0.3)
    ax.tick_params(axis='both', which='major', labelsize=8)
    
    # Legend
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    legend_elements = [
        Line2D([0], [0], color='#d97706', lw=2, label='Imóvel Alvo (CAR)')
    ]
    if show_veg:
        legend_elements.append(Patch(facecolor='#22c55e', edgecolor='#15803d', alpha=0.35, label='Vegetação Nativa'))
    if show_app_rios:
        legend_elements.append(Patch(facecolor='#3b82f6', edgecolor='#1d4ed8', alpha=0.4, hatch='//', label='APP Margem Rio'))
    if show_app_nas:
        legend_elements.append(Patch(facecolor='#06b6d4', edgecolor='#0e7490', alpha=0.45, label='APP Raio Nascente'))
    if show_topo:
        legend_elements.append(Line2D([0], [0], color='#cbd5e1', lw=1, linestyle='--', label='Curvas de Nível'))
    legend_elements.append(Patch(facecolor='#e2e8f0', edgecolor='#94a3b8', alpha=0.3, label='Imóveis Adjacentes'))
    
    ax.legend(handles=legend_elements, loc='lower right', fontsize=8)
    
    plt.tight_layout()
    plt.savefig(output_png_path, dpi=150)
    plt.close()
    return True

def generate_report_pdf(type_report, cod_imovel, output_pdf_path, options="all"):
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
        if generate_property_map(cod_imovel, temp_map_png, options):
            story.append(Image(temp_map_png, width=320, height=266))
            story.append(Spacer(1, 8))
            
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
    
    # Clean up temp file
    if type_report == "property":
        try:
            temp_map_png = os.path.join(ROOT_DIR, "scratch", f"temp_map_{cod_imovel.replace('-', '_')}.png")
            if os.path.exists(temp_map_png):
                os.remove(temp_map_png)
        except Exception:
            pass
            
    return True

def export_geopdf_map(output_pdf_path, xmin, ymin, xmax, ymax, active_layers):
    driver = ogr.GetDriverByName("GeoJSON")
    
    dx = xmax - xmin
    dy = ymax - ymin
    aspect_ratio = dy / dx if dx > 0 else 1.0
    
    fig = plt.figure(figsize=(10, 10 * aspect_ratio), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis('off')
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    
    layer_map = {
        'municipio': ('municipio.geojson', '#ef4444', 'none', 1.0, None, 2),
        'distritos': ('distritos.geojson', '#3b82f6', '#93c5fd', 0.15, None, 1),
        'setores': ('setores.geojson', '#10b981', '#6ee7b7', 0.1, None, 1),
        'iru': ('iru.geojson', '#d97706', '#fbbf24', 0.15, None, 1),
        'app_rios': ('app_rios.geojson', '#1d4ed8', '#3b82f6', 0.35, '//', 1),
        'drenagem': ('drenagem.geojson', '#2563eb', 'none', 1.0, None, 1.5),
        'app_nascente': ('app_nascente.geojson', '#0e7490', '#06b6d4', 0.45, None, 1),
        'app_lago_natural': ('app_lago_natural.geojson', '#0284c7', '#38bdf8', 0.4, None, 1),
        'app_reservatorio': ('app_reservatorio.geojson', '#0369a1', '#0ea5e9', 0.4, None, 1),
        'app_topo_morro': ('app_topo_morro.geojson', '#b45309', '#f59e0b', 0.3, None, 1),
        'reserva_legal_proposta': ('reserva_legal_proposta.geojson', '#f97316', '#fdba74', 0.25, None, 1),
        'reserva_legal_aprovada': ('reserva_legal_aprovada.geojson', '#10b981', '#a7f3d0', 0.25, None, 1),
        'reserva_legal_averbada': ('reserva_legal_averbada.geojson', '#047857', '#6ee7b7', 0.25, None, 1),
        'vegetacao_nativa': ('vegetacao_nativa.geojson', '#15803d', '#22c55e', 0.35, None, 1),
        'urbano_ast': ('urbano_ast.geojson', '#ec4899', '#fbcfe8', 0.3, None, 1),
        'zona_urbana': ('zona_urbana.geojson', '#64748b', 'none', 0.5, None, 1),
        'regiao_metropolitana': ('regiao_metropolitana.geojson', '#a855f7', '#c084fc', 0.08, None, 1)
    }
    
    bg_keys = ['regiao_metropolitana', 'distritos', 'setores', 'iru', 'urbano_ast', 'reserva_legal_proposta', 'reserva_legal_aprovada', 'reserva_legal_averbada', 'vegetacao_nativa', 'app_topo_morro', 'app_lago_natural', 'app_reservatorio', 'app_rios', 'app_nascente']
    line_keys = ['zona_urbana', 'drenagem', 'municipio']
    
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(xmin, ymin)
    ring.AddPoint(xmax, ymin)
    ring.AddPoint(xmax, ymax)
    ring.AddPoint(xmin, ymax)
    ring.AddPoint(xmin, ymin)
    bbox_geom = ogr.Geometry(ogr.wkbPolygon)
    bbox_geom.AddGeometry(ring)
    
    def plot_keys(keys_list):
        for key in keys_list:
            if key in active_layers and key in layer_map:
                filename, edge_c, fill_c, alpha, hatch, lw = layer_map[key]
                filepath = os.path.join(DATA_DIR, filename)
                if not os.path.exists(filepath):
                    continue
                ds = driver.Open(filepath, 0)
                if not ds:
                    continue
                layer = ds.GetLayer()
                layer.SetSpatialFilter(bbox_geom)
                for feat in layer:
                    geom = feat.GetGeometryRef()
                    if geom:
                        geom_type = geom.GetGeometryType()
                        if geom_type in [ogr.wkbLineString, ogr.wkbMultiLineString]:
                            for i in range(geom.GetGeometryCount()):
                                line = geom.GetGeometryRef(i)
                                if line.GetGeometryType() == ogr.wkbLineString:
                                    pts = [line.GetPoint(j)[:2] for j in range(line.GetPointCount())]
                                    if len(pts) > 1:
                                        x, y = zip(*pts)
                                        ax.plot(x, y, color=edge_c, linewidth=lw, alpha=alpha)
                                else:
                                    for k in range(line.GetGeometryCount()):
                                        sub_line = line.GetGeometryRef(k)
                                        pts = [sub_line.GetPoint(j)[:2] for j in range(sub_line.GetPointCount())]
                                        if len(pts) > 1:
                                            x, y = zip(*pts)
                                            ax.plot(x, y, color=edge_c, linewidth=lw, alpha=alpha)
                        elif geom_type in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
                            add_geom_to_plot(ax, geom, edge_c, fill_c if fill_c != 'none' else 'none', alpha=alpha, hatch=hatch)
    
    plot_keys(bg_keys)
    plot_keys(line_keys)
    
    temp_png_path = os.path.join(ROOT_DIR, "scratch", f"temp_export_{int(xmin*10000)}_{int(ymin*10000)}.png")
    os.makedirs(os.path.dirname(temp_png_path), exist_ok=True)
    plt.savefig(temp_png_path, dpi=150, bbox_inches=None, pad_inches=0)
    plt.close()
    
    try:
        from osgeo import gdal
        gdal.Translate(output_pdf_path, temp_png_path, format="PDF", outputSRS="EPSG:4326", outputBounds=[xmin, ymax, xmax, ymin])
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
