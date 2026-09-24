# My agent: Smart Pantry & Chef Concierge

One-liner: A conversational agent that helps home cooks manage their pantry inventory, discover personalized recipes grounded in available ingredients, and generate custom dish visuals and nutritional calculations.

Tool coverage:
- Memory: Remembers dietary preferences, household allergies, preferred cuisines, and skill level across sessions.
- Tools: Pantry inventory lookup/update, recipe search, nutritional scaling.
- Catalog/UI: Pantry item list and recipe collection (renders as rich cards/tables with A2UI).
- Image gen: Generates AI dish previews for proposed recipes.
- Sandbox: Performs batch ingredient conversions and nutrition scaling calculations.

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch: Code sandbox for nutritional calculations, Firestore for pantry inventory.

GCP Resources:
- Firestore Database: `(default)` in `us-east1` (Collection: `pantry`)
- Cloud Storage Bucket: `gs://smart-pantry-chef-media-qwiklabs-gcp-02-9ae4d5107538` (Public Object Viewer enabled)
