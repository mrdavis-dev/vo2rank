FROM python:3.11-slim

WORKDIR /app

# Copiar todos los archivos (HTML, CSS, JS y assets)
COPY index.html /app/
COPY img/ /app/img/

# Crear un servidor HTTP simple con Python
# El servidor escuchará en el puerto 8000
CMD ["python", "-m", "http.server", "8000", "--directory", "/app"]

EXPOSE 8000
