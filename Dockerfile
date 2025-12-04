FROM python:3.10-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio para requirements si no existe
RUN mkdir -p backend

# Copiar requirements del backend
COPY backend/requirements.txt ./backend/

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copiar todo el código de la aplicación
COPY backend/ ./backend/
COPY *.html ./
COPY img/ ./img/
COPY admin/ ./admin/

# Crear directorio para comprobantes
RUN mkdir -p backend/comprobantes

# Exponer puerto (Railway usa la variable PORT)
EXPOSE 8000

# Ejecutar con gunicorn para producción
CMD gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 backend.app:app
