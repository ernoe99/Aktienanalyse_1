#!/bin/bash

# Quick Deployment Script für Simple Stock Analyzer
# Verwendung: ./deploy.sh [commit-message]

set -e  # Bei Fehler abbrechen

echo "🚀 Simple Stock Analyzer - Quick Deploy Script"
echo "=============================================="
echo ""

# Farben für Output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Commit Message
if [ -z "$1" ]; then
    COMMIT_MSG="Update: Bug fixes and improvements"
else
    COMMIT_MSG="$1"
fi

echo "📝 Commit Message: $COMMIT_MSG"
echo ""

# Schritt 1: Git Status prüfen
echo "📊 Checking Git status..."
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Kein Git Repository gefunden!${NC}"
    echo "Initialisiere Git Repository..."
    git init
    echo -e "${GREEN}✅ Git Repository initialisiert${NC}"
fi

# Schritt 2: Remote überprüfen
echo ""
echo "🔗 Checking remote repository..."
if ! git remote | grep -q "origin"; then
    echo -e "${YELLOW}⚠️  Kein Remote 'origin' gefunden${NC}"
    echo "Bitte Remote hinzufügen mit:"
    echo "git remote add origin https://github.com/USERNAME/REPO_NAME.git"
    exit 1
fi
echo -e "${GREEN}✅ Remote repository OK${NC}"

# Schritt 3: Änderungen prüfen
echo ""
echo "🔍 Checking for changes..."
if [ -z "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}⚠️  Keine Änderungen zum Committen${NC}"
    read -p "Trotzdem pushen? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Abgebrochen."
        exit 0
    fi
else
    echo -e "${GREEN}✅ Änderungen gefunden${NC}"
    git status --short
fi

# Schritt 4: Add, Commit, Push
echo ""
echo "📦 Adding files..."
git add Simple_stock_analyzer_go.py requirements.txt README.md
echo -e "${GREEN}✅ Files added${NC}"

echo ""
echo "💾 Committing changes..."
if ! git diff-index --quiet HEAD --; then
    git commit -m "$COMMIT_MSG"
    echo -e "${GREEN}✅ Changes committed${NC}"
else
    echo -e "${YELLOW}⚠️  Nichts zum Committen${NC}"
fi

echo ""
echo "🚀 Pushing to GitHub..."
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
git push origin "$CURRENT_BRANCH"
echo -e "${GREEN}✅ Pushed to GitHub successfully!${NC}"

# Schritt 5: Streamlit Cloud Info
echo ""
echo "=============================================="
echo -e "${GREEN}✅ Deployment vorbereitet!${NC}"
echo ""
echo "Nächste Schritte:"
echo "1. Öffne https://share.streamlit.io"
echo "2. Wähle dein Repository"
echo "3. Setze Main file: Simple_stock_analyzer_go.py"
echo "4. Klicke auf Deploy"
echo ""
echo "Oder für automatisches Öffnen:"
echo -e "${YELLOW}open https://share.streamlit.io${NC}"
echo ""

# Optional: Streamlit Cloud automatisch öffnen
read -p "Streamlit Cloud jetzt öffnen? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v open &> /dev/null; then
        open https://share.streamlit.io
    elif command -v xdg-open &> /dev/null; then
        xdg-open https://share.streamlit.io
    elif command -v start &> /dev/null; then
        start https://share.streamlit.io
    else
        echo "Bitte öffne manuell: https://share.streamlit.io"
    fi
fi

echo ""
echo "🎉 Fertig!"
