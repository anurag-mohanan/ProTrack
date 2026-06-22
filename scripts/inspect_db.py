import sqlite3

conn = sqlite3.connect("protrack.db")
print("ROLES:")
for row in conn.execute("SELECT id, name FROM roles"):
    print(row)
print("\nUSERS:")
for row in conn.execute("SELECT id, email, first_name, last_name, role_id, is_active FROM users"):
    print(row)
print("\nCUSTOMERS:")
for row in conn.execute("SELECT id, name FROM customers"):
    print(row)
print("\nCONTACTS:")
for row in conn.execute("SELECT id, customer_id, first_name, last_name FROM contacts"):
    print(row)
