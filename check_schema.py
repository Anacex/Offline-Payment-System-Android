from app.core.db import engine
from sqlalchemy import inspect, text

inspector = inspect(engine)

print("Checking 'users' table schema...")
print("="*60)

if 'users' in inspector.get_table_names():
    columns = inspector.get_columns('users')
    print(f"\nColumns in 'users' table:")
    for col in columns:
        print(f"  - {col['name']}: {col['type']}")
else:
    print("Table 'users' does not exist!")

print("\n" + "="*60)
print("All tables in database:")
for table in inspector.get_table_names():
    print(f"  - {table}")
