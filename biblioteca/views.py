# ============================================================
# views.py — Mashic Music con MongoDB (pymongo)
# ============================================================
# Instalar: pip install pymongo
# En settings.py agregar:
#   from pymongo import MongoClient
#   MONGO_CLIENT = MongoClient("mongodb://localhost:27017/")
#   MONGO_DB = MONGO_CLIENT["MashicDB"]
# ============================================================

from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from datetime import datetime
import os
import json
from biblioteca.spotify_utils import obtener_portada_spotify

# ── Conexión a MongoDB ──────────────────────────────────────
def get_db():
    return settings.MONGO_DB

# ── Helper: obtener o guardar portada ───────────────────────
# ── Helper obtener o guardar portada (OPTIMIZADO) ───────────────────────
def obtener_o_guardar_portada(cancion_doc):
    # Verificamos si la portada ya vino en los datos que cargamos
    if cancion_doc.get('url_portada'):
        return cancion_doc['url_portada']
    
    # Si no la tiene, recién ahí consultamos a Spotify
    titulo = cancion_doc.get('titulo', '')
    album = cancion_doc.get('album', {}).get('titulo_album', '')
    nueva_url = obtener_portada_spotify(titulo, album)
    
    # Guardamos en Mongo para que la próxima vez cargue al instante
    db = get_db()
    db.canciones.update_one(
        {"_id": cancion_doc['_id']},
        {"$set": {"url_portada": nueva_url}}
    )
    return nueva_url


# ============================================================
# AUTENTICACIÓN
# ============================================================

def iniciar_sesion(request):
    if request.method == 'POST':
        correo = request.POST.get('correo')
        password = request.POST.get('password')
        db = get_db()

        usuario = db.usuarios.find_one({
            "email": correo,
            "password": password
        })

        if usuario:
            request.session['usuario_id']     = usuario['_id']
            request.session['usuario_nombre'] = usuario['email']
            request.session['usuario_rol']    = usuario['perfil']['id_perfil']
            return redirect('lista_canciones')
        else:
            return render(request, 'biblioteca/login.html', {'error': 'Correo o contraseña incorrectos'})

    return render(request, 'biblioteca/login.html')


def cerrar_sesion(request):
    request.session.flush()
    return redirect('iniciar_sesion')


def crear_cuenta(request):
    if request.method == 'POST':
        correo       = request.POST.get('correo')
        password     = request.POST.get('password')
        fecha_nac    = request.POST.get('fecha_nacimiento')
        rol_texto    = request.POST.get('rol')  # 'Artista' o 'Oyente'
        perfil_id    = 2 if rol_texto == 'Artista' else 3
        nombre_perfil = 'Artista' if perfil_id == 2 else 'Oyente'

        db = get_db()

        # Verificar si ya existe
        if db.usuarios.find_one({"email": correo}):
            return render(request, 'biblioteca/registro.html', {
                'error': 'Ese correo ya está registrado en Mashic Music.'
            })

        # Nuevo ID
        ultimo = db.usuarios.find_one(sort=[("_id", -1)])
        nuevo_id = (ultimo['_id'] + 1) if ultimo else 101

        nuevo_usuario = {
            "_id": nuevo_id,
            "email": correo,
            "password": password,
            "fecha_nacimiento": fecha_nac,
            "fecha_registro": datetime.now().strftime('%Y-%m-%d'),
            "perfil": {"id_perfil": perfil_id, "nombre_perfil": nombre_perfil},
            "suscripcion": {"tipo_plan": "Free"}
        }

        # Si es artista, agregar sub-documento artista
        if perfil_id == 2:
            nombre_artistico = request.POST.get('nombre_artistico', correo.split('@')[0])
            nuevo_usuario["artista"] = {
                "nombre_artistico": nombre_artistico,
                "biografia": "",
                "estado_visibilidad": "1"
            }

        db.usuarios.insert_one(nuevo_usuario)
        return redirect('iniciar_sesion')

    return render(request, 'biblioteca/registro.html')


# ============================================================
# CANCIONES
# ============================================================

def lista_canciones(request):
    db = get_db()
    usuario_id    = request.session.get('usuario_id')
    playlists_usuario = []

    # SOLUCIÓN 1: Filtramos para que no traiga los álbumes vacíos (placeholders)
    canciones_raw = list(db.canciones.find({"es_placeholder": {"$ne": True}}))
    canciones = []
    for c in canciones_raw:
        canciones.append({
            'ID_Canto': c['_id'],
            'Titulo': c.get('titulo', ''),
            'Nombre_Artistico': c.get('artista', {}).get('nombre_artistico', ''),
            'Titulo_Album': c.get('album', {}).get('titulo_album', ''),
            'Ruta_Archivo': c.get('ruta_archivo', ''),
            
            # ¡AQUÍ APLICAMOS LA OPTIMIZACIÓN! Pasamos todo el objeto 'c' de una vez
            'Portada': obtener_o_guardar_portada(c),
            
            # SOLUCIÓN 3: Pasamos el ID del artista al HTML para que muestre los botones
            'Usuario_Mashi_ID_Mashi': c.get('artista', {}).get('id_usuario_mashi', '')
        })

    if usuario_id:
        playlists_raw = list(db.playlists.find({"usuario_id": usuario_id}, {"_id": 1, "nombre_playlist": 1}))
        playlists_usuario = [{'ID_Playlist': p['_id'], 'Nombre_Playlist': p['nombre_playlist']} for p in playlists_raw]

    return render(request, 'biblioteca/lista_canciones.html', {
        'canciones': canciones,
        'playlists_usuario': playlists_usuario
    })

def detalle_cancion(request, id_canto, id_playlist=None, id_album=None):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('iniciar_sesion')

    db = get_db()
    c = db.canciones.find_one({"_id": id_canto})
    if not c:
        return redirect('lista_canciones')

    cancion = {
        'ID_Canto':         c['_id'],
        'Titulo':           c.get('titulo', ''),
        'Titulo_Album':     c.get('album', {}).get('titulo_album', ''),
        'Ruta_Archivo':     c.get('ruta_archivo', ''),
        'Nombre_Artistico': c.get('artista', {}).get('nombre_artistico', ''),
        # AQUÍ APLICAMOS LA OPTIMIZACIÓN
        'Portada':          obtener_o_guardar_portada(c) 
    }

    # Navegación álbum / playlist / global
    if id_album:
        lista_ids = [x['_id'] for x in db.canciones.find({"album.id_album": id_album}, {"_id": 1})]
    elif id_playlist:
        pl = db.playlists.find_one({"_id": id_playlist})
        lista_ids = [s['id_canto'] for s in pl.get('canciones_incrustadas', [])] if pl else []
    else:
        lista_ids = [x['_id'] for x in db.canciones.find({}, {"_id": 1})]

    try:
        idx     = lista_ids.index(id_canto)
        prev_id = lista_ids[idx - 1] if idx > 0 else None
        next_id = lista_ids[idx + 1] if idx < len(lista_ids) - 1 else None
    except ValueError:
        prev_id, next_id = None, None

    if id_album:
        back_url = f'/album/{id_album}/'
    elif id_playlist:
        back_url = f'/playlist/{id_playlist}/'
    else:
        back_url = '/'

    return render(request, 'biblioteca/detalle_cancion.html', {
        'cancion':     cancion,
        'prev_id':     prev_id,
        'next_id':     next_id,
        'id_playlist': id_playlist,
        'id_album':    id_album,
        'back_url':    back_url,
    })



def agregar_cancion(request):
    usuario_id  = request.session.get('usuario_id')
    usuario_rol = request.session.get('usuario_rol')
    db = get_db()

    if usuario_rol == 1:
        pipeline = [{"$group": {"_id": "$album.id_album", "titulo_album": {"$first": "$album.titulo_album"}}}]
    else:
        pipeline = [
            {"$match": {"artista.id_usuario_mashi": usuario_id}},
            {"$group": {"_id": "$album.id_album", "titulo_album": {"$first": "$album.titulo_album"}}}
        ]
    albumes_raw = list(db.canciones.aggregate(pipeline))
    albumes = [{'ID_Album': a['_id'], 'Titulo_Album': a['titulo_album']} for a in albumes_raw if a['_id']]

    if request.method == 'POST':
        titulo    = request.POST.get('titulo')
        id_album  = int(request.POST.get('id_album'))
        duracion  = int(request.POST.get('duracion'))
        archivo   = request.FILES.get('archivo_mp3')
        ruta_db   = 'Pendiente.mp3'

        if archivo:
            carpeta = os.path.join(settings.BASE_DIR, 'media', 'canciones')
            os.makedirs(carpeta, exist_ok=True)
            with open(os.path.join(carpeta, archivo.name), 'wb+') as f:
                for chunk in archivo.chunks():
                    f.write(chunk)
            ruta_db = 'canciones/' + archivo.name

        album_ref = db.canciones.find_one({"album.id_album": id_album}, {"album": 1})
        titulo_album = album_ref['album']['titulo_album'] if album_ref else ''

        # SOLUCIÓN 2: Buscar el nombre del artista
        usuario = db.usuarios.find_one({"_id": usuario_id})
        nombre_artistico = usuario.get('artista', {}).get('nombre_artistico', '') if usuario else ''
        
        # Si el usuario es antiguo y no tiene el nombre guardado en su perfil, lo sacamos de otra canción suya
        if not nombre_artistico:
            cancion_previa = db.canciones.find_one({"artista.id_usuario_mashi": usuario_id})
            if cancion_previa:
                nombre_artistico = cancion_previa.get('artista', {}).get('nombre_artistico', '')

        ultimo = db.canciones.find_one(sort=[("_id", -1)])
        nuevo_id = (ultimo['_id'] + 1) if ultimo else 401

        db.canciones.insert_one({
            "_id": nuevo_id,
            "titulo": titulo,
            "ruta_archivo": ruta_db,
            "duracion_segundos": duracion,
            "peso_mb": 3.5,
            "album": {"id_album": id_album, "titulo_album": titulo_album},
            "artista": {"nombre_artistico": nombre_artistico, "id_usuario_mashi": usuario_id},
            "generos": []
        })
        return redirect('lista_canciones')

    return render(request, 'biblioteca/agregar_cancion.html', {'albumes': albumes})


def editar_cancion(request, id_canto, id_album=None):
    db = get_db()

    if request.method == 'POST':
        titulo          = request.POST.get('titulo')
        id_album_origen = request.POST.get('id_album_origen')

        db.canciones.update_one(
            {"_id": id_canto},
            {"$set": {"titulo": titulo}}
        )

        if id_album_origen and id_album_origen != 'None':
            return redirect('detalle_album', id_album=int(id_album_origen))
        return redirect('lista_canciones')

    c = db.canciones.find_one({"_id": id_canto})
    if not c:
        return redirect('lista_canciones')

    cancion = {
        'ID_Canto':      c['_id'],
        'Titulo':        c.get('titulo', ''),
        'Album_ID_Album': c.get('album', {}).get('id_album', ''),
        'Duracion_Segundos': c.get('duracion_segundos', 0)
    }

    return render(request, 'biblioteca/editar_cancion.html', {
        'cancion': cancion,
        'id_album_origen': id_album
    })


def eliminar_cancion(request, id_canto):
    db = get_db()
    # Quitar de todas las playlists
    db.playlists.update_many(
        {},
        {"$pull": {"canciones_incrustadas": {"id_canto": id_canto}}}
    )
    # Quitar reproducciones
    db.reproducciones.delete_many({"cancion_id": id_canto})
    # Eliminar la canción
    db.canciones.delete_one({"_id": id_canto})

    next_url = request.GET.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('lista_canciones')


# ============================================================
# ÁLBUMES
# ============================================================

def agregar_album(request):
    usuario_id = request.session.get('usuario_id')
    db = get_db()

    if request.method == 'POST':
        titulo_album = request.POST.get('titulo_album')

        # Obtener el siguiente ID del álbum
        ultimo_album = db.canciones.find(
            {"album.id_album": {"$exists": True}}
        ).sort([("album.id_album", -1)]).limit(1)

        ultimo_album = list(ultimo_album)

        if ultimo_album:
            nuevo_id_album = ultimo_album[0]["album"]["id_album"] + 1
        else:
            nuevo_id_album = 301

        # Obtener el siguiente _id disponible para la colección canciones
        ultimo_doc = db.canciones.find_one(sort=[("_id", -1)])
        nuevo_id_placeholder = (ultimo_doc["_id"] + 1) if ultimo_doc else 99001

        # Datos del artista
        usuario = db.usuarios.find_one({"_id": usuario_id})
        nombre_artistico = (
            usuario.get("artista", {}).get("nombre_artistico", "")
            if usuario else ""
        )

        # Obtener portada desde Spotify
        url_portada = obtener_portada_spotify(
            titulo_album,
            nombre_artistico
        )

        # Crear placeholder del álbum
        db.canciones.insert_one({
            "_id": nuevo_id_placeholder,
            "titulo": f"__album_placeholder_{nuevo_id_album}",
            "ruta_archivo": "",
            "duracion_segundos": 0,
            "peso_mb": 0,
            "album": {
                "id_album": nuevo_id_album,
                "titulo_album": titulo_album,
                "url_portada": url_portada,
                "fecha_lanzamiento": datetime.now().strftime("%Y-%m-%d")
            },
            "artista": {
                "nombre_artistico": nombre_artistico,
                "id_usuario_mashi": usuario_id
            },
            "generos": [],
            "es_placeholder": True
        })

        return redirect('mi_biblioteca')

    return render(request, 'biblioteca/agregar_album.html')

def eliminar_album(request, id_album):
    db = get_db()
    # Solo eliminar si no tiene canciones reales
    canciones_reales = db.canciones.count_documents({
        "album.id_album": id_album,
        "es_placeholder": {"$ne": True}
    })
    if canciones_reales == 0:
        db.canciones.delete_many({"album.id_album": id_album})
    return redirect('mi_biblioteca')


def detalle_album(request, id_album):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('iniciar_sesion')

    db = get_db()

    # Info del álbum (desde cualquier canción del álbum)
    ref = db.canciones.find_one({"album.id_album": id_album})
    if not ref:
        return redirect('mi_biblioteca')

    album = {
        'Titulo_Album':     ref['album'].get('titulo_album', ''),
        'Nombre_Artistico': ref.get('artista', {}).get('nombre_artistico', ''),
        'URL_Portada':      ref['album'].get('url_portada', '')
    }

    # Canciones reales del álbum
    canciones_raw = list(db.canciones.find({
        "album.id_album": id_album,
        "es_placeholder": {"$ne": True}
    }))
    
    canciones = []
    for c in canciones_raw:
        canciones.append({
            'ID_Canto':         c['_id'],
            'Titulo':           c.get('titulo', ''),
            'Titulo_Album':     c.get('album', {}).get('titulo_album', ''),
            'Ruta_Archivo':     c.get('ruta_archivo', ''),
            'Nombre_Artistico': c.get('artista', {}).get('nombre_artistico', ''),
            # AQUÍ APLICAMOS LA OPTIMIZACIÓN
            'Portada':          obtener_o_guardar_portada(c)
        })

    return render(request, 'biblioteca/detalle_album.html', {
        'album':    album,
        'canciones': canciones,
        'id_album': id_album
    })


# ============================================================
# MI BIBLIOTECA — PLAYLISTS
# ============================================================

def mi_biblioteca(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('iniciar_sesion')

    db = get_db()

    # Crear playlist
    if request.method == 'POST':
        nombre = request.POST.get('nombre_playlist', '').strip()
        if nombre:
            ultimo = db.playlists.find_one(sort=[("_id", -1)])
            nuevo_id = (ultimo['_id'] + 1) if ultimo else 1
            db.playlists.insert_one({
                "_id":               nuevo_id,
                "nombre_playlist":   nombre,
                "fecha_creacion":    datetime.now().strftime('%Y-%m-%d'),
                "usuario_id":        usuario_id,
                "canciones_incrustadas": []
            })
        return redirect('mi_biblioteca')

    # Playlists del usuario
    playlists_raw = list(db.playlists.find({"usuario_id": usuario_id}))
    playlists = [{'ID_Playlist': p['_id'], 'Nombre_Playlist': p['nombre_playlist']} for p in playlists_raw]

    # Álbumes del artista (canciones únicas por album agrupadas)
    usuario = db.usuarios.find_one({"_id": usuario_id})
    mis_albumes = []
    if usuario and usuario.get('perfil', {}).get('id_perfil') in [1, 2]:
        pipeline = [
            {"$match": {"artista.id_usuario_mashi": usuario_id}},
            {"$group": {
                "_id":         "$album.id_album",
                "Titulo_Album": {"$first": "$album.titulo_album"},
                "URL_Portada":  {"$first": "$album.url_portada"}
            }}
        ]
        for a in db.canciones.aggregate(pipeline):
            if a['_id']:
                mis_albumes.append({
                    'ID_Album':    a['_id'],
                    'Titulo_Album': a.get('Titulo_Album', ''),
                    'URL_Portada': a.get('URL_Portada', '')
                })

    return render(request, 'biblioteca/mi_biblioteca.html', {
        'playlists':  playlists,
        'mis_albumes': mis_albumes
    })


def detalle_playlist(request, id_playlist):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('iniciar_sesion')

    db = get_db()
    pl = db.playlists.find_one({"_id": id_playlist, "usuario_id": usuario_id})
    if not pl:
        return redirect('mi_biblioteca')

    nombre_playlist = pl.get('nombre_playlist', '')
    ids_canciones   = [s['id_canto'] for s in pl.get('canciones_incrustadas', [])]

    canciones = []
    for cid in ids_canciones:
        c = db.canciones.find_one({"_id": cid})
        if c:
            canciones.append({
                'ID_Canto':         c['_id'],
                'Titulo':           c.get('titulo', ''),
                'Titulo_Album':     c.get('album', {}).get('titulo_album', ''),
                'Nombre_Artistico': c.get('artista', {}).get('nombre_artistico', ''),
                # AQUÍ APLICAMOS LA OPTIMIZACIÓN
                'Portada':          obtener_o_guardar_portada(c)
            })

    return render(request, 'biblioteca/detalle_playlist.html', {
        'nombre_playlist': nombre_playlist,
        'id_playlist':     id_playlist,
        'canciones':       canciones
    })


def eliminar_playlist(request, id_playlist):
    usuario_id = request.session.get('usuario_id')
    if usuario_id:
        db = get_db()
        db.playlists.delete_one({"_id": id_playlist, "usuario_id": usuario_id})
    return redirect('mi_biblioteca')


def agregar_a_playlist(request):
    if request.method == 'POST':
        id_canto    = int(request.POST.get('id_canto'))
        id_playlist = int(request.POST.get('id_playlist'))
        db = get_db()

        # Verificar que no esté ya
        pl = db.playlists.find_one({"_id": id_playlist})
        ya_existe = any(s['id_canto'] == id_canto for s in pl.get('canciones_incrustadas', [])) if pl else False

        if not ya_existe:
            db.playlists.update_one(
                {"_id": id_playlist},
                {"$push": {"canciones_incrustadas": {"id_canto": id_canto}}}
            )
    return redirect('lista_canciones')


def eliminar_de_playlist(request, id_playlist, id_canto):
    usuario_id = request.session.get('usuario_id')
    if usuario_id:
        db = get_db()
        db.playlists.update_one(
            {"_id": id_playlist, "usuario_id": usuario_id},
            {"$pull": {"canciones_incrustadas": {"id_canto": id_canto}}}
        )
    return redirect('detalle_playlist', id_playlist=id_playlist)


# ============================================================
# REPRODUCCIONES Y REGALÍAS
# ============================================================

def registrar_reproduccion(request):
    if request.method == 'POST':
        usuario_id = request.session.get('usuario_id')
        if not usuario_id:
            return JsonResponse({'ok': False})

        id_canto = int(request.POST.get('id_canto'))
        segundos = int(request.POST.get('segundos'))

        db = get_db()
        ultimo = db.reproducciones.find_one(sort=[("_id", -1)])
        nuevo_id = (ultimo['_id'] + 1) if ultimo else 1

        db.reproducciones.insert_one({
            "_id":        nuevo_id,
            "usuario_id": usuario_id,
            "cancion_id": id_canto,
            "segundos_escuchados": segundos,
            "fecha_hora": datetime.now()
        })

    return JsonResponse({'ok': True})


def regalias(request):
    usuario_id  = request.session.get('usuario_id')
    usuario_rol = request.session.get('usuario_rol')
    if not usuario_id:
        return redirect('iniciar_sesion')
    if usuario_rol not in [1, 2]:
        return redirect('lista_canciones')

    db       = get_db()
    TARIFA   = 0.005
    mes_actual = datetime.now().strftime('%m-%Y')
    anio     = datetime.now().year
    mes      = datetime.now().month

    # Canciones del artista
    canciones_artista = [c['_id'] for c in db.canciones.find({"artista.id_usuario_mashi": usuario_id}, {"_id": 1})]

    # Streams válidos este mes (>= 30 seg)
    inicio_mes = datetime(anio, mes, 1)
    streams_mes = db.reproducciones.count_documents({
        "cancion_id":           {"$in": canciones_artista},
        "segundos_escuchados":  {"$gte": 30},
        "fecha_hora":           {"$gte": inicio_mes}
    })
    ingresos_mes = round(streams_mes * TARIFA, 2)

    # Total histórico desde liquidaciones
    liq_total = list(db.liquidaciones.find({"artista_usuario_id": usuario_id}))
    total_historico = round(sum(float(l.get('monto_generado', 0)) for l in liq_total), 2)

    # Gráfica: últimas 6 liquidaciones
    liq_rows = sorted(liq_total, key=lambda x: x.get('mes_anio', ''))[-6:]
    meses_labels    = json.dumps([l['mes_anio'] for l in liq_rows] or [mes_actual])
    ingresos_por_mes = json.dumps([float(l.get('monto_generado', 0)) for l in liq_rows] or [0])

    # Streams por álbum este mes
    pipeline = [
        {"$match": {
            "cancion_id":          {"$in": canciones_artista},
            "segundos_escuchados": {"$gte": 30},
            "fecha_hora":          {"$gte": inicio_mes}
        }},
        {"$lookup": {
            "from":         "canciones",
            "localField":   "cancion_id",
            "foreignField": "_id",
            "as":           "cancion_info"
        }},
        {"$unwind": "$cancion_info"},
        {"$group": {
            "_id":   "$cancion_info.album.titulo_album",
            "total": {"$sum": 1}
        }},
        {"$sort": {"total": -1}}
    ]
    album_rows   = list(db.reproducciones.aggregate(pipeline))
    max_streams  = max((r['total'] for r in album_rows), default=1)
    rendimiento_albumes = [{
        'Titulo_Album':  r['_id'],
        'total_streams': r['total'],
        'ingresos':      round(r['total'] * TARIFA, 2),
        'porcentaje':    round((r['total'] / max_streams) * 100, 1)
    } for r in album_rows]

    albumes_labels  = json.dumps([r['Titulo_Album'] for r in rendimiento_albumes])
    albumes_streams = json.dumps([r['total_streams'] for r in rendimiento_albumes])

    # Historial de liquidaciones del artista
    liquidaciones = [{
        'Mes_Anio':              l.get('mes_anio', ''),
        'Total_Streams_Validos': l.get('total_streams_validos', 0),
        'Monto_Generado':        l.get('monto_generado', 0),
        'Estado_Pago':           l.get('estado_pago', 'Pendiente')
    } for l in sorted(liq_total, key=lambda x: x.get('mes_anio', ''), reverse=True)]

    return render(request, 'biblioteca/regalias.html', {
        'mes_actual':       mes_actual,
        'streams_mes':      streams_mes,
        'ingresos_mes':     ingresos_mes,
        'total_historico':  total_historico,
        'rendimiento_albumes': rendimiento_albumes,
        'liquidaciones':    liquidaciones,
        'meses_labels':     meses_labels,
        'ingresos_por_mes': ingresos_por_mes,
        'albumes_labels':   albumes_labels,
        'albumes_streams':  albumes_streams,
    })


def regalias_admin(request):
    usuario_id  = request.session.get('usuario_id')
    usuario_rol = request.session.get('usuario_rol')
    if not usuario_id or usuario_rol != 1:
        return redirect('lista_canciones')

    db       = get_db()
    TARIFA   = 0.005
    mes_actual = datetime.now().strftime('%m-%Y')
    anio     = datetime.now().year
    mes      = datetime.now().month
    inicio_mes = datetime(anio, mes, 1)

    # Streams válidos globales este mes
    streams_totales = db.reproducciones.count_documents({
        "segundos_escuchados": {"$gte": 30},
        "fecha_hora":          {"$gte": inicio_mes}
    })
    total_a_pagar_mes = round(streams_totales * TARIFA, 2)

    # Total histórico pagado en la plataforma
    liq_todas = list(db.liquidaciones.find({}))
    total_historico_plataforma = round(sum(float(l.get('monto_generado', 0)) for l in liq_todas), 2)

    # Gráfica global: pagos por mes (últimos 6)
    from collections import defaultdict
    pagos_mes_dict = defaultdict(float)
    for l in liq_todas:
        pagos_mes_dict[l.get('mes_anio', '')] += float(l.get('monto_generado', 0))
    ultimos_6 = sorted(pagos_mes_dict.items())[-6:]
    meses_labels = json.dumps([x[0] for x in ultimos_6] or [mes_actual])
    pagos_por_mes = json.dumps([x[1] for x in ultimos_6] or [0])

    # Rendimiento por artista este mes
    pipeline = [
        {"$match": {
            "segundos_escuchados": {"$gte": 30},
            "fecha_hora":          {"$gte": inicio_mes}
        }},
        {"$lookup": {
            "from":         "canciones",
            "localField":   "cancion_id",
            "foreignField": "_id",
            "as":           "cancion_info"
        }},
        {"$unwind": "$cancion_info"},
        {"$group": {
            "_id":   "$cancion_info.artista.nombre_artistico",
            "total": {"$sum": 1}
        }},
        {"$sort": {"total": -1}}
    ]
    artistas_rows = list(db.reproducciones.aggregate(pipeline))
    max_s = max((r['total'] for r in artistas_rows), default=1)
    rendimiento_artistas = [{
        'Nombre_Artistico': r['_id'],
        'total_streams':    r['total'],
        'monto_a_pagar':    round(r['total'] * TARIFA, 2),
        'porcentaje':       round((r['total'] / max_s) * 100, 1)
    } for r in artistas_rows]

    artistas_labels  = json.dumps([r['Nombre_Artistico'] for r in rendimiento_artistas])
    artistas_streams = json.dumps([r['total_streams'] for r in rendimiento_artistas])

    # Historial global liquidaciones
    liquidaciones_globales = []
    for l in sorted(liq_todas, key=lambda x: x.get('_id', 0), reverse=True)[:50]:
        # Buscar nombre artista
        usuario = db.usuarios.find_one({"_id": l.get('artista_usuario_id')})
        nombre  = usuario.get('artista', {}).get('nombre_artistico', '?') if usuario else '?'
        liquidaciones_globales.append({
            'ID_Liquidacion':        l['_id'],
            'Nombre_Artistico':      nombre,
            'Mes_Anio':              l.get('mes_anio', ''),
            'Total_Streams_Validos': l.get('total_streams_validos', 0),
            'Monto_Generado':        l.get('monto_generado', 0),
            'Estado_Pago':           l.get('estado_pago', 'Pendiente')
        })

    # POST: generar liquidación o marcar pagado
    mensaje = None
    error   = False
    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'liquidar':
            mes_anio = request.POST.get('mes_anio', mes_actual)
            tarifa   = float(request.POST.get('tarifa', 0.005))
            try:
                partes = mes_anio.split('-')
                m, a   = int(partes[0]), int(partes[1])
                inicio = datetime(a, m, 1)
                fin    = datetime(a, m + 1, 1) if m < 12 else datetime(a + 1, 1, 1)

                # Agrupar streams por artista en ese período
                pipeline_liq = [
                    {"$match": {
                        "segundos_escuchados": {"$gte": 30},
                        "fecha_hora":          {"$gte": inicio, "$lt": fin}
                    }},
                    {"$lookup": {"from": "canciones", "localField": "cancion_id", "foreignField": "_id", "as": "c"}},
                    {"$unwind": "$c"},
                    {"$group": {
                        "_id":   "$c.artista.id_usuario_mashi",
                        "total": {"$sum": 1}
                    }}
                ]
                grupos = list(db.reproducciones.aggregate(pipeline_liq))
                ultimo_liq = db.liquidaciones.find_one(sort=[("_id", -1)])
                next_id    = (ultimo_liq['_id'] + 1) if ultimo_liq else 1

                for g in grupos:
                    monto = round(g['total'] * tarifa, 2)
                    db.liquidaciones.insert_one({
                        "_id":                   next_id,
                        "artista_usuario_id":    g['_id'],
                        "mes_anio":              mes_anio,
                        "total_streams_validos": g['total'],
                        "monto_generado":        monto,
                        "estado_pago":           "Pendiente"
                    })
                    next_id += 1

                mensaje = f"Liquidación {mes_anio} generada para {len(grupos)} artistas."
            except Exception as e:
                mensaje = f"Error: {e}"
                error   = True

        elif accion == 'marcar_pagado':
            id_liq = int(request.POST.get('id_liquidacion'))
            db.liquidaciones.update_one({"_id": id_liq}, {"$set": {"estado_pago": "Pagado"}})
            mensaje = "Liquidación marcada como pagada."

        return redirect('regalias_admin')

    return render(request, 'biblioteca/regalias_admin.html', {
        'mes_actual':                mes_actual,
        'streams_totales_mes':       streams_totales,
        'total_a_pagar_mes':         total_a_pagar_mes,
        'total_historico_plataforma': total_historico_plataforma,
        'rendimiento_artistas':      rendimiento_artistas,
        'liquidaciones_globales':    liquidaciones_globales,
        'meses_labels':              meses_labels,
        'pagos_por_mes':             pagos_por_mes,
        'artistas_labels':           artistas_labels,
        'artistas_streams':          artistas_streams,
        'mensaje':                   mensaje,
        'error':                     error,
    })