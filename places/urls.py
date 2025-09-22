from django.urls import path
from . import views

app_name = 'places'

urlpatterns = [
    # Core URLs
    path('', views.home, name='home'),
    path('place/<int:pk>/', views.place_detail, name='place_detail'),
    path('place/add/', views.add_place, name='add_place'),
    path('place/<int:pk>/edit/', views.edit_place, name='edit_place'),
    path('place/<int:pk>/check-in/', views.check_in, name='check_in'),
    path('place/<int:pk>/checkins/', views.place_checkins, name='place_checkins'),
    path('route-planner/', views.route_planner, name='route_planner'),
    
    # User URLs
    path('user/<str:username>/', views.profile, name='profile'),
    path('favorites/', views.favorites, name='favorites'),
    path('notifications/', views.notifications, name='notifications'),
    path('check-ins/', views.check_ins, name='check_ins'),

    # API Endpoints
    path('api/notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('api/notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('api/notifications/<int:pk>/', views.delete_notification, name='delete_notification'),
    path('api/notifications/clear-all/', views.clear_all_notifications, name='clear_all_notifications'),
    path('api/notifications/check-new/', views.check_new_notifications, name='check_new_notifications'),

    # URLs
    path('nearby/', views.nearby_places_view, name='nearby_places'),
    path('api/nearby-places/', views.get_nearby_places, name='get_nearby_places'),
    path('search/', views.search_results, name='search_results'),
    path('edit/', views.edit_profile, name='edit_profile'),

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
    path('place/<int:pk>/update-status/', views.update_place_status, name='update_status'),
    path('analytics/', views.analytics, name='analytics'),
    
    # PWA URLs
    path('manifest.json', views.manifest, name='manifest'),
    path('service-worker.js', views.service_worker, name='service_worker'),

    # Main check-in detail view
    path('checkin/<int:pk>/', views.checkin_detail, name='checkin_detail'),

    # API endpoints for voting and replies
    path('api/comments/<int:comment_id>/vote/', views.vote_comment, name='vote_comment'),
    path('api/comments/reply/', views.reply_comment, name='reply_comment'),
]

