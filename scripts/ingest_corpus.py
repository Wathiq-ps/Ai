import asyncio
from datetime import date

import asyncpg

from app.config import settings
from app.document_loader import load_corpus_file
from app.knowledge import ingest_document

# Looked up by code, not hardcoded: a Back-end migrate:fresh reissues this row
# with a new uuid, and a stale literal silently ingests against nothing.
JUR_CODE = "PS"

# Provenance per SPRINT4_NEXT_STEPS.md's decision of record: name the actual
# West Bank instrument in publisher/citation/source_url instead of relabelling
# the PS jurisdiction row.
CORPUS = [
    dict(file="majalla-ahkam-adliyya.txt", law_type="general",
         title_ar="مجلة الأحكام العدلية", title_en="Mejelle (Ottoman Civil Code)",
         publisher="المكتبة الشاملة (تحقيق نجيب هواويني)",
         citation="مجلة الأحكام العدلية (1293هـ)",
         url="https://shamela.ws/book/8502", eff=date(1876, 1, 1)),
    dict(file="landlord-tenant-62-1953.txt", law_type="rent",
         title_ar="قانون المالكين والمستأجرين رقم (62) لسنة 1953",
         title_en="Landlord and Tenant Law No. 62 of 1953",
         publisher="ديوان الجريدة الرسمية - فلسطين",
         citation="قانون رقم (62) لسنة 1953 وتعديلاته",
         url="https://mjr.ogb.gov.ps/MergedLegislations/ViewText/119", eff=date(1953, 1, 1)),
    dict(file="buildings-land-tax-11-1954.txt", law_type="tax",
         title_ar="قانون ضريبة الأبنية والأراضي داخل مناطق البلديات والمجالس المحلية رقم (11) لسنة 1954",
         title_en="Buildings and Land Tax Law No. 11 of 1954",
         publisher="ديوان الجريدة الرسمية - فلسطين",
         citation="قانون رقم (11) لسنة 1954 وتعديلاته",
         url="https://mjr.ogb.gov.ps/MergedLegislations/ViewText/102", eff=date(1954, 4, 1)),
    dict(file="immovable-property-foreigners-40-1953.txt", law_type="ownership",
         title_ar="قانون إيجار وبيع الأموال غير المنقولة من الأجانب رقم (40) لسنة 1953",
         title_en="Lease and Sale of Immovable Property to Foreigners Law No. 40 of 1953",
         publisher="ديوان الجريدة الرسمية - فلسطين",
         citation="قانون رقم (40) لسنة 1953 وتعديلاته",
         url="https://mjr.ogb.gov.ps/MergedLegislations/ViewText/43", eff=date(1953, 1, 1)),
    # Sale of immovable property (2026-09-26). Jordanian-era West Bank laws are
    # not in MJR's consolidated set (PA-era only) nor dftp.gov.ps (its
    # Jordanian/Egyptian era is Gaza's Egyptian administration); An-Najah's
    # Maqam carries them, each tagged ساري النفاذ في الضفة الغربية. Text only,
    # Maqam's editorial article headings and case links left out.
    dict(file="immovable-property-disposal-49-1953.txt", law_type="sale",
         title_ar="قانون التصرف في الأموال غير المنقولة رقم (49) لسنة 1953",
         title_en="Disposal of Immovable Property Law No. 49 of 1953",
         publisher="موسوعة مقام - كلية القانون، جامعة النجاح الوطنية",
         citation="قانون رقم (49) لسنة 1953",
         url="https://maqam.najah.edu/legislation/59/", eff=date(1953, 1, 1)),
    dict(file="immovable-property-amendments-51-1958.txt", law_type="sale",
         title_ar="قانون معدل للأحكام المتعلقة بالأموال غير المنقولة رقم (51) لسنة 1958",
         title_en="Law Amending the Provisions on Immovable Property No. 51 of 1958",
         publisher="موسوعة مقام - كلية القانون، جامعة النجاح الوطنية",
         citation="قانون رقم (51) لسنة 1958",
         url="https://maqam.najah.edu/legislation/159/", eff=date(1958, 1, 1)),
    dict(file="immovable-property-debt-security-46-1953.txt", law_type="sale",
         title_ar="قانون وضع الأموال غير المنقولة تأميناً للدين رقم (46) لسنة 1953",
         title_en="Immovable Property as Security for Debt Law No. 46 of 1953",
         publisher="موسوعة مقام - كلية القانون، جامعة النجاح الوطنية",
         citation="قانون رقم (46) لسنة 1953",
         url="https://maqam.najah.edu/legislation/44/", eff=date(1953, 1, 1)),
    dict(file="unregistered-property-registration-6-1964.txt", law_type="ownership",
         title_ar="قانون تسجيل الأموال غير المنقولة التي لم يسبق تسجيلها رقم (6) لسنة 1964",
         title_en="Registration of Previously Unregistered Immovable Property Law No. 6 of 1964",
         publisher="موسوعة مقام - كلية القانون، جامعة النجاح الوطنية",
         citation="قانون رقم (6) لسنة 1964",
         url="https://maqam.najah.edu/legislation/46/", eff=date(1964, 1, 1)),
    dict(file="land-registration-regulation-1-1953.txt", law_type="ownership",
         title_ar="نظام تسجيل الأراضي رقم (1) لسنة 1953",
         title_en="Land Registration Regulation No. 1 of 1953",
         publisher="موسوعة مقام - كلية القانون، جامعة النجاح الوطنية",
         citation="نظام رقم (1) لسنة 1953",
         url="https://maqam.najah.edu/legislation/1190/", eff=date(1953, 1, 1)),
]


async def main():
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)
    async with pool.acquire() as c:
        JUR = await c.fetchval("select id from app.jurisdictions where code=$1", JUR_CODE)
        if JUR is None:
            raise SystemExit(f"no jurisdiction {JUR_CODE!r} — is the Back-end migrated/seeded?")
        print(f"jurisdiction {JUR_CODE} = {JUR}")
        for e in CORPUS:
            text, raw_path = load_corpus_file(e["file"])
            sid = await c.fetchval(
                "select id from knowledge.sources where jurisdiction_id=$1 and title_ar=$2", JUR, e["title_ar"])
            if sid:
                print(f"source exists  {e['file']}  {sid}")
            else:
                sid = await c.fetchval("""
                    insert into knowledge.sources
                      (jurisdiction_id, law_type, title_ar, title_en, publisher, citation, source_url,
                       effective_from, is_verified)
                    values ($1,$2::app.law_type,$3,$4,$5,$6,$7,$8,false) returning id""",
                    JUR, e["law_type"], e["title_ar"], e["title_en"], e["publisher"],
                    e["citation"], e["url"], e["eff"])
                print(f"source created {e['file']}  {sid}")
            doc_id = await ingest_document(pool, source_id=sid, title=e["title_en"],
                                           raw_text=text, raw_path=raw_path)
            print(f"   document {doc_id}  chars={len(text)}  raw_path={raw_path}")
    await pool.close()

asyncio.run(main())
