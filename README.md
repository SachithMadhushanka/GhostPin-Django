# Expearls - Advanced Historical Places Explorer

A comprehensive Django Progressive Web App (PWA) for discovering, exploring, and sharing historical places with advanced gamification, social features, and community-driven content.

## 🌟 Features

### Core Features
- **Place Discovery**: Browse and search historical places with detailed information
- **Interactive Maps**: Leaflet.js integration with custom markers and route planning
- **User Authentication**: Complete registration, login, and profile management
- **Content Management**: Add, edit, and moderate historical places
- **Progressive Web App**: Installable, offline-capable, with push notifications

### Advanced Features
- **Gamification System**: Points, levels, badges, and leaderboards
- **Check-in System**: Location verification with photo proof
- **Collections & Routes**: Curated trails connecting multiple places
- **Challenge System**: Weekly, monthly, and seasonal challenges
- **Social Features**: Comments, ratings, favorites, and user profiles
- **Expert System**: Trusted users and local expert designations
- **Analytics Dashboard**: Comprehensive admin analytics
- **Notification System**: Real-time notifications for user activities

### Technical Features
- **Responsive Design**: Mobile-first design with Tailwind CSS
- **PWA Capabilities**: Service worker, offline caching, installable
- **RESTful API**: JSON endpoints for mobile app integration
- **Admin Interface**: Enhanced Django admin with custom views
- **Security**: CSRF protection, user permissions, content moderationipt
- **Maps**: Leaflet.js with OpenStreetMap
- **PWA**: Custom manifest.json and service-worker.js
- **Authentication**: Django Auth
- **Media Storage**: Local (media/ folder)

## Installation & Setup

### Prerequisites

- Python 3.8+
- pip

### Local Development

1. **Clone or extract the project**
   ```bash
   cd ghostpin
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Create a superuser** (for admin access)
   ```bash
   python manage.py createsuperuser
   ```

5. **Collect static files** (for production)
   ```bash
   python manage.py collectstatic
   ```

6. **Run the development server**
   ```bash
   python manage.py runserver
   ```

7. **Access the application**
   - Main app: http://127.0.0.1:8000/
   - Admin panel: http://127.0.0.1:8000/admin/
   - Review places: http://127.0.0.1:8000/admin/review/

## Project Structure

```
ghostpin/
├── ghostpin/                 # Main project directory
│   ├── __init__.py
│   ├── settings.py          # Django settings
│   ├── urls.py              # Main URL configuration
│   └── wsgi.py              # WSGI configuration
├── places/                   # Main app
│   ├── models.py            # Place and Comment models
│   ├── views.py             # All views including PWA endpoints
│   ├── forms.py             # Django forms
│   ├── admin.py             # Admin configuration
│   └── urls.py              # App URL patterns
├── templates/                # HTML templates
│   ├── base.html            # Base template with PWA setup
│   ├── home.html            # Homepage with places grid
│   ├── place_detail.html    # Place details with map
│   ├── add_place.html       # Add new place form
│   ├── review_places.html   # Admin review interface
│   └── registration/
│       └── login.html       # Login page
├── static/                   # Static files
│   ├── icons/               # PWA icons
│   ├── manifest.json        # PWA manifest (served via view)
│   └── service-worker.js    # Service worker (served via view)
├── media/                    # User uploads
│   └── places/              # Place images
├── requirements.txt          # Python dependencies
└── README.md                # This file
```

## Models

### Place Model
- `name`: CharField(max_length=100)
- `description`: TextField
- `latitude`: FloatField
- `longitude`: FloatField
- `image`: ImageField (optional)
- `created_by`: ForeignKey(User)
- `status`: CharField (pending/approved/rejected)
- `created_at`: DateTimeField

### Comment Model
- `user`: ForeignKey(User)
- `place`: ForeignKey(Place)
- `text`: TextField
- `created_at`: DateTimeField

## URL Patterns

- `/` - Homepage (list approved places)
- `/place/<id>/` - Place detail page
- `/place/add/` - Add new place form
- `/admin/review/` - Review pending places (staff only)
- `/accounts/login/` - Login page
- `/accounts/logout/` - Logout
- `/manifest.json` - PWA manifest
- `/service-worker.js` - Service worker

## PWA Features

### Manifest.json
- App name: "Expearls - Explore Historical Places"
- Theme color: #4CAF50 (green)
- Display mode: standalone
- Custom icons (192x192, 512x512)
- Shortcuts for quick actions

### Service Worker
- Caches static assets for offline use
- Serves cached content when offline
- Background sync support
- Push notification ready

### Installation
Users can install the app on their devices:
- **Mobile**: "Add to Home Screen" prompt
- **Desktop**: Install button in browser

## Admin Features

### Django Admin
- Full CRUD operations for places and comments
- Bulk approve/reject actions
- Search and filtering

### Custom Review Interface
- Dedicated review page for staff users
- AJAX-powered approve/reject buttons
- Map previews for each place
- Real-time status updates

## Usage

### For Regular Users
1. Browse approved historical places on the homepage
2. Click on places to view details, maps, and comments
3. Login to add comments and submit new places
4. Install the PWA for offline access

### For Admins/Staff
1. Login with staff account
2. Access "Review Places" from the navigation
3. Review submitted places with map previews
4. Approve or reject places with one click
5. Use Django admin for advanced management

## Deployment

### Development
```bash
python manage.py runserver 0.0.0.0:8000
```

### Production Options

#### Option 1: Railway/Render/Fly.io
1. Update `ALLOWED_HOSTS` in settings.py
2. Configure PostgreSQL database
3. Set up static file serving
4. Deploy with platform-specific instructions

#### Option 2: Traditional VPS
1. Install nginx and gunicorn
2. Configure database (PostgreSQL recommended)
3. Set up SSL certificate (required for PWA)
4. Configure static file serving

### Environment Variables (Production)
```bash
DEBUG=False
SECRET_KEY=your-secret-key
DATABASE_URL=your-database-url
ALLOWED_HOSTS=your-domain.com
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source and available under the MIT License.

## Support

For issues and questions:
1. Check the Django documentation
2. Review the code comments
3. Test in development environment first
4. Check browser console for PWA issues

---

Built with ❤️ using Django and modern web technologies.

