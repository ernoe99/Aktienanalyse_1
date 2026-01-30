# 🐧 Vollständige Installationsanleitung für Ubuntu

## Voraussetzungen

- Ubuntu 20.04, 22.04 oder 24.04
- Internetverbindung
- Terminal-Zugang

---

## Schritt 1: Python prüfen und installieren

```bash
# Python-Version prüfen (mindestens 3.8 erforderlich)
python3 --version

# Falls Python nicht installiert ist:
sudo apt update
sudo apt install python3 python3-pip python3-venv -y
```

---

## Schritt 2: Projektverzeichnis erstellen

```bash
# Verzeichnis erstellen
mkdir -p ~/stock_analyzer
cd ~/stock_analyzer
```

---

## Schritt 3: Virtuelle Umgebung erstellen (empfohlen)

```bash
# Virtuelle Umgebung erstellen
python3 -m venv venv

# Virtuelle Umgebung aktivieren
source venv/bin/activate

# Der Prompt sollte jetzt (venv) anzeigen
```

---

## Schritt 4: Dateien erstellen

### Option A: Dateien manuell erstellen

```bash
# requirements.txt erstellen
cat > requirements.txt << 'EOF'
streamlit>=1.28.0
yfinance>=0.2.31
pandas>=2.0.0
numpy>=1.24.0
plotly>=5.18.0
EOF

# stock_analyzer.py erstellen (aus dem Download kopieren)
# Oder mit nano/vim bearbeiten:
nano stock_analyzer.py
# Dann den Python-Code einfügen und speichern (Ctrl+O, Enter, Ctrl+X)
```

### Option B: Dateien aus Download kopieren

```bash
# Falls Sie die Dateien heruntergeladen haben:
cp ~/Downloads/stock_analyzer.py ~/stock_analyzer/
cp ~/Downloads/requirements.txt ~/stock_analyzer/
```

---

## Schritt 5: Abhängigkeiten installieren

```bash
# Sicherstellen, dass Sie im richtigen Verzeichnis sind
cd ~/stock_analyzer

# Virtuelle Umgebung aktiviert? Falls nicht:
source venv/bin/activate

# Abhängigkeiten installieren
pip install --upgrade pip
pip install -r requirements.txt
```

**Erwartete Ausgabe:**
```
Successfully installed streamlit-1.xx.x yfinance-0.2.xx pandas-2.x.x ...
```

---

## Schritt 6: Anwendung starten

```bash
# Streamlit-App starten
streamlit run stock_analyzer.py
```

**Erwartete Ausgabe:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

---

## Schritt 7: Im Browser öffnen

Der Browser sollte automatisch öffnen. Falls nicht:

```bash
# Manuell öffnen (Ubuntu Desktop)
xdg-open http://localhost:8501

# Oder einfach im Browser eingeben:
# http://localhost:8501
```

---

## 🔄 Späterer Start (Kurzversion)

Nach der Installation brauchen Sie nur noch:

```bash
cd ~/stock_analyzer
source venv/bin/activate
streamlit run stock_analyzer.py
```

---

## ⏹️ Anwendung beenden

- **Im Terminal:** `Ctrl + C`
- **Virtuelle Umgebung verlassen:** `deactivate`

---

## 🛠️ Fehlerbehebung

### Problem: "streamlit: command not found"
```bash
# Virtuelle Umgebung aktivieren
source venv/bin/activate
# Oder global installieren:
pip3 install streamlit
```

### Problem: "ModuleNotFoundError"
```bash
# Alle Pakete neu installieren
pip install -r requirements.txt --force-reinstall
```

### Problem: Port 8501 bereits belegt
```bash
# Anderen Port verwenden
streamlit run stock_analyzer.py --server.port 8502
```

### Problem: Kein Display (Server ohne GUI)
```bash
# Headless-Modus
streamlit run stock_analyzer.py --server.headless true
# Dann von anderem Rechner zugreifen via Network URL
```

---

## 📝 Nützliche Streamlit-Optionen

```bash
# Anderen Port verwenden
streamlit run stock_analyzer.py --server.port 8080

# Von anderen Geräten im Netzwerk zugreifen erlauben
streamlit run stock_analyzer.py --server.address 0.0.0.0

# Browser nicht automatisch öffnen
streamlit run stock_analyzer.py --server.headless true

# Debug-Modus
streamlit run stock_analyzer.py --logger.level debug

# Alle Optionen kombinieren
streamlit run stock_analyzer.py \
    --server.port 8080 \
    --server.address 0.0.0.0 \
    --server.headless true
```

---

## 🖥️ Desktop-Shortcut erstellen (optional)

```bash
# Desktop-Eintrag erstellen
cat > ~/.local/share/applications/stock-analyzer.desktop << 'EOF'
[Desktop Entry]
Name=Stock Analyzer
Comment=Aktienanalyse für Optionenstrategie
Exec=bash -c "cd ~/stock_analyzer && source venv/bin/activate && streamlit run stock_analyzer.py"
Icon=utilities-system-monitor
Terminal=true
Type=Application
Categories=Finance;
EOF

# Desktop-Datei ausführbar machen
chmod +x ~/.local/share/applications/stock-analyzer.desktop
```

---

## 🔄 Updates installieren

```bash
cd ~/stock_analyzer
source venv/bin/activate
pip install --upgrade -r requirements.txt
```
