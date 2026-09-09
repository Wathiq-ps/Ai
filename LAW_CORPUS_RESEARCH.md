# Palestinian real-estate law — corpus sourcing study

> Background research (2026-09-08) into which statutes govern real-estate
> contracts in Palestine and where their text can be obtained. Findings are
> web-sourced and **not legally reviewed** — every claim below should be
> confirmed by a Palestinian lawyer before it is used as the basis for
> citations in generated contracts.

## Headline: the two starting assumptions

| Assumption | Verdict |
|---|---|
| The governing law dates from ~1934 | **Mostly wrong, but explicable.** No 1934 statute governs property. "1934" is almost certainly Drayton's *Laws of Palestine, Revised Edition* — the official consolidation of Mandate law in force at 31 Dec 1933, published 1934. That is a **compilation**, not a property statute. The substantive stack is Ottoman (1858, 1913) + Mandate ordinances (1920–1947) + Jordanian/Egyptian layers. |
| One uniform body of law applies to all of Palestine | **Wrong — and this is the load-bearing finding.** For four of the five subject areas, the West Bank and Gaza apply **different statutes, with different numbers and different text.** Only the general contract layer is genuinely common. |

### Evidence for the divergence

Presidential Decision No. 1 of 1994 froze in place the laws in force in each
area before 5 June 1967 **"حتى يتم توحيدها"** — until unified. They were never
unified.

The clearest proof is that the two Land Authorities publish near-**disjoint**
lists of the laws they administer:

- **Gaza PLA** (`pla.gov.ps`): Ottoman Land Code, Ottoman Disposal of Immovable
  Property Law, Land Transfer Law (+ 1937/38/39/43/47 amendments), Land
  Settlement of Title Ordinance 9/1928, Survey Law 1929 — Ottoman + Mandate,
  plus Egyptian-era (1954–1966) and Gaza-issued PA-era acts.
- **Ramallah PLA** (`pla.pna.ps`): Land and Water Settlement Law 40/1952,
  Disposal of Immovable Property Law 49/1953, Registration of Immovable
  Property Law 6/1964, Land Registration Fees Law 26/1964, Buildings and Land
  Tax Law 11/1954 — an almost entirely **Jordanian 1952–1967** corpus.

The sharpest single example: the West Bank's Law 49/1953 **expressly repealed**
(art. 18) the Ottoman 1913 law that Gaza still applies today.

## Per-area split

| Area | West Bank | Gaza |
|---|---|---|
| Sale of immovable property | قانون التصرف في الأموال غير المنقولة رقم (49) لسنة 1953 (Jordanian) | قانون التصرف بالأموال غير المنقولة (العثماني) 1331هـ / 1913 |
| Lease / rent | قانون المالكين والمستأجرين رقم (62) لسنة 1953, as amended (incl. قرار بقانون 35/2022) | قانون إيجار العقارات رقم (5) لسنة 2013 (Gaza-seated PLC) |
| Ownership / registration | Ottoman Land Code 1858 substrate + Jordanian 40/1952, 6/1964, 51/1958, 41/1953 | Ottoman Land Code 1858 substrate + Mandate 9/1928, Land Transfer Law, Survey Law 1929 |
| Tax and fees | قانون ضريبة الأبنية والأراضي رقم (11) لسنة 1954; قانون ضريبة الأراضي 30/1955 | قانون ضريبة الأملاك داخل المدن رقم 42 لسنة 1940 (Mandate) |
| General contract law | **مجلة الأحكام العدلية (1876), 1,851 articles — common to both** | same |

The Majalla is the one uniform layer. The Jordanian Civil Code 43/1976 does
**not** extend to the West Bank (enacted after Jordan's 1967 disengagement), and
the مشروع القانون المدني الفلسطيني has never been enacted. So general sale
(البيع) and lease (الإجارة) rules come from the Majalla in both territories.

## Where the text lives

| Source | Operator | Official? | Format | Amendments | WB/GZ tag | Verdict |
|---|---|---|---|---|---|---|
| `mjr.ogb.gov.ps` | ديوان الجريدة الرسمية (Ramallah) | **Yes** — official DB by Cabinet Decision 1/2022 | HTML, clean Arabic, **consolidated** | Inline + footnotes | No | **Primary** |
| `maqam.najah.edu` | An-Najah University, Law College | Authoritative-secondary | HTML, **per-article URLs** | Per-law list | **Yes** | **Secondary / schema donor** |
| `muqtafi.birzeit.edu` | Birzeit Institute of Law | Authoritative-secondary | HTML full text | Partial | Partial | Backup — see obstacles |
| `pla.gov.ps` / `pla.pna.ps` | Palestinian Land Authority ×2 | Official | **PDF only** | No | Implicit | Authority for *which* laws apply, not for text |
| `dftp.gov.ps` | ديوان الفتوى والتشريع | Official | Gazette archive | Status facet نافذ/معدل/ملغى | Era facet | Gap-filler, esp. Gaza |
| `qistas.com` | Commercial | No | **Paywalled**, truncated | — | — | Reject |

Recommended starting document (consolidated, article 1 verbatim available):
`https://mjr.ogb.gov.ps/MergedLegislations/ViewText/119` — قانون المالكين
والمستأجرين رقم (62) لسنة 1953.

Maqam's per-article URLs (`/legislation/{law}/item/{article}/`) map directly
onto our article-citation schema, and it carries an explicit applicability tag
(`ساري النفاذ في الضفة الغربية`) that MJR lacks.

## Establishing effective dates

Two gazettes, not one: الوقائع الفلسطينية issued in Ramallah (indexed at
`mjr.ogb.gov.ps`, ~8,700 legislations) and a **separate** الوقائع الفلسطينية
issued in Gaza carrying post-2007 Gaza legislation.

Practical rule for the pipeline:

- `effective_from` — from the statute's own commencement article (nearly all
  say *"يعمل به من تاريخ نشره في الجريدة الرسمية"*) plus the gazette issue date.
- `effective_to` — only from an express repeal in a later instrument.
- **Never** infer currency from a database merely carrying a text. MJR and
  Maqam both hold repealed and superseded instruments. Cross-check against the
  `dftp.gov.ps` status facet **and** the relevant Land Authority's published
  list.

## Obstacles that affect the loader

1. **Birzeit's Muqtafi is HTTP-only** — every `*.birzeit.edu` host refused TLS
   on 443. Any fetcher that force-upgrades to HTTPS sees the site as dead.
   Newest visible items are 2020–2021, so currency is questionable.
2. **MJR returns 403 to non-browser user agents.** Needs a realistic UA and
   respectful rate limiting.
3. **Post-2007 Gaza legislation is largely absent from the West Bank
   databases.** Gaza's Law 5/2013 returned no hit in Maqam, Muqtafi or MJR;
   only a university faculty page and a journal article carried it. `plc.gov.ps`
   failed DNS resolution during the study.
4. **Both Land Authorities publish PDF only** — no article structure, text
   layer unverified, and the Gaza PDFs are Mandate/Ottoman-era documents most
   likely to be **scans requiring OCR**. Filenames are unpunctuated Arabic with
   inconsistent spacing, so title parsing needs normalisation.
5. **Inconsistent numbering in secondary sources** — قانون رسوم تسجيل الأراضي
   رقم 26 is cited as both 1958 and 1964. Resolve numbers against the gazette,
   never a secondary source.
6. **No terms-of-use clause was located** on MJR, Maqam or Muqtafi. The
   statutory text itself is uncopyrightable legal material; any restriction
   would attach to the *database layer* (consolidation notes, article IDs,
   judgment cross-links). Store the primary text, treat Maqam's article IDs as
   internal keys only, and get written clearance before redistributing anyone's
   consolidation apparatus.

## Open questions

- Gaza's counterparts for **notarisation** and **land-registration fees** —
  not established.
- Whether the Ottoman Land Code 1858 is formally repealed or merely displaced
  in the West Bank by the 1952–1964 Jordanian suite.
- Provenance of قانون ضريبة بيع العقار رقم 21 لسنة 1974 in the West Bank.
- Legal status of Gaza PLC statutes (2013, 2015, 2017) before Ramallah-based
  courts — they were passed by a rump PLC during the political split. Affects
  whether the system cites them as authority or flags them as contested.
- **East Jerusalem** is outside this study entirely; Israeli land law applies
  there in practice. Must be treated as a third jurisdiction or excluded
  explicitly.

## Feasibility

A usable machine-readable corpus **does exist for the West Bank** — official,
free, consolidated, article-addressable.

**For Gaza it largely does not.** The Gaza half should be planned as a
manual/OCR collection effort against PDF sources, not an automated ingest.
