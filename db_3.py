import sqlite3
import os

# Database file path
DB_PATH = "example3.db"

# Display the absolute path of the database file
print(f"Database path: {os.path.abspath(DB_PATH)}")

# Initialize the database table, ensuring `user_id` and `info` columns exist
def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Create the table only if it doesn't already exist
        c.execute("""
            CREATE TABLE IF NOT EXISTS BackgroundInfo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                info TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        print("Database initialized successfully.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")

# Add a single background info entry
def add_background_info(user_id, new_info):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        print(f"Inserting data: user_id = {user_id}, info = {new_info}")
        c.execute("""
            INSERT INTO BackgroundInfo (user_id, info) VALUES (?, ?)
        """, (user_id, new_info))

        conn.commit()
        print("Data successfully written to the database.")
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unknown error: {e}")

# Add multiple background info entries in bulk
def add_bulk_background_info(user_id, info_list):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        print(f"Bulk inserting data: user_id = {user_id}")
        c.executemany("""
            INSERT INTO BackgroundInfo (user_id, info) VALUES (?, ?)
        """, [(user_id, info) for info in info_list])

        conn.commit()
        print("Bulk data successfully written to the database.")
        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unknown error: {e}")

# Retrieve and display all background info entries
def get_all_background_info():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        print("Retrieving data...")
        c.execute("""SELECT id, user_id, info FROM BackgroundInfo""")
        rows = c.fetchall()

        if not rows:
            print("No background information found in the database.")
        else:
            for row in rows:
                print(f"ID: {row[0]}, User ID: {row[1]}, Background Info: {row[2]}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unknown error: {e}")

# Delete a specific entry by ID
def delete_background_info_by_id(record_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        print(f"Deleting data with ID: {record_id}")
        c.execute("DELETE FROM BackgroundInfo WHERE id = ?", (record_id,))
        conn.commit()

        if c.rowcount > 0:
            print("Data successfully deleted.")
        else:
            print("No data found with the specified ID.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unknown error: {e}")

# Delete multiple entries by IDs in bulk
def delete_bulk_background_info(record_ids):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        print(f"Bulk deleting data with IDs: {record_ids}")
        placeholders = ",".join(["?"] * len(record_ids))  # Dynamically generate placeholders
        query = f"DELETE FROM BackgroundInfo WHERE id IN ({placeholders})"
        c.execute(query, record_ids)
        conn.commit()

        if c.rowcount > 0:
            print(f"Successfully deleted {c.rowcount} records.")
        else:
            print("No data found with the specified IDs.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Unknown error: {e}")

# Main program
if __name__ == "__main__":
    init_db()

    print("1. Add background info")
    print("2. View all background info")
    print("3. Add bulk background info")
    print("4. Delete data by ID")
    print("5. Delete bulk data by IDs")

    choice = input("Please select an option (1/2/3/4/5): ").strip()

    if choice == "1":
        user_id = input("Enter user ID: ").strip()
        new_info = input("Enter new background info: ").strip()
        add_background_info(user_id, new_info)
    elif choice == "2":
        get_all_background_info()
    elif choice == "3":
        user_id = input("Enter user ID: ").strip()
        print("Enter multiple background info entries (one per line):")
        info_list = []
        while True:
            new_info = input("Background info (press Enter to finish): ").strip()
            if not new_info:
                break
            info_list.append(new_info)
        add_bulk_background_info(user_id, info_list)
    elif choice == "4":
        record_id = input("Enter the ID of the data to delete: ").strip()
        if record_id.isdigit():
            delete_background_info_by_id(int(record_id))
        else:
            print("Invalid ID. Please enter a number.")
    elif choice == "5":
        print("Enter the IDs to delete in bulk, separated by commas (e.g., 1,2,3)")
        record_ids = input("Enter ID list: ").strip()
        try:
            id_list = [int(id.strip()) for id in record_ids.split(",") if id.strip().isdigit()]
            if id_list:
                delete_bulk_background_info(id_list)
            else:
                print("Invalid input. Please enter valid numeric IDs.")
        except ValueError:
            print("Invalid input. Please ensure the format is correct.")
    else:
        print("Invalid choice.")
