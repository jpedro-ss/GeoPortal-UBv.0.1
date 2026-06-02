import os
import json
import shutil
import subprocess
import numpy as np
from PIL import Image
from osgeo import gdal, ogr, osr

# Define paths
ROOT_DIR = r"c:\Users\joao_\Downloads\Portal_WebGIS"
DATA_DIR = os.path.join(ROOT_DIR, "data")
RASTER_DIR = os.path.join(DATA_DIR, "rasters")

# Create folders if not exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(RASTER_DIR, exist_ok=True)

# Helper to run ogr2ogr
def run_ogr2ogr(input_path, output_path, simplify_tolerance=None):
    qgis_bin = r"C:\Program Files\QGIS 3.40.8\bin"
    ogr2ogr_exe = os.path.join(qgis_bin, "ogr2ogr.exe")
    
    # Base command
    cmd = [
        ogr2ogr_exe,
        "-f", "GeoJSON",
        output_path,
        input_path,
        "-t_srs", "EPSG:4326"  # Ensure WGS84
    ]
    
    if simplify_tolerance:
        cmd.extend(["-simplify", str(simplify_tolerance)])
        
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"Error simplifying {input_path}: {result.stderr}")
        return False
    print(f"Successfully processed {input_path}")
    return True

# Process Rasters using VECTORIZED NUMPY with strict exact NoData checks
def process_rasters_vectorized():
    rasters = [
        {
            "name": "modelo_digital",
            "path": os.path.join(ROOT_DIR, "Acesso_urbano", "Acesso_município", "Acesso_infraestrutura", "Acesso_modelo digital", "Acesso_modelo digital.tif"),
            "stops": [
                (195.0, (46, 117, 89, 230)),    # Dark Green
                (350.0, (120, 194, 110, 230)), # Light Green
                (550.0, (230, 220, 140, 230)), # Beige
                (700.0, (190, 130, 80, 230)),  # Sand Brown
                (850.0, (120, 60, 30, 230)),   # Dark Brown
                (910.0, (240, 240, 255, 230))  # Snow/High White
            ],
            "nodata": 32767.0
        },
        {
            "name": "declividade",
            "path": os.path.join(ROOT_DIR, "Acesso_urbano", "Acesso_município", "Acesso_infraestrutura", "Acesso_declividade", "Acesso_declividade.tif"),
            "stops": [
                (0.0, (46, 204, 113, 0)),      # Gentle - transparent
                (5.0, (46, 204, 113, 100)),    # Flat/gentle - Soft Green
                (15.0, (241, 196, 15, 180)),   # Moderate - Yellow
                (30.0, (230, 126, 34, 210)),   # Steep - Orange
                (45.0, (231, 76, 60, 230)),    # Very Steep - Light Red
                (100.0, (150, 0, 0, 240))      # Extreme - Dark Red
            ],
            "nodata": -3.4028230607370965e+38
        },
        {
            "name": "deslisamento", # Aspect (Slope direction)
            "path": os.path.join(ROOT_DIR, "Acesso_urbano", "Acesso_município", "Acesso_infraestrutura", "Acesso_deslisamento", "Acesso_deslisamento.tif"),
            "stops": None,
            "nodata": -3.4028230607370965e+38
        }
    ]
    
    # Extract bounds from first raster
    ds = gdal.Open(rasters[0]["path"], gdal.GA_ReadOnly)
    width = ds.RasterXSize
    height = ds.RasterYSize
    geotransform = ds.GetGeoTransform()
    
    xmin = geotransform[0]
    xmax = xmin + width * geotransform[1]
    ymax = geotransform[3]
    ymin = ymax + height * geotransform[5]
    
    bounds = [[ymin, xmin], [ymax, xmax]]
    print(f"Raster spatial bounds: {bounds}")
    with open(os.path.join(RASTER_DIR, "bounds.json"), "w") as f:
        json.dump({"bounds": bounds}, f, indent=4)
    ds = None
    
    for r in rasters:
        print(f"Processing raster vectorized with NoData fix: {r['name']}")
        ds = gdal.Open(r["path"], gdal.GA_ReadOnly)
        band = ds.GetRasterBand(1)
        data = band.ReadAsArray().astype(np.float32)
        nodata_val = r["nodata"]
        
        img_h, img_w = data.shape
        rgba_img = np.zeros((img_h, img_w, 4), dtype=np.uint8)
        
        # Mask out nodata and nan - extremely robust to remove all blank/white borders
        nodata_mask = (data == nodata_val) | np.isnan(data) | (data >= 32767.0) | (data < -3e38)
        
        if r["name"] == "deslisamento": # Aspect color wheel mapping
            aspect_mask = (data < 0) | nodata_mask
            
            deg = data
            c = (1.0 - abs(2.0 * 0.55 - 1.0)) * 0.8  # 0.72
            deg_60 = deg / 60.0
            term = (deg_60 % 2.0) - 1.0
            x = c * (1.0 - np.abs(term))
            m = 0.55 - c / 2.0  # 0.19
            
            r_p = np.zeros(data.shape, dtype=np.float32)
            g_p = np.zeros(data.shape, dtype=np.float32)
            b_p = np.zeros(data.shape, dtype=np.float32)
            
            m0 = (deg >= 0) & (deg < 60)
            m1 = (deg >= 60) & (deg < 120)
            m2 = (deg >= 120) & (deg < 180)
            m3 = (deg >= 180) & (deg < 240)
            m4 = (deg >= 240) & (deg < 300)
            m5 = (deg >= 300) & (deg <= 360)
            
            r_p[m0] = c
            g_p[m0] = x[m0]
            
            r_p[m1] = x[m1]
            g_p[m1] = c
            
            g_p[m2] = c
            b_p[m2] = x[m2]
            
            g_p[m3] = x[m3]
            b_p[m3] = c
            
            r_p[m4] = x[m4]
            b_p[m4] = c
            
            r_p[m5] = c
            b_p[m5] = x[m5]
            
            rgba_img[..., 0] = ((r_p + m) * 255).astype(np.uint8)
            rgba_img[..., 1] = ((g_p + m) * 255).astype(np.uint8)
            rgba_img[..., 2] = ((b_p + m) * 255).astype(np.uint8)
            rgba_img[..., 3] = 160  # Aspect transparency
            rgba_img[aspect_mask] = [0, 0, 0, 0]
            
        else: # DEM and Slope gradient rendering
            stops = r["stops"]
            val_clipped = np.clip(data, stops[0][0], stops[-1][0])
            
            r_channel = np.zeros(data.shape, dtype=np.float32)
            g_channel = np.zeros(data.shape, dtype=np.float32)
            b_channel = np.zeros(data.shape, dtype=np.float32)
            a_channel = np.zeros(data.shape, dtype=np.float32)
            
            for i in range(len(stops) - 1):
                s1, c1 = stops[i]
                s2, c2 = stops[i+1]
                
                # Create mask for this segment interval
                mask = (val_clipped >= s1) & (val_clipped <= s2)
                if not np.any(mask):
                    continue
                
                # Interpolation ratio
                t = (val_clipped - s1) / (s2 - s1)
                
                r_channel[mask] = c1[0] + (c2[0] - c1[0]) * t[mask]
                g_channel[mask] = c1[1] + (c2[1] - c1[1]) * t[mask]
                b_channel[mask] = c1[2] + (c2[2] - c1[2]) * t[mask]
                a_channel[mask] = c1[3] + (c2[3] - c1[3]) * t[mask]
                
            rgba_img[..., 0] = r_channel.astype(np.uint8)
            rgba_img[..., 1] = g_channel.astype(np.uint8)
            rgba_img[..., 2] = b_channel.astype(np.uint8)
            rgba_img[..., 3] = a_channel.astype(np.uint8)
            rgba_img[nodata_mask] = [0, 0, 0, 0]
            
        # Save as PNG
        pil_img = Image.fromarray(rgba_img, "RGBA")
        # Resize to max 2048 to load instantly in Leaflet with gorgeous visual fidelity
        pil_img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        pil_img.save(os.path.join(RASTER_DIR, f"{r['name']}.png"), "PNG")
        print(f"Saved styled PNG to {r['name']}.png")
        ds = None

# Process all Vector layers (already simplified, but let's run just rasters if vectors are already processed to save time! Or we can run both. Actually, to be super fast, we can just process rasters!)
def process_vectors():
    # Only runs if they don't exist yet to save massive CPU, otherwise we already have them!
    # Let's keep it complete.
    pass

if __name__ == "__main__":
    print("Starting WebGIS raster update pipeline with exact NoData mask...")
    process_rasters_vectorized()
    print("WebGIS raster update completed successfully!")
