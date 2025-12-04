# vo2rank

Sistema de gestión de carreras y registros para VO2Max Running Club.

## Requisitos

- Python 3.8+
- PostgreSQL (Railway)
- Entorno virtual de Python

## Configuración

1. Activar el entorno virtual:
```bash
source /root/projects/vo2rank/.venv/bin/activate
```

2. Configurar variables de entorno en `backend/.env`:
```
DATABASE_URL=postgresql://postgres:cBOYRtwEhqPHKOUJXmtFhJWVCNaHezGg@switchback.proxy.rlwy.net:41713/railway
EMAIL_ADDRESS=vo2maxtnc@gmail.com
EMAIL_PASSWORD=<app_password>
ADMIN_EMAIL=codedevel.14@gmail.com
```

## Iniciar el Sistema

### Backend (Puerto 5000)

```bash
cd /root/projects/vo2rank/backend
python app.py
```

O en background:
```bash
cd /root/projects/vo2rank/backend && python app.py > /tmp/backend.log 2>&1 &
```

### Frontend (Puerto 8000)

```bash
cd /root/projects/vo2rank
python -m http.server 8000
```

O en background:
```bash
cd /root/projects/vo2rank && python -m http.server 8000 > /tmp/http_server.log 2>&1 &
```

## Acceso

- **Landing Page**: http://localhost:8000/index.html
- **Registro**: http://localhost:8000/registro.html
- **Admin Panel**: http://localhost:8000/admin/index.html
- **API Backend**: http://localhost:5000/api

## Comandos Útiles

### Verificar servicios activos
```bash
# Ver procesos de Python
ps aux | grep python

# Ver puertos en uso
lsof -i :5000
lsof -i :8000
```

### Detener servicios
```bash
# Matar backend
pkill -f "python.*app.py"

# Matar servidor HTTP
pkill -f "http.server"
```

### Crear tabla de registros
```bash
cd /root/projects/vo2rank/backend
python create_registros_table.py
```

### Insertar datos de prueba
```bash
cd /root/projects/vo2rank/backend
python insert_data.py
```

## Estructura del Proyecto

```
vo2rank/
├── backend/
│   ├── app.py                      # API Flask principal
│   ├── .env                        # Variables de entorno
│   ├── create_registros_table.py   # Script para crear tabla
│   └── insert_data.py              # Script para datos de prueba
├── index.html                      # Landing page
├── registro.html                   # Formulario de registro
├── validacion.html                 # Subir comprobante de pago
├── ranking.html                    # Resultados de carreras
└── admin/
    ├── index.html                  # Panel de administración
    └── login.html                  # Login admin
```

