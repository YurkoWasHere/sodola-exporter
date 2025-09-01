#!/usr/bin/env python3
"""
Sodola HTTP Exporter Service

HTTP service that provides Prometheus metrics for Sodola devices, similar to SNMP exporter.
Supports multi-target monitoring via query parameters.

Usage:
    python3 sodola_http_exporter.py [--port 9117] [--host 0.0.0.0]
    
Prometheus endpoint:
    http://localhost:9117/sodola?target=192.168.40.6&username=admin&password=admin
"""

import argparse
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import time
from sodola_exporter import SodolaExporter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sodola-http-exporter')

class SodolaHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Sodola metrics"""
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            parsed_url = urlparse(self.path)
            
            if parsed_url.path == '/sodola':
                self.handle_metrics_request(parsed_url)
            elif parsed_url.path == '/health':
                self.handle_health_request()
            elif parsed_url.path == '/':
                self.handle_root_request()
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            logger.error(f"Error handling request {self.path}: {e}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def handle_metrics_request(self, parsed_url):
        """Handle /sodola metrics endpoint"""
        query_params = parse_qs(parsed_url.query)
        
        # Extract target and credentials
        target = query_params.get('target', [None])[0]
        username = query_params.get('username', ['admin'])[0]
        password = query_params.get('password', ['admin'])[0]
        
        if not target:
            self.send_error(400, "Missing required 'target' parameter")
            return
        
        # Ensure target has protocol
        if not target.startswith(('http://', 'https://')):
            target = f"http://{target}"
        
        try:
            logger.info(f"Scraping metrics from {target}")
            start_time = time.time()
            
            # Create exporter and scrape metrics
            exporter = SodolaExporter(target, username, password)
            metrics = exporter.scrape_metrics()
            prometheus_output = exporter.format_prometheus_metrics(metrics)
            
            scrape_duration = time.time() - start_time
            logger.info(f"Scrape completed in {scrape_duration:.2f}s for {target}")
            
            # Add scrape duration metric
            prometheus_output += f"\n# HELP sodola_scrape_duration_seconds Time spent scraping Sodola device\n"
            prometheus_output += f"# TYPE sodola_scrape_duration_seconds gauge\n"
            prometheus_output += f"sodola_scrape_duration_seconds {scrape_duration}\n"
            
            # Add scrape success metric
            prometheus_output += f"\n# HELP sodola_up Whether the Sodola device is up and responding\n"
            prometheus_output += f"# TYPE sodola_up gauge\n"
            prometheus_output += f"sodola_up 1\n"
            
            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
            self.end_headers()
            self.wfile.write(prometheus_output.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Failed to scrape {target}: {e}")
            
            # Send error metrics
            error_metrics = f"# HELP sodola_up Whether the Sodola device is up and responding\n"
            error_metrics += f"# TYPE sodola_up gauge\n"
            error_metrics += f"sodola_up 0\n"
            error_metrics += f"\n# HELP sodola_scrape_duration_seconds Time spent scraping Sodola device\n"
            error_metrics += f"# TYPE sodola_scrape_duration_seconds gauge\n"
            error_metrics += f"sodola_scrape_duration_seconds 0\n"
            
            self.send_response(200)  # Still return 200 to avoid Prometheus errors
            self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
            self.end_headers()
            self.wfile.write(error_metrics.encode('utf-8'))
    
    def handle_health_request(self):
        """Handle /health endpoint"""
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "sodola-http-exporter"
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(health_status, indent=2).encode('utf-8'))
    
    def handle_root_request(self):
        """Handle root endpoint with service information"""
        info = """<!DOCTYPE html>
<html>
<head>
    <title>Sodola HTTP Exporter</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .endpoint { background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 4px; }
        code { background: #e8e8e8; padding: 2px 4px; border-radius: 2px; }
    </style>
</head>
<body>
    <h1>Sodola HTTP Exporter</h1>
    <p>HTTP service that provides Prometheus metrics for Sodola network devices.</p>
    
    <h2>Endpoints</h2>
    
    <div class="endpoint">
        <h3>GET /sodola</h3>
        <p>Scrape metrics from a Sodola device</p>
        <p><strong>Parameters:</strong></p>
        <ul>
            <li><code>target</code> - Required. Sodola device IP/hostname</li>
            <li><code>username</code> - Optional. Default: admin</li>
            <li><code>password</code> - Optional. Default: admin</li>
        </ul>
        <p><strong>Example:</strong> <code>/sodola?target=192.168.40.6</code></p>
    </div>
    
    <div class="endpoint">
        <h3>GET /health</h3>
        <p>Service health check</p>
    </div>
    
    <h2>Usage with Prometheus</h2>
    <pre>
scrape_configs:
  - job_name: 'sodola'
    static_configs:
      - targets:
        - 192.168.40.6
        - 192.168.40.4
    metrics_path: /sodola
    params:
      username: [admin]
      password: [admin]
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target
      - source_labels: [__param_target]
        target_label: instance
      - target_label: __address__
        replacement: localhost:9117
    </pre>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(info.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to use proper logging"""
        logger.info(f"{self.client_address[0]} - {format % args}")


class SodolaHTTPServer:
    """HTTP server for Sodola metrics"""
    
    def __init__(self, host='0.0.0.0', port=9118):
        self.host = host
        self.port = port
        self.server = None
    
    def start(self):
        """Start the HTTP server"""
        try:
            self.server = HTTPServer((self.host, self.port), SodolaHTTPHandler)
            logger.info(f"Sodola HTTP Exporter started on {self.host}:{self.port}")
            logger.info(f"Metrics endpoint: http://{self.host}:{self.port}/sodola")
            logger.info(f"Health endpoint: http://{self.host}:{self.port}/health")
            
            self.server.serve_forever()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
            self.stop()
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise
    
    def stop(self):
        """Stop the HTTP server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Server stopped")


def main():
    parser = argparse.ArgumentParser(description="Sodola HTTP Exporter for Prometheus")
    parser.add_argument("--host", default="0.0.0.0", 
                       help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9118,
                       help="Port to listen on (default: 9118)")
    parser.add_argument("--log-level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help="Log level (default: INFO)")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # Start server
    server = SodolaHTTPServer(args.host, args.port)
    server.start()


if __name__ == "__main__":
    main()