import getpass
import os

from django.contrib.auth import password_validation
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.services.lifecycle import bootstrap_admin


class Command(BaseCommand):
    help = "Create the initial admin account and its audit event."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email")
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument(
            "--password-env",
            default="PATHGEN_BOOTSTRAP_ADMIN_PASSWORD",
            help="Environment variable containing the password.",
        )
        parser.add_argument("--noinput", action="store_true")

    def handle(self, *args, **options):
        password = os.getenv(options["password_env"])
        if not password and options["noinput"]:
            raise CommandError(f'{options["password_env"]} is not set.')
        if not password:
            password = getpass.getpass("Password: ")
            confirmation = getpass.getpass("Password (again): ")
            if password != confirmation:
                raise CommandError("Passwords do not match.")

        try:
            password_validation.validate_password(password)
            admin = bootstrap_admin(
                username=options["username"],
                password=password,
                email=options["email"],
                first_name=options["first_name"],
                last_name=options["last_name"],
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f'Admin "{admin.username}" created.'))
