"""
Unified import command

Usage:
    python manage.py import_all_data
    python manage.py import_all_data --file data.xlsx
    python manage.py import_all_data --images data_images
    python manage.py import_all_data --badge-images badge_images
    python manage.py import_all_data --dry-run
    python manage.py import_all_data --update
    python manage.py import_all_data --user admin
"""

import os
import json
import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.core.files import File
from django.contrib.auth.models import User

from places.models import (
    Place, Category,
    Badge, Challenge,
    Trail, TrailPlace,
    ExpertArea,
)

# ---------------------------
# CONFIG
# ---------------------------
COL = {
    'name':           'Name',
    'description':    'Description',
    'legends':        'Legends / Stories',
    'latitude':       'Latitude',
    'longitude':      'Longitude',
    'categories':     'Categories\n(slugs, comma-sep)',
    'difficulty':     'Difficulty',
    'accessibility':  'Accessibility Info',
    'best_time':      'Best Time to Visit',
    'safety':         'Safety Rating\n(1-5)',
    'status':         'Status',
    'image_filename': 'Image Filename\n(save as)',
}

# Sheet names as they appear in the xlsx (case-sensitive)
SHEET_CATEGORIES   = 'All Categories'
SHEET_PLACES       = 'Places (Import Ready)'
SHEET_BADGES       = 'Badges'
SHEET_CHALLENGES   = 'Challenges'
SHEET_TRAILS       = 'Trails'
SHEET_TRAIL_PLACES = 'Trail_Places'
SHEET_EXPERT_AREAS = 'Expert_Areas'

VALID_DIFFICULTIES = {'easy', 'moderate', 'challenging'}
VALID_STATUSES     = {'approved', 'pending', 'rejected'}
VALID_BADGE_CATS   = {'explorer', 'contributor', 'social', 'special'}


# ============================================================
class Command(BaseCommand):
    help = "Import EVERYTHING (places, categories, badges, challenges, trails, expert areas)"

    def add_arguments(self, parser):
        parser.add_argument('--file',         default='data.xlsx')
        parser.add_argument('--images',       default='data_images')
        parser.add_argument('--badge-images', default='badge_images')
        parser.add_argument('--user',         default=None)
        parser.add_argument('--dry-run',      action='store_true')
        parser.add_argument('--update',       action='store_true')

    # ============================================================
    def handle(self, *args, **options):
        file_path    = options['file']
        images_dir   = options['images']
        badge_images = options['badge_images']
        dry_run      = options['dry_run']
        update       = options['update']

        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        xls  = pd.ExcelFile(file_path)
        user = self._get_user(options['user'])

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be saved.\n"))

        # ORDER MATTERS: categories before places, trails before trail_places
        self.import_categories(xls, dry_run)
        self.import_expert_areas(xls, dry_run)
        self.import_places(xls, user, images_dir, update, dry_run)
        self.import_badges(xls, badge_images, dry_run)
        self.import_challenges(xls, dry_run)
        self.import_trails(xls, dry_run)
        self.import_trail_places(xls, dry_run)

        self.stdout.write(self.style.SUCCESS("\n✅ ALL DATA IMPORTED"))

    # ============================================================
    # USER
    # ============================================================

    def _get_user(self, username):
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"User '{username}' not found.")
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            raise CommandError(
                "No superuser found. Create one first or pass --user <username>."
            )
        return user

    # ============================================================
    # CATEGORIES
    # ============================================================

    def import_categories(self, xls, dry_run):
        if SHEET_CATEGORIES not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(
                f"Sheet '{SHEET_CATEGORIES}' not found — skipping categories."
            ))
            return

        df = pd.read_excel(xls, SHEET_CATEGORIES)
        created_count = 0

        for i, row in df.iterrows():
            slug = self.clean(row.iloc[0])
            name = self.clean(row.iloc[1])
            if not slug or not name:
                continue

            slug = slugify(slug)
            if dry_run:
                self.stdout.write(f"  [CAT] {slug} → {name}")
                continue

            try:
                _, created = Category.objects.get_or_create(
                    slug=slug, defaults={'name': name}
                )
                if created:
                    created_count += 1
            except Exception as e:
                self.stderr.write(f"  [CAT] Row {i} error: {e}")

        if not dry_run:
            self.stdout.write(f"  Categories: {created_count} created.")

    # ============================================================
    # EXPERT AREAS
    # ============================================================

    def import_expert_areas(self, xls, dry_run):
        if SHEET_EXPERT_AREAS not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(
                f"Sheet '{SHEET_EXPERT_AREAS}' not found — skipping expert areas."
            ))
            return

        df = pd.read_excel(xls, SHEET_EXPERT_AREAS)
        upserted_count = 0

        for i, row in df.iterrows():
            name = self.clean(row.get('name'))
            if not name:
                self.stderr.write(f"  [EXPERT_AREA] Row {i}: missing name — skipped.")
                continue

            if dry_run:
                self.stdout.write(f"  [EXPERT_AREA] {name}")
                continue

            try:
                ExpertArea.objects.update_or_create(
                    name=name,
                    defaults={
                        'description': self.clean(row.get('description'), ''),
                    }
                )
                upserted_count += 1
            except Exception as e:
                self.stderr.write(f"  [EXPERT_AREA] Row {i} '{name}': error — {e}")

        if not dry_run:
            self.stdout.write(f"  Expert Areas: {upserted_count} upserted.")

    # ============================================================
    # PLACES
    # ============================================================

    def import_places(self, xls, user, images_dir, update, dry_run):
        if SHEET_PLACES not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(
                f"Sheet '{SHEET_PLACES}' not found — skipping places."
            ))
            return

        df = pd.read_excel(xls, SHEET_PLACES)
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for i, row in df.iterrows():
            name = self.clean(row.get(COL['name']))
            if not name:
                self.stderr.write(f"  [PLACE] Row {i}: missing name — skipped.")
                skipped_count += 1
                continue

            try:
                # ── Validate difficulty ──────────────────────────────────
                difficulty = self.clean(row.get(COL['difficulty']), 'easy').lower()
                if difficulty not in VALID_DIFFICULTIES:
                    self.stderr.write(
                        f"  [PLACE] Row {i} '{name}': invalid difficulty "
                        f"'{difficulty}' — defaulting to 'easy'."
                    )
                    difficulty = 'easy'

                # ── Validate status ──────────────────────────────────────
                status = self.clean(row.get(COL['status']), 'pending').lower()
                if status not in VALID_STATUSES:
                    self.stderr.write(
                        f"  [PLACE] Row {i} '{name}': invalid status "
                        f"'{status}' — defaulting to 'pending'."
                    )
                    status = 'pending'

                # ── Validate safety rating ───────────────────────────────
                safety_rating = 3
                safety_raw = row.get(COL['safety'])
                if not pd.isna(safety_raw):
                    try:
                        safety_val = int(float(safety_raw))
                        if 1 <= safety_val <= 5:
                            safety_rating = safety_val
                        else:
                            self.stderr.write(
                                f"  [PLACE] Row {i} '{name}': safety rating "
                                f"{safety_val} out of range — defaulting to 3."
                            )
                    except (ValueError, TypeError):
                        pass

                if dry_run:
                    self.stdout.write(
                        f"  [PLACE] {name} | {status} | {difficulty} | "
                        f"safety={safety_rating}"
                    )
                    continue

                place, created = Place.objects.get_or_create(
                    name=name,
                    defaults={'created_by': user}
                )

                if not created and not update:
                    skipped_count += 1
                    continue

                # ── Core fields ──────────────────────────────────────────
                place.description        = self.clean(row.get(COL['description']), '')
                place.legends_stories    = self.clean(row.get(COL['legends']), '')
                place.latitude           = float(row.get(COL['latitude'], 0) or 0)
                place.longitude          = float(row.get(COL['longitude'], 0) or 0)
                place.difficulty         = difficulty
                place.accessibility_info = self.clean(row.get(COL['accessibility']), '')
                place.best_time_to_visit = self.clean(row.get(COL['best_time']), '')
                place.safety_rating      = safety_rating
                place.status             = status
                place.created_by         = user
                place.save()

                # ── Categories ───────────────────────────────────────────
                place.category.clear()
                for slug in self.parse_slugs(row.get(COL['categories'])):
                    try:
                        place.category.add(Category.objects.get(slug=slug))
                    except Category.DoesNotExist:
                        self.stderr.write(
                            f"  [PLACE] '{name}': category slug '{slug}' "
                            f"not found — skipped."
                        )

                # ── Image ────────────────────────────────────────────────
                img = self.clean(row.get(COL['image_filename']))
                if img:
                    path = os.path.join(images_dir, img)
                    if os.path.exists(path):
                        with open(path, 'rb') as f:
                            place.image.save(img, File(f), save=True)
                    else:
                        self.stderr.write(
                            f"  [PLACE] '{name}': image file '{path}' "
                            f"not found — skipped."
                        )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                self.stderr.write(f"  [PLACE] Row {i} '{name}': unexpected error — {e}")
                skipped_count += 1
                continue

        if not dry_run:
            self.stdout.write(
                f"  Places: {created_count} created, "
                f"{updated_count} updated, {skipped_count} skipped."
            )

    # ============================================================
    # BADGES
    # ============================================================

    def import_badges(self, xls, images_dir, dry_run):
        if SHEET_BADGES not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(
                f"Sheet '{SHEET_BADGES}' not found — skipping badges."
            ))
            return

        df = pd.read_excel(xls, SHEET_BADGES)
        upserted_count = 0

        for i, row in df.iterrows():
            name = self.clean(row.get('name'))
            if not name:
                self.stderr.write(f"  [BADGE] Row {i}: missing name — skipped.")
                continue

            try:
                criteria = self.parse_json(
                    row.get('criteria'), field='criteria', row=i, label=name
                )
                if criteria is None:
                    continue

                category = self.clean(row.get('category'), 'explorer').lower()
                if category not in VALID_BADGE_CATS:
                    self.stderr.write(
                        f"  [BADGE] '{name}': invalid category '{category}' "
                        f"— defaulting to 'explorer'."
                    )
                    category = 'explorer'

                points_required = 0
                pts_raw = row.get('points_required')
                if not pd.isna(pts_raw):
                    try:
                        points_required = int(float(pts_raw))
                    except (ValueError, TypeError):
                        pass

                is_active = bool(row.get('is_active', True))

                if dry_run:
                    self.stdout.write(
                        f"  [BADGE] {name} | cat={category} | "
                        f"pts={points_required} | active={is_active}"
                    )
                    continue

                badge, _ = Badge.objects.update_or_create(
                    name=name,
                    defaults={
                        'description':     self.clean(row.get('description'), ''),
                        'icon':            self.clean(row.get('icon'), ''),
                        'criteria':        criteria,
                        'category':        category,
                        'points_required': points_required,
                        'is_active':       is_active,
                    }
                )

                # ── Badge image ──────────────────────────────────────────
                img_raw = self.clean(row.get('image'))
                if img_raw and not badge.image:
                    img_filename = img_raw if '.' in img_raw else f"{img_raw}.jpg"
                    path = os.path.join(images_dir, img_filename)
                    if os.path.exists(path):
                        with open(path, 'rb') as f:
                            badge.image.save(img_filename, File(f), save=True)
                    else:
                        self.stderr.write(
                            f"  [BADGE] '{name}': image file '{path}' "
                            f"not found — skipped."
                        )

                upserted_count += 1

            except Exception as e:
                self.stderr.write(f"  [BADGE] Row {i} '{name}': unexpected error — {e}")
                continue

        if not dry_run:
            self.stdout.write(f"  Badges: {upserted_count} upserted.")

    # ============================================================
    # CHALLENGES
    # ============================================================

    def import_challenges(self, xls, dry_run):
        if SHEET_CHALLENGES not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(
                f"Sheet '{SHEET_CHALLENGES}' not found — skipping challenges."
            ))
            return

        df = pd.read_excel(xls, SHEET_CHALLENGES)
        upserted_count = 0

        for i, row in df.iterrows():
            title = self.clean(row.get('title'))
            if not title:
                self.stderr.write(f"  [CHALLENGE] Row {i}: missing title — skipped.")
                continue

            try:
                criteria = self.parse_json(
                    row.get('criteria'), field='criteria', row=i, label=title
                )
                if criteria is None:
                    continue

                start_date = parse_datetime(str(row.get('start_date', '')))
                end_date   = parse_datetime(str(row.get('end_date', '')))

                if not start_date or not end_date:
                    self.stderr.write(
                        f"  [CHALLENGE] '{title}': invalid start/end date — skipped."
                    )
                    continue

                if timezone.is_naive(start_date):
                    start_date = timezone.make_aware(start_date)
                if timezone.is_naive(end_date):
                    end_date = timezone.make_aware(end_date)

                reward_points = 50
                rp_raw = row.get('reward_points')
                if not pd.isna(rp_raw):
                    try:
                        reward_points = int(float(rp_raw))
                    except (ValueError, TypeError):
                        pass

                is_active = bool(row.get('is_active', True))

                if dry_run:
                    self.stdout.write(
                        f"  [CHALLENGE] {title} | type={row.get('challenge_type')} | "
                        f"pts={reward_points} | active={is_active}"
                    )
                    continue

                Challenge.objects.update_or_create(
                    title=title,
                    defaults={
                        'description':    self.clean(row.get('description'), ''),
                        'challenge_type': self.clean(row.get('challenge_type'), ''),
                        'criteria':       criteria,
                        'reward_points':  reward_points,
                        'start_date':     start_date,
                        'end_date':       end_date,
                        'is_active':      is_active,
                    }
                )
                upserted_count += 1

            except Exception as e:
                self.stderr.write(
                    f"  [CHALLENGE] Row {i} '{title}': unexpected error — {e}"
                )
                continue

        if not dry_run:
            self.stdout.write(f"  Challenges: {upserted_count} upserted.")

    # ============================================================
    # TRAILS
    # ============================================================

    def import_trails(self, xls, dry_run):
        if SHEET_TRAILS not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(
                f"Sheet '{SHEET_TRAILS}' not found — skipping trails."
            ))
            return

        df = pd.read_excel(xls, SHEET_TRAILS)
        upserted_count = 0

        for i, row in df.iterrows():
            name = self.clean(row.get('name'))
            if not name:
                continue

            try:
                created_by_username = self.clean(row.get('created_by'))
                try:
                    trail_user = User.objects.get(username=created_by_username)
                except User.DoesNotExist:
                    self.stderr.write(
                        f"  [TRAIL] '{name}': user '{created_by_username}' "
                        f"not found — skipped."
                    )
                    continue

                difficulty = self.clean(row.get('difficulty'), 'easy').lower()
                if difficulty not in VALID_DIFFICULTIES:
                    self.stderr.write(
                        f"  [TRAIL] '{name}': invalid difficulty '{difficulty}' "
                        f"— defaulting to 'easy'."
                    )
                    difficulty = 'easy'

                is_public = True
                ip_raw = row.get('is_public')
                if not pd.isna(ip_raw):
                    try:
                        is_public = bool(float(ip_raw))
                    except (ValueError, TypeError):
                        pass

                required_points = 0
                rp_raw = row.get('required_points')
                if not pd.isna(rp_raw):
                    try:
                        required_points = int(float(rp_raw))
                    except (ValueError, TypeError):
                        pass

                if dry_run:
                    self.stdout.write(
                        f"  [TRAIL] {name} | by={created_by_username} | "
                        f"{difficulty} | public={is_public} | "
                        f"required_pts={required_points}"
                    )
                    continue

                Trail.objects.update_or_create(
                    name=name,
                    defaults={
                        'description':     self.clean(row.get('description'), ''),
                        'created_by':      trail_user,
                        'difficulty':      difficulty,
                        'is_public':       is_public,
                        'required_points': required_points,
                    }
                )
                upserted_count += 1

            except Exception as e:
                self.stderr.write(
                    f"  [TRAIL] Row {i} '{name}': unexpected error — {e}"
                )
                continue

        if not dry_run:
            self.stdout.write(f"  Trails: {upserted_count} upserted.")

    # ============================================================
    # TRAIL PLACES
    # ============================================================

    def import_trail_places(self, xls, dry_run):
        if SHEET_TRAIL_PLACES not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(
                f"Sheet '{SHEET_TRAIL_PLACES}' not found — skipping trail places."
            ))
            return

        df = pd.read_excel(xls, SHEET_TRAIL_PLACES)
        upserted_count = 0

        for i, row in df.iterrows():
            trail_name = self.clean(row.get('trail'))
            place_name = self.clean(row.get('place'))
            if not trail_name or not place_name:
                self.stderr.write(
                    f"  [TRAIL_PLACE] Row {i}: missing trail or place name — skipped."
                )
                continue

            try:
                try:
                    trail = Trail.objects.get(name=trail_name)
                except Trail.DoesNotExist:
                    self.stderr.write(
                        f"  [TRAIL_PLACE] Row {i}: trail '{trail_name}' "
                        f"not found — skipped."
                    )
                    continue

                try:
                    place = Place.objects.get(name=place_name)
                except Place.DoesNotExist:
                    self.stderr.write(
                        f"  [TRAIL_PLACE] Row {i}: place '{place_name}' not found "
                        f"— skipped. (Hint: name must match Places sheet exactly.)"
                    )
                    continue

                notes = self.clean(row.get('notes'), '')

                distance_from_previous = None
                dfp_raw = row.get('distance_from_previous')
                if not pd.isna(dfp_raw):
                    try:
                        distance_from_previous = float(dfp_raw)
                    except (ValueError, TypeError):
                        pass

                order = int(row.get('order', 0))

                if dry_run:
                    self.stdout.write(
                        f"  [TRAIL_PLACE] {trail_name} → #{order} {place_name}"
                    )
                    continue

                TrailPlace.objects.update_or_create(
                    trail=trail,
                    place=place,
                    defaults={
                        'order':                  order,
                        'notes':                  notes,
                        'distance_from_previous': distance_from_previous,
                    }
                )
                upserted_count += 1

            except Exception as e:
                self.stderr.write(
                    f"  [TRAIL_PLACE] Row {i} '{trail_name}→{place_name}': "
                    f"unexpected error — {e}"
                )
                continue

        if not dry_run:
            self.stdout.write(f"  Trail places: {upserted_count} upserted.")

    # ============================================================
    # HELPERS
    # ============================================================

    def clean(self, val, default=None):
        """Return stripped string, or default if NaN/None/empty."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        s = str(val).strip()
        return s if s else default

    def parse_slugs(self, val):
        """Parse a comma-separated slug string into a list of slugified values."""
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return []
        return [slugify(s.strip()) for s in str(val).split(',') if s.strip()]

    def parse_json(self, val, field='field', row=None, label=''):
        """
        Parse a JSON string. Returns the parsed object or None on failure.
        Logs a descriptive error so the row can be fixed in the xlsx.
        """
        loc = f"row {row}" if row is not None else ''
        if val is None or (isinstance(val, float) and pd.isna(val)):
            self.stderr.write(f"  [{label}] {loc}: '{field}' is empty — skipped.")
            return None
        try:
            return json.loads(str(val))
        except json.JSONDecodeError as e:
            self.stderr.write(
                f"  [{label}] {loc}: invalid JSON in '{field}': {e} — skipped."
            )
            return None