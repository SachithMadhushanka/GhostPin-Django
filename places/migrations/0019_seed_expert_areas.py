# Save this file as:
#   places/migrations/0019_seed_expert_areas.py
# (adjust the number to be one higher than your latest migration)
#
# Then run: python manage.py migrate

from django.db import migrations

EXPERT_AREAS = [
    # Languages
    "Sinhala",
    "English",
    "Tamil",
    "Mandarin",
    "Japanese",
    "German",
    "French",
    # Travel & Outdoors
    "Traveling",
    "Hiking & Trekking",
    "Camping",
    "Exploring",
    "Wildlife & Nature",
    "Beaches & Water",
    "Mountains & Highlands",
    # Arts & Media
    "Photography",
    "Videography",
    "Travel Writing",
    # Local Knowledge
    "Guiding",
    "Local Culture & Heritage",
    "Food & Cuisine",
    "History & Archaeology",
    "Religious & Sacred Sites",
    # Adventure
    "Cycling",
    "Rock Climbing",
    "Surfing & Water Sports",
    "Bird Watching",
]


def seed_expert_areas(apps, schema_editor):
    ExpertArea = apps.get_model("places", "ExpertArea")
    for name in EXPERT_AREAS:
        ExpertArea.objects.get_or_create(name=name)


def unseed_expert_areas(apps, schema_editor):
    ExpertArea = apps.get_model("places", "ExpertArea")
    ExpertArea.objects.filter(name__in=EXPERT_AREAS).delete()


class Migration(migrations.Migration):

    # ── change this to match your actual latest migration file name ──
    dependencies = [
        ("places", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_expert_areas, reverse_code=unseed_expert_areas),
    ]