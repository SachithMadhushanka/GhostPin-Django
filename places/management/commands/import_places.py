"""
Management command: import_places
Place this file at:
    places/management/commands/import_places.py

Usage:
    python manage.py import_places
    python manage.py import_places --file path/to/Expearls_Places_Import_v3.xlsx
    python manage.py import_places --file data.xlsx --images path/to/images/folder
    python manage.py import_places --dry-run          # preview without saving
    python manage.py import_places --update           # update existing places too
    python manage.py import_places --user admin       # specify which user to assign


    python manage.py import_places --images /Users/sachithmadhushaka/Documents/GhostPin/data_images --update
"""

import os
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from django.core.files import File
from django.contrib.auth.models import User

from places.models import Place, Category


# ── Column name map (Excel header → variable) ─────────────────────────────────
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

VALID_DIFFICULTIES = {'easy', 'moderate', 'challenging'}
VALID_STATUSES     = {'approved', 'pending', 'rejected'}


class Command(BaseCommand):
    help = 'Import places and categories from Expearls Excel file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file', '-f',
            default='Expearls_Places_Import_v3.xlsx',
            help='Path to the Excel file (default: Expearls_Places_Import_v3.xlsx)',
        )
        parser.add_argument(
            '--images', '-i',
            default='data_images',
            help='Path to folder containing place images (default: data_images/)',
        )
        parser.add_argument(
            '--user', '-u',
            default=None,
            help='Username to assign as created_by (default: first superuser)',
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing places with new data (default: skip existing)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be imported without saving anything',
        )
        parser.add_argument(
            '--skip-categories',
            action='store_true',
            help='Skip category import (if already imported)',
        )

    # ─────────────────────────────────────────────────────────────────────────
    def handle(self, *args, **options):
        file_path  = options['file']
        images_dir = options['images']
        update     = options['update']
        dry_run    = options['dry_run']
        skip_cats  = options['skip_categories']

        if not os.path.exists(file_path):
            raise CommandError(f"File not found: {file_path}")

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — nothing will be saved.\n'))

        try:
            xls = pd.ExcelFile(file_path)
        except Exception as e:
            raise CommandError(f"Cannot open Excel file: {e}")

        admin_user = self._get_user(options['user'])

        # Import categories first
        if not skip_cats:
            if 'All Categories' in xls.sheet_names:
                cat_df = pd.read_excel(xls, sheet_name='All Categories', header=0)
                self._import_categories(cat_df, dry_run)
            else:
                self.stdout.write(self.style.WARNING(
                    "No 'All Categories' sheet found — skipping category import."
                ))

        # Import places
        if 'Places (Import Ready)' in xls.sheet_names:
            places_df = pd.read_excel(xls, sheet_name='Places (Import Ready)', header=0)
            self._import_places(places_df, admin_user, images_dir, update, dry_run)
        else:
            raise CommandError("No 'Places (Import Ready)' sheet found in the Excel file.")

    # ─────────────────────────────────────────────────────────────────────────
    def _get_user(self, username):
        if username:
            try:
                return User.objects.get(username=username)
            except User.DoesNotExist:
                raise CommandError(f"User '{username}' not found.")
        user = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(is_staff=True).first()
            or User.objects.first()
        )
        if not user:
            raise CommandError(
                "No users found. Create one first: python manage.py createsuperuser"
            )
        self.stdout.write(f"Using user '{user.username}' as created_by.\n")
        return user

    # ─────────────────────────────────────────────────────────────────────────
    def _import_categories(self, df, dry_run):
        self.stdout.write(self.style.HTTP_INFO('\n── Importing Categories ──'))

        slug_col = df.columns[0]
        name_col = df.columns[1]
        created_count = skipped_count = 0

        for _, row in df.iterrows():
            raw_slug = str(row[slug_col]).strip()
            name     = str(row[name_col]).strip()
            if not raw_slug or raw_slug == 'nan' or not name or name == 'nan':
                continue
            slug = slugify(raw_slug)

            if dry_run:
                exists = Category.objects.filter(slug=slug).exists()
                label  = 'EXISTS' if exists else 'CREATE'
                self.stdout.write(f"  [{label}] {name} ({slug})")
                if not exists:
                    created_count += 1
                continue

            category, created = Category.objects.get_or_create(
                slug=slug, defaults={'name': name}
            )
            if created:
                created_count += 1
                self.stdout.write(f"  [CREATED] {name} ({slug})")
            else:
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"  Categories: {created_count} created, {skipped_count} already existed.\n"
        ))

    # ─────────────────────────────────────────────────────────────────────────
    def _import_places(self, df, admin_user, images_dir, update, dry_run):
        self.stdout.write(self.style.HTTP_INFO('── Importing Places ──'))

        created_count = updated_count = skipped_count = error_count = 0

        for idx, row in df.iterrows():
            row_num = idx + 2

            # ── Required fields ───────────────────────────────────────────────
            name = self._clean_str(row.get(COL['name']))
            if not name:
                self.stdout.write(self.style.ERROR(
                    f"  Row {row_num}: Skipping — empty Name."
                ))
                error_count += 1
                continue

            description   = self._clean_str(row.get(COL['description']),   default='')
            legends       = self._clean_str(row.get(COL['legends']),        default='')
            accessibility = self._clean_str(row.get(COL['accessibility']),  default='')
            best_time     = self._clean_str(row.get(COL['best_time']),      default='')

            try:
                latitude  = float(row.get(COL['latitude'],  0) or 0)
                longitude = float(row.get(COL['longitude'], 0) or 0)
            except (ValueError, TypeError):
                self.stdout.write(self.style.WARNING(
                    f"  Row {row_num} ({name}): Bad coordinates — using 0,0."
                ))
                latitude = longitude = 0.0

            difficulty = self._clean_str(
                row.get(COL['difficulty']), default='moderate'
            ).lower()
            if difficulty not in VALID_DIFFICULTIES:
                difficulty = 'moderate'

            try:
                safety_rating = int(float(row.get(COL['safety'], 3) or 3))
                safety_rating = max(1, min(5, safety_rating))
            except (ValueError, TypeError):
                safety_rating = 3

            status = self._clean_str(
                row.get(COL['status']), default='pending'
            ).lower()
            if status not in VALID_STATUSES:
                status = 'pending'

            cat_slugs      = self._parse_category_slugs(row.get(COL['categories']))
            image_filename = self._clean_str(row.get(COL['image_filename']), default='')

            # ── Dry run ───────────────────────────────────────────────────────
            if dry_run:
                exists = Place.objects.filter(name=name).exists()
                label  = 'UPDATE' if (exists and update) else ('SKIP' if exists else 'CREATE')
                self.stdout.write(
                    f"  [{label}] {name} | {difficulty} | "
                    f"safety={safety_rating} | cats={cat_slugs}"
                )
                if not exists:
                    created_count += 1
                continue

            # ── Create or get ─────────────────────────────────────────────────
            place, created = Place.objects.get_or_create(
                name=name,
                defaults={
                    'description':        description,
                    'legends_stories':    legends,
                    'latitude':           latitude,
                    'longitude':          longitude,
                    'difficulty':         difficulty,
                    'accessibility_info': accessibility,
                    'best_time_to_visit': best_time,
                    'safety_rating':      safety_rating,
                    'status':             status,
                    'created_by':         admin_user,
                }
            )

            if not created:
                if update:
                    place.description        = description
                    place.legends_stories    = legends
                    place.latitude           = latitude
                    place.longitude          = longitude
                    place.difficulty         = difficulty
                    place.accessibility_info = accessibility
                    place.best_time_to_visit = best_time
                    place.safety_rating      = safety_rating
                    place.status             = status
                    place.save()
                    updated_count += 1
                    self.stdout.write(f"  [UPDATED] {name}")
                else:
                    skipped_count += 1
                    continue
            else:
                created_count += 1
                self.stdout.write(f"  [CREATED] {name}")

            # ── Categories ────────────────────────────────────────────────────
            for slug in cat_slugs:
                try:
                    place.category.add(Category.objects.get(slug=slug))
                except Category.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"    Category '{slug}' not found — skipped for '{name}'"
                    ))

            # ── Image ─────────────────────────────────────────────────────────
            if image_filename and not place.image:
                # List of extensions to try if file doesn't exist
                possible_extensions = ['', '.jpg', '.jpeg', '.png', '.webp', '.gif']
                found_image = False

                for ext in possible_extensions:
                    # Add extension if not already present
                    if not image_filename.lower().endswith(ext):
                        trial_filename = image_filename + ext
                    else:
                        trial_filename = image_filename

                    image_path = os.path.join(images_dir, trial_filename)
                    if os.path.isfile(image_path):
                        with open(image_path, 'rb') as f:
                            place.image.save(trial_filename, File(f), save=True)
                        self.stdout.write(f"    Image: {trial_filename}")
                        found_image = True
                        break  # stop after first valid file

                if not found_image:
                    self.stdout.write(self.style.WARNING(
                        f"    Image not found for '{name}': {image_filename}"
                    ))

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN complete — {created_count} would be created."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Import complete:\n"
                f"  Created:  {created_count}\n"
                f"  Updated:  {updated_count}\n"
                f"  Skipped:  {skipped_count}\n"
                f"  Errors:   {error_count}"
            ))

    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _clean_str(value, default=None):
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        s = str(value).strip()
        return s if s and s.lower() != 'nan' else default

    @staticmethod
    def _parse_category_slugs(value):
        if not value or (isinstance(value, float) and pd.isna(value)):
            return []
        return [slugify(s.strip()) for s in str(value).split(',') if s.strip()]