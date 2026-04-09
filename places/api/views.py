# places/api/views.py
import math
from django.utils import timezone
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, F

from rest_framework import generics, status, permissions, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken

from geopy.distance import geodesic

from ..models import (
    Place, PlaceImage, CheckIn, Comment, Vote, Favorite,
    Trail, TrailPlace,
    Badge, UserBadge,
    Challenge, UserChallengeCompletion,
    Notification,
    UserProfile, Category,
    TourPackage,
)
from ..views import (
    evaluate_badges_for_user,
    evaluate_challenges_for_user,
    award_trail_completions,
    _recalculate_level,
    get_challenge_progress,
    CHECKIN_COOLDOWN_SECONDS,
)
from .serializers import (
    RegisterSerializer,
    UserProfileSerializer, UserProfileUpdateSerializer,
    PlaceListSerializer, PlaceDetailSerializer, PlaceCreateSerializer,
    CommentSerializer, CommentCreateSerializer,
    CheckInSerializer, CheckInCreateSerializer,
    TrailListSerializer, TrailDetailSerializer,
    BadgeSerializer,
    ChallengeSerializer,
    NotificationSerializer,
    TourListSerializer, TourDetailSerializer,
    LeaderboardSerializer,
    CategorySerializer,
)


# ─────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/"""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Auto-create profile + welcome notification
        profile, _ = UserProfile.objects.get_or_create(user=user)
        Notification.objects.create(
            user=user,
            title="Welcome to Expearls!",
            message="Thanks for signing up! Start exploring and adding places.",
            notification_type="welcome",
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access':  str(refresh.access_token),
            'user': {
                'id':       user.id,
                'username': user.username,
                'email':    user.email,
            }
        }, status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklist the refresh token."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()
            return Response({'detail': 'Logged out.'})
        except Exception:
            return Response({'detail': 'Invalid token.'}, status=400)


# ─────────────────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────────────────

class MyProfileView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/profile/me/"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserProfileUpdateSerializer
        return UserProfileSerializer

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class UserProfileView(generics.RetrieveAPIView):
    """GET /api/profile/<username>/"""
    serializer_class   = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_object(self):
        user = get_object_or_404(User, username=self.kwargs['username'])
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile


# ─────────────────────────────────────────────────────────
# Places
# ─────────────────────────────────────────────────────────

class PlaceListView(generics.ListAPIView):
    """GET /api/places/  — supports ?search=, ?category=, ?difficulty=, ?sort="""
    serializer_class   = PlaceListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Place.objects.filter(status='approved').prefetch_related('category')

        q = self.request.query_params.get('search', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        category = self.request.query_params.get('category', '')
        if category:
            qs = qs.filter(category__slug=category)

        difficulty = self.request.query_params.get('difficulty', '')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        sort = self.request.query_params.get('sort', '-created_at')
        allowed_sorts = ['name', '-name', 'visit_count', '-visit_count',
                         'created_at', '-created_at']
        if sort in allowed_sorts:
            qs = qs.order_by(sort)

        return qs


class PlaceDetailView(generics.RetrieveAPIView):
    """GET /api/places/<slug>/"""
    serializer_class   = PlaceDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field       = 'slug'

    def get_queryset(self):
        return Place.objects.filter(status='approved').prefetch_related(
            'category', 'images', 'videos'
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Increment visit count
        Place.objects.filter(pk=instance.pk).update(visit_count=F('visit_count') + 1)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class PlaceCreateView(generics.CreateAPIView):
    """POST /api/places/add/"""
    serializer_class   = PlaceCreateSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def perform_create(self, serializer):
        place = serializer.save()
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        profile.points += 20
        profile.save()
        _recalculate_level(profile)
        evaluate_badges_for_user(self.request.user)
        Notification.objects.create(
            user=self.request.user,
            title="Place Submitted",
            message=f'"{place.name}" is pending review.',
            notification_type="place_added",
            related_place=place,
        )


class NearbyPlacesView(APIView):
    """GET /api/places/nearby/?lat=&lng=&distance=10"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        try:
            lat      = float(request.query_params.get('lat'))
            lng      = float(request.query_params.get('lng'))
            max_km   = float(request.query_params.get('distance', 10))
        except (TypeError, ValueError):
            return Response({'error': 'lat, lng are required.'}, status=400)

        lat_range = max_km / 111
        lng_range = max_km / (111 * math.cos(math.radians(lat)))
        candidates = Place.objects.filter(
            status='approved',
            latitude__range=(lat - lat_range,  lat + lat_range),
            longitude__range=(lng - lng_range, lng + lng_range),
        ).prefetch_related('category')

        results = []
        for place in candidates:
            dist = geodesic((lat, lng), (place.latitude, place.longitude)).km
            if dist <= max_km:
                data = PlaceListSerializer(place, context={'request': request}).data
                data['distance_km'] = round(dist, 2)
                results.append(data)

        results.sort(key=lambda x: x['distance_km'])
        return Response(results)


class TrendingPlacesView(generics.ListAPIView):
    """GET /api/places/trending/"""
    serializer_class   = PlaceListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Place.objects.filter(status='approved').annotate(
            vote_count=Count('vote', distinct=True),
            ci_count=Count('checkin', distinct=True),
        ).order_by('-visit_count', '-ci_count', '-vote_count')[:20]


class ToggleFavoriteView(APIView):
    """POST /api/places/<slug>/favorite/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        place = get_object_or_404(Place, slug=slug, status='approved')
        fav, created = Favorite.objects.get_or_create(user=request.user, place=place)
        if not created:
            fav.delete()
        return Response({'favorited': created})


class FavoritesListView(generics.ListAPIView):
    """GET /api/places/favorites/"""
    serializer_class   = PlaceListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        fav_ids = Favorite.objects.filter(
            user=self.request.user
        ).values_list('place_id', flat=True)
        return Place.objects.filter(pk__in=fav_ids, status='approved')


class VotePlaceView(APIView):
    """POST /api/places/<slug>/vote/  body: {"vote_type": "up"|"down"}"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, slug):
        place     = get_object_or_404(Place, slug=slug, status='approved')
        vote_type = request.data.get('vote_type')
        if vote_type not in ('up', 'down'):
            return Response({'error': 'vote_type must be up or down.'}, status=400)

        vote, created = Vote.objects.get_or_create(
            user=request.user, place=place,
            defaults={'vote_type': vote_type}
        )
        if not created:
            if vote.vote_type == vote_type:
                vote.delete()
            else:
                vote.vote_type = vote_type
                vote.save()

        Place.objects.filter(pk=place.pk).update(
            approval_votes=Vote.objects.filter(place=place, vote_type='up').count(),
            rejection_votes=Vote.objects.filter(place=place, vote_type='down').count(),
        )
        place.refresh_from_db()
        return Response({
            'approval_votes':  place.approval_votes,
            'rejection_votes': place.rejection_votes,
        })


# ─────────────────────────────────────────────────────────
# Comments
# ─────────────────────────────────────────────────────────

class PlaceCommentsView(generics.ListCreateAPIView):
    """GET / POST /api/places/<slug>/comments/"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CommentCreateSerializer
        return CommentSerializer

    def get_queryset(self):
        place = get_object_or_404(Place, slug=self.kwargs['slug'])
        return Comment.objects.filter(place=place, parent=None).prefetch_related('replies')

    def perform_create(self, serializer):
        place = get_object_or_404(Place, slug=self.kwargs['slug'])
        serializer.save(user=self.request.user, place=place)
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        profile.points += 5
        profile.save()
        _recalculate_level(profile)
        evaluate_badges_for_user(self.request.user)


# ─────────────────────────────────────────────────────────
# Check-ins
# ─────────────────────────────────────────────────────────

class CheckInView(APIView):
    """POST /api/checkin/  — create a new check-in"""
    permission_classes = [permissions.IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = CheckInCreateSerializer(
            data=request.data, context={'request': request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        place = serializer.validated_data['place']

        # Already checked in?
        if CheckIn.objects.filter(user=request.user, place=place).exists():
            return Response({'detail': 'Already checked in here.'}, status=400)

        # Cooldown check
        last = CheckIn.objects.filter(user=request.user).order_by('-created_at').first()
        if last:
            elapsed = (timezone.now() - last.created_at).total_seconds()
            if elapsed < CHECKIN_COOLDOWN_SECONDS:
                wait = int(CHECKIN_COOLDOWN_SECONDS - elapsed)
                return Response(
                    {'detail': f'Please wait {wait}s before your next check-in.'},
                    status=429
                )

        checkin = serializer.save(user=request.user)

        # Points
        points = 10
        if checkin.photo_proof:
            points += 5
        if checkin.location_verified:
            points += 5
        checkin.points_awarded = points
        checkin.save()

        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.points += points
        profile.save()
        _recalculate_level(profile)

        award_trail_completions(request.user, place)
        evaluate_challenges_for_user(request.user)
        evaluate_badges_for_user(request.user)

        return Response(
            CheckInSerializer(checkin, context={'request': request}).data,
            status=201
        )


class MyCheckInsView(generics.ListAPIView):
    """GET /api/checkins/mine/"""
    serializer_class   = CheckInSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CheckIn.objects.filter(
            user=self.request.user
        ).select_related('place').order_by('-created_at')


# ─────────────────────────────────────────────────────────
# Trails
# ─────────────────────────────────────────────────────────

class TrailListView(generics.ListAPIView):
    """GET /api/trails/  — supports ?search=, ?difficulty=, ?category="""
    serializer_class   = TrailListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs = Trail.objects.filter(is_public=True).prefetch_related('places', 'category')

        q = self.request.query_params.get('search', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

        difficulty = self.request.query_params.get('difficulty', '')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        category = self.request.query_params.get('category', '')
        if category:
            qs = qs.filter(category__slug=category)

        return qs.order_by('-created_at')


class TrailDetailView(generics.RetrieveAPIView):
    """GET /api/trails/<pk>/"""
    serializer_class   = TrailDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Trail.objects.filter(is_public=True).prefetch_related(
            'trailplace_set__place', 'category'
        )


# ─────────────────────────────────────────────────────────
# Badges & Challenges
# ─────────────────────────────────────────────────────────

class BadgeListView(generics.ListAPIView):
    """GET /api/badges/"""
    serializer_class   = BadgeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset           = Badge.objects.filter(is_active=True).order_by('points_required')


class ChallengeListView(generics.ListAPIView):
    """GET /api/challenges/"""
    serializer_class   = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        now = timezone.now()
        return Challenge.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        ).order_by('end_date')


# ─────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────

class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/"""
    serializer_class   = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


class MarkNotificationReadView(APIView):
    """POST /api/notifications/<pk>/read/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, user=request.user)
        notif.is_read = True
        notif.save()
        return Response({'detail': 'Marked as read.'})


class MarkAllNotificationsReadView(APIView):
    """POST /api/notifications/read-all/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
        return Response({'updated': count})


class UnreadNotificationCountView(APIView):
    """GET /api/notifications/unread-count/"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).count()
        return Response({'unread_count': count})


# ─────────────────────────────────────────────────────────
# Tours
# ─────────────────────────────────────────────────────────

class TourListView(generics.ListAPIView):
    """GET /api/tours/"""
    serializer_class   = TourListSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return TourPackage.objects.filter(
            is_active=True
        ).prefetch_related('trails', 'offerings')


class TourDetailView(generics.RetrieveAPIView):
    """GET /api/tours/<slug>/"""
    serializer_class   = TourDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field       = 'slug'

    def get_queryset(self):
        return TourPackage.objects.filter(
            is_active=True
        ).prefetch_related('trails', 'offerings', 'itinerary_days')


# ─────────────────────────────────────────────────────────
# Leaderboard & Categories
# ─────────────────────────────────────────────────────────

class LeaderboardView(generics.ListAPIView):
    """GET /api/leaderboard/"""
    serializer_class   = LeaderboardSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from ..models import UserProfile
        return UserProfile.objects.select_related('user').order_by('-points')[:50]


class CategoryListView(generics.ListAPIView):
    """GET /api/categories/"""
    serializer_class   = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    queryset           = Category.objects.all().order_by('name')


# ─────────────────────────────────────────────────────────
# Stats (dashboard data for home screen)
# ─────────────────────────────────────────────────────────

class HomeStatsView(APIView):
    """GET /api/stats/ — numbers for the app home screen."""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get(self, request):
        from ..models import UserProfile
        data = {
            'total_places': Place.objects.filter(status='approved').count(),
            'total_trails': Trail.objects.filter(is_public=True).count(),
            'total_tours':  TourPackage.objects.filter(is_active=True).count(),
            'total_users':  UserProfile.objects.count(),
        }
        if request.user.is_authenticated:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            data['my_points']  = profile.points
            data['my_level']   = profile.level
            data['my_checkins'] = CheckIn.objects.filter(user=request.user).count()
            data['my_badges']  = UserBadge.objects.filter(user=request.user).count()
        return Response(data)