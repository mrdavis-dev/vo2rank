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

