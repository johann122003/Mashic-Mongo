from django.urls import path
from . import views   

urlpatterns = [
    path('', views.lista_canciones, name='lista_canciones'),
    path('agregar/', views.agregar_cancion, name='agregar_cancion'),
    path('eliminar/<int:id_canto>/', views.eliminar_cancion, name='eliminar_cancion'),
    path('editar/<int:id_canto>/', views.editar_cancion, name='editar_cancion'),
    path('cancion/<int:id_canto>/', views.detalle_cancion, name='detalle_cancion'),
    path('login/', views.iniciar_sesion, name='iniciar_sesion'),
    path('logout/', views.cerrar_sesion, name='cerrar_sesion'),
    path('mi-biblioteca/', views.mi_biblioteca, name='mi_biblioteca'),
    path('eliminar-playlist/<int:id_playlist>/', views.eliminar_playlist, name='eliminar_playlist'),
    path('agregar-a-playlist/', views.agregar_a_playlist, name='agregar_a_playlist'),
    path('quitar-de-playlist/<int:id_playlist>/<int:id_canto>/', views.eliminar_de_playlist, name='eliminar_de_playlist'),
    path('playlist/<int:id_playlist>/', views.detalle_playlist, name='detalle_playlist'),
    path('cancion/<int:id_canto>/<int:id_playlist>/', views.detalle_cancion, name='detalle_cancion'),
    path('agregar-album/', views.agregar_album, name='agregar_album'),
    path('eliminar-album/<int:id_album>/', views.eliminar_album, name='eliminar_album'),
    path('album/<int:id_album>/', views.detalle_album, name='detalle_album'),
    path('cancion/<int:id_canto>/album/<int:id_album>/', views.detalle_cancion, name='detalle_cancion_album'),
    path('editar/<int:id_canto>/album/<int:id_album>/', views.editar_cancion, name='editar_cancion_album'),
    path('registrar-reproduccion/', views.registrar_reproduccion, name='registrar_reproduccion'),
    path('regalias/', views.regalias, name='regalias'),
    path('panel-regalias/', views.regalias_admin, name='regalias_admin'),
    path('registro/', views.crear_cuenta, name='crear_cuenta'),
]