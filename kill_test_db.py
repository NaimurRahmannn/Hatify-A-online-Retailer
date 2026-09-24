import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Ecommerce_Storefront.settings')
django.setup()

from django.db import connection
cursor = connection.cursor()
cursor.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'test_neondb' AND pid <> pg_backend_pid();")
print("Terminated active connections to test_neondb")
