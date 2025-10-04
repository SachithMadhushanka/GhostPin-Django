import re
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
import json
import os
from django.utils.text import slugify
import uuid


def place_image_upload_to(instance, filename):
    place_name = slugify(instance.name) if instance.name else 'unknown'
    ext = filename.split('.')[-1]
    unique_suffix = uuid.uuid4().hex[:8]
    filename = f"{place_name}_{unique_suffix}.{ext}"
    return os.path.join('places', place_name, filename)

def user_avatar_upload_to(instance, filename):
    username = slugify(instance.user.username) if instance.user else 'anonymous'
    ext = filename.split('.')[-1]
    unique_suffix = uuid.uuid4().hex[:8]
    filename = f"avatar_{unique_suffix}.{ext}"
    return os.path.join('avatars', username, filename)

def checkin_photo_upload_to(instance, filename):
    username = slugify(instance.user.username) if instance.user else 'anonymous'
    place_name = slugify(instance.place.name) if instance.place else 'unknown-place'
    ext = filename.split('.')[-1]
    unique_suffix = uuid.uuid4().hex[:8]
    filename = f"checkin_{unique_suffix}.{ext}"
    return os.path.join('checkins', username, place_name, filename)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to=user_avatar_upload_to, null=True, blank=True)
    bio = models.TextField(blank=True)
    
    # New fields to match the template
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    show_email = models.BooleanField(default=False)
    show_location = models.BooleanField(default=False)
    allow_messages = models.BooleanField(default=True)
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    weekly_digest = models.BooleanField(default=True)

    # Existing fields
    is_trusted = models.BooleanField(default=False)
    is_local_expert = models.BooleanField(default=False)
    expert_areas = models.ManyToManyField('ExpertArea', blank=True)
    points = models.IntegerField(default=0)
    level = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"



class ExpertArea(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class Place(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('moderate', 'Moderate'),
        ('challenging', 'Challenging'),
    ]
    
    SAFETY_CHOICES = [
        (1, '⭐ Very Unsafe'),
        (2, '⭐⭐ Unsafe'),
        (3, '⭐⭐⭐ Neutral'),
        (4, '⭐⭐⭐⭐ Safe'),
        (5, '⭐⭐⭐⭐⭐ Very Safe'),
    ]

    CATEGORY_CHOICES = [
    ('buddhist_temple', 'Buddhist Temple'),
    ('hindu_temple', 'Hindu Temple'),
    ('mosque', 'Islam Mosque'),
    ('church', 'Christian Church'),
    ('gurdwara', 'Sikh Gurdwara'),
    ('synagogue', 'Jewish Synagogue'),
    ('waterfall', 'Waterfall'),
    ('camping_spot', 'Camping Spot'),
    ('local_food', 'Local Food Spot'),
    ('other', 'Other'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField()
    legends_stories = models.TextField(blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    image = models.ImageField(upload_to=place_image_upload_to, null=True, blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='easy')
    accessibility_info = models.TextField(blank=True)
    best_time_to_visit = models.CharField(max_length=100, blank=True)
    safety_rating = models.IntegerField(choices=SAFETY_CHOICES, default=3)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approval_votes = models.IntegerField(default=0)
    rejection_votes = models.IntegerField(default=0)
    visit_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_absolute_url(self):
        return reverse('place_detail', kwargs={'pk': self.pk})
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    @property
    def average_rating(self):
        ratings = self.comments.filter(rating__isnull=False)
        if ratings.exists():
            return ratings.aggregate(models.Avg('rating'))['rating__avg']
        return 0
    
    def get_icon_url(self):
        icon_map = {
            'buddhist_temple': 'static/icons/buddhist_temple.png',
            'hindu_temple': 'static/icons/hindu_temple.png',
            'mosque': 'static/icons/mosque.png',
            'church': 'static/icons/church.png',
            'gurdwara': 'static/icons/gurdwara.png',
            'synagogue': 'static/icons/synagogue.png',
        }
        return icon_map.get(self.category, 'static/icons/other.png')


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=place_image_upload_to)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_challenge_photo = models.BooleanField(default=False)
    challenge_description = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for {self.place.name}"


class CheckIn(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    photo_proof = models.ImageField(upload_to=checkin_photo_upload_to, null=True, blank=True)
    location_verified = models.BooleanField(default=False)
    points_awarded = models.IntegerField(default=10)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'place']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} checked in at {self.place.name}"


class PlaceCollection(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('moderate', 'Moderate'),
        ('challenging', 'Challenging'),
    ]
    CATEGORY_CHOICES = Place.CATEGORY_CHOICES  # Reuse from Place

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default='other',
    )
    
    name = models.CharField(max_length=200)
    description = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    places = models.ManyToManyField('Place', through='CollectionPlace')
    is_public = models.BooleanField(default=True)
    allow_comments = models.BooleanField(default=True)  # ✅ ADD THIS
    cover_image = models.ImageField(upload_to='collection_covers/', null=True, blank=True)  # ✅ ADD THIS
    distance = models.FloatField(null=True, blank=True)  # ✅ ADD THIS
    estimated_duration = models.DurationField(null=True, blank=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='easy')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class CollectionPlace(models.Model):
    collection = models.ForeignKey(PlaceCollection, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    distance_from_previous = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ['order']
        unique_together = ['collection', 'place']
    
    def __str__(self):
        return f"{self.place.name} in {self.collection.name}"


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='comments')
    checkin = models.ForeignKey('CheckIn', on_delete=models.CASCADE, null=True, blank=True, related_name='comments')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    text = models.TextField()
    votes = models.IntegerField(default=0)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def youtube_id(self):
        match = re.search(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            self.text
        )
        return match.group(1) if match else None
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Comment by {self.user.username} on {self.place.name}'



class Vote(models.Model):
    VOTE_CHOICES = [
        ('up', 'Upvote'),
        ('down', 'Downvote'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    vote_type = models.CharField(max_length=10, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [
            ['user', 'place'],
            ['user', 'comment'],
        ]
    
    def __str__(self):
        target = self.place or self.comment
        return f"{self.user.username} {self.vote_type}voted {target}"


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'place']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} favorited {self.place.name}"

class CollectionFavorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    collection = models.ForeignKey(PlaceCollection, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'collection']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} favorited {self.collection.name}"



class AudioGuide(models.Model):
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='audio_guides')
    title = models.CharField(max_length=200)
    audio_file = models.FileField(upload_to='audio_guides/')
    duration = models.DurationField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Audio guide: {self.title} for {self.place.name}"


class Badge(models.Model):
    CATEGORY_CHOICES = [
        ('explorer', 'Explorer'),
        ('contributor', 'Contributor'),
        ('social', 'Social'),
        ('special', 'Special'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=10)
    criteria = models.JSONField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='explorer')
    points_required = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'badge']
        ordering = ['-earned_at']
    
    def __str__(self):
        return f"{self.user.username} earned {self.badge.name}"


class Challenge(models.Model):
    CHALLENGE_TYPES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('seasonal', 'Seasonal'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    challenge_type = models.CharField(max_length=50, choices=CHALLENGE_TYPES)
    criteria = models.JSONField()
    reward_points = models.IntegerField(default=50)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('place_added', 'Place Added'),
        ('place_approved', 'Place Approved'),
        ('place_rejected', 'Place Rejected'),
        ('comment_reply', 'Comment Reply'),
        ('nearby_place', 'Nearby Place'),
        ('challenge', 'Challenge'),
        ('badge_earned', 'Badge Earned'),
        ('welcome', 'Welcome'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    message = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    is_read = models.BooleanField(default=False)
    related_place = models.ForeignKey(Place, on_delete=models.CASCADE, null=True, blank=True)
    related_collection = models.ForeignKey(PlaceCollection, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"


class Report(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
    ]
    
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE)
    place = models.ForeignKey(Place, on_delete=models.CASCADE, null=True, blank=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        target = self.place or self.comment
        return f"Report by {self.reported_by.username} on {target}"
