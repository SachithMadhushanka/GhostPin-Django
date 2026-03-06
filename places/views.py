import math
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import now
from collections import Counter
import json
import os, re
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Count, Sum, Avg
from geopy.distance import geodesic
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.db import transaction
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
)

from .forms import (
    TrailForm,
    PlaceForm,
    CommentForm,
    PlaceImageForm,
    CheckInForm,
    TrailForm,
    UserProfileForm,
    SearchForm,
    VoteForm,
    RegisterForm,
    ChallengeForm,
    TourPackageForm,
)

# ─────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────
MAX_PLACES_PER_TRAIL = 20  # ✅ FIX: cap trail size


def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser


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
        "total": total,
        "completed": completed,
        "percent": round((completed / total) * 100),
    }


# ─────────────────────────────────────────────────────────
# Core Views
# ─────────────────────────────────────────────────────────

def home(request):
    # ── Paginated recent places (bottom strip) ──────────────
    all_places = Place.objects.filter(
        status='approved'
    ).order_by('-created_at')

    paginator   = Paginator(all_places, 12)
    page_number = request.GET.get('page')
    places      = paginator.get_page(page_number)

    # ── Trending places ──────────────────────────────────────
    # Actual related names from your model error output:
    #   vote, checkin, comments, visit_count (direct field)
    trending_places = Place.objects.filter(
        status='approved'
    ).annotate(
        vote_count=Count('vote', distinct=True),
        check_in_count=Count('checkin', distinct=True),
        comment_count=Count('comments', distinct=True),
    ).order_by('-visit_count', '-check_in_count', '-vote_count')[:6]

    # ── Featured trails ─────────────────────────────────────
    featured_trails = Trail.objects.filter(
        is_public=True
    ).prefetch_related('places').order_by('-created_at')[:3]

    # ── Tour packages ────────────────────────────────────────
    try:
        featured_tours = TourPackage.objects.filter(
            is_active=True
        ).prefetch_related('offerings', 'trails').order_by('-created_at')[:3]
    except Exception:
        featured_tours = []

    # ── Badges preview ───────────────────────────────────────
    featured_badges = Badge.objects.filter(
        is_active=True
    ).order_by('points_required')[:6]

    # ── Active challenges (with user progress) ───────────────
    now = timezone.now()
    challenges_qs = Challenge.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now,
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

    # ── Leaderboard top 8 ────────────────────────────────────
    top_profiles = UserProfile.objects.select_related('user').order_by('-points')[:8]
    top_explorers = []
    for rank, profile in enumerate(top_profiles, start=1):
        top_explorers.append({
            'rank':     rank,
            'username': profile.user.username,
            'profile':  profile,
        })

    # ── Hero stat pills ──────────────────────────────────────
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
        place.visit_count += 1
        place.save(update_fields=["visit_count"])

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
                        place=place,
                        uploaded_by=request.user,
                        url=video_url,
                        platform=platform,
                        thumbnail_url=thumbnail,
                    )
                    messages.success(request, "Video added successfully!")
                else:
                    messages.error(request, "Unsupported video platform.")
            return redirect("places:place_detail", slug=place.slug)

        elif "image_submit" in request.POST:
            image_form = PlaceImageForm(request.POST, request.FILES)
            if image_form.is_valid():
                image = image_form.save(commit=False)
                image.place = place
                image.uploaded_by = request.user
                image.save()
                messages.success(request, "Image uploaded successfully!")
            else:
                messages.error(request, "Invalid image. Please try again.")
            return redirect("places:place_detail", slug=place.slug)

        elif "comment_submit" in request.POST:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.user = request.user
                comment.place = place

                checkin_id = request.POST.get("checkin_id")
                if checkin_id:
                    try:
                        checkin = CheckIn.objects.get(id=checkin_id)
                        comment.checkin = checkin
                    except CheckIn.DoesNotExist:
                        pass

                comment.save()

                profile, created = UserProfile.objects.get_or_create(user=request.user)
                profile.points += 5
                profile.save()
                evaluate_badges_for_user(request.user)

                messages.success(request, "Comment added successfully!")
                return redirect("places:place_detail", slug=place.slug)

    context = {
        "place": place,
        "comments": comments,
        "comment_form": comment_form,
        "place_images": place_images,
        "is_favorited": is_favorited,
        "user_checkin": user_checkin,
        "related_places": related_places,
        "place_videos": place_videos,
        "image_form": PlaceImageForm(),
    }
    return render(request, "place_detail.html", context)


@login_required
def add_place(request):
    if request.method == "POST":
        form = PlaceForm(request.POST, request.FILES)
        if form.is_valid():
            place = form.save(commit=False)
            place.created_by = request.user
            place.status = "pending"
            place.save()
            form.save_m2m()

            Notification.objects.create(
                user=request.user,
                title="Place Submitted",
                message=f'You added a new place: "{place.name}" and it is pending approval.',
                notification_type="place_added",
                related_place=place,
            )

            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.points += 20
            profile.save()

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
            place = form.save(commit=False)
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
# User Views
# ─────────────────────────────────────────────────────────


@login_required
def profile(request, username):
    user = get_object_or_404(User, username=username)
    profile, created = UserProfile.objects.get_or_create(user=user)

    user_places = Place.objects.filter(created_by=user, status="approved")
    user_checkins = CheckIn.objects.filter(user=user)
    user_badges = UserBadge.objects.filter(user=user)
    user_trails = Trail.objects.filter(created_by=user, is_public=True)
    user_images = (
        PlaceImage.objects.filter(uploaded_by=user)
        .select_related("place")
        .order_by("-created_at")
    )
    user_videos = (
        PlaceVideo.objects.filter(uploaded_by=user)
        .select_related("place")
        .order_by("-created_at")
    )

    if profile.points >= 1000:
        profile.level = 5
    elif profile.points >= 500:
        profile.level = 4
    elif profile.points >= 200:
        profile.level = 3
    elif profile.points >= 50:
        profile.level = 2
    else:
        profile.level = 1
    profile.save()

    context = {
        "profile_user": user,
        "profile": profile,
        "user_places": user_places,
        "user_checkins": user_checkins,
        "user_badges": user_badges,
        "user_trails": user_trails,
        "user_images": user_images,
        "user_videos": user_videos,
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

    context = {
        "favorites": favorites,
        "category_count": category_count,
    }
    return render(request, "favorites.html", context)


@login_required
def notifications(request):
    notification_list = Notification.objects.filter(user=request.user).order_by(
        "-created_at"
    )

    paginator = Paginator(notification_list, 10)
    page_number = request.GET.get("page")
    notifications_page = paginator.get_page(page_number)

    unread_count = notification_list.filter(is_read=False).count()

    return render(
        request,
        "notifications.html",
        {"notifications": notifications_page, "unread_count": unread_count},
    )


@login_required
@require_POST
def mark_notification_read(request, pk):
    try:
        notification = Notification.objects.get(pk=pk, user=request.user)
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
            notification = Notification.objects.get(pk=pk, user=request.user)
            notification.delete()
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
    dates = sorted(set(ci.created_at.date() for ci in checkins))
    if not dates:
        return []
    streaks = []
    current_streak = 1
    for i in range(1, len(dates)):
        if dates[i] == dates[i - 1] + timedelta(days=1):
            current_streak += 1
        else:
            streaks.append(current_streak)
            current_streak = 1
    streaks.append(current_streak)
    return streaks


@login_required
def check_ins(request):
    user = request.user
    today = now().date()
    checkins = CheckIn.objects.filter(user=user).select_related("place")

    total_points = checkins.aggregate(total=Sum("points_awarded"))["total"] or 0
    unique_places = checkins.values("place").distinct().count()

    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    week_checkins = checkins.filter(created_at__date__gte=week_ago).count()
    month_checkins = checkins.filter(created_at__date__gte=month_ago).count()

    total_count = checkins.count()
    photo_checkins = checkins.filter(photo_proof__isnull=False).count()
    verified_checkins = checkins.filter(location_verified=True).count()

    photo_percent = round((photo_checkins / total_count) * 100, 1) if total_count else 0
    verified_percent = (
        round((verified_checkins / total_count) * 100, 1) if total_count else 0
    )

    streaks = get_streaks(checkins)
    longest_streak = max(streaks) if streaks else 0

    months = checkins.dates("created_at", "month")
    month_counts = Counter([dt.strftime("%B %Y") for dt in months])
    most_active_month = month_counts.most_common(1)[0][0] if month_counts else "N/A"

    category_counts = Counter(
        [cat.name for c in checkins if c.place for cat in c.place.category.all()]
    )
    favorite_category = (
        category_counts.most_common(1)[0][0] if category_counts else "N/A"
    )

    recent_badges = (
        UserBadge.objects.filter(user=user)
        .select_related("badge")
        .order_by("-earned_at")[:5]
    )

    return render(
        request,
        "check_ins.html",
        {
            "checkins": checkins,
            "total_points": total_points,
            "unique_places": unique_places,
            "week_checkins": week_checkins,
            "month_checkins": month_checkins,
            "photo_checkins": photo_percent,
            "verified_checkins": verified_percent,
            "longest_streak": longest_streak,
            "most_active_month": most_active_month,
            "favorite_category": favorite_category,
            "recent_badges": recent_badges,
        },
    )


def award_trail_completions(user, checked_place):
    affected_trails = Trail.objects.filter(
        trailplace__place=checked_place, is_public=True
    ).distinct()

    for trail in affected_trails:
        already_rewarded = Notification.objects.filter(
            user=user,
            notification_type="challenge",
            message__icontains=trail.name,
            title__icontains="Completed",
        ).exists()
        if already_rewarded:
            continue

        progress = get_trail_progress(user, trail)
        if progress["completed"] == progress["total"] and progress["total"] > 0:
            multipliers = {"easy": 1.0, "moderate": 1.3, "challenging": 1.5}
            multiplier = multipliers.get(trail.difficulty, 1.0)
            bonus = int(100 * multiplier)

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.points += bonus
            profile.save()

            Notification.objects.create(
                user=user,
                title="Trail Completed! 🎉",
                message=f'You completed "{trail.name}" and earned {bonus} bonus points!',
                notification_type="challenge",
                related_trail=trail,
            )

            if hasattr(trail, "completion_badge") and trail.completion_badge:
                UserBadge.objects.get_or_create(user=user, badge=trail.completion_badge)


@login_required
def check_in(request, slug):
    place = get_object_or_404(Place, slug=slug, status="approved")

    existing_checkin = CheckIn.objects.filter(user=request.user, place=place).first()
    if existing_checkin:
        messages.info(request, "You have already checked in at this place.")
        return redirect("places:place_detail", slug=place.slug)

    if request.method == "POST":
        form = CheckInForm(request.POST, request.FILES)
        if form.is_valid():
            checkin = form.save(commit=False)
            checkin.user = request.user
            checkin.place = place
            checkin.location_verified = request.POST.get("location_verified") == "true"

            points = 10
            if checkin.photo_proof:
                points += 5
            if checkin.location_verified:
                points += 5
            checkin.points_awarded = points
            checkin.save()

            award_trail_completions(request.user, place)
            evaluate_challenges_for_user(request.user)
            evaluate_badges_for_user(request.user)

            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.points += checkin.points_awarded
            profile.save()

            messages.success(
                request,
                f"Checked in successfully! You earned {checkin.points_awarded} points.",
            )
            return redirect("places:place_detail", slug=place.slug)
    else:
        form = CheckInForm()

    return render(request, "check_in.html", {"form": form, "place": place})


# ─────────────────────────────────────────────────────────
# Trails
# ─────────────────────────────────────────────────────────


def trails(request):
    """
    ✅ FIX 1: Added pagination (was missing).
    ✅ FIX 2: Added .distinct() to prevent duplicate rows from M2M category joins.
    ✅ FIX 3: Fixed difficulty sort — was using raw string comparison; now uses
               CASE ordering via annotate or a sensible fallback.
    ✅ FIX 4: Added popularity stats (checkin_count annotation).
    """
    trails_qs = (
        Trail.objects.filter(is_public=True)
        .annotate(
            place_count=Count("places", distinct=True),  # ✅ distinct avoids inflation
            checkin_count=Count("places__checkin", distinct=True),  # ✅ popularity stat
        )
        .select_related("created_by")
        .prefetch_related("places", "category")
        .distinct()  # ✅ FIX category M2M duplicate rows
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
        trails_qs = trails_qs.order_by("-checkin_count")  # ✅ real popularity
    elif sort_by == "difficulty":
        # ✅ FIX: map difficulty to a numeric weight for proper ordering
        from django.db.models import Case, When, IntegerField, Value

        trails_qs = trails_qs.annotate(
            diff_order=Case(
                When(difficulty="easy", then=Value(1)),
                When(difficulty="moderate", then=Value(2)),
                When(difficulty="challenging", then=Value(3)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("diff_order")
    else:
        trails_qs = trails_qs.order_by("-created_at")

    difficulty_choices = Trail.DIFFICULTY_CHOICES
    category_choices = Category.objects.filter(trails__isnull=False).distinct()

    # ✅ FIX: pagination
    paginator = Paginator(trails_qs, 9)
    page_number = request.GET.get("page")
    trails_page = paginator.get_page(page_number)

    # Attach per-user progress to each trail in the page
    if request.user.is_authenticated:
        for trail in trails_page:
            trail.user_progress = get_trail_progress(request.user, trail)
    else:
        for trail in trails_page:
            trail.user_progress = None

    context = {
        "trails": trails_page,  # ✅ now paginated
        "search_query": search_query,
        "selected_difficulty": difficulty,
        "selected_category": category,
        "selected_sort": sort_by,
        "difficulty_choices": difficulty_choices,
        "category_choices": category_choices,
        "is_paginated": trails_page.has_other_pages(),
    }
    return render(request, "trails.html", context)


def trail_detail(request, pk):
    trail = get_object_or_404(Trail, pk=pk)

    # ✅ FIX: lock check should also handle unauthenticated users gracefully
    is_locked = False
    if trail.required_points > 0:
        if not request.user.is_authenticated:
            is_locked = True
        else:
            user_profile = getattr(request.user, "userprofile", None)
            # ✅ FIX: was checking wrong condition — staff bypass, correct points check
            if not request.user.is_staff and (
                user_profile is None or user_profile.points < trail.required_points
            ):
                is_locked = True

    if not trail.is_public and (
        not request.user.is_authenticated or trail.created_by != request.user
    ):
        if not (request.user.is_authenticated and request.user.is_staff):
            raise Http404("Trail not found")

    progress = None
    if request.user.is_authenticated:
        progress = get_trail_progress(request.user, trail)

    trail_places = (
        TrailPlace.objects.filter(trail=trail)
        .select_related("place")
        .prefetch_related("place__category")
        .order_by("order")
    )

    # ✅ FIX: save_trail is now a real toggle (remove if already saved)
    if request.method == "POST" and request.user.is_authenticated:
        action = request.POST.get("action")

        if action == "save_trail":
            favorite, created = TrailFavorite.objects.get_or_create(
                user=request.user,
                trail=trail,
            )
            if created:
                messages.success(request, "Trail saved to your favorites!")
            else:
                favorite.delete()
                messages.info(request, "Trail removed from your favorites.")

        elif action == "start_trail":
            # ✅ FIX: redirect to first uncompleted place in the trail
            if is_locked:
                messages.error(
                    request,
                    f"You need {trail.required_points} points to start this trail.",
                )
                return redirect("places:trail_detail", pk=trail.pk)

            if trail_places.exists():
                # Find first place user hasn't checked into yet
                checked_ids = set(
                    CheckIn.objects.filter(user=request.user).values_list(
                        "place_id", flat=True
                    )
                )
                first_unchecked = next(
                    (tp for tp in trail_places if tp.place_id not in checked_ids),
                    trail_places.first(),
                )
                messages.success(
                    request, f"Starting trail at {first_unchecked.place.name}!"
                )
                return redirect("places:place_detail", slug=first_unchecked.place.slug)
            else:
                messages.warning(request, "This trail has no places yet.")

        elif action == "export_route":
            # ✅ FIX: generate a real GPX export instead of a fake response
            return _export_trail_gpx(trail, trail_places)

    total_distance = sum([tp.distance_from_previous or 0 for tp in trail_places])
    estimated_time = trail.estimated_duration or "Varies"

    # ✅ FIX: is_saved state for the button
    is_saved = False
    if request.user.is_authenticated:
        is_saved = TrailFavorite.objects.filter(user=request.user, trail=trail).exists()

    context = {
        "trail": trail,
        "trail_places": trail_places,
        "total_distance": total_distance,
        "estimated_time": estimated_time,
        "can_edit": request.user.is_authenticated
        and (request.user == trail.created_by or request.user.is_staff),
        "progress": progress,
        "is_locked": is_locked,
        "is_saved": is_saved,  # ✅ saved state for button
    }
    return render(request, "trail_detail.html", context)


def _export_trail_gpx(trail, trail_places):
    """✅ FIX: Real GPX export instead of a fake success message."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="RoamLk" xmlns="http://www.topografix.com/GPX/1/1">',
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
    """
    ✅ FIX: Wrapped place insertion in transaction.atomic().
    ✅ FIX: Added max-place enforcement (MAX_PLACES_PER_TRAIL).
    ✅ FIX: Added duplicate name check per creator.
    ✅ FIX: Added zero-place validation.
    ✅ FIX: Deduplicate place_ids to prevent duplicate TrailPlace entries.
    """
    if request.method == "POST":
        form = TrailForm(request.POST, request.FILES)

        # ✅ FIX: duplicate name check per user
        trail_name = request.POST.get("name", "").strip()
        if Trail.objects.filter(
            created_by=request.user, name__iexact=trail_name
        ).exists():
            messages.error(
                request,
                f'You already have a trail named "{trail_name}". Please choose a different name.',
            )
            available_places = Place.objects.filter(status="approved").order_by("name")
            return render(
                request,
                "create_trail.html",
                {"form": form, "available_places": available_places},
            )

        if form.is_valid():
            selected_places_raw = request.POST.get("selected_places", "")
            place_ids = _parse_place_ids(selected_places_raw)

            # ✅ FIX: zero-place validation
            save_as_draft = request.POST.get("save_as_draft", False)
            if not save_as_draft and len(place_ids) == 0:
                messages.error(request, "A trail must include at least one place.")
                available_places = Place.objects.filter(status="approved").order_by(
                    "name"
                )
                return render(
                    request,
                    "create_trail.html",
                    {"form": form, "available_places": available_places},
                )

            # ✅ FIX: max place limit
            if len(place_ids) > MAX_PLACES_PER_TRAIL:
                messages.error(
                    request,
                    f"A trail can contain at most {MAX_PLACES_PER_TRAIL} places.",
                )
                available_places = Place.objects.filter(status="approved").order_by(
                    "name"
                )
                return render(
                    request,
                    "create_trail.html",
                    {"form": form, "available_places": available_places},
                )

            # ✅ FIX: wrap in transaction
            with transaction.atomic():
                trail = form.save(commit=False)
                trail.created_by = request.user
                if save_as_draft:
                    trail.is_public = False
                trail.save()
                form.save_m2m()

                _attach_places_to_trail(trail, place_ids)

            if save_as_draft:
                messages.success(request, "Trail saved as draft!")
            else:
                messages.success(request, "Trail created successfully!")
            return redirect("places:trail_detail", pk=trail.pk)
    else:
        form = TrailForm()

    available_places = Place.objects.filter(status="approved").order_by("name")

    preselected_places = []
    places_param = request.GET.get("places", "")
    if places_param:
        try:
            place_ids = [int(i) for i in places_param.split(",") if i.strip()]
            preselected_places = Place.objects.filter(
                pk__in=place_ids, status="approved"
            )
        except ValueError:
            pass

    context = {
        "form": form,
        "available_places": available_places,
        "preselected_places": preselected_places,
        "max_places": MAX_PLACES_PER_TRAIL,  # pass to template for JS validation
    }
    return render(request, "create_trail.html", context)


@login_required
def edit_trail(request, pk):
    """
    ✅ FIX: Wrapped in transaction.atomic().
    ✅ FIX: Duplicate name check (excluding current trail).
    ✅ FIX: Zero-place and max-place validation.
    ✅ FIX: Deduplicate place ids.
    """
    trail = get_object_or_404(Trail, pk=pk)

    if trail.created_by != request.user and not request.user.is_staff:
        messages.error(request, "You can only edit your own trails.")
        return redirect("places:trail_detail", pk=trail.pk)

    if request.method == "POST":
        form = TrailForm(request.POST, request.FILES, instance=trail)

        # ✅ FIX: duplicate name check excluding self
        trail_name = request.POST.get("name", "").strip()
        if (
            Trail.objects.filter(created_by=request.user, name__iexact=trail_name)
            .exclude(pk=trail.pk)
            .exists()
        ):
            messages.error(
                request, f'You already have another trail named "{trail_name}".'
            )
            available_places = Place.objects.filter(status="approved").order_by("name")
            current_places = trail.places.all()
            return render(
                request,
                "create_trail.html",
                {
                    "form": form,
                    "trail": trail,
                    "available_places": available_places,
                    "current_places": current_places,
                    "is_editing": True,
                    "max_places": MAX_PLACES_PER_TRAIL,
                },
            )

        if form.is_valid():
            selected_places_raw = request.POST.get("selected_places", "")
            place_ids = _parse_place_ids(selected_places_raw)

            if len(place_ids) == 0:
                messages.error(request, "A trail must include at least one place.")
                available_places = Place.objects.filter(status="approved").order_by(
                    "name"
                )
                current_places = trail.places.all()
                return render(
                    request,
                    "create_trail.html",
                    {
                        "form": form,
                        "trail": trail,
                        "available_places": available_places,
                        "current_places": current_places,
                        "is_editing": True,
                        "max_places": MAX_PLACES_PER_TRAIL,
                    },
                )

            # ✅ FIX: max place limit
            if len(place_ids) > MAX_PLACES_PER_TRAIL:
                messages.error(
                    request,
                    f"A trail can contain at most {MAX_PLACES_PER_TRAIL} places.",
                )
                available_places = Place.objects.filter(status="approved").order_by(
                    "name"
                )
                current_places = trail.places.all()
                return render(
                    request,
                    "create_trail.html",
                    {
                        "form": form,
                        "trail": trail,
                        "available_places": available_places,
                        "current_places": current_places,
                        "is_editing": True,
                        "max_places": MAX_PLACES_PER_TRAIL,
                    },
                )

            # ✅ FIX: wrap in transaction
            with transaction.atomic():
                trail = form.save()
                TrailPlace.objects.filter(trail=trail).delete()
                _attach_places_to_trail(trail, place_ids)

            messages.success(request, "Trail updated successfully!")
            return redirect("places:trail_detail", pk=trail.pk)
    else:
        form = TrailForm(instance=trail)

    available_places = Place.objects.filter(status="approved").order_by("name")
    current_places = trail.places.all()

    context = {
        "form": form,
        "trail": trail,
        "available_places": available_places,
        "current_places": current_places,
        "is_editing": True,
        "max_places": MAX_PLACES_PER_TRAIL,
    }
    return render(request, "create_trail.html", context)


# ─── Helpers ───────────────────────────────────────────────


def _parse_place_ids(raw):
    """
    Parse comma-separated place IDs, deduplicate while preserving order.
    ✅ FIX: prevents duplicate TrailPlace entries from double-clicks.
    """
    seen = set()
    ids = []
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
    """Create TrailPlace entries. Skips non-existent / unapproved places."""
    place_map = {
        p.pk: p for p in Place.objects.filter(pk__in=place_ids, status="approved")
    }
    for order, place_id in enumerate(place_ids, start=1):
        if place_id in place_map:
            TrailPlace.objects.create(
                trail=trail, place=place_map[place_id], order=order
            )


# ─────────────────────────────────────────────────────────
# Gamification
# ─────────────────────────────────────────────────────────


def leaderboard(request):
    base_qs = UserProfile.objects.select_related("user")
    total_points = base_qs.aggregate(Sum("points"))["points__sum"] or 0
    total_users = base_qs.count()

    top_users = base_qs.annotate(
        place_count=Count("user__place", filter=Q(user__place__status="approved"))
    ).order_by("-points")[:50]

    user_rank = None
    if request.user.is_authenticated and hasattr(request.user, "userprofile"):
        higher_ranked = UserProfile.objects.filter(
            points__gt=request.user.userprofile.points
        ).count()
        user_rank = higher_ranked + 1

    return render(
        request,
        "leaderboard.html",
        {
            "top_users": top_users,
            "total_users": total_users,
            "user_rank": user_rank,
            "total_points": total_points,
        },
    )


# ─────────────────────────────────────────────────────────
# Challenge Engine
# ─────────────────────────────────────────────────────────


def get_challenge_progress(user, challenge):
    """
    Compute a user's live progress toward a challenge.
    No join required — computed purely from CheckIn records.

    Rules:
    - Only check-ins within the challenge's start/end window count.
    - If criteria has a category slug, only check-ins at places in that
      category count. If no category, all places count.
    - If require_photo=True, the check-in must have a photo.
    - If require_review=True, the user must have left a comment on that
      place within the challenge window.
    - Each place counts once (distinct), regardless of how many times
      the user checked in there.

    Returns:
        {
            'required': int,
            'completed': int,   # capped at required for display
            'percent': int,     # 0–100
            'is_done': bool,
        }
    """
    criteria = challenge.criteria or {}
    required = max(int(criteria.get("visit_count", 1)), 1)
    require_photo = bool(criteria.get("require_photo", False))
    require_review = bool(criteria.get("require_review", False))
    category_slug = criteria.get("category", "").strip()

    checkins = CheckIn.objects.filter(
        user=user,
        created_at__gte=challenge.start_date,
        created_at__lte=challenge.end_date,
    )

    # Category restriction — only matching category counts
    if category_slug:
        checkins = checkins.filter(place__category__slug=category_slug)

    # Photo proof required
    if require_photo:
        checkins = checkins.exclude(photo_proof="").exclude(photo_proof__isnull=True)

    # Review required: user must have commented on that place in the window
    if require_review:
        reviewed_place_ids = Comment.objects.filter(
            user=user,
            created_at__gte=challenge.start_date,
            created_at__lte=challenge.end_date,
        ).values_list("place_id", flat=True)
        checkins = checkins.filter(place_id__in=reviewed_place_ids)

    # Count distinct places (one check-in per place is enough)
    raw_count = checkins.values("place_id").distinct().count()
    completed = min(raw_count, required)

    return {
        "required": required,
        "completed": completed,
        "percent": round((completed / required) * 100),
        "is_done": raw_count >= required,
    }


def evaluate_challenges_for_user(user):
    """
    Called after every check-in.
    Scans all currently active challenges, computes progress for the user,
    and fires a one-time reward for any newly completed challenges.
    Safe to call repeatedly — unique_together on UserChallengeCompletion
    prevents double rewards.
    """
    now_ts = timezone.now()

    active_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__lte=now_ts,
        end_date__gte=now_ts,
    )

    # Challenges this user has already been rewarded for — skip them
    already_completed = set(
        UserChallengeCompletion.objects.filter(user=user).values_list(
            "challenge_id", flat=True
        )
    )

    for challenge in active_challenges:
        if challenge.pk in already_completed:
            continue

        progress = get_challenge_progress(user, challenge)
        if progress["is_done"]:
            _grant_challenge_reward(user, challenge)


def _grant_challenge_reward(user, challenge):
    """
    Award points + notification for completing a challenge.
    Uses get_or_create so it's idempotent even if called concurrently.
    """
    completion, created = UserChallengeCompletion.objects.get_or_create(
        user=user,
        challenge=challenge,
        defaults={"points_awarded": challenge.reward_points},
    )
    if not created:
        return  # already rewarded, nothing to do

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.points += challenge.reward_points
    profile.save(update_fields=["points"])

    Notification.objects.create(
        user=user,
        title="Challenge Completed! 🏆",
        message=(
            f'You completed "{challenge.title}" and earned '
            f"{challenge.reward_points} bonus points!"
        ),
        notification_type="challenge",
    )


# ─────────────────────────────────────────────────────────
# Updated challenges view
# ─────────────────────────────────────────────────────────


def challenges(request):
    now_ts = timezone.now()

    active_challenges = list(
        Challenge.objects.filter(
            is_active=True,
            start_date__lte=now_ts,
            end_date__gte=now_ts,
        ).order_by("end_date")
    )

    past_challenges = Challenge.objects.filter(
        end_date__lt=now_ts,
    ).order_by(
        "-end_date"
    )[:10]

    # Attach live progress to each active challenge for authenticated users
    if request.user.is_authenticated:
        completed_ids = set(
            UserChallengeCompletion.objects.filter(user=request.user).values_list(
                "challenge_id", flat=True
            )
        )
        for ch in active_challenges:
            ch.user_progress = get_challenge_progress(request.user, ch)
            ch.user_completed = ch.pk in completed_ids
    else:
        for ch in active_challenges:
            ch.user_progress = None
            ch.user_completed = False

    return render(
        request,
        "challenges.html",
        {
            "active_challenges": active_challenges,
            "past_challenges": past_challenges,
        },
    )


@login_required
@user_passes_test(is_staff_or_superuser)
def create_challenge(request):
    """Staff-only: create a new challenge."""
    if request.method == "POST":
        form = ChallengeForm(request.POST)
        if form.is_valid():
            challenge = form.save()
            messages.success(
                request, f'Challenge "{challenge.title}" created successfully!'
            )
            return redirect("places:challenges")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ChallengeForm()

    return render(request, "create_challenge.html", {"form": form, "action": "Create"})


@login_required
@user_passes_test(is_staff_or_superuser)
def edit_challenge(request, pk):
    """Staff-only: edit an existing challenge."""
    challenge = get_object_or_404(Challenge, pk=pk)

    if request.method == "POST":
        form = ChallengeForm(request.POST, instance=challenge)
        if form.is_valid():
            form.save()
            messages.success(request, f'Challenge "{challenge.title}" updated!')
            return redirect("places:challenges")
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ChallengeForm(instance=challenge)
        form._load_criteria_initial()

    return render(
        request,
        "create_challenge.html",
        {
            "form": form,
            "challenge": challenge,
            "action": "Edit",
        },
    )


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def delete_challenge(request, pk):
    """Staff-only: delete a challenge (POST only)."""
    challenge = get_object_or_404(Challenge, pk=pk)
    title = challenge.title
    challenge.delete()
    messages.success(request, f'Challenge "{title}" deleted.')
    return redirect("places:challenges")


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def toggle_challenge_active(request, pk):
    """Staff-only AJAX: toggle is_active."""
    challenge = get_object_or_404(Challenge, pk=pk)
    challenge.is_active = not challenge.is_active
    challenge.save(update_fields=["is_active"])
    return JsonResponse({"success": True, "is_active": challenge.is_active})


# ─────────────────────────────────────────────────────────
# Badge Engine
# ─────────────────────────────────────────────────────────

def get_badge_progress(user, badge):
    """
    Compute a user's live progress toward a badge.
    Returns:
        {
            'current':    int,   # raw current value
            'threshold':  int,   # target value
            'percent':    int,   # 0–100, capped
            'is_done':    bool,
            'label':      str,   # human-readable description e.g. "8 / 10 check-ins"
            'action_hint':str,   # what the user should do next
        }
    """
    criteria = badge.criteria or {}
    badge_type = criteria.get("type", "")
    threshold = max(int(criteria.get("threshold", 1)), 1)

    profile = getattr(user, "userprofile", None)

    if badge_type == "checkins":
        current = CheckIn.objects.filter(user=user).values("place").distinct().count()
        label = f"{current} / {threshold} places visited"
        hint = "Check in at more places to progress."

    elif badge_type == "places_added":
        current = Place.objects.filter(created_by=user, status="approved").count()
        label = f"{current} / {threshold} places contributed"
        hint = "Submit more places and get them approved."

    elif badge_type == "points":
        current = profile.points if profile else 0
        label = f"{current} / {threshold} points"
        hint = "Keep exploring and contributing to earn more points."

    elif badge_type == "category":
        slug = criteria.get("slug", "")
        current = (
            CheckIn.objects.filter(user=user, place__category__slug=slug)
            .values("place")
            .distinct()
            .count()
        )
        label = f"{current} / {threshold} {slug} places visited"
        hint = f"Check in at more {slug} places."

    elif badge_type == "streak":
        # Reuse existing get_streaks helper
        checkins = CheckIn.objects.filter(user=user)
        streaks = get_streaks(checkins)
        current = max(streaks) if streaks else 0
        label = f"{current} / {threshold} day streak"
        hint = "Check in on consecutive days to build your streak."

    elif badge_type == "reviews":
        current = Comment.objects.filter(user=user, rating__isnull=False).count()
        label = f"{current} / {threshold} reviews written"
        hint = "Leave star ratings when visiting places."

    elif badge_type == "trail_complete":
        # Count distinct trails fully completed (all places checked in)
        completed = 0
        for trail in Trail.objects.filter(is_public=True):
            p = get_trail_progress(user, trail)
            if p["total"] > 0 and p["completed"] == p["total"]:
                completed += 1
        current = completed
        label = f"{current} / {threshold} trails completed"
        hint = "Complete all places in a trail."

    elif badge_type == "photo_checkins":
        current = (
            CheckIn.objects.filter(user=user)
            .exclude(photo_proof="")
            .exclude(photo_proof__isnull=True)
            .count()
        )
        label = f"{current} / {threshold} photo check-ins"
        hint = "Upload photo proof when checking in."

    else:
        # Unknown criteria type — treat as binary (earned or not)
        current = (
            threshold
            if UserBadge.objects.filter(user=user, badge=badge).exists()
            else 0
        )
        label = "Special achievement"
        hint = "Complete special activities to earn this badge."

    is_done = current >= threshold
    percent = min(round((current / threshold) * 100), 100)

    return {
        "current": current,
        "threshold": threshold,
        "percent": percent,
        "is_done": is_done,
        "label": label,
        "action_hint": hint,
    }


def evaluate_badges_for_user(user):
    """
    Check all active badges and award any that the user has now earned
    but hasn't been awarded yet. Safe to call multiple times.
    """
    already_earned = set(
        UserBadge.objects.filter(user=user).values_list("badge_id", flat=True)
    )
    active_badges = Badge.objects.filter(is_active=True)

    for badge in active_badges:
        if badge.pk in already_earned:
            continue
        progress = get_badge_progress(user, badge)
        if progress["is_done"]:
            UserBadge.objects.get_or_create(user=user, badge=badge)
            Notification.objects.create(
                user=user,
                title="Badge Earned! 🏅",
                message=f'You earned the "{badge.name}" badge!',
                notification_type="badge_earned",
            )


def badges(request):
    all_badges = Badge.objects.filter(is_active=True).order_by(
        "category", "points_required"
    )

    earned_map = {}  # badge_id → UserBadge (for earned_at date)
    progress_map = {}  # badge_id → progress dict

    if request.user.is_authenticated:
        for ub in UserBadge.objects.filter(user=request.user).select_related("badge"):
            earned_map[ub.badge_id] = ub

        for badge in all_badges:
            progress_map[badge.pk] = get_badge_progress(request.user, badge)

    # Attach computed data directly onto each badge object for the template
    for badge in all_badges:
        badge.is_earned = badge.pk in earned_map
        badge.earned_at = earned_map[badge.pk].earned_at if badge.is_earned else None
        badge.progress = progress_map.get(badge.pk)

    earned_count = len(earned_map)
    total_count = all_badges.count()

    badge_category_tabs = [
        ("all", "All Badges", "fas fa-th"),
        ("explorer", "Explorer", "fas fa-map-marked-alt"),
        ("contributor", "Contributor", "fas fa-hands-helping"),
        ("social", "Social", "fas fa-users"),
        ("special", "Special", "fas fa-star"),
    ]

    return render(
        request,
        "badges.html",
        {
            "all_badges": all_badges,
            "user_badges": list(earned_map.keys()),
            "earned_count": earned_count,
            "total_count": total_count,
            "badge_category_tabs": badge_category_tabs,
        },
    )

# ── Example badge criteria JSON for the Django admin ───────────────────
#
# First explorer:       {"type": "checkins",       "threshold": 1}
# Trailblazer:          {"type": "checkins",       "threshold": 10}
# Centurion:            {"type": "checkins",       "threshold": 100}
# First contribution:   {"type": "places_added",   "threshold": 1}
# Top contributor:      {"type": "places_added",   "threshold": 10}
# Points milestone:     {"type": "points",         "threshold": 500}
# Waterfall hunter:     {"type": "category",       "slug": "waterfall", "threshold": 5}
# Week streak:          {"type": "streak",         "threshold": 7}
# Reviewer:             {"type": "reviews",        "threshold": 5}
# Trail finisher:       {"type": "trail_complete", "threshold": 1}
# Photographer:         {"type": "photo_checkins", "threshold": 10}


# ─────────────────────────────────────────────────────────
# AJAX Views
# ─────────────────────────────────────────────────────────


@login_required
@require_POST
def toggle_favorite(request, slug):
    place = get_object_or_404(Place, slug=slug)
    favorite, created = Favorite.objects.get_or_create(user=request.user, place=place)

    if not created:
        favorite.delete()

    is_favorited = Favorite.objects.filter(user=request.user, place=place).exists()

    if request.headers.get("HX-Request"):
        html = render_to_string(
            "partials/favorite_button.html",
            {
                "place": place,
                "is_favorited": is_favorited,
            },
            request=request,
        )
        return HttpResponse(html)

    return redirect("places:place_detail", slug=slug)


@login_required
@require_POST
def vote_place(request, slug):
    place = get_object_or_404(Place, slug=slug)
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
        else:
            vote.vote_type = vote_type
            vote.save()

    place.approval_votes = Vote.objects.filter(place=place, vote_type="up").count()
    place.rejection_votes = Vote.objects.filter(place=place, vote_type="down").count()
    place.save()

    return JsonResponse(
        {
            "success": True,
            "action": "voted",
            "approval_votes": place.approval_votes,
            "rejection_votes": place.rejection_votes,
        }
    )


# ─────────────────────────────────────────────────────────
# Admin Views
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
    place = get_object_or_404(Place, slug=slug)
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
            profile, created = UserProfile.objects.get_or_create(user=place.created_by)
            profile.points += 50
            profile.save()
            evaluate_badges_for_user(place.created_by)

        return JsonResponse({"success": True, "status": status})

    return JsonResponse({"success": False, "error": "Invalid status"})


@login_required
@user_passes_test(is_staff_or_superuser)
def analytics(request):
    month_ago = timezone.now() - timedelta(days=30)
    total_places = Place.objects.count()
    approved_places = Place.objects.filter(status="approved").count()
    pending_places = Place.objects.filter(status="pending").count()
    total_users = User.objects.count()
    total_checkins = CheckIn.objects.count()

    recent_places = Place.objects.order_by("-created_at")[:10]
    recent_checkins = CheckIn.objects.select_related("user", "place").order_by(
        "-created_at"
    )[:10]

    context = {
        "total_places": total_places,
        "approved_places": approved_places,
        "pending_places": pending_places,
        "total_users": total_users,
        "total_checkins": total_checkins,
        "recent_places": recent_places,
        "recent_checkins": recent_checkins,
        "category_labels": list(Category.objects.values_list("name", flat=True)),
        "category_data": [cat.places.count() for cat in Category.objects.all()],
        "new_users_this_month": User.objects.filter(date_joined__gte=month_ago).count(),
        "new_places_this_month": Place.objects.filter(
            created_at__gte=month_ago
        ).count(),
        "new_checkins_this_month": CheckIn.objects.filter(
            created_at__gte=month_ago
        ).count(),
        "active_users": CheckIn.objects.filter(created_at__gte=month_ago)
        .values("user")
        .distinct()
        .count(),
    }
    return render(request, "analytics.html", context)


# ─────────────────────────────────────────────────────────
# PWA / Misc
# ─────────────────────────────────────────────────────────


def manifest(request):
    manifest_data = {
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
            {
                "src": "/static/icons/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": "/static/icons/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
        "shortcuts": [
            {
                "name": "Add New Place",
                "short_name": "Add Place",
                "description": "Submit a new place",
                "url": "/place/add/",
                "icons": [
                    {"src": "/static/icons/icon-192x192.png", "sizes": "192x192"}
                ],
            }
        ],
    }
    response = JsonResponse(manifest_data)
    response["Content-Type"] = "application/manifest+json"
    return response


def service_worker(request):
    service_worker_path = os.path.join(settings.BASE_DIR, "static", "service-worker.js")
    try:
        with open(service_worker_path, "r") as f:
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
        lat = float(request.GET.get("lat"))
        lng = float(request.GET.get("lng"))
        distance_km = float(request.GET.get("distance", 10))

        user_location = (lat, lng)
        lat_range = distance_km / 111
        lng_range = distance_km / (111 * math.cos(math.radians(lat)))

        candidate_places = Place.objects.filter(
            status="approved",
            latitude__range=(lat - lat_range, lat + lat_range),
            longitude__range=(lng - lng_range, lng + lng_range),
        ).prefetch_related("category")

        places = []
        for place in candidate_places:
            place_location = (place.latitude, place.longitude)
            distance = geodesic(user_location, place_location).km

            if distance <= distance_km:
                categories = [c.name.strip() for c in place.category.all()]
                category_name = ", ".join(categories) if categories else "Other"

                places.append(
                    {
                        "id": place.id,
                        "name": place.name,
                        "slug": place.slug, 
                        "description": place.description[:200],
                        "category": category_name,
                        "latitude": place.latitude,
                        "longitude": place.longitude,
                        "distance": round(distance, 2),
                        "rating": place.average_rating,
                        "visit_count": place.visit_count,
                    }
                )

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
    query = request.GET.get("q", "")
    category = request.GET.get("category", "")
    difficulty = request.GET.get("difficulty", "")
    sort = request.GET.get("sort", "name")

    places = Place.objects.filter(status="approved")

    if query:
        places = places.filter(name__icontains=query)
    if category:
        places = places.filter(category__slug=category)
    if difficulty:
        places = places.filter(difficulty=difficulty)
    if sort in ["name", "created_at", "visit_count"]:
        places = places.order_by(sort)

    paginator = Paginator(places, 6)
    page_number = request.GET.get("page")
    places_page = paginator.get_page(page_number)

    return render(
        request,
        "search_results.html",
        {
            "places": places_page,
            "query": query,
            "categories": Category.objects.all(),
        },
    )

# ── Profile completion scorer ─────────────────────────────

PROFILE_FIELDS = [
    ('avatar',      20, 'Upload a profile photo'),
    ('bio',         15, 'Write a short bio'),
    ('location',    10, 'Add your location'),
    ('website',      5, 'Link your website'),
    ('first_name',  10, 'Add your first name'),   
    ('last_name',   10, 'Add your last name'),
    ('email',       10, 'Confirm your email'),
    ('show_email',   5, 'Set email visibility'),
    ('show_location',5, 'Set location visibility'),
    ('expert_areas', 10,'Choose areas of expertise'),
]

PROFILE_COMPLETION_TOTAL = sum(w for _, w, _ in PROFILE_FIELDS)  # = 100


def get_profile_completion(user, profile):
    """
    Returns (score: int 0–100, missing: list[str], completed: list[str])
    """
    score = 0
    missing = []
    completed = []

    field_checks = {
        'avatar':       bool(profile.avatar),
        'bio':          bool(profile.bio and profile.bio.strip()),
        'location':     bool(profile.location and profile.location.strip()),
        'website':      bool(profile.website and profile.website.strip()),
        'first_name':   bool(user.first_name and user.first_name.strip()),
        'last_name':    bool(user.last_name and user.last_name.strip()),
        'email':        bool(user.email and user.email.strip()),
        'show_email':   True,           # just having the field set counts
        'show_location':True,
        'expert_areas': profile.expert_areas.exists(),
    }

    for field, weight, hint in PROFILE_FIELDS:
        if field_checks.get(field, False):
            score += weight
            completed.append(hint)
        else:
            missing.append(hint)

    return score, missing, completed


def _resize_avatar(image_file, max_size=(400, 400), quality=85):
    """
    Resize + convert uploaded avatar to JPEG, max 400×400.
    Returns a ContentFile ready to save, or None on error.
    """
    try:
        img = Image.open(image_file)

        # Convert palette/RGBA → RGB for JPEG
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Crop to square from centre
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top  = (h - side) // 2
        img  = img.crop((left, top, left + side, top + side))

        # Resize
        img.thumbnail(max_size, Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format='JPEG', quality=quality, optimize=True)
        return ContentFile(buf.getvalue())
    except Exception:
        return None


ALLOWED_AVATAR_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
MAX_AVATAR_SIZE_MB    = 5


@login_required
def edit_profile(request):
    user    = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # ── Pre-save completion score ──────────────────────────
    score_before, _, _ = get_profile_completion(user, profile)

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)

        # ── Avatar safety checks ──────────────────────────
        avatar_error = None
        avatar_file  = request.FILES.get('avatar')

        if avatar_file:
            content_type = getattr(avatar_file, 'content_type', '')
            size_mb = avatar_file.size / (1024 * 1024)

            if content_type not in ALLOWED_AVATAR_TYPES:
                avatar_error = 'Avatar must be a JPEG, PNG, GIF, or WebP image.'
            elif size_mb > MAX_AVATAR_SIZE_MB:
                avatar_error = f'Avatar must be smaller than {MAX_AVATAR_SIZE_MB} MB.'

        if avatar_error:
            messages.error(request, avatar_error)
            score, missing, completed = get_profile_completion(user, profile)
            return render(request, 'places/edit_profile.html', {
                'form': form,
                'profile': profile,
                'completion_score': score,
                'completion_missing': missing,
                'completion_completed': completed,
            })

        if form.is_valid():
            profile_obj = form.save(commit=False)

            # ── Avatar processing ─────────────────────────
            if avatar_file:
                resized = _resize_avatar(avatar_file)
                if resized:
                    # Delete old avatar to save storage
                    if profile_obj.avatar:
                        old_path = profile_obj.avatar.path
                        if os.path.isfile(old_path):
                            os.remove(old_path)
                    ext      = 'jpg'
                    filename = f'avatar_{user.pk}.{ext}'
                    profile_obj.avatar.save(filename, resized, save=False)

            # ── User model fields ─────────────────────────
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name  = request.POST.get('last_name',  '').strip()

            new_email = request.POST.get('email', '').strip()
            if new_email and new_email != user.email:
                # Basic uniqueness check
                from django.contrib.auth.models import User as AuthUser
                if AuthUser.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                    messages.error(request, 'That email address is already in use.')
                    score, missing, completed = get_profile_completion(user, profile)
                    return render(request, 'places/edit_profile.html', {
                        'form': form,
                        'profile': profile,
                        'completion_score': score,
                        'completion_missing': missing,
                        'completion_completed': completed,
                    })
                user.email = new_email

            user.save()
            profile_obj.save()
            form.save_m2m()

            # ── Post-save completion score ─────────────────
            score_after, missing, completed = get_profile_completion(user, profile_obj)

            # ── Gamification: profile completion milestone ─
            _award_profile_completion_points(user, profile_obj, score_before, score_after)

            # ── Re-evaluate badges (profile fields unlock badges) ──
            evaluate_badges_for_user(user)

            messages.success(request, 'Profile updated successfully!')

            # If they just hit 100% for the first time, celebrate
            if score_before < 100 <= score_after:
                messages.success(request, '🎉 Your profile is now 100% complete! You earned bonus points.')

            return redirect('places:profile', username=user.username)

    else:
        form = UserProfileForm(instance=profile)

    score, missing, completed = get_profile_completion(user, profile)

    context = {
        'form':                 form,
        'profile':              profile,
        'completion_score':     score,
        'completion_missing':   missing,
        'completion_completed': completed,
        # Pre-populate User model fields into context for the template
        'initial_first_name':   user.first_name,
        'initial_last_name':    user.last_name,
        'initial_email':        user.email,
    }
    return render(request, 'places/edit_profile.html', context)


# ── Profile completion point rewards ─────────────────────

_COMPLETION_MILESTONES = {
    25:  ('Profile 25% Complete',  10),
    50:  ('Profile Halfway There', 20),
    75:  ('Profile 75% Complete',  30),
    100: ('Profile Complete! 🎉',  50),
}


def _award_profile_completion_points(user, profile, score_before, score_after):
    """
    Award points and a notification the first time a user crosses
    each completion milestone (25 / 50 / 75 / 100 %).
    Uses notifications as a lightweight "already rewarded" check
    so it's idempotent.
    """
    uprof, _ = UserProfile.objects.get_or_create(user=user)

    for threshold, (title, pts) in _COMPLETION_MILESTONES.items():
        if score_before < threshold <= score_after:
            already = Notification.objects.filter(
                user=user,
                notification_type='profile_complete',
                title=title,
            ).exists()
            if not already:
                uprof.points += pts
                uprof.save(update_fields=['points'])
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=(
                        f'Your profile is now {threshold}% complete. '
                        f'You earned {pts} bonus points!'
                    ),
                    notification_type='profile_complete',
                )

def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Notification.objects.create(
                user=user,
                title="Welcome to RoamLk!",
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
    checkin = get_object_or_404(CheckIn, pk=pk)
    place = checkin.place
    all_checkins = CheckIn.objects.filter(place=place).select_related("user")
    comments = (
        Comment.objects.filter(checkin=checkin, parent=None)
        .select_related("user")
        .prefetch_related("replies")
    )

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.place = checkin.place
            comment.checkin = checkin
            comment.save()
            return redirect(request.path_info)
    else:
        form = CommentForm()

    context = {
        "checkin": checkin,
        "place": place,
        "checkins": all_checkins,
        "comments": comments,
        "form": form,
    }
    return render(request, "checkins/checkin_detail.html", context)


@login_required
@require_POST
def vote_comment(request, comment_id):
    data = json.loads(request.body)
    vote_type = data.get("vote_type")
    comment = get_object_or_404(Comment, id=comment_id)

    vote, created = Vote.objects.get_or_create(user=request.user, comment=comment)
    vote.vote_type = vote_type
    vote.save()

    upvotes = Vote.objects.filter(comment=comment, vote_type="up").count()
    downvotes = Vote.objects.filter(comment=comment, vote_type="down").count()

    return JsonResponse({"success": True, "upvotes": upvotes, "downvotes": downvotes})


@require_POST
def reply_comment(request):
    parent_id = request.POST.get("parent_id")
    text = request.POST.get("reply_text")
    user = request.user

    if not user.is_authenticated:
        return JsonResponse({"success": False, "error": "Login required"}, status=401)

    parent = get_object_or_404(Comment, id=parent_id)
    Comment.objects.create(user=user, place=parent.place, parent=parent, text=text)
    return JsonResponse({"success": True})


def place_checkins(request, slug):
    place = get_object_or_404(Place, slug=slug, status="approved")
    checkins_list = (
        CheckIn.objects.filter(place=place)
        .select_related("user")
        .order_by("-created_at")
    )

    unique_visitors = checkins_list.values("user").distinct().count()
    verified_checkins = checkins_list.filter(location_verified=True).count()
    photo_checkins = (
        checkins_list.exclude(photo_proof__isnull=True).exclude(photo_proof="").count()
    )

    paginator = Paginator(checkins_list, 10)
    page_number = request.GET.get("page")
    checkins = paginator.get_page(page_number)

    context = {
        "place": place,
        "checkins": checkins,
        "unique_visitors": unique_visitors,
        "verified_checkins": verified_checkins,
        "photo_checkins": photo_checkins,
        "has_more": checkins.has_next(),
    }
    return render(request, "place_checkins.html", context)


def route_planner(request):
    destination_id = request.GET.get("destination", "")
    slugs = [s.strip() for s in destination_id.split(",") if s.strip()]
    destination = None
    preselected_waypoints = []

    if slugs:
        destination = Place.objects.filter(slug=slugs[0], status="approved").first()
        if len(slugs) > 1:
            preselected_waypoints = list(
                Place.objects.filter(slug__in=slugs[1:], status="approved").values(
                    "id", "name", "latitude", "longitude"
                )
            )

    all_places = Place.objects.filter(status="approved").prefetch_related("category")
    all_places_data = [
        {
            "id": p.id,
            "name": p.name,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "description": p.description,
            "category": [c.slug for c in p.category.all()],
            "rating": float(p.average_rating) if p.average_rating else 0.0,
        }
        for p in all_places
    ]
    categories = Category.objects.all()
    context = {
        "destination": destination,
        "preselected_waypoints": json.dumps(preselected_waypoints),
        "all_places": json.dumps(all_places_data),
        "categories": categories,
    }
    return render(request, "places/route_planner.html", context)


def about(request):
    return render(request, "about.html")

# ─────────────────────────────────────────────────────────
# Tour views (public + staff-only CRUD)
# ─────────────────────────────────────────────────────────

# ── Public views ──────────────────────────────────────────

def tour_list(request):
    """Public listing of all active tour packages."""
    tours = TourPackage.objects.filter(is_active=True).prefetch_related('trails', 'offerings')
    return render(request, 'tours.html', {'tours': tours})


def tour_detail(request, slug):
    """Public detail page for a single tour package."""
    tour = get_object_or_404(TourPackage, slug=slug, is_active=True)
    trails   = tour.trails.all().prefetch_related('places')
    offerings = tour.offerings.all()
    other_tours = TourPackage.objects.filter(is_active=True).exclude(pk=tour.pk)[:3]

    return render(request, 'tour_detail.html', {
        'tour':        tour,
        'trails':      trails,
        'offerings':   offerings,
        'other_tours': other_tours,
    })


# ── Staff views ───────────────────────────────────────────

@login_required
@user_passes_test(is_staff_or_superuser)
def create_tour(request):
    """Staff-only: create a new tour package."""
    if request.method == 'POST':
        form = TourPackageForm(request.POST, request.FILES)
        if form.is_valid():
            tour = form.save(commit=False)
            tour.created_by = request.user
            tour.save()
            form.save_m2m()
            messages.success(request, f'Tour "{tour.name}" created successfully!')
            return redirect('places:tour_detail', slug=tour.slug)
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = TourPackageForm()

    all_trails   = Trail.objects.filter(is_public=True).order_by('name')
    all_offerings = TourOffering.objects.all().order_by('name')

    return render(request, 'create_tour.html', {
        'form':          form,
        'all_trails':    all_trails,
        'all_offerings': all_offerings,
        'action':        'Create',
    })


@login_required
@user_passes_test(is_staff_or_superuser)
def edit_tour(request, slug):
    """Staff-only: edit an existing tour package."""
    tour = get_object_or_404(TourPackage, slug=slug)

    if request.method == 'POST':
        form = TourPackageForm(request.POST, request.FILES, instance=tour)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tour "{tour.name}" updated!')
            return redirect('places:tour_detail', slug=tour.slug)
        else:
            messages.error(request, 'Please fix the errors below.')
    else:
        form = TourPackageForm(instance=tour)

    all_trails    = Trail.objects.filter(is_public=True).order_by('name')
    all_offerings = TourOffering.objects.all().order_by('name')
    selected_trail_ids    = list(tour.trails.values_list('pk', flat=True))
    selected_offering_ids = list(tour.offerings.values_list('pk', flat=True))

    return render(request, 'create_tour.html', {
        'form':                  form,
        'tour':                  tour,
        'all_trails':            all_trails,
        'all_offerings':         all_offerings,
        'selected_trail_ids':    selected_trail_ids,
        'selected_offering_ids': selected_offering_ids,
        'action':                'Edit',
    })


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def delete_tour(request, slug):
    """Staff-only: delete a tour package."""
    tour = get_object_or_404(TourPackage, slug=slug)
    name = tour.name
    tour.delete()
    messages.success(request, f'Tour "{name}" deleted.')
    return redirect('places:tour_list')


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def toggle_tour_active(request, slug):
    """Staff-only AJAX: toggle is_active on a tour."""
    tour = get_object_or_404(TourPackage, slug=slug)
    tour.is_active = not tour.is_active
    tour.save(update_fields=['is_active'])
    return JsonResponse({'success': True, 'is_active': tour.is_active})


# def route_planner(request):
#     destination_id = request.GET.get('destination', '')
#     slugs = [s.strip() for s in destination_id.split(',') if s.strip()]
#
#     destination = None
#     preselected_waypoints = []

#     if slugs:
#         destination = Place.objects.filter(slug=slugs[0], status='approved').first()
#         if len(slugs) > 1:
#             preselected_waypoints = list(
#                 Place.objects.filter(slug__in=slugs[1:], status='approved')
#                 .values('id', 'name', 'latitude', 'longitude')
#             )

#     context = {
#         'destination': destination,
#         'preselected_waypoints': json.dumps(preselected_waypoints),
#         'all_places': json.dumps(all_places_data),
#         'categories': categories,
#     }


# @require_POST
# def update_place_status(request, slug):
#     if not request.user.is_staff:
#         return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

#     place = get_object_or_404(Place, slug=slug)
#     status = request.POST.get('status')

#     if status in ['approved', 'rejected']:
#         place.status = status
#         place.save()
#         return JsonResponse({'success': True})
#     return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
