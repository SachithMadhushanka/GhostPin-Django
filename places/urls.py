from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "places"

urlpatterns = [
    # Core URLs
    path("", views.home, name="home"),
    path("place/add/", views.add_place, name="add_place"),
    path("place/<slug:slug>/", views.place_detail, name="place_detail"),
    path("place/<slug:slug>/edit/", views.edit_place, name="edit_place"),
    path("place/<slug:slug>/check-in/", views.check_in, name="check_in"),
    path("place/<slug:slug>/checkins/", views.place_checkins, name="place_checkins"),
    path("route-planner/", views.route_planner, name="route_planner"),
    # User URLs
    path("user/<str:username>/", views.profile, name="profile"),
    path("favorites/", views.favorites, name="favorites"),
    path("notifications/", views.notifications, name="notifications"),
    path("check-ins/", views.check_ins, name="check_ins"),
    # API Endpoints
    path(
        "api/notifications/<int:pk>/read/",
        views.mark_notification_read,
        name="mark_notification_read",
    ),
    path(
        "api/notifications/mark-all-read/",
        views.mark_all_notifications_read,
        name="mark_all_notifications_read",
    ),
    path(
        "api/notifications/<int:pk>/",
        views.delete_notification,
        name="delete_notification",
    ),
    path(
        "api/notifications/clear-all/",
        views.clear_all_notifications,
        name="clear_all_notifications",
    ),
    path(
        "api/notifications/check-new/",
        views.check_new_notifications,
        name="check_new_notifications",
    ),
    # URLs
    path("nearby/", views.nearby_places_view, name="nearby_places"),
    path("api/nearby-places/", views.get_nearby_places, name="get_nearby_places"),
    path("search/", views.search_results, name="search_results"),
    path("edit/", views.edit_profile, name="edit_profile"),
    path("about/", views.about, name="about"),
    #   Trails URLs
    path("trails/", views.trails, name="trails"),
    path("trail/create/", views.create_trail, name="create_trail"),
    path("trail/<int:pk>/", views.trail_detail, name="trail_detail"),
    path("trail/<int:pk>/edit/", views.edit_trail, name="edit_trail"),
    # Gamification URLs
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("challenges/", views.challenges, name="challenges"),
    path("badges/", views.badges, name="badges"),
    # Challenge management (staff only)
    path("challenges/create/", views.create_challenge, name="create_challenge"),
    path("challenges/<int:pk>/edit/", views.edit_challenge, name="edit_challenge"),
    path(
        "challenges/<int:pk>/delete/", views.delete_challenge, name="delete_challenge"
    ),
    path(
        "challenges/<int:pk>/toggle/",
        views.toggle_challenge_active,
        name="toggle_challenge_active",
    ),
    # AJAX URLs
    path(
        "place/<slug:slug>/toggle-favorite/",
        views.toggle_favorite,
        name="toggle_favorite",
    ),
    path("place/<slug:slug>/vote/", views.vote_place, name="vote_place"),
    # Admin URLs
    path("review/", views.review_places, name="review_places"),
    path(
        "place/<slug:slug>/update-status/",
        views.update_place_status,
        name="update_status",
    ),
    path("analytics/", views.analytics, name="analytics"),
    # PWA URLs
    path("manifest.json", views.manifest, name="manifest"),
    path("service-worker.js", views.service_worker, name="service_worker"),
    # Main check-in detail view
    path("checkin/<int:pk>/", views.checkin_detail, name="checkin_detail"),
    # API endpoints for voting and replies
    path(
        "api/comments/<int:comment_id>/vote/", views.vote_comment, name="vote_comment"
    ),
    path("api/comments/reply/", views.reply_comment, name="reply_comment"),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    # Tours
    path('tours/', views.tour_list, name='tour_list'),
    path('tours/create/', views.create_tour, name='create_tour'),
    path('tours/<slug:slug>/', views.tour_detail, name='tour_detail'),
    path('tours/<slug:slug>/edit/', views.edit_tour, name='edit_tour'),
    path('tours/<slug:slug>/delete/', views.delete_tour, name='delete_tour'),
    path('tours/<slug:slug>/toggle/', views.toggle_tour_active, name='toggle_tour_active'),
]
