# places/api/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from ..models import (
    Place, PlaceImage, PlaceVideo,
    Trail, TrailPlace,
    CheckIn,
    Comment, Vote, Favorite,
    Badge, UserBadge,
    Challenge, UserChallengeCompletion,
    Notification,
    UserProfile, ExpertArea,
    Category,
    TourPackage, TourOffering, TourItineraryDay,
)


# ─────────────────────────────────────────────────────────
# Auth / User
# ─────────────────────────────────────────────────────────

class RegisterSerializer(serializers.ModelSerializer):
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label="Confirm password")

    class Meta:
        model  = User
        fields = ['username', 'email', 'password', 'password2']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class UserBasicSerializer(serializers.ModelSerializer):
    """Lightweight user info — used inside nested serializers."""
    avatar = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'username', 'first_name', 'last_name', 'avatar']

    def get_avatar(self, obj):
        request = self.context.get('request')
        try:
            profile = obj.userprofile
            if profile.avatar and request:
                return request.build_absolute_uri(profile.avatar.url)
        except UserProfile.DoesNotExist:
            pass
        return None


class ExpertAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ExpertArea
        fields = ['id', 'name', 'description']


class UserProfileSerializer(serializers.ModelSerializer):
    user         = UserBasicSerializer(read_only=True)
    expert_areas = ExpertAreaSerializer(many=True, read_only=True)
    avatar_url   = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = [
            'user', 'avatar_url', 'bio', 'location', 'website',
            'show_email', 'show_location',
            'is_trusted', 'is_local_expert', 'expert_areas',
            'points', 'level',
        ]

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name  = serializers.CharField(source='user.last_name',  required=False)
    email      = serializers.EmailField(source='user.email',      required=False)

    class Meta:
        model  = UserProfile
        fields = [
            'avatar', 'bio', 'location', 'website',
            'show_email', 'show_location',
            'allow_messages', 'email_notifications',
            'push_notifications', 'weekly_digest',
            'first_name', 'last_name', 'email',
        ]

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        instance.user.save()
        return super().update(instance, validated_data)


# ─────────────────────────────────────────────────────────
# Category
# ─────────────────────────────────────────────────────────

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Category
        fields = ['id', 'name', 'slug']


# ─────────────────────────────────────────────────────────
# Place
# ─────────────────────────────────────────────────────────

class PlaceImageSerializer(serializers.ModelSerializer):
    image_url   = serializers.SerializerMethodField()
    uploaded_by = UserBasicSerializer(read_only=True)

    class Meta:
        model  = PlaceImage
        fields = ['id', 'image_url', 'uploaded_by', 'is_challenge_photo',
                  'challenge_description', 'created_at']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class PlaceVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlaceVideo
        fields = ['id', 'url', 'platform', 'thumbnail_url', 'created_at']


class PlaceListSerializer(serializers.ModelSerializer):
    """Compact — used in lists / map pins."""
    category       = CategorySerializer(many=True, read_only=True)
    image_url      = serializers.SerializerMethodField()
    average_rating = serializers.FloatField(read_only=True)

    class Meta:
        model  = Place
        fields = [
            'id', 'name', 'slug', 'description',
            'latitude', 'longitude', 'image_url',
            'category', 'difficulty', 'safety_rating',
            'average_rating', 'visit_count', 'status',
        ]

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class PlaceDetailSerializer(PlaceListSerializer):
    """Full detail — used on place detail screen."""
    images         = PlaceImageSerializer(many=True, read_only=True)
    videos         = PlaceVideoSerializer(many=True, read_only=True)
    created_by     = UserBasicSerializer(read_only=True)
    is_favorited   = serializers.SerializerMethodField()
    user_checkin   = serializers.SerializerMethodField()

    class Meta(PlaceListSerializer.Meta):
        fields = PlaceListSerializer.Meta.fields + [
            'legends_stories', 'accessibility_info', 'best_time_to_visit',
            'approval_votes', 'rejection_votes',
            'images', 'videos', 'created_by',
            'is_favorited', 'user_checkin', 'created_at',
        ]

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(user=request.user, place=obj).exists()
        return False

    def get_user_checkin(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            ci = CheckIn.objects.filter(user=request.user, place=obj).first()
            if ci:
                return CheckInSerializer(ci, context=self.context).data
        return None


class PlaceCreateSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), many=True
    )

    class Meta:
        model  = Place
        fields = [
            'name', 'description', 'legends_stories',
            'latitude', 'longitude', 'image',
            'category', 'difficulty', 'safety_rating',
            'accessibility_info', 'best_time_to_visit',
        ]

    def create(self, validated_data):
        categories = validated_data.pop('category', [])
        place = Place.objects.create(
            created_by=self.context['request'].user,
            status='pending',
            **validated_data
        )
        place.category.set(categories)
        return place


# ─────────────────────────────────────────────────────────
# Comments
# ─────────────────────────────────────────────────────────

class CommentSerializer(serializers.ModelSerializer):
    user    = UserBasicSerializer(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model  = Comment
        fields = ['id', 'user', 'text', 'rating', 'votes', 'replies', 'created_at']

    def get_replies(self, obj):
        qs = obj.replies.all()
        return CommentSerializer(qs, many=True, context=self.context).data


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Comment
        fields = ['text', 'rating']


# ─────────────────────────────────────────────────────────
# Check-in
# ─────────────────────────────────────────────────────────

class CheckInSerializer(serializers.ModelSerializer):
    place     = PlaceListSerializer(read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model  = CheckIn
        fields = [
            'id', 'place', 'photo_url', 'notes',
            'location_verified', 'points_awarded', 'created_at',
        ]

    def get_photo_url(self, obj):
        request = self.context.get('request')
        if obj.photo_proof and request:
            return request.build_absolute_uri(obj.photo_proof.url)
        return None


class CheckInCreateSerializer(serializers.ModelSerializer):
    place_slug        = serializers.SlugRelatedField(
        slug_field='slug', queryset=Place.objects.filter(status='approved'),
        source='place', write_only=True
    )
    location_verified = serializers.BooleanField(default=False)

    class Meta:
        model  = CheckIn
        fields = ['place_slug', 'photo_proof', 'notes', 'location_verified']


# ─────────────────────────────────────────────────────────
# Trails
# ─────────────────────────────────────────────────────────

class TrailPlaceSerializer(serializers.ModelSerializer):
    place = PlaceListSerializer(read_only=True)

    class Meta:
        model  = TrailPlace
        fields = ['order', 'place', 'notes', 'distance_from_previous']


class TrailListSerializer(serializers.ModelSerializer):
    category    = CategorySerializer(many=True, read_only=True)
    place_count = serializers.IntegerField(source='places.count', read_only=True)
    cover_url   = serializers.SerializerMethodField()
    created_by  = UserBasicSerializer(read_only=True)

    class Meta:
        model  = Trail
        fields = [
            'id', 'name', 'description', 'difficulty',
            'distance', 'estimated_duration', 'category',
            'cover_url', 'place_count', 'is_public',
            'required_points', 'created_by', 'created_at',
        ]

    def get_cover_url(self, obj):
        request = self.context.get('request')
        if obj.cover_image and request:
            return request.build_absolute_uri(obj.cover_image.url)
        return None


class TrailDetailSerializer(TrailListSerializer):
    trail_places  = TrailPlaceSerializer(many=True, read_only=True,
                                         source='trailplace_set')
    user_progress = serializers.SerializerMethodField()

    class Meta(TrailListSerializer.Meta):
        fields = TrailListSerializer.Meta.fields + ['trail_places', 'user_progress']

    def get_user_progress(self, obj):
        request = self.context.get('request')
        if not (request and request.user.is_authenticated):
            return None
        from ..views import get_trail_progress
        return get_trail_progress(request.user, obj)


# ─────────────────────────────────────────────────────────
# Badges
# ─────────────────────────────────────────────────────────

class BadgeSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    is_earned = serializers.SerializerMethodField()
    earned_at = serializers.SerializerMethodField()

    class Meta:
        model  = Badge
        fields = [
            'id', 'name', 'description', 'icon', 'image_url',
            'category', 'points_required', 'is_earned', 'earned_at',
        ]

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def get_is_earned(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserBadge.objects.filter(user=request.user, badge=obj).exists()
        return False

    def get_earned_at(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            ub = UserBadge.objects.filter(user=request.user, badge=obj).first()
            return ub.earned_at if ub else None
        return None


# ─────────────────────────────────────────────────────────
# Challenges
# ─────────────────────────────────────────────────────────

class ChallengeSerializer(serializers.ModelSerializer):
    user_progress  = serializers.SerializerMethodField()
    user_completed = serializers.SerializerMethodField()

    class Meta:
        model  = Challenge
        fields = [
            'id', 'title', 'description', 'challenge_type',
            'reward_points', 'start_date', 'end_date',
            'user_progress', 'user_completed',
        ]

    def get_user_progress(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from ..views import get_challenge_progress
            return get_challenge_progress(request.user, obj)
        return None

    def get_user_completed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return UserChallengeCompletion.objects.filter(
                user=request.user, challenge=obj
            ).exists()
        return False


# ─────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────

class NotificationSerializer(serializers.ModelSerializer):
    icon       = serializers.CharField(source='get_icon',       read_only=True)
    icon_color = serializers.CharField(source='get_icon_color', read_only=True)

    class Meta:
        model  = Notification
        fields = [
            'id', 'title', 'message', 'notification_type',
            'is_read', 'icon', 'icon_color', 'created_at',
        ]


# ─────────────────────────────────────────────────────────
# Tours
# ─────────────────────────────────────────────────────────

class TourOfferingSerializer(serializers.ModelSerializer):
    class Meta:
        model  = TourOffering
        fields = ['id', 'name', 'icon']


class TourItineraryDaySerializer(serializers.ModelSerializer):
    highlights_list = serializers.ListField(source='highlights_list', read_only=True)

    class Meta:
        model  = TourItineraryDay
        fields = [
            'day_number', 'title', 'description',
            'distance_km', 'highlights_list',
        ]


class TourListSerializer(serializers.ModelSerializer):
    image_url      = serializers.SerializerMethodField()
    offerings      = TourOfferingSerializer(many=True, read_only=True)
    trail_count    = serializers.IntegerField(source='trails.count', read_only=True)
    duration_display = serializers.CharField(read_only=True)

    class Meta:
        model  = TourPackage
        fields = [
            'id', 'name', 'slug', 'description',
            'image_url', 'duration_display', 'price_lkr',
            'event_date', 'event_time',
            'starting_location', 'ending_location',
            'trail_count', 'offerings',
        ]

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None


class TourDetailSerializer(TourListSerializer):
    trails        = TrailListSerializer(many=True, read_only=True)
    itinerary     = TourItineraryDaySerializer(
        many=True, read_only=True, source='itinerary_days'
    )
    contact_list     = serializers.ListField(read_only=True)
    what_to_bring_list = serializers.ListField(read_only=True)

    class Meta(TourListSerializer.Meta):
        fields = TourListSerializer.Meta.fields + [
            'trails', 'itinerary',
            'contact_list', 'what_to_bring_list',
        ]


# ─────────────────────────────────────────────────────────
# Leaderboard
# ─────────────────────────────────────────────────────────

class LeaderboardSerializer(serializers.ModelSerializer):
    username   = serializers.CharField(source='user.username')
    full_name  = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = ['username', 'full_name', 'avatar_url', 'points', 'level']

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username

    def get_avatar_url(self, obj):
        request = self.context.get('request')
        if obj.avatar and request:
            return request.build_absolute_uri(obj.avatar.url)
        return None