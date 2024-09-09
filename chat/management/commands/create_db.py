from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

class Command(BaseCommand):
    help = 'Create the database if it does not exist'

    def handle(self, *args, **kwargs):
        connection = connections['default']
        try:
            # Try to connect to the database
            connection.cursor()
            self.stdout.write(self.style.SUCCESS('Database already exists.'))
        except OperationalError:
            # Database does not exist; create it
            from django.db import connection
            from django.conf import settings
            import psycopg2

            db_name = settings.DATABASES['default']['NAME']
            user = settings.DATABASES['default']['USER']
            password = settings.DATABASES['default']['PASSWORD']
            host = settings.DATABASES['default']['HOST']
            port = settings.DATABASES['default']['PORT']

            conn = psycopg2.connect(dbname='postgres', user=user, password=password, host=host, port=port)
            conn.autocommit = True
            cursor = conn.cursor()
            try:
                cursor.execute(f'CREATE DATABASE {db_name}')
                self.stdout.write(self.style.SUCCESS(f'Database {db_name} created successfully.'))
            except psycopg2.Error as e:
                self.stdout.write(self.style.ERROR(f'Error creating database: {e}'))
            finally:
                cursor.close()
                conn.close()
