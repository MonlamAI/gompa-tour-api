from fastapi import APIRouter, HTTPException, Depends
from prisma import Prisma
from typing import Optional, List
from Config.connection import get_db
from model.festival import FestivalCreate,festivalTranslationCreate,FestivalTranslationUpdate,FestivalUpdate
from lib.upsert_translations import assert_languages_exist, upsert_content_translations
from lib.require_api_key import require_api_key

router = APIRouter()

@router.post("/", dependencies=[Depends(require_api_key)])
async def create_festival(festival: FestivalCreate, db: Prisma = Depends(get_db)):
    try:
        await assert_languages_exist(db, [t.languageCode for t in festival.translations])
        translations_data = [
            {
                "language": {"connect": {"code": t.languageCode}},
                "name": t.name,
                "description": t.description,
                "description_audio": t.description_audio
            }
            for t in festival.translations
        ]
        
        created_festival = await db.festival.create(
            data={
                "start_date": festival.start_date,
                "end_date": festival.end_date,
                "image": festival.image,
                "translations": {
                    "create": translations_data
                }
            },
            include={
                "translations": True
            }
        )
        return created_festival
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{festival_id}")
async def get_festival(festival_id: str, db: Prisma = Depends(get_db)):
    festival = await db.festival.find_first(
        where={"id": festival_id},
        include={"translations": True}
    )
    if not festival:
        raise HTTPException(status_code=404, detail="Festival not found")
    return festival

@router.get("/")
async def get_festivals(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Prisma = Depends(get_db)
):
    where = {}
    if start_date:
        where["start_date"] = {"gte": start_date}
    if end_date:
        where["end_date"] = {"lte": end_date}
    
    festivals = await db.festival.find_many(
        where=where,
        include={"translations": True}
    )
    return festivals

@router.post("/{festival_id}/translations", dependencies=[Depends(require_api_key)])
async def add_festival_translation(
    festival_id: str,
    translation: festivalTranslationCreate,
    db: Prisma = Depends(get_db)
):
    try:
        # Check if the gonpa exists
        existing_festival = await db.festival.find_first(where={"id": festival_id})
        if not existing_festival:
            raise HTTPException(status_code=404, detail="festival not found")

        await assert_languages_exist(db, [translation.languageCode])

        # Check if translation for this language already exists
        existing_translation = await db.festivaltranslation.find_first(
            where={
                "festivalId": festival_id,
                "languageCode": translation.languageCode
            }
        )
        if existing_translation:
            raise HTTPException(
                status_code=400,
                detail=f"Translation for language {translation.languageCode} already exists"
            )

        # Create new translation
        new_translation = await db.festivaltranslation.create(
            data={
                "festival": {"connect": {"id": festival_id}},
                "language": {"connect": {"code": translation.languageCode}},
                "name": translation.name,
                "description": translation.description,
                "description_audio": translation.description_audio
            }
        )
        return new_translation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{festival_id}/translations/{language_code}", dependencies=[Depends(require_api_key)])
async def delete_festival_translation(

    festival_id: str,
    language_code: str,
    db: Prisma = Depends(get_db)
):
    try:
        # Check if the translation exists
        existing_translation = await db.festivaltranslation.find_first(
            where={
                "festivalId": festival_id,
                "languageCode": language_code
            }
        )
        if not existing_translation:
            raise HTTPException(
                status_code=404,
                detail=f"Translation for language {language_code} not found"
            )

        # Get total translation count
        translation_count = await db.festivaltranslation.count(
            where={"festivalId": festival_id}
        )
        
        # Prevent deletion if it's the last translation
        if translation_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last translation. Gonpa must have at least one translation"
            )

        # Delete the translation
        deleted_translation = await db.festivaltranslation.delete(
            where={
                "languageCode":  language_code,
                "festivalId": festival_id

            }
        )
        return {
            "message": f"Translation for language {language_code} deleted successfully",
            "translation": deleted_translation
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.delete("/{fest_id}", dependencies=[Depends(require_api_key)])
async def delete_fest_site(fest_id: str, db: Prisma = Depends(get_db)):
    try:
        existing_gonpa = await db.festival.find_first(where={"id": fest_id})
        if not existing_gonpa:
            raise HTTPException(status_code=404, detail="festival not found")
            
        deleted_site = await db.festival.delete(
            where={"id": fest_id},
            include={
                "translations": True
            }
        )
        return {"message": "festival site deleted successfully", "site": deleted_site}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.put("/{festival_id}", dependencies=[Depends(require_api_key)])
async def update_festival(
    festival_id: str,
    festival_data: FestivalUpdate,
    db: Prisma = Depends(get_db)
):
    try:
        existing_festival = await db.festival.find_first(where={"id": festival_id})
        if not existing_festival:
            raise HTTPException(status_code=404, detail="Festival not found")

        await upsert_content_translations(
            db,
            db.festivaltranslation,
            parent_id_field="festivalId",
            parent_id=festival_id,
            parent_relation="festival",
            translations=festival_data.translations,
        )

        update_data = {}
        if festival_data.start_date:
            update_data["start_date"] = festival_data.start_date
        if festival_data.end_date:
            update_data["end_date"] = festival_data.end_date
        if festival_data.image:
            update_data["image"] = festival_data.image

        if update_data:
            await db.festival.update(
                where={"id": festival_id},
                data=update_data,
            )

        updated_festival = await db.festival.find_unique(
            where={"id": festival_id},
            include={"translations": True},
        )

        return {"message": "Festival updated successfully", "festival": updated_festival}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# @router.put("/{festival_id}/translations/{language_code}")
# async def update_festival_translation(
#     festival_id: str,
#     language_code: str,
#     translation_data: FestivalTranslationUpdate,
#     db: Prisma = Depends(get_db)
# ):
#     try:
#         # Check if translation exists
#         existing_translation = await db.festivaltranslation.find_first(
#             where={
#                 "festivalId": festival_id,
#                 "languageCode": language_code
#             }
#         )
#         if not existing_translation:
#             raise HTTPException(
#                 status_code=404,
#                 detail=f"Translation for language {language_code} not found"
#             )

#         # Prepare update data
#         update_data = {}
#         if translation_data.name:
#             update_data["name"] = translation_data.name
#         if translation_data.description:
#             update_data["description"] = translation_data.description
#         if translation_data.description_audio:
#             update_data["description_audio"] = translation_data.description_audio

#         # Update the translation
#         updated_translation = await db.festivaltranslation.update(
#             where={"id": existing_translation.id},
#             data=update_data
#         )

#         return {
#             "message": f"Translation for language {language_code} updated successfully",
#             "translation": updated_translation
#         }

#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

