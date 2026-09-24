# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import logging
import os
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

load_dotenv()

FIRESTORE_PROJECT_ID = "qwiklabs-gcp-02-9ae4d5107538"
GCS_BUCKET_NAME = "smart-pantry-chef-media-qwiklabs-gcp-02-9ae4d5107538"

db = firestore.Client(project=FIRESTORE_PROJECT_ID)

# Load Agent Engine resource name from deployment_metadata.json if available
agent_engine_resource_name = None
metadata_path = os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
if os.path.exists(metadata_path):
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Failed to load deployment_metadata.json: {e}")

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


def get_pantry_items(category: str = "") -> str:
    """Reads items from the Firestore pantry collection.

    Args:
        category: Optional category filter (e.g. 'Meat', 'Produce', 'Pantry', 'Dairy').

    Returns:
        A JSON string listing pantry items with quantities, units, and expiration dates.
    """
    collection_ref = db.collection("pantry")
    if category:
        docs = collection_ref.where("category", "==", category).stream()
    else:
        docs = collection_ref.stream()

    items = []
    for doc in docs:
        data = doc.to_dict()
        items.append(data)

    if not items:
        return f"No pantry items found{' for category ' + category if category else ''}."
    return json.dumps(items, indent=2)


def add_or_update_pantry_item(
    item_name: str, quantity: float, unit: str, category: str, expiration_date: str = ""
) -> str:
    """Adds or updates an item in the Firestore pantry collection.

    Args:
        item_name: Name of the item (e.g. 'Chicken Breast', 'Olive Oil').
        quantity: Numerical quantity available.
        unit: Unit of measurement (e.g. 'grams', 'items', 'ml').
        category: Food category (e.g. 'Meat', 'Produce', 'Pantry', 'Dairy').
        expiration_date: Expiration date string (YYYY-MM-DD).

    Returns:
        Confirmation message of the operation.
    """
    doc_id = item_name.lower().replace(" ", "_").replace("(", "").replace(")", "")
    item_data = {
        "name": item_name,
        "quantity": float(quantity),
        "unit": unit,
        "category": category,
        "expiration_date": expiration_date,
    }
    db.collection("pantry").document(doc_id).set(item_data)
    return f"Successfully saved pantry item '{item_name}' ({quantity} {unit}) in category '{category}'."


def search_recipes(ingredients: str = "", max_prep_time_minutes: int = 45) -> str:
    """Searches for delicious local recipes that can be made with specified or pantry ingredients.

    Args:
        ingredients: Optional comma-separated list of key ingredients (e.g. 'chicken, tomatoes').
        max_prep_time_minutes: Maximum preparation time in minutes.

    Returns:
        A JSON string containing matching recipe ideas with required ingredients, prep time, and instructions.
    """
    recipes = [
        {
            "title": "Garlic Tomato Chicken Pasta",
            "prep_time_minutes": 25,
            "key_ingredients": ["chicken", "tomatoes", "garlic", "pasta", "olive oil", "parmesan"],
            "description": "Seared chicken breast tossed with freshly sautéed garlic, tomatoes, spaghetti, olive oil, and topped with grated parmesan cheese.",
            "instructions": [
                "Boil spaghetti until al dente.",
                "Sauté diced chicken breast in olive oil until golden brown.",
                "Add minced garlic and diced tomatoes to the skillet.",
                "Toss cooked pasta into skillet and top with fresh parmesan cheese.",
            ],
        },
        {
            "title": "Classic Fresh Tomato Pasta",
            "prep_time_minutes": 15,
            "key_ingredients": ["tomatoes", "garlic", "pasta", "olive oil", "parmesan"],
            "description": "Quick and flavorful pasta tossed with garlic-infused olive oil, sweet ripe tomatoes, and parmesan.",
            "instructions": [
                "Cook pasta according to package directions.",
                "Heat olive oil and gently sauté sliced garlic.",
                "Add chopped tomatoes and simmer for 5 minutes.",
                "Combine with pasta and sprinkle with parmesan.",
            ],
        },
        {
            "title": "Pan-Seared Garlic Herb Chicken",
            "prep_time_minutes": 20,
            "key_ingredients": ["chicken", "garlic", "olive oil"],
            "description": "Tender chicken breasts seared in aromatic garlic and olive oil.",
            "instructions": [
                "Season chicken breasts with salt and pepper.",
                "Heat olive oil in pan and add crushed garlic cloves.",
                "Sear chicken 6-7 minutes per side until cooked through.",
            ],
        },
    ]

    filtered = []
    ing_list = [i.strip().lower() for i in ingredients.split(",")] if ingredients else []

    for r in recipes:
        if r["prep_time_minutes"] > max_prep_time_minutes:
            continue
        if ing_list:
            match = any(
                any(user_ing in req_ing for req_ing in r["key_ingredients"])
                for user_ing in ing_list
            )
            if not match:
                continue
        filtered.append(r)

    results = filtered if filtered else recipes
    return json.dumps(results, indent=2)


def fetch_online_recipes(query: str = "chicken") -> str:
    """Fetches real online recipes from TheMealDB public API.

    Args:
        query: Search term for dish or main ingredient (e.g. 'chicken', 'pasta', 'arrabiata').

    Returns:
        A JSON string containing real recipes with ingredients, instructions, area/cuisine, and photo URLs.
    """
    url = f"https://www.themealdb.com/api/json/v1/1/search.php?s={urllib.parse.quote(query)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartPantryChef/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            meals = data.get("meals")
            if not meals:
                return f"No online recipes found for query '{query}'."

            results = []
            for meal in meals[:3]:
                ingredients = []
                for i in range(1, 21):
                    ing = meal.get(f"strIngredient{i}")
                    measure = meal.get(f"strMeasure{i}")
                    if ing and ing.strip():
                        ingredients.append(f"{measure.strip() if measure else ''} {ing.strip()}".strip())

                results.append({
                    "title": meal.get("strMeal"),
                    "category": meal.get("strCategory"),
                    "area": meal.get("strArea"),
                    "instructions": meal.get("strInstructions"),
                    "image_url": meal.get("strMealThumb"),
                    "ingredients": ingredients,
                })
            return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error fetching online recipes: {str(e)}"


def generate_dish_image(dish_name: str, tool_context: ToolContext) -> str:
    """Generates an image preview of a dish/recipe using the gemini-3.1-flash-lite-image model, saves it as an artifact, and uploads it to public Cloud Storage.

    Args:
        dish_name: Name or description of the dish to generate an image for (e.g. 'Spaghetti Arrabiata').
        tool_context: ADK ToolContext for saving session artifacts.

    Returns:
        The public HTTPS URL (https://storage.googleapis.com/<bucket>/<object>) of the generated image.
    """
    genai_client = genai.Client(
        vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
    )
    prompt = f"A professional food photography photo of {dish_name}, appetizing presentation."
    response = genai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
    )

    if not response.candidates or not response.candidates[0].content.parts:
        return f"Error: Failed to generate image for '{dish_name}'."

    part = response.candidates[0].content.parts[0]
    image_bytes = part.inline_data.data
    mime_type = part.inline_data.mime_type or "image/jpeg"

    filename = f"dish_{uuid.uuid4().hex[:8]}.jpg"

    # 1. Save artifact to show up in Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 2. Upload image bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    return public_url


def generate_dish_video(dish_name: str, tool_context: ToolContext) -> str:
    """Generates a short culinary demonstration video for a dish or recipe using Google's Omni model (gemini-omni-flash-preview) in the global region, saves it as an artifact, and uploads it to public Cloud Storage.

    Args:
        dish_name: Name or description of the dish or cooking demonstration to generate a video for (e.g. 'Sautéing Garlic and Tomatoes' or 'Plated Spaghetti').
        tool_context: ADK ToolContext for saving session artifacts.

    Returns:
        The public HTTPS URL (https://storage.googleapis.com/<bucket>/<object>) of the generated video.
    """
    genai_client = genai.Client(
        vertexai=True, project=FIRESTORE_PROJECT_ID, location="global"
    )
    prompt = f"A short 5-second culinary video showing {dish_name}, high quality, appetizing."
    interaction = genai_client.interactions.create(
        model="gemini-omni-flash-preview",
        input=prompt,
    )

    if not hasattr(interaction, "output_video") or not interaction.output_video or not interaction.output_video.data:
        return f"Error: Failed to generate video for '{dish_name}'."

    video_bytes = interaction.output_video.data
    mime_type = interaction.output_video.mime_type or "video/mp4"

    filename = f"video_{uuid.uuid4().hex[:8]}.mp4"

    # 1. Save artifact with tool_context.save_artifact so it shows up in Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 2. Upload video bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
    return public_url



def geocode_address(address: str) -> str:
    """Uses Google Geocoding API to convert an address string into geographic coordinates.

    Args:
        address: Address string (e.g. '1600 Amphitheatre Parkway, Mountain View, CA' or 'San Francisco, CA').

    Returns:
        A JSON string containing the formatted address and latitude/longitude location.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not configured."

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") != "OK" or not data.get("results"):
                return f"Geocoding failed for address '{address}': {data.get('status')}"

            result = data["results"][0]
            loc = result["geometry"]["location"]
            res_dict = {
                "address": result.get("formatted_address"),
                "location": {
                    "latitude": loc.get("lat"),
                    "longitude": loc.get("lng"),
                },
            }
            return json.dumps(res_dict, indent=2)
    except Exception as e:
        return f"Error calling Geocoding API: {str(e)}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "supermarket",
    radius_meters: float = 5000.0,
) -> str:
    """Uses Google Places API (New) to search for nearby places of a specific type.

    Args:
        latitude: Geographic latitude coordinate.
        longitude: Geographic longitude coordinate.
        place_type: Type of place to search for (e.g. 'supermarket', 'grocery_store', 'bakery', 'restaurant').
        radius_meters: Search radius in meters (default 5000.0 meters).

    Returns:
        A JSON string listing nearby places with their name, formatted address, and location.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not configured."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": float(latitude), "longitude": float(longitude)},
                "radius": float(radius_meters),
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            places = data.get("places", [])
            if not places:
                return f"No nearby places of type '{place_type}' found within {radius_meters}m."

            results = []
            for p in places:
                display_name = p.get("displayName", {}).get("text", "")
                results.append({
                    "name": display_name,
                    "address": p.get("formattedAddress"),
                    "location": p.get("location"),
                })
            return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error calling Places API (New): {str(e)}"


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        logging.warning(f"Memory service not available or error adding session to memory: {e}")
    return None


def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id="5128256372365852672",
    )


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are the Smart Pantry & Chef Concierge assistant. You help users manage their pantry "
        "inventory stored in Firestore, search for online or local recipes, generate AI food previews "
        "using image generation, locate nearby supermarkets and grocery stores using Google Maps APIs, "
        "execute python code in a sandbox, and keep track of food items."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects.\n\n"
        "Memory & Personalization: You remember the user's stated preferences, dietary restrictions, "
        "and food allergies from previous conversations. Always strictly respect all user allergies and "
        "health requirements when suggesting recipes, ingredients, or meal options.\n\n"
        "When you need to run Python code, output the code inside a standard python markdown block "
        "(e.g. ```python ... ```). Do not invoke any function tool named code_interpreter."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        get_pantry_items,
        add_or_update_pantry_item,
        search_recipes,
        fetch_online_recipes,
        generate_dish_image,
        generate_dish_video,
        geocode_address,
        find_nearby_places,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
