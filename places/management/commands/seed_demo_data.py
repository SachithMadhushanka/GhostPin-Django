import random
from faker import Faker
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from places.models import (
    UserProfile, Place, CheckIn, Comment, Vote, Favorite,
    Trail, TrailPlace, Badge, UserBadge, Notification
)

fake = Faker()

class Command(BaseCommand):
    help = "Generate demo data"

    def handle(self, *args, **kwargs):

        self.stdout.write("Creating demo users...")

        users = []

        for i in range(30):
            username = fake.user_name() + str(i)

            user = User.objects.create_user(
                username=username,
                email=fake.email(),
                password="password123"
            )

            UserProfile.objects.create(
                user=user,
                bio=fake.sentence(),
                location=fake.city(),
                points=random.randint(0, 500)
            )

            users.append(user)

        places = list(Place.objects.filter(status="approved"))

        if not places:
            self.stdout.write("No approved places found!")
            return

        self.stdout.write("Creating checkins...")

        checkins = []

        for i in range(200):
            user = random.choice(users)
            place = random.choice(places)

            checkin, created = CheckIn.objects.get_or_create(
                user=user,
                place=place,
                defaults={
                    "notes": fake.sentence(),
                    "points_awarded": random.randint(5, 20)
                }
            )

            if created:
                checkins.append(checkin)

        self.stdout.write("Creating comments...")

        comments = []

        for i in range(300):

            user = random.choice(users)
            place = random.choice(places)

            comment = Comment.objects.create(
                user=user,
                place=place,
                text=fake.paragraph(),
                rating=random.randint(3, 5)
            )

            comments.append(comment)

        self.stdout.write("Creating replies...")

        for comment in random.sample(comments, 80):

            Comment.objects.create(
                user=random.choice(users),
                place=comment.place,
                parent=comment,
                text=fake.sentence()
            )

        self.stdout.write("Creating votes...")

        for comment in random.sample(comments, 200):

            Vote.objects.get_or_create(
                user=random.choice(users),
                comment=comment,
                vote_type=random.choice(["up", "down"])
            )

        self.stdout.write("Creating favorites...")

        for i in range(150):

            Favorite.objects.get_or_create(
                user=random.choice(users),
                place=random.choice(places)
            )

        self.stdout.write("Creating trails...")

        trails = []

        for i in range(10):

            trail = Trail.objects.create(
                name=fake.catch_phrase(),
                description=fake.text(),
                created_by=random.choice(users),
                difficulty=random.choice(["easy","moderate","challenging"])
            )

            trails.append(trail)

            trail_places = random.sample(places, min(5, len(places)))

            order = 1

            for place in trail_places:

                TrailPlace.objects.create(
                    trail=trail,
                    place=place,
                    order=order
                )

                order += 1

        self.stdout.write("Creating badges...")

        badges = []

        for i in range(6):

            badge = Badge.objects.create(
                name=fake.word().title() + " Badge",
                description=fake.sentence(),
                criteria={"checkins": random.randint(5,20)},
                category=random.choice(["explorer","contributor","social"])
            )

            badges.append(badge)

        for user in users:

            for badge in random.sample(badges, random.randint(0,3)):

                UserBadge.objects.get_or_create(
                    user=user,
                    badge=badge
                )

        self.stdout.write("Creating notifications...")

        for i in range(200):

            Notification.objects.create(
                user=random.choice(users),
                title="New Activity",
                message=fake.sentence(),
                notification_type=random.choice([
                    "badge_earned",
                    "challenge",
                    "place_added"
                ])
            )

        self.stdout.write(self.style.SUCCESS("Demo data created successfully!"))