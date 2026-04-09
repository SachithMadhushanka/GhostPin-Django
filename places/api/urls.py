# places/api/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    RegisterView, LogoutView,
    MyProfileView, UserProfileView,
    PlaceListView, PlaceDetailView, PlaceCreateView,
    NearbyPlacesView, TrendingPlacesView,
    ToggleFavoriteView, FavoritesListView, VotePlaceView,
    PlaceCommentsView,
    CheckInView, MyCheckInsView,
    TrailListView, TrailDetailView,
    BadgeListView, ChallengeListView,
    NotificationListView, MarkNotificationReadView,
    MarkAllNotificationsReadView, UnreadNotificationCountView,
    TourListView, TourDetailView,
    LeaderboardView, CategoryListView, HomeStatsView,
)

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────
    path('auth/register/',      RegisterView.as_view(),          name='api-register'),
    path('auth/login/',         TokenObtainPairView.as_view(),   name='api-login'),
    path('auth/refresh/',       TokenRefreshView.as_view(),      name='api-token-refresh'),
    path('auth/logout/',        LogoutView.as_view(),            name='api-logout'),

    # ── Profile ───────────────────────────────────────────
    path('profile/me/',                     MyProfileView.as_view(),   name='api-my-profile'),
    path('profile/<str:username>/',         UserProfileView.as_view(), name='api-user-profile'),

    # ── Places ────────────────────────────────────────────
    path('places/',                         PlaceListView.as_view(),       name='api-places'),
    path('places/add/',                     PlaceCreateView.as_view(),     name='api-place-add'),
    path('places/trending/',                TrendingPlacesView.as_view(),  name='api-trending'),
    path('places/nearby/',                  NearbyPlacesView.as_view(),    name='api-nearby'),
    path('places/favorites/',               FavoritesListView.as_view(),   name='api-favorites'),
    path('places/<slug:slug>/',             PlaceDetailView.as_view(),     name='api-place-detail'),
    path('places/<slug:slug>/favorite/',    ToggleFavoriteView.as_view(),  name='api-toggle-favorite'),
    path('places/<slug:slug>/vote/',        VotePlaceView.as_view(),       name='api-vote-place'),
    path('places/<slug:slug>/comments/',    PlaceCommentsView.as_view(),   name='api-place-comments'),

    # ── Check-ins ─────────────────────────────────────────
    path('checkin/',                        CheckInView.as_view(),         name='api-checkin'),
    path('checkins/mine/',                  MyCheckInsView.as_view(),      name='api-my-checkins'),

    # ── Trails ────────────────────────────────────────────
    path('trails/',                         TrailListView.as_view(),       name='api-trails'),
    path('trails/<int:pk>/',               TrailDetailView.as_view(),     name='api-trail-detail'),

    # ── Badges & Challenges ───────────────────────────────
    path('badges/',                         BadgeListView.as_view(),       name='api-badges'),
    path('challenges/',                     ChallengeListView.as_view(),   name='api-challenges'),

    # ── Notifications ─────────────────────────────────────
    path('notifications/',                  NotificationListView.as_view(),         name='api-notifications'),
    path('notifications/read-all/',         MarkAllNotificationsReadView.as_view(), name='api-notif-read-all'),
    path('notifications/unread-count/',     UnreadNotificationCountView.as_view(),  name='api-notif-count'),
    path('notifications/<int:pk>/read/',    MarkNotificationReadView.as_view(),     name='api-notif-read'),

    # ── Tours ─────────────────────────────────────────────
    path('tours/',                          TourListView.as_view(),        name='api-tours'),
    path('tours/<slug:slug>/',             TourDetailView.as_view(),      name='api-tour-detail'),

    # ── Misc ──────────────────────────────────────────────
    path('leaderboard/',                    LeaderboardView.as_view(),     name='api-leaderboard'),
    path('categories/',                     CategoryListView.as_view(),    name='api-categories'),
    path('stats/',                          HomeStatsView.as_view(),       name='api-stats'),
]