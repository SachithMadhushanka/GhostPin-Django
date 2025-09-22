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
import json
import os
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.db.models import Sum 
from geopy.distance import geodesic
from django.views.decorators.csrf import csrf_exempt

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
            return redirect('places:home')
    
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
                return redirect('places:place_detail', pk=place.pk)
    
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

            Notification.objects.create(
                user=request.user,
                title='Place Submitted',
                message=f'You added a new place: "{place.name}" and it is pending approval.',
                notification_type='place_added',
                related_place=place  # assuming your model has this FK
            )

            # Award points for adding a place
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            profile.points += 20
            profile.save()
            
            messages.success(request, 'Place submitted successfully! It will be reviewed by our team.')
            return redirect('places:home')
    else:
        form = PlaceForm()
    
    return render(request, 'add_place.html', {'form': form})


@login_required
def edit_place(request, pk):
    """Edit place (owner or admin only)"""
    place = get_object_or_404(Place, pk=pk)

    if place.created_by != request.user and not request.user.is_staff:
        messages.error(request, 'You can only edit your own places.')
        return redirect('places:place_detail', pk=place.pk)

    if request.method == 'POST':
        form = PlaceForm(request.POST, request.FILES, instance=place)
        if form.is_valid():
            form.save()
            messages.success(request, 'Place updated successfully!')
            return redirect('places:place_detail', pk=place.pk)
        else:
            print(form.errors)
            messages.error(request, 'Please correct the errors below.')
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
    notification_list = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    paginator = Paginator(notification_list, 10)
    page_number = request.GET.get('page')
    notifications_page = paginator.get_page(page_number)

    unread_count = notification_list.filter(is_read=False).count()

    return render(request, 'notifications.html', {
        'notifications': notifications_page,
        'unread_count': unread_count
    })

# Notification API Views
@login_required
@require_POST
def mark_notification_read(request, pk):
    """Mark a single notification as read"""
    try:
        notification = Notification.objects.get(pk=pk, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'})


@login_required
@require_POST
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    updated_count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True, 'updated_count': updated_count})


@login_required
def delete_notification(request, pk):
    """Delete a single notification"""
    if request.method == 'DELETE':
        try:
            notification = Notification.objects.get(pk=pk, user=request.user)
            notification.delete()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
def clear_all_notifications(request):
    """Delete all notifications for the current user"""
    if request.method == 'DELETE':
        deleted_count = Notification.objects.filter(user=request.user).count()
        Notification.objects.filter(user=request.user).delete()
        return JsonResponse({'success': True, 'deleted_count': deleted_count})
    return JsonResponse({'success': False, 'error': 'Invalid method'})


@login_required
def check_new_notifications(request):
    """Check for new unread notifications"""
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    has_new = unread_count > 0
    return JsonResponse({
        'has_new': has_new,
        'unread_count': unread_count
    })

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
        return redirect('places:place_detail', pk=place.pk)
    
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
            return redirect('places:place_detail', pk=place.pk)
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
            return redirect('places:collection_detail', pk=collection.pk)
    else:
        form = PlaceCollectionForm()
    
    return render(request, 'create_collection.html', {'form': form})


# Gamification
def leaderboard(request):
    """User leaderboard"""
    top_users = (
        UserProfile.objects.select_related('user')
        .annotate(approved_places=Count('user__place', filter=Q(user__place__status='approved')))
        .order_by('-points')[:50]
    )
    total_points = top_users.aggregate(Sum('points'))['points__sum'] or 0

    user_rank = None
    if request.user.is_authenticated and hasattr(request.user, 'userprofile'):
        # Count how many users have more points than the current user
        higher_ranked = UserProfile.objects.filter(points__gt=request.user.userprofile.points).count()
        user_rank = higher_ranked + 1  # Rank is 1 + number of users above

    return render(request, 'leaderboard.html', {
        'top_users': top_users,
        'user_rank': user_rank,
        'total_points': total_points,
    })


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

    is_favorited = Favorite.objects.filter(user=request.user, place=place).exists()

    # HTMX request → return only updated button HTML
    if request.headers.get("HX-Request"):
        html = render_to_string("partials/favorite_button.html", {
            "place": place,
            "is_favorited": is_favorited,
        }, request=request)
        return HttpResponse(html)

    # Normal request → redirect
    return redirect("places:place_detail", pk=pk)

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
            message=(
                f'Your place "{place.name}" was {status} '
                f'by {request.user.get_full_name() or request.user.username}.'
            ),
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

@login_required
def nearby_places_view(request):
    return render(request, 'nearby_places.html')

def get_nearby_places(request):
    try:
        lat = float(request.GET.get('lat'))
        lng = float(request.GET.get('lng'))
        distance_km = float(request.GET.get('distance', 10))

        user_location = (lat, lng)
        places = []

        for place in Place.objects.all():
            place_location = (place.latitude, place.longitude)
            distance = geodesic(user_location, place_location).km
            if distance <= distance_km:
                places.append({
                    'id': place.id,
                    'name': place.name,
                    'description': place.description,
                    'category': place.category,
                    'category_icon': getattr(place, 'category_icon', '🏛️'),
                    'latitude': place.latitude,
                    'longitude': place.longitude,
                    'distance': round(distance, 2),
                    'rating': place.average_rating,
                    'visit_count': place.visit_count
                })
        
        if request.user.is_authenticated and len(places) > 0:
            nearby_count = len(places)

            # Optional: avoid duplicate notifications within the last hour
            recent = Notification.objects.filter(
                user=request.user,
                notification_type='nearby_place',
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).exists()

            if not recent:
                Notification.objects.create(
                    user=request.user,
                    title="Nearby Places Alert",
                    message=f"There are {nearby_count} historical places near you. Check them out!",
                    notification_type="nearby_place"
                )

        return JsonResponse({'places': places})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def search_results(request):
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    difficulty = request.GET.get('difficulty', '')
    sort = request.GET.get('sort', 'name')  # default sort

    places = Place.objects.all()

    if query:
        places = places.filter(name__icontains=query)

    if category:
        places = places.filter(category=category)

    if difficulty:
        places = places.filter(difficulty=difficulty)

    if sort in ['name', 'created_at', 'visit_count', 'average_rating']:
        places = places.order_by(sort)

    paginator = Paginator(places, 6)  # 6 per page
    page_number = request.GET.get('page')
    places_page = paginator.get_page(page_number)

    return render(request, 'search_results.html', {
        'places': places_page,
        'query': query
    })

@login_required
def edit_profile(request):
    user = request.user
    profile = user.userprofile  # Adjust if you're using OneToOneField or similar

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)

        if form.is_valid():
            form.save()
            # Update base User model fields too
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.save()

            return redirect('places:profile', username=user.username)
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'places/edit_profile.html', {
        'form': form,
        'user': user,
    })

@require_POST
def update_place_status(request, pk):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    place = get_object_or_404(Place, pk=pk)
    status = request.POST.get('status')

    if status in ['approved', 'rejected']:
        place.status = status
        place.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()

            # ✅ Create welcome notification after signup
            Notification.objects.create(
                user=user,
                title="Welcome to GhostPin!",
                message="Thanks for signing up! Start exploring and adding historical places.",
                notification_type="welcome",
            )

            messages.success(request, 'Account created successfully. Please log in.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def checkin_detail(request, pk):
    checkin = get_object_or_404(CheckIn, pk=pk)
    place = checkin.place
    all_checkins = CheckIn.objects.filter(place=place).select_related('user')
    comments = Comment.objects.filter(checkin=checkin, parent=None).select_related('user').prefetch_related('replies')

    if request.method == 'POST':
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
        'checkin': checkin,
        'place': place,
        'checkins': all_checkins,
        'comments': comments,
        'form': form,
    }
    return render(request, 'checkins/checkin_detail.html', context)

@csrf_exempt
@require_POST
def vote_comment(request, comment_id):
    import json
    data = json.loads(request.body)

    vote_type = data.get('vote_type')
    user = request.user
    comment = get_object_or_404(Comment, id=comment_id)

    if not user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Login required'}, status=401)

    vote, created = Vote.objects.get_or_create(user=user, comment=comment)

    if not created:
        # User already voted, update
        vote.vote_type = vote_type
        vote.save()
    else:
        vote.vote_type = vote_type
        vote.save()

    # Calculate new vote counts
    upvotes = Vote.objects.filter(comment=comment, vote_type='up').count()
    downvotes = Vote.objects.filter(comment=comment, vote_type='down').count()

    return JsonResponse({
        'success': True,
        'upvotes': upvotes,
        'downvotes': downvotes
    })

@csrf_exempt
@require_POST
def reply_comment(request):
    parent_id = request.POST.get('parent_id')
    text = request.POST.get('reply_text')
    user = request.user

    if not user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Login required'}, status=401)

    parent = get_object_or_404(Comment, id=parent_id)

    reply = Comment.objects.create(
        user=user,
        place=parent.place,
        parent=parent,
        text=text
    )

    return JsonResponse({'success': True})

def place_checkins(request, pk):
    """Display all check-ins for a specific place with full details"""
    place = get_object_or_404(Place, pk=pk, status='approved')
    
    # Get all check-ins for this place
    checkins_list = CheckIn.objects.filter(place=place).select_related('user').order_by('-created_at')
    
    # Calculate statistics
    unique_visitors = checkins_list.values('user').distinct().count()
    verified_checkins = checkins_list.filter(location_verified=True).count() 
    photo_checkins = checkins_list.exclude(photo_proof__isnull=True).exclude(photo_proof='').count()  # ✅ ensure correct field
    
    # Pagination
    paginator = Paginator(checkins_list, 10)  # Show 10 check-ins per page
    page_number = request.GET.get('page')
    checkins = paginator.get_page(page_number)
    
    # Check if there are more pages
    has_more = checkins.has_next()
    
    context = {
        'place': place,
        'checkins': checkins,
        'unique_visitors': unique_visitors,
        'verified_checkins': verified_checkins,
        'photo_checkins': photo_checkins,
        'has_more': has_more,
    }
    return render(request, 'place_checkins.html', context)

def route_planner(request):
    """Route planner with waypoint discovery"""
    destination_id = request.GET.get('destination')
    destination = None
    
    if destination_id:
        try:
            destination = Place.objects.get(pk=destination_id, status='approved')
        except Place.DoesNotExist:
            destination = None
    
    # Get all approved places for potential waypoints
    all_places = Place.objects.filter(status='approved').values(
        'id', 'name', 'latitude', 'longitude', 'category', 'description'
    )
    
    context = {
        'destination': destination,
        'all_places': list(all_places),
    }
    return render(request, 'places/route_planner.html', context)