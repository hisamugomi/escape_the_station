from django.urls import path
from game_api import views

urlpatterns = [
    path('', views.game_view, name='game'),
    path('api/map', views.get_map, name='get_map'),
    path('api/action', views.handle_action, name='handle_action'),
]
