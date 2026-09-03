from fastapi import APIRouter, HTTPException, Depends
from prisma import Prisma
from model.contact import ContactBase,ContactUpdate
from Config.connection import get_db
from lib.require_api_key import require_api_key
from lib.upsert_translations import (
    assert_languages_exist,
    contact_translation_fields,
    upsert_translations,
)


router = APIRouter(
)

@router.post("/", dependencies=[Depends(require_api_key)])
async def create_contact(contact: ContactBase, db: Prisma = Depends(get_db)):
    try:
        await assert_languages_exist(db, [t.languageCode for t in contact.translations])
        translations_data = [
            {
                "language": {"connect": {"code": t.languageCode}},
                "address": t.address,
                "city": t.city,
                "state": t.state,
                "postal_code": t.postal_code,
                "country": t.country
            }
            for t in contact.translations
        ]
        
        created_contact = await db.contact.create(
            data={
                "email": contact.email,
                "phone_number": contact.phone_number,
                "translations": {
                    "create": translations_data
                }
            },
            include={
                "translations": True
            }
        )
        return created_contact
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{contact_id}")
async def get_contact(contact_id: str, db: Prisma = Depends(get_db)):
    contact = await db.contact.find_unique(
        where={"id": contact_id},
        include={"translations": True}
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.delete("/{contact_id}", dependencies=[Depends(require_api_key)])
async def get_contact(contact_id: str, db: Prisma = Depends(get_db)):
    contact = await db.contact.delete(
        where={"id": contact_id}
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.put("/{contact_id}", dependencies=[Depends(require_api_key)])
async def update_contact(contact_id: str, contact: ContactUpdate, db: Prisma = Depends(get_db)):
    existing_contact = await db.contact.find_unique(where={"id": contact_id})
    if not existing_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    try:
        await upsert_translations(
            db,
            db.contacttranslation,
            parent_id_field="contactId",
            parent_id=contact_id,
            parent_relation="contact",
            translations=contact.translations,
            fields_of=contact_translation_fields,
        )
        await db.contact.update(
            where={"id": contact_id},
            data={
                "email": contact.email,
                "phone_number": contact.phone_number,
            },
        )
        return await db.contact.find_unique(
            where={"id": contact_id},
            include={"translations": True},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))