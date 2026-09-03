from fastapi import HTTPException
from prisma import Prisma


async def assert_languages_exist(db: Prisma, language_codes) -> None:
    """Fail before any write if a payload locale is not in the Language table."""
    codes = sorted({code for code in language_codes if code})
    if not codes:
        return

    rows = await db.language.find_many(where={"code": {"in": codes}})
    found = {row.code for row in rows}
    missing = [code for code in codes if code not in found]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unknown language codes: "
                + ", ".join(missing)
                + ". Add them with POST /language before saving translations."
            ),
        )


def content_translation_fields(translation) -> dict:
    audio = getattr(translation, "description_audio", None)
    return {
        "name": translation.name,
        "description": translation.description,
        "description_audio": audio or "",
    }


def contact_translation_fields(translation) -> dict:
    return {
        "address": translation.address,
        "city": translation.city,
        "state": translation.state,
        "postal_code": translation.postal_code,
        "country": translation.country,
    }


async def upsert_translations(
    db: Prisma,
    table,
    *,
    parent_id_field: str,
    parent_id: str,
    parent_relation: str,
    translations,
    fields_of,
):
    """Create or update rows by (parent, language). Never deletes other locales."""
    if not translations:
        return

    await assert_languages_exist(db, [t.languageCode for t in translations])

    for translation in translations:
        code = translation.languageCode
        fields = fields_of(translation)
        existing = await table.find_first(
            where={
                parent_id_field: parent_id,
                "languageCode": code,
            }
        )
        if existing:
            await table.update(where={"id": existing.id}, data=fields)
        else:
            await table.create(
                data={
                    parent_relation: {"connect": {"id": parent_id}},
                    "language": {"connect": {"code": code}},
                    **fields,
                }
            )


async def upsert_content_translations(
    db: Prisma,
    table,
    *,
    parent_id_field: str,
    parent_id: str,
    parent_relation: str,
    translations,
):
    await upsert_translations(
        db,
        table,
        parent_id_field=parent_id_field,
        parent_id=parent_id,
        parent_relation=parent_relation,
        translations=translations,
        fields_of=content_translation_fields,
    )
