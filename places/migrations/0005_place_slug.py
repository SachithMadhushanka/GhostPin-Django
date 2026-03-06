from django.db import migrations, models
from django.utils.text import slugify
import uuid


def generate_slugs(apps, schema_editor):
    Place = apps.get_model('places', 'Place')
    for place in Place.objects.all():
        base_slug = slugify(place.name)
        slug = base_slug
        while Place.objects.filter(slug=slug).exclude(pk=place.pk).exists():
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
        place.slug = slug
        place.save()


class Migration(migrations.Migration):

    dependencies = [
        ('places', '0004_remove_report_comment_remove_report_place_and_more'),  # ← keep your existing dependency as-is
    ]

    operations = [
        # Step 1: Add slug WITHOUT unique constraint first
        migrations.AddField(
            model_name='place',
            name='slug',
            field=models.SlugField(max_length=250, blank=True, default=''),
            preserve_default=False,
        ),
        # Step 2: Populate slugs for existing rows
        migrations.RunPython(generate_slugs, migrations.RunPython.noop),
        # Step 3: Now add the unique constraint safely
        migrations.AlterField(
            model_name='place',
            name='slug',
            field=models.SlugField(max_length=250, unique=True, blank=True),
        ),
    ]