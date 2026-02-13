from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework.authtoken.models import Token

from apps.accounts.models import Subscription
from services.stock_service import ensure_index_stocks


class Command(BaseCommand):
    help = "부하테스트용 사용자/구독 데이터를 초기화합니다."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="loadtest-pro")
        parser.add_argument("--password", required=True)
        parser.add_argument("--email", default="loadtest@example.com")
        parser.add_argument(
            "--plan",
            choices=[Subscription.Plan.FREE, Subscription.Plan.PRO, Subscription.Plan.ENTERPRISE],
            default=Subscription.Plan.PRO,
        )
        parser.add_argument("--days-valid", type=int, default=365)
        parser.add_argument("--create-token", action="store_true")
        parser.add_argument("--no-seed-indexes", action="store_true")

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]
        email = options["email"].strip()
        plan = options["plan"]
        days_valid = options["days_valid"]
        create_token = options["create_token"]
        no_seed_indexes = options["no_seed_indexes"]

        if not username:
            self.stderr.write(self.style.ERROR("username은 비어 있을 수 없습니다."))
            return

        if days_valid < 1:
            self.stderr.write(self.style.ERROR("--days-valid는 1 이상이어야 합니다."))
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email},
        )
        user.email = email
        user.set_password(password)
        user.save(update_fields=["email", "password"])

        today = timezone.localdate()
        Subscription.objects.filter(user=user, is_active=True).update(is_active=False)
        subscription = Subscription.objects.create(
            user=user,
            plan=plan,
            is_active=True,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=days_valid),
            is_trial=False,
            metadata={"source": "bootstrap_loadtest"},
        )

        token_key = None
        if create_token:
            Token.objects.filter(user=user).delete()
            token_key = Token.objects.create(user=user).key

        seeded_indices = None
        if not no_seed_indexes:
            seeded_indices = ensure_index_stocks()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"loadtest user {action}: {user.username}"))
        self.stdout.write(f"plan: {subscription.plan}, active until: {subscription.end_date}")
        if token_key:
            self.stdout.write(f"token: {token_key}")
        if seeded_indices is not None:
            self.stdout.write(f"seeded_index_count: {len(seeded_indices)}")
