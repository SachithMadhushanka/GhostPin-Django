import re
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
import json
import os
from django.utils.text import slugify
import uuid


# ─────────────────────────────────────────────────────────
# Upload path helpers
# ─────────────────────────────────────────────────────────

def place_image_upload_to(instance, filename):
    """Used for Place.image — instance IS the Place."""
    place_name    = slugify(instance.name)
    ext           = filename.split('.')[-1]
    unique_suffix = uuid.uuid4().hex[:8]
    filename      = f"{place_name}_{unique_suffix}.{ext}"
    return os.path.join('places', place_name, filename)


def place_extra_image_upload_to(instance, filename):
    """Used for PlaceImage.image — instance has a .place FK."""
    place_name    = slugify(instance.place.name) if instance.place else 'unknown'
    ext           = filename.split('.')[-1]
    unique_suffix = uuid.uuid4().hex[:8]
    filename      = f"{place_name}_{unique_suffix}.{ext}"
    return os.path.join('places', place_name, filename)


def badge_image_upload_to(instance, filename):
    ext           = filename.split('.')[-1]
    unique_suffix = uuid.uuid4().hex[:8]
    return os.path.join('badges', f"{slugify(instance.name)}_{unique_suffix}.{ext}")


def user_avatar_upload_to(instance, filename):
    username      = slugify(instance.user.username) if instance.user else 'anonymous'
    ext           = filename.split('.')[-1]
    unique_suffix = uuid.uuid4().hex[:8]
    filename      = f"avatar_{unique_suffix}.{ext}"
    return os.path.join('avatars', username, filename)


def checkin_photo_upload_to(instance, filename):
    username      = slugify(instance.user.username)  if instance.user  else 'anonymous'
    place_name    = slugify(instance.place.name)     if instance.place else 'unknown-place'
    ext           = filename.split('.')[-1]
    unique_suffix = uuid.uuid4().hex[:8]
    filename      = f"checkin_{unique_suffix}.{ext}"
    return os.path.join('checkins', username, place_name, filename)

# ─────────────────────────────────────────────────────────
# UserProfile class
# ─────────────────────────────────────────────────────────

class UserProfile(models.Model):
    user   = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to=user_avatar_upload_to, null=True, blank=True)
    bio    = models.TextField(blank=True)

    # Location
    location      = models.CharField(max_length=100, blank=True)
    show_location = models.BooleanField(default=False)

    # Contact — phone
    phone_number = models.CharField(max_length=30, blank=True)
    show_phone   = models.BooleanField(default=False)

    # Website
    website_url = models.URLField(blank=True, verbose_name="Website URL")

    # Social media
    youtube_url   = models.URLField(blank=True, verbose_name="YouTube URL")
    facebook_url  = models.URLField(blank=True, verbose_name="Facebook URL")
    instagram_url = models.URLField(blank=True, verbose_name="Instagram URL")
    tiktok_url    = models.URLField(blank=True, verbose_name="TikTok URL")
    linkedin_url  = models.URLField(blank=True, verbose_name="LinkedIn URL")
    x_url         = models.URLField(blank=True, verbose_name="X (Twitter) URL")

    # Privacy
    show_email       = models.BooleanField(default=False)
    allow_messages   = models.BooleanField(default=True)

    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    push_notifications  = models.BooleanField(default=True)
    weekly_digest       = models.BooleanField(default=True)

    # Expertise / gamification
    is_trusted      = models.BooleanField(default=False)
    is_local_expert = models.BooleanField(default=False)
    expert_areas    = models.ManyToManyField('ExpertArea', blank=True)
    points          = models.IntegerField(default=0)
    level           = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def approved_places(self):
        return Place.objects.filter(created_by=self.user, status='approved').count()

    def __str__(self):
        return f"{self.user.username}'s Profile"

    # ── Helpers used by templates ──────────────────────────
    @property
    def social_links(self):
        """Return a list of (platform, url, icon_class, label) for non-empty URLs."""
        platforms = [
            ('website',   self.website_url,   'fas fa-globe',       'Website'),
            ('youtube',   self.youtube_url,   'fab fa-youtube',     'YouTube'),
            ('facebook',  self.facebook_url,  'fab fa-facebook',    'Facebook'),
            ('instagram', self.instagram_url, 'fab fa-instagram',   'Instagram'),
            ('tiktok',    self.tiktok_url,    'fab fa-tiktok',      'TikTok'),
            ('linkedin',  self.linkedin_url,  'fab fa-linkedin',    'LinkedIn'),
            ('x',         self.x_url,         'fab fa-x-twitter',   'X'),
        ]
        return [(slug, url, icon, label) for slug, url, icon, label in platforms if url]

# ─────────────────────────────────────────────────────────
# Supporting lookups
# ─────────────────────────────────────────────────────────

class ExpertArea(models.Model):
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────
# Place
# ─────────────────────────────────────────────────────────

class Place(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    DIFFICULTY_CHOICES = [
        ('easy',        'Easy'),
        ('moderate',    'Moderate'),
        ('challenging', 'Challenging'),
    ]

    SAFETY_CHOICES = [
        (1, '⭐ Very Unsafe'),
        (2, '⭐⭐ Unsafe'),
        (3, '⭐⭐⭐ Neutral'),
        (4, '⭐⭐⭐⭐ Safe'),
        (5, '⭐⭐⭐⭐⭐ Very Safe'),
    ]

    name               = models.CharField(max_length=200)
    slug               = models.SlugField(max_length=250, unique=True, blank=True)
    description        = models.TextField()
    legends_stories    = models.TextField(blank=True)
    latitude           = models.FloatField(null=True, blank=True, default=0)
    longitude          = models.FloatField(null=True, blank=True, default=0)
    image              = models.ImageField(
        upload_to=place_image_upload_to, max_length=300, null=True, blank=True
    )
    category           = models.ManyToManyField(Category, related_name='places')
    difficulty         = models.CharField(
        max_length=20, choices=DIFFICULTY_CHOICES, default='easy'
    )
    accessibility_info = models.TextField(blank=True)
    best_time_to_visit = models.CharField(max_length=200, blank=True)
    safety_rating      = models.IntegerField(choices=SAFETY_CHOICES, default=3)
    created_by         = models.ForeignKey(User, on_delete=models.CASCADE)
    updated_by         = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_places'
    )
    status             = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    approval_votes     = models.IntegerField(default=0)
    rejection_votes    = models.IntegerField(default=0)
    visit_count        = models.IntegerField(default=0)
    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug      = base_slug
            while Place.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('places:place_detail', kwargs={'slug': self.slug})

    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def average_rating(self):
        ratings = self.comments.filter(rating__isnull=False)
        if ratings.exists():
            return ratings.aggregate(models.Avg('rating'))['rating__avg']
        return 0


# ─────────────────────────────────────────────────────────
# Place media
# ─────────────────────────────────────────────────────────

class PlaceImage(models.Model):
    place                 = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='images')
    image                 = models.ImageField(upload_to=place_extra_image_upload_to, max_length=300)
    uploaded_by           = models.ForeignKey(User, on_delete=models.CASCADE)
    is_challenge_photo    = models.BooleanField(default=False)
    challenge_description = models.CharField(max_length=200, blank=True)
    created_at            = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.place.name}"


class PlaceVideo(models.Model):
    PLATFORM_CHOICES = [
        ('youtube',   'YouTube'),
        ('facebook',  'Facebook'),
        ('instagram', 'Instagram'),
        ('tiktok',    'TikTok'),
    ]
    place         = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='videos')
    uploaded_by   = models.ForeignKey(User, on_delete=models.CASCADE)
    url           = models.URLField()
    platform      = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    thumbnail_url = models.URLField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.platform} video for {self.place.name}"


# ─────────────────────────────────────────────────────────
# Check-in
# ─────────────────────────────────────────────────────────

class CheckIn(models.Model):
    """
    Records a user's visit to a place.

    Anti-cheat fields:
      photo_hash  — SHA-256 of the uploaded photo bytes; used to reject reused images.
      trust_score — Raw score (0–5+) from checkin_trust.compute_trust_score().
                    0–1 = unverified, 2–3 = likely, 4+ = verified.
    """
    user              = models.ForeignKey(User, on_delete=models.CASCADE)
    place             = models.ForeignKey(Place, on_delete=models.CASCADE)
    photo_proof       = models.ImageField(
        upload_to=checkin_photo_upload_to, null=True, blank=True
    )
    location_verified = models.BooleanField(default=False)
    photo_hash        = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    trust_score       = models.PositiveSmallIntegerField(default=0)
    points_awarded    = models.IntegerField(default=10)
    notes             = models.TextField(blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'place']
        ordering        = ['-created_at']

    def __str__(self):
        return f"{self.user.username} checked in at {self.place.name}"

    @property
    def trust_tier(self):
        """Human-readable tier derived from trust_score."""
        if self.trust_score >= 4:
            return 'verified'
        if self.trust_score >= 2:
            return 'likely'
        return 'unverified'


# ─────────────────────────────────────────────────────────
# Trails
# ─────────────────────────────────────────────────────────

class Trail(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy',        'Easy'),
        ('moderate',    'Moderate'),
        ('challenging', 'Challenging'),
    ]

    name               = models.CharField(max_length=200)
    description        = models.TextField()
    created_by         = models.ForeignKey(User, on_delete=models.CASCADE)
    places             = models.ManyToManyField(
        'Place', through='TrailPlace', related_name='trails'
    )
    category           = models.ManyToManyField(Category, related_name='trails', blank=True)
    is_public          = models.BooleanField(default=True)
    allow_comments     = models.BooleanField(default=True)
    cover_image        = models.ImageField(
        upload_to='trail_covers/', max_length=300, null=True, blank=True
    )
    distance           = models.FloatField(null=True, blank=True)
    estimated_duration = models.DurationField(null=True, blank=True)
    difficulty         = models.CharField(
        max_length=20, choices=DIFFICULTY_CHOICES, default='easy'
    )
    required_points    = models.IntegerField(default=0)
    completion_badge   = models.ForeignKey(
        'Badge', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='trail_reward'
    )
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def duration_display(self):
        if not self.estimated_duration:
            return None
        total   = int(self.estimated_duration.total_seconds())
        hours   = total // 3600
        minutes = (total % 3600) // 60
        if hours and minutes:
            return f"{hours}h {minutes}m"
        if hours:
            return f"{hours} hours"
        return f"{minutes}m"


class TrailPlace(models.Model):
    trail                  = models.ForeignKey(Trail, on_delete=models.CASCADE)
    place                  = models.ForeignKey(Place, on_delete=models.CASCADE)
    order                  = models.PositiveIntegerField()
    notes                  = models.TextField(blank=True)
    distance_from_previous = models.FloatField(null=True, blank=True)
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering        = ['order']
        unique_together = ['trail', 'place']

    def __str__(self):
        return f"{self.place.name} in {self.trail.name}"


class TrailCompletion(models.Model):
    """
    Records that a user has fully completed a trail (checked in at every place).
    Used instead of Notification text-matching — rename-safe and O(1) to query.
    """
    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trail_completions')
    trail          = models.ForeignKey(Trail, on_delete=models.CASCADE, related_name='completions')
    completed_at   = models.DateTimeField(auto_now_add=True)
    points_awarded = models.IntegerField(default=0)

    class Meta:
        unique_together = ['user', 'trail']
        ordering        = ['-completed_at']

    def __str__(self):
        return f"{self.user.username} completed '{self.trail.name}'"


# ─────────────────────────────────────────────────────────
# Comments & votes
# ─────────────────────────────────────────────────────────

class Comment(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    place      = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='comments')
    checkin    = models.ForeignKey(
        CheckIn, on_delete=models.CASCADE, null=True, blank=True, related_name='comments'
    )
    parent     = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies'
    )
    text       = models.TextField()
    votes      = models.IntegerField(default=0)
    rating     = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.user.username} on {self.place.name}'

    @property
    def youtube_id(self):
        match = re.search(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            self.text,
        )
        return match.group(1) if match else None


class Vote(models.Model):
    VOTE_CHOICES = [
        ('up',   'Upvote'),
        ('down', 'Downvote'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    place      = models.ForeignKey(Place,   on_delete=models.CASCADE, null=True, blank=True)
    comment    = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
    vote_type  = models.CharField(max_length=10, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ['user', 'place'],
            ['user', 'comment'],
        ]

    def __str__(self):
        target = self.place or self.comment
        return f"{self.user.username} {self.vote_type}voted {target}"


# ─────────────────────────────────────────────────────────
# Favourites
# ─────────────────────────────────────────────────────────

class Favorite(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    place      = models.ForeignKey(Place, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'place']
        ordering        = ['-created_at']

    def __str__(self):
        return f"{self.user.username} favorited {self.place.name}"


class TrailFavorite(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    trail      = models.ForeignKey(Trail, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'trail']
        ordering        = ['-created_at']

    def __str__(self):
        return f"{self.user.username} favorited {self.trail.name}"


# ─────────────────────────────────────────────────────────
# Badges
# ─────────────────────────────────────────────────────────

class Badge(models.Model):
    CATEGORY_CHOICES = [
        ('explorer',    'Explorer'),
        ('contributor', 'Contributor'),
        ('social',      'Social'),
        ('special',     'Special'),
    ]

    name            = models.CharField(max_length=100)
    description     = models.TextField()
    icon            = models.CharField(max_length=10, blank=True)
    image           = models.ImageField(
        upload_to=badge_image_upload_to, null=True, blank=True, max_length=300
    )
    criteria        = models.JSONField()
    category        = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default='explorer'
    )
    points_required = models.IntegerField(default=0)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    user      = models.ForeignKey(User, on_delete=models.CASCADE)
    badge     = models.ForeignKey(Badge, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'badge']
        ordering        = ['-earned_at']

    def __str__(self):
        return f"{self.user.username} earned {self.badge.name}"


# ─────────────────────────────────────────────────────────
# Challenges
# ─────────────────────────────────────────────────────────

class Challenge(models.Model):
    CHALLENGE_TYPES = [
        ('weekly',   'Weekly'),
        ('monthly',  'Monthly'),
        ('seasonal', 'Seasonal'),
    ]

    title          = models.CharField(max_length=200)
    description    = models.TextField()
    challenge_type = models.CharField(max_length=50, choices=CHALLENGE_TYPES)
    criteria       = models.JSONField()
    reward_points  = models.IntegerField(default=50)
    start_date     = models.DateTimeField()
    end_date       = models.DateTimeField()
    is_active      = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class UserChallengeCompletion(models.Model):
    """
    Records that a user completed a challenge and received the reward.
    Progress is computed live from CheckIn records — no join step required.
    """
    user          = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='challenge_completions'
    )
    challenge     = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name='completions'
    )
    completed_at  = models.DateTimeField(auto_now_add=True)
    points_awarded = models.IntegerField(default=0)

    class Meta:
        unique_together = ['user', 'challenge']  # reward fires exactly once
        ordering        = ['-completed_at']

    def __str__(self):
        return f"{self.user.username} completed '{self.challenge.title}'"


# ─────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('place_added',      'Place Added'),
        ('place_approved',   'Place Approved'),
        ('place_rejected',   'Place Rejected'),
        ('comment_reply',    'Comment Reply'),
        ('nearby_place',     'Nearby Place'),
        ('challenge',        'Challenge'),
        ('badge_earned',     'Badge Earned'),
        ('welcome',          'Welcome'),
        ('welcome_back',     'Welcome Back'),
        ('profile_complete', 'Profile Complete'),   # ← added
    ]

    user              = models.ForeignKey(User, on_delete=models.CASCADE)
    title             = models.CharField(max_length=100)
    message           = models.CharField(max_length=255)
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    is_read           = models.BooleanField(default=False)
    related_place     = models.ForeignKey(
        Place, on_delete=models.SET_NULL, null=True, blank=True
    )
    related_trail     = models.ForeignKey(
        Trail, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def get_icon(self):
        icons = {
            'place_added':      'fa-map-marker-alt',
            'place_approved':   'fa-check-circle',
            'place_rejected':   'fa-times-circle',
            'comment_reply':    'fa-reply',
            'nearby_place':     'fa-location-arrow',
            'challenge':        'fa-tasks',
            'badge_earned':     'fa-trophy',
            'welcome':          'fa-hand-wave',
            'welcome_back':     'fa-hand-wave',
            'profile_complete': 'fa-user-check',
        }
        return icons.get(self.notification_type, 'fa-bell')

    def get_icon_color(self):
        colors = {
            'place_approved':   'bg-green-100 text-green-600',
            'place_rejected':   'bg-red-100 text-red-600',
            'badge_earned':     'bg-yellow-100 text-yellow-600',
            'comment_reply':    'bg-blue-100 text-blue-600',
            'challenge':        'bg-purple-100 text-purple-600',
            'welcome':          'bg-green-100 text-green-600',
            'welcome_back':     'bg-green-100 text-green-600',
            'profile_complete': 'bg-teal-100 text-teal-600',
        }
        return colors.get(self.notification_type, 'bg-gray-100 text-gray-600')

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"


# ─────────────────────────────────────────────────────────
# Tours
# ─────────────────────────────────────────────────────────

class TourOffering(models.Model):
    """Reusable offering options (Breakfast, Tent, Guide, etc.)."""
    name = models.CharField(max_length=100)
    icon = models.CharField(
        max_length=50, blank=True,
        help_text="FontAwesome class e.g. 'fas fa-utensils'"
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class TourPackage(models.Model):
    # ── Core info ─────────────────────────────────────────
    name        = models.CharField(max_length=200)
    slug        = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    image       = models.ImageField(upload_to='tours/', blank=True, null=True)

    # ── Logistics ─────────────────────────────────────────
    duration_hours = models.DecimalField(
        max_digits=5, decimal_places=1,
        help_text="Duration in hours, e.g. 9.5"
    )
    price_lkr = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Price per person in LKR"
    )

    # ── Event date & time ─────────────────────────────────
    event_date = models.DateField(
        null=True, blank=True,
        help_text="Date the tour takes place (leave blank if not a fixed-date event)"
    )
    event_time = models.TimeField(
        null=True, blank=True,
        help_text="Start time on the event date (optional)"
    )

    # ── Route ─────────────────────────────────────────────
    starting_location = models.CharField(
        max_length=255, blank=True,
        help_text="Where the tour begins, e.g. 'Colombo Fort Railway Station'"
    )
    ending_location = models.CharField(
        max_length=255, blank=True,
        help_text="Where the tour ends (leave blank if same as start)"
    )

    # ── What to bring ─────────────────────────────────────
    what_to_bring = models.TextField(
        blank=True,
        help_text="One item per line, e.g. 'Sunscreen\\nWater bottle\\nComfortable shoes'"
    )

    # ── Relationships ─────────────────────────────────────
    trails = models.ManyToManyField(
        'Trail', related_name='tour_packages', blank=True,
        help_text="Select existing trails included in this tour"
    )
    offerings = models.ManyToManyField(
        TourOffering, related_name='tour_packages', blank=True,
        help_text="What is included in the tour"
    )

    # ── Booking ───────────────────────────────────────────
    contact_numbers = models.TextField(
        blank=True,
        help_text="One phone number per line"
    )

    # ── Meta ──────────────────────────────────────────────
    is_active  = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='tour_packages'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            n    = 1
            while TourPackage.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n   += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def contact_list(self):
        return [c.strip() for c in self.contact_numbers.splitlines() if c.strip()]

    @property
    def what_to_bring_list(self):
        return [i.strip() for i in self.what_to_bring.splitlines() if i.strip()]

    @property
    def duration_display(self):
        h     = self.duration_hours
        hours = int(h)
        mins  = int((h - hours) * 60)
        if mins:
            return f"{hours}h {mins}m"
        return f"{hours} hours"

    @property
    def price_display(self):
        return f"LKR {self.price_lkr:,.0f}"


class TourItineraryDay(models.Model):
    """A single day entry in a tour's itinerary."""
    tour        = models.ForeignKey(
        TourPackage, on_delete=models.CASCADE, related_name='itinerary_days'
    )
    day_number  = models.PositiveSmallIntegerField(help_text="1, 2, 3 …")
    title       = models.CharField(
        max_length=200, blank=True,
        help_text="Short title, e.g. 'Colombo to Kandy'"
    )
    description = models.TextField(blank=True, help_text="What happens on this day")
    distance_km = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True,
        help_text="Approximate distance covered (optional)"
    )
    highlights  = models.TextField(
        blank=True,
        help_text="Comma-separated highlight tags, e.g. 'Sunrise view,Temple visit,Local lunch'"
    )

    class Meta:
        ordering        = ['tour', 'day_number']
        unique_together = [['tour', 'day_number']]

    def __str__(self):
        return f"{self.tour.name} — Day {self.day_number}"

    @property
    def highlights_list(self):
        return [h.strip() for h in self.highlights.split(',') if h.strip()]

# class AudioGuide(models.Model):
#     place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='audio_guides')
#     title = models.CharField(max_length=200)
#     audio_file = models.FileField(upload_to='audio_guides/')
#     duration = models.DurationField(null=True, blank=True)
#     created_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     is_approved = models.BooleanField(default=False)
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     def __str__(self):
#         return f"Audio guide: {self.title} for {self.place.name}"

# class Report(models.Model):
#     STATUS_CHOICES = [
#         ('pending', 'Pending'),
#         ('resolved', 'Resolved'),
#     ]
    
#     reported_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     place = models.ForeignKey(Place, on_delete=models.CASCADE, null=True, blank=True)
#     comment = models.ForeignKey(Comment, on_delete=models.CASCADE, null=True, blank=True)
#     reason = models.CharField(max_length=100)
#     description = models.TextField(blank=True)
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
#     created_at = models.DateTimeField(auto_now_add=True)
    
#     class Meta:
#         ordering = ['-created_at']
    
#     def __str__(self):
#         target = self.place or self.comment
#         return f"Report by {self.reported_by.username} on {target}"

