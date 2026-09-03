from fastapi import APIRouter, HTTPException, Depends
from prisma import Prisma
from typing import Optional
from Config.connection import get_db
from typing import List
from model.gonpa import GonpaCreate,GonpaTranslationCreate,GonpaUpdate
from lib.upsert_translations import assert_languages_exist, upsert_content_translations
from lib.require_api_key import require_api_key
from model.enum import Sect, GonpaType

router = APIRouter(
)

@router.post("/", dependencies=[Depends(require_api_key)])
async def create_gonpa(gonpa: GonpaCreate, db: Prisma = Depends(get_db)):
    try:
        await assert_languages_exist(db, [t.languageCode for t in gonpa.translations])
        translations_data = [
            {
                "language": {"connect": {"code": t.languageCode}},
                "name": t.name,
                "description": t.description,
                "description_audio": t.description_audio
            }
            for t in gonpa.translations
        ]
        
        created_gonpa = await db.gonpa.create(
            data={
                "image": gonpa.image,
                "geo_location": gonpa.geo_location,
                "sect": gonpa.sect,
                "type": gonpa.type,
                "contact": {"connect": {"id": gonpa.contactId}},
                "translations": {
                    "create": translations_data
                }
            },
            include={
                "translations": True,
                "contact": True
            }
        )
        return created_gonpa
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/types",response_model=List[str])
async def get_gonpa_types():
    return [e.value for e in GonpaType]

@router.get("/sections",response_model=List[str])
async def get_gonpa_types():
    return [e.value for e in Sect]

@router.get("/types/{type}")
async def get_gonpa_type(type: GonpaType, db: Prisma = Depends(get_db)):
    return await db.gonpa.find_many(where={"type": type})

@router.get("/{gonpa_id}")
async def get_gonpa(gonpa_id: str, db: Prisma = Depends(get_db)):
    gonpa = await db.gonpa.find_first(
        where={"id": gonpa_id},
        include={
            "translations": True,
            "contact": {
                "include": {
                    "translations": True
                }
            }
        }
    )
    if not gonpa:
        raise HTTPException(status_code=404, detail="Gonpa not found")
    return gonpa


@router.put("/{gonpa_id}", dependencies=[Depends(require_api_key)])
async def update_gonpa(
    gonpa_id: str, 
    gonpa_update: GonpaUpdate, 
    db: Prisma = Depends(get_db)
):
    try:
        # Check if the Gonpa exists
        existing_gonpa = await db.gonpa.find_first(where={"id": gonpa_id})
        if not existing_gonpa:
            raise HTTPException(status_code=404, detail="Gonpa not found")

        await upsert_content_translations(
            db,
            db.gonpatranslation,
            parent_id_field="gonpaId",
            parent_id=gonpa_id,
            parent_relation="gonpa",
            translations=gonpa_update.translations,
        )

        update_data = {
            "image": gonpa_update.image,
            "geo_location": gonpa_update.geo_location,
            "sect": gonpa_update.sect,
            "type": gonpa_update.type,
        }

        if gonpa_update.contactId:
            update_data["contact"] = {"connect": {"id": gonpa_update.contactId}}

        await db.gonpa.update(
            where={"id": gonpa_id},
            data=update_data,
        )

        return await db.gonpa.find_unique(
            where={"id": gonpa_id},
            include={"translations": True, "contact": True},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/")
async def get_gonpas(
    sect: Optional[Sect] = None,
    type: Optional[GonpaType] = None,
    db: Prisma = Depends(get_db)
):
    where = {}
    if sect:
        where["sect"] = sect
    if type:
        where["type"] = type

    gonpas = await db.gonpa.find_many(
        where=where,
        include={
            "translations": True,
            "contact": {
                "include": {
                    "translations": True
                }
            }
        }
    )
    return gonpas



@router.post("/{gonpa_id}/translations", dependencies=[Depends(require_api_key)])
async def add_gonpa_translation(
    gonpa_id: str,
    translation: GonpaTranslationCreate,
    db: Prisma = Depends(get_db)
):
    try:
        # Check if the gonpa exists
        existing_gonpa = await db.gonpa.find_first(where={"id": gonpa_id})
        if not existing_gonpa:
            raise HTTPException(status_code=404, detail="Gonpa not found")

        await assert_languages_exist(db, [translation.languageCode])
            
        # Check if translation for this language already exists
        existing_translation = await db.gonpatranslation.find_first(
            where={
                "gonpaId": gonpa_id,
                "languageCode": translation.languageCode
            }
        )
        if existing_translation:
            raise HTTPException(
                status_code=400,
                detail=f"Translation for language {translation.languageCode} already exists"
            )

        # Create new translation
        new_translation = await db.gonpatranslation.create(
            data={
                "gonpa": {"connect": {"id": gonpa_id}},
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

@router.delete("/{gonpa_id}/translations/{language_code}", dependencies=[Depends(require_api_key)])
async def delete_gonpa_translation(

    gonpa_id: str,
    language_code: str,
    db: Prisma = Depends(get_db)
):
    try:
        # Check if the translation exists
        existing_translation = await db.gonpatranslation.find_first(
            where={
                "gonpaId": gonpa_id,
                "languageCode": language_code
            }
        )
        if not existing_translation:
            raise HTTPException(
                status_code=404,
                detail=f"Translation for language {language_code} not found"
            )

        # Get total translation count
        translation_count = await db.gonpatranslation.count(
            where={"gonpaId": gonpa_id}
        )
        
        # Prevent deletion if it's the last translation
        if translation_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last translation. Gonpa must have at least one translation"
            )

        # Delete the translation
        deleted_translation = await db.gonpatranslation.delete(
            where={
                "gonpaId_languageCode": {
                    "gonpaId": gonpa_id,
                    "languageCode": language_code
                }
            }
        )
        return {
            "message": f"Translation for language {language_code} deleted successfully",
            "translation": deleted_translation
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.delete("/{gonpa_id}", dependencies=[Depends(require_api_key)])
async def delete_gompa_site(gonpa_id: str, db: Prisma = Depends(get_db)):
    try:
        existing_gonpa = await db.gonpa.find_first(where={"id": gonpa_id})
        if not existing_gonpa:
            raise HTTPException(status_code=404, detail="Gonpa not found")
            
        deleted_site = await db.gonpa.delete(
            where={"id": gonpa_id},
            include={
                "translations": True
            }
        )
        return {"message": "Gonpa site deleted successfully", "site": deleted_site}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
