from django.core.management.commands.migrate import Command as MigrateCommand  # type: ignore[import]
from django.db import connections
from salesforce.backend import enterprise


class Command(MigrateCommand):

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--sf-interactive', action='store_true',
            help='Run migrate subcommands interactive.',
        )
        parser.add_argument(
            '--sf-no-check-permissions', action='store_true',
            help='Run migrate without check permissions of CustomObjects.',
        )

    def handle(self, *args, **options):
        database = options['database']
        connection = connections[database]
        if connection.vendor == 'salesforce':
            connection.migrate_options = {
                'sf_interactive', options['sf_interactive'],
                'sf_no_check_permissions': options['sf_no_check_permissions'],
            }
            enterprise.check_enterprise_license()
        super().handle(*args, **options)
