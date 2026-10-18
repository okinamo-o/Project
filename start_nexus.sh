#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

mkdir -p "$DIR/logs"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}        NEXUS AI DIGITAL TWIN - AUTOMATED LINUX LAUNCHER              ${NC}"
echo -e "${BLUE}======================================================================${NC}"

# 1. Locate Python environment
if [ -f "$DIR/.venv/bin/python" ]; then
    PYTHON_EXE="$DIR/.venv/bin/python"
elif [ -f "$DIR/backend/venv/bin/python" ]; then
    PYTHON_EXE="$DIR/backend/venv/bin/python"
else
    PYTHON_EXE="python3"
fi
echo -e "[*] Environnement Python : ${GREEN}$PYTHON_EXE${NC}"

# 2. Start Docker containers (PostgreSQL & Mosquitto MQTT)
if command -v docker &>/dev/null && [ -f "docker-compose.yml" ]; then
    echo -e "[*] Demarrage des conteneurs Docker (Postgres, Mosquitto MQTT)..."
    docker compose up -d postgres mosquitto >/dev/null 2>&1 || true
    echo -e "  [${GREEN}OK${NC}] Services Docker actifs"
fi

# 3. Clean up any existing instances on ports 8000 and 3000
echo -e "[*] Nettoyage des ports 8000 et 3000..."
fuser -k 8000/tcp >/dev/null 2>&1 || true
fuser -k 3000/tcp >/dev/null 2>&1 || true
sleep 1

# Setup process cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}[*] Arret des services NEXUS...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    fuser -k 8000/tcp >/dev/null 2>&1 || true
    fuser -k 3000/tcp >/dev/null 2>&1 || true
    echo -e "${GREEN}[OK] Services NEXUS arretes avec succes.${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 4. Start Backend Server
echo -e "[*] Lancement du Backend API & Subsystems IA (FastAPI)..."
PYTHONPATH="$DIR" "$PYTHON_EXE" -m backend.app.main > "$DIR/logs/backend.log" 2>&1 &
BACKEND_PID=$!

# Wait for Backend to become healthy
echo -e "[*] En attente de la disponibilite du Backend..."
BACKEND_READY=0
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/api/health 2>/dev/null | grep -q '"status":"healthy"'; then
        BACKEND_READY=1
        echo -e "  [${GREEN}OK${NC}] Backend connecte et sain (http://127.0.0.1:8000) !"
        break
    fi
    sleep 0.5
done

if [ $BACKEND_READY -ne 1 ]; then
    echo -e "  [${RED}ERREUR${NC}] Le backend n'a pas repondu a temps. Verifiez logs/backend.log :"
    tail -n 20 "$DIR/logs/backend.log"
    exit 1
fi

# 5. Start Frontend Server
echo -e "[*] Lancement du Frontend 3D Twin (Next.js)..."
cd "$DIR/frontend"
npm run dev > "$DIR/logs/frontend.log" 2>&1 &
FRONTEND_PID=$!
cd "$DIR"

# Wait for Frontend to become ready
echo -e "[*] En attente du demarrage du Frontend..."
for i in {1..30}; do
    if curl -s http://localhost:3000 2>/dev/null | grep -q "html"; then
        echo -e "  [${GREEN}OK${NC}] Frontend 3D pret sur http://localhost:3000 !"
        break
    fi
    sleep 0.5
done

echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}  NEXUS EST PLEINEMENT ACTIF ET OPERATIONNEL !                         ${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo -e "  💻 Dashboard 3D Twin    : ${BLUE}http://localhost:3000${NC}"
echo -e "  📚 Documentation API    : ${BLUE}http://127.0.0.1:8000/docs${NC}"
echo -e "  🩺 Verification Sante   : ${BLUE}http://127.0.0.1:8000/api/health${NC}"
echo -e "  📋 Logs Backend         : ${YELLOW}tail -f logs/backend.log${NC}"
echo -e "  📋 Logs Frontend        : ${YELLOW}tail -f logs/frontend.log${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo -e "Appuyez sur ${RED}Ctrl+C${NC} pour arreter l'ensemble des services."
echo ""

# Open Browser
if command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:3000" >/dev/null 2>&1 &
fi

# Follow backend logs or keep alive
wait
