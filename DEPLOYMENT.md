# Despliegue en Railway

## Pasos para desplegar en Railway

### 1. Preparar el repositorio

El proyecto ya está configurado con:
- ✅ `Dockerfile` - Configuración de contenedor
- ✅ `railway.json` - Configuración de Railway
- ✅ `.dockerignore` - Archivos excluidos del build
- ✅ `backend/requirements.txt` - Dependencias Python

### 2. Variables de entorno requeridas en Railway

Configurar estas variables en Railway Dashboard:

```env
DATABASE_URL=postgresql://user:password@host:port/database
EMAIL_ADDRESS=vo2maxtnc@gmail.com
EMAIL_PASSWORD=gmgl ecro jvwj kuqw
ADMIN_EMAIL=codedevel.14@gmail.com
SECRET_KEY=tu_clave_secreta_aleatoria
PORT=8000
```

**Nota**: Railway automáticamente proporciona `DATABASE_URL` si conectas una base de datos PostgreSQL.

### 3. Base de datos PostgreSQL

Railway puede proporcionar PostgreSQL automáticamente:
1. En tu proyecto Railway, click en "+ New"
2. Selecciona "Database" → "PostgreSQL"
3. Railway creará automáticamente `DATABASE_URL`

### 4. Inicializar la base de datos

Después del primer deploy, ejecutar estos scripts (puedes hacerlo desde Railway CLI o conectándote a la BD):

```bash
# Crear tabla de administradores
python backend/create_admin_table.py

# Insertar datos de carreras de ejemplo
python backend/insert_data.py
```

O conectarte directamente a la BD de Railway y ejecutar:

```sql
-- Crear tabla de administradores
CREATE TABLE IF NOT EXISTS administradores (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(100),
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insertar admin por defecto (password: Passruner)
INSERT INTO administradores (email, password_hash, nombre)
VALUES (
    'admin@vo2max.com',
    '8a8b3c9f0c5e5f5e2e8c3f5e2e8c3f5e2e8c3f5e2e8c3f5e2e8c3f5e2e8c3f5e',
    'Administrador'
);
```

### 5. Desplegar en Railway

#### Opción A: Desde GitHub (Recomendado)

1. Sube el código a un repositorio GitHub
2. En Railway Dashboard:
   - Click en "+ New Project"
   - Selecciona "Deploy from GitHub repo"
   - Selecciona tu repositorio
   - Railway detectará automáticamente el Dockerfile

#### Opción B: Desde Railway CLI

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Inicializar proyecto
railway init

# Deploy
railway up
```

### 6. Configurar dominio

Railway te dará un dominio automático como: `tu-proyecto.up.railway.app`

Puedes configurar un dominio personalizado en Settings → Domains

### 7. Actualizar URLs en el frontend

Una vez desplegado, actualizar las URLs del API en los archivos HTML:

En `index.html`, `registro.html`, `validacion.html`, `admin/index.html`, `admin/login.html`:

Cambiar:
```javascript
const API_URL = `${window.location.protocol}//${window.location.hostname}:5000/api`;
```

Por:
```javascript
const API_URL = `https://tu-proyecto.up.railway.app/api`;
```

O mejor, usar detección automática:
```javascript
const API_URL = window.location.hostname === 'localhost' 
    ? `${window.location.protocol}//${window.location.hostname}:5000/api`
    : `${window.location.origin}/api`;
```

### 8. Verificar deployment

1. Acceder a tu URL de Railway
2. Verificar que carga la landing page
3. Probar el login admin: `admin@vo2max.com` / `Passruner`
4. Verificar que el panel de admin funciona

### 9. Monitoreo

Railway proporciona:
- Logs en tiempo real
- Métricas de uso
- Alertas de errores

## Estructura del proyecto en Railway

```
/app
├── backend/
│   ├── app.py (servidor Flask)
│   ├── requirements.txt
│   ├── comprobantes/ (archivos subidos)
│   └── *.py (scripts auxiliares)
├── admin/
│   ├── index.html
│   └── login.html
├── img/
│   └── logovo2max.png
├── index.html (landing page)
├── registro.html
├── validacion.html
└── ranking.html
```

## Solución de problemas

### Error: "Port already in use"
Railway asigna el puerto automáticamente via variable `PORT`. El código ya está configurado para esto.

### Error: "Database connection failed"
Verificar que `DATABASE_URL` esté correctamente configurado en las variables de entorno.

### Error: "Module not found"
Verificar que `requirements.txt` contenga todas las dependencias necesarias.

### Comprobantes no se ven
Verificar que la carpeta `backend/comprobantes/` tenga permisos de escritura.

## Comandos útiles

```bash
# Ver logs
railway logs

# Ver variables de entorno
railway variables

# Conectarse a la base de datos
railway connect postgres

# Reiniciar servicio
railway restart
```

## Costos

Railway ofrece:
- **Plan gratuito**: $5 de crédito mensual
- **Plan hobby**: $5/mes por servicio
- Cobra por uso (RAM, CPU, storage)

Este proyecto debería funcionar cómodamente en el plan gratuito con tráfico bajo-medio.
