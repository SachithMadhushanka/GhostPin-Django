from django import forms
from django.contrib.auth.models import User
from .models import (
    Place, Comment, PlaceImage, CheckIn, PlaceCollection, 
    AudioGuide, Report, UserProfile, Vote, ExpertArea
)


class PlaceForm(forms.ModelForm):
    class Meta:
        model = Place
        fields = [
            'name', 'description', 'legends_stories', 'latitude', 'longitude', 
            'image', 'category', 'difficulty','safety_rating', 
            'accessibility_info', 'best_time_to_visit'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Enter place name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 4,
                'placeholder': 'Describe this historical place...'
            }),
            'legends_stories': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 3,
                'placeholder': 'Share any legends or local stories about this place...'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'step': 'any',
                'placeholder': 'Latitude (e.g., 40.7128)'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'step': 'any',
                'placeholder': 'Longitude (e.g., -74.0060)'
            }),
            'image': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'accept': 'image/*'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
             }),
            # 'category_icon': forms.Select(attrs={
            #     'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
            #     'placeholder': '📍 (emoji icon for this place)'
            # }),
            'difficulty': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
            }),
            'safety_rating': forms.Select(attrs={ 
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
            }),
            'accessibility_info': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 2,
                'placeholder': 'Accessibility information (wheelchair access, parking, etc.)'
            }),
            'best_time_to_visit': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Best time to visit (e.g., Spring, Early morning, etc.)'
            })
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text', 'rating']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 3,
                'placeholder': 'Add your comment...'
            }),
            'rating': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
            }, choices=[(i, f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)])
        }


class PlaceImageForm(forms.ModelForm):
    class Meta:
        model = PlaceImage
        fields = ['image', 'is_challenge_photo', 'challenge_description']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'accept': 'image/*'
            }),
            'is_challenge_photo': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-green-600 shadow-sm focus:border-green-300 focus:ring focus:ring-green-200 focus:ring-opacity-50'
            }),
            'challenge_description': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Describe the photo challenge (if applicable)'
            })
        }


class CheckInForm(forms.ModelForm):
    class Meta:
        model = CheckIn
        fields = ['photo_proof', 'notes']
        widgets = {
            'photo_proof': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'accept': 'image/*'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 3,
                'placeholder': 'Share your experience at this place...'
            })
        }


class PlaceCollectionForm(forms.ModelForm):
    class Meta:
        model = PlaceCollection
        fields = [
            'name',
            'description',
            'is_public',
            'allow_comments',       
            'estimated_duration',
            'distance',             
            'difficulty',
            'category',             
            'cover_image',          
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Collection name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 4,
                'placeholder': 'Describe this collection or trail...'
            }),
            'is_public': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-green-600 shadow-sm focus:border-green-300 focus:ring focus:ring-green-200 focus:ring-opacity-50'
            }),
            'allow_comments': forms.CheckboxInput(attrs={     # ✅ NEW
                'class': 'rounded border-gray-300 text-green-600 shadow-sm focus:border-green-300 focus:ring focus:ring-green-200 focus:ring-opacity-50'
            }),
            'estimated_duration': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'e.g., 2:30:00 (2 hours 30 minutes)'
            }),
            'distance': forms.NumberInput(attrs={              # ✅ NEW
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Total distance in km'
            }),
            'difficulty': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
            }),
            'category': forms.Select(attrs={                  # ✅ NEW
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
            }),
            'cover_image': forms.ClearableFileInput(attrs={   # ✅ NEW
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
            }),
        }



class AudioGuideForm(forms.ModelForm):
    class Meta:
        model = AudioGuide
        fields = ['title', 'audio_file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Audio guide title'
            }),
            'audio_file': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'accept': 'audio/*'
            })
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'description']
        widgets = {
            'reason': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500'
            }, choices=[
                ('inappropriate', 'Inappropriate Content'),
                ('spam', 'Spam'),
                ('false_info', 'False Information'),
                ('harassment', 'Harassment'),
                ('other', 'Other')
            ]),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500',
                'rows': 3,
                'placeholder': 'Please provide details about why you are reporting this...'
            })
        }


class UserProfileForm(forms.ModelForm):
    expert_areas = forms.ModelMultipleChoiceField(
        queryset=ExpertArea.objects.all(),
        widget=forms.SelectMultiple(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
        }),
        required=False,
        label="Areas of Expertise"
    )

    class Meta:
        model = UserProfile
        fields = [
            'avatar', 'bio', 'location', 'website', 'expert_areas',
            'show_email', 'show_location', 'allow_messages',
            'email_notifications', 'push_notifications', 'weekly_digest'
        ]
        widgets = {
            'avatar': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'accept': 'image/*'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'rows': 4,
                'placeholder': 'Tell us about yourself...'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'Your city or region'
            }),
            'website': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500',
                'placeholder': 'https://yourwebsite.com'
            }),
            # 👇 Remove 'expert_areas' from widgets — it's already defined above
            'show_email': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'show_location': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'allow_messages': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'email_notifications': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'push_notifications': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'weekly_digest': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
        }

class SearchForm(forms.Form):
    query = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500',
            'placeholder': 'Search places...'
        })
    )
    category = forms.ChoiceField(
        choices=[('', 'All Categories')] + Place.CATEGORY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
        })
    )
    difficulty = forms.ChoiceField(
        choices=[('', 'All Difficulties')] + Place.DIFFICULTY_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500'
        })
    )


class VoteForm(forms.Form):
    vote_type = forms.ChoiceField(
        choices=Vote.VOTE_CHOICES,
        widget=forms.HiddenInput()
    )

