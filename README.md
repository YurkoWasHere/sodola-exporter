# Sodola Prometheus Exporter

This tool scrapes metrics from a Sodola web interface and exports them in Prometheus format for monitoring and alerting.

## Features

- Authenticates with Sodola web interface using MD5 hash authentication
- **SNMP-Compatible Metrics**: Uses standard interface MIB naming conventions
- **Port Statistics Monitoring**: Detailed per-port metrics including:
  - Administrative status (ifAdminStatus) - enabled/disabled state
  - Operational status (ifOperStatus) - link up/down status
  - Unicast packet counters (ifInUcastPkts, ifOutUcastPkts)
  - Error counters (ifInErrors, ifOutErrors)
- **Labels**: Each metric includes interface labels (ifIndex, ifName, ifDescr, ifAlias)
- Outputs metrics in standard Prometheus exposition format compatible with SNMP exporters
- Supports both one-time scraping and continuous monitoring
- Configurable host, credentials, and output options

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Make scripts executable (if not already):
```bash
chmod +x sodola_exporter.py run_exporter.sh
```

## Usage

### Direct Python Script

```bash
# One-time scrape to stdout
python3 sodola_exporter.py

# One-time scrape to file
python3 sodola_exporter.py --output metrics.txt

# Continuous monitoring every 30 seconds
python3 sodola_exporter.py --interval 30

# Custom host and credentials
python3 sodola_exporter.py --host http://192.168.1.100 --username myuser --password mypass
```

### Using the Wrapper Script

```bash
# One-time scrape to stdout
./run_exporter.sh

# One-time scrape to file
./run_exporter.sh --output metrics.txt

# Continuous monitoring every 60 seconds to file
./run_exporter.sh --interval 60 --output /var/lib/prometheus/sodola_metrics.txt
```

## Configuration

### Command Line Options

- `--host`: Sodola device URL (default: http://192.168.40.6)
- `--username`: Username for authentication (default: admin)
- `--password`: Password for authentication (default: admin)
- `--output`: Output file path (default: stdout)
- `--interval`: Continuous monitoring interval in seconds (optional)

### Environment Variables

You can also set these environment variables instead of using command-line arguments:
- `SODOLA_HOST`
- `SODOLA_USERNAME`
- `SODOLA_PASSWORD`

## Prometheus Integration

### Method 1: HTTP Service (Recommended)

The recommended approach is to run the HTTP service that provides multi-target support like the SNMP exporter:

```bash
# Start the HTTP service
python3 sodola_http_exporter.py --port 9118

# Or install as a systemd service
sudo ./install.sh
```

#### Prometheus Configuration

Add this to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'sodola-switches'
    static_configs:
      - targets:
        - 192.168.40.6    # Sodola switch 1  
        - 192.168.40.4    # Sodola switch 2
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
        replacement: localhost:9118  # The Sodola exporter's hostname:port
    scrape_interval: 30s
```

#### File-based Service Discovery

```yaml
scrape_configs:
  - job_name: 'sodola-network'
    file_sd_configs:
      - files:
        - '/opt/prometheus/sodola.network.d/*.json'
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
        replacement: localhost:9118
```

### Method 2: File-based Collection

Configure the exporter to write metrics to a file that Prometheus can scrape using the textfile collector:

```bash
# Run continuously and write to textfile collector directory
./run_exporter.sh --interval 30 --output /var/lib/node_exporter/textfile_collector/sodola.prom
```

### Method 3: Scheduled Execution

Use cron to run the exporter periodically:

```bash
# Add to crontab to run every minute
* * * * * /path/to/sodola/run_exporter.sh --output /var/lib/prometheus/sodola.prom
```

## Example Output

The exporter provides SNMP-compatible metrics in standard Prometheus format:

```
# HELP ifAdminStatus The desired state of the interface (1=up, 2=down)
# TYPE ifAdminStatus gauge
ifAdminStatus{ifAlias="Port 1",ifDescr="Port 1",ifIndex="1",ifName="Port1"} 1.0
ifAdminStatus{ifAlias="Port 2",ifDescr="Port 2",ifIndex="2",ifName="Port2"} 1.0
ifAdminStatus{ifAlias="Port 8",ifDescr="Port 8",ifIndex="8",ifName="Port8"} 1.0

# HELP ifOperStatus The current operational state of the interface (1=up, 2=down)
# TYPE ifOperStatus gauge
ifOperStatus{ifAlias="Port 1",ifDescr="Port 1",ifIndex="1",ifName="Port1"} 1.0
ifOperStatus{ifAlias="Port 2",ifDescr="Port 2",ifIndex="2",ifName="Port2"} 1.0
ifOperStatus{ifAlias="Port 3",ifDescr="Port 3",ifIndex="3",ifName="Port3"} 2.0
ifOperStatus{ifAlias="Port 8",ifDescr="Port 8",ifIndex="8",ifName="Port8"} 1.0

# HELP ifInUcastPkts The number of packets delivered by this sub-layer to a higher sub-layer which were not addressed to a multicast or broadcast address
# TYPE ifInUcastPkts counter
ifInUcastPkts{ifAlias="Port 1",ifDescr="Port 1",ifIndex="1",ifName="Port1"} 111356.0
ifInUcastPkts{ifAlias="Port 2",ifDescr="Port 2",ifIndex="2",ifName="Port2"} 653554.0
ifInUcastPkts{ifAlias="Port 8",ifDescr="Port 8",ifIndex="8",ifName="Port8"} 127292.0

# HELP ifOutUcastPkts The total number of packets that higher-level protocols requested be transmitted which were not addressed to a multicast or broadcast address
# TYPE ifOutUcastPkts counter
ifOutUcastPkts{ifAlias="Port 1",ifDescr="Port 1",ifIndex="1",ifName="Port1"} 784698.0
ifOutUcastPkts{ifAlias="Port 2",ifDescr="Port 2",ifIndex="2",ifName="Port2"} 76919.0
ifOutUcastPkts{ifAlias="Port 8",ifDescr="Port 8",ifIndex="8",ifName="Port8"} 39015.0

# HELP ifSpeed An estimate of the interface current bandwidth in bits per second
# TYPE ifSpeed gauge
ifSpeed{ifAlias="Port 1",ifDescr="Port 1",ifIndex="1",ifName="Port1"} 2500000000.0
ifSpeed{ifAlias="Port 2",ifDescr="Port 2",ifIndex="2",ifName="Port2"} 1000000000.0
ifSpeed{ifAlias="Port 8",ifDescr="Port 8",ifIndex="8",ifName="Port8"} 1000000000.0

# HELP ifHighSpeed An estimate of the interface current bandwidth in units of 1,000,000 bits per second
# TYPE ifHighSpeed gauge
ifHighSpeed{ifAlias="Port 1",ifDescr="Port 1",ifIndex="1",ifName="Port1"} 2500.0
ifHighSpeed{ifAlias="Port 2",ifDescr="Port 2",ifIndex="2",ifName="Port2"} 1000.0
ifHighSpeed{ifAlias="Port 8",ifDescr="Port 8",ifIndex="8",ifName="Port8"} 1000.0
```

### Available Metrics

The exporter provides standard SNMP interface MIB metrics:

#### Interface Status Metrics
- `ifAdminStatus` - Administrative state of the interface (1=up, 2=down)
- `ifOperStatus` - Operational state of the interface (1=up, 2=down)

#### Interface Speed and Duplex Metrics
- `ifSpeed` - Interface bandwidth in bits per second
- `ifHighSpeed` - Interface bandwidth in units of 1,000,000 bits per second (for high-speed interfaces)
- `ifDuplex` - Duplex mode of the interface (2=half-duplex, 3=full-duplex)

#### Interface Traffic Counters
- `ifInUcastPkts` - Inbound unicast packets
- `ifOutUcastPkts` - Outbound unicast packets
- `ifInErrors` - Inbound packets with errors
- `ifOutErrors` - Outbound packets with errors

#### Interface Labels
Each metric includes the following labels for identification:
- `ifIndex` - Interface index number
- `ifName` - Interface name (e.g., "Port1")
- `ifDescr` - Interface description (e.g., "Port 1")  
- `ifAlias` - Interface alias (e.g., "Port 1")

This format is fully compatible with existing SNMP monitoring setups and Prometheus dashboards designed for network interface monitoring.

## Troubleshooting

### Authentication Issues
- Verify the host URL is correct and accessible
- Check username/password credentials
- Ensure the device is not blocking requests

### No Metrics Found
- The tool automatically discovers pages and extracts metrics
- If no metrics are found, the HTML structure may be different than expected
- Check the verbose output to see which pages were discovered

### Connection Issues
- Verify network connectivity to the device
- Check if the device requires HTTPS
- Ensure firewall rules allow access

## Development

The tool is designed to be easily extensible:

- Modify `_extract_metrics_from_html()` to add new metric extraction patterns
- Add new pages to `discover_pages()` for specific device types
- Customize `_sanitize_metric_name()` for different naming conventions

## License

This tool is provided as-is for monitoring purposes.