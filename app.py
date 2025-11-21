import streamlit as st
import pandas as pd
import requests
import psycopg2
import psycopg2.extras
import time
from datetime import datetime, date, timedelta
import calendar
from urllib.parse import urlparse, parse_qs

# --- 1. Configuración y Constantes ---
DB_FILE = "puntuaciones.db"
STRAVA_API_URL = "https://www.strava.com/api/v3/"

# OAuth Endpoints
AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
REDIRECT_URI = "vo2rank.up.railway.app" 
SCOPES = "activity:read_all,profile:read_all"

# Reglas de Puntuación
DIA_JUEVES = 3  # Lunes=0, Jueves=3
PUNTOS_NORMALES = 1
PUNTOS_JUEVES = 3
# Tipos de actividad permitidos para puntuar
ALLOWED_ACTIVITY_TYPES = {"Run", "Walk"}

# Credenciales de Streamlit Secrets
import os

# Cargar variables de entorno desde un archivo .env si está disponible.
# Intentamos usar python-dotenv si está instalado; si no, parseamos .env manualmente.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Fallback simple: cargar .env en el cwd si existe
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and v and k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

# Soportar tanto mayúsculas como minúsculas en las claves del .env
CLIENT_ID = os.getenv('CLIENT_ID') or os.getenv('client_id') or "0"
CLIENT_SECRET = os.getenv('CLIENT_SECRET') or os.getenv('client_secret') or "0"
CLUB_ID = os.getenv('CLUB_ID') or os.getenv('club_id') or None

if CLIENT_ID == "0" or CLIENT_SECRET == "0":
    st.error("🚨 CONFIGURACIÓN FALTANTE: Configura 'CLIENT_ID' y 'CLIENT_SECRET' en .env o variables de entorno")


st.set_page_config(
        page_title="VO2 Ranking",
        page_icon="🏆",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

# --- 2. Funciones de Base de Datos (SQLite) y OAuth ---

def get_db_conn():
    """Devuelve una conexión a la base de datos PostgreSQL usando DATABASE_URL."""
    DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('database_url')
    if not DATABASE_URL:
        # No paramos la ejecución, pero avisamos: el resto de funciones comprobará None
        st.error("🚨 DATABASE_URL no está configurada. Define la variable de entorno DATABASE_URL apuntando a tu Postgres.")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    except Exception as e:
        st.error(f"Error conectando a la base de datos PostgreSQL: {e}")
        return None


def init_db():
    """Inicializa la base de datos y crea las tablas si no existen."""
    conn = get_db_conn()
    if conn is None:
        return
    cursor = conn.cursor()
    # Tabla para actividades puntuadas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            athlete_id INTEGER,
            activity_id BIGINT PRIMARY KEY,
            firstname TEXT,
            lastname TEXT,
            gender TEXT,
            points INTEGER,
            activity_date TIMESTAMP,
            date_scored TIMESTAMP
        )
    """)
    # Tabla para almacenar los tokens de los atletas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS athlete_tokens (
            athlete_id BIGINT PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at BIGINT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

@st.cache_data(ttl=5) 
def load_ranking_data():
    """Carga todos los datos de la tabla de puntuaciones."""
    init_db()
    conn = get_db_conn()
    if conn is None:
        return pd.DataFrame()
    cur = conn.cursor()
    cur.execute("SELECT * FROM scores")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        return pd.DataFrame(columns=['athlete_id','activity_id','firstname','lastname','gender','points','activity_date','date_scored'])
    df = pd.DataFrame(rows)
    return df

def get_athlete_token_data(athlete_id):
    """Busca los tokens de un atleta por ID."""
    conn = get_db_conn()
    if conn is None:
        return None
    cursor = conn.cursor()
    cursor.execute("SELECT access_token, refresh_token, expires_at FROM athlete_tokens WHERE athlete_id=%s", (athlete_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result:
        return {'access_token': result['access_token'], 'refresh_token': result['refresh_token'], 'expires_at': result['expires_at']}
    return None

def save_athlete_tokens(athlete_id, access_token, refresh_token, expires_at):
    """Guarda o actualiza los tokens de un atleta."""
    conn = get_db_conn()
    if conn is None:
        return False
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO athlete_tokens (athlete_id, access_token, refresh_token, expires_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (athlete_id) DO UPDATE
        SET access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at
    """, (athlete_id, access_token, refresh_token, expires_at))
    conn.commit()
    cursor.close()
    conn.close()
    return True

def register_activity(activity_data):
    """Registra una nueva actividad en la base de datos."""
    conn = get_db_conn()
    if conn is None:
        return False
    cursor = conn.cursor()
    values = (
        activity_data['athlete_id'], activity_data['activity_id'],
        activity_data['firstname'], activity_data['lastname'],
        activity_data['gender'], activity_data['points'],
        activity_data['activity_date'], datetime.now().isoformat()
    )
    cursor.execute("""
        INSERT INTO scores (athlete_id, activity_id, firstname, lastname, gender, points, activity_date, date_scored)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (activity_id) DO NOTHING
    """, values)
    conn.commit()
    inserted = cursor.rowcount > 0
    cursor.close()
    conn.close()
    return inserted

def refresh_access_token(athlete_id, refresh_token):
    """Refresca el Access Token si está expirado."""
    # (Lógica de refresh token... sin cambios, se mantiene la misma estructura)
    st.info(f"Refrescando token para el atleta {athlete_id}...")
    payload = {
        'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
        'grant_type': 'refresh_token', 'refresh_token': refresh_token
    }
    response = requests.post(TOKEN_URL, data=payload)
    if response.status_code == 200:
        data = response.json()
        expires_at = int(time.time()) + data['expires_in'] - 60
        save_athlete_tokens(athlete_id, data['access_token'], data['refresh_token'], expires_at)
        st.session_state['current_token'] = data['access_token']
        st.success("Token de acceso refrescado exitosamente.")
        return data['access_token']
    else:
        st.error("Error al refrescar el token. Por favor, inicia sesión de nuevo.")
        st.session_state['logged_in'] = False
        return None

def get_valid_token(athlete_id):
    """Devuelve un token válido (refresca si es necesario)."""
    token_data = get_athlete_token_data(athlete_id)
    if not token_data:
        st.session_state['logged_in'] = False
        return None
    if token_data['expires_at'] < time.time():
        return refresh_access_token(athlete_id, token_data['refresh_token'])
    else:
        st.session_state['current_token'] = token_data['access_token']
        return token_data['access_token']

def handle_oauth_callback(code):
    """Intercambia el código de autorización por tokens y guarda los datos del atleta."""
    # (Lógica de callback de OAuth... sin cambios, se mantiene la misma estructura)
    # st.info("Intercambiando código de autorización por tokens...")
    payload = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
               'code': code, 'grant_type': 'authorization_code'}
    response = requests.post(TOKEN_URL, data=payload)
    if response.status_code == 200:
        data = response.json()
        athlete_id = data['athlete']['id']
        expires_at = int(time.time()) + data['expires_in'] - 60
        save_athlete_tokens(athlete_id, data['access_token'], data['refresh_token'], expires_at)
        st.session_state['logged_in'] = True
        st.session_state['athlete_id'] = athlete_id
        st.session_state['current_token'] = data['access_token']
        st.session_state['athlete_name'] = f"{data['athlete']['firstname']} {data['athlete']['lastname']}"
        st.session_state['athlete_gender'] = data['athlete'].get('sex', 'N/A')
        # st.success(f"¡Bienvenido/a, {st.session_state['athlete_name']}! Autenticación exitosa.")
    else:
        st.error(f"Error en la autenticación con Strava: Código {response.status_code}. Intenta de nuevo.")
        st.session_state['logged_in'] = False


# --- 3. Funciones de Data Fetching con Filtro por Mes ---

def get_month_timestamps():
    """Calcula los Unix timestamps para el inicio y fin del mes actual."""
    today = date.today()
    
    # Inicio del mes actual (00:00:00 del día 1)
    start_of_month = today.replace(day=1)
    ts_after = int(time.mktime(start_of_month.timetuple()))
    
    # Fin del mes actual (23:59:59 del último día)
    _, num_days = calendar.monthrange(today.year, today.month)
    end_of_month = today.replace(day=num_days) + timedelta(hours=23, minutes=59, seconds=59)
    ts_before = int(time.mktime(end_of_month.timetuple()))
    
    return ts_after, ts_before


def get_activities(access_token, page=1, per_page=200):
    """Obtiene las actividades del atleta autenticado SOLAMENTE para el mes actual."""
    
    ts_after, ts_before = get_month_timestamps()
    
    url = f"{STRAVA_API_URL}athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Parámetros 'after' y 'before' para filtrar por el mes actual
    params = {
        "page": page, 
        "per_page": per_page,
        "after": ts_after,
        "before": ts_before 
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.error("Error 401: Token de Acceso inválido. Necesitas iniciar sesión de nuevo.")
            st.session_state['logged_in'] = False 
            return None
        else:
            st.error(f"Error al obtener actividades de Strava: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error de conexión a Strava: {e}")
        return None

def score_activity(activity_data):
    """Aplica la lógica de puntos (1 punto normal, 3 puntos los jueves)."""
    # Preferir la fecha local de inicio (evita errores por zonas horarias)
    date_str = activity_data.get('start_date_local') or activity_data.get('start_date')

    try:
        # Strava devuelve 'start_date' con 'Z' (UTC) y 'start_date_local' sin sufijo.
        if isinstance(date_str, str) and date_str.endswith('Z'):
            activity_datetime = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            activity_datetime = datetime.fromisoformat(date_str)

        day_of_week = activity_datetime.weekday()

        if day_of_week == DIA_JUEVES:
            return PUNTOS_JUEVES, activity_datetime.isoformat()
        else:
            return PUNTOS_NORMALES, activity_datetime.isoformat()
    except Exception:
        return 0, datetime.now().isoformat()

def process_and_score(access_token):
    """Procesa las actividades del atleta logeado y registra las nuevas."""
    
    # 1. Obtener actividades filtradas por mes
    with st.spinner('Consultando actividades del mes actual en Strava...'):
        activities = get_activities(access_token)
    
    if not activities:
        return False
    # Mostrar conteo por tipo recibido (para inspección)
    from collections import Counter, defaultdict
    types_counter = Counter(a.get('type') for a in activities)
    st.info(f"Tipos de actividad recibidos (raw): {dict(types_counter)} | Total raw: {len(activities)}")

    # Deduplicar actividades por 'id' — si hay duplicados con distintos 'type', preferir 'Run' sobre 'Walk'
    activities_by_id = {}
    dup_info = defaultdict(list)
    for a in activities:
        aid = a.get('id')
        atype = a.get('type')
        if aid in activities_by_id:
            dup_info[aid].append(atype)
            # preferir Run si aparece
            existing = activities_by_id[aid]
            if existing.get('type') != atype:
                # si nuevo es Run y existente no, reemplazar
                if atype == 'Run' and existing.get('type') != 'Run':
                    activities_by_id[aid] = a
        else:
            activities_by_id[aid] = a

    duplicates = {k: v for k, v in dup_info.items() if v}
    if duplicates:
        st.warning(f"Actividades duplicadas detectadas por id: {duplicates}")

    deduped_activities = list(activities_by_id.values())
    deduped_types = Counter(a.get('type') for a in deduped_activities)
    st.info(f"Tipos de actividad después de dedup: {dict(deduped_types)} | Total unique: {len(deduped_activities)}")

    # Filtrar solo los tipos permitidos (Run y Walk) sobre la lista deduplicada
    filtered_activities = [a for a in deduped_activities if a.get('type') in ALLOWED_ACTIVITY_TYPES]
    if not filtered_activities:
        st.info("No hay actividades de tipo 'Run' o 'Walk' en el mes actual.")
        return False
    # Reporte por día de la semana (inspección) y detalle de los jueves
    weekday_names = ['Lun','Mar','Mie','Jue','Vie','Sab','Dom']
    weekday_counter = Counter()
    thursday_list = []
    for a in filtered_activities:
        date_str = a.get('start_date_local') or a.get('start_date')
        try:
            if isinstance(date_str, str) and date_str.endswith('Z'):
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(date_str)
            wd = dt.weekday()
            weekday_counter[weekday_names[wd]] += 1
            if wd == DIA_JUEVES:
                thursday_list.append({'id': a.get('id'), 'date': dt.isoformat(), 'type': a.get('type')})
        except Exception:
            continue

    st.info(f"Actividades por día (filtradas): {dict(weekday_counter)}")
    st.info(f"Jueves detectados (filtrados): {len(thursday_list)} — detalle: {thursday_list}")
    
    athlete_id = st.session_state['athlete_id']
    firstname = st.session_state.get('athlete_name', '').split(' ')[0]
    lastname = st.session_state.get('athlete_name', '').split(' ')[-1]
    gender = st.session_state.get('athlete_gender', 'N/A')

    new_entries = 0
    
    for act in filtered_activities:
        points, activity_date = score_activity(act)
        
        if points > 0:
            activity_data = {
                'athlete_id': athlete_id,
                'activity_id': act['id'],
                'firstname': firstname,
                'lastname': lastname,
                'gender': gender,
                'points': points,
                'activity_date': activity_date,
            }
            
            if register_activity(activity_data):
                new_entries += 1
                
    if new_entries > 0:
        st.success(f"🎉 Se han registrado {new_entries} actividades nuevas para {firstname} {lastname}.")
        return True
    else:
        st.info(f"No se encontraron nuevas actividades para {firstname} {lastname} en el mes actual (o ya fueron puntuadas).")
        return False


# --- 4. Interfaz de Streamlit y Lógica Principal ---

def display_ranking(df, gender_code, title):
    """Muestra la tabla de ranking para un género específico."""
    st.subheader(f"{title}")
    ranking_data = df[df['gender'] == gender_code].copy()
    
    if ranking_data.empty:
        st.info(f"No hay actividades registradas para el ranking {title}.")
        return

    final_ranking = ranking_data.groupby(['firstname', 'lastname'])['points'].sum().reset_index(name='Puntos Totales')
    final_ranking = final_ranking.sort_values(by='Puntos Totales', ascending=False)
    final_ranking['Posición'] = final_ranking['Puntos Totales'].rank(method='min', ascending=False).astype(int)
    
    cols = ['Posición', 'firstname', 'lastname', 'Puntos Totales']
    final_ranking = final_ranking[cols].rename(columns={'firstname': 'Nombre', 'lastname': 'Apellido'})
    
    color = '#5c7cfa' if gender_code == 'M' else '#ff608c'
    st.dataframe(
        final_ranking.style.bar(subset=['Puntos Totales'], color=color, align='left'),
        use_container_width=True,
        hide_index=True
    )

def app():
    st.title("🏆 Ranking de Club - Puntos por Actividad")
    # st.markdown(f"### Solo actividades del mes: {datetime.now().strftime('%B %Y')}")
    
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['athlete_id'] = None

    query_params = st.query_params
    
    if 'code' in query_params and not st.session_state['logged_in']:
        handle_oauth_callback(query_params['code'])

    if not st.session_state['logged_in']:
        auth_url = (
            f"{AUTHORIZE_URL}?client_id={CLIENT_ID}&response_type=code"
            f"&redirect_uri={REDIRECT_URI}&scope={SCOPES}"
        )
        col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
        with col_btn2:
            if st.button("🔗 Iniciar Sesión con Strava", use_container_width=True, type="primary"):
                st.markdown(f"<meta http-equiv='refresh' content='0;url={auth_url}' />", unsafe_allow_html=True)
        
        st.warning("Para sincronizar tus actividades, debes iniciar sesión con Strava.")

    else:
        valid_token = get_valid_token(st.session_state['athlete_id'])

        if valid_token:
            st.success(f"Conectado como: **{st.session_state.get('athlete_name', 'Atleta')}**")
            st.markdown("---")

            with st.expander("Sincronizar mis Actividades Recientes", expanded=True):
                if st.button("🔄 Sincronizar y Puntuuar Actividades Nuevas"):
                    with st.spinner('Consultando y procesando actividades...'):
                        process_and_score(valid_token)
                    load_ranking_data.clear() 
        else:
            st.warning("Tu sesión ha expirado o hubo un error al refrescar el token. Por favor, vuelve a iniciar sesión.")
            st.session_state['logged_in'] = False
    
    st.markdown("---")

    current_df = load_ranking_data()
    
    if current_df.empty:
        st.info("Aún no hay actividades registradas en la base de datos para este mes.")
    else:
        display_ranking(current_df, 'M', "Ranking Masculino")
        st.markdown("")
        display_ranking(current_df, 'F', "Ranking Femenino")

        # Contar actividades únicas por atleta y por día (evita contar Run+Walk como dos si ocurren el mismo día)
        try:
            df_copy = current_df.copy()
            # Normalizar usando la porción YYYY-MM-DD de activity_date para evitar problemas de zona horaria
            # y considerar Run+Walk en la misma fecha como una sola actividad para el conteo.
            df_copy['activity_day_str'] = df_copy['activity_date'].astype(str).str.slice(0, 10)
            unique_count = df_copy.drop_duplicates(subset=['athlete_id', 'activity_day_str']).shape[0]
            raw_count = len(current_df)
            # st.caption(f"Total de actividades puntuadas este mes (únicas por día/atleta): {unique_count} (filas registradas: {raw_count})")
        except Exception:
            st.caption(f"Total de actividades puntuadas este mes: {len(current_df)}")


if __name__ == "__main__":
    init_db()
    app()