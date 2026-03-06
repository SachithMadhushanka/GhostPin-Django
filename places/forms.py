from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from .models import (
    Place,
    Category,
    Comment,
    PlaceImage,
    CheckIn,
    Trail,
    UserProfile,
    Vote,
    ExpertArea,
    Challenge,
    TourPackage,
    TourOffering,
    #   , AudioGuide, Report
)


class PlaceForm(forms.ModelForm):
    category = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.SelectMultiple(
            attrs={
                "class": "category-multi-select w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
            }
        ),
        required=True,
    )

    class Meta:
        model = Place
        fields = [
            "name",
            "description",
            "legends_stories",
            "latitude",
            "longitude",
            "image",
            "difficulty",
            "safety_rating",
            "category",
            "accessibility_info",
            "best_time_to_visit",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "placeholder": "Enter place name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "rows": 4,
                    "placeholder": "Describe this place...",
                }
            ),
            "legends_stories": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "rows": 3,
                    "placeholder": "Share any legends or local stories about this place...",
                }
            ),
            "latitude": forms.NumberInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "step": "any",
                    "placeholder": "Latitude (e.g., 40.7128)",
                }
            ),
            "longitude": forms.NumberInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "step": "any",
                    "placeholder": "Longitude (e.g., -74.0060)",
                }
            ),
            "image": forms.FileInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "accept": "image/*",
                }
            ),
            # 'category': forms.SelectMultiple(attrs={
            #     'class': 'category-multi-select w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
            # }),
            # 'category': forms.Select(attrs={
            #     'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
            #  }),
            # 'category_icon': forms.Select(attrs={
            #     'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
            #     'placeholder': '📍 (emoji icon for this place)'
            # }),
            "difficulty": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                }
            ),
            "safety_rating": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                }
            ),
            "accessibility_info": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "rows": 2,
                    "placeholder": "Accessibility information (wheelchair access, parking, etc.)",
                }
            ),
            "best_time_to_visit": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "placeholder": "Best time to visit (e.g., Spring, Early morning, etc.)",
                }
            ),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["text", "rating"]
        widgets = {
            "text": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "rows": 3,
                    "placeholder": "Add your comment...",
                }
            ),
            "rating": forms.Select(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
                },
                choices=[(i, f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)],
            ),
        }


class PlaceImageForm(forms.ModelForm):
    class Meta:
        model = PlaceImage
        fields = ["image", "is_challenge_photo", "challenge_description"]
        widgets = {
            "image": forms.FileInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "accept": "image/*",
                }
            ),
            "is_challenge_photo": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-gray-300 text-green-600 shadow-sm focus:border-green-300 focus:ring focus:ring-green-200 focus:ring-opacity-50"
                }
            ),
            "challenge_description": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "placeholder": "Describe the photo challenge (if applicable)",
                }
            ),
        }


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500",
                "placeholder": "your.email@example.com",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class CheckInForm(forms.ModelForm):
    class Meta:
        model = CheckIn
        fields = ["photo_proof", "notes"]
        widgets = {
            "photo_proof": forms.FileInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "accept": "image/*",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "rows": 3,
                    "placeholder": "Share your experience at this place...",
                }
            ),
        }


class TrailForm(forms.ModelForm):
    """
    Full TrailForm including all fields referenced by create_trail_v5 / edit_trail.

    Fields added vs a minimal form:
        cover_image    — ImageField: rendered as the drag-drop widget in the template
        distance       — FloatField: auto-filled by OSRM JS, or entered manually
        allow_comments — BooleanField: "Allow comments" checkbox in Additional Options
        category       — M2M: TomSelect widget in the template

    enctype="multipart/form-data" must be set on the <form> tag (already is in create_trail_v5).
    """

    class Meta:
        model = Trail
        fields = [
            "name",
            "description",
            "difficulty",
            "estimated_duration",
            "distance",
            "category",
            "cover_image",
            "is_public",
            "allow_comments",
            "required_points",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "w-full border border-gray-300 rounded-lg px-3 py-2 "
                    "focus:ring-2 focus:ring-purple-500 focus:border-transparent",
                    "placeholder": "Give your trail a memorable name…",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "w-full border border-gray-300 rounded-lg px-3 py-2 "
                    "focus:ring-2 focus:ring-purple-500 focus:border-transparent",
                    "rows": 4,
                    "placeholder": "Describe this trail — what makes it special?",
                }
            ),
            "difficulty": forms.Select(
                attrs={
                    "class": "w-full border border-gray-300 rounded-lg px-3 py-2 "
                    "focus:ring-2 focus:ring-purple-500",
                    "id": "id_difficulty",  # required by JS recalcDistance listener
                }
            ),
            "estimated_duration": forms.TextInput(
                attrs={
                    "class": "w-full border border-gray-300 rounded-lg px-3 py-2 "
                    "focus:ring-2 focus:ring-blue-500",
                    "placeholder": "HH:MM:SS",
                    "id": "id_estimated_duration",  # required by JS auto-fill
                }
            ),
            "distance": forms.NumberInput(
                attrs={
                    "class": "w-full border border-gray-300 rounded-lg px-3 py-2 "
                    "focus:ring-2 focus:ring-purple-500",
                    "step": "0.01",
                    "placeholder": "km",
                    "id": "id_distance",  # required by JS auto-fill
                }
            ),
            "category": forms.SelectMultiple(
                attrs={
                    "id": "id_category",  # required by TomSelect init
                }
            ),
            # cover_image rendered manually in template as drag-drop widget;
            # the real <input type="file"> is hidden but must be present for upload.
            "cover_image": forms.ClearableFileInput(
                attrs={
                    "accept": "image/*",
                }
            ),
            "is_public": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-purple-600 focus:ring-purple-500 border-gray-300 rounded",
                }
            ),
            "allow_comments": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-purple-600 focus:ring-purple-500 border-gray-300 rounded",
                }
            ),
            "required_points": forms.NumberInput(
                attrs={
                    "class": "w-full border border-gray-300 rounded-lg px-3 py-2 "
                    "focus:ring-2 focus:ring-purple-500",
                    "min": "0",
                    "placeholder": "0 = free for everyone",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make non-essential fields optional at the form level
        # (model already has null=True / blank=True for these)
        self.fields["distance"].required = False
        self.fields["estimated_duration"].required = False
        self.fields["cover_image"].required = False
        self.fields["category"].required = False
        self.fields["required_points"].required = False


class UserProfileForm(forms.ModelForm):
    expert_areas = forms.ModelMultipleChoiceField(
        queryset=ExpertArea.objects.all(),
        widget=forms.SelectMultiple(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
            }
        ),
        required=False,
        label="Areas of Expertise",
    )

    class Meta:
        model = UserProfile
        fields = [
            "avatar",
            "bio",
            "location",
            "website",
            "expert_areas",
            "show_email",
            "show_location",
            "allow_messages",
            "email_notifications",
            "push_notifications",
            "weekly_digest",
        ]
        widgets = {
            "avatar": forms.FileInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "accept": "image/*",
                }
            ),
            "bio": forms.Textarea(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "rows": 4,
                    "placeholder": "Tell us about yourself...",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "placeholder": "Your city or region",
                }
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500",
                    "placeholder": "https://yourwebsite.com",
                }
            ),
            # 👇 Remove 'expert_areas' from widgets — it's already defined above
            "show_email": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                }
            ),
            "show_location": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                }
            ),
            "allow_messages": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                }
            ),
            "email_notifications": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                }
            ),
            "push_notifications": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                }
            ),
            "weekly_digest": forms.CheckboxInput(
                attrs={
                    "class": "h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                }
            ),
        }


class SearchForm(forms.Form):
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500",
                "placeholder": "Search places...",
            }
        ),
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
            }
        ),
    )
    difficulty = forms.ChoiceField(
        choices=[("", "All Difficulties")] + Place.DIFFICULTY_CHOICES,
        required=False,
        widget=forms.Select(
            attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500"
            }
        ),
    )


class VoteForm(forms.Form):
    vote_type = forms.ChoiceField(choices=Vote.VOTE_CHOICES, widget=forms.HiddenInput())


class ChallengeForm(forms.ModelForm):
    start_date = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-input"}
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    end_date = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-input"}
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    # Human-friendly criteria fields (converted to JSON on save)
    criteria_visit_count = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=5,
        required=False,
        label="Places to Visit",
        widget=forms.NumberInput(
            attrs={"class": "form-input", "placeholder": "e.g. 5"}
        ),
    )
    criteria_require_photo = forms.BooleanField(
        required=False,
        label="Require Photo Proof",
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )
    criteria_require_review = forms.BooleanField(
        required=False,
        label="Require Written Review",
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
    )
    criteria_category = forms.CharField(
        max_length=100,
        required=False,
        label="Restrict to Category (optional)",
        widget=forms.TextInput(
            attrs={"class": "form-input", "placeholder": "e.g. waterfall"}
        ),
    )

    class Meta:
        model = Challenge
        fields = [
            "title",
            "description",
            "challenge_type",
            "reward_points",
            "start_date",
            "end_date",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Challenge title"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 4,
                    "placeholder": "Describe the challenge…",
                }
            ),
            "challenge_type": forms.Select(attrs={"class": "form-input"}),
            "reward_points": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end <= start:
            raise forms.ValidationError("End date must be after start date.")
        return cleaned

    def save(self, commit=True):
        challenge = super().save(commit=False)
        # Build the JSON criteria dict from the helper fields
        challenge.criteria = {
            "visit_count": self.cleaned_data.get("criteria_visit_count") or 1,
            "require_photo": self.cleaned_data.get("criteria_require_photo", False),
            "require_review": self.cleaned_data.get("criteria_require_review", False),
            "category": self.cleaned_data.get("criteria_category", ""),
        }
        if commit:
            challenge.save()
        return challenge

    def _load_criteria_initial(self):
        """Call this when editing an existing instance to populate criteria fields."""
        if (
            self.instance
            and self.instance.pk
            and isinstance(self.instance.criteria, dict)
        ):
            c = self.instance.criteria
            self.fields["criteria_visit_count"].initial = c.get("visit_count", 5)
            self.fields["criteria_require_photo"].initial = c.get(
                "require_photo", False
            )
            self.fields["criteria_require_review"].initial = c.get(
                "require_review", False
            )
            self.fields["criteria_category"].initial = c.get("category", "")


class TourPackageForm(forms.ModelForm):
    """
    Staff-only form for creating / editing tour packages.
    Trails and offerings use checkbox selects rendered as
    pill-style toggles in the template.
    """

    trails = forms.ModelMultipleChoiceField(
        queryset=Trail.objects.filter(is_public=True).order_by('name'),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Select all trails that are part of this tour."
    )

    offerings = forms.ModelMultipleChoiceField(
        queryset=TourOffering.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="What is included in the tour package?"
    )

    class Meta:
        model  = TourPackage
        fields = [
            'name', 'description', 'image',
            'duration_hours', 'price_lkr',
            'trails', 'offerings',
            'contact_numbers', 'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Horton Plains Adventure Tour',
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe the tour experience, highlights, and what to expect…',
            }),
            'duration_hours': forms.NumberInput(attrs={
                'step': '0.5',
                'min': '0.5',
                'placeholder': '9',
            }),
            'price_lkr': forms.NumberInput(attrs={
                'step': '100',
                'min': '0',
                'placeholder': '5900',
            }),
            'contact_numbers': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': '+94 77 123 4567\n+94 71 987 6543',
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Tour name is required.")
        return name

    def clean_price_lkr(self):
        price = self.cleaned_data.get('price_lkr')
        if price is not None and price < 0:
            raise forms.ValidationError("Price cannot be negative.")
        return price

    def clean_duration_hours(self):
        dur = self.cleaned_data.get('duration_hours')
        if dur is not None and dur <= 0:
            raise forms.ValidationError("Duration must be greater than 0.")
        return dur


# class AudioGuideForm(forms.ModelForm):
#     class Meta:
#         model = AudioGuide
#         fields = ['title', 'audio_file']
#         widgets = {
#             'title': forms.TextInput(attrs={
#                 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
#                 'placeholder': 'Audio guide title'
#             }),
#             'audio_file': forms.FileInput(attrs={
#                 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
#                 'accept': 'audio/*'
#             })
#         }


# class ReportForm(forms.ModelForm):
#     class Meta:
#         model = Report
#         fields = ['reason', 'description']
#         widgets = {
#             'reason': forms.Select(attrs={
#                 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500'
#             }, choices=[
#                 ('inappropriate', 'Inappropriate Content'),
#                 ('spam', 'Spam'),
#                 ('false_info', 'False Information'),
#                 ('harassment', 'Harassment'),
#                 ('other', 'Other')
#             ]),
#             'description': forms.Textarea(attrs={
#                 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500',
#                 'rows': 3,
#                 'placeholder': 'Please provide details about why you are reporting this...'
#             })
#         }
