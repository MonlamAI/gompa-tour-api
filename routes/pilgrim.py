from fastapi import APIRouter, HTTPException, Depends
from prisma import Prisma
from typing import Optional
from Config.connection import get_db
from typing import List
from model.pilgrim import PilgrimSiteCreate,PilgrimSiteTranslationCreate,PilgrimSiteUpdate
from lib.upsert_translations import assert_languages_exist, upsert_content_translations

router = APIRouter(
)

@router.post("/")
async def create_pilgrim_site(pilgrim_site: PilgrimSiteCreate, db: Prisma = Depends(get_db)):
    try:
        await assert_languages_exist(db, [t.languageCode for t in pilgrim_site.translations])
        translations_data = [
            {
                "language": {"connect": {"code": t.languageCode}},
                "name": t.name,
                "description": t.description,
                "description_audio": t.description_audio
            }
            for t in pilgrim_site.translations
        ]

        # Prepare the data dictionary
        site_data = {
            "image": pilgrim_site.image,
            "geo_location": pilgrim_site.geo_location,
            "translations": {"create": translations_data}
        }

        # ✅ Only include `contact` if `contactId` is provided
        if pilgrim_site.contactId:
            site_data["contact"] = {"connect": {"id": pilgrim_site.contactId}}

        # Create the Pilgrim Site
        created_site = await db.pilgrimsite.create(
            data=site_data,
            include={"translations": True, "contact": True}
        )

        return created_site

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{site_id}")
async def get_pilgrim_site(site_id: str, db: Prisma = Depends(get_db)):
    site = await db.pilgrimsite.find_first(
        where={"id": site_id},
        include={
            "translations": True,
            "contact": {
                "include": {
                    "translations": True
                }
            }
        }
    )
    if not site:
        raise HTTPException(status_code=404, detail="Pilgrim site not found")
    return site

@router.put("/{site_id}")
async def update_pilgrim_site(
    site_id: str, 
    site_update: PilgrimSiteUpdate, 
    db: Prisma = Depends(get_db)
):
    try:
        # Check if the Pilgrim Site exists
        existing_site = await db.pilgrimsite.find_first(where={"id": site_id})
        if not existing_site:
            raise HTTPException(status_code=404, detail="Pilgrim site not found")

        await upsert_content_translations(
            db,
            db.pilgrimsitetranslation,
            parent_id_field="pilgrimSiteId",
            parent_id=site_id,
            parent_relation="pilgrimSite",
            translations=site_update.translations,
        )

        update_data = {
            "image": site_update.image,
            "geo_location": site_update.geo_location,
        }
    
        if site_update.contactId:
            update_data["contact"] = {"connect": {"id": site_update.contactId}}

        await db.pilgrimsite.update(
            where={"id": site_id},
            data=update_data,
        )

        return await db.pilgrimsite.find_unique(
            where={"id": site_id},
            include={
                "translations": True,
                "contact": True
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/")
async def get_pilgrim_sites(db: Prisma = Depends(get_db)):
    sites = await db.pilgrimsite.find_many(
        include={
            "translations": True,
            "contact": {
                "include": {
                    "translations": True
                }
            }
        }
    )
    return sites 

@router.delete("/{site_id}")
async def delete_pilgrim_site(site_id: str, db: Prisma = Depends(get_db)):
    try:
        existing_site = await db.pilgrimsite.find_first(where={"id": site_id})
        if not existing_site:
            raise HTTPException(status_code=404, detail="Pilgrim site not found")
            
        deleted_site = await db.pilgrimsite.delete(
            where={"id": site_id},
            include={
                "translations": True
            }
        )
        return {"message": "Pilgrim site deleted successfully", "site": deleted_site}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.post("/{site_id}/translations")
async def add_pilgrim_site_translation(
    site_id: str,
    translation: PilgrimSiteTranslationCreate,
    db: Prisma = Depends(get_db)
):
    try:
        # Check if the pilgrim site exists
        existing_site = await db.pilgrimsite.find_first(where={"id": site_id})
        if not existing_site:
            raise HTTPException(status_code=404, detail="Pilgrim site not found")

        await assert_languages_exist(db, [translation.languageCode])
            
        # Check if translation for this language already exists
        existing_translation = await db.pilgrimsitetranslation.find_first(
            where={
                "pilgrimSiteId": site_id,
                "languageCode": translation.languageCode
            }
        )
        if existing_translation:
            raise HTTPException(
                status_code=400,
                detail=f"Translation for language {translation.languageCode} already exists"
            )

        # Create new translation
        new_translation = await db.pilgrimsitetranslation.create(
            data={
                "pilgrimSite": {"connect": {"id": site_id}},
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

@router.delete("/{site_id}/translations/{language_code}")
async def delete_pilgrim_site_translation(
    site_id: str,
    language_code: str,
    db: Prisma = Depends(get_db)
):
    try:
        # Check if the translation exists
        existing_translation = await db.pilgrimsitetranslation.find_first(
            where={
                "pilgrimSiteId": site_id,
                "languageCode": language_code
            }
        )
        if not existing_translation:
            raise HTTPException(
                status_code=404,
                detail=f"Translation for language {language_code} not found"
            )

        # Get total translation count
        translation_count = await db.pilgrimsitetranslation.count(
            where={"pilgrimSiteId": site_id}
        )
        
        # Prevent deletion if it's the last translation
        if translation_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last translation. Pilgrim site must have at least one translation"
            )

        # Delete the translation
        deleted_translation = await db.pilgrimsitetranslation.delete(
            where={
                "pilgrimSiteId_languageCode": {
                    "pilgrimSiteId": site_id,
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