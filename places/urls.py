from django.urls import path
from . import views

urlpatterns = [
    # Core URLs
    path('', views.home, name='home'),
    path('place/<int:pk>/', views.place_detail, name='place_detail'),
    path('place/add/', views.add_place, name='add_place'),
    path('place/<int:pk>/edit/', views.edit_place, name='edit_place'),
    path('place/<int:pk>/check-in/', views.check_in, name='check_in'),
    
    # User URLs
    path('user/<str:username>/', views.profile, name='profile'),
    path('favorites/', views.favorites, name='favorites'),
    path('notifications/', views.notifications, name='notifications'),
    path('check-ins/', views.check_ins, name='check_ins'),

    # URLs
    path('nearby/', views.nearby_places_view, name='nearby_places'),
    path('search/', views.search_results, name='search_results'),

    # Collections URLs
    path('collections/', views.collections, name='collections'),
    path('collection/<int:pk>/', views.collection_detail, name='collection_detail'),
    path('collection/create/', views.create_collection, name='create_collection'),
    
    # Gamification URLs
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('challenges/', views.challenges, name='challenges'),
    path('badges/', views.badges, name='badges'),
    
    # AJAX URLs
    path('place/<int:pk>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('place/<int:pk>/vote/', views.vote_place, name='vote_place'),
    
    # Admin URLs
    path('review/', views.review_places, name='review_places'),
    path('place/<int:pk>/update-status/', views.update_place_status, name='update_place_status'),
    path('analytics/', views.analytics, name='analytics'),
    
    # PWA URLs
    path('manifest.json', views.manifest, name='manifest'),
    path('service-worker.js', views.service_worker, name='service_worker'),
]

