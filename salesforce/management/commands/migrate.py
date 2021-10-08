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

    def handle(self, *args, **options):
        database = options['database']
        connection = connections[database]
        if connection.vendor == 'salesforce':
            connection.migrate_options = {
                'sf_interactive', options['sf_interactive'],
            }
            enterprise.check_enterprise_license()
        super().handle(*args, **options)
