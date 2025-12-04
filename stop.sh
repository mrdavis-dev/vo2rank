#!/bin/bash

# Script para detener Backend y Frontend de VO2Max

echo "🛑 Deteniendo servicios de VO2Max..."

# Detener Backend
echo "   Deteniendo Backend (puerto 5000)..."
pkill -f "python.*app.py"
if [ $? -eq 0 ]; then
    echo "   ✅ Backend detenido"
else
    echo "   ⚠️  No se encontró proceso del Backend"
fi

# Detener Frontend
echo "   Deteniendo Frontend (puerto 8000)..."
pkill -f "http.server 8000"
if [ $? -eq 0 ]; then
    echo "   ✅ Frontend detenido"
else
    echo "   ⚠️  No se encontró proceso del Frontend"
fi

# Esperar un momento
sleep 1

# Verificar que los puertos están libres
if lsof -i :5000 > /dev/null 2>&1; then
    echo "   ⚠️  Puerto 5000 aún en uso, forzando cierre..."
    lsof -i :5000 -t | xargs kill -9 2>/dev/null
fi

if lsof -i :8000 > /dev/null 2>&1; then
    echo "   ⚠️  Puerto 8000 aún en uso, forzando cierre..."
    lsof -i :8000 -t | xargs kill -9 2>/dev/null
fi

echo ""
echo "✅ Todos los servicios han sido detenidos"
