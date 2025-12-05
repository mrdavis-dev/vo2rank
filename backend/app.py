import os
from flask import Flask, jsonify, request, session, send_from_directory, Response
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import uuid
import resend
from werkzeug.utils import secure_filename
from datetime import datetime
import secrets
import hashlib
from PIL import Image
import io

load_dotenv()

# Configurar Resend API Key
resend.api_key = os.getenv('API_KEY_RESEND')

app = Flask(__name__, static_folder='..', static_url_path='')
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Configuración de sesión para producción
app.config['SESSION_COOKIE_SECURE'] = True  # Solo HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No accesible desde JavaScript
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Protección CSRF
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 horas
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# Tokens válidos en memoria (en producción usarías Redis o base de datos)
valid_tokens = {}

def generar_token_admin(admin_id, admin_email):
    """Genera un token único para el administrador"""
    token = secrets.token_urlsafe(32)
    valid_tokens[token] = {
        'admin_id': admin_id,
        'admin_email': admin_email,
        'created': datetime.now()
    }
    return token

def verificar_token(token):
    """Verifica si un token es válido y devuelve los datos del admin"""
    if token in valid_tokens:
        # Verificar que no haya expirado (24 horas)
        datos = valid_tokens[token]
        tiempo_transcurrido = (datetime.now() - datos['created']).total_seconds()
        if tiempo_transcurrido < 86400:  # 24 horas
            return datos
        else:
            # Token expirado, eliminarlo
            del valid_tokens[token]
    return None

CORS(app, supports_credentials=True)

# Configuración de carpetas
# NOTA: En Railway, los archivos se guardan en el sistema de archivos efímero del contenedor
# Si el contenedor se reinicia, los archivos se perderán
# Para producción, considera usar: Railway Volumes, AWS S3, Cloudinary, etc.
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'comprobantes')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"✓ Directorio de comprobantes creado: {UPLOAD_FOLDER}")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max

# Configuración de correo
EMAIL_FROM = 'VO2Max Running <noreply@paylert.app>'  # Dominio verificado en Resend
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'codedevel.14@gmail.com')

# Configuración de la base de datos PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:cBOYRtwEhqPHKOUJXmtFhJWVCNaHezGg@switchback.proxy.rlwy.net:41713/railway')

def get_db_connection():
    """Crea una conexión a la base de datos PostgreSQL"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error conectando a la base de datos: {e}")
        return None

def send_email(to_email, subject, body):
    """Envía un correo electrónico usando Resend"""
    try:
        params = {
            "from": EMAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "html": body,
        }
        
        email = resend.Emails.send(params)
        email_id = email.get('id', 'N/A') if isinstance(email, dict) else 'N/A'
        print(f"✓ Correo enviado exitosamente a {to_email} (ID: {email_id})")
        return True
    except Exception as e:
        print(f"✗ Error enviando correo a {to_email}: {str(e)}")
        print(f"   Tipo de error: {type(e).__name__}")
        # Con el dominio de prueba de Resend, solo se pueden enviar correos a direcciones verificadas
        # Para enviar a cualquier dirección, necesitas verificar tu propio dominio en Resend
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def require_auth(f):
    """Decorador para requerir autenticación"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar token en header Authorization o en parámetro query
        token = None
        
        # Buscar en header Authorization
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]  # Quitar "Bearer "
        
        # Si no hay en header, buscar en parámetro query
        if not token:
            token = request.args.get('token')
        
        # Si no hay token, verificar sesión antigua (para backwards compatibility)
        if not token and 'admin_logged_in' in session:
            return f(*args, **kwargs)
        
        # Verificar token
        if token:
            admin_data = verificar_token(token)
            if admin_data:
                # Guardar en request context para que pueda ser usado en la función
                request.admin_id = admin_data['admin_id']
                request.admin_email = admin_data['admin_email']
                return f(*args, **kwargs)
        
        return jsonify({'error': 'No autorizado', 'redirect': '/admin/login.html'}), 401
    return decorated_function

# Inicializar las tablas si no existen
def init_db():
    """Inicializa la base de datos con las tablas necesarias"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        with conn.cursor() as cur:
            # Tabla de carreras
            cur.execute('''
                CREATE TABLE IF NOT EXISTS carreras (
                    id SERIAL PRIMARY KEY,
                    titulo VARCHAR(255) NOT NULL,
                    descripcion TEXT,
                    fecha DATE NOT NULL,
                    estado VARCHAR(50) DEFAULT 'proxima',
                    categorias VARCHAR(255),
                    ubicacion VARCHAR(255),
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de información del club
            cur.execute('''
                CREATE TABLE IF NOT EXISTS club_info (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(255) NOT NULL,
                    descripcion TEXT,
                    mision TEXT,
                    vision TEXT,
                    whatsapp_link VARCHAR(255),
                    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Tabla de registros de corredores
            cur.execute('''
                CREATE TABLE IF NOT EXISTS registros (
                    id SERIAL PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL,
                    apellido VARCHAR(100) NOT NULL,
                    edad INT NOT NULL,
                    genero VARCHAR(20) NOT NULL,
                    correo VARCHAR(150) NOT NULL,
                    team VARCHAR(100),
                    categoria VARCHAR(50) NOT NULL,
                    codigo_registro VARCHAR(50) NOT NULL UNIQUE,
                    estado VARCHAR(50) DEFAULT 'pendiente',
                    dorsal INT UNIQUE,
                    comprobante BYTEA,
                    comprobante_filename VARCHAR(255),
                    comprobante_mimetype VARCHAR(50),
                    dorsal_entregado BOOLEAN DEFAULT FALSE,
                    asistio BOOLEAN DEFAULT FALSE,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_validacion TIMESTAMP,
                    fecha_entrega_dorsal TIMESTAMP
                )
            ''')
            
            # Agregar columnas nuevas si no existen (para tablas ya creadas)
            cur.execute('''
                ALTER TABLE registros 
                ADD COLUMN IF NOT EXISTS comprobante_filename VARCHAR(255);
            ''')
            
            cur.execute('''
                ALTER TABLE registros 
                ADD COLUMN IF NOT EXISTS comprobante_mimetype VARCHAR(50);
            ''')
            
            cur.execute('''
                ALTER TABLE registros 
                ADD COLUMN IF NOT EXISTS dorsal_entregado BOOLEAN DEFAULT FALSE;
            ''')
            
            cur.execute('''
                ALTER TABLE registros 
                ADD COLUMN IF NOT EXISTS asistio BOOLEAN DEFAULT FALSE;
            ''')
            
            cur.execute('''
                ALTER TABLE registros 
                ADD COLUMN IF NOT EXISTS fecha_entrega_dorsal TIMESTAMP;
            ''')
            
            # Modificar comprobante a BYTEA si es VARCHAR (nota: esto es complicado en PostgreSQL)
            # Por ahora, dejaremos que coexistan ambas versiones
            
            conn.commit()
            print("Base de datos inicializada correctamente")
    except Exception as e:
        print(f"Error inicializando la base de datos: {e}")
    finally:
        conn.close()

# ===== ENDPOINTS DE AUTENTICACIÓN =====

@app.route('/api/login', methods=['POST'])
def login():
    """Endpoint para login de administrador"""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({
            'success': False,
            'message': 'Email y contraseña son requeridos'
        }), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({
            'success': False,
            'message': 'Error de conexión con la base de datos'
        }), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Hash de la contraseña ingresada
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            # Buscar admin en la base de datos
            cur.execute('''
                SELECT id, email, nombre, activo 
                FROM administradores 
                WHERE email = %s AND password_hash = %s AND activo = TRUE
            ''', (email, password_hash))
            
            admin = cur.fetchone()
            
            if admin:
                # Generar token en lugar de usar sesión
                token = generar_token_admin(admin['id'], admin['email'])
                
                return jsonify({
                    'success': True,
                    'message': 'Login exitoso',
                    'nombre': admin['nombre'],
                    'token': token
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Credenciales incorrectas'
                }), 401
    except Exception as e:
        print(f"Error en login: {e}")
        return jsonify({
            'success': False,
            'message': 'Error al procesar el login'
        }), 500
    finally:
        conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    """Endpoint para cerrar sesión"""
    # Buscar token para invalidarlo
    token = None
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    
    if token and token in valid_tokens:
        del valid_tokens[token]
    
    # Limpiar sesión antigua también (backwards compatibility)
    session.pop('admin_logged_in', None)
    session.pop('admin_email', None)
    
    return jsonify({
        'success': True,
        'message': 'Sesión cerrada'
    })

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """Verifica si el usuario está autenticado"""
    # Buscar token en header o query
    token = None
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    
    if not token:
        token = request.args.get('token')
    
    # Si no hay token, verificar sesión antigua
    if not token and 'admin_logged_in' in session:
        return jsonify({
            'authenticated': True,
            'email': session.get('admin_email'),
            'nombre': session.get('admin_nombre')
        })
    
    # Verificar token
    if token:
        admin_data = verificar_token(token)
        if admin_data:
            return jsonify({
                'authenticated': True,
                'email': admin_data['admin_email'],
                'token': token
            })
    
    return jsonify({
        'authenticated': False
    }), 401

@app.route('/api/cambiar-password', methods=['POST'])
@require_auth
def cambiar_password():
    """Cambiar contraseña del administrador"""
    data = request.json
    password_actual = data.get('password_actual')
    password_nueva = data.get('password_nueva')
    
    if not password_actual or not password_nueva:
        return jsonify({
            'success': False,
            'message': 'Contraseña actual y nueva son requeridas'
        }), 400
    
    if len(password_nueva) < 6:
        return jsonify({
            'success': False,
            'message': 'La nueva contraseña debe tener al menos 6 caracteres'
        }), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({
            'success': False,
            'message': 'Error de conexión'
        }), 500
    
    try:
        with conn.cursor() as cur:
            admin_id = session.get('admin_id')
            password_actual_hash = hashlib.sha256(password_actual.encode()).hexdigest()
            
            # Verificar contraseña actual
            cur.execute('''
                SELECT id FROM administradores 
                WHERE id = %s AND password_hash = %s
            ''', (admin_id, password_actual_hash))
            
            if not cur.fetchone():
                return jsonify({
                    'success': False,
                    'message': 'Contraseña actual incorrecta'
                }), 401
            
            # Actualizar contraseña
            password_nueva_hash = hashlib.sha256(password_nueva.encode()).hexdigest()
            cur.execute('''
                UPDATE administradores 
                SET password_hash = %s 
                WHERE id = %s
            ''', (password_nueva_hash, admin_id))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Contraseña actualizada correctamente'
            })
    except Exception as e:
        print(f"Error cambiando contraseña: {e}")
        return jsonify({
            'success': False,
            'message': 'Error al cambiar contraseña'
        }), 500
    finally:
        conn.close()

# ===== ENDPOINTS PÚBLICOS =====

# Endpoint: Servir página principal
@app.route('/')
def serve_index():
    """Sirve la página principal"""
    return send_from_directory('.', 'index.html')

# Endpoint: Servir archivos HTML
@app.route('/<path:filename>')
def serve_static(filename):
    """Sirve archivos estáticos HTML, CSS, JS, imágenes"""
    if filename.endswith('.html'):
        return send_from_directory('.', filename)
    return send_from_directory('.', filename)

# Endpoint: Servir archivos de comprobantes desde la base de datos
@app.route('/comprobantes/<codigo>')
@require_auth
def serve_comprobante(codigo):
    """Sirve el comprobante desde la base de datos (solo para admins autenticados)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT comprobante, comprobante_mimetype, comprobante_filename 
                FROM registros 
                WHERE codigo_registro = %s AND comprobante IS NOT NULL
            ''', (codigo,))
            result = cur.fetchone()
            
            if not result or not result['comprobante']:
                return jsonify({'error': 'Comprobante no encontrado'}), 404
            
            return Response(
                result['comprobante'],
                mimetype=result['comprobante_mimetype'] or 'image/jpeg',
                headers={'Content-Disposition': f'inline; filename="{result["comprobante_filename"]}"'}
            )
    except Exception as e:
        print(f"Error sirviendo comprobante: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Obtener información del club
@app.route('/api/club-info', methods=['GET'])
def get_club_info():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT * FROM club_info LIMIT 1')
            club_info = cur.fetchone()
            
            if club_info:
                return jsonify(club_info)
            else:
                return jsonify({'error': 'Información del club no encontrada'}), 404
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Obtener carreras próximas
@app.route('/api/carreras/proximas', methods=['GET'])
def get_carreras_proximas():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT * FROM carreras 
                WHERE estado = 'proxima' 
                ORDER BY fecha ASC
            ''')
            carreras = cur.fetchall()
            return jsonify(carreras)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Obtener carreras realizadas
@app.route('/api/carreras/realizadas', methods=['GET'])
def get_carreras_realizadas():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT * FROM carreras 
                WHERE estado = 'realizada' 
                ORDER BY fecha DESC
            ''')
            carreras = cur.fetchall()
            return jsonify(carreras)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Obtener todas las carreras
@app.route('/api/carreras', methods=['GET'])
def get_all_carreras():
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT * FROM carreras ORDER BY fecha DESC')
            carreras = cur.fetchall()
            return jsonify(carreras)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Registrar corredor
@app.route('/api/registrar-corredor', methods=['POST'])
def registrar_corredor():
    """Registra un nuevo corredor y envía correos"""
    data = request.json
    
    # Generar código único de registro
    codigo_registro = f"REG-{uuid.uuid4().hex[:8].upper()}"
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO registros (carrera_id, nombre, apellido, edad, genero, correo, team, categoria, codigo_registro)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                data.get('carrera_id'),
                data['nombre'],
                data['apellido'],
                data['edad'],
                data['genero'],
                data['correo'],
                data.get('team'),
                data['categoria'],
                codigo_registro
            ))
            conn.commit()
        
        # Enviar correo al corredor
        asunto_corredor = "Tu Pre-Registro en VO2Max Running"
        cuerpo_corredor = f"""
        <html>
            <body>
                <h2>¡Bienvenido a VO2Max Running!</h2>
                <p>Hola {data['nombre']},</p>
                <p>Tu pre-registro ha sido completado exitosamente. Tu código de registro es:</p>
                <h3 style="color: #38a169;">{codigo_registro}</h3>
                <p>Ahora debes completar tu registro subiendo el comprobante de pago en el siguiente enlace:</p>
                <p><a href="https://vo2maxproject.up.railway.app/validacion.html?codigo={codigo_registro}" style="background-color: #38a169; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Subir Comprobante</a></p>
                <h4>Métodos de Pago:</h4>
                <ul>
                    <li><strong>Yappy:</strong> +507 6974-8190</li>
                    <li><strong>Transferencia Banistmo:</strong><br>Cuenta de ahorros<br>Christopher Jurado<br>0119978303</li>
                </ul>
                <p>Una vez validado tu pago, recibirás tu número de dorsal y las instrucciones del día de la carrera.</p>
                <p>¡A correr!</p>
                <p>VO2Max Team</p>
            </body>
        </html>
        """
        
        # Enviar correo al admin
        asunto_admin = f"Nuevo Registro: {data['nombre']} {data['apellido']}"
        cuerpo_admin = f"""
        <html>
            <body>
                <h2>Nuevo Registro de Corredor</h2>
                <p><strong>Código:</strong> {codigo_registro}</p>
                <p><strong>Nombre:</strong> {data['nombre']} {data['apellido']}</p>
                <p><strong>Correo:</strong> {data['correo']}</p>
                <p><strong>Edad:</strong> {data['edad']}</p>
                <p><strong>Género:</strong> {data['genero']}</p>
                <p><strong>Categoría:</strong> {data['categoria']}</p>
                <p><strong>Team:</strong> {data.get('team', 'N/A')}</p>
            </body>
        </html>
        """
        
        send_email(data['correo'], asunto_corredor, cuerpo_corredor)
        send_email(ADMIN_EMAIL, asunto_admin, cuerpo_admin)
        
        return jsonify({
            'success': True,
            'message': 'Registro completado. Revisa tu correo para continuar.',
            'codigo': codigo_registro
        })
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Subir comprobante de pago
@app.route('/api/subir-comprobante', methods=['POST'])
def subir_comprobante():
    """Sube el comprobante de pago y lo guarda comprimido en la base de datos"""
    codigo = request.form.get('codigo')
    
    if 'comprobante' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['comprobante']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        original_filename = file.filename
        file_extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'bin'
        
        # Crear nombre corto: codigo_timestamp.ext (máx 50 caracteres)
        import time
        short_filename = f"{codigo}_{int(time.time())}.{file_extension}"
        
        # Asegurar que no exceda 255 caracteres (aunque con este formato es imposible)
        short_filename = short_filename[:255]
        
        # Leer el archivo UNA sola vez
        file_data = file.read()
        original_size = len(file_data)
        print(f"📤 Archivo recibido: {original_filename} ({original_size} bytes)")
        print(f"   Guardando como: {short_filename}")
        
        # Si es imagen, comprimirla
        if file_extension in ['jpg', 'jpeg', 'png']:
            try:
                # Abrir imagen con PIL
                image = Image.open(io.BytesIO(file_data))
                print(f"📸 Imagen abierta: {image.format} {image.size}")
                
                # Convertir a RGB si es necesario (para PNG con transparencia)
                if image.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = background
                
                # Redimensionar si es muy grande (max 1200px en el lado más largo)
                max_size = 1200
                if max(image.size) > max_size:
                    ratio = max_size / max(image.size)
                    new_size = tuple(int(dim * ratio) for dim in image.size)
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                
                # Comprimir y guardar en buffer
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG', quality=70, optimize=True)
                file_data = buffer.getvalue()
                file_extension = 'jpg'
                
                compressed_size = len(file_data)
                print(f"✓ Imagen comprimida: {original_size}b → {compressed_size}b ({100 - int(compressed_size*100/original_size)}% reducción)")
            except Exception as e:
                print(f"⚠ Error comprimiendo imagen, guardando original: {e}")
                print(f"✓ Guardando imagen original: {filename} ({original_size} bytes)")
        
        # Determinar mimetype
        mimetype_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'pdf': 'application/pdf'
        }
        mimetype = mimetype_map.get(file_extension, 'application/octet-stream')
        
        print(f"✓ Guardando comprobante en BD: {short_filename} ({len(file_data)} bytes, mimetype: {mimetype})")
        
        with conn.cursor() as cur:
            # Guardar archivo como BYTEA en la base de datos
            cur.execute('''
                UPDATE registros 
                SET comprobante = %s, 
                    comprobante_filename = %s,
                    comprobante_mimetype = %s,
                    estado = %s
                WHERE codigo_registro = %s
            ''', (psycopg2.Binary(file_data), short_filename, mimetype, 'pendiente_validacion', codigo))
            conn.commit()
            print(f"✓ Comprobante guardado en BD para {codigo}")
            
            # Obtener datos del corredor para el correo del admin
            cur.execute('SELECT correo, nombre, apellido FROM registros WHERE codigo_registro = %s', (codigo,))
            corredor = cur.fetchone()
        
        if corredor:
            # Enviar correo al admin con el comprobante
            asunto_admin = f"Comprobante de Pago Recibido - {codigo}"
            cuerpo_admin = f"""
            <html>
                <body>
                    <h2>Comprobante de Pago Recibido</h2>
                    <p><strong>Código de Registro:</strong> {codigo}</p>
                    <p><strong>Corredor:</strong> {corredor[1]} {corredor[2]}</p>
                    <p><strong>Correo:</strong> {corredor[0]}</p>
                    <p>Por favor valida el comprobante en el panel de administración.</p>
                    <p><a href="https://vo2maxproject.up.railway.app/admin/index.html" style="background-color: #38a169; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Ir al Panel de Admin</a></p>
                </body>
            </html>
            """
            send_email(ADMIN_EMAIL, asunto_admin, cuerpo_admin)
        
        return jsonify({
            'success': True,
            'message': 'Comprobante subido correctamente. El admin validará tu pago.'
        })
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Obtener registro por código
@app.route('/api/registro/<codigo>', methods=['GET'])
def get_registro(codigo):
    """Obtiene un registro por código"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Excluir comprobante (BYTEA) pero incluir comprobante_filename
            cur.execute('''
                SELECT id, nombre, apellido, edad, genero, correo, team, categoria, 
                       codigo_registro, estado, dorsal, fecha_creacion, fecha_validacion,
                       carrera_id, dorsal_entregado, asistio, fecha_entrega_dorsal,
                       comprobante_filename, comprobante_mimetype
                FROM registros WHERE codigo_registro = %s
            ''', (codigo,))
            registro = cur.fetchone()
            
            if registro:
                return jsonify(registro)
            else:
                return jsonify({'error': 'Registro no encontrado'}), 404
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Validar pago (admin)
@app.route('/api/validar-pago', methods=['POST'])
@require_auth
def validar_pago():
    """Valida el pago y envía dorsal al corredor"""
    try:
        data = request.json
        codigo = data.get('codigo')
        valido = data.get('valido')  # True o False
        
        print(f"Validando pago - Código: {codigo}, Válido: {valido}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Obtener datos del corredor
                cur.execute('SELECT * FROM registros WHERE codigo_registro = %s', (codigo,))
                registro = cur.fetchone()
                
                if not registro:
                    return jsonify({'error': 'Registro no encontrado'}), 404
                
                if valido:
                    # Obtener el último dorsal asignado
                    cur.execute('SELECT MAX(dorsal) FROM registros WHERE dorsal IS NOT NULL')
                    result = cur.fetchone()
                    max_dorsal = result['max'] if result and result['max'] is not None else None
                    
                    # Generar dorsal secuencial comenzando desde 001
                    if max_dorsal is None:
                        dorsal = 1
                    else:
                        dorsal = max_dorsal + 1
                    
                    print(f"Asignando dorsal {dorsal} al código {codigo}")
                    
                    cur.execute('''
                        UPDATE registros SET estado = %s, dorsal = %s, fecha_validacion = %s
                        WHERE codigo_registro = %s
                    ''', ('pagado', dorsal, datetime.now(), codigo))
                    conn.commit()
                    
                    # Enviar correo al corredor con dorsal e instrucciones
                    asunto = "¡Confirmado! Tu Dorsal para la Carrera del Grinch"
                    cuerpo = f"""
                    <html>
                        <head>
                            <style>
                                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                                .header {{ background-color: #38a169; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                                .content {{ background-color: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }}
                                .dorsal {{ background-color: #38a169; color: white; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; border-radius: 10px; margin: 20px 0; }}
                                .info-item {{ display: flex; align-items: start; gap: 10px; margin: 15px 0; }}
                                .icon {{ color: #38a169; min-width: 20px; }}
                                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 14px; }}
                                ul {{ padding-left: 20px; }}
                                li {{ margin: 8px 0; }}
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <div class="header">
                                    <h2 style="margin: 0;">¡Tu Inscripción ha sido Confirmada!</h2>
                                </div>
                                <div class="content">
                                    <p>Hola <strong>{registro['nombre']}</strong>,</p>
                                    <p>Tu pago ha sido validado correctamente. Aquí está tu información para la carrera:</p>
                                    
                                    <div class="dorsal">
                                        DORSAL: {str(dorsal).zfill(3)}
                                    </div>
                                    
                                    <h3 style="color: #38a169; margin-top: 30px;">Información de la Carrera:</h3>
                                    
                                    <div class="info-item">
                                        <span class="icon">📅</span>
                                        <div><strong>Fecha:</strong> 21 de diciembre de 2025</div>
                                    </div>
                                    
                                    <div class="info-item">
                                        <span class="icon">🕐</span>
                                        <div><strong>Hora:</strong> Desde las 6:00 a.m.</div>
                                    </div>
                                    
                                    <div class="info-item">
                                        <span class="icon">📍</span>
                                        <div><strong>Lugar:</strong> Cancha de San Pablo Viejo, David, Chiriquí</div>
                                    </div>
                                    
                                    <h3 style="color: #38a169; margin-top: 30px;">Instrucciones Importantes:</h3>
                                    <ul>
                                        <li>Presentarse 30 minutos antes de la hora de inicio</li>
                                        <li>Llevar identificación válida</li>
                                        <li>Usar el dorsal en la parte frontal del pecho</li>
                                        <li>Recoger tu kit en el punto de entrega</li>
                                        <li>Hidratarse bien antes de la carrera</li>
                                    </ul>
                                    
                                    <div class="footer">
                                        <p><strong>¡Que disfrutes la carrera!</strong></p>
                                        <p>VO2Max Team</p>
                                    </div>
                                </div>
                            </div>
                        </body>
                    </html>
                    """
                    send_email(registro['correo'], asunto, cuerpo)
                    
                    return jsonify({
                        'success': True,
                        'message': f'Pago validado. Dorsal: {str(dorsal).zfill(3)}',
                        'dorsal': dorsal,
                        'dorsal_formatted': str(dorsal).zfill(3)
                    })
                else:
                    # Rechazar registro
                    cur.execute('''
                        UPDATE registros SET estado = %s, fecha_validacion = %s
                        WHERE codigo_registro = %s
                    ''', ('rechazado', datetime.now(), codigo))
                    conn.commit()
                    
                    # Enviar correo de rechazo
                    asunto = "Tu Comprobante de Pago ha Sido Rechazado"
                    cuerpo = f"""
                    <html>
                        <body>
                            <h2>Comprobante Rechazado</h2>
                            <p>Hola {registro['nombre']},</p>
                            <p>El comprobante de pago que subiste no fue válido. Por favor:</p>
                            <ul>
                                <li>Verifica que el comprobante sea claro y legible</li>
                                <li>Asegúrate de que sea del monto correcto</li>
                                <li>Intenta subir el comprobante nuevamente</li>
                            </ul>
                            <p><a href="https://vo2maxproject.up.railway.app/validacion.html?codigo={codigo}">Subir Nuevo Comprobante</a></p>
                            <p>VO2Max Team</p>
                        </body>
                    </html>
                    """
                    send_email(registro['correo'], asunto, cuerpo)
                    
                    return jsonify({
                        'success': True,
                        'message': 'Pago rechazado. Correo enviado al corredor.'
                    })
        except Exception as e:
            conn.rollback()
            print(f"Error en validación: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
        finally:
            conn.close()
    except Exception as e:
        print(f"Error general en validar_pago: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Endpoint: Obtener registros pendientes (admin)
@app.route('/api/registros-pendientes', methods=['GET'])
@require_auth
def get_registros_pendientes():
    """Obtiene los registros pendientes de validación (sin traer imagenes)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT id, nombre, apellido, edad, genero, correo, team, categoria, 
                       codigo_registro, estado, comprobante_filename, comprobante_mimetype,
                       CASE WHEN comprobante IS NOT NULL THEN true ELSE false END as tiene_comprobante,
                       fecha_creacion
                FROM registros 
                WHERE estado = 'pendiente_validacion'
                ORDER BY 
                    CASE WHEN comprobante IS NOT NULL THEN 0 ELSE 1 END,
                    fecha_creacion DESC
            ''')
            registros = cur.fetchall()
            return jsonify(registros)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Marcar entrega de dorsal
@app.route('/api/entregar-dorsal', methods=['POST'])
@require_auth
def entregar_dorsal():
    """Marca que el dorsal fue entregado al corredor"""
    data = request.json
    codigo = data.get('codigo')
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE registros 
                SET dorsal_entregado = TRUE, fecha_entrega_dorsal = %s
                WHERE codigo_registro = %s AND estado = 'pagado'
            ''', (datetime.now(), codigo))
            conn.commit()
            
            if cur.rowcount == 0:
                return jsonify({'error': 'Registro no encontrado o no está pagado'}), 404
            
            return jsonify({
                'success': True,
                'message': 'Dorsal marcado como entregado'
            })
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Marcar asistencia
@app.route('/api/marcar-asistencia', methods=['POST'])
@require_auth
def marcar_asistencia():
    """Marca que el corredor asistió a la carrera"""
    data = request.json
    codigo = data.get('codigo')
    asistio = data.get('asistio', True)
    
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE registros 
                SET asistio = %s
                WHERE codigo_registro = %s AND estado = 'pagado'
            ''', (asistio, codigo))
            conn.commit()
            
            if cur.rowcount == 0:
                return jsonify({'error': 'Registro no encontrado o no está pagado'}), 404
            
            return jsonify({
                'success': True,
                'message': f'Asistencia marcada como {asistio}'
            })
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Endpoint: Obtener corredores inscritos (pagados) - Para el día de la carrera
@app.route('/api/registros-inscritos', methods=['GET'])
@require_auth
def get_registros_inscritos():
    """Obtiene los registros con pago validado (estado = pagado)"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'No se pudo conectar a la base de datos'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT id, nombre, apellido, edad, genero, correo, team, categoria, 
                       codigo_registro, dorsal, dorsal_entregado, asistio, 
                       fecha_entrega_dorsal, fecha_creacion
                FROM registros 
                WHERE estado = 'pagado'
                ORDER BY dorsal ASC
            ''')
            registros = cur.fetchall()
            
            # Formatear dorsales con 3 dígitos
            for registro in registros:
                if registro['dorsal']:
                    registro['dorsal_formatted'] = str(registro['dorsal']).zfill(3)
            
            return jsonify(registros)
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# Inicializar base de datos al importar el módulo (para gunicorn)
init_db()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)