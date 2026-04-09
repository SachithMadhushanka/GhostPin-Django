"""
URL configuration for ghostpin project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from places import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('places.urls', 'places'), namespace='places')),
    path('api/', include('places.api.urls')),

    # Authentication
    path('accounts/login/', auth_views.LoginView.as_view(
        template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),

     
    # ── Password Reset Flow ──────────────────────────────────────────────────
 
    # Step 1 — User enters their email
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset.html',
            email_template_name='registration/password_reset_email.txt',
            subject_template_name='registration/password_reset_subject.txt',
            success_url='/password-reset/sent/',
        ),
        name='password_reset',
    ),
 
    # Step 2 — "Check your email" confirmation page
    path(
        'password-reset/sent/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
 
    # Step 3 — User clicks link in email → enters new password
    path(
        'password-reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url='/password-reset/complete/',
        ),
        name='password_reset_confirm',
    ),
 
    # Step 4 — Success page after password is changed
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),

    # Password change (add these since you removed auth.urls)
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(
        template_name='registration/password_change_form.html'), name='password_change'),
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='registration/password_change_done.html'), name='password_change_done'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
