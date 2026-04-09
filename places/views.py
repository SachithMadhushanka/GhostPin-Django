import math
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Avg, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import now
from collections import Counter
import json
import os
import re
import logging
from django.conf import settings
from django.db.models import Count, Sum, Avg
from geopy.distance import geodesic
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.db import transaction, IntegrityError
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

from .models import (
    TrailFavorite,
    Place,
    Comment,
    PlaceImage,
    CheckIn,
    Trail,
    TrailPlace,
    TrailCompletion,
    Vote,
    Favorite,
    Badge,
    UserBadge,
    Challenge,
    Notification,
    UserProfile,
    ExpertArea,
    Category,
    PlaceVideo,
    UserChallengeCompletion,
    TourPackage,
    TourOffering,
    TourItineraryDay,
)

from .forms import (
    TrailForm,
    PlaceForm,
    CommentForm,
    PlaceImageForm,
    CheckInForm,
    UserProfileForm,
    SearchForm,
    VoteForm,
    RegisterForm,
    ChallengeForm,
    TourPackageForm,
)

from .checkin_trust import compute_photo_hash, compute_trust_score

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────

MAX_PLACES_PER_TRAIL     = 20
CHECKIN_COOLDOWN_SECONDS = 300
NOTIFICATION_HOURLY_CAP  = 5

# Points constants — kept here so the template context stays in sync
BASE_CHECKIN_POINTS    = 10
PHOTO_BONUS_POINTS     = 5
VERIFIED_BONUS_POINTS  = 5


# ─────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────

def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser


def _can_notify(user, max_per_hour=NOTIFICATION_HOURLY_CAP):
    cutoff = timezone.now() - timedelta(hours=1)
    recent = Notification.objects.filter(
        user=user,
        created_at__gte=cutoff,
    ).count()
    return recent < max_per_hour


def _recalculate_level(profile):
    """
    Recalculate and persist the user's level based on current points.
    Only writes to DB when the level actually changes.
    Call after every profile.points mutation.
    """
    if profile.points >= 1000:
        new_level = 5
    elif profile.points >= 500:
        new_level = 4
    elif profile.points >= 200:
        new_level = 3
    elif profile.points >= 50:
        new_level = 2
    else:
        new_level = 1

    if profile.level != new_level:
        profile.level = new_level
        profile.save(update_fields=['level'])


def extract_video_info(url):
    yt_match = re.search(
        r"(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})", url
    )
    if yt_match:
        video_id = yt_match.group(1)
        return "youtube", f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    if "facebook.com" in url or "fb.watch" in url:
        return "facebook", "https://www.facebook.com/images/fb_icon_325x325.png"
    if "instagram.com" in url:
        return (
            "instagram",
            "https://www.instagram.com/static/images/ico/favicon-200.png/ab6eff595bb1.png",
        )
    if "tiktok.com" in url:
        return (
            "tiktok",
            "https://sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/tiktok/webapp/main/webapp-desktop/8152caf0c8e8bc67ae0d.png",
        )
    return None, None


def get_trail_progress(user, trail):
    trail_place_ids = TrailPlace.objects.filter(trail=trail).values_list(
        "place_id", flat=True
    )
    total = len(trail_place_ids)
    if total == 0:
        return {"total": 0, "completed": 0, "percent": 0}

    completed = (
        CheckIn.objects.filter(user=user, place_id__in=trail_place_ids)
        .values("place_id")
        .distinct()
        .count()
    )
    return {
        "total":     total,
        "completed": completed,
        "percent":   round((completed / total) * 100),
    }


# ─────────────────────────────────────────────────────────
# Core views
# ─────────────────────────────────────────────────────────

def home(request):
    all_places = Place.objects.filter(status='approved').order_by('-created_at')

    paginator   = Paginator(all_places, 12)
    page_number = request.GET.get('page')
    places      = paginator.get_page(page_number)

    trending_places = Place.objects.filter(status='approved').annotate(
        vote_count    = Count('vote',     distinct=True),
        check_in_count= Count('checkin',  distinct=True),
        comment_count = Count('comments', distinct=True),
    ).order_by('-visit_count', '-check_in_count', '-vote_count')[:6]

    featured_trails = Trail.objects.filter(
        is_public=True
    ).prefetch_related('places').order_by('-created_at')[:3]

    try:
        featured_tours = TourPackage.objects.filter(
            is_active=True
        ).prefetch_related('offerings', 'trails').order_by('-created_at')[:3]
    except Exception:
        featured_tours = []

    featured_badges = Badge.objects.filter(is_active=True).order_by('points_required')[:6]

    now_ts = timezone.now()
    challenges_qs = Challenge.objects.filter(
        is_active=True,
        start_date__lte=now_ts,
        end_date__gte=now_ts,
    ).order_by('end_date')[:4]

    if request.user.is_authenticated:
        try:
            from .challenge_engine import get_challenge_progress
            active_challenges = []
            for ch in challenges_qs:
                ch.user_progress = get_challenge_progress(request.user, ch)
                active_challenges.append(ch)
        except (ImportError, Exception):
            active_challenges = list(challenges_qs)
    else:
        active_challenges = list(challenges_qs)

    top_profiles  = UserProfile.objects.select_related('user').order_by('-points')[:8]
    top_explorers = [
        {'rank': rank, 'username': p.user.username, 'profile': p}
        for rank, p in enumerate(top_profiles, start=1)
    ]

    total_places = Place.objects.filter(status='approved').count()
    total_trails = Trail.objects.filter(is_public=True).count()
    total_users  = UserProfile.objects.count()
    try:
        total_tours = TourPackage.objects.filter(is_active=True).count()
    except Exception:
        total_tours = 0

    return render(request, 'home.html', {
        'places':            places,
        'trending_places':   trending_places,
        'featured_trails':   featured_trails,
        'featured_tours':    featured_tours,
        'featured_badges':   featured_badges,
        'active_challenges': active_challenges,
        'top_explorers':     top_explorers,
        'total_places':      total_places,
        'total_trails':      total_trails,
        'total_tours':       total_tours,
        'total_users':       total_users,
    })


def place_detail(request, slug):
    place = get_object_or_404(Place, slug=slug)

    if place.status != "approved" and place.created_by != request.user:
        if not request.user.is_staff:
            messages.error(request, "This place is not available.")
            return redirect("places:home")

    related_places = (
        Place.objects.filter(status="approved", category__in=place.category.all())
        .exclude(pk=place.pk)
        .distinct()[:4]
    )

    place_videos = place.videos.all().order_by("-created_at")
    place_images = place.images.all()

    if not request.user.is_staff:
        from django.db.models import F
        Place.objects.filter(pk=place.pk).update(visit_count=F('visit_count') + 1)
        place.refresh_from_db(fields=['visit_count'])

    comments = place.comments.filter(parent=None).prefetch_related("replies")

    is_favorited = False
    user_checkin = None
    if request.user.is_authenticated:
        is_favorited = Favorite.objects.filter(user=request.user, place=place).exists()
        user_checkin = CheckIn.objects.filter(user=request.user, place=place).first()

    comment_form = CommentForm()
    if request.method == "POST" and request.user.is_authenticated:

        if "video_submit" in request.POST:
            video_url = request.POST.get("video_url", "").strip()
            if video_url:
                platform, thumbnail = extract_video_info(video_url)
                if platform:
                    PlaceVideo.objects.create(
                        place=place, uploaded_by=request.user,
                        url=video_url, platform=platform, thumbnail_url=thumbnail,
                    )
                    messages.success(request, "Video added successfully!")
                else:
                    messages.error(request, "Unsupported video platform.")
            return redirect("places:place_detail", slug=place.slug)

        elif "image_submit" in request.POST:
            image_form = PlaceImageForm(request.POST, request.FILES)
            if image_form.is_valid():
                image              = image_form.save(commit=False)
                image.place        = place
                image.uploaded_by  = request.user
                image.save()
                messages.success(request, "Image uploaded successfully!")
            else:
                messages.error(request, "Invalid image. Please try again.")
            return redirect("places:place_detail", slug=place.slug)

        elif "comment_submit" in request.POST:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment       = comment_form.save(commit=False)
                comment.user  = request.user
                comment.place = place

                checkin_id = request.POST.get("checkin_id")
                if checkin_id:
                    try:
                        comment.checkin = CheckIn.objects.get(id=checkin_id)
                    except CheckIn.DoesNotExist:
                        pass

                comment.save()

                # Rate-limit comment points — max 3 comments earn points per day
                today_start    = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
                comments_today = Comment.objects.filter(
                    user=request.user, created_at__gte=today_start
                ).count()
                if comments_today <= 3:
                    profile, _ = UserProfile.objects.get_or_create(user=request.user)
                    profile.points += 5
                    profile.save()
                    _recalculate_level(profile)
                evaluate_badges_for_user(request.user)

                messages.success(request, "Comment added successfully!")
                return redirect("places:place_detail", slug=place.slug)

    context = {
        "place":         place,
        "comments":      comments,
        "comment_form":  comment_form,
        "place_images":  place_images,
        "is_favorited":  is_favorited,
        "user_checkin":  user_checkin,
        "related_places":related_places,
        "place_videos":  place_videos,
        "image_form":    PlaceImageForm(),
    }
    return render(request, "place_detail.html", context)


@login_required
def add_place(request):
    if request.method == "POST":
        form = PlaceForm(request.POST, request.FILES)
        if form.is_valid():
            place            = form.save(commit=False)
            place.created_by = request.user
            place.status     = "pending"
            place.save()
            form.save_m2m()

            Notification.objects.create(
                user=request.user,
                title="Place Submitted",
                message=f'You added a new place: "{place.name}" and it is pending approval.',
                notification_type="place_added",
                related_place=place,
            )

            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            duplicate_exists = Place.objects.filter(
                created_by=request.user, name__iexact=place.name,
            ).exclude(pk=place.pk).exists()
            if not duplicate_exists:
                profile.points += 20
                profile.save()
                _recalculate_level(profile)
            evaluate_badges_for_user(request.user)

            messages.success(
                request,
                "Place submitted successfully! It will be reviewed by our team.",
            )
            return redirect("places:home")
    else:
        form = PlaceForm()

    return render(request, "add_place.html", {"form": form})


@login_required
def edit_place(request, slug):
    place = get_object_or_404(Place, slug=slug)

    if place.created_by != request.user and not request.user.is_staff:
        messages.error(request, "You can only edit your own places.")
        return redirect("places:place_detail", slug=place.slug)

    if request.method == "POST":
        form = PlaceForm(request.POST, request.FILES, instance=place)
        if form.is_valid():
            place            = form.save(commit=False)
            place.updated_by = request.user
            place.save()
            form.save_m2m()
            messages.success(request, "Place updated successfully!")
            return redirect("places:place_detail", slug=place.slug)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PlaceForm(instance=place)

    return render(request, "edit_place.html", {"form": form, "place": place})


# ─────────────────────────────────────────────────────────
# User views
# ─────────────────────────────────────────────────────────

@login_required
def profile(request, username):
    user    = get_object_or_404(User, username=username)
    profile, created = UserProfile.objects.get_or_create(user=user)

    user_places   = Place.objects.filter(created_by=user, status="approved")
    user_checkins = CheckIn.objects.filter(user=user)
    user_badges   = UserBadge.objects.filter(user=user)
    user_trails   = Trail.objects.filter(created_by=user, is_public=True)
    user_images   = (
        PlaceImage.objects.filter(uploaded_by=user)
        .select_related("place")
        .order_by("-created_at")
    )
    user_videos   = (
        PlaceVideo.objects.filter(uploaded_by=user)
        .select_related("place")
        .order_by("-created_at")
    )

    if profile.points >= 1000:
        new_level = 5
    elif profile.points >= 500:
        new_level = 4
    elif profile.points >= 200:
        new_level = 3
    elif profile.points >= 50:
        new_level = 2
    else:
        new_level = 1

    if profile.level != new_level:
        profile.level = new_level
        profile.save(update_fields=['level'])

    context = {
        "profile_user": user,
        "profile":      profile,
        "user_places":  user_places,
        "user_checkins":user_checkins,
        "user_badges":  user_badges,
        "user_trails":  user_trails,
        "user_images":  user_images,
        "user_videos":  user_videos,
    }
    return render(request, "profile.html", context)


@login_required
def favorites(request):
    favorites = (
        Favorite.objects.filter(user=request.user)
        .select_related("place")
        .order_by("-created_at")
    )
    category_count = (
        Category.objects.filter(
            places__in=Favorite.objects.filter(user=request.user).values("place")
        )
        .distinct()
        .count()
    )
    return render(request, "favorites.html", {
        "favorites":      favorites,
        "category_count": category_count,
    })


@login_required
def notifications(request):
    notification_list = Notification.objects.filter(user=request.user).order_by("-created_at")

    paginator           = Paginator(notification_list, 10)
    page_number         = request.GET.get("page")
    notifications_page  = paginator.get_page(page_number)
    unread_count        = notification_list.filter(is_read=False).count()

    return render(request, "notifications.html", {
        "notifications": notifications_page,
        "unread_count":  unread_count,
    })


@login_required
@require_POST
def mark_notification_read(request, pk):
    try:
        notification         = Notification.objects.get(pk=pk, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({"success": True})
    except Notification.DoesNotExist:
        return JsonResponse({"success": False, "error": "Notification not found"})


@login_required
@require_POST
def mark_all_notifications_read(request):
    updated_count = Notification.objects.filter(
        user=request.user, is_read=False
    ).update(is_read=True)
    return JsonResponse({"success": True, "updated_count": updated_count})


@login_required
def delete_notification(request, pk):
    if request.method == "DELETE":
        try:
            Notification.objects.get(pk=pk, user=request.user).delete()
            return JsonResponse({"success": True})
        except Notification.DoesNotExist:
            return JsonResponse({"success": False, "error": "Notification not found"})
    return JsonResponse({"success": False, "error": "Invalid method"})


@login_required
def clear_all_notifications(request):
    if request.method == "DELETE":
        deleted_count = Notification.objects.filter(user=request.user).count()
        Notification.objects.filter(user=request.user).delete()
        return JsonResponse({"success": True, "deleted_count": deleted_count})
    return JsonResponse({"success": False, "error": "Invalid method"})


@login_required
def check_new_notifications(request):
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"has_new": unread_count > 0, "unread_count": unread_count})


def get_streaks(checkins):
    dates = sorted(set(checkins.values_list('created_at__date', flat=True)))
    if not dates:
        return []
    streaks        = []
    current_streak = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current_streak += 1
        else:
            streaks.append(current_streak)
            current_streak = 1
    streaks.append(current_streak)
    return streaks


@login_required
def check_ins(request):
    user       = request.user
    today      = now().date()
    checkins_qs = CheckIn.objects.filter(user=user).select_related("place")

    total_points  = checkins_qs.aggregate(total=Sum("points_awarded"))["total"] or 0
    unique_places = checkins_qs.values("place").distinct().count()

    week_ago        = today - timedelta(days=7)
    month_ago       = today - timedelta(days=30)
    week_checkins   = checkins_qs.filter(created_at__date__gte=week_ago).count()
    month_checkins  = checkins_qs.filter(created_at__date__gte=month_ago).count()

    total_count       = checkins_qs.count()
    photo_checkins    = checkins_qs.exclude(photo_proof="").exclude(photo_proof__isnull=True).count()
    verified_checkins = checkins_qs.filter(location_verified=True).count()
    photo_percent     = round((photo_checkins    / total_count) * 100, 1) if total_count else 0
    verified_percent  = round((verified_checkins / total_count) * 100, 1) if total_count else 0

    streaks        = get_streaks(checkins_qs)
    longest_streak = max(streaks) if streaks else 0

    months            = checkins_qs.dates("created_at", "month")
    month_counts      = Counter([dt.strftime("%B %Y") for dt in months])
    most_active_month = month_counts.most_common(1)[0][0] if month_counts else "N/A"

    category_counts  = Counter(
        [cat.name for c in checkins_qs if c.place for cat in c.place.category.all()]
    )
    favorite_category = category_counts.most_common(1)[0][0] if category_counts else "N/A"

    recent_badges = (
        UserBadge.objects.filter(user=user)
        .select_related("badge")
        .order_by("-earned_at")[:5]
    )
    recent_milestones = [
        {"title": ub.badge.name, "date": ub.earned_at}
        for ub in UserBadge.objects.filter(user=user)
        .select_related("badge")
        .order_by("-earned_at")[:5]
    ]

    paginator   = Paginator(checkins_qs, 20)
    page_number = request.GET.get("page")
    checkins    = paginator.get_page(page_number)

    return render(request, "check_ins.html", {
        "checkins":           checkins,
        "total_count":        total_count,
        "total_points":       total_points,
        "unique_places":      unique_places,
        "week_checkins":      week_checkins,
        "month_checkins":     month_checkins,
        "photo_checkins":     photo_percent,
        "verified_checkins":  verified_percent,
        "longest_streak":     longest_streak,
        "most_active_month":  most_active_month,
        "favorite_category":  favorite_category,
        "recent_badges":      recent_badges,
        "recent_milestones":  recent_milestones,
    })


# ─────────────────────────────────────────────────────────
# Trail completion rewards
# ─────────────────────────────────────────────────────────

def award_trail_completions(user, checked_place):
    affected_trails = Trail.objects.filter(
        trailplace__place=checked_place, is_public=True
    ).distinct()

    for trail in affected_trails:
        if TrailCompletion.objects.filter(user=user, trail=trail).exists():
            continue

        progress = get_trail_progress(user, trail)
        if progress["completed"] == progress["total"] and progress["total"] > 0:
            multipliers = {"easy": 1.0, "moderate": 1.3, "challenging": 1.5}
            bonus       = int(100 * multipliers.get(trail.difficulty, 1.0))

            TrailCompletion.objects.create(user=user, trail=trail, points_awarded=bonus)

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.points += bonus
            profile.save()
            _recalculate_level(profile)
            evaluate_badges_for_user(user)

            if _can_notify(user):
                Notification.objects.create(
                    user=user,
                    title="Trail Completed! 🎉",
                    message=f'You completed "{trail.name}" and earned {bonus} bonus points!',
                    notification_type="challenge",
                    related_trail=trail,
                )

            if hasattr(trail, "completion_badge") and trail.completion_badge:
                UserBadge.objects.get_or_create(user=user, badge=trail.completion_badge)


# ─────────────────────────────────────────────────────────
# Check-in view
# ─────────────────────────────────────────────────────────

@login_required
def check_in(request, slug):
    place = get_object_or_404(Place, slug=slug, status="approved")

    # Early duplicate guard (also enforced atomically below)
    if CheckIn.objects.filter(user=request.user, place=place).exists():
        messages.info(request, "You have already checked in at this place.")
        return redirect("places:place_detail", slug=place.slug)

    if request.method == "POST":
        form = CheckInForm(request.POST, request.FILES)
        if form.is_valid():
            checkin                   = form.save(commit=False)
            checkin.user              = request.user
            checkin.place             = place
            checkin.location_verified = request.POST.get("location_verified") == "true"

            # ── Cooldown (per-user across all places) ─────────────
            last_checkin = (
                CheckIn.objects.filter(user=request.user)
                .order_by("-created_at")
                .first()
            )
            if last_checkin:
                elapsed = (timezone.now() - last_checkin.created_at).total_seconds()
                if elapsed < CHECKIN_COOLDOWN_SECONDS:
                    wait = int(CHECKIN_COOLDOWN_SECONDS - elapsed)
                    messages.warning(
                        request,
                        f"⏳ Please wait {wait} seconds before your next check-in.",
                    )
                    return redirect("places:place_detail", slug=place.slug)

            # ── Duplicate image hash check ────────────────────────
            photo_file = request.FILES.get("photo_proof")
            if photo_file:
                photo_hash = compute_photo_hash(photo_file)
                if CheckIn.objects.filter(photo_hash=photo_hash).exists():
                    messages.error(
                        request,
                        "This photo has already been used for a check-in. "
                        "Please upload a new photo taken at this location.",
                    )
                    return render(request, "check_in.html", {
                        "form":                  form,
                        "place":                 place,
                        "base_checkin_points":   BASE_CHECKIN_POINTS,
                        "photo_bonus_points":    PHOTO_BONUS_POINTS,
                        "verified_bonus_points": VERIFIED_BONUS_POINTS,
                        "max_points":            BASE_CHECKIN_POINTS + PHOTO_BONUS_POINTS + VERIFIED_BONUS_POINTS,
                    })
                checkin.photo_hash = photo_hash

            # ── Trust score + points ──────────────────────────────
            trust                  = compute_trust_score(checkin, place)
            checkin.points_awarded = trust["points"]
            checkin.trust_score    = trust["score"]

            # ── Atomic save + points award ────────────────────────
            try:
                with transaction.atomic():
                    checkin.save()   # IntegrityError on duplicate (race condition)
                    profile, _ = UserProfile.objects.select_for_update().get_or_create(
                        user=request.user
                    )
                    profile.points += checkin.points_awarded
                    profile.save(update_fields=["points"])
                    _recalculate_level(profile)
            except IntegrityError:
                messages.info(request, "You have already checked in at this place.")
                return redirect("places:place_detail", slug=place.slug)

            # ── Gamification hooks (outside transaction) ──────────
            try:
                award_trail_completions(request.user, place)
                evaluate_challenges_for_user(request.user)
                evaluate_badges_for_user(request.user)
            except Exception as exc:
                logger.warning(
                    "Gamification hooks failed for %s at %s: %s",
                    request.user.username, place.slug, exc,
                )

            # ── User-facing message ───────────────────────────────
            tier_labels = {
                "verified":   "✅ Verified",
                "likely":     "🟡 Likely Verified",
                "unverified": "⚪ Unverified",
            }
            messages.success(
                request,
                f"Checked in! You earned {checkin.points_awarded} points. "
                f"Status: {tier_labels.get(trust['tier'], '')}",
            )
            return redirect("places:place_detail", slug=place.slug)
    else:
        form = CheckInForm()

    return render(request, "check_in.html", {
        "form":                  form,
        "place":                 place,
        "base_checkin_points":   BASE_CHECKIN_POINTS,
        "photo_bonus_points":    PHOTO_BONUS_POINTS,
        "verified_bonus_points": VERIFIED_BONUS_POINTS,
        "max_points":            BASE_CHECKIN_POINTS + PHOTO_BONUS_POINTS + VERIFIED_BONUS_POINTS,
    })


# ─────────────────────────────────────────────────────────
# Trails
# ─────────────────────────────────────────────────────────

def trails(request):
    trails_qs = (
        Trail.objects.filter(is_public=True)
        .annotate(
            place_count   = Count("places",          distinct=True),
            checkin_count = Count("places__checkin", distinct=True),
        )
        .select_related("created_by")
        .prefetch_related("places", "category")
        .distinct()
    )

    search_query = request.GET.get("search", "")
    if search_query:
        trails_qs = trails_qs.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__name__icontains=search_query)
        ).distinct()

    difficulty = request.GET.get("difficulty", "")
    if difficulty and difficulty in ("easy", "moderate", "challenging"):
        trails_qs = trails_qs.filter(difficulty=difficulty)

    category = request.GET.get("category", "")
    if category:
        trails_qs = trails_qs.filter(category__slug=category).distinct()

    sort_by = request.GET.get("sort", "created_at")
    if sort_by == "name":
        trails_qs = trails_qs.order_by("name")
    elif sort_by == "places":
        trails_qs = trails_qs.order_by("-place_count")
    elif sort_by == "popularity":
        trails_qs = trails_qs.order_by("-checkin_count")
    elif sort_by == "difficulty":
        from django.db.models import Case, When, IntegerField, Value
        trails_qs = trails_qs.annotate(
            diff_order=Case(
                When(difficulty="easy",        then=Value(1)),
                When(difficulty="moderate",    then=Value(2)),
                When(difficulty="challenging", then=Value(3)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("diff_order")
    else:
        trails_qs = trails_qs.order_by("-created_at")

    paginator   = Paginator(trails_qs, 9)
    page_number = request.GET.get("page")
    trails_page = paginator.get_page(page_number)

    if request.user.is_authenticated:
        for trail in trails_page:
            trail.user_progress = get_trail_progress(request.user, trail)
    else:
        for trail in trails_page:
            trail.user_progress = None

    return render(request, "trails.html", {
        "trails":             trails_page,
        "search_query":       search_query,
        "selected_difficulty":difficulty,
        "selected_category":  category,
        "selected_sort":      sort_by,
        "difficulty_choices": Trail.DIFFICULTY_CHOICES,
        "category_choices":   Category.objects.filter(trails__isnull=False).distinct(),
        "is_paginated":       trails_page.has_other_pages(),
    })


def trail_detail(request, pk):
    trail = get_object_or_404(Trail, pk=pk)

    is_locked = False
    if trail.required_points > 0:
        if not request.user.is_authenticated:
            is_locked = True
        else:
            user_profile = getattr(request.user, "userprofile", None)
            if not request.user.is_staff and (
                user_profile is None or user_profile.points < trail.required_points
            ):
                is_locked = True

    if not trail.is_public and (
        not request.user.is_authenticated or trail.created_by != request.user
    ):
        if not (request.user.is_authenticated and request.user.is_staff):
            raise Http404("Trail not found")

    progress = get_trail_progress(request.user, trail) if request.user.is_authenticated else None

    trail_places = (
        TrailPlace.objects.filter(trail=trail)
        .select_related("place")
        .prefetch_related("place__category")
        .order_by("order")
    )

    if request.method == "POST" and request.user.is_authenticated:
        action = request.POST.get("action")

        if action == "save_trail":
            favorite, created = TrailFavorite.objects.get_or_create(
                user=request.user, trail=trail
            )
            if created:
                messages.success(request, "Trail saved to your favorites!")
            else:
                favorite.delete()
                messages.info(request, "Trail removed from your favorites.")

        elif action == "start_trail":
            if is_locked:
                messages.error(
                    request, f"You need {trail.required_points} points to start this trail."
                )
                return redirect("places:trail_detail", pk=trail.pk)

            if trail_places.exists():
                checked_ids    = set(
                    CheckIn.objects.filter(user=request.user).values_list("place_id", flat=True)
                )
                first_unchecked = next(
                    (tp for tp in trail_places if tp.place_id not in checked_ids),
                    trail_places.first(),
                )
                messages.success(request, f"Starting trail at {first_unchecked.place.name}!")
                return redirect("places:place_detail", slug=first_unchecked.place.slug)
            else:
                messages.warning(request, "This trail has no places yet.")

        elif action == "export_route":
            return _export_trail_gpx(trail, trail_places)

    total_distance = sum([tp.distance_from_previous or 0 for tp in trail_places])
    is_saved       = (
        request.user.is_authenticated
        and TrailFavorite.objects.filter(user=request.user, trail=trail).exists()
    )

    return render(request, "trail_detail.html", {
        "trail":          trail,
        "trail_places":   trail_places,
        "total_distance": total_distance,
        "estimated_time": trail.estimated_duration or "Varies",
        "can_edit":       request.user.is_authenticated
                          and (request.user == trail.created_by or request.user.is_staff),
        "progress":       progress,
        "is_locked":      is_locked,
        "is_saved":       is_saved,
    })


def _export_trail_gpx(trail, trail_places):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Expearls" xmlns="http://www.topografix.com/GPX/1/1">',
        f"  <metadata><name>{trail.name}</name></metadata>",
        "  <rte>",
        f"    <name>{trail.name}</name>",
    ]
    for tp in trail_places:
        lines.append(
            f'    <rtept lat="{tp.place.latitude}" lon="{tp.place.longitude}">'
            f"<name>{tp.place.name}</name></rtept>"
        )
    lines += ["  </rte>", "</gpx>"]
    response = HttpResponse("\n".join(lines), content_type="application/gpx+xml")
    safe_name = trail.name.replace(" ", "_").lower()
    response["Content-Disposition"] = f'attachment; filename="{safe_name}_route.gpx"'
    return response


@login_required
def create_trail(request):
    if request.method == "POST":
        form       = TrailForm(request.POST, request.FILES)
        trail_name = request.POST.get("name", "").strip()

        if Trail.objects.filter(created_by=request.user, name__iexact=trail_name).exists():
            messages.error(
                request,
                f'You already have a trail named "{trail_name}". Please choose a different name.',
            )
            available_places = Place.objects.filter(status="approved").order_by("name")
            return render(request, "create_trail.html", {
                "form": form, "available_places": available_places,
            })

        if form.is_valid():
            place_ids    = _parse_place_ids(request.POST.get("selected_places", ""))
            save_as_draft = request.POST.get("save_as_draft", False)

            if not save_as_draft and len(place_ids) == 0:
                messages.error(request, "A trail must include at least one place.")
                return render(request, "create_trail.html", {
                    "form": form,
                    "available_places": Place.objects.filter(status="approved").order_by("name"),
                })

            if len(place_ids) > MAX_PLACES_PER_TRAIL:
                messages.error(request, f"A trail can contain at most {MAX_PLACES_PER_TRAIL} places.")
                return render(request, "create_trail.html", {
                    "form": form,
                    "available_places": Place.objects.filter(status="approved").order_by("name"),
                })

            with transaction.atomic():
                trail            = form.save(commit=False)
                trail.created_by = request.user
                if save_as_draft:
                    trail.is_public = False
                trail.save()
                form.save_m2m()
                _attach_places_to_trail(trail, place_ids)

            messages.success(request, "Trail saved as draft!" if save_as_draft else "Trail created successfully!")
            return redirect("places:trail_detail", pk=trail.pk)
    else:
        form = TrailForm()

    available_places   = Place.objects.filter(status="approved").order_by("name")
    preselected_places = []
    places_param       = request.GET.get("places", "")
    if places_param:
        try:
            ids = [int(i) for i in places_param.split(",") if i.strip()]
            preselected_places = Place.objects.filter(pk__in=ids, status="approved")
        except ValueError:
            pass

    return render(request, "create_trail.html", {
        "form":               form,
        "available_places":   available_places,
        "preselected_places": preselected_places,
        "max_places":         MAX_PLACES_PER_TRAIL,
    })


@login_required
def edit_trail(request, pk):
    trail = get_object_or_404(Trail, pk=pk)

    if trail.created_by != request.user and not request.user.is_staff:
        messages.error(request, "You can only edit your own trails.")
        return redirect("places:trail_detail", pk=trail.pk)

    if request.method == "POST":
        form       = TrailForm(request.POST, request.FILES, instance=trail)
        trail_name = request.POST.get("name", "").strip()

        if (
            Trail.objects.filter(created_by=request.user, name__iexact=trail_name)
            .exclude(pk=trail.pk)
            .exists()
        ):
            messages.error(request, f'You already have another trail named "{trail_name}".')
            return render(request, "create_trail.html", {
                "form": form, "trail": trail, "is_editing": True,
                "available_places": Place.objects.filter(status="approved").order_by("name"),
                "current_places":   trail.places.all(),
                "max_places":       MAX_PLACES_PER_TRAIL,
            })

        if form.is_valid():
            place_ids = _parse_place_ids(request.POST.get("selected_places", ""))

            if len(place_ids) == 0:
                messages.error(request, "A trail must include at least one place.")
                return render(request, "create_trail.html", {
                    "form": form, "trail": trail, "is_editing": True,
                    "available_places": Place.objects.filter(status="approved").order_by("name"),
                    "current_places":   trail.places.all(),
                    "max_places":       MAX_PLACES_PER_TRAIL,
                })

            if len(place_ids) > MAX_PLACES_PER_TRAIL:
                messages.error(request, f"A trail can contain at most {MAX_PLACES_PER_TRAIL} places.")
                return render(request, "create_trail.html", {
                    "form": form, "trail": trail, "is_editing": True,
                    "available_places": Place.objects.filter(status="approved").order_by("name"),
                    "current_places":   trail.places.all(),
                    "max_places":       MAX_PLACES_PER_TRAIL,
                })

            with transaction.atomic():
                trail = form.save()
                TrailPlace.objects.filter(trail=trail).delete()
                _attach_places_to_trail(trail, place_ids)

            messages.success(request, "Trail updated successfully!")
            return redirect("places:trail_detail", pk=trail.pk)
    else:
        form = TrailForm(instance=trail)

    return render(request, "create_trail.html", {
        "form":             form,
        "trail":            trail,
        "available_places": Place.objects.filter(status="approved").order_by("name"),
        "current_places":   trail.places.all(),
        "is_editing":       True,
        "max_places":       MAX_PLACES_PER_TRAIL,
    })


def _parse_place_ids(raw):
    seen, ids = set(), []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            pid = int(part)
            if pid not in seen:
                seen.add(pid)
                ids.append(pid)
        except ValueError:
            continue
    return ids


def _attach_places_to_trail(trail, place_ids):
    place_map = {p.pk: p for p in Place.objects.filter(pk__in=place_ids, status="approved")}
    for order, place_id in enumerate(place_ids, start=1):
        if place_id in place_map:
            TrailPlace.objects.create(trail=trail, place=place_map[place_id], order=order)


# ─────────────────────────────────────────────────────────
# Gamification
# ─────────────────────────────────────────────────────────

def leaderboard(request):
    base_qs      = UserProfile.objects.select_related("user")
    total_points = base_qs.aggregate(Sum("points"))["points__sum"] or 0
    total_users  = base_qs.count()

    top_users = base_qs.annotate(
        place_count=Count("user__place", filter=Q(user__place__status="approved"))
    ).order_by("-points")[:50]

    user_rank = None
    if request.user.is_authenticated and hasattr(request.user, "userprofile"):
        higher_ranked = UserProfile.objects.filter(
            points__gt=request.user.userprofile.points
        ).count()
        user_rank = higher_ranked + 1

    return render(request, "leaderboard.html", {
        "top_users":    top_users,
        "total_users":  total_users,
        "user_rank":    user_rank,
        "total_points": total_points,
    })


# ─────────────────────────────────────────────────────────
# Challenge engine
# ─────────────────────────────────────────────────────────

def get_challenge_progress(user, challenge):
    criteria      = challenge.criteria or {}
    criteria_type = criteria.get("type", "")

    def _base_checkins():
        return CheckIn.objects.filter(
            user=user,
            created_at__gte=challenge.start_date,
            created_at__lte=challenge.end_date,
        )

    def _make_result(raw_count, threshold):
        completed = min(raw_count, threshold)
        return {
            "required":  threshold,
            "completed": completed,
            "percent":   round((completed / threshold) * 100),
            "is_done":   raw_count >= threshold,
        }

    if criteria_type == "daily_checkin":
        limit = max(int(criteria.get("limit", 1)), 1)
        from django.db.models import Count as _Count
        from django.db.models.functions import TruncDate
        daily = (
            _base_checkins()
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(cnt=_Count("id"))
            .order_by()
        )
        max_on_any_day = max((r["cnt"] for r in daily), default=0)
        return _make_result(1 if max_on_any_day >= limit else 0, 1)

    if criteria_type == "photo_checkin":
        raw = (
            _base_checkins()
            .exclude(photo_proof="").exclude(photo_proof__isnull=True)
            .count()
        )
        return _make_result(min(raw, 1), 1)

    if criteria_type == "photo_checkins":
        threshold = max(int(criteria.get("threshold", 1)), 1)
        raw = (
            _base_checkins()
            .exclude(photo_proof="").exclude(photo_proof__isnull=True)
            .count()
        )
        return _make_result(raw, threshold)

    if criteria_type == "new_checkins":
        threshold    = max(int(criteria.get("threshold", 1)), 1)
        pre_existing = CheckIn.objects.filter(
            user=user, created_at__lt=challenge.start_date
        ).values_list("place_id", flat=True)
        checkins = _base_checkins().exclude(place_id__in=pre_existing)
        slug = criteria.get("category", "").strip()
        if slug:
            checkins = checkins.filter(place__category__slug=slug)
        if criteria.get("require_photo"):
            checkins = checkins.exclude(photo_proof="").exclude(photo_proof__isnull=True)
        return _make_result(checkins.values("place_id").distinct().count(), threshold)

    if criteria_type == "checkins":
        threshold = max(int(criteria.get("threshold", 1)), 1)
        checkins  = _base_checkins()
        day_map   = {"mon":1,"tue":2,"wed":3,"thu":4,"fri":5,"sat":6,"sun":7}
        days      = [d.lower() for d in criteria.get("days", [])]
        if days:
            iso_days = [day_map[d] for d in days if d in day_map]
            if iso_days:
                django_days = {1:2,2:3,3:4,4:5,5:6,6:7,7:1}
                checkins = checkins.filter(
                    created_at__week_day__in=[django_days[i] for i in iso_days]
                )
        slug = criteria.get("category", "").strip()
        if slug:
            checkins = checkins.filter(place__category__slug=slug)
        if criteria.get("require_photo"):
            checkins = checkins.exclude(photo_proof="").exclude(photo_proof__isnull=True)
        if criteria.get("require_review"):
            reviewed_ids = Comment.objects.filter(
                user=user,
                created_at__gte=challenge.start_date,
                created_at__lte=challenge.end_date,
            ).values_list("place_id", flat=True)
            checkins = checkins.filter(place_id__in=reviewed_ids)
        return _make_result(checkins.values("place_id").distinct().count(), threshold)

    if criteria_type == "unique_categories":
        threshold = max(int(criteria.get("threshold", 1)), 1)
        place_ids = _base_checkins().values_list("place_id", flat=True).distinct()
        raw       = Category.objects.filter(places__pk__in=place_ids).distinct().count()
        return _make_result(raw, threshold)

    if criteria_type == "trail_complete":
        threshold = max(int(criteria.get("threshold", 1)), 1)
        return _make_result(TrailCompletion.objects.filter(user=user).count(), threshold)

    if criteria_type == "nearby_checkins":
        threshold = max(int(criteria.get("threshold", 1)), 1)
        return _make_result(_base_checkins().filter(location_verified=True).count(), threshold)

    # Fallback
    required  = max(int(criteria.get("visit_count", criteria.get("threshold", 1))), 1)
    raw_count = _base_checkins().values("place_id").distinct().count()
    return _make_result(raw_count, required)


def evaluate_challenges_for_user(user):
    now_ts = timezone.now()
    active_challenges = Challenge.objects.filter(
        is_active=True, start_date__lte=now_ts, end_date__gte=now_ts,
    )
    already_completed = set(
        UserChallengeCompletion.objects.filter(user=user).values_list("challenge_id", flat=True)
    )
    for challenge in active_challenges:
        if challenge.pk in already_completed:
            continue
        if get_challenge_progress(user, challenge)["is_done"]:
            _grant_challenge_reward(user, challenge)


def _grant_challenge_reward(user, challenge):
    completion, created = UserChallengeCompletion.objects.get_or_create(
        user=user, challenge=challenge,
        defaults={"points_awarded": challenge.reward_points},
    )
    if not created:
        return

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.points += challenge.reward_points
    profile.save(update_fields=["points"])
    _recalculate_level(profile)
    evaluate_badges_for_user(user)

    if _can_notify(user):
        Notification.objects.create(
            user=user,
            title="Challenge Completed! 🏆",
            message=(
                f'You completed "{challenge.title}" and earned '
                f"{challenge.reward_points} bonus points!"
            ),
            notification_type="challenge",
        )


def challenges(request):
    now_ts = timezone.now()

    active_challenges = list(
        Challenge.objects.filter(
            is_active=True, start_date__lte=now_ts, end_date__gte=now_ts,
        ).order_by("end_date")
    )
    past_challenges = Challenge.objects.filter(end_date__lt=now_ts).order_by("-end_date")[:10]

    if request.user.is_authenticated:
        completed_ids = set(
            UserChallengeCompletion.objects.filter(user=request.user).values_list("challenge_id", flat=True)
        )
        for ch in active_challenges:
            ch.user_progress = get_challenge_progress(request.user, ch)
            ch.user_completed = ch.pk in completed_ids
    else:
        for ch in active_challenges:
            ch.user_progress  = None
            ch.user_completed = False

    return render(request, "challenges.html", {
        "active_challenges": active_challenges,
        "past_challenges":   past_challenges,
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def create_challenge(request):
    if request.method == "POST":
        form = ChallengeForm(request.POST)
        if form.is_valid():
            challenge = form.save()
            messages.success(request, f'Challenge "{challenge.title}" created successfully!')
            return redirect("places:challenges")
        messages.error(request, "Please fix the errors below.")
    else:
        form = ChallengeForm()
    return render(request, "create_challenge.html", {"form": form, "action": "Create"})


@login_required
@user_passes_test(is_staff_or_superuser)
def edit_challenge(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    if request.method == "POST":
        form = ChallengeForm(request.POST, instance=challenge)
        if form.is_valid():
            form.save()
            messages.success(request, f'Challenge "{challenge.title}" updated!')
            return redirect("places:challenges")
        messages.error(request, "Please fix the errors below.")
    else:
        form = ChallengeForm(instance=challenge)
        form._load_criteria_initial()
    return render(request, "create_challenge.html", {
        "form": form, "challenge": challenge, "action": "Edit",
    })


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def delete_challenge(request, pk):
    challenge = get_object_or_404(Challenge, pk=pk)
    title     = challenge.title
    challenge.delete()
    messages.success(request, f'Challenge "{title}" deleted.')
    return redirect("places:challenges")


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def toggle_challenge_active(request, pk):
    challenge           = get_object_or_404(Challenge, pk=pk)
    challenge.is_active = not challenge.is_active
    challenge.save(update_fields=["is_active"])
    return JsonResponse({"success": True, "is_active": challenge.is_active})


# ─────────────────────────────────────────────────────────
# Badge engine
# ─────────────────────────────────────────────────────────

def get_badge_progress(user, badge):
    criteria   = badge.criteria or {}
    badge_type = criteria.get("type", "")
    threshold  = max(int(criteria.get("threshold", 1)), 1)

    if badge_type == "checkins":
        current = CheckIn.objects.filter(user=user).values("place").distinct().count()
        label   = f"{current} / {threshold} places visited"
        hint    = "Check in at more places to progress."

    elif badge_type == "places_added":
        current = Place.objects.filter(created_by=user, status="approved").count()
        label   = f"{current} / {threshold} places contributed"
        hint    = "Submit more places and get them approved."

    elif badge_type == "points":
        try:
            current = UserProfile.objects.get(user=user).points
        except UserProfile.DoesNotExist:
            current = 0
        label = f"{current} / {threshold} points"
        hint  = "Keep exploring and contributing to earn more points."

    elif badge_type == "category":
        slug    = criteria.get("slug", "")
        current = (
            CheckIn.objects.filter(user=user, place__category__slug=slug)
            .values("place").distinct().count()
        )
        label = f"{current} / {threshold} {slug} places visited"
        hint  = f"Check in at more {slug} places."

    elif badge_type == "streak":
        checkins = CheckIn.objects.filter(user=user)
        streaks  = get_streaks(checkins)
        current  = max(streaks) if streaks else 0
        label    = f"{current} / {threshold} day streak"
        hint     = "Check in on consecutive days to build your streak."

    elif badge_type == "reviews":
        current = Comment.objects.filter(user=user, rating__isnull=False).count()
        label   = f"{current} / {threshold} reviews written"
        hint    = "Leave star ratings when visiting places."

    elif badge_type == "trail_complete":
        current = TrailCompletion.objects.filter(user=user).count()
        label   = f"{current} / {threshold} trails completed"
        hint    = "Complete all places in a trail."

    elif badge_type == "photo_checkins":
        current = (
            CheckIn.objects.filter(user=user)
            .exclude(photo_proof="").exclude(photo_proof__isnull=True)
            .count()
        )
        label = f"{current} / {threshold} photo check-ins"
        hint  = "Upload photo proof when checking in."

    else:
        current = threshold if UserBadge.objects.filter(user=user, badge=badge).exists() else 0
        label   = "Special achievement"
        hint    = "Complete special activities to earn this badge."

    is_done = current >= threshold
    percent = min(round((current / threshold) * 100), 100)

    return {
        "current":     current,
        "threshold":   threshold,
        "percent":     percent,
        "is_done":     is_done,
        "label":       label,
        "action_hint": hint,
    }


def evaluate_badges_for_user(user):
    """Award any badges the user has now earned. Safe to call multiple times (idempotent)."""
    already_earned = set(
        UserBadge.objects.filter(user=user).values_list("badge_id", flat=True)
    )
    for badge in Badge.objects.filter(is_active=True):
        if badge.pk in already_earned:
            continue
        if get_badge_progress(user, badge)["is_done"]:
            _, created = UserBadge.objects.get_or_create(user=user, badge=badge)
            if created and _can_notify(user):
                Notification.objects.create(
                    user=user,
                    title="Badge Earned! 🏅",
                    message=f'You earned the "{badge.name}" badge!',
                    notification_type="badge_earned",
                )


def badges(request):
    all_badges = Badge.objects.filter(is_active=True).order_by("category", "points_required")

    earned_map   = {}
    progress_map = {}

    if request.user.is_authenticated:
        for ub in UserBadge.objects.filter(user=request.user).select_related("badge"):
            earned_map[ub.badge_id] = ub
        for badge in all_badges:
            progress_map[badge.pk] = get_badge_progress(request.user, badge)

    for badge in all_badges:
        badge.is_earned = badge.pk in earned_map
        badge.earned_at = earned_map[badge.pk].earned_at if badge.is_earned else None
        badge.progress  = progress_map.get(badge.pk)
    
    remaining_count = all_badges.count() - len(earned_map)

    return render(request, "badges.html", {
        "all_badges":         all_badges,
        "user_badges":        list(earned_map.keys()),
        "earned_count":       len(earned_map),
        "total_count":        all_badges.count(),
        "remaining_count":    remaining_count,
        "badge_category_tabs": [
            ("all",         "All Badges",   "fas fa-th"),
            ("explorer",    "Explorer",     "fas fa-map-marked-alt"),
            ("contributor", "Contributor",  "fas fa-hands-helping"),
            ("social",      "Social",       "fas fa-users"),
            ("special",     "Special",      "fas fa-star"),
        ],
    })


# ─────────────────────────────────────────────────────────
# AJAX views
# ─────────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_favorite(request, slug):
    place    = get_object_or_404(Place, slug=slug)
    favorite, created = Favorite.objects.get_or_create(user=request.user, place=place)
    if not created:
        favorite.delete()

    is_favorited = Favorite.objects.filter(user=request.user, place=place).exists()

    if request.headers.get("HX-Request"):
        html = render_to_string(
            "partials/favorite_button.html",
            {"place": place, "is_favorited": is_favorited},
            request=request,
        )
        return HttpResponse(html)
    return redirect("places:place_detail", slug=slug)


@login_required
@require_POST
def vote_place(request, slug):
    place     = get_object_or_404(Place, slug=slug)
    vote_type = request.POST.get("vote_type")

    if vote_type not in ["up", "down"]:
        return JsonResponse({"success": False, "error": "Invalid vote type"})

    vote, created = Vote.objects.get_or_create(
        user=request.user, place=place, defaults={"vote_type": vote_type}
    )
    if not created:
        if vote.vote_type == vote_type:
            vote.delete()
            return JsonResponse({"success": True, "action": "removed"})
        vote.vote_type = vote_type
        vote.save()

    place.approval_votes  = Vote.objects.filter(place=place, vote_type="up").count()
    place.rejection_votes = Vote.objects.filter(place=place, vote_type="down").count()
    place.save(update_fields=["approval_votes", "rejection_votes"])

    return JsonResponse({
        "success":         True,
        "action":          "voted",
        "approval_votes":  place.approval_votes,
        "rejection_votes": place.rejection_votes,
    })


# ─────────────────────────────────────────────────────────
# Admin views
# ─────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_staff_or_superuser)
def review_places(request):
    pending_places = Place.objects.filter(status="pending").select_related("created_by")
    return render(request, "review_places.html", {"places": pending_places})


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def update_place_status(request, slug):
    place  = get_object_or_404(Place, slug=slug)
    status = request.POST.get("status")

    if status in ["approved", "rejected"]:
        place.status = status
        place.save()

        Notification.objects.create(
            user=place.created_by,
            title=f"Place {status.title()}",
            message=(
                f'Your place "{place.name}" was {status} '
                f"by {request.user.get_full_name() or request.user.username}."
            ),
            notification_type=f"place_{status}",
            related_place=place,
        )

        if status == "approved":
            profile, _ = UserProfile.objects.get_or_create(user=place.created_by)
            already_awarded = Notification.objects.filter(
                user=place.created_by,
                notification_type="place_approved",
                related_place=place,
            ).exists()
            if not already_awarded:
                profile.points += 50
                profile.save(update_fields=["points"])
                _recalculate_level(profile)
            evaluate_badges_for_user(place.created_by)

        return JsonResponse({"success": True, "status": status})

    return JsonResponse({"success": False, "error": "Invalid status"})


@login_required
@user_passes_test(is_staff_or_superuser)
def analytics(request):
    month_ago = timezone.now() - timedelta(days=30)
    return render(request, "analytics.html", {
        "total_places":           Place.objects.count(),
        "approved_places":        Place.objects.filter(status="approved").count(),
        "pending_places":         Place.objects.filter(status="pending").count(),
        "total_users":            User.objects.count(),
        "total_checkins":         CheckIn.objects.count(),
        "recent_places":          Place.objects.order_by("-created_at")[:10],
        "recent_checkins":        CheckIn.objects.select_related("user", "place").order_by("-created_at")[:10],
        "category_labels":        list(Category.objects.values_list("name", flat=True)),
        "category_data":          [cat.places.count() for cat in Category.objects.all()],
        "new_users_this_month":   User.objects.filter(date_joined__gte=month_ago).count(),
        "new_places_this_month":  Place.objects.filter(created_at__gte=month_ago).count(),
        "new_checkins_this_month":CheckIn.objects.filter(created_at__gte=month_ago).count(),
        "active_users":           CheckIn.objects.filter(created_at__gte=month_ago).values("user").distinct().count(),
    })


# ─────────────────────────────────────────────────────────
# PWA / Misc
# ─────────────────────────────────────────────────────────

def manifest(request):
    data = {
        "name": "GhostPin - Explore Places",
        "short_name": "GhostPin",
        "description": "Discover and explore places around the world",
        "start_url": "/",
        "display": "standalone",
        "theme_color": "#4CAF50",
        "background_color": "#ffffff",
        "orientation": "portrait-primary",
        "scope": "/",
        "lang": "en",
        "categories": ["travel", "education", "lifestyle"],
        "icons": [
            {"src": "/static/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
        ],
        "shortcuts": [
            {
                "name": "Add New Place", "short_name": "Add Place",
                "description": "Submit a new place", "url": "/place/add/",
                "icons": [{"src": "/static/icons/icon-192x192.png", "sizes": "192x192"}],
            }
        ],
    }
    response = JsonResponse(data)
    response["Content-Type"] = "application/manifest+json"
    return response


def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, "static", "service-worker.js")
    try:
        with open(sw_path, "r") as f:
            content = f.read()
        response = HttpResponse(content, content_type="application/javascript")
        response["Cache-Control"] = "no-cache"
        return response
    except FileNotFoundError:
        raise Http404("Service worker not found")


@login_required
def nearby_places_view(request):
    return render(request, "nearby_places.html")


@require_GET
def get_nearby_places(request):
    try:
        lat         = float(request.GET.get("lat"))
        lng         = float(request.GET.get("lng"))
        distance_km = float(request.GET.get("distance", 10))

        user_location = (lat, lng)
        lat_range     = distance_km / 111
        lng_range     = distance_km / (111 * math.cos(math.radians(lat)))

        candidate_places = Place.objects.filter(
            status="approved",
            latitude__range =(lat - lat_range, lat + lat_range),
            longitude__range=(lng - lng_range, lng + lng_range),
        ).prefetch_related("category")

        places = []
        for place in candidate_places:
            distance = geodesic(user_location, (place.latitude, place.longitude)).km
            if distance <= distance_km:
                categories   = [c.name.strip() for c in place.category.all()]
                places.append({
                    "id":          place.id,
                    "name":        place.name,
                    "slug":        place.slug,
                    "description": place.description[:200],
                    "category":    ", ".join(categories) if categories else "Other",
                    "latitude":    place.latitude,
                    "longitude":   place.longitude,
                    "distance":    round(distance, 2),
                    "rating":      place.average_rating,
                    "visit_count": place.visit_count,
                })

        if request.user.is_authenticated and places:
            recent = Notification.objects.filter(
                user=request.user,
                notification_type="nearby_place",
                created_at__gte=timezone.now() - timedelta(hours=1),
            ).exists()
            if not recent:
                Notification.objects.create(
                    user=request.user,
                    title="Nearby Places Alert",
                    message=f"There are {len(places)} places near you.",
                    notification_type="nearby_place",
                )

        return JsonResponse({"places": places})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@login_required
def search_results(request):
    query      = request.GET.get("q", "")
    category   = request.GET.get("category", "")
    difficulty = request.GET.get("difficulty", "")
    sort       = request.GET.get("sort", "name")

    places = Place.objects.filter(status="approved")
    if query:
        places = places.filter(name__icontains=query)
    if category:
        places = places.filter(category__slug=category)
    if difficulty:
        places = places.filter(difficulty=difficulty)
    if sort in ["name", "created_at", "visit_count"]:
        places = places.order_by(sort)

    paginator   = Paginator(places, 6)
    places_page = paginator.get_page(request.GET.get("page"))

    return render(request, "search_results.html", {
        "places":     places_page,
        "query":      query,
        "categories": Category.objects.all(),
    })


# ─────────────────────────────────────────────────────────
# Profile completion
# ─────────────────────────────────────────────────────────

PROFILE_FIELDS = [
    ('avatar',        20, 'Upload a profile photo'),
    ('bio',           15, 'Write a short bio'),
    ('location',      10, 'Add your location'),
    ('any_link',      10, 'Add at least one social or website link'),
    ('phone_number',   5, 'Add a phone number'),
    ('first_name',    10, 'Add your first name'),
    ('last_name',     10, 'Add your last name'),
    ('email',         10, 'Confirm your email'),
    ('show_email',     5, 'Set email visibility'),
    ('show_location',  5, 'Set location visibility'),
    ('expert_areas',  10, 'Choose areas of expertise'),
]
 
PROFILE_COMPLETION_TOTAL = sum(w for _, w, _ in PROFILE_FIELDS)  # = 110 — renormalised to 100% in the view


def get_profile_completion(user, profile):
    """
    Returns (score_0_to_100, missing_hints, completed_hints).
 
    'any_link' is satisfied when at least one of the seven link fields is filled.
    """
    any_link = any([
        profile.website_url,
        profile.youtube_url,
        profile.facebook_url,
        profile.instagram_url,
        profile.tiktok_url,
        profile.linkedin_url,
        profile.x_url,
    ])
 
    field_checks = {
        'avatar':        bool(profile.avatar),
        'bio':           bool(profile.bio and profile.bio.strip()),
        'location':      bool(profile.location and profile.location.strip()),
        'any_link':      any_link,
        'phone_number':  bool(profile.phone_number and profile.phone_number.strip()),
        'first_name':    bool(user.first_name and user.first_name.strip()),
        'last_name':     bool(user.last_name  and user.last_name.strip()),
        'email':         bool(user.email      and user.email.strip()),
        'show_email':    profile.show_email,
        'show_location': profile.show_location,
        'expert_areas':  profile.expert_areas.exists(),
    }
 
    raw_score = 0
    missing   = []
    completed = []
 
    for field, weight, hint in PROFILE_FIELDS:
        if field_checks.get(field, False):
            raw_score += weight
            completed.append(hint)
        else:
            missing.append(hint)
 
    # Normalise to 0-100 (total weights = 110)
    score = min(round(raw_score * 100 / PROFILE_COMPLETION_TOTAL), 100)
    return score, missing, completed


def _resize_avatar(image_file, max_size=(400, 400), quality=85):
    try:
        img = Image.open(image_file)
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top  = (h - side) // 2
        img  = img.crop((left, top, left + side, top + side))
        img.thumbnail(max_size, Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        return ContentFile(buf.getvalue())
    except Exception:
        return None


ALLOWED_AVATAR_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_AVATAR_SIZE_MB   = 5


@login_required
def edit_profile(request):
    user      = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    score_before, _, _ = get_profile_completion(user, profile)

    if request.method == 'POST':
        form         = UserProfileForm(request.POST, request.FILES, instance=profile)
        avatar_error = None
        avatar_file  = request.FILES.get('avatar')

        if avatar_file:
            content_type = getattr(avatar_file, 'content_type', '')
            size_mb      = avatar_file.size / (1024 * 1024)
            if content_type not in ALLOWED_AVATAR_TYPES:
                avatar_error = 'Avatar must be a JPEG, PNG, GIF, or WebP image.'
            elif size_mb > MAX_AVATAR_SIZE_MB:
                avatar_error = f'Avatar must be smaller than {MAX_AVATAR_SIZE_MB} MB.'

        if avatar_error:
            messages.error(request, avatar_error)
            score, missing, completed = get_profile_completion(user, profile)
            return render(request, 'places/edit_profile.html', {
                'form': form, 'profile': profile,
                'completion_score': score, 'completion_missing': missing,
                'completion_completed': completed,
            })

        if form.is_valid():
            profile_obj = form.save(commit=False)

            if avatar_file:
                resized = _resize_avatar(avatar_file)
                if resized:
                    if profile_obj.avatar:
                        try:
                            old_path = profile_obj.avatar.path
                            if os.path.isfile(old_path):
                                os.remove(old_path)
                        except (ValueError, OSError):
                            pass
                    profile_obj.avatar.save(f'avatar_{user.pk}.jpg', resized, save=True)

            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name  = request.POST.get('last_name',  '').strip()

            new_email = request.POST.get('email', '').strip()
            if new_email and new_email != user.email:
                if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                    messages.error(request, 'That email address is already in use.')
                    score, missing, completed = get_profile_completion(user, profile)
                    return render(request, 'places/edit_profile.html', {
                        'form': form, 'profile': profile,
                        'completion_score': score, 'completion_missing': missing,
                        'completion_completed': completed,
                    })
                user.email = new_email

            user.save()
            profile_obj.save()
            form.save_m2m()

            score_after, missing, completed = get_profile_completion(user, profile_obj)
            _award_profile_completion_points(user, profile_obj, score_before, score_after)
            evaluate_badges_for_user(user)

            messages.success(request, 'Profile updated successfully!')
            if score_before < 100 <= score_after:
                messages.success(request, '🎉 Your profile is now 100% complete! You earned bonus points.')

            return redirect('places:profile', username=user.username)
    else:
        form = UserProfileForm(instance=profile)

    score, missing, completed = get_profile_completion(user, profile)
    return render(request, 'places/edit_profile.html', {
        'form':                 form,
        'profile':              profile,
        'completion_score':     score,
        'completion_missing':   missing,
        'completion_completed': completed,
        'initial_first_name':   user.first_name,
        'initial_last_name':    user.last_name,
        'initial_email':        user.email,
    })


_COMPLETION_MILESTONES = {
    25:  ('Profile 25% Complete',  10),
    50:  ('Profile Halfway There', 20),
    75:  ('Profile 75% Complete',  30),
    100: ('Profile Complete! 🎉',  50),
}


def _award_profile_completion_points(user, profile, score_before, score_after):
    uprof, _ = UserProfile.objects.get_or_create(user=user)
    for threshold, (title, pts) in _COMPLETION_MILESTONES.items():
        if score_before < threshold <= score_after:
            already = Notification.objects.filter(
                user=user, notification_type='profile_complete', title=title,
            ).exists()
            if not already:
                uprof.points += pts
                uprof.save(update_fields=['points'])
                _recalculate_level(uprof)
                evaluate_badges_for_user(user)
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=f'Your profile is now {threshold}% complete. You earned {pts} bonus points!',
                    notification_type='profile_complete',
                )


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Notification.objects.create(
                user=user,
                title="Welcome to Expearls!",
                message="Thanks for signing up! Start exploring and adding places.",
                notification_type="welcome",
            )
            messages.success(request, "Account created successfully. Please log in.")
            return redirect("login")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def checkin_detail(request, pk):
    checkin      = get_object_or_404(CheckIn, pk=pk)
    place        = checkin.place
    all_checkins = CheckIn.objects.filter(place=place).select_related("user")
    comments     = (
        Comment.objects.filter(checkin=checkin, parent=None)
        .select_related("user")
        .prefetch_related("replies")
    )
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment         = form.save(commit=False)
            comment.user    = request.user
            comment.place   = checkin.place
            comment.checkin = checkin
            comment.save()
            return redirect(request.path_info)
    else:
        form = CommentForm()

    return render(request, "checkins/checkin_detail.html", {
        "checkin":  checkin,
        "place":    place,
        "checkins": all_checkins,
        "comments": comments,
        "form":     form,
    })


@login_required
@require_POST
def vote_comment(request, comment_id):
    data      = json.loads(request.body)
    vote_type = data.get("vote_type")
    if vote_type not in ["up", "down"]:
        return JsonResponse({"success": False, "error": "Invalid vote type"})

    comment    = get_object_or_404(Comment, id=comment_id)
    vote, created = Vote.objects.get_or_create(
        user=request.user, comment=comment, defaults={"vote_type": vote_type}
    )
    if not created:
        if vote.vote_type == vote_type:
            vote.delete()
        else:
            vote.vote_type = vote_type
            vote.save()

    return JsonResponse({
        "success":   True,
        "upvotes":   Vote.objects.filter(comment=comment, vote_type="up").count(),
        "downvotes": Vote.objects.filter(comment=comment, vote_type="down").count(),
    })


@require_POST
def reply_comment(request):
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Login required"}, status=401)
    parent = get_object_or_404(Comment, id=request.POST.get("parent_id"))
    Comment.objects.create(
        user=request.user, place=parent.place, parent=parent,
        text=request.POST.get("reply_text"),
    )
    return JsonResponse({"success": True})


def place_checkins(request, slug):
    place        = get_object_or_404(Place, slug=slug, status="approved")
    checkins_list = (
        CheckIn.objects.filter(place=place)
        .select_related("user")
        .order_by("-created_at")
    )

    total_count       = checkins_list.count()
    unique_visitors   = checkins_list.values("user").distinct().count()
    verified_checkins = checkins_list.filter(location_verified=True).count()
    photo_checkins    = checkins_list.exclude(photo_proof__isnull=True).exclude(photo_proof="").count()

    paginator   = Paginator(checkins_list, 10)
    checkins    = paginator.get_page(request.GET.get("page"))

    return render(request, "place_checkins.html", {
        "place":             place,
        "checkins":          checkins,
        "total_count":       total_count,
        "unique_visitors":   unique_visitors,
        "verified_checkins": verified_checkins,
        "photo_checkins":    photo_checkins,
        "has_more":          checkins.has_next(),
    })


def route_planner(request):
    destination_id     = request.GET.get("destination", "")
    slugs              = [s.strip() for s in destination_id.split(",") if s.strip()]
    destination        = None
    preselected_waypoints = []

    if slugs:
        destination = Place.objects.filter(slug=slugs[0], status="approved").first()
        if len(slugs) > 1:
            preselected_waypoints = list(
                Place.objects.filter(slug__in=slugs[1:], status="approved")
                .values("id", "name", "latitude", "longitude")
            )

    all_places = Place.objects.filter(status="approved").prefetch_related("category")
    all_places_data = [
        {
            "id":          p.id,
            "name":        p.name,
            "latitude":    p.latitude,
            "longitude":   p.longitude,
            "description": p.description,
            "category":    [c.slug for c in p.category.all()],
            "rating":      float(p.average_rating) if p.average_rating else 0.0,
        }
        for p in all_places
    ]

    return render(request, "places/route_planner.html", {
        "destination":          destination,
        "preselected_waypoints":json.dumps(preselected_waypoints),
        "all_places":           json.dumps(all_places_data),
        "categories":           Category.objects.all(),
    })


def about(request):
    return render(request, "about.html")


# ─────────────────────────────────────────────────────────
# Tour views
# ─────────────────────────────────────────────────────────

def tour_list(request):
    tours = TourPackage.objects.filter(is_active=True).prefetch_related('trails', 'offerings')
    return render(request, 'tours.html', {'tours': tours})


def tour_detail(request, slug):
    tour      = get_object_or_404(TourPackage, slug=slug, is_active=True)
    return render(request, 'tour_detail.html', {
        'tour':        tour,
        'trails':      tour.trails.all().prefetch_related('places'),
        'offerings':   tour.offerings.all(),
        'itinerary':   tour.itinerary_days.all(),
        'other_tours': TourPackage.objects.filter(is_active=True).exclude(pk=tour.pk)[:3],
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def create_tour(request):
    if request.method == 'POST':
        form = TourPackageForm(request.POST, request.FILES)
        if form.is_valid():
            tour            = form.save(commit=False)
            tour.created_by = request.user
            tour.save()
            form.save_m2m()
            messages.success(request, f'Tour "{tour.name}" created successfully!')
            return redirect('places:tour_detail', slug=tour.slug)
        messages.error(request, 'Please fix the errors below.')
    else:
        form = TourPackageForm()

    return render(request, 'create_tour.html', {
        'form':          form,
        'all_trails':    Trail.objects.filter(is_public=True).order_by('name'),
        'all_offerings': TourOffering.objects.all().order_by('name'),
        'action':        'Create',
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def edit_tour(request, slug):
    tour = get_object_or_404(TourPackage, slug=slug)
    if request.method == 'POST':
        form = TourPackageForm(request.POST, request.FILES, instance=tour)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tour "{tour.name}" updated!')
            return redirect('places:tour_detail', slug=tour.slug)
        messages.error(request, 'Please fix the errors below.')
    else:
        form = TourPackageForm(instance=tour)

    return render(request, 'create_tour.html', {
        'form':                  form,
        'tour':                  tour,
        'all_trails':            Trail.objects.filter(is_public=True).order_by('name'),
        'all_offerings':         TourOffering.objects.all().order_by('name'),
        'selected_trail_ids':    list(tour.trails.values_list('pk', flat=True)),
        'selected_offering_ids': list(tour.offerings.values_list('pk', flat=True)),
        'action':                'Edit',
    })


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def delete_tour(request, slug):
    tour  = get_object_or_404(TourPackage, slug=slug)
    name  = tour.name
    tour.delete()
    messages.success(request, f'Tour "{name}" deleted.')
    return redirect('places:tour_list')


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def toggle_tour_active(request, slug):
    tour           = get_object_or_404(TourPackage, slug=slug)
    tour.is_active = not tour.is_active
    tour.save(update_fields=['is_active'])
    return JsonResponse({'success': True, 'is_active': tour.is_active})