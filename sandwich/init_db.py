"""
init_db.py
==========
Creates database/portal.db, all the tables, and the demo data.

    python init_db.py            # create if missing (safe to re-run)
    python init_db.py --reset    # delete the database and rebuild it from scratch
"""

import sys

import database
import seed_data


def main():
    reset = "--reset" in sys.argv

    if reset:
        database.reset_db()
        print("Deleted the old database.")

    print("Creating tables ...")
    database.init_db()

    conn = database.connect()
    try:
        if seed_data.is_seeded(conn):
            print("\nDemo data already present - nothing to insert.")
            print("Run  python init_db.py --reset  to rebuild from scratch.")
        else:
            print("Inserting demo data ...")
            seed_data.seed(conn)
            print("\nDone. Database ready at:", database.DB_PATH)
            print("\nDemo logins (password for all: %s)" % seed_data.DEMO_PASSWORD)
            print("  student   rahul@demo.com")
            print("  company   hr@technova.com")
            print("  college   dean@cvr.edu.in")
        print("\nNext step:  python app.py")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
