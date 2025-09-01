#!/bin/bash

# Sodola Prometheus Exporter Runner Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPORTER_SCRIPT="$SCRIPT_DIR/sodola_exporter.py"

# Default values
HOST="http://192.168.40.6"
USERNAME="admin"
PASSWORD="admin"
INTERVAL=""
OUTPUT=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --username)
            USERNAME="$2"
            shift 2
            ;;
        --password)
            PASSWORD="$2"
            shift 2
            ;;
        --interval)
            INTERVAL="$2"
            shift 2
            ;;
        --output|-o)
            OUTPUT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --host HOST          Sodola device URL (default: http://192.168.40.6)"
            echo "  --username USERNAME  Username (default: admin)"
            echo "  --password PASSWORD  Password (default: admin)"
            echo "  --output, -o FILE    Output file (default: stdout)"
            echo "  --interval SECONDS   Continuous monitoring interval"
            echo "  --help, -h          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # One-time scrape to stdout"
            echo "  $0 --output metrics.txt               # One-time scrape to file"
            echo "  $0 --interval 30                     # Continuous monitoring every 30 seconds"
            echo "  $0 --interval 60 --output metrics.txt # Continuous to file"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build command
CMD="python3 '$EXPORTER_SCRIPT' --host '$HOST' --username '$USERNAME' --password '$PASSWORD'"

if [[ -n "$INTERVAL" ]]; then
    CMD="$CMD --interval '$INTERVAL'"
fi

if [[ -n "$OUTPUT" ]]; then
    CMD="$CMD --output '$OUTPUT'"
fi

# Execute the command
eval $CMD