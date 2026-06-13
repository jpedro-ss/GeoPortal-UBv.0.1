import os
import json
import requests

# Define paths
ROOT_DIR = r"c:\Users\joao_\Downloads\Portal_WebGIS"
DATA_DIR = os.path.join(ROOT_DIR, "data")

def sanitize_value(val):
    if not isinstance(val, str):
        return val
    
    # Clean encoding issues recursively
    val = val.replace("anllise", "análise")
    val = val.replace("anllises", "análises")
    val = val.replace("Aguardando anllise", "Aguardando Análise")
    val = val.replace("Aguardando análise", "Aguardando Análise")
    val = val.replace("no averbada", "não averbada")
    val = val.replace("no averbada", "não averbada")
    val = val.replace("no", "não")
    
    # Translate CAR status codes
    if val == "AT":
        return "Ativo (AT)"
    elif val == "PE":
        return "Pendente (PE)"
    elif val == "SU":
        return "Suspenso (SU)"
    elif val == "CA":
        return "Cancelado (CA)"
        
    return val

def clean_geojson_files():
    print("Iniciando limpeza de codificação nos arquivos GeoJSON...")
    geojson_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith('.geojson')]
    
    cleaned_count = 0
    for filename in geojson_files:
        filepath = os.path.join(DATA_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            modified = False
            for feature in data.get("features", []):
                props = feature.get("properties", {})
                for key, val in list(props.items()):
                    new_val = sanitize_value(val)
                    if new_val != val:
                        props[key] = new_val
                        modified = True
            
            if modified:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                print(f"  [Limpeza] Arquivo corrigido com sucesso: {filename}")
                cleaned_count += 1
            else:
                print(f"  [Limpeza] Sem pendências de caracteres em: {filename}")
                
        except Exception as e:
            print(f"  [ERRO] Falha ao processar {filename}: {e}")
            
    print(f"Limpeza concluída. {cleaned_count} arquivos atualizados.")
    return cleaned_count

def update_ibge_data():
    print("Sincronizando dados demográficos do IBGE para Ubaíra (2932101)...")
    live_data = {
        "populacao": 26116, # Censo 2022 default
        "densidade": 21.2,
        "area": 1231.0,
        "nome": "Ubaíra",
        "codigo": "2932101",
        "atualizado": False
    }
    
    try:
        # 1. Fetch general municipality meta
        meta_url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios/2932101"
        r_meta = requests.get(meta_url, timeout=8)
        if r_meta.status_code == 200:
            meta = r_meta.json()
            live_data["nome"] = meta.get("nome", "Ubaíra")
            
        # 2. Fetch Censo 2022 Population variable from SIDRA API
        # Agregado 9860, variavel 93 (População residente), localidade N6 (Município 2932101)
        pop_url = "https://servicodados.ibge.gov.br/api/v3/agregados/9860/periodos/2022/variaveis/93?localidades=N6[2932101]"
        r_pop = requests.get(pop_url, timeout=8)
        if r_pop.status_code == 200:
            pop_res = r_pop.json()
            # Parse population value
            try:
                pop_val = pop_res[0]["resultados"][0]["series"][0]["serie"]["2022"]
                live_data["populacao"] = int(pop_val)
                # Recalculate density based on standard area
                live_data["densidade"] = round(live_data["populacao"] / live_data["area"], 2)
                live_data["atualizado"] = True
                print(f"  [IBGE] População atualizada via API: {live_data['populacao']} habitantes.")
            except (KeyError, IndexError, ValueError) as parse_err:
                print(f"  [IBGE] Erro ao decodificar resposta do SIDRA: {parse_err}")
        else:
            print(f"  [IBGE] SIDRA respondeu com status {r_pop.status_code}")
            
    except Exception as e:
        print(f"  [IBGE] Falha na conexão com APIs do IBGE (usando defaults locais): {e}")
        
    # Write live data to JSON file
    ibge_path = os.path.join(DATA_DIR, "ibge_live.json")
    with open(ibge_path, "w", encoding="utf-8") as f:
        json.dump(live_data, f, ensure_ascii=False, indent=4)
    print(f"Dados do IBGE gravados em: {ibge_path}")
    return live_data

def update_car_from_wfs():
    print("Consultando novos registros de CAR no WFS oficial do INEMA Bahia...")
    wfs_url = (
        "http://geoservicos.inema.ba.gov.br/geoserver/wfs"
        "?service=WFS&version=1.0.0&request=GetFeature"
        "&typeName=inema:imovel_rural"
        "&CQL_FILTER=municipio='Ubaíra'"
        "&outputFormat=application/json"
    )
    
    try:
        r = requests.get(wfs_url, timeout=12)
        if r.status_code == 200:
            geojson_data = r.json()
            features = geojson_data.get("features", [])
            if len(features) > 0:
                # Overwrite local iru.geojson with fresh online features
                filepath = os.path.join(DATA_DIR, "iru.geojson")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(geojson_data, f, ensure_ascii=False, indent=4)
                print(f"  [SICAR] Baixadas {len(features)} propriedades rurais atualizadas do INEMA.")
                return len(features)
            else:
                print("  [SICAR] Nenhum registro encontrado para Ubaíra no WFS.")
        else:
            print(f"  [SICAR] WFS do INEMA respondeu com erro {r.status_code}. Mantendo dados locais.")
    except Exception as e:
        print(f"  [SICAR] Servidor WFS indisponível ou lento ({e}). Utilizando banco de dados local consolidado.")
    return 0

def run_update_pipeline():
    print("=== INICIANDO PIPELINE DE ATUALIZAÇÃO DO GEOPORTAL ===")
    
    # 1. Fetch CAR from WFS (Safe execution)
    update_car_from_wfs()
    
    # 2. Fetch IBGE demographic statistics
    ibge_stats = update_ibge_data()
    
    # 3. Clean up encodings (fix "anllise" and codes like "AT" / "PE")
    clean_count = clean_geojson_files()
    
    print("=== PIPELINE DE ATUALIZAÇÃO CONCLUÍDO COM SUCESSO ===")
    return {
        "success": True,
        "ibge": ibge_stats,
        "cleaned_files": clean_count
    }

if __name__ == "__main__":
    run_update_pipeline()
