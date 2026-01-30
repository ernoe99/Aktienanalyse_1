#!/bin/bash
#
# start_analyzer.sh - Startskript für Stock Analyzer
# Verwendung: ./start_analyzer.sh [port]
#

# Konfiguration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PORT="${1:-8501}"

# Farben für Ausgabe
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}   Stock Analyzer - Startskript${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""

# Prüfen ob Python installiert ist
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 ist nicht installiert!${NC}"
    echo "Bitte installieren mit: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Prüfen ob virtuelle Umgebung existiert
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚙️  Erstelle virtuelle Umgebung...${NC}"
    python3 -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Fehler beim Erstellen der virtuellen Umgebung!${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Virtuelle Umgebung erstellt${NC}"
fi

# Virtuelle Umgebung aktivieren
echo -e "${YELLOW}⚙️  Aktiviere virtuelle Umgebung...${NC}"
source "$VENV_DIR/bin/activate"

# Prüfen ob Abhängigkeiten installiert sind
if ! python -c "import streamlit" 2>/dev/null; then
    echo -e "${YELLOW}⚙️  Installiere Abhängigkeiten...${NC}"
    pip install --upgrade pip -q
    pip install -r "$SCRIPT_DIR/requirements.txt"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Fehler beim Installieren der Abhängigkeiten!${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Abhängigkeiten installiert${NC}"
fi

# Starte Streamlit
echo ""
echo -e "${GREEN}🚀 Starte Stock Analyzer auf Port $PORT...${NC}"
echo -e "${YELLOW}   Öffne im Browser: http://localhost:$PORT${NC}"
echo -e "${YELLOW}   Beenden mit: Ctrl+C${NC}"
echo ""

streamlit run "$SCRIPT_DIR/stock_analyzer.py" \
    --server.port "$PORT" \
    --server.headless true \
    --browser.gatherUsageStats false

# Hinweis: Browser manuell öffnen unter http://localhost:$PORT
