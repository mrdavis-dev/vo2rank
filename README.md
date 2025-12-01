# VO2RANK - Endurance Run Results

Aplicación web para visualizar los resultados oficiales de la carrera Endurance Run por categoría.

## Características

- Tabla interactiva de resultados por distancia (5K, 10K, 21K)
- Diseño responsivo con Tailwind CSS
- Visualización de posición general, dorsal, nombre, categoría y tiempo
- Interfaz amigable con pestañas para filtrar por distancia

## Requisitos

- Docker
- O Python 3.11+ (sin Docker)

## Uso con Docker

### Construir la imagen

```bash
docker build -t vo2rank-server .
```

### Ejecutar el contenedor

```bash
docker run -p 8000:8000 vo2rank-server
```

Luego abre tu navegador en `http://localhost:8000`

## Uso sin Docker

Si prefieres ejecutar directamente con Python:

```bash
python -m http.server 8000 --directory .
```

Accede a `http://localhost:8000`

## Estructura del Proyecto

```
vo2rank/
├── index.html       # Página principal con tabla de resultados
├── Dockerfile       # Configuración para Docker
└── README.md        # Este archivo
```

## Contenido

La aplicación contiene resultados de tres categorías de distancia:

- **5K**: Resultados de 5 kilómetros
- **10K**: Resultados de 10 kilómetros  
- **21K**: Resultados de 21 kilómetros (media maratón)

Cada entrada incluye:
- Posición general
- Número de dorsal
- Nombre del participante
- Categoría
- Posición en categoría
- Tiempo de carrera

## Tecnologías

- HTML5
- CSS (Tailwind CSS)
- JavaScript vanilla
- Python http.server

## Puerto

Por defecto, el servidor se ejecuta en el **puerto 8000**.
