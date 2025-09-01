#!/usr/bin/env python3
"""
Sodola Web UI Prometheus Exporter

This tool scrapes metrics from the Sodola web interface and exports them
in Prometheus format.
"""

import hashlib
import requests
from requests.sessions import Session
import re
import time
import argparse
from typing import Dict, List, Tuple, Optional
from urllib.parse import urljoin


class SodolaExporter:
    def __init__(self, host: str, username: str = "admin", password: str = "admin"):
        self.host = host.rstrip('/')
        self.username = username
        self.password = password
        self.session = Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux x86_64) Prometheus Sodola Exporter'
        })
        
    def _md5_hash(self, text: str) -> str:
        """Create MD5 hash as expected by Sodola login"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def login(self) -> bool:
        """Login to Sodola web interface"""
        try:
            # Create MD5 hash of username+password
            combined = self.username + self.password
            response_hash = self._md5_hash(combined)
            
            # Prepare login data
            login_data = {
                'username': self.username,
                'password': self.password,
                'Response': response_hash,
                'language': 'EN'
            }
            
            # Set cookie as the JavaScript would
            self.session.cookies.set('admin', response_hash)
            
            # Submit login
            login_url = f"{self.host}/login.cgi"
            response = self.session.post(login_url, data=login_data)
            
            # Check if login was successful
            if response.status_code == 200:
                # Look for redirect or success indicators
                if 'login.cgi' not in response.url and response.url != login_url:
                    return True
                # Some systems return 200 but with error content
                if 'error' not in response.text.lower():
                    return True
                    
            return False
            
        except Exception as e:
            print(f"Login failed: {e}")
            return False
    
    def discover_pages(self) -> List[str]:
        """Discover available pages in the web interface"""
        pages = []
        common_paths = [
            '/', '/index.cgi', '/main.cgi', '/status.cgi', '/system.cgi',
            '/info.cgi', '/config.cgi', '/network.cgi', '/device.cgi',
            '/stats.cgi', '/monitor.cgi', '/port.cgi?page=stats', '/port.cgi'
        ]
        
        for path in common_paths:
            try:
                url = f"{self.host}{path}"
                response = self.session.get(url, timeout=5)
                if response.status_code == 200 and len(response.text) > 100:
                    pages.append(path)
            except:
                continue
                
        return pages
    
    def scrape_metrics(self) -> Dict[str, List[Tuple[str, Dict[str, str], float]]]:
        """Scrape metrics from all available pages"""
        if not self.login():
            raise Exception("Failed to login to Sodola device")
            
        metrics = {}
        pages = self.discover_pages()
        
        print(f"Found {len(pages)} accessible pages")
        
        for page in pages:
            try:
                url = f"{self.host}{page}"
                response = self.session.get(url, timeout=10)
                
                # Handle port pages specially
                if 'port.cgi?page=stats' in page:
                    page_metrics = self._extract_port_stats(response.text)
                    # Merge the dictionaries of metric lists
                    for metric_name, metric_list in page_metrics.items():
                        if metric_name not in metrics:
                            metrics[metric_name] = []
                        metrics[metric_name].extend(metric_list)
                elif page == '/port.cgi':
                    page_metrics = self._extract_port_config(response.text)
                    # Merge the dictionaries of metric lists
                    for metric_name, metric_list in page_metrics.items():
                        if metric_name not in metrics:
                            metrics[metric_name] = []
                        metrics[metric_name].extend(metric_list)
                else:
                    # Skip other pages for now to focus on port stats
                    pass
            except Exception as e:
                print(f"Failed to scrape {page}: {e}")
                
        return metrics
    
    def _extract_metrics_from_html(self, html: str, page_name: str) -> Dict[str, float]:
        """Extract numeric metrics from HTML content"""
        metrics = {}
        
        # Common patterns for finding metrics
        patterns = [
            # Look for table cells or spans with numbers
            r'<td[^>]*>([^<]*\d+(?:\.\d+)?[^<]*)</td>',
            r'<span[^>]*>([^<]*\d+(?:\.\d+)?[^<]*)</span>',
            r'<div[^>]*>([^<]*\d+(?:\.\d+)?[^<]*)</div>',
            # Look for specific metric formats
            r'(\w+):\s*(\d+(?:\.\d+)?)',
            r'(\w+)\s*=\s*(\d+(?:\.\d+)?)',
            # Network interface stats
            r'(rx_bytes|tx_bytes|rx_packets|tx_packets):\s*(\d+)',
            # System stats
            r'(cpu|memory|temperature|uptime|voltage):\s*(\d+(?:\.\d+)?)',
            # Status indicators
            r'(status|state|connected|online):\s*(\d+)',
        ]
        
        # Clean HTML for better text extraction
        clean_text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r'<style.*?</style>', '', clean_text, flags=re.DOTALL | re.IGNORECASE)
        
        for pattern in patterns:
            matches = re.findall(pattern, clean_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple) and len(match) == 2:
                    key, value = match
                    try:
                        float_val = float(value)
                        metric_name = self._sanitize_metric_name(f"sodola_{page_name}_{key}")
                        metrics[metric_name] = float_val
                    except ValueError:
                        continue
                elif isinstance(match, str):
                    # Extract number from single match
                    numbers = re.findall(r'\d+(?:\.\d+)?', match)
                    if numbers:
                        try:
                            float_val = float(numbers[0])
                            # Try to infer metric name from surrounding context
                            context = re.search(r'(\w+)[^>]*>' + re.escape(match), clean_text)
                            if context:
                                metric_name = self._sanitize_metric_name(f"sodola_{page_name}_{context.group(1)}")
                                metrics[metric_name] = float_val
                        except ValueError:
                            continue
        
        return metrics
    
    def _extract_port_stats(self, html: str) -> Dict[str, List[Tuple[str, Dict[str, str], float]]]:
        """Extract port statistics from the port stats table
        
        Returns:
            Dict with metric names as keys and list of (metric_name, labels, value) tuples
        """
        metrics = {}
        
        # Parse the port statistics table
        # Look for table rows with port data
        port_pattern = r'<tr>\s*<td>Port\s+(\d+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>(\d+)</td>\s*<td>(\d+)</td>\s*<td>(\d+)</td>\s*<td>(\d+)</td>\s*</tr>'
        
        matches = re.findall(port_pattern, html, re.IGNORECASE)
        
        # Initialize metric groups
        if 'ifAdminStatus' not in metrics:
            metrics['ifAdminStatus'] = []
        if 'ifOperStatus' not in metrics:
            metrics['ifOperStatus'] = []
        if 'ifInUcastPkts' not in metrics:
            metrics['ifInUcastPkts'] = []
        if 'ifOutUcastPkts' not in metrics:
            metrics['ifOutUcastPkts'] = []
        if 'ifInErrors' not in metrics:
            metrics['ifInErrors'] = []
        if 'ifOutErrors' not in metrics:
            metrics['ifOutErrors'] = []
        if 'ifHCInOctets' not in metrics:
            metrics['ifHCInOctets'] = []
        if 'ifHCOutOctets' not in metrics:
            metrics['ifHCOutOctets'] = []
        
        for match in matches:
            port_num, state, link_status, tx_good, tx_bad, rx_good, rx_bad = match
            
            # Create labels similar to SNMP exporter
            labels = {
                'ifIndex': port_num,
                'ifName': f'Port{port_num}',
                'ifDescr': f'Port {port_num}',
                'ifAlias': f'Port {port_num}'
            }
            
            # Administrative status (1=up, 2=down in SNMP conventions)
            admin_status = 1 if state.strip().lower() == 'enable' else 2
            metrics['ifAdminStatus'].append(('ifAdminStatus', labels, float(admin_status)))
            
            # Operational status (1=up, 2=down in SNMP conventions)
            oper_status = 1 if 'up' in link_status.lower() else 2
            metrics['ifOperStatus'].append(('ifOperStatus', labels, float(oper_status)))
            
            # Packet counters
            try:
                tx_good_pkts = float(tx_good)
                tx_bad_pkts = float(tx_bad)
                rx_good_pkts = float(rx_good)
                rx_bad_pkts = float(rx_bad)
                
                metrics['ifOutUcastPkts'].append(('ifOutUcastPkts', labels, tx_good_pkts))
                metrics['ifOutErrors'].append(('ifOutErrors', labels, tx_bad_pkts))
                metrics['ifInUcastPkts'].append(('ifInUcastPkts', labels, rx_good_pkts))
                metrics['ifInErrors'].append(('ifInErrors', labels, rx_bad_pkts))
                
                # Estimate byte counters from packet counters
                # Use average Ethernet frame size estimates based on typical network traffic
                # - Good packets: assume ~800 bytes average (mix of small control and larger data frames)
                # - Error packets: assume ~64 bytes average (typically smaller, malformed frames)
                avg_good_frame_size = 800
                avg_error_frame_size = 64
                
                estimated_tx_bytes = (tx_good_pkts * avg_good_frame_size) + (tx_bad_pkts * avg_error_frame_size)
                estimated_rx_bytes = (rx_good_pkts * avg_good_frame_size) + (rx_bad_pkts * avg_error_frame_size)
                
                metrics['ifHCOutOctets'].append(('ifHCOutOctets', labels, estimated_tx_bytes))
                metrics['ifHCInOctets'].append(('ifHCInOctets', labels, estimated_rx_bytes))
                
            except ValueError:
                continue
        
        return metrics
    
    def _extract_port_config(self, html: str) -> Dict[str, List[Tuple[str, Dict[str, str], float]]]:
        """Extract port configuration from the port config table"""
        metrics = {}
        
        # Parse the port configuration table - look for the status table at the bottom
        # This table shows actual port states and speeds
        port_pattern = r'<tr>\s*<td>Port\s+(\d+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*</tr>'
        
        matches = re.findall(port_pattern, html, re.IGNORECASE)
        
        # Initialize metric groups for additional SNMP metrics
        if 'ifSpeed' not in metrics:
            metrics['ifSpeed'] = []
        if 'ifHighSpeed' not in metrics:
            metrics['ifHighSpeed'] = []
        if 'ifDuplex' not in metrics:
            metrics['ifDuplex'] = []
        
        for match in matches:
            port_num, state, config_speed, actual_speed, config_flow, actual_flow = match
            
            # Create labels similar to SNMP exporter
            labels = {
                'ifIndex': port_num,
                'ifName': f'Port{port_num}',
                'ifDescr': f'Port {port_num}',
                'ifAlias': f'Port {port_num}'
            }
            
            # Parse actual speed/duplex information
            speed_mbps = 0
            duplex = 2  # 2=half-duplex, 3=full-duplex in SNMP
            
            actual_speed = actual_speed.strip()
            if 'Link Down' not in actual_speed:
                # Parse speed and duplex
                if '10G' in actual_speed or '10000' in actual_speed:
                    speed_mbps = 10000
                elif '2500' in actual_speed:
                    speed_mbps = 2500
                elif '1000' in actual_speed:
                    speed_mbps = 1000
                elif '100' in actual_speed:
                    speed_mbps = 100
                elif '10' in actual_speed:
                    speed_mbps = 10
                    
                # Duplex detection
                if 'Full' in actual_speed:
                    duplex = 3  # full-duplex
                elif 'Half' in actual_speed:
                    duplex = 2  # half-duplex
                else:
                    duplex = 3  # assume full-duplex for modern links
            
            # Add SNMP metrics
            # ifSpeed - interface speed in bits per second
            if speed_mbps > 0:
                speed_bps = speed_mbps * 1000000
                metrics['ifSpeed'].append(('ifSpeed', labels, float(speed_bps)))
                
                # ifHighSpeed - interface speed in millions of bits per second (for high-speed interfaces)
                if speed_mbps >= 20:  # SNMP convention: use ifHighSpeed for >= 20 Mbps
                    metrics['ifHighSpeed'].append(('ifHighSpeed', labels, float(speed_mbps)))
                    
            # ifDuplex - duplex mode (not standard SNMP but commonly used)
            metrics['ifDuplex'].append(('ifDuplex', labels, float(duplex)))
        
        return metrics
    
    def _sanitize_metric_name(self, name: str) -> str:
        """Sanitize metric name for Prometheus format"""
        # Convert to lowercase and replace invalid chars with underscores
        name = re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())
        # Remove duplicate underscores
        name = re.sub(r'_+', '_', name)
        # Remove leading/trailing underscores
        name = name.strip('_')
        return name
    
    def format_prometheus_metrics(self, metrics: Dict[str, List[Tuple[str, Dict[str, str], float]]]) -> str:
        """Format metrics in Prometheus exposition format similar to SNMP exporter"""
        output = []
        
        # Define metric descriptions similar to SNMP MIB
        metric_descriptions = {
            'ifAdminStatus': 'The desired state of the interface (1=up, 2=down)',
            'ifOperStatus': 'The current operational state of the interface (1=up, 2=down)',
            'ifSpeed': 'An estimate of the interface current bandwidth in bits per second',
            'ifHighSpeed': 'An estimate of the interface current bandwidth in units of 1,000,000 bits per second',
            'ifDuplex': 'The duplex mode of the interface (2=half-duplex, 3=full-duplex)',
            'ifHCInOctets': 'The total number of octets received on the interface, including framing characters - 1.3.6.1.2.1.31.1.1.1.6',
            'ifHCOutOctets': 'The total number of octets transmitted out of the interface, including framing characters - 1.3.6.1.2.1.31.1.1.1.10',
            'ifInUcastPkts': 'The number of packets delivered by this sub-layer to a higher sub-layer which were not addressed to a multicast or broadcast address',
            'ifOutUcastPkts': 'The total number of packets that higher-level protocols requested be transmitted which were not addressed to a multicast or broadcast address',
            'ifInErrors': 'The number of inbound packets that contained errors preventing them from being deliverable',
            'ifOutErrors': 'The number of outbound packets that could not be transmitted because of errors'
        }
        
        metric_types = {
            'ifAdminStatus': 'gauge',
            'ifOperStatus': 'gauge',
            'ifSpeed': 'gauge',
            'ifHighSpeed': 'gauge',
            'ifDuplex': 'gauge',
            'ifHCInOctets': 'counter',
            'ifHCOutOctets': 'counter',
            'ifInUcastPkts': 'counter',
            'ifOutUcastPkts': 'counter',
            'ifInErrors': 'counter',
            'ifOutErrors': 'counter'
        }
        
        # Sort metrics to match SNMP exporter order (HC octets come before unicast packets in standard MIBs)
        metric_order = ['ifAdminStatus', 'ifOperStatus', 'ifSpeed', 'ifHighSpeed', 'ifDuplex', 'ifHCInOctets', 'ifHCOutOctets', 'ifInUcastPkts', 'ifOutUcastPkts', 'ifInErrors', 'ifOutErrors']
        
        for metric_name in metric_order:
            if metric_name in metrics and metrics[metric_name]:
                # Add HELP and TYPE headers
                output.append(f"# HELP {metric_name} {metric_descriptions.get(metric_name, 'No description available')}")
                output.append(f"# TYPE {metric_name} {metric_types.get(metric_name, 'gauge')}")
                
                # Add metrics with labels, sorted by ifIndex
                for _, labels, value in sorted(metrics[metric_name], key=lambda x: int(x[1]['ifIndex'])):
                    label_str = ','.join([f'{k}="{v}"' for k, v in sorted(labels.items())])
                    output.append(f"{metric_name}{{{label_str}}} {value}")
                
        return '\n'.join(output)


def main():
    parser = argparse.ArgumentParser(description="Export Sodola metrics to Prometheus format")
    parser.add_argument("--host", default="http://192.168.40.6", 
                       help="Sodola device URL (default: http://192.168.40.6)")
    parser.add_argument("--username", default="admin", 
                       help="Username (default: admin)")
    parser.add_argument("--password", default="admin", 
                       help="Password (default: admin)")
    parser.add_argument("--output", "-o", 
                       help="Output file (default: stdout)")
    parser.add_argument("--interval", type=int, 
                       help="Continuous monitoring interval in seconds")
    
    args = parser.parse_args()
    
    exporter = SodolaExporter(args.host, args.username, args.password)
    
    if args.interval:
        # Continuous monitoring mode
        print(f"Starting continuous monitoring every {args.interval} seconds...")
        while True:
            try:
                metrics = exporter.scrape_metrics()
                prometheus_output = exporter.format_prometheus_metrics(metrics)
                
                if args.output:
                    with open(args.output, 'w') as f:
                        f.write(prometheus_output)
                    print(f"Metrics written to {args.output}")
                else:
                    print(prometheus_output)
                    
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nStopping monitoring...")
                break
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(args.interval)
    else:
        # One-time scrape
        try:
            metrics = exporter.scrape_metrics()
            prometheus_output = exporter.format_prometheus_metrics(metrics)
            
            if args.output:
                with open(args.output, 'w') as f:
                    f.write(prometheus_output)
                print(f"Metrics written to {args.output}")
            else:
                print(prometheus_output)
                
        except Exception as e:
            print(f"Error: {e}")
            return 1
    
    return 0


if __name__ == "__main__":
    exit(main())