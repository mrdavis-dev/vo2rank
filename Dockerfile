FROM python:3.11-slim

WORKDIR /app

# Copiar el archivo HTML
COPY index.html /app/index.html

# Crear un servidor HTTP simple con Python
# El servidor escuchará en el puerto 8000
CMD ["python", "-m", "http.server", "8000", "--directory", "/app"]

EXPOSE 8000
