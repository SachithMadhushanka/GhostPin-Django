from django.contrib import admin
from .models import (
    UserProfile,
    ExpertArea,
    Place,
    PlaceImage,
    CheckIn,
    Trail,
    TrailPlace,
    Comment,
    Vote,
    Favorite,
    Badge,
    UserBadge,
    Challenge,
    Notification,
    Category,
    PlaceVideo,
    TourPackage,
    TourOffering,
    TourItineraryDay,
)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "is_trusted",
        "is_local_expert",
        "points",
        "level",
        "created_at",
    ]
    list_filter = ["is_trusted", "is_local_expert", "level", "created_at"]
    search_fields = ["user__username", "user__email", "bio"]
    filter_horizontal = ["expert_areas"]
    actions = ["make_trusted", "remove_trusted", "make_local_expert"]

    def make_trusted(self, request, queryset):
        queryset.update(is_trusted=True)
        self.message_user(request, f"{queryset.count()} users marked as trusted.")
    make_trusted.short_description = "Mark selected users as trusted"

    def remove_trusted(self, request, queryset):
        queryset.update(is_trusted=False)
        self.message_user(request, f"{queryset.count()} users removed from trusted.")
    remove_trusted.short_description = "Remove trusted status from selected users"

    def make_local_expert(self, request, queryset):
        queryset.update(is_local_expert=True)
        self.message_user(request, f"{queryset.count()} users marked as local experts.")
    make_local_expert.short_description = "Mark selected users as local experts"


@admin.register(ExpertArea)
class ExpertAreaAdmin(admin.ModelAdmin):
    list_display = ["name", "created_at"]
    search_fields = ["name", "description"]


class PlaceImageInline(admin.TabularInline):
    model = PlaceImage
    extra = 1
    readonly_fields = ["uploaded_by", "created_at"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "get_categories",
        "difficulty",
        "created_by",
        "status",
        "approval_votes",
        "rejection_votes",
        "visit_count",
        "created_at",
    ]
    list_filter = ["status", "difficulty", "created_at", "category"]
    search_fields = ["name", "description", "legends_stories"]
    actions = ["approve_places", "reject_places"]
    inlines = [PlaceImageInline]
    readonly_fields = [
        "approval_votes", "rejection_votes", "visit_count", "created_at", "updated_at",
    ]
    filter_horizontal = ("category",)
    fieldsets = (
        ("Basic Information", {"fields": ("name", "description", "legends_stories", "image")}),
        ("Location", {"fields": ("latitude", "longitude")}),
        ("Categorization", {"fields": ("category", "difficulty")}),
        ("Additional Info", {"fields": ("accessibility_info", "best_time_to_visit", "safety_rating")}),
        ("Status & Metadata", {
            "fields": (
                "created_by", "status", "approval_votes", "rejection_votes",
                "visit_count", "created_at", "updated_at",
            )
        }),
    )

    def get_categories(self, obj):
        return ", ".join([cat.name for cat in obj.category.all()])
    get_categories.short_description = "Categories"

    def approve_places(self, request, queryset):
        queryset.update(status="approved")
        self.message_user(request, f"{queryset.count()} places approved.")
    approve_places.short_description = "Approve selected places"

    def reject_places(self, request, queryset):
        queryset.update(status="rejected")
        self.message_user(request, f"{queryset.count()} places rejected.")
    reject_places.short_description = "Reject selected places"


@admin.register(PlaceImage)
class PlaceImageAdmin(admin.ModelAdmin):
    list_display = ["place", "uploaded_by", "is_challenge_photo", "created_at"]
    list_filter = ["is_challenge_photo", "created_at"]
    search_fields = ["place__name", "uploaded_by__username", "challenge_description"]


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ["user", "place", "location_verified", "points_awarded", "created_at"]
    list_filter = ["location_verified", "created_at"]
    search_fields = ["user__username", "place__name"]
    readonly_fields = ["created_at"]


class TrailPlaceInline(admin.TabularInline):
    model = TrailPlace
    extra = 1
    ordering = ["order"]


@admin.register(Trail)
class TrailAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "is_public", "difficulty", "created_at"]
    list_filter = ["is_public", "difficulty", "created_at"]
    search_fields = ["name", "description"]
    inlines = [TrailPlaceInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["user", "place", "rating", "votes", "parent", "created_at"]
    list_filter = ["rating", "created_at"]
    search_fields = ["text", "user__username", "place__name"]
    readonly_fields = ["votes", "created_at"]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["user", "place", "comment", "vote_type", "created_at"]
    list_filter = ["vote_type", "created_at"]
    search_fields = ["user__username"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ["user", "place", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__username", "place__name"]


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["name", "badge_preview", "category", "points_required", "is_active", "created_at"]
    list_filter = ["is_active", "category", "created_at"]
    search_fields = ["name", "description"]

    def badge_preview(self, obj):
        if obj.image:
            from django.utils.html import format_html
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius:50%;object-fit:cover;">',
                obj.image.url,
            )
        return obj.icon
    badge_preview.short_description = "Icon/Image"


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ["user", "badge", "earned_at"]
    list_filter = ["badge", "earned_at"]
    search_fields = ["user__username", "badge__name"]


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ["title", "challenge_type", "reward_points", "start_date", "end_date", "is_active"]
    list_filter = ["challenge_type", "is_active", "start_date", "end_date"]
    search_fields = ["title", "description"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user", "title", "notification_type", "is_read", "created_at"]
    list_filter = ["notification_type", "is_read", "created_at"]
    search_fields = ["user__username", "title", "message"]
    actions = ["mark_as_read", "mark_as_unread"]

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} notifications marked as read.")
    mark_as_read.short_description = "Mark selected notifications as read"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)
        self.message_user(request, f"{queryset.count()} notifications marked as unread.")
    mark_as_unread.short_description = "Mark selected notifications as unread"


@admin.register(PlaceVideo)
class PlaceVideoAdmin(admin.ModelAdmin):
    list_display = ["place", "platform", "uploaded_by", "created_at"]
    list_filter = ["platform", "created_at"]
    search_fields = ["place__name", "uploaded_by__username", "url"]


@admin.register(TourOffering)
class TourOfferingAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon']
    search_fields = ['name']


# ── TourItineraryDay inline for TourPackage ───────────────
class TourItineraryDayInline(admin.StackedInline):
    model = TourItineraryDay
    extra = 1
    fields = ['day_number', 'title', 'description', 'distance_km', 'highlights']
    ordering = ['day_number']


@admin.register(TourPackage)
class TourPackageAdmin(admin.ModelAdmin):
    list_display  = [
        'name', 'price_lkr', 'duration_hours',
        'event_date', 'event_time',
        'starting_location', 'is_active', 'created_by', 'created_at',
    ]
    list_filter   = ['is_active', 'event_date']
    search_fields = ['name', 'description', 'starting_location', 'ending_location']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['trails', 'offerings']
    inlines = [TourItineraryDayInline]

    fieldsets = (
        ('Core Info', {
            'fields': ('name', 'slug', 'description', 'image', 'is_active', 'created_by'),
        }),
        ('Logistics', {
            'fields': ('duration_hours', 'price_lkr'),
        }),
        ('Event Date & Time', {
            'fields': ('event_date', 'event_time'),
            'description': 'Leave blank if this is not a fixed-date event.',
        }),
        ('Route', {
            'fields': ('starting_location', 'ending_location'),
        }),
        ('What to Bring', {
            'fields': ('what_to_bring',),
            'description': 'Enter one item per line.',
        }),
        ('Trails & Offerings', {
            'fields': ('trails', 'offerings'),
        }),
        ('Booking', {
            'fields': ('contact_numbers',),
            'description': 'Enter one phone number per line.',
        }),
    )


@admin.register(TourItineraryDay)
class TourItineraryDayAdmin(admin.ModelAdmin):
    list_display  = ['tour', 'day_number', 'title', 'distance_km']
    list_filter   = ['tour']
    search_fields = ['tour__name', 'title', 'description']
    ordering      = ['tour', 'day_number']


# ─────────────────────────────────────────────────────────
# SEED: Run this in Django shell to create default offerings
# python manage.py shell
# ─────────────────────────────────────────────────────────
#
# from places.models import TourOffering
# defaults = [
#     ('Breakfast',         'fas fa-coffee'),
#     ('Tea Break',         'fas fa-mug-hot'),
#     ('Lunch',             'fas fa-utensils'),
#     ('Dinner',            'fas fa-concierge-bell'),
#     ('Camping Equipment', 'fas fa-campground'),
#     ('Tour Guide',        'fas fa-user-tie'),
#     ('Pickup & Drop-off', 'fas fa-shuttle-van'),
#     ('Transport',         'fas fa-bus'),
#     ('First Aid Kit',     'fas fa-first-aid'),
#     ('Photography',       'fas fa-camera'),
# ]
# for name, icon in defaults:
#     TourOffering.objects.get_or_create(name=name, defaults={'icon': icon})
# print("Done!")