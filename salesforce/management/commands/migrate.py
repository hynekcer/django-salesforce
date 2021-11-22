from django.core.management.base import CommandError
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
        parser.add_argument(
            '--sf-create-permission-set', action='store_true',
            help='only Create PermissionSet "Django_Salesforce" on a new SF database to enable migrations.',
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
        if options['sf_create_permission_set']:
            if connection.vendor == 'salesforce':
                from salesforce.backend.schema import DatabaseSchemaEditor  # pylint:disable=import-outside-toplevel
                DatabaseSchemaEditor.create_permission_set(connection)
            else:
                raise CommandError("The option --sf-create-permission-set requires a Salesforce database")
        else:
            super().handle(*args, **options)
