# Place this file at:
# yourapp/management/commands/backfill_badges.py
#
# (Create the management/commands/ directories if they don't exist,
#  and add empty __init__.py files in each)
#
# Run with:
#   python manage.py backfill_badges
# Or for a single user:
#   python manage.py backfill_badges --username pramudith

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Evaluate and award badges for all existing users based on their current activity'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Only backfill for this specific username',
        )

    def handle(self, *args, **options):
        # Import here to avoid circular import issues
        from places.views import evaluate_badges_for_user  # adjust 'places' to your app name

        username = options.get('username')
        if username:
            users = User.objects.filter(username=username)
            if not users.exists():
                self.stderr.write(f'User "{username}" not found.')
                return
        else:
            users = User.objects.all()

        total = users.count()
        awarded = 0

        self.stdout.write(f'Evaluating badges for {total} user(s)...')

        for user in users:
            from places.models import UserBadge
            before = UserBadge.objects.filter(user=user).count()
            evaluate_badges_for_user(user)
            after = UserBadge.objects.filter(user=user).count()
            new = after - before
            if new > 0:
                awarded += new
                self.stdout.write(
                    self.style.SUCCESS(f'  {user.username}: +{new} badge(s)')
                )
            else:
                self.stdout.write(f'  {user.username}: no new badges')

        self.stdout.write(self.style.SUCCESS(f'\nDone. {awarded} badge(s) awarded across {total} user(s).'))