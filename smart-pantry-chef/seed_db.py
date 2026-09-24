"""Seed script for Smart Pantry & Chef Concierge Firestore database."""

from google.cloud import firestore

FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-9ae4d5107538"


def seed_database():
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)

    pantry_items = [
        {
            "name": "Chicken Breast",
            "quantity": 500.0,
            "unit": "grams",
            "category": "Meat",
            "expiration_date": "2026-09-28",
        },
        {
            "name": "Tomatoes",
            "quantity": 6.0,
            "unit": "items",
            "category": "Produce",
            "expiration_date": "2026-09-30",
        },
        {
            "name": "Garlic",
            "quantity": 1.0,
            "unit": "head",
            "category": "Produce",
            "expiration_date": "2026-10-15",
        },
        {
            "name": "Olive Oil",
            "quantity": 500.0,
            "unit": "ml",
            "category": "Pantry",
            "expiration_date": "2026-12-31",
        },
        {
            "name": "Pasta (Spaghetti)",
            "quantity": 1000.0,
            "unit": "grams",
            "category": "Pantry",
            "expiration_date": "2027-01-01",
        },
        {
            "name": "Parmesan Cheese",
            "quantity": 200.0,
            "unit": "grams",
            "category": "Dairy",
            "expiration_date": "2026-10-10",
        },
    ]

    collection_ref = db.collection("pantry")
    print(f"Seeding items into 'pantry' collection on project '{FIRESTORE_PROJECT_ID}'...")
    for item in pantry_items:
        doc_id = item["name"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        collection_ref.document(doc_id).set(item)
        print(f" - Added document: {doc_id} -> {item}")

    print("Database seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
