import os
import sys
import json
import urllib.parse
import http.server
import socketserver

# Import custom pipelines
import update_data
import report_generator

PORT = 8080
ROOT_DIR = r"c:\Users\joao_\Downloads\Portal_WebGIS"

# Ensure working directory is ROOT_DIR
os.chdir(ROOT_DIR)

class GeoPortalHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Print directly to stdout (forces flush to task logs)
        sys.stdout.write(f"[Server] {self.address_string()} - [{self.log_date_time_string()}] {format % args}\n")
        sys.stdout.flush()

    def do_OPTIONS(self):
        # Handle CORS preflight requests
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()

    def send_json_error(self, status_code, message):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.end_headers()
        res = {"success": False, "error": message}
        self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        self.log_message(f"POST request received: {parsed_url.path}")
        
        if parsed_url.path == '/api/update_data':
            try:
                res = update_data.run_update_pipeline()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Private-Network', 'true')
                self.end_headers()
                
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode('utf-8'))
            except Exception as e:
                self.send_json_error(500, f"Erro interno ao atualizar: {e}")
                
        elif parsed_url.path == '/api/export_geopdf':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                params = json.loads(post_data.decode('utf-8'))
                
                xmin = float(params.get('xmin'))
                ymin = float(params.get('ymin'))
                xmax = float(params.get('xmax'))
                ymax = float(params.get('ymax'))
                active_layers = list(params.get('layers', []))
                basemap = params.get('basemap', 'osm')
                
                pdf_filename = "mapa_georreferenciado_ubaira.pdf"
                pdf_path = os.path.join(ROOT_DIR, "scratch", pdf_filename)
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                
                success = report_generator.export_geopdf_map(pdf_path, xmin, ymin, xmax, ymax, active_layers, basemap=basemap)
                
                if success and os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        pdf_bytes = f.read()
                        
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/pdf')
                    self.send_header('Content-Disposition', f'attachment; filename="{pdf_filename}"')
                    self.send_header('Content-Length', str(len(pdf_bytes)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Private-Network', 'true')
                    self.end_headers()
                    self.wfile.write(pdf_bytes)
                    
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass
                else:
                    self.send_json_error(500, "Erro ao processar e exportar o PDF georreferenciado.")
                    
            except Exception as e:
                self.send_json_error(500, f"Erro interno ao exportar: {e}")
                
        else:
            super().do_POST()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        self.log_message(f"GET request received: {parsed_url.path}")
        
        if parsed_url.path == '/api/generate_report':
            try:
                query_params = urllib.parse.parse_qs(parsed_url.query)
                type_report = query_params.get('type', ['municipal'])[0]
                cod_imovel = query_params.get('cod_imovel', [None])[0]
                
                # Active options (defaults if not specified)
                options = query_params.get('options', ['all'])[0]
                basemap = query_params.get('basemap', ['osm'])[0]
                active_layers_str = query_params.get('active_layers', [''])[0]
                active_layers = [l.strip() for l in active_layers_str.split(',') if l.strip()]
                
                if type_report == "municipal":
                    pdf_filename = "relatorio_geral_ubaira.pdf"
                else:
                    safe_car = cod_imovel.replace('-', '_') if cod_imovel else "imovel"
                    pdf_filename = f"relatorio_imovel_{safe_car}.pdf"
                    
                pdf_path = os.path.join(ROOT_DIR, "scratch", pdf_filename)
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                
                success = report_generator.generate_report_pdf(
                    type_report, cod_imovel, pdf_path, options,
                    basemap=basemap, active_layers=active_layers
                )
                
                if success and os.path.exists(pdf_path):
                    with open(pdf_path, 'rb') as f:
                        pdf_bytes = f.read()
                        
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/pdf')
                    safe_filename_header = urllib.parse.quote(pdf_filename)
                    self.send_header('Content-Disposition', f"attachment; filename*=UTF-8''{safe_filename_header}")
                    self.send_header('Content-Length', str(len(pdf_bytes)))
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Private-Network', 'true')
                    self.end_headers()
                    self.wfile.write(pdf_bytes)
                    
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass
                else:
                    self.send_json_error(404, f"Imóvel rural '{cod_imovel}' não encontrado ou erro na compilação do relatório.")
                    
            except Exception as e:
                self.send_json_error(500, f"Erro interno ao compilar relatório: {e}")
                
        else:
            super().do_GET()

def start_server():
    GeoPortalHTTPRequestHandler.protocol_version = "HTTP/1.1"
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("", PORT), GeoPortalHTTPRequestHandler) as httpd:
        sys.stdout.write(f"\n=======================================================\n")
        sys.stdout.write(f"  GeoPortal Ubaíra - Servidor Técnico Ativo\n")
        sys.stdout.write(f"  Acesse: http://localhost:{PORT}\n")
        sys.stdout.write(f"=======================================================\n\n")
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            sys.stdout.write("\nEncerrando servidor...\n")
            sys.stdout.flush()
            sys.exit(0)

if __name__ == "__main__":
    start_server()
