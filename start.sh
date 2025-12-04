#!/bin/bash

# Script para iniciar Backend y Frontend de VO2Max

echo "🚀 Iniciando servicios de VO2Max..."

# Verificar que el entorno virtual existe
if [ ! -d "/root/projects/vo2rank/.venv" ]; then
    echo "❌ Error: Entorno virtual no encontrado"
    exit 1
fi

# Detener procesos anteriores si existen
echo "🧹 Limpiando procesos anteriores..."
pkill -f "python.*app.py" 2>/dev/null
pkill -f "http.server 8000" 2>/dev/null
sleep 2

# Iniciar Backend (Puerto 5000)
echo "📡 Iniciando Backend en puerto 5000..."
cd /root/projects/vo2rank/backend
/root/projects/vo2rank/.venv/bin/python app.py > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Esperar a que el backend inicie
sleep 3

# Verificar que el backend está corriendo
if lsof -i :5000 > /dev/null 2>&1; then
    echo "   ✅ Backend corriendo en http://localhost:5000"
else
    echo "   ❌ Error al iniciar Backend"
    cat /tmp/backend.log
    exit 1
fi

# Iniciar Frontend (Puerto 8000)
echo "🌐 Iniciando Frontend en puerto 8000..."
cd /root/projects/vo2rank
/root/projects/vo2rank/.venv/bin/python -m http.server 8000 > /tmp/http_server.log 2>&1 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

# Esperar a que el frontend inicie
sleep 2

# Verificar que el frontend está corriendo
if lsof -i :8000 > /dev/null 2>&1; then
    echo "   ✅ Frontend corriendo en http://localhost:8000"
else
    echo "   ❌ Error al iniciar Frontend"
    cat /tmp/http_server.log
    exit 1
fi

echo ""
echo "✅ Todos los servicios están corriendo"
echo ""
echo "📍 URLs:"
echo "   - Landing Page: http://localhost:8000/index.html"
echo "   - Registro:     http://localhost:8000/registro.html"
echo "   - Admin Panel:  http://localhost:8000/admin/index.html"
echo "   - API Backend:  http://localhost:5000/api"
echo ""
echo "📋 Logs:"
echo "   - Backend:  tail -f /tmp/backend.log"
echo "   - Frontend: tail -f /tmp/http_server.log"
echo ""
echo "🛑 Para detener: ./stop.sh"
