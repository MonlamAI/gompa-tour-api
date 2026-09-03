from fastapi import APIRouter, HTTPException, Depends
from prisma import Prisma
from typing import List
from Config.connection import get_db
from model.language import LanguageBase
from lib.require_api_key import require_api_key

router = APIRouter(
)

@router.post("/", response_model=LanguageBase, dependencies=[Depends(require_api_key)])
async def create_language(language: LanguageBase, db: Prisma = Depends(get_db)):
    try:
        created_language = await db.language.create(
            data={
                "code": language.code,
                "name": language.name
            }
        )
        return created_language
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[LanguageBase])
async def get_languages(db: Prisma = Depends(get_db)):
    return await db.language.find_many()

@router.delete("/{language_code}", response_model=LanguageBase, dependencies=[Depends(require_api_key)])
async def delete_language(language_code: str, db: Prisma = Depends(get_db)):
    try:
        # Find the language before deleting
        language = await db.language.find_first(where={"code": language_code})

        if not language:
            raise HTTPException(status_code=404, detail="Language not found")

        # Delete the language
        await db.language.delete(where={"code": language_code})

        return language  # Return the deleted language
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))