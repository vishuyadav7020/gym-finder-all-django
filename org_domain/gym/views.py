from bson import ObjectId

from django.utils import timezone

from django.utils.decorators import method_decorator

from django.views.decorators.csrf import csrf_exempt

from rest_framework import status

from rest_framework.permissions import AllowAny

from rest_framework.response import Response

from rest_framework.views import APIView



from .mongo import org_gym_collection

from org_domain.authentication.mongo import org_collection

from org_domain.schema import GymSchema



import jwt

import os

import uuid

from django.conf import settings

from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


def flatten_photos(photos):
    """Flatten nested photo arrays into a flat list of strings."""
    result = []
    if not photos:
        return result
    for item in photos:
        if isinstance(item, list):
            result.extend(flatten_photos(item))
        elif isinstance(item, str) and item:
            result.append(item)
    return result


def save_gym_image(image_file) -> str:

    """Save uploaded image to media/gym_images/ and return relative path"""

    ext = os.path.splitext(image_file.name)[1]

    filename = f"{uuid.uuid4().hex}{ext}"

    upload_dir = os.path.join(settings.MEDIA_ROOT, "gym_images")

    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb+") as f:

        for chunk in image_file.chunks():

            f.write(chunk)

    return f"gym_images/{filename}"





def get_owner_from_token(request):

    """Extract owner_id from JWT token in Authorization header"""

    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):

        return None

    token = auth_header.split(" ")[1]

    try:

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])

        return payload.get("owner_id")

    except jwt.ExpiredSignatureError:

        return None

    except jwt.DecodeError:

        return None





def gym_response(gym_doc: dict) -> dict:

    """Format gym document for API response"""

    if not gym_doc:

        return {}

    gym_doc = dict(gym_doc)

    if "_id" in gym_doc:

        gym_doc["_id"] = str(gym_doc["_id"])

    if "owner_id" in gym_doc:

        gym_doc["owner_id"] = str(gym_doc["owner_id"])

    # Flatten photos array
    if "photos" in gym_doc:
        gym_doc["photos"] = flatten_photos(gym_doc.get("photos", []))

    # Ensure plans is a proper array
    if "plans" in gym_doc:
        plans = gym_doc["plans"]
        # If plans is a string, try to parse it
        if isinstance(plans, str):
            try:
                import json
                gym_doc["plans"] = json.loads(plans)
            except:
                gym_doc["plans"] = []
        # If plans is not a list, make it an empty list
        elif not isinstance(plans, list):
            gym_doc["plans"] = []
        # If plans is a list but contains string elements, try to parse them
        elif isinstance(plans, list) and len(plans) > 0:
            if isinstance(plans[0], str):
                try:
                    import json
                    gym_doc["plans"] = json.loads(plans[0])
                except:
                    gym_doc["plans"] = []

    # Ensure gym_classification is a proper array
    if "gym_classification" in gym_doc:
        classification = gym_doc["gym_classification"]
        
        # If it's a string, try to parse it as JSON
        if isinstance(classification, str):
            try:
                import json
                gym_doc["gym_classification"] = json.loads(classification)
            except Exception:
                # If parsing fails, treat it as a single-item array
                gym_doc["gym_classification"] = [classification] if classification else []
        # If it's not a list, make it an empty list
        elif not isinstance(classification, list):
            gym_doc["gym_classification"] = []
        # If it's a list but contains a JSON string as first element, parse it
        elif isinstance(classification, list) and len(classification) > 0:
            if isinstance(classification[0], str):
                try:
                    import json
                    parsed = json.loads(classification[0])
                    if isinstance(parsed, list):
                        gym_doc["gym_classification"] = parsed
                    else:
                        gym_doc["gym_classification"] = classification
                except Exception:
                    gym_doc["gym_classification"] = classification
        # Ensure it's a list
        else:
            gym_doc["gym_classification"] = classification

    # Convert datetime objects to ISO strings

    for key in ("created_at", "updated_at"):

        if key in gym_doc and gym_doc[key]:

            gym_doc[key] = gym_doc[key].isoformat()

    return gym_doc





@method_decorator(csrf_exempt, name="dispatch")

class CreateGymView(APIView):

    """

    POST /api/org/gym/create/

    Body (multipart/form-data): gym_name, location, address, phone_number, email,

    description, image (file), amenities (JSON string or repeated), price_range

    """

    authentication_classes = []

    permission_classes = [AllowAny]

    parser_classes = [MultiPartParser, FormParser, JSONParser]



    def post(self, request):

        owner_id = get_owner_from_token(request)

        if not owner_id:

            return Response(

                {"error": "Authentication required"},

                status=status.HTTP_401_UNAUTHORIZED,

            )



        data = request.data



        # Validate required fields

        if not data.get("gym_name"):

            return Response(

                {"error": "gym_name is required"},

                status=status.HTTP_400_BAD_REQUEST,

            )



        # Handle main image upload

        image_url = None

        image_file = request.FILES.get("image")

        if image_file:

            relative_path = save_gym_image(image_file)

            image_url = f"{settings.MEDIA_URL}{relative_path}"



        # Handle multiple photos upload

        photos = []

        photo_files = request.FILES.getlist("photos")

        for pf in photo_files:

            rel = save_gym_image(pf)

            photos.append(f"{settings.MEDIA_URL}{rel}")



        # Parse amenities — could be JSON string or list from form-data

        amenities = data.get("amenities", [])

        if isinstance(amenities, str):

            import json

            try:

                amenities = json.loads(amenities)

            except (json.JSONDecodeError, ValueError):

                amenities = [a.strip() for a in amenities.split(",") if a.strip()]

        # Parse gym_classification — could be JSON string or list from form-data

        gym_classification = data.get("gym_classification", [])

        if isinstance(gym_classification, str):

            import json

            try:

                gym_classification = json.loads(gym_classification)

            except (json.JSONDecodeError, ValueError):

                gym_classification = [c.strip() for c in gym_classification.split(",") if c.strip()]

        # Parse plans if provided
        plans = data.get("plans", [])
        if isinstance(plans, str):
            import json
            try:
                plans = json.loads(plans)
            except (json.JSONDecodeError, ValueError):
                plans = []

        # Create gym document using schema

        gym_doc = GymSchema.create_gym(

            owner_id=owner_id,

            gym_name=data["gym_name"],

            location=data.get("location", ""),

            address=data.get("address", ""),

            phone_number=data.get("phone_number", ""),

            email=data.get("email") or None,

            description=data.get("description") or None,

            image_url=image_url,

            amenities=amenities,

            gym_classification=gym_classification,

            price_range=data.get("price_range") or None,

            website=data.get("website") or None,

            morning_open=data.get("morning_open") or None,

            morning_close=data.get("morning_close") or None,

            evening_open=data.get("evening_open") or None,

            evening_close=data.get("evening_close") or None,

        )
        
        # Add plans to gym document
        if plans:
            gym_doc["plans"] = plans

        if photos:

            gym_doc["photos"] = photos



        result = org_gym_collection.insert_one(gym_doc)

        gym_id = str(result.inserted_id)



        # Update owner's gyms array and total_gyms count

        org_collection.update_one(

            {"_id": ObjectId(owner_id)},

            {

                "$push": {"gyms": gym_id},

                "$inc": {"total_gyms": 1},

                "$set": {"updated_at": timezone.now()},

            },

        )



        gym_doc["_id"] = gym_id

        return Response(

            {"message": "Gym created successfully", "gym": gym_response(gym_doc)},

            status=status.HTTP_201_CREATED,

        )





@method_decorator(csrf_exempt, name="dispatch")

class ListGymsView(APIView):

    """

    GET /api/org/gym/list/

    Returns all gyms for the authenticated owner

    """

    authentication_classes = []

    permission_classes = [AllowAny]



    def get(self, request):

        owner_id = get_owner_from_token(request)

        if not owner_id:

            return Response(

                {"error": "Authentication required"},

                status=status.HTTP_401_UNAUTHORIZED,

            )



        gyms_cursor = org_gym_collection.find(

            {"owner_id": owner_id}

        ).sort("created_at", -1)



        gyms = [gym_response(g) for g in gyms_cursor]



        return Response({"gyms": gyms}, status=status.HTTP_200_OK)





@method_decorator(csrf_exempt, name="dispatch")

class GetGymView(APIView):

    """

    GET /api/org/gym/<gym_id>/

    Returns a single gym by ID

    """

    authentication_classes = []

    permission_classes = [AllowAny]



    def get(self, request, gym_id):

        try:

            gym = org_gym_collection.find_one({"_id": ObjectId(gym_id)})

        except Exception:

            return Response(

                {"error": "Invalid gym ID"},

                status=status.HTTP_400_BAD_REQUEST,

            )



        if not gym:

            return Response(

                {"error": "Gym not found"},

                status=status.HTTP_404_NOT_FOUND,

            )



        return Response({"gym": gym_response(gym)}, status=status.HTTP_200_OK)





@method_decorator(csrf_exempt, name="dispatch")

class UpdateGymView(APIView):

    """

    PUT /api/org/gym/update/<gym_id>/

    Body (multipart/form-data): any gym fields to update, image (file)

    """

    authentication_classes = []

    permission_classes = [AllowAny]

    parser_classes = [MultiPartParser, FormParser, JSONParser]



    def put(self, request, gym_id):

        owner_id = get_owner_from_token(request)

        if not owner_id:

            return Response(

                {"error": "Authentication required"},

                status=status.HTTP_401_UNAUTHORIZED,

            )



        try:

            gym = org_gym_collection.find_one({"_id": ObjectId(gym_id)})

        except Exception:

            return Response(

                {"error": "Invalid gym ID"},

                status=status.HTTP_400_BAD_REQUEST,

            )



        if not gym:

            return Response(

                {"error": "Gym not found"},

                status=status.HTTP_404_NOT_FOUND,

            )



        # Verify ownership

        if gym.get("owner_id") != owner_id:

            return Response(

                {"error": "You don't have permission to update this gym"},

                status=status.HTTP_403_FORBIDDEN,

            )



        data = request.data



        # Handle main image upload

        image_file = request.FILES.get("image")

        if image_file:

            # Delete old image file if exists

            old_url = gym.get("image_url", "")

            if old_url:

                old_path = os.path.join(settings.MEDIA_ROOT, old_url.replace(settings.MEDIA_URL, ""))

                if os.path.exists(old_path):

                    os.remove(old_path)

            relative_path = save_gym_image(image_file)

            data = dict(data)

            data["image_url"] = f"{settings.MEDIA_URL}{relative_path}"



        # Handle multiple photos upload

        photo_files = request.FILES.getlist("photos")

        if photo_files:

            existing_photos = flatten_photos(gym.get("photos", []))

            new_photos = []

            for pf in photo_files:

                rel = save_gym_image(pf)

                new_photos.append(f"{settings.MEDIA_URL}{rel}")

            data = dict(data) if not isinstance(data, dict) else data

            data["photos"] = existing_photos + new_photos



        # Handle photo removal

        import json as json_mod

        remove_photos_raw = data.get("remove_photos")

        if remove_photos_raw:

            if isinstance(remove_photos_raw, str):

                try:

                    remove_photos = json_mod.loads(remove_photos_raw)

                except (json_mod.JSONDecodeError, ValueError):

                    remove_photos = []

            else:

                remove_photos = list(remove_photos_raw)

            current_photos = flatten_photos(data.get("photos", gym.get("photos", [])))

            data = dict(data) if not isinstance(data, dict) else data

            data["photos"] = [p for p in current_photos if p not in remove_photos]

            # Delete removed photo files from disk

            for rp in remove_photos:

                rp_path = os.path.join(settings.MEDIA_ROOT, rp.replace(settings.MEDIA_URL, ""))

                if os.path.exists(rp_path):

                    os.remove(rp_path)



        # Parse amenities

        if "amenities" in data:

            amenities = data["amenities"]

            if isinstance(amenities, str):

                import json

                try:

                    amenities = json.loads(amenities)

                except (json.JSONDecodeError, ValueError):

                    amenities = [a.strip() for a in amenities.split(",") if a.strip()]

            data = dict(data)

            data["amenities"] = amenities

        # Parse gym_classification

        if "gym_classification" in data:

            gym_classification = data["gym_classification"]

            if isinstance(gym_classification, str):

                import json

                try:

                    gym_classification = json.loads(gym_classification)

                except (json.JSONDecodeError, ValueError):

                    gym_classification = [c.strip() for c in gym_classification.split(",") if c.strip()]

            data = dict(data)

            data["gym_classification"] = gym_classification



        # Parse plans if provided
        print(f"DEBUG: All data keys: {list(data.keys())}")
        if "plans" in data:
            print(f"DEBUG: Plans received in request: {data['plans']}")
            print(f"DEBUG: Plans type: {type(data['plans'])}")
            data = dict(data) if not isinstance(data, dict) else data
            if isinstance(data["plans"], str):
                try:
                    import json
                    parsed_plans = json.loads(data["plans"])
                    print(f"DEBUG: Plans after parsing: {parsed_plans}")
                    print(f"DEBUG: Plans type after parsing: {type(parsed_plans)}")
                    # Ensure it's a list, not a string or other type
                    if isinstance(parsed_plans, list):
                        data["plans"] = parsed_plans
                        print(f"DEBUG: Plans set to list with {len(parsed_plans)} items")
                    else:
                        print(f"ERROR: Parsed plans is not a list, it's {type(parsed_plans)}")
                        data["plans"] = []
                except Exception as e:
                    print(f"ERROR: Error parsing plans: {e}")
                    data["plans"] = []
            elif isinstance(data["plans"], list):
                print(f"DEBUG: Plans already a list with {len(data['plans'])} items")
            else:
                print(f"WARNING: Plans is neither string nor list, type: {type(data['plans'])}")
                data["plans"] = []
        else:
            print("DEBUG: No plans field in request data")

        # Only allow updating specific fields

        allowed_fields = [

            "gym_name", "location", "address", "phone_number", "email",

            "description", "image_url", "photos", "amenities", "gym_classification", "price_range",

            "status", "timings", "website", "morning_open", "morning_close", "evening_open", "evening_close", "plans",

        ]

        update_data = {k: v for k, v in data.items() if k in allowed_fields}
        
        print(f"DEBUG: update_data keys: {list(update_data.keys())}")
        if "plans" in update_data:
            print(f"DEBUG: Plans in update_data: {update_data['plans']}")
        else:
            print("DEBUG: Plans NOT in update_data!")

        update_data["updated_at"] = timezone.now()



        org_gym_collection.update_one(

            {"_id": ObjectId(gym_id)},

            {"$set": update_data},

        )



        updated_gym = org_gym_collection.find_one({"_id": ObjectId(gym_id)})

        return Response(

            {"message": "Gym updated successfully", "gym": gym_response(updated_gym)},

            status=status.HTTP_200_OK,

        )





@method_decorator(csrf_exempt, name="dispatch")

class DeleteGymView(APIView):

    """

    DELETE /api/org/gym/delete/<gym_id>/

    """

    authentication_classes = []

    permission_classes = [AllowAny]



    def delete(self, request, gym_id):

        owner_id = get_owner_from_token(request)

        if not owner_id:

            return Response(

                {"error": "Authentication required"},

                status=status.HTTP_401_UNAUTHORIZED,

            )



        try:

            gym = org_gym_collection.find_one({"_id": ObjectId(gym_id)})

        except Exception:

            return Response(

                {"error": "Invalid gym ID"},

                status=status.HTTP_400_BAD_REQUEST,

            )



        if not gym:

            return Response(

                {"error": "Gym not found"},

                status=status.HTTP_404_NOT_FOUND,

            )



        # Verify ownership

        if gym.get("owner_id") != owner_id:

            return Response(

                {"error": "You don't have permission to delete this gym"},

                status=status.HTTP_403_FORBIDDEN,

            )



        org_gym_collection.delete_one({"_id": ObjectId(gym_id)})



        # Update owner's gyms array and total_gyms count

        org_collection.update_one(

            {"_id": ObjectId(owner_id)},

            {

                "$pull": {"gyms": gym_id},

                "$inc": {"total_gyms": -1},

                "$set": {"updated_at": timezone.now()},

            },

        )



        return Response(

            {"message": "Gym deleted successfully"},

            status=status.HTTP_200_OK,

        )





@method_decorator(csrf_exempt, name="dispatch")

class PublicListGymsView(APIView):

    """

    GET /api/org/gym/public/list/

    Returns all active/verified gyms — no auth required.

    """

    authentication_classes = []

    permission_classes = [AllowAny]



    def get(self, request):

        gyms_cursor = org_gym_collection.find(

            {"status": "active"}

        ).sort("created_at", -1)



        gyms = []

        for g in gyms_cursor:

            gd = gym_response(g)

            # Attach owner name

            owner_id = g.get("owner_id")

            if owner_id:

                try:

                    owner = org_collection.find_one({"_id": ObjectId(owner_id)})

                    gd["owner_name"] = owner.get("full_name", "") if owner else ""

                except Exception:

                    gd["owner_name"] = ""

            else:

                gd["owner_name"] = ""

            gyms.append(gd)



        return Response({"gyms": gyms}, status=status.HTTP_200_OK)





@method_decorator(csrf_exempt, name="dispatch")

class PublicGymDetailView(APIView):

    """

    GET /api/org/gym/public/<gym_id>/

    Returns a single active gym with owner info — no auth required.

    """

    authentication_classes = []

    permission_classes = [AllowAny]



    def get(self, request, gym_id):

        try:

            gym = org_gym_collection.find_one({"_id": ObjectId(gym_id)})

        except Exception:

            return Response(

                {"error": "Invalid gym ID"},

                status=status.HTTP_400_BAD_REQUEST,

            )



        if not gym:

            return Response(

                {"error": "Gym not found"},

                status=status.HTTP_404_NOT_FOUND,

            )



        gd = gym_response(gym)



        # Attach owner info

        owner_id = gym.get("owner_id")

        if owner_id:

            try:

                owner = org_collection.find_one({"_id": ObjectId(owner_id)})

                if owner:

                    gd["owner_name"] = owner.get("full_name", "")

                    gd["owner_email"] = owner.get("email", "")

                else:

                    gd["owner_name"] = ""

                    gd["owner_email"] = ""

            except Exception:

                gd["owner_name"] = ""

                gd["owner_email"] = ""

        else:

            gd["owner_name"] = ""

            gd["owner_email"] = ""



        # Increment view count

        org_gym_collection.update_one(

            {"_id": ObjectId(gym_id)},

            {"$inc": {"views_count": 1}},

        )



        return Response({"gym": gd}, status=status.HTTP_200_OK)

