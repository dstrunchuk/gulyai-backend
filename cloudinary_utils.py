import os
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

async def upload_to_cloudinary(file):
    result = cloudinary.uploader.upload(
        file.file,
        folder="gulyai_profiles",
        transformation=[
            {"width": 600, "height": 600, "crop": "limit", "quality": "auto"}
        ]
    )
    return result["secure_url"]