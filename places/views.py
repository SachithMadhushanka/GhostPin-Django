from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import json
import os
from django.conf import settings

from .models import (
    Place, Comment, PlaceImage, CheckIn, PlaceCollection, CollectionPlace,
    Vote, Favorite, AudioGuide, Badge, UserBadge, Challenge, Notification,
    Report, UserProfile, ExpertArea
)
from .forms import (
    PlaceForm, CommentForm, PlaceImageForm, CheckInForm, PlaceCollectionForm,
    AudioGuideForm, ReportForm, UserProfileForm, SearchForm, VoteForm
)


# Core Views
def home(request):
    """Enhanced homepage with search, filters, and featured content"""
    search_form = SearchForm(request.GET)
    places = Place.objects.filter(status='approved')
    
    # Apply search filters
    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        category = search_form.cleaned_data.get('category')
        difficulty = search_form.cleaned_data.get('difficulty')
        
        if query:
            places = places.filter(
                Q(name__icontains=query) | 
                Q(description__icontains=query) |
                Q(legends_stories__icontains=query)
            )
        if category:
            places = places.filter(category=category)
        if difficulty:
            places = places.filter(difficulty=difficulty)
    
    # Get featured collections
    featured_collections = PlaceCollection.objects.filter(is_public=True)[:3]
    
    # Get trending places (most visited in last 30 days)
    trending_places = places.order_by('-visit_count')[:6]
    
    # Pagination
    paginator = Paginator(places, 12)
    page_number = request.GET.get('page')
    places_page = paginator.get_page(page_number)
    
    context = {
        'places': places_page,
        'search_form': search_form,
        'featured_collections': featured_collections,
        'trending_places': trending_places,
    }
    return render(request, 'home.html', context)


def place_detail(request, pk):
    """Enhanced place detail with all features"""
    place = get_object_or_404(Place, pk=pk)
    
    # Only show approved places to non-owners
    if place.status != 'approved' and place.created_by != request.user:
        if not request.user.is_staff:
            messages.error(request, 'This place is not available.')
            return redirect('home')
    
    # Increment visit count
    place.visit_count += 1
    place.save(update_fields=['visit_count'])
    
    # Get related data
    comments = place.comments.filter(parent=None).prefetch_related('replies')
    place_images = place.images.all()
    audio_guides = place.audio_guides.filter(is_approved=True)
    
    # Check if user has favorited this place
    is_favorited = False
    user_checkin = None
    if request.user.is_authenticated:
        is_favorited = Favorite.objects.filter(user=request.user, place=place).exists()
        user_checkin = CheckIn.objects.filter(user=request.user, place=place).first()
    
    # Handle comment submission
    comment_form = CommentForm()
    if request.method == 'POST' and request.user.is_authenticated:
        if 'comment_submit' in request.POST:
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.user = request.user
                comment.place = place
                comment.save()
                
                # Award points for commenting
                profile, created = UserProfile.objects.get_or_create(user=request.user)
                profile.points += 5
                profile.save()
                
                messages.success(request, 'Comment added successfully!')
                return redirect('place_detail', pk=place.pk)
    
    context = {
        'place': place,
        'comments': comments,
        'comment_form': comment_form,
        'place_images': place_images,
        'audio_guides': audio_guides,
        'is_favorited': is_favorited,
        'user_checkin': user_checkin,
    }
    return render(request, 'place_detail.html', context)


@login_required
def add_place(request):
    """Enhanced place submission form"""
    if request.method == 'POST':
        form = PlaceForm(request.POST, request.FILES)
        if form.is_valid():
            place = form.save(commit=False)
            place.created_by = request.user
            place.status = 'pending'
            place.save()
            
            # Award points for adding a place
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.points += 20
            profile.save()
            
            messages.success(request, 'Place submitted successfully! It will be reviewed by our team.')
            return redirect('home')
    else:
        form = PlaceForm()
    
    return render(request, 'add_place.html', {'form': form})


@login_required
def edit_place(request, pk):
    """Edit place (owner or admin only)"""
    place = get_object_or_404(Place, pk=pk)
    
    if place.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'You can only edit your own places.')
        return redirect('place_detail', pk=place.pk)
    
    if request.method == 'POST':
        form = PlaceForm(request.POST, request.FILES, instance=place)
        if form.is_valid():
            form.save()
            messages.success(request, 'Place updated successfully!')
            return redirect('place_detail', pk=place.pk)
    else:
        form = PlaceForm(instance=place)
    
    return render(request, 'edit_place.html', {'form': form, 'place': place})


# User Views
@login_required
def profile(request, username):
    """User profile page"""
    user = get_object_or_404(User, username=username)
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Get user's contributions
    user_places = Place.objects.filter(created_by=user, status='approved')
    user_checkins = CheckIn.objects.filter(user=user)
    user_badges = UserBadge.objects.filter(user=user)
    user_collections = PlaceCollection.objects.filter(created_by=user, is_public=True)
    
    # Calculate level based on points
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
        'profile_user': user,
        'profile': profile,
        'user_places': user_places,
        'user_checkins': user_checkins,
        'user_badges': user_badges,
        'user_collections': user_collections,
    }
    return render(request, 'profile.html', context)


@login_required
def favorites(request):
    """User's favorite places"""
    favorites = Favorite.objects.filter(user=request.user).select_related('place')
    return render(request, 'favorites.html', {'favorites': favorites})


@login_required
def notifications(request):
    """User notifications"""
    notifications = Notification.objects.filter(user=request.user)
    
    # Mark all as read
    if request.method == 'POST':
        notifications.update(is_read=True)
        return redirect('notifications')
    
    return render(request, 'notifications.html', {'notifications': notifications})


@login_required
def check_ins(request):
    """User's check-in history"""
    checkins = CheckIn.objects.filter(user=request.user).select_related('place')
    return render(request, 'check_ins.html', {'checkins': checkins})


# Check-in System
@login_required
def check_in(request, pk):
    """Check in at a place"""
    place = get_object_or_404(Place, pk=pk, status='approved')
    
    # Check if user already checked in
    existing_checkin = CheckIn.objects.filter(user=request.user, place=place).first()
    if existing_checkin:
        messages.info(request, 'You have already checked in at this place.')
        return redirect('place_detail', pk=place.pk)
    
    if request.method == 'POST':
        form = CheckInForm(request.POST, request.FILES)
        if form.is_valid():
            checkin = form.save(commit=False)
            checkin.user = request.user
            checkin.place = place
            checkin.save()
            
            # Award points
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.points += checkin.points_awarded
            profile.save()
            
            messages.success(request, f'Checked in successfully! You earned {checkin.points_awarded} points.')
            return redirect('place_detail', pk=place.pk)
    else:
        form = CheckInForm()
    
    return render(request, 'check_in.html', {'form': form, 'place': place})


# Collections
def collections(request):
    """Browse public collections"""
    collections = PlaceCollection.objects.filter(is_public=True).annotate(
        place_count=Count('places')
    )
    return render(request, 'collections.html', {'collections': collections})


def collection_detail(request, pk):
    """Collection detail with route map"""
    collection = get_object_or_404(PlaceCollection, pk=pk)
    
    if not collection.is_public and collection.created_by != request.user:
        raise Http404("Collection not found")
    
    collection_places = CollectionPlace.objects.filter(
        collection=collection
    ).select_related('place').order_by('order')
    
    return render(request, 'collection_detail.html', {
        'collection': collection,
        'collection_places': collection_places
    })


@login_required
def create_collection(request):
    """Create a new collection"""
    if request.method == 'POST':
        form = PlaceCollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.created_by = request.user
            collection.save()
            
            messages.success(request, 'Collection created successfully!')
            return redirect('collection_detail', pk=collection.pk)
    else:
        form = PlaceCollectionForm()
    
    return render(request, 'create_collection.html', {'form': form})


# Gamification
def leaderboard(request):
    """User leaderboard"""
    top_users = UserProfile.objects.select_related('user').order_by('-points')[:50]
    return render(request, 'leaderboard.html', {'top_users': top_users})


def challenges(request):
    """Current and past challenges"""
    active_challenges = Challenge.objects.filter(
        is_active=True,
        start_date__lte=timezone.now(),
        end_date__gte=timezone.now()
    )
    past_challenges = Challenge.objects.filter(
        end_date__lt=timezone.now()
    ).order_by('-end_date')[:10]
    
    return render(request, 'challenges.html', {
        'active_challenges': active_challenges,
        'past_challenges': past_challenges
    })


def badges(request):
    """All available badges"""
    all_badges = Badge.objects.filter(is_active=True)
    user_badges = []
    
    if request.user.is_authenticated:
        user_badges = UserBadge.objects.filter(user=request.user).values_list('badge_id', flat=True)
    
    return render(request, 'badges.html', {
        'all_badges': all_badges,
        'user_badges': user_badges
    })


# AJAX Views
@login_required
@require_POST
def toggle_favorite(request, pk):
    """Toggle favorite status for a place"""
    place = get_object_or_404(Place, pk=pk)
    favorite, created = Favorite.objects.get_or_create(user=request.user, place=place)
    
    if not created:
        favorite.delete()
        is_favorited = False
    else:
        is_favorited = True
    
    return JsonResponse({'is_favorited': is_favorited})


@login_required
@require_POST
def vote_place(request, pk):
    """Vote on a place"""
    place = get_object_or_404(Place, pk=pk)
    vote_type = request.POST.get('vote_type')
    
    if vote_type not in ['up', 'down']:
        return JsonResponse({'success': False, 'error': 'Invalid vote type'})
    
    vote, created = Vote.objects.get_or_create(
        user=request.user, place=place,
        defaults={'vote_type': vote_type}
    )
    
    if not created:
        if vote.vote_type == vote_type:
            vote.delete()
            return JsonResponse({'success': True, 'action': 'removed'})
        else:
            vote.vote_type = vote_type
            vote.save()
    
    # Update place vote counts
    place.approval_votes = Vote.objects.filter(place=place, vote_type='up').count()
    place.rejection_votes = Vote.objects.filter(place=place, vote_type='down').count()
    place.save()
    
    return JsonResponse({
        'success': True,
        'action': 'voted',
        'approval_votes': place.approval_votes,
        'rejection_votes': place.rejection_votes
    })


# Admin Views
def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_or_superuser)
def review_places(request):
    """Admin view to approve/reject submitted places"""
    pending_places = Place.objects.filter(status='pending').select_related('created_by')
    return render(request, 'review_places.html', {'places': pending_places})


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def update_place_status(request, pk):
    """AJAX endpoint to update place status"""
    place = get_object_or_404(Place, pk=pk)
    status = request.POST.get('status')
    
    if status in ['approved', 'rejected']:
        place.status = status
        place.save()
        
        # Create notification for place owner
        Notification.objects.create(
            user=place.created_by,
            title=f'Place {status.title()}',
            message=f'Your place "{place.name}" has been {status}.',
            notification_type=f'place_{status}',
            related_place=place
        )
        
        # Award points for approved places
        if status == 'approved':
            profile, created = UserProfile.objects.get_or_create(user=place.created_by)
            profile.points += 50  # Bonus for approved place
            profile.save()
        
        return JsonResponse({'success': True, 'status': status})
    
    return JsonResponse({'success': False, 'error': 'Invalid status'})


@login_required
@user_passes_test(is_staff_or_superuser)
def analytics(request):
    """Admin analytics dashboard"""
    total_places = Place.objects.count()
    approved_places = Place.objects.filter(status='approved').count()
    pending_places = Place.objects.filter(status='pending').count()
    total_users = User.objects.count()
    total_checkins = CheckIn.objects.count()
    
    # Recent activity
    recent_places = Place.objects.order_by('-created_at')[:10]
    recent_checkins = CheckIn.objects.select_related('user', 'place').order_by('-created_at')[:10]
    
    context = {
        'total_places': total_places,
        'approved_places': approved_places,
        'pending_places': pending_places,
        'total_users': total_users,
        'total_checkins': total_checkins,
        'recent_places': recent_places,
        'recent_checkins': recent_checkins,
    }
    return render(request, 'analytics.html', context)


# PWA Views (from original implementation)
def manifest(request):
    """Serve PWA manifest.json"""
    manifest_data = {
        "name": "GhostPin - Explore Historical Places",
        "short_name": "GhostPin",
        "description": "Discover and explore historical places around the world",
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
                "purpose": "any maskable"
            },
            {
                "src": "/static/icons/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ],
        "shortcuts": [
            {
                "name": "Add New Place",
                "short_name": "Add Place",
                "description": "Submit a new historical place",
                "url": "/place/add/",
                "icons": [
                    {
                        "src": "/static/icons/icon-192x192.png",
                        "sizes": "192x192"
                    }
                ]
            }
        ]
    }
    
    response = JsonResponse(manifest_data)
    response['Content-Type'] = 'application/manifest+json'
    return response


def service_worker(request):
    """Serve service worker JavaScript file"""
    service_worker_path = os.path.join(settings.BASE_DIR, 'static', 'service-worker.js')
    
    try:
        with open(service_worker_path, 'r') as f:
            content = f.read()
        
        from django.http import HttpResponse
        response = HttpResponse(content, content_type='application/javascript')
        response['Cache-Control'] = 'no-cache'
        return response
    except FileNotFoundError:
        from django.http import Http404
        raise Http404("Service worker not found")

