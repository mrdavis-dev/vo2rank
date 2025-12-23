# VO2RANK - Endurance Run Registration & Results

Aplicación web completa para gestión de registros, validación de pagos y visualización de resultados de carreras. Incluye panel administrativo para crear y gestionar rankings.

## Características

- 🏃 Registro de participantes
- 💳 Validación de comprobantes de pago
- 📊 Gestión de rankings (manual o desde PDF)
- 📱 Visualización responsiva de resultados
- 🔐 Panel administrativo con autenticación
- 📈 Estadísticas por categoría
- 🎖️ Medallas para posiciones (🥇🥈🥉)

## Requisitos

- Python 3.11+
- PostgreSQL 12+
- Node.js (opcional, para desarrollo frontend)

## Instalación

### 1. Clonar y configurar el proyecto

```bash
cd /root/projects/vo2rank
```

### 2. Crear entorno virtual y instalar dependencias

```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 3. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto:

```env
DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/vo2rank
SECRET_KEY=tu-clave-secreta-aqui
RESEND_API_KEY=tu-api-key-resend
JWT_SECRET=tu-jwt-secret
```

### 4. Configurar base de datos

Asegúrate de que PostgreSQL está corriendo y crea la base de datos:

```bash
psql -U postgres -c "CREATE DATABASE vo2rank;"
```

## Ejecución Rápida

### Opción 1: Dos terminales (Recomendado para desarrollo)

**Terminal 1 - Backend Flask:**
```bash
cd /root/projects/vo2rank
source .venv/bin/activate
python backend/app.py
```
Accede a: `http://localhost:5000`

**Terminal 2 - Frontend:**
```bash
cd /root/projects/vo2rank
python -m http.server 8000 --directory .
```
Accede a: `http://localhost:8000`

### Opción 2: Un comando (Background)

```bash
cd /root/projects/vo2rank
source .venv/bin/activate

# Levantar Flask en background
nohup python backend/app.py > backend.log 2>&1 &

# Levantar servidor HTTP
python -m http.server 8000 --directory .
```

### Opción 3: Con Script automatizado

```bash
#!/bin/bash
cd /root/projects/vo2rank
source .venv/bin/activate

# Terminal 1: Flask
gnome-terminal -- bash -c "cd /root/projects/vo2rank && source .venv/bin/activate && python backend/app.py"

# Terminal 2: Frontend
gnome-terminal -- bash -c "cd /root/projects/vo2rank && python -m http.server 8000 --directory ."

sleep 2
echo "✅ Backend en http://localhost:5000"
echo "✅ Frontend en http://localhost:8000"
```

### URLs de acceso

| Componente | URL | Puerto |
|-----------|-----|--------|
| **Frontend (Público)** | http://localhost:8000 | 8000 |
| **Panel Admin** | http://localhost:8000/admin | 8000 |
| **Backend API** | http://localhost:5000/api | 5000 |

## Uso con Docker (Completo)

### Construir la imagen

```bash
docker build -t vo2rank-server .
```

### Ejecutar el contenedor

```bash
docker run -p 5000:5000 -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/vo2rank \
  -e SECRET_KEY=tu-clave \
  -e RESEND_API_KEY=tu-key \
  vo2rank-server
```

## Estructura del Proyecto

```
vo2rank/
├── backend/
│   ├── app.py                    # Aplicación Flask principal
│   ├── requirements.txt          # Dependencias Python
│   └── __pycache__/
├── admin/
│   ├── index.html                # Panel administrativo
│   ├── login.html                # Login admin
│   ├── registro-rapido.html      # Registro rápido
│   ├── index_old.html            # Backup
│   └── ...
├── img/                          # Imágenes y assets
├── index.html                    # Página principal (pública)
├── ranking.html                  # Página de rankings
├── validacion.html               # Validación de comprobantes
├── registro.html                 # Formulario de registro
├── Dockerfile                    # Configuración Docker
├── docker-compose.yml            # Orquestación (opcional)
├── .env.example                  # Variables de entorno ejemplo
└── README.md                     # Este archivo
```

## Endpoints Principales

### API Pública
- `GET /` - Página principal
- `GET /api/carreras` - Lista de carreras
- `GET /api/rankings` - Lista de rankings
- `GET /api/rankings/<id>` - Detalle de un ranking

### API Admin (requiere autenticación)
- `POST /api/rankings/crear` - Crear ranking manual
- `POST /api/rankings/crear-desde-pdf` - Crear ranking desde PDF
- `PUT /api/rankings/<id>` - Actualizar ranking
- `DELETE /api/rankings/<id>` - Eliminar ranking

### Páginas Admin
- `/admin/` - Panel principal (requiere login)
- `/admin/login.html` - Inicio de sesión
- `/admin/rankings.html` - Gestión de rankings

## Tecnologías

### Backend
- Flask 2.3.2 - Web framework
- PostgreSQL - Base de datos
- psycopg2 - Driver PostgreSQL
- pdfplumber 0.10.3 - Extracción de tablas de PDF
- Pillow 10.1.0 - Procesamiento de imágenes
- python-dotenv - Gestión de variables de entorno
- resend - Servicio de email

### Frontend
- HTML5
- CSS (Tailwind CSS)
- JavaScript vanilla
- Font Awesome 6.0.0 - Iconos

## Puertos

- **Backend**: 5000 (Flask)
- **Frontend**: 8000 (HTTP simple) o 8080 (Docker)
- **Base de datos**: 5432 (PostgreSQL)

## Troubleshooting

### Error: "net::ERR_CONNECTION_REFUSED"
- Verifica que el backend está corriendo: `python backend/app.py`
- Revisa el puerto 5000 no esté en uso: `lsof -i :5000`

### Error: "Base de datos no encontrada"
- Asegúrate de que PostgreSQL está corriendo
- Verifica la variable `DATABASE_URL` en `.env`
- Crea la base de datos si no existe

### Error: "No module named 'pdfplumber'"
- Reinstala las dependencias: `pip install -r backend/requirements.txt`

## Licencia

Privada - VO2Max Running
