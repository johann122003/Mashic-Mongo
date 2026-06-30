import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Diccionario para guardar portadas y que no cargue lento
cache_portadas = {}

# PON TUS CREDENCIALES AQUÍ
SPOTIFY_CLIENT_ID = '92b472ff7e87473896922bed480cf4a1'
SPOTIFY_CLIENT_SECRET = '16bcb76345384eb792b5165160a426ed'

def obtener_portada_spotify(nombre_cancion, nombre_album):
    # Primero buscamos en la caché (memoria rápida)
    clave = f"{nombre_cancion}_{nombre_album}"
    if clave in cache_portadas:
        return cache_portadas[clave]
    
    try:
        credenciales = SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID, 
            client_secret=SPOTIFY_CLIENT_SECRET
        )
        sp = spotipy.Spotify(client_credentials_manager=credenciales)
        
        query = f"track:{nombre_cancion} album:{nombre_album}"
        resultados = sp.search(q=query, type='track', limit=1)
        
        if resultados['tracks']['items']:
            pista = resultados['tracks']['items'][0]
            if pista['album']['images']:
                url = pista['album']['images'][1]['url']
                cache_portadas[clave] = url # Guardamos en caché
                return url
                
        default_url = 'https://ui-avatars.com/api/?name=🎵&background=0A0A0A&color=FDE047&size=128'
        cache_portadas[clave] = default_url
        return default_url
                
    except Exception as e:
        print(f"Error: {e}")
        return 'https://ui-avatars.com/api/?name=🎵&background=0A0A0A&color=FDE047&size=128'