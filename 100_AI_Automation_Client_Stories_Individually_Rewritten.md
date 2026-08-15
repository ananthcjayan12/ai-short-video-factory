# **100 AI Automation Client-Story Scripts**

**Individually rewritten: Narration \+ Backend \+ Viewer DIY**

| Important storytelling note: These scripts are based on validated public pain-point research, not 100 verified paid-client engagements. The narration uses a client-case style. Until a case is genuinely yours, say 'the client in this example', 'a business we studied', or 'here is how I would solve this for a client'. Replace it with 'one of our clients' only when that is factually true. |
| :---- |

**Creative rule used in this version:** Each entry was treated as a separate problem. The AI capability, backend architecture, DIY stack, story opening, pacing and payoff were varied based on the actual workflow. AI handles ambiguity; normal code handles exact steps; humans keep control of high-impact exceptions.

# **Contractor / Handyman**

## **PAIN-001 — Context-aware receipt-to-job matcher**

**Pain: Materials from multiple suppliers end up charged to the wrong job.**

### **Narration**

The client in this example was a owner / gc in contractor / handyman, and the problem looked almost too small to automate: materials from multiple suppliers end up charged to the wrong job. When we watched the workflow, crew buys from several suppliers; owner later tries to remember which purchase belonged to which active project. We did not replace their main software. We built a context-aware receipt-to-job matcher. In the background, A vision model reads each receipt. A second reasoning step looks at the crew member, work schedule, supplier, purchased items and recent job history. Deterministic rules accept high-confidence matches; ambiguous purchases are sent back as one short question. The important part is that AI is only handling the messy interpretation; anything exact is handled by normal code, and uncertain cases stay with a person. The result was simple: the owner stops checking every receipt and only answers the handful the system cannot place confidently. If I were building the first version today, I would prove this with sample data first, then connect the real systems only after the team trusts the decisions. That is usually how a useful AI integration should start: one painful workflow, one measurable exception queue, and no unnecessary new platform.

### **Backend — what we actually built**

* A vision model reads each receipt.  
* A second reasoning step looks at the crew member, work schedule, supplier, purchased items and recent job history.  
* Deterministic rules accept high-confidence matches; ambiguous purchases are sent back as one short question.

### **Viewer DIY — easiest version to build**

**Suggested stack:** WhatsApp/Telegram \+ n8n \+ vision-capable AI \+ Google Sheets

**1\.** Create an Active Jobs sheet.

**2\.** Send a receipt photo plus a short note to a test chat.

**3\.** Let n8n extract vendor/date/items/amount, pass the active-job context to the AI, and write Job \+ Confidence \+ Reason into a second sheet.

**4\.** Keep low-confidence matches in REVIEW.

## **PAIN-002 — AI receipt memory that asks at the right moment**

**Pain: Paper receipts fade or sit in the truck until tax time, with job context forgotten.**

### **Narration**

The first thing this contractor / handyman client showed us was not their software. It was the workaround. Receipts accumulate in glovebox; owner later scans/types them and tries to remember which job each purchase was for. That workaround existed because paper receipts fade or sit in the truck until tax time, with job context forgotten. Our fix was a aI receipt memory that asks at the right moment. The system reads a receipt when it is fresh, stores the image, and links it to the sender, time and rough job context. If the project is unclear, the AI asks immediately instead of waiting until month-end when nobody remembers. Notice what the AI is doing here: it is understanding information that a rigid rule struggles with. The calculations, file moves or final updates are still deterministic. That design matters because it gives the team a visible REVIEW state instead of pretending the model is always right. In practice, the clever part is not OCR; it is moving the clarification from tax time to the exact moment the worker still remembers. For a small business, the DIY version can stop there. At higher volume, the same logic can sit behind the inbox, portal or existing system so the employee never has to start the workflow manually.

### **Backend — what we actually built**

* The system reads a receipt when it is fresh, stores the image, and links it to the sender, time and rough job context.  
* If the project is unclear, the AI asks immediately instead of waiting until month-end when nobody remembers.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Telegram bot \+ Drive \+ OCR/vision AI \+ Sheets

**1\.** Make a Telegram bot where you send a receipt photo.

**2\.** Store the image in Drive, extract the fields, and ask the sender one follow-up such as 'Which job was this for?' only when confidence is low.

**3\.** Append the final answer to an expense sheet.

## **PAIN-003 — Multimodal site-note-to-estimate copilot**

**Pain: Site notes and photos must be retyped later into an Excel estimate and PDF.**

### **Narration**

This case started with one question from the client: 'Why are we still doing this by hand?' The 'this' was site notes and photos must be retyped later into an Excel estimate and PDF. Their current process was straightforward but painful: take handwritten/phone notes and pictures on site, then return to computer and rebuild the quote in the existing workbook. We built a multimodal site-note-to-estimate copilot, but the interesting part was not the word AI. The AI looks at site photos, transcribes the contractor's voice note, extracts scope items, identifies missing measurements and compares the draft against the contractor's own pricebook. Code fills the existing estimate template; AI never invents a price. That split gave us a safer design: AI interprets the ambiguous input, code enforces the hard rules, and the employee approves exceptions. Instead of typing an estimate from memory later, the contractor leaves the site with a structured draft and a short list of questions. The simple prototype is something anyone can test with fake files first. The custom version only becomes necessary when you want it running continuously across real accounts, permissions and business-specific rules.

### **Backend — what we actually built**

* The AI looks at site photos, transcribes the contractor's voice note, extracts scope items, identifies missing measurements and compares the draft against the contractor's own pricebook.  
* Code fills the existing estimate template; AI never invents a price.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone voice memo \+ photos \+ Claude/ChatGPT vision \+ Python/Sheets

**1\.** Take three fake site photos and a 30-second voice memo.

**2\.** Give the model a small pricebook CSV and ask it to create scope rows with quantity, unit and 'missing information'.

**3\.** Use a tiny Python script or Apps Script to place approved rows into your estimate template.

## **PAIN-004 — Omnichannel invoice inbox with AI deduplication**

**Pain: Vendor invoices arrive by email, paper and text, so some never reach the project-cost record.**

### **Narration**

At first the client thought they needed a completely new system because vendor invoices arrive by email, paper and text, so some never reach the project-cost record. They did not. Their existing tools already held the right data; the missing piece was intelligence between them. Search inbox/messages/paper pile when reconciling; manually key invoice total/vendor/job. So we added a omnichannel invoice inbox with AI deduplication. Under the hood, Email PDFs, phone photos and forwarded messages all land in one intake folder. AI identifies whether each document is an invoice, extracts vendor/job/amount and recognizes duplicates even when filenames differ. Code files the original and updates project cost only after review. That means the AI never gets to silently make the final business decision. It produces a structured answer, confidence and evidence, then normal code handles the predictable next step. The client no longer has to remember where an invoice arrived; every channel collapses into one review queue. This is the kind of AI automation I like most: invisible enough that staff keep their normal workflow, but smart enough to remove the repetitive interpretation in the middle.

### **Backend — what we actually built**

* Email PDFs, phone photos and forwarded messages all land in one intake folder.  
* AI identifies whether each document is an invoice, extracts vendor/job/amount and recognizes duplicates even when filenames differ.  
* Code files the original and updates project cost only after review.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Gmail/Drive \+ n8n \+ document AI \+ SQLite/Sheets

**1\.** Create an 'Invoices' Gmail label and a Drive upload folder.

**2\.** Route both into one n8n workflow.

**3\.** Extract fields, generate a content fingerprint, and ask the AI to resolve vendor/job from context.

**4\.** Show NEW, DUPLICATE and REVIEW in a simple table.

## **PAIN-005 — AI cost-code matcher with overrun explanation**

**Pain: Estimate and actual cost live in different places, making budget overruns visible late.**

### **Narration**

One of the easiest ways to find a good AI automation is to watch what somebody does every Friday. In this client scenario, the recurring headache was estimate and actual cost live in different places, making budget overruns visible late. By the time the task started, estimate line items sit in one sheet/system while receipts, card charges and vendor invoices are entered separately. We replaced the repetitive middle with a aI cost-code matcher with overrun explanation. Actual card charges and vendor invoices are mapped to estimate cost codes using vendor, description, job and historical coding. A small rules engine calculates variance. AI then explains why a category is drifting instead of merely showing a red number. The model is not there to be clever for the sake of it; it is there because the input is inconsistent, handwritten, conversational or differently named. Once the information becomes structured, normal code takes over. The AI does not predict the future; it turns scattered actuals into an early warning the owner can understand. A viewer can build the small version with exports and sample files. The production version is where we connect the same logic to the client's real tools and put monitoring, permissions and human review around it.

### **Backend — what we actually built**

* Actual card charges and vendor invoices are mapped to estimate cost codes using vendor, description, job and historical coding.  
* A small rules engine calculates variance.  
* AI then explains why a category is drifting instead of merely showing a red number.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Excel/CSV \+ Python \+ AI reasoning \+ Streamlit

**1\.** Create an estimate CSV and an actual-transactions CSV.

**2\.** Use Python for arithmetic and an AI call only to suggest cost-code mappings for messy descriptions.

**3\.** Display budget, actual, variance and a short evidence-based explanation for the top three overruns.

## **PAIN-006 — Contract assembler that chooses only approved clauses**

**Pain: Accepted estimate still becomes a manual Word/PDF/sign/scan/email contract workflow.**

### **Narration**

We discovered this problem only because the client showed us a mistake that had already happened. The root cause was accepted estimate still becomes a manual Word/PDF/sign/scan/email contract workflow. Their team was copy customer/job/price data from estimate into Word, export PDF, send, receive scan/signature, file it. Instead of adding another checklist, we built a contract assembler that chooses only approved clauses. Once an estimate is approved, the system pulls job/customer/scope data, detects the job type and selects from a library of pre-approved clauses. AI turns scope bullets into readable contract language, while deterministic rules control which clauses are included. What I like about this architecture is that it is explicit about uncertainty. High-confidence, rule-safe cases can flow through; questionable cases are surfaced with the reason the system is unsure. The value is not 'AI writes a contract'; it is eliminating retyping while keeping legal wording controlled. That is a much better use of AI than asking a model to 'do everything'. It makes the messy information legible, then lets the business keep control of the important action.

### **Backend — what we actually built**

* Once an estimate is approved, the system pulls job/customer/scope data, detects the job type and selects from a library of pre-approved clauses.  
* AI turns scope bullets into readable contract language, while deterministic rules control which clauses are included.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Google Docs/Word templates \+ Apps Script/Python \+ AI drafting

**1\.** Create three approved clause snippets and one contract template.

**2\.** Feed an approved estimate row into a script.

**3\.** Let AI rewrite only the scope section, then let rules insert the correct payment/warranty/cancellation clauses.

**4\.** Highlight every generated paragraph for review.

## **PAIN-007 — AI client-selection listener across messages and photos**

**Pain: Client selections and allowances become a sprawling manual spec sheet.**

### **Narration**

The client described this as 'just admin', but it was happening often enough to deserve a proper solution: client selections and allowances become a sprawling manual spec sheet. The workflow was track fixtures, finishes, prices, decisions and change-order impact in long documents/spreadsheets. Our approach was a aI client-selection listener across messages and photos. The system watches a project inbox, reads messages such as 'we'll take the matte black tap' and recognizes attached product screenshots. It connects the choice to the right room/category, compares it with the allowance and asks for confirmation if the decision is ambiguous. We deliberately separated understanding from execution. The AI reads, interprets or matches; deterministic logic validates numbers, dates and permissions; a human gets the final say on exceptions. The spec sheet becomes a by-product of the client's normal conversation instead of another document someone has to maintain. The DIY build is useful because it lets the owner test the idea with a handful of records. If it works, the custom integration can remove the upload, copy-paste and manual trigger altogether.

### **Backend — what we actually built**

* The system watches a project inbox, reads messages such as 'we'll take the matte black tap' and recognizes attached product screenshots.  
* It connects the choice to the right room/category, compares it with the allowance and asks for confirmation if the decision is ambiguous.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Project email/WhatsApp export \+ AI vision/text \+ Airtable/Sheets

**1\.** Make a sample inbox with five client messages and screenshots.

**2\.** Give the AI the project's selection categories and allowance table.

**3\.** Extract Item, Room, Selected Product, Price, Decision Status and Source Link.

**4\.** Only CONFIRMED choices update the selection log.

## **PAIN-008 — Document AI for COI/license compliance**

**Pain: Subcontractor insurance certificates and licenses expire inside a spreadsheet.**

### **Narration**

This is a good example of why 'just automate it' is usually the wrong starting point. The client's actual pain was subcontractor insurance certificates and licenses expire inside a spreadsheet. They were manually maintain expiry dates and periodically scan rows to see what is about to lapse. If we had automated those clicks blindly, we would only have made the bad workflow faster. Instead we built a document AI for COI/license compliance. AI reads certificates and licenses with different layouts, identifies the subcontractor, document type, policy/license number and expiry date, and cross-checks it against the subcontractor master. Rules generate 30/14/7-day alerts; the AI drafts a precise request for whatever is actually missing. The AI's job is to understand context; the software's job is to enforce the business rules. Instead of scanning an expiry spreadsheet, the office sees only vendors that actually need action. So the final workflow is not a flashy chatbot. It is a quiet system that knows when it has enough evidence to proceed and when it needs to ask a person.

### **Backend — what we actually built**

* AI reads certificates and licenses with different layouts, identifies the subcontractor, document type, policy/license number and expiry date, and cross-checks it against the subcontractor master.  
* Rules generate 30/14/7-day alerts; the AI drafts a precise request for whatever is actually missing.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Drive folder \+ document AI \+ Sheets \+ scheduled Apps Script

**1\.** Drop five synthetic COIs/licenses into a folder.

**2\.** Extract the key fields into a compliance sheet.

**3\.** Add a scheduled script that finds upcoming expiries.

**4\.** Ask the AI to draft a reminder that names the exact expired/missing document, but keep sending manual for the prototype.

## **PAIN-009 — AI bid normalizer and exclusion finder**

**Pain: Subcontractor bids must be copied into the project's personal budget spreadsheet.**

### **Narration**

The interesting part of this client case was that the software was not broken. The gap was between the software and the way people actually work. Subcontractor bids must be copied into the project's personal budget spreadsheet. Day to day, receive bid PDFs/emails, then type totals/trades/allowances into Excel; family/crew may keep additional handwritten notes. We filled that gap with a aI bid normalizer and exclusion finder. Different subcontractor bids describe the same scope differently. AI maps line items into the builder's common trade structure, extracts exclusions/allowances and flags where two bids are not truly comparable. Code then calculates totals in the existing budget sheet. Because the AI output is structured and evidence-backed, the next step can be ordinary code: calculate, rename, file, sync or draft. The system does not just copy bid totals; it catches the sentence that makes the cheap bid not actually cheap. That is the pattern I would teach in the Short: use AI where language, images or messy naming create ambiguity; use code everywhere else.

### **Backend — what we actually built**

* Different subcontractor bids describe the same scope differently.  
* AI maps line items into the builder's common trade structure, extracts exclusions/allowances and flags where two bids are not truly comparable.  
* Code then calculates totals in the existing budget sheet.

### **Viewer DIY — easiest version to build**

**Suggested stack:** PDF/email bids \+ document AI \+ Python/Excel

**1\.** Create three fake bids for the same trade with deliberately different wording.

**2\.** Ask the AI to return normalized scope, price, exclusions and allowances with source references.

**3\.** Use Python to build an apples-to-apples comparison and highlight missing scope.

## **PAIN-010 — AI wrong-job time anomaly detector**

**Pain: Crew hours are sometimes logged to the wrong job and only discovered during billing.**

### **Narration**

A client in contractor / handyman brought us a process they had stopped questioning years ago. Compare time entries against where the crew actually worked and repair job-cost records manually. The reason was crew hours are sometimes logged to the wrong job and only discovered during billing. We rebuilt only the painful part as a aI wrong-job time anomaly detector. Crew time entries are checked against the day's schedule, job address, technician notes and—if available—coarse location evidence. AI explains suspicious entries such as a technician logging Project A while every other signal points to Project B. Nothing is changed automatically. There is no magic 'agent' making uncontrolled decisions here. The model turns unstructured business information into a reviewable structure, and the rest of the workflow follows explicit rules. Billing staff review two suspicious entries instead of discovering the mistake after the invoice has gone out. That makes it easy to demo, easy for a viewer to reproduce at small scale, and much easier to harden into a real client integration later.

### **Backend — what we actually built**

* Crew time entries are checked against the day's schedule, job address, technician notes and—if available—coarse location evidence.  
* AI explains suspicious entries such as a technician logging Project A while every other signal points to Project B.  
* Nothing is changed automatically.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Time CSV \+ schedule CSV \+ optional location export \+ Python/AI

**1\.** Create a fake time export and schedule with two intentional wrong-job entries.

**2\.** Use deterministic matching for employee/date first, then let AI review only conflicts using job name/address/note context.

**3\.** Output 'Likely wrong job' with a reason and confidence.

# **Property Management**

## **PAIN-011 — AI maintenance-time translator into owner billing**

**Pain: Maintenance hours go paper → property spreadsheet → Buildium owner expense, three times.**

### **Narration**

The fastest way to explain this client problem is with the before-and-after. Before: tech records start/end on paper; office retypes by property; then retypes each task again into owner expenses. The underlying issue was maintenance hours go paper → property spreadsheet → Buildium owner expense, three times. After: a aI maintenance-time translator into owner billing. The tool reads handwritten/scanned hours or a simple tech form, understands messy job notes, matches them to property/work-order IDs, and converts them into the owner's billing categories. The PMS import remains deterministic. The important design choice is the handoff point. AI stops once it has interpreted the messy input and attached confidence/evidence. Code takes over for exact calculations or updates, and a person handles anything uncertain. The same work record stops being typed three times because AI handles the messy translation once. That one separation is what makes the prototype feel impressive without becoming unsafe or impossible for the audience to understand.

### **Backend — what we actually built**

* The tool reads handwritten/scanned hours or a simple tech form, understands messy job notes, matches them to property/work-order IDs, and converts them into the owner's billing categories.  
* The PMS import remains deterministic.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Mobile form/scan \+ vision/text AI \+ Buildium CSV template

**1\.** Use a Google Form or scan a fake paper timesheet.

**2\.** Give the AI a property/work-order list and billing-category table.

**3\.** Extract technician, property, hours, work description and billing category, then generate a Buildium-style import CSV with REVIEW rows.

## **PAIN-012 — AI billing-narrative generator from time-clock rows**

**Pain: Time-clock spreadsheet is manually copied into an invoice-template spreadsheet.**

### **Narration**

The client did not ask us for AI. They asked us to stop time-clock spreadsheet is manually copied into an invoice-template spreadsheet. That distinction changed the solution. Their team was export time app CSV, then copy tech/property/hours/rates into the existing invoice workbook. We used a aI billing-narrative generator from time-clock rows because the bottleneck involved information that was too inconsistent for simple rules. A time-clock export contains employee, time and maybe a short note, but the owner's invoice needs a clean description. AI turns terse notes into consistent owner-facing narratives using the work-order context; code handles hours, rates and totals. Once the AI converts that mess into structured data, the rest is intentionally boring software. The spreadsheet copy disappears, but more importantly the invoice text becomes consistent without inventing work that was not done. For a Short, I would show the messy input first, then the AI's structured interpretation, then the tiny exception list. That tells the audience exactly where the intelligence lives.

### **Backend — what we actually built**

* A time-clock export contains employee, time and maybe a short note, but the owner's invoice needs a clean description.  
* AI turns terse notes into consistent owner-facing narratives using the work-order context; code handles hours, rates and totals.

### **Viewer DIY — easiest version to build**

**Suggested stack:** CSV \+ work-order export \+ AI \+ Excel template

**1\.** Create a time CSV and work-order CSV.

**2\.** Match rows by technician/date/property.

**3\.** Ask the AI to turn notes like 'sink leak done' into a neutral billing description using only provided facts.

**4\.** Fill the existing invoice template with formulas for labor totals.

## **PAIN-013 — AI rent-payment identity matcher**

**Pain: Owner checks the bank app every morning to know who paid rent.**

### **Narration**

This client case had a very specific failure point: owner checks the bank app every morning to know who paid rent. It was not happening because staff were careless. The process itself required them to open bank account, compare deposits to expected tenants, then update/remember a spreadsheet. We solved that with a aI rent-payment identity matcher. Bank deposits rarely match tenant names perfectly. The system uses amount, date, payment reference, tenant history and expected rent to suggest who paid. Exact matches are automatic; partial payments, combined payments and unknown senders stay in review. The system is designed to prove its work—source link, reason or confidence—before anything important happens. The owner checks the exception list instead of opening the bank app every morning and mentally matching deposits. That makes the same idea useful as a DIY prototype and credible as a professional integration, because the viewer can see that we are not just wrapping a prompt around a spreadsheet.

### **Backend — what we actually built**

* Bank deposits rarely match tenant names perfectly.  
* The system uses amount, date, payment reference, tenant history and expected rent to suggest who paid.  
* Exact matches are automatic; partial payments, combined payments and unknown senders stay in review.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Bank CSV \+ rent roll \+ Python \+ AI matching

**1\.** Create a rent roll and a bank CSV with misspelled references, one partial payment and one unknown sender.

**2\.** Use code for exact amount/date matches and AI only for ambiguous reference text.

**3\.** Return PAID, PARTIAL, REVIEW and UNMATCHED.

## **PAIN-014 — AI unit-history builder from receipts, photos and notes**

**Pain: Unit upgrade history is maintained manually across rows for appliances, paint, flooring, counters and fixtures.**

### **Narration**

I like this case because the best solution was not obvious from the pain. Unit upgrade history is maintained manually across rows for appliances, paint, flooring, counters and fixtures. The client's routine was edit a spreadsheet after each turnover/upgrade and search old rows when planning the next one. Rather than automating the routine literally, we changed where the decision happens by building a aI unit-history builder from receipts, photos and notes. Whenever work is done in a unit, the system reads the receipt, contractor note and before/after photo metadata, identifies the asset or finish, and adds a dated event to that unit's history. AI lets the manager later ask natural questions such as 'When was 4B's water heater replaced?'. Now AI performs the interpretation at the moment the data arrives, and the downstream steps become simple rules. The upgrade spreadsheet becomes a searchable memory of the building rather than a row somebody remembers to update. That is the kind of redesign that makes a one-minute story worth sharing: the audience sees not just a tool, but a better way to structure the work.

### **Backend — what we actually built**

* Whenever work is done in a unit, the system reads the receipt, contractor note and before/after photo metadata, identifies the asset or finish, and adds a dated event to that unit's history.  
* AI lets the manager later ask natural questions such as 'When was 4B's water heater replaced?'.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Drive folders \+ AI extraction \+ SQLite/Sheets \+ simple search

**1\.** Make three unit folders with fake receipts/photos/notes.

**2\.** Extract Unit, Asset, Work Done, Vendor, Date, Cost and Source.

**3\.** Store them in a sheet or SQLite database, then add a basic natural-language search that filters the structured records.

## **PAIN-015 — AI owner-analytics narrator on top of PMS exports**

**Pain: Needed revenue/occupancy analytics are calculated manually because the PMS view is not the owner's view.**

### **Narration**

The client's team had accepted this as normal: export reservation data, calculate totals/occupancy in a spreadsheet each time. But that normal behavior was hiding a real problem—needed revenue/occupancy analytics are calculated manually because the PMS view is not the owner's view. We built a aI owner-analytics narrator on top of PMS exports. The PMS provides raw occupancy and revenue, but not the owner's exact questions. A small analytics layer calculates the numbers deterministically, then AI turns them into an explanation: what moved, which properties drove it and which anomalies deserve inspection. The system does not replace the employee's judgment; it compresses the amount of information they have to judge. The client gets their own management view without replacing the PMS or trusting AI to do the math. In a DIY version you can demonstrate the exact same architecture with five fake records. In the production version the inputs simply arrive automatically from the real business systems.

### **Backend — what we actually built**

* The PMS provides raw occupancy and revenue, but not the owner's exact questions.  
* A small analytics layer calculates the numbers deterministically, then AI turns them into an explanation: what moved, which properties drove it and which anomalies deserve inspection.

### **Viewer DIY — easiest version to build**

**Suggested stack:** PMS CSV \+ Python/pandas \+ AI narrative \+ Streamlit

**1\.** Create a reservation export for three properties over two months.

**2\.** Calculate occupancy, ADR and revenue with Python.

**3\.** Give only those computed metrics to AI and ask for a five-bullet owner briefing with evidence and no invented causes.

## **PAIN-016 — AI card-transaction evidence matcher**

**Pain: Every property-card transaction must be GL-coded, described and matched to a receipt.**

### **Narration**

This was one of those workflows where adding more software would have made things worse. The client already had tools; what they lacked was a way to understand the information moving between them. Prepare a spreadsheet for each property/card, classify transaction, find receipt and link/match it. That created every property-card transaction must be GL-coded, described and matched to a receipt. Our fix was a aI card-transaction evidence matcher. Property-card transactions are linked to receipts by vendor, amount, date and textual clues. AI suggests a GL/property classification only after it finds supporting evidence in the receipt or historical mapping. Missing receipts become a chase list. The model's output is not the final answer—it is a structured proposal with evidence. Instead of coding every line from scratch, the accountant validates evidence-backed suggestions and focuses on missing receipts. That is the story I would tell: we did not sell them another dashboard; we made the systems they already pay for work together intelligently.

### **Backend — what we actually built**

* Property-card transactions are linked to receipts by vendor, amount, date and textual clues.  
* AI suggests a GL/property classification only after it finds supporting evidence in the receipt or historical mapping.  
* Missing receipts become a chase list.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Card CSV \+ receipt folder \+ document AI \+ accounting mapping sheet

**1\.** Prepare 20 card rows and 15 fake receipts.

**2\.** Extract receipt data, exact-match amount/vendor/date first, then let AI resolve fuzzy vendor names and suggest property/GL from a small approved mapping table.

**3\.** Output unmatched transactions separately.

## **PAIN-017 — AI owner-report redactor and explainer**

**Pain: Raw maintenance Google Sheet cannot simply be shared with every owner.**

### **Narration**

If you only looked at this process once, you might ignore it. But the client repeated it constantly: maintain one operational sheet but manually prepare safer owner-specific views/updates. Eventually that led to raw maintenance Google Sheet cannot simply be shared with every owner. We built a aI owner-report redactor and explainer. The raw maintenance sheet contains internal notes, vendor comments and information one owner should not see about another property. AI classifies which notes are owner-safe, rewrites technician shorthand into clear updates and code filters rows by owner/property. I would show the backend in one sentence on screen: messy input goes to AI, AI returns structured facts plus confidence, normal code runs the business rule, and the human sees exceptions. The owner gets a clean update without giving them access to the operational sheet or manually rewriting every line. That is simple enough for the audience to follow but deep enough to show there is real integration work behind it.

### **Backend — what we actually built**

* The raw maintenance sheet contains internal notes, vendor comments and information one owner should not see about another property.  
* AI classifies which notes are owner-safe, rewrites technician shorthand into clear updates and code filters rows by owner/property.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Google Sheet \+ Apps Script/Python \+ AI summarization

**1\.** Create one maintenance sheet with internal and owner-safe columns.

**2\.** Filter rows deterministically by owner.

**3\.** Let AI rewrite only the work description into a concise status and flag questionable/internal language for manual approval.

**4\.** Export a PDF or email draft.

## **PAIN-018 — AI vendor-compliance chaser**

**Pain: Vendor COI/license renewals are a manual spreadsheet reminder job.**

### **Narration**

The client showed us the end result first: a spreadsheet, folder or queue that took far too much effort to keep correct. The cause was vendor COI/license renewals are a manual spreadsheet reminder job. Behind it, staff had to track vendor document expirations and send reminders by looking ahead manually. We attacked the cause with a aI vendor-compliance chaser. Document AI reads new COIs/licenses, identifies what changed, and maintains a vendor compliance profile. A reasoning step chooses the right follow-up: missing certificate, wrong entity name, expired policy or missing license. Staff sees a prioritized queue, not generic reminders. Because the AI is grounded in the client's own records and rules, it can interpret business-specific language without becoming the source of truth itself. The reminder system becomes intelligent enough to ask for the right document instead of sending 'please update your COI' to everyone. The audience can reproduce the prototype with exports; the professional version connects those same steps to live systems with security and monitoring.

### **Backend — what we actually built**

* Document AI reads new COIs/licenses, identifies what changed, and maintains a vendor compliance profile.  
* A reasoning step chooses the right follow-up: missing certificate, wrong entity name, expired policy or missing license.  
* Staff sees a prioritized queue, not generic reminders.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Shared vendor inbox \+ document AI \+ Sheets/Airtable \+ scheduled workflow

**1\.** Build five fake vendor profiles and six sample documents.

**2\.** Extract expiry/entity/type.

**3\.** Compare with requirements and have AI generate a one-sentence 'why this needs attention'.

**4\.** Draft—but do not auto-send—the vendor message.

## **PAIN-019 — AI work-order conversation agent**

**Pain: Open work orders require repeated vendor/tenant follow-up to discover what is actually happening.**

### **Narration**

Here is what made this client problem interesting: the data already existed, but not in a form the next step could use. Open work orders require repeated vendor/tenant follow-up to discover what is actually happening. Staff were review open jobs, email/text vendors, ask tenant whether work is complete, update status manually. We built a aI work-order conversation agent to translate that messy information into a clean intermediate structure. The agent reads the work order plus the latest vendor and tenant email/text thread. It determines current status—scheduled, waiting on estimate, tenant unavailable, work completed, invoice missing—and identifies the next person who owes an action. It drafts only that follow-up. From there, deterministic code handles the rest. Instead of coordinators rereading every thread, the system tells them which conversations are actually stuck and why. That is the core AI-integration lesson behind the case: do not ask the model to run the business; ask it to understand the part that ordinary software cannot understand reliably.

### **Backend — what we actually built**

* The agent reads the work order plus the latest vendor and tenant email/text thread.  
* It determines current status—scheduled, waiting on estimate, tenant unavailable, work completed, invoice missing—and identifies the next person who owes an action.  
* It drafts only that follow-up.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Gmail export/test inbox \+ work-order CSV \+ AI thread summarization

**1\.** Create four fake work orders and message threads with different stalled states.

**2\.** Ask the AI to return Current Status, Last Evidence, Next Action, Who Owes It and Draft Follow-up.

**3\.** Use a rule to show only jobs with no update for X days.

## **PAIN-020 — AI source-of-truth reconciler**

**Pain: Property data lives in Sheets, Drive and the PMS, producing conflicting 'sources of truth'.**

### **Narration**

The client initially described the task as 'copying information'. When we looked closer, the hard part was not copying at all—it was deciding what the information meant. Property data lives in Sheets, Drive and the PMS, producing conflicting 'sources of truth'. Their current process was manually compare addresses, units, owners, vendors or statuses across exports/files when something looks wrong. So we built a aI source-of-truth reconciler. Sheets, Drive folder names and PMS exports often refer to the same property differently. AI performs entity resolution—'14 King St', 'King Street \#14', internal ID 0042—while code checks hard identifiers and counts. Conflicts become a canonical-data review queue. Once meaning becomes structured, every later step can be boring, testable code. The goal is not another database; it is a weekly check that tells the team exactly where their systems disagree. That is also why the DIY version is approachable: start with sample exports, make the interpretation visible, and only automate the final handoff once you trust it.

### **Backend — what we actually built**

* Sheets, Drive folder names and PMS exports often refer to the same property differently.  
* AI performs entity resolution—'14 King St', 'King Street \#14', internal ID 0042—while code checks hard identifiers and counts.  
* Conflicts become a canonical-data review queue.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Two/three exports \+ Python \+ embeddings/AI \+ simple review UI

**1\.** Create three small datasets with deliberate naming differences and conflicting owner/unit fields.

**2\.** Exact-match stable IDs first; use AI only to propose likely entity matches.

**3\.** Present side-by-side values and let a human choose the canonical record.

# **Hotels**

## **PAIN-021 — AI shift-receipt reconciler**

**Pain: Receipt details are retyped into Excel at the end of the shift.**

### **Narration**

The client in this example was a front desk / night audit in hotels, and the problem looked almost too small to automate: receipt details are retyped into Excel at the end of the shift. When we watched the workflow, manually enter every receipt into finance sheet; guest interruptions cause staff to lose their place. We did not replace their main software. We built a aI shift-receipt reconciler. In the background, A vision model reads receipt slips and the PMS/terminal export. Code totals the shift; AI handles messy merchant text, handwritten annotations and ambiguous receipt types. It groups everything and flags missing or duplicate receipts before the night audit. The important part is that AI is only handling the messy interpretation; anything exact is handled by normal code, and uncertain cases stay with a person. The result was simple: the front desk does not retype a stack into Excel; they review the few pieces that do not reconcile. If I were building the first version today, I would prove this with sample data first, then connect the real systems only after the team trusts the decisions. That is usually how a useful AI integration should start: one painful workflow, one measurable exception queue, and no unnecessary new platform.

### **Backend — what we actually built**

* A vision model reads receipt slips and the PMS/terminal export.  
* Code totals the shift; AI handles messy merchant text, handwritten annotations and ambiguous receipt types.  
* It groups everything and flags missing or duplicate receipts before the night audit.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone/scan \+ vision AI \+ PMS/terminal CSV \+ Python

**1\.** Create ten synthetic receipt images and a shift transaction CSV.

**2\.** Extract receipt number/amount/type, match them to the export, and show Missing Receipt, Duplicate and Amount Mismatch.

**3\.** Keep the arithmetic in code.

## **PAIN-022 — AI audit-report schema adapter**

**Pain: The final audit report is downloaded to Excel and reorganized every night.**

### **Narration**

The first thing this hotels client showed us was not their software. It was the workaround. Download PMS report, move/reorder columns or rows into the hotel's preferred finance/audit layout. That workaround existed because the final audit report is downloaded to Excel and reorganized every night. Our fix was a aI audit-report schema adapter. The hotel's PMS spits out a report in its own layout, while finance expects another. Instead of hard-coding column positions forever, AI identifies what each changing column means and maps it to a stable schema; code performs the reorder, formulas and total checks. Notice what the AI is doing here: it is understanding information that a rigid rule struggles with. The calculations, file moves or final updates are still deterministic. That design matters because it gives the team a visible REVIEW state instead of pretending the model is always right. In practice, the clever part is surviving small report-layout changes without someone rewriting the Excel cleanup every month. For a small business, the DIY version can stop there. At higher volume, the same logic can sit behind the inbox, portal or existing system so the employee never has to start the workflow manually.

### **Backend — what we actually built**

* The hotel's PMS spits out a report in its own layout, while finance expects another.  
* Instead of hard-coding column positions forever, AI identifies what each changing column means and maps it to a stable schema; code performs the reorder, formulas and total checks.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Downloaded XLSX/CSV \+ AI schema mapping \+ Python

**1\.** Make two fake nightly reports with renamed/reordered columns.

**2\.** Ask AI to map each source column to your fixed audit schema with confidence.

**3\.** Python applies the mapping, rebuilds the workbook and validates totals.

**4\.** Unknown columns go to REVIEW.

## **PAIN-023 — AI deposit-folio reconstruction checker**

**Pain: Advanced-deposit folios are sometimes rebuilt manually in Excel because the PMS is picky.**

### **Narration**

This case started with one question from the client: 'Why are we still doing this by hand?' The 'this' was advanced-deposit folios are sometimes rebuilt manually in Excel because the PMS is picky. Their current process was straightforward but painful: copy deposit/reservation details into an external workbook/folio representation. We built a aI deposit-folio reconstruction checker, but the interesting part was not the word AI. The system reads reservation data, deposit transactions and any existing folio export. AI understands labels and notes, while deterministic rules rebuild the expected deposit ledger. It highlights missing postings or mismatched dates before a staff member prepares the folio. That split gave us a safer design: AI interprets the ambiguous input, code enforces the hard rules, and the employee approves exceptions. Rather than manually rebuilding a folio in Excel, staff start from a reconciled draft with the questionable line already isolated. The simple prototype is something anyone can test with fake files first. The custom version only becomes necessary when you want it running continuously across real accounts, permissions and business-specific rules.

### **Backend — what we actually built**

* The system reads reservation data, deposit transactions and any existing folio export.  
* AI understands labels and notes, while deterministic rules rebuild the expected deposit ledger.  
* It highlights missing postings or mismatched dates before a staff member prepares the folio.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Reservation CSV \+ ledger CSV/PDF \+ Python \+ AI parsing

**1\.** Create a fake reservation, several deposits and one missing transaction.

**2\.** Normalize the ledger, build the expected timeline and have AI explain only the mismatch using source references.

**3\.** Generate a draft folio table for review.

## **PAIN-024 — AI folio-correction assistant**

**Pain: Correcting a paid folio can require copying reservation data, reposting charges and then editing a PDF.**

### **Narration**

At first the client thought they needed a completely new system because correcting a paid folio can require copying reservation data, reposting charges and then editing a PDF. They did not. Their existing tools already held the right data; the missing piece was intelligence between them. Create/copy reservation, manually repost services, produce adjusted document, edit dates/text as needed. So we added a aI folio-correction assistant. Under the hood, For a paid folio, the risky part is knowing what must be reversed, reposted or documented. The assistant compares the original folio with the requested correction and the hotel's approved correction rules, then produces a step-by-step plan. Staff performs every PMS action manually. That means the AI never gets to silently make the final business decision. It produces a structured answer, confidence and evidence, then normal code handles the predictable next step. AI becomes a second pair of eyes on a complex correction, not a bot moving money without supervision. This is the kind of AI automation I like most: invisible enough that staff keep their normal workflow, but smart enough to remove the repetitive interpretation in the middle.

### **Backend — what we actually built**

* For a paid folio, the risky part is knowing what must be reversed, reposted or documented.  
* The assistant compares the original folio with the requested correction and the hotel's approved correction rules, then produces a step-by-step plan.  
* Staff performs every PMS action manually.

### **Viewer DIY — easiest version to build**

**Suggested stack:** PDF folio \+ correction request \+ approved SOP \+ AI reasoning

**1\.** Use a synthetic folio and a written SOP.

**2\.** Ask the model to identify the exact differences and produce 'Required correction / Evidence / SOP step / Human action'.

**3\.** Do not connect it to the PMS in the prototype.

## **PAIN-025 — AI-assisted DNR identity search**

**Pain: DNR / banned-guest lists can be printed or kept on a corkboard, so new staff miss matches.**

### **Narration**

One of the easiest ways to find a good AI automation is to watch what somebody does every Friday. In this client scenario, the recurring headache was dNR / banned-guest lists can be printed or kept on a corkboard, so new staff miss matches. By the time the task started, staff visually scans a paper/list when a guest checks in. We replaced the repetitive middle with a aI-assisted DNR identity search. The system converts old DNR notes into structured identifiers—name variants, phone, email, incident date—and uses fuzzy matching to warn staff when a new reservation resembles a prior record. It also shows exactly why it matched so staff can verify identity. The model is not there to be clever for the sake of it; it is there because the input is inconsistent, handwritten, conversational or differently named. Once the information becomes structured, normal code takes over. The paper corkboard becomes searchable, but the final decision stays with trained staff because names alone are not enough. A viewer can build the small version with exports and sample files. The production version is where we connect the same logic to the client's real tools and put monitoring, permissions and human review around it.

### **Backend — what we actually built**

* The system converts old DNR notes into structured identifiers—name variants, phone, email, incident date—and uses fuzzy matching to warn staff when a new reservation resembles a prior record.  
* It also shows exactly why it matched so staff can verify identity.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Local database \+ embeddings/fuzzy search \+ simple front-desk UI

**1\.** Create 20 fake DNR records with spelling variations and five incoming reservations.

**2\.** Build a local search that returns top candidate matches with shared identifiers and confidence.

**3\.** Never auto-cancel or deny a guest.

## **PAIN-026 — Voice-first linen count with AI anomaly checking**

**Pain: Linen inventory for a large hotel is physically counted and totaled manually every month.**

### **Narration**

We discovered this problem only because the client showed us a mistake that had already happened. The root cause was linen inventory for a large hotel is physically counted and totaled manually every month. Their team was count sheets per area/item, then add totals and compare with prior month. Instead of adding another checklist, we built a voice-first linen count with AI anomaly checking. Housekeepers count aloud by zone—'king sheets 84, queen sheets 61...'—and speech AI maps those phrases to the hotel's linen master. Code totals counts. AI compares against the previous month and asks about implausible jumps or missing categories. What I like about this architecture is that it is explicit about uncertainty. High-confidence, rule-safe cases can flow through; questionable cases are surfaced with the reason the system is unsure. The team still physically counts linen, but nobody has to key and total every number afterward. That is a much better use of AI than asking a model to 'do everything'. It makes the messy information legible, then lets the business keep control of the important action.

### **Backend — what we actually built**

* Housekeepers count aloud by zone—'king sheets 84, queen sheets 61...'—and speech AI maps those phrases to the hotel's linen master.  
* Code totals counts.  
* AI compares against the previous month and asks about implausible jumps or missing categories.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone voice notes \+ speech-to-text \+ item master \+ Sheets

**1\.** Create a linen master and record two short fake count voice notes.

**2\.** Transcribe, map spoken item names to master items, sum by zone, and flag anything with an unusual percentage change.

**3\.** Let staff correct the transcript before saving.

## **PAIN-027 — AI authorization-document tracker without storing card data**

**Pain: Credit-card authorization forms are resent and re-confirmed because the hotel cannot find them at check-in.**

### **Narration**

The client described this as 'just admin', but it was happening often enough to deserve a proper solution: credit-card authorization forms are resent and re-confirmed because the hotel cannot find them at check-in. The workflow was send authorization, call ahead, resend if requested, then guest arrives and desk searches email/fax/files again. Our approach was a aI authorization-document tracker without storing card data. The system watches the approved mailbox/fax folder, recognizes authorization forms, matches them to reservations using guest/company/dates and stores only document status plus a secure link. It never extracts or exposes the card number in the working table. We deliberately separated understanding from execution. The AI reads, interprets or matches; deterministic logic validates numbers, dates and permissions; a human gets the final say on exceptions. Arrival staff see a missing-document list before the guest arrives instead of discovering at check-in that the form cannot be found. The DIY build is useful because it lets the owner test the idea with a handful of records. If it works, the custom integration can remove the upload, copy-paste and manual trigger altogether.

### **Backend — what we actually built**

* The system watches the approved mailbox/fax folder, recognizes authorization forms, matches them to reservations using guest/company/dates and stores only document status plus a secure link.  
* It never extracts or exposes the card number in the working table.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Gmail/Drive \+ document AI \+ reservation export \+ secure links

**1\.** Use redacted sample authorization forms.

**2\.** Extract guest/company/date/reservation hints, match to a fake arrival list and output Received / Missing / Unclear.

**3\.** Store the file path, not card details, in the demo sheet.

## **PAIN-028 — AI multi-PMS harmonizer**

**Pain: Different hotels/PMSs send reports that someone manually re-enters into a management spreadsheet.**

### **Narration**

This is a good example of why 'just automate it' is usually the wrong starting point. The client's actual pain was different hotels/PMSs send reports that someone manually re-enters into a management spreadsheet. They were night auditor scans/emails or exports reports; central employee keys selected numbers into one workbook. If we had automated those clicks blindly, we would only have made the bad workflow faster. Instead we built a aI multi-PMS harmonizer. Each hotel sends a differently named report. AI learns the meaning of columns and hotel-specific terminology, maps them into one company schema, and code validates totals before the portfolio dashboard updates. The mapping is remembered per hotel but rechecked when layouts change. The AI's job is to understand context; the software's job is to enforce the business rules. Central finance stops retyping numbers but still gets a clear alert when one property's report no longer matches the expected structure. So the final workflow is not a flashy chatbot. It is a quiet system that knows when it has enough evidence to proceed and when it needs to ask a person.

### **Backend — what we actually built**

* Each hotel sends a differently named report.  
* AI learns the meaning of columns and hotel-specific terminology, maps them into one company schema, and code validates totals before the portfolio dashboard updates.  
* The mapping is remembered per hotel but rechecked when layouts change.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Multiple CSV/XLSX reports \+ AI schema mapper \+ Python/Supabase

**1\.** Create three fake hotel reports with different columns for Room Revenue, Occupancy and ADR.

**2\.** Have AI return a mapping JSON for each.

**3\.** Transform them into one canonical table and reject any hotel whose totals fail validation.

## **PAIN-029 — AI rooming-list cleaner and block exception finder**

**Pain: Rooming lists and room blocks need manual import/checking, and unused rooms may not be released correctly.**

### **Narration**

The interesting part of this client case was that the software was not broken. The gap was between the software and the way people actually work. Rooming lists and room blocks need manual import/checking, and unused rooms may not be released correctly. Day to day, receive Excel rooming list, reshape/import it, compare booked names/rooms against block, manually identify leftover rooms. We filled that gap with a aI rooming-list cleaner and block exception finder. AI understands messy names, notes and company labels in a rooming list, while code handles dates, room counts and block totals. It spots duplicates, likely same-person variants, rooms outside the block and unused allocation. Because the AI output is structured and evidence-backed, the next step can be ordinary code: calculate, rename, file, sync or draft. The group coordinator reviews a handful of exceptions instead of manually comparing two spreadsheets line by line. That is the pattern I would teach in the Short: use AI where language, images or messy naming create ambiguity; use code everywhere else.

### **Backend — what we actually built**

* AI understands messy names, notes and company labels in a rooming list, while code handles dates, room counts and block totals.  
* It spots duplicates, likely same-person variants, rooms outside the block and unused allocation.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Excel rooming list \+ block export \+ Python \+ AI entity matching

**1\.** Create a 20-person rooming list with two misspellings and one duplicate.

**2\.** Normalize names with AI, compare dates/room types deterministically, then output Ready to Import, Duplicate, Outside Block and Unused Rooms.

## **PAIN-030 — AI pre-audit of group routing instructions**

**Pain: Group routing mistakes can require voiding, rerouting and reposting many charges.**

### **Narration**

A client in hotels brought us a process they had stopped questioning years ago. Inspect reservations/folios and manually repair charge routing after discovering the mistake. The reason was group routing mistakes can require voiding, rerouting and reposting many charges. We rebuilt only the painful part as a aI pre-audit of group routing instructions. The agent reads the group contract or billing email and converts it into a structured rule—room/tax to master, incidentals to guest, parking excluded, etc. It then compares that intent with the PMS routing export and flags reservations configured differently. There is no magic 'agent' making uncontrolled decisions here. The model turns unstructured business information into a reviewable structure, and the rest of the workflow follows explicit rules. The expensive mistake is caught before checkout, and the AI is interpreting the group's language rather than touching the folio itself. That makes it easy to demo, easy for a viewer to reproduce at small scale, and much easier to harden into a real client integration later.

### **Backend — what we actually built**

* The agent reads the group contract or billing email and converts it into a structured rule—room/tax to master, incidentals to guest, parking excluded, etc.  
* It then compares that intent with the PMS routing export and flags reservations configured differently.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Group contract/email \+ PMS routing CSV \+ AI extraction \+ Python rules

**1\.** Write two fake group billing instructions and create a routing export with three mistakes.

**2\.** Ask AI to extract the billing rules as JSON.

**3\.** Python applies those rules to each reservation and creates a pre-audit exception list.

# **Bookkeeping**

## **PAIN-031 — AI receipt ledger with duplicate and evidence checks**

**Pain: Hundreds of paper receipts are manually typed into a Google Sheet each year.**

### **Narration**

The fastest way to explain this client problem is with the before-and-after. Before: read receipt and enter date/vendor/amount/category/reference into spreadsheet one by one. The underlying issue was hundreds of paper receipts are manually typed into a Google Sheet each year. After: a aI receipt ledger with duplicate and evidence checks. The vision model reads each receipt, but a second layer checks whether that purchase already exists, whether tax/total arithmetic makes sense, and whether the category suggestion is supported by the description or a prior mapping. The original image stays linked as evidence. The important design choice is the handoff point. AI stops once it has interpreted the messy input and attached confidence/evidence. Code takes over for exact calculations or updates, and a person handles anything uncertain. The bookkeeper is validating a structured ledger instead of typing 400 rows and hoping none were entered twice. That one separation is what makes the prototype feel impressive without becoming unsafe or impossible for the audience to understand.

### **Backend — what we actually built**

* The vision model reads each receipt, but a second layer checks whether that purchase already exists, whether tax/total arithmetic makes sense, and whether the category suggestion is supported by the description or a prior mapping.  
* The original image stays linked as evidence.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone/Drive \+ vision AI \+ Python/Sheets

**1\.** Scan ten fake receipts including one duplicate.

**2\.** Extract fields, calculate a receipt fingerprint, and use an approved vendor-category table before asking AI about unknown vendors.

**3\.** Output Ready, Duplicate and Review.

## **PAIN-032 — AI-assisted bank reconciliation with semantic matching**

**Pain: Large bank reconciliations are done by putting two CSVs side-by-side and walking a running-zero formula until it breaks.**

### **Narration**

The client did not ask us for AI. They asked us to stop large bank reconciliations are done by putting two CSVs side-by-side and walking a running-zero formula until it breaks. That distinction changed the solution. Their team was sort bank/book CSVs by date, compare line by line, find first discrepancy, repair and continue. We used a aI-assisted bank reconciliation with semantic matching because the bottleneck involved information that was too inconsistent for simple rules. Code exact-matches identical date/amount/reference pairs first. AI is only called for the hard remainder: abbreviated vendor names, batch deposits, timing differences and descriptive references. Every proposed fuzzy match shows the evidence and confidence. Once the AI converts that mess into structured data, the rest is intentionally boring software. The AI works on the final 10% of messy reconciliation, not on arithmetic that code can do perfectly. For a Short, I would show the messy input first, then the AI's structured interpretation, then the tiny exception list. That tells the audience exactly where the intelligence lives.

### **Backend — what we actually built**

* Code exact-matches identical date/amount/reference pairs first.  
* AI is only called for the hard remainder: abbreviated vendor names, batch deposits, timing differences and descriptive references.  
* Every proposed fuzzy match shows the evidence and confidence.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Two CSVs \+ Python \+ AI/fuzzy matching \+ Streamlit

**1\.** Build two 50-row fake ledgers with several clear and ambiguous differences.

**2\.** Run exact matching first, then send only unmatched candidates to AI.

**3\.** Display side-by-side evidence and never hide unmatched amounts.

## **PAIN-033 — AI transaction-evidence graph**

**Pain: Amex transactions, invoice evidence, SharePoint files and QBO entry form a repeated manual reconciliation chain.**

### **Narration**

This client case had a very specific failure point: amex transactions, invoice evidence, SharePoint files and QBO entry form a repeated manual reconciliation chain. It was not happening because staff were careless. The process itself required them to type/import card transactions, locate invoices, link them, file matched PDFs, then accounting re-enters/post processes. We solved that with a aI transaction-evidence graph. Instead of moving through Amex, SharePoint, QBO and email one by one, the system builds links between a transaction, likely invoice/receipt, project/client and accounting code. AI resolves messy document text; code keeps the graph auditable with source links. The system is designed to prove its work—source link, reason or confidence—before anything important happens. The accountant sees the evidence chain in one place and only searches manually when the graph has a gap. That makes the same idea useful as a DIY prototype and credible as a professional integration, because the viewer can see that we are not just wrapping a prompt around a spreadsheet.

### **Backend — what we actually built**

* Instead of moving through Amex, SharePoint, QBO and email one by one, the system builds links between a transaction, likely invoice/receipt, project/client and accounting code.  
* AI resolves messy document text; code keeps the graph auditable with source links.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Statement CSV \+ invoice folder \+ email export \+ AI \+ SQLite

**1\.** Create 15 card transactions and a folder of 12 invoices with varied filenames.

**2\.** Extract vendor/date/amount, match evidence, and build a simple table showing Transaction → Document → Client/Project → Proposed Code → Confidence.

## **PAIN-034 — AI monthly-document collector**

**Pain: Monthly client statements/documents arrive late or get buried in email threads.**

### **Narration**

I like this case because the best solution was not obvious from the pain. Monthly client statements/documents arrive late or get buried in email threads. The client's routine was check each client folder/inbox against a recurring checklist and send repeated 'still missing' emails. Rather than automating the routine literally, we changed where the decision happens by building a aI monthly-document collector. The agent knows each client's recurring document checklist. It searches the approved inbox/folder for likely statements even when filenames are vague, extracts the account/month, and marks what is truly missing. Then it drafts one concise request containing only the outstanding items. Now AI performs the interpretation at the moment the data arrives, and the downstream steps become simple rules. The firm stops chasing documents that were already sent three email threads ago. That is the kind of redesign that makes a one-minute story worth sharing: the audience sees not just a tool, but a better way to structure the work.

### **Backend — what we actually built**

* The agent knows each client's recurring document checklist.  
* It searches the approved inbox/folder for likely statements even when filenames are vague, extracts the account/month, and marks what is truly missing.  
* Then it drafts one concise request containing only the outstanding items.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Gmail/Drive \+ client checklist \+ document AI \+ scheduled workflow

**1\.** Create three client folders, a checklist and sample emails/files with messy filenames.

**2\.** Ask AI to identify account/month/type, compare against the checklist and produce Missing Items \+ Draft Request.

**3\.** Keep sending manual.

## **PAIN-035 — AI client-question compressor for unclear transactions**

**Pain: Unclear transactions are manually copied into a question spreadsheet for the client.**

### **Narration**

The client's team had accepted this as normal: identify uncategorized/ambiguous rows, make a client-facing sheet, wait for answers, copy answers back. But that normal behavior was hiding a real problem—unclear transactions are manually copied into a question spreadsheet for the client. We built a aI client-question compressor for unclear transactions. Instead of copying 40 mystery transactions into a spreadsheet, AI groups similar ones—same vendor, recurring amount, same cardholder—and turns them into the smallest set of questions a client can actually answer. Their reply is mapped back to all affected transactions. The system does not replace the employee's judgment; it compresses the amount of information they have to judge. The automation reduces not just data entry, but the amount of back-and-forth the client has to endure. In a DIY version you can demonstrate the exact same architecture with five fake records. In the production version the inputs simply arrive automatically from the real business systems.

### **Backend — what we actually built**

* Instead of copying 40 mystery transactions into a spreadsheet, AI groups similar ones—same vendor, recurring amount, same cardholder—and turns them into the smallest set of questions a client can actually answer.  
* Their reply is mapped back to all affected transactions.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Transaction CSV \+ AI clustering \+ simple web form/Sheet

**1\.** Create 25 unclear transactions with repeated vendors.

**2\.** Cluster them into groups and generate questions like 'What is ABC Services used for?

**3\.** This affects 7 transactions.' Add a Group ID so one client answer updates every row in that group.

## **PAIN-036 — AI purchase-context chatbot**

**Pain: Bookkeeper has to ask the owner/spouse what purchases were for and where the receipt is.**

### **Narration**

This was one of those workflows where adding more software would have made things worse. The client already had tools; what they lacked was a way to understand the information moving between them. Review statement row, message spouse, search for receipt, manually update category/notes. That created bookkeeper has to ask the owner/spouse what purchases were for and where the receipt is. Our fix was a aI purchase-context chatbot. The owner or spouse gets one weekly message containing only purchases the system cannot explain. AI uses prior answers, merchant history and transaction text to ask a useful question instead of 'what is this?'. Replies are structured and attached to the right transactions. The model's output is not the final answer—it is a structured proposal with evidence. The conversation happens in plain language while the bookkeeping system receives structured evidence behind the scenes. That is the story I would tell: we did not sell them another dashboard; we made the systems they already pay for work together intelligently.

### **Backend — what we actually built**

* The owner or spouse gets one weekly message containing only purchases the system cannot explain.  
* AI uses prior answers, merchant history and transaction text to ask a useful question instead of 'what is this?'.  
* Replies are structured and attached to the right transactions.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Messaging bot/email \+ bank CSV \+ AI \+ Sheets

**1\.** Create ten unknown purchases and a small history of prior explanations.

**2\.** Have AI draft concise grouped questions.

**3\.** Simulate replies and map them back using transaction IDs.

**4\.** Do not let AI create a tax category without bookkeeper review.

## **PAIN-037 — AI batch petty-cash capture from a single camera session**

**Pain: A stack of 50 petty-cash receipts becomes 50 repetitive entries.**

### **Narration**

If you only looked at this process once, you might ignore it. But the client repeated it constantly: read and key each petty-cash receipt into books or a spreadsheet. Eventually that led to a stack of 50 petty-cash receipts becomes 50 repetitive entries. We built a aI batch petty-cash capture from a single camera session. Instead of photographing 50 receipts one by one, the user records or scans a batch. Vision splits pages/frames into individual receipts, extracts fields and checks that the receipt total agrees with the petty-cash replenishment amount. Unreadable items are isolated. I would show the backend in one sentence on screen: messy input goes to AI, AI returns structured facts plus confidence, normal code runs the business rule, and the human sees exceptions. The human still confirms the pile, but the repetitive entry and total check become one batch operation. That is simple enough for the audience to follow but deep enough to show there is real integration work behind it.

### **Backend — what we actually built**

* Instead of photographing 50 receipts one by one, the user records or scans a batch.  
* Vision splits pages/frames into individual receipts, extracts fields and checks that the receipt total agrees with the petty-cash replenishment amount.  
* Unreadable items are isolated.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone scan/PDF \+ vision AI \+ Python

**1\.** Create a multi-page PDF containing several fake receipts.

**2\.** Ask the model to return one JSON object per receipt with page reference.

**3\.** Sum them in code and compare against a known petty-cash top-up.

**4\.** Show unreadable/missing totals separately.

## **PAIN-038 — AI-guided legacy desktop posting**

**Pain: Vendor invoice data already exists in Excel but is re-entered one invoice at a time into Peachtree.**

### **Narration**

The client showed us the end result first: a spreadsheet, folder or queue that took far too much effort to keep correct. The cause was vendor invoice data already exists in Excel but is re-entered one invoice at a time into Peachtree. Behind it, staff had to open spreadsheet row, create vendor invoice in legacy accounting system, type same fields, repeat 100+ times. We attacked the cause with a aI-guided legacy desktop posting. The source invoices already exist in Excel; the problem is the old accounting software. The safest build first creates a validated import if the product supports one. If not, a desktop agent reads one row at a time, navigates the form and pauses whenever vendor/account validation fails. Because the AI is grounded in the client's own records and rules, it can interpret business-specific language without becoming the source of truth itself. We use AI around the brittle legacy edge; we do not let it invent accounting entries. The audience can reproduce the prototype with exports; the professional version connects those same steps to live systems with security and monitoring.

### **Backend — what we actually built**

* The source invoices already exist in Excel; the problem is the old accounting software.  
* The safest build first creates a validated import if the product supports one.  
* If not, a desktop agent reads one row at a time, navigates the form and pauses whenever vendor/account validation fails.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Excel \+ Python \+ supported import or desktop RPA \+ AI error interpretation

**1\.** Use a mock legacy form or test app, not production Peachtree.

**2\.** Let a script read five invoice rows and fill the mock form.

**3\.** Add AI only to interpret validation messages or map vendor name variants.

**4\.** Require a click to approve each batch.

## **PAIN-039 — AI bookkeeping work-status agent**

**Pain: Monthly client work is tracked in a separate Excel checklist just to know what reconciliation/financials are missing.**

### **Narration**

Here is what made this client problem interesting: the data already existed, but not in a form the next step could use. Monthly client work is tracked in a separate Excel checklist just to know what reconciliation/financials are missing. Staff were update status manually across clients and re-request missing information. We built a aI bookkeeping work-status agent to translate that messy information into a clean intermediate structure. Rather than manually updating a checklist, the agent inspects folder contents, reconciliation exports and recent client emails to infer whether each monthly task is Ready, Waiting on Client, In Progress or Needs Review. Each status includes the evidence that caused it. From there, deterministic code handles the rest. The tracker updates from the work itself instead of becoming another piece of work. That is the core AI-integration lesson behind the case: do not ask the model to run the business; ask it to understand the part that ordinary software cannot understand reliably.

### **Backend — what we actually built**

* Rather than manually updating a checklist, the agent inspects folder contents, reconciliation exports and recent client emails to infer whether each monthly task is Ready, Waiting on Client, In Progress or Needs Review.  
* Each status includes the evidence that caused it.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Client folders \+ checklist \+ email metadata \+ AI reasoning

**1\.** Create five fake clients with different missing documents and task files.

**2\.** Ask AI to produce Status, Evidence and Next Action from the folder/email metadata.

**3\.** Render a dashboard with only blocked or overdue work.

## **PAIN-040 — AI PDF-bank-statement recovery pipeline**

**Pain: Broken bank feeds leave hundreds of missing transactions and the bank only supplies PDF statements.**

### **Narration**

The client initially described the task as 'copying information'. When we looked closer, the hard part was not copying at all—it was deciding what the information meant. Broken bank feeds leave hundreds of missing transactions and the bank only supplies PDF statements. Their current process was extract/import PDF data, clean merged cells/formatting, compare with books and reconstruct gaps. So we built a aI PDF-bank-statement recovery pipeline. Document AI extracts transactions from ugly bank PDFs, but code then proves the extraction: opening/closing balance math, running balance consistency and duplicate checks. Only after those validations does it compare against the books and locate the missing bank-feed period. Once meaning becomes structured, every later step can be boring, testable code. AI gets the data out of the PDF; deterministic accounting checks decide whether the extraction is trustworthy. That is also why the DIY version is approachable: start with sample exports, make the interpretation visible, and only automate the final handoff once you trust it.

### **Backend — what we actually built**

* Document AI extracts transactions from ugly bank PDFs, but code then proves the extraction: opening/closing balance math, running balance consistency and duplicate checks.  
* Only after those validations does it compare against the books and locate the missing bank-feed period.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Bank PDF \+ document AI \+ Python reconciliation

**1\.** Use a synthetic PDF statement with a running balance and a books CSV missing several rows.

**2\.** Extract transactions, validate the balance equation, then compare against books.

**3\.** Show missing rows plus page references for each transaction.

# **Restaurant**

## **PAIN-041 — AI vendor-price and surcharge detective**

**Pain: Vendor prices creep up and new fuel/delivery/market fees are easy to miss across 10–15 invoices a week.**

### **Narration**

The client in this example was a owner / buyer in restaurant, and the problem looked almost too small to automate: vendor prices creep up and new fuel/delivery/market fees are easy to miss across 10–15 invoices a week. When we watched the workflow, manually compare new invoices against old ones line by line. We did not replace their main software. We built a aI vendor-price and surcharge detective. In the background, AI recognizes that 'CHKN BRST 40LB', 'Chicken Breast Case' and a new vendor SKU are the same purchasing item, then code compares unit-normalized prices. A classifier separately identifies fuel, delivery, market and miscellaneous surcharges so hidden fee creep is visible. The important part is that AI is only handling the messy interpretation; anything exact is handled by normal code, and uncertain cases stay with a person. The result was simple: the owner gets alerted to the change that matters instead of manually comparing fifteen entire invoices. If I were building the first version today, I would prove this with sample data first, then connect the real systems only after the team trusts the decisions. That is usually how a useful AI integration should start: one painful workflow, one measurable exception queue, and no unnecessary new platform.

### **Backend — what we actually built**

* AI recognizes that 'CHKN BRST 40LB', 'Chicken Breast Case' and a new vendor SKU are the same purchasing item, then code compares unit-normalized prices.  
* A classifier separately identifies fuel, delivery, market and miscellaneous surcharges so hidden fee creep is visible.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Invoice PDFs/photos \+ AI line-item normalization \+ Python dashboard

**1\.** Create invoices from two weeks with changed descriptions and a new surcharge.

**2\.** Extract and normalize item identity/unit, calculate price change in code, and display New Fee / Price Increase / Pack Change with source snippets.

## **PAIN-042 — Voice inventory that understands kitchen language**

**Pain: Weekly inventory count is manually written/typed into a spreadsheet and rolled into food-cost reports.**

### **Narration**

The first thing this restaurant client showed us was not their software. It was the workaround. Print or open count sheet, physically count, key quantities, combine with sales/purchases. That workaround existed because weekly inventory count is manually written/typed into a spreadsheet and rolled into food-cost reports. Our fix was a voice inventory that understands kitchen language. During count, the chef speaks naturally—'two and a half cases of wings, six bottles of oil...' AI transcribes and maps those phrases to the restaurant's item master and units. Code calculates the count and highlights items that differ sharply from expected usage. Notice what the AI is doing here: it is understanding information that a rigid rule struggles with. The calculations, file moves or final updates are still deterministic. That design matters because it gives the team a visible REVIEW state instead of pretending the model is always right. In practice, counting stays physical, but the clipboard-to-spreadsheet stage disappears. For a small business, the DIY version can stop there. At higher volume, the same logic can sit behind the inbox, portal or existing system so the employee never has to start the workflow manually.

### **Backend — what we actually built**

* During count, the chef speaks naturally—'two and a half cases of wings, six bottles of oil...' AI transcribes and maps those phrases to the restaurant's item master and units.  
* Code calculates the count and highlights items that differ sharply from expected usage.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone voice note \+ speech AI \+ inventory master \+ Sheets

**1\.** Record a short fake count using kitchen shorthand.

**2\.** Provide the item master with aliases and pack sizes.

**3\.** Convert speech to structured counts and flag unknown aliases for correction.

**4\.** Do not estimate missing counts.

## **PAIN-043 — AI ingredient graph for recipe-cost propagation**

**Pain: Recipe costing is layered across raw ingredients, base recipes and finished dishes, so supplier price changes require many updates.**

### **Narration**

This case started with one question from the client: 'Why are we still doing this by hand?' The 'this' was recipe costing is layered across raw ingredients, base recipes and finished dishes, so supplier price changes require many updates. Their current process was straightforward but painful: update raw ingredient cost and manually ensure dependent recipe/plate costs recalculate correctly. We built a aI ingredient graph for recipe-cost propagation, but the interesting part was not the word AI. Supplier invoices use vendor SKUs; recipes use kitchen names. AI creates the semantic bridge between them—this case of tomatoes feeds these sauce recipes, which feed these menu items. Code then propagates price changes through the dependency graph. That split gave us a safer design: AI interprets the ambiguous input, code enforces the hard rules, and the employee approves exceptions. AI solves the naming problem; code handles every cost calculation so margins remain explainable. The simple prototype is something anyone can test with fake files first. The custom version only becomes necessary when you want it running continuously across real accounts, permissions and business-specific rules.

### **Backend — what we actually built**

* Supplier invoices use vendor SKUs; recipes use kitchen names.  
* AI creates the semantic bridge between them—this case of tomatoes feeds these sauce recipes, which feed these menu items.  
* Code then propagates price changes through the dependency graph.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Supplier CSV/invoices \+ recipe sheets \+ AI entity mapping \+ Python

**1\.** Create a 10-ingredient master, three base recipes and four dishes.

**2\.** Let AI map vendor descriptions to ingredients, then use code to recalculate recipe and plate cost.

**3\.** Show which dishes changed most after one supplier price increase.

## **PAIN-044 — AI culinary-unit normalizer**

**Pain: Pricing a dish requires converting every ingredient into ounce/slice/tablespoon cost.**

### **Narration**

At first the client thought they needed a completely new system because pricing a dish requires converting every ingredient into ounce/slice/tablespoon cost. They did not. Their existing tools already held the right data; the missing piece was intelligence between them. Look up purchase pack price/size, calculate base-unit cost and build each recipe line manually. So we added a aI culinary-unit normalizer. Under the hood, A dish may use tablespoons while the invoice sells gallons, or slices while the case contains loaves. AI interprets the vendor pack description and culinary unit context, then proposes the conversion path. Code performs the actual math and rejects conversions with missing density/yield assumptions. That means the AI never gets to silently make the final business decision. It produces a structured answer, confidence and evidence, then normal code handles the predictable next step. The tool is useful precisely because it knows when 'one tablespoon' cannot be safely derived from the purchasing data. This is the kind of AI automation I like most: invisible enough that staff keep their normal workflow, but smart enough to remove the repetitive interpretation in the middle.

### **Backend — what we actually built**

* A dish may use tablespoons while the invoice sells gallons, or slices while the case contains loaves.  
* AI interprets the vendor pack description and culinary unit context, then proposes the conversion path.  
* Code performs the actual math and rejects conversions with missing density/yield assumptions.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Ingredient sheet \+ supplier pack descriptions \+ AI \+ Python calculator

**1\.** Create five ingredients with messy pack descriptions.

**2\.** Ask AI to translate each into base unit and required assumptions.

**3\.** Only calculate when the conversion is deterministic.

**4\.** Mark anything needing yield/density as REVIEW.

## **PAIN-045 — AI tip-pool rule interpreter with deterministic payroll math**

**Pain: Credit-card tip pool is recalculated from total tips and employee hours every payroll/day.**

### **Narration**

One of the easiest ways to find a good AI automation is to watch what somebody does every Friday. In this client scenario, the recurring headache was credit-card tip pool is recalculated from total tips and employee hours every payroll/day. By the time the task started, export/read total tips and hours, copy each employee's hours, calculate proportional share. We replaced the repetitive middle with a aI tip-pool rule interpreter with deterministic payroll math. The restaurant's written tip policy and shift data are converted into a clear rule set. AI identifies which employees/shifts are in scope; code calculates the proportional split and produces an explanation for unusual cases such as split shifts or missing clock-outs. The model is not there to be clever for the sake of it; it is there because the input is inconsistent, handwritten, conversational or differently named. Once the information becomes structured, normal code takes over. AI understands the policy wording; payroll math remains deterministic and reviewable. A viewer can build the small version with exports and sample files. The production version is where we connect the same logic to the client's real tools and put monitoring, permissions and human review around it.

### **Backend — what we actually built**

* The restaurant's written tip policy and shift data are converted into a clear rule set.  
* AI identifies which employees/shifts are in scope; code calculates the proportional split and produces an explanation for unusual cases such as split shifts or missing clock-outs.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Tip policy text \+ timeclock CSV \+ Python \+ AI rule extraction

**1\.** Use a fake written policy and shift file.

**2\.** Extract the rule into JSON, manually verify it, then run the tip calculation in code.

**3\.** Show employee, eligible hours, share and any REVIEW reason.

## **PAIN-046 — AI exact-item purchasing assistant**

**Pain: The 'little things' ordering list depends on exact supplier, model, pack size or link so staff buys the right item.**

### **Narration**

We discovered this problem only because the client showed us a mistake that had already happened. The root cause was the 'little things' ordering list depends on exact supplier, model, pack size or link so staff buys the right item. Their team was maintain a spreadsheet of item details and manually build an order from low/missing stock. Instead of adding another checklist, we built a aI exact-item purchasing assistant. Staff can photograph an empty box or say 'we need the same gloves as last time'. Vision/text AI identifies the exact internal item and retrieves the approved supplier/model/pack from purchase history. It drafts the order but does not substitute products silently. What I like about this architecture is that it is explicit about uncertainty. High-confidence, rule-safe cases can flow through; questionable cases are surfaced with the reason the system is unsure. The system prevents the classic mistake where a generic description causes someone to buy the wrong size or pack. That is a much better use of AI than asking a model to 'do everything'. It makes the messy information legible, then lets the business keep control of the important action.

### **Backend — what we actually built**

* Staff can photograph an empty box or say 'we need the same gloves as last time'.  
* Vision/text AI identifies the exact internal item and retrieves the approved supplier/model/pack from purchase history.  
* It drafts the order but does not substitute products silently.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone photo/voice \+ item master \+ AI vision \+ supplier-history sheet

**1\.** Create a small approved supplies catalog with images/model numbers.

**2\.** Photograph one sample item and use AI to identify likely catalog match.

**3\.** Return Approved Item, Supplier, Pack, Last Price and Confidence, with manual confirmation before adding to order.

## **PAIN-047 — AI invoice-scan sanity checker**

**Pain: Invoice-scanning software can misread pack size or unit, making food-cost data wrong unless someone double-checks.**

### **Narration**

The client described this as 'just admin', but it was happening often enough to deserve a proper solution: invoice-scanning software can misread pack size or unit, making food-cost data wrong unless someone double-checks. The workflow was inspect questionable scanned line items against invoice image and fix unit/quantity manually. Our approach was a aI invoice-scan sanity checker. The scan may say 6 cases when the invoice image says 6 each, or interpret a 4x1 gallon pack incorrectly. The checker compares extracted values with the visual source, vendor SKU history and plausible unit price. Only suspicious lines get a second AI pass or human review. We deliberately separated understanding from execution. The AI reads, interprets or matches; deterministic logic validates numbers, dates and permissions; a human gets the final say on exceptions. Instead of trusting OCR blindly, the system actively looks for the exact errors that destroy food-cost accuracy. The DIY build is useful because it lets the owner test the idea with a handful of records. If it works, the custom integration can remove the upload, copy-paste and manual trigger altogether.

### **Backend — what we actually built**

* The scan may say 6 cases when the invoice image says 6 each, or interpret a 4x1 gallon pack incorrectly.  
* The checker compares extracted values with the visual source, vendor SKU history and plausible unit price.  
* Only suspicious lines get a second AI pass or human review.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Invoice image \+ historical item master \+ vision AI \+ validation rules

**1\.** Create one invoice with three deliberately tricky pack lines.

**2\.** Extract once, then run checks for unit price outside historical range and pack format mismatch.

**3\.** Re-query only flagged lines with the cropped invoice image.

## **PAIN-048 — AI capture coach at the moment of invoice photography**

**Pain: Managers photograph invoices, but scans can be rejected or originals become hard to retrieve.**

### **Narration**

This is a good example of why 'just automate it' is usually the wrong starting point. The client's actual pain was managers photograph invoices, but scans can be rejected or originals become hard to retrieve. They were take invoice photo, upload, later chase a clearer image/original when processing fails. If we had automated those clicks blindly, we would only have made the bad workflow faster. Instead we built a aI capture coach at the moment of invoice photography. Before an invoice leaves the manager's hand, on-device or fast vision checks whether the page is cropped, blurry, shadowed, missing a second page or lacks a readable total/vendor. It tells the user exactly what to retake. The AI's job is to understand context; the software's job is to enforce the business rules. The best automation happens before bad data enters the accounting workflow at all. So the final workflow is not a flashy chatbot. It is a quiet system that knows when it has enough evidence to proceed and when it needs to ask a person.

### **Backend — what we actually built**

* Before an invoice leaves the manager's hand, on-device or fast vision checks whether the page is cropped, blurry, shadowed, missing a second page or lacks a readable total/vendor.  
* It tells the user exactly what to retake.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Mobile web form \+ vision model/image-quality checks \+ Drive

**1\.** Build a simple upload page.

**2\.** Test with a clean image, blurred image and cropped two-page invoice.

**3\.** Return 'Good to upload' or a precise instruction such as 'Retake page 2; total is cut off'.

**4\.** Store only accepted files.

## **PAIN-049 — AI supplier-SKU identity resolver**

**Pain: Supplier item numbers or descriptions change and the same ingredient can become a new/duplicate item.**

### **Narration**

The interesting part of this client case was that the software was not broken. The gap was between the software and the way people actually work. Supplier item numbers or descriptions change and the same ingredient can become a new/duplicate item. Day to day, notice duplicates later, manually map old/new descriptions/SKUs and repair cost history. We filled that gap with a aI supplier-SKU identity resolver. When a supplier changes item numbers or descriptions, AI compares description, pack size, brand, price history and prior aliases to suggest whether it is the same ingredient. Code maintains a permanent alias map once a human approves the match. Because the AI output is structured and evidence-backed, the next step can be ordinary code: calculate, rename, file, sync or draft. One human approval teaches the system the alias instead of forcing the team to repair the same duplicate every week. That is the pattern I would teach in the Short: use AI where language, images or messy naming create ambiguity; use code everywhere else.

### **Backend — what we actually built**

* When a supplier changes item numbers or descriptions, AI compares description, pack size, brand, price history and prior aliases to suggest whether it is the same ingredient.  
* Code maintains a permanent alias map once a human approves the match.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Old/new supplier catalogs \+ AI matching \+ alias table

**1\.** Create two supplier files with six renamed SKUs.

**2\.** Ask AI for candidate matches and evidence.

**3\.** Approve a few in an alias table, then show how future invoices automatically map to the canonical ingredient.

## **PAIN-050 — AI call-off conversation summarizer**

**Pain: Employee call-offs and reasons are hard to review consistently over time.**

### **Narration**

A client in restaurant brought us a process they had stopped questioning years ago. Receive texts/calls, remember or manually note who called off and why. The reason was employee call-offs and reasons are hard to review consistently over time. We rebuilt only the painful part as a aI call-off conversation summarizer. Call-offs arrive as texts or calls with different wording. AI turns the message into date, shift, employee, stated reason and whether coverage was requested, then code appends the record. Managers can view patterns, but the system never recommends discipline. There is no magic 'agent' making uncontrolled decisions here. The model turns unstructured business information into a reviewable structure, and the rest of the workflow follows explicit rules. The admin record becomes consistent while sensitive employment decisions remain entirely human. That makes it easy to demo, easy for a viewer to reproduce at small scale, and much easier to harden into a real client integration later.

### **Backend — what we actually built**

* Call-offs arrive as texts or calls with different wording.  
* AI turns the message into date, shift, employee, stated reason and whether coverage was requested, then code appends the record.  
* Managers can view patterns, but the system never recommends discipline.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Shared SMS/email export \+ AI extraction \+ attendance sheet

**1\.** Create ten fake call-off messages with slang and incomplete details.

**2\.** Extract only what is explicitly stated, mark missing shift/reason as UNKNOWN, and build a weekly summary by employee/shift without any performance score.

# **E-commerce / Retail**

## **PAIN-051 — AI self-healing supplier spreadsheet mapper**

**Pain: Manufacturer provides only huge spreadsheets for 10K+ SKUs; no API.**

### **Narration**

The fastest way to explain this client problem is with the before-and-after. Before: download new spreadsheet and manually work out what should change across store systems. The underlying issue was manufacturer provides only huge spreadsheets for 10K+ SKUs; no API. After: a aI self-healing supplier spreadsheet mapper. The manufacturer sends giant spreadsheets whose column names and layout change. AI inspects the new file, identifies which columns correspond to SKU, cost, stock, description and status, and maps them into a fixed product schema. Code validates row counts and key fields before applying changes. The important design choice is the handoff point. AI stops once it has interpreted the messy input and attached confidence/evidence. Code takes over for exact calculations or updates, and a person handles anything uncertain. The integration works without an API and is resilient to ordinary spreadsheet layout changes. That one separation is what makes the prototype feel impressive without becoming unsafe or impossible for the audience to understand.

### **Backend — what we actually built**

* The manufacturer sends giant spreadsheets whose column names and layout change.  
* AI inspects the new file, identifies which columns correspond to SKU, cost, stock, description and status, and maps them into a fixed product schema.  
* Code validates row counts and key fields before applying changes.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Supplier XLSX \+ AI schema mapping \+ Python

**1\.** Create two versions of a supplier spreadsheet with renamed/reordered columns.

**2\.** Ask AI to produce a mapping JSON.

**3\.** Transform both into one canonical CSV and show only added, changed and discontinued SKUs.

## **PAIN-052 — AI bundle relationship graph**

**Pain: About 1,000 SKUs are bundles, so component stock changes must roll up to bundle availability.**

### **Narration**

The client did not ask us for AI. They asked us to stop about 1,000 SKUs are bundles, so component stock changes must roll up to bundle availability. That distinction changed the solution. Their team was maintain bundle relationships in spreadsheet and calculate availability manually or with fragile formulas. We used a aI bundle relationship graph because the bottleneck involved information that was too inconsistent for simple rules. Bundle SKUs are linked to component SKUs and sometimes descriptions are inconsistent. AI helps build and maintain the component relationship graph from product names/BOM notes; code computes buildable quantity and explains which component is limiting each bundle. Once the AI converts that mess into structured data, the rest is intentionally boring software. AI understands the product relationships; stock arithmetic stays exact. For a Short, I would show the messy input first, then the AI's structured interpretation, then the tiny exception list. That tells the audience exactly where the intelligence lives.

### **Backend — what we actually built**

* Bundle SKUs are linked to component SKUs and sometimes descriptions are inconsistent.  
* AI helps build and maintain the component relationship graph from product names/BOM notes; code computes buildable quantity and explains which component is limiting each bundle.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Catalog CSV \+ bundle definitions \+ AI entity mapping \+ Python

**1\.** Create ten components and five bundles, including one ambiguous component name.

**2\.** Use AI to map the definitions once, then calculate available bundle quantity deterministically.

**3\.** Display 'Limited by SKU X'.

## **PAIN-053 — Multimodal asset-to-SKU matcher**

**Pain: Hundreds or thousands of product asset files must be matched to the right SKUs.**

### **Narration**

This client case had a very specific failure point: hundreds or thousands of product asset files must be matched to the right SKUs. It was not happening because staff were careless. The process itself required them to rename/search folders and attach images/manuals to products individually. We solved that with a multimodal asset-to-SKU matcher. Hundreds of product photos, manuals and PDFs have bad filenames. AI reads text from the file, looks at the product image/manual content and compares it with catalog descriptions to suggest the most likely SKU. Approved matches are renamed and moved automatically. The system is designed to prove its work—source link, reason or confidence—before anything important happens. The AI is doing visual and semantic identity matching, not just renaming by filename. That makes the same idea useful as a DIY prototype and credible as a professional integration, because the viewer can see that we are not just wrapping a prompt around a spreadsheet.

### **Backend — what we actually built**

* Hundreds of product photos, manuals and PDFs have bad filenames.  
* AI reads text from the file, looks at the product image/manual content and compares it with catalog descriptions to suggest the most likely SKU.  
* Approved matches are renamed and moved automatically.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Asset folder \+ catalog CSV \+ vision/document AI \+ Python file organizer

**1\.** Create ten product rows and eight poorly named image/PDF files.

**2\.** Generate top-three SKU candidates with evidence, approve them in a small UI, then have Python rename/copy the file into SKU folders.

## **PAIN-054 — AI browser copilot for product onboarding**

**Pain: Each product listing needs 5–10 minutes of tab switching, copy/paste, EAN/UPC, YouTube, HTML, SEO and formatting.**

### **Narration**

I like this case because the best solution was not obvious from the pain. Each product listing needs 5–10 minutes of tab switching, copy/paste, EAN/UPC, YouTube, HTML, SEO and formatting. The client's routine was open supplier/source pages and image/EAN sites, copy fields, format, preview, repeat hundreds of times. Rather than automating the routine literally, we changed where the decision happens by building a aI browser copilot for product onboarding. The agent opens the approved manufacturer page, finds specs/EAN/media, understands which attributes matter for that category, and drafts channel-ready copy. Deterministic validation checks required fields, forbidden claims, image count and SKU uniqueness before export. Now AI performs the interpretation at the moment the data arrives, and the downstream steps become simple rules. The seller still approves the listing, but the browser tab-hopping and copying vanish. That is the kind of redesign that makes a one-minute story worth sharing: the audience sees not just a tool, but a better way to structure the work.

### **Backend — what we actually built**

* The agent opens the approved manufacturer page, finds specs/EAN/media, understands which attributes matter for that category, and drafts channel-ready copy.  
* Deterministic validation checks required fields, forbidden claims, image count and SKU uniqueness before export.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Playwright \+ AI extraction/copy \+ product schema \+ CSV export

**1\.** Use two public/sample product pages or local HTML pages.

**2\.** Have Playwright collect the page, AI map facts into your product schema, then validate mandatory fields.

**3\.** Generate one clean import row and a REVIEW list for missing data.

## **PAIN-055 — AI replenishment exception planner**

**Pain: 500 SKUs from \~100 suppliers make native reports \+ one spreadsheet too complex for replenishment.**

### **Narration**

The client's team had accepted this as normal: combine supplier/stock information manually to decide what to reorder. But that normal behavior was hiding a real problem—500 SKUs from \~100 suppliers make native reports \+ one spreadsheet too complex for replenishment. We built a aI replenishment exception planner. Instead of replacing inventory planning, the system combines current stock, recent sales, supplier MOQ/lead time and open orders. AI explains unusual situations—new item, erratic demand, supplier constraint—while code calculates baseline reorder quantities. The system does not replace the employee's judgment; it compresses the amount of information they have to judge. The buyer starts with a reasoned exception list rather than scanning 500 SKUs and 100 supplier tabs. In a DIY version you can demonstrate the exact same architecture with five fake records. In the production version the inputs simply arrive automatically from the real business systems.

### **Backend — what we actually built**

* Instead of replacing inventory planning, the system combines current stock, recent sales, supplier MOQ/lead time and open orders.  
* AI explains unusual situations—new item, erratic demand, supplier constraint—while code calculates baseline reorder quantities.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Inventory/sales/supplier CSVs \+ Python \+ AI explanation

**1\.** Create 30 SKUs with stock, sales and supplier MOQ/lead time.

**2\.** Calculate a simple reorder baseline in code.

**3\.** Ask AI only to explain outliers and group recommendations by supplier.

**4\.** Avoid claiming demand prediction accuracy.

## **PAIN-056 — AI vision intake for one-off liquidation inventory**

**Pain: Incoming unique inventory often has no normal UPC or predictable reorder behavior.**

### **Narration**

This was one of those workflows where adding more software would have made things worse. The client already had tools; what they lacked was a way to understand the information moving between them. Unpack shipment, identify/price each odd item, create label/record manually, then track sale. That created incoming unique inventory often has no normal UPC or predictable reorder behavior. Our fix was a aI vision intake for one-off liquidation inventory. A worker photographs an unusual item. Vision identifies the likely category, extracts visible brand/model/size and checks prior internal inventory for similar items. The system creates an internal SKU and draft description; a human sets the final selling price. The model's output is not the final answer—it is a structured proposal with evidence. The business gets fast structured intake even when every item is unique and there is nothing useful to scan. That is the story I would tell: we did not sell them another dashboard; we made the systems they already pay for work together intelligently.

### **Backend — what we actually built**

* A worker photographs an unusual item.  
* Vision identifies the likely category, extracts visible brand/model/size and checks prior internal inventory for similar items.  
* The system creates an internal SKU and draft description; a human sets the final selling price.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone camera \+ vision AI \+ local item database \+ label printer/CSV

**1\.** Create five unusual household items with no UPC.

**2\.** Photograph them, extract visible attributes, search a small prior-item list for similarities and generate an internal SKU \+ label description.

**3\.** Do not automate final valuation.

## **PAIN-057 — AI item-identity link from intake to COG**

**Pain: Every item is stickered/recorded, manually invoiced, entered into a sales sheet, then matched back to COG.**

### **Narration**

If you only looked at this process once, you might ignore it. But the client repeated it constantly: move the same item ID/price/customer data between several paper/spreadsheet steps. Eventually that led to every item is stickered/recorded, manually invoiced, entered into a sales sheet, then matched back to COG. We built a aI item-identity link from intake to COG. Each physical item gets one internal ID. AI can recognize the item's label/photo later when it appears in an invoice or sale record, helping link sale price back to original cost. Code maintains the one-to-one lifecycle and catches duplicate IDs. I would show the backend in one sentence on screen: messy input goes to AI, AI returns structured facts plus confidence, normal code runs the business rule, and the human sees exceptions. The automation removes four manual records by making the item's identity travel with it. That is simple enough for the audience to follow but deep enough to show there is real integration work behind it.

### **Backend — what we actually built**

* Each physical item gets one internal ID.  
* AI can recognize the item's label/photo later when it appears in an invoice or sale record, helping link sale price back to original cost.  
* Code maintains the one-to-one lifecycle and catches duplicate IDs.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Internal QR/label \+ vision scan \+ sales sheet \+ Python

**1\.** Create ten sample items with internal IDs and photos.

**2\.** Simulate sales using label/photo input, resolve the item ID, and automatically generate a sales/COG row.

**3\.** Flag any attempt to sell the same unique ID twice.

## **PAIN-058 — AI learns bulk-catalog transformation rules from examples**

**Pain: Simple product-title/data changes can take hours because each listing must be edited separately.**

### **Narration**

The client showed us the end result first: a spreadsheet, folder or queue that took far too much effort to keep correct. The cause was simple product-title/data changes can take hours because each listing must be edited separately. Behind it, staff had to find product, edit field, save, repeat across many items/channels. We attacked the cause with a aI learns bulk-catalog transformation rules from examples. Instead of hand-editing 2,000 titles, the operator gives five before/after examples. AI infers a transformation rule—brand first, remove pack code, standardize size—and applies it to a preview. Code compares every result and supports rollback. Because the AI is grounded in the client's own records and rules, it can interpret business-specific language without becoming the source of truth itself. The operator teaches the system the editorial pattern once rather than editing every product. The audience can reproduce the prototype with exports; the professional version connects those same steps to live systems with security and monitoring.

### **Backend — what we actually built**

* Instead of hand-editing 2,000 titles, the operator gives five before/after examples.  
* AI infers a transformation rule—brand first, remove pack code, standardize size—and applies it to a preview.  
* Code compares every result and supports rollback.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Catalog CSV \+ AI transformation \+ diff/rollback script

**1\.** Create 30 fake titles and manually edit five.

**2\.** Ask AI to describe the rule and transform the rest.

**3\.** Show a before/after diff and require approval before writing a new CSV; keep the original untouched.

## **PAIN-059 — AI marketplace-schema translator**

**Pain: One master product dataset must be reshaped differently for WooCommerce, Amazon and eBay.**

### **Narration**

Here is what made this client problem interesting: the data already existed, but not in a form the next step could use. One master product dataset must be reshaped differently for WooCommerce, Amazon and eBay. Staff were maintain master CSV then manually map/rename/format columns for each marketplace. We built a aI marketplace-schema translator to translate that messy information into a clean intermediate structure. Each marketplace asks for the same product facts under different names, enums and category-specific fields. AI maps the canonical product record into the channel schema, while deterministic validators check accepted values, lengths and mandatory attributes. From there, deterministic code handles the rest. AI handles semantic schema differences; code enforces each marketplace's hard requirements. That is the core AI-integration lesson behind the case: do not ask the model to run the business; ask it to understand the part that ordinary software cannot understand reliably.

### **Backend — what we actually built**

* Each marketplace asks for the same product facts under different names, enums and category-specific fields.  
* AI maps the canonical product record into the channel schema, while deterministic validators check accepted values, lengths and mandatory attributes.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Master catalog \+ Amazon/eBay/Woo sample schemas \+ AI mapping \+ Python

**1\.** Create five canonical products and simplified channel templates.

**2\.** Ask AI for source-to-channel mappings and enum conversions.

**3\.** Generate three import files and a validation report listing fields that cannot be safely inferred.

## **PAIN-060 — AI supplier-catalog semantic diff**

**Pain: Supplier price/stock changes are hidden inside a new spreadsheet because the supplier has no API.**

### **Narration**

The client initially described the task as 'copying information'. When we looked closer, the hard part was not copying at all—it was deciding what the information meant. Supplier price/stock changes are hidden inside a new spreadsheet because the supplier has no API. Their current process was download current file, search important SKUs or compare manually with old version. So we built a aI supplier-catalog semantic diff. A supplier's latest file may rename columns, change descriptions and quietly alter stock/price. AI first maps the new file to the old schema and resolves renamed products; code then calculates an exact delta for price, stock, MOQ and discontinued status. Once meaning becomes structured, every later step can be boring, testable code. The owner no longer hunts through a giant spreadsheet to discover what changed overnight. That is also why the DIY version is approachable: start with sample exports, make the interpretation visible, and only automate the final handoff once you trust it.

### **Backend — what we actually built**

* A supplier's latest file may rename columns, change descriptions and quietly alter stock/price.  
* AI first maps the new file to the old schema and resolves renamed products; code then calculates an exact delta for price, stock, MOQ and discontinued status.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Old/new supplier XLSX \+ AI schema/entity matching \+ Python

**1\.** Create two supplier files with column changes, renamed SKUs and stock/price differences.

**2\.** Normalize them, resolve likely same products, and output only meaningful changes with confidence and source rows.

# **Recruiting / Staffing**

## **PAIN-061 — AI evidence extractor, not resume judge**

**Pain: Hundreds to 1,000+ resumes are reviewed manually when the HR system lacks useful screening.**

### **Narration**

The client in this example was a hiring manager / recruiter in recruiting / staffing, and the problem looked almost too small to automate: hundreds to 1,000+ resumes are reviewed manually when the HR system lacks useful screening. When we watched the workflow, open each resume and manually record objective evidence against the role. We did not replace their main software. We built a aI evidence extractor, not resume judge. In the background, The model reads resumes and extracts only explicit evidence for the role's published criteria—years with a tool, certification mentioned, location, work authorization if stated—along with the exact source text. It does not infer protected traits or make the hiring decision. The important part is that AI is only handling the messy interpretation; anything exact is handled by normal code, and uncertain cases stay with a person. The result was simple: aI removes the scavenger hunt inside each resume while the recruiter remains responsible for judgment. If I were building the first version today, I would prove this with sample data first, then connect the real systems only after the team trusts the decisions. That is usually how a useful AI integration should start: one painful workflow, one measurable exception queue, and no unnecessary new platform.

### **Backend — what we actually built**

* The model reads resumes and extracts only explicit evidence for the role's published criteria—years with a tool, certification mentioned, location, work authorization if stated—along with the exact source text.  
* It does not infer protected traits or make the hiring decision.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Resume PDFs \+ role criteria \+ document AI \+ review table

**1\.** Create five fictional resumes and a role rubric.

**2\.** Extract criterion-by-criterion evidence with page/section references and UNKNOWN when absent.

**3\.** Let the recruiter review the matrix manually; do not rank candidates automatically.

## **PAIN-062 — AI recruiting-ops memory from sheets, notes and whiteboards**

**Pain: Multiple requisitions are tracked across Google Sheets, Excel, whiteboards and even binders.**

### **Narration**

The first thing this recruiting / staffing client showed us was not their software. It was the workaround. Maintain role status/candidates in sheet while screening notes live on printed job posts/CVs. That workaround existed because multiple requisitions are tracked across Google Sheets, Excel, whiteboards and even binders. Our fix was a aI recruiting-ops memory from sheets, notes and whiteboards. The team can photograph a whiteboard, import its req spreadsheet and paste meeting notes. AI identifies roles, owners, blockers and candidate-stage updates, then proposes changes to one operational view. Nothing overwrites the source without approval. Notice what the AI is doing here: it is understanding information that a rigid rule struggles with. The calculations, file moves or final updates are still deterministic. That design matters because it gives the team a visible REVIEW state instead of pretending the model is always right. In practice, the team keeps working naturally while AI turns scattered status signals into one reviewable picture. For a small business, the DIY version can stop there. At higher volume, the same logic can sit behind the inbox, portal or existing system so the employee never has to start the workflow manually.

### **Backend — what we actually built**

* The team can photograph a whiteboard, import its req spreadsheet and paste meeting notes.  
* AI identifies roles, owners, blockers and candidate-stage updates, then proposes changes to one operational view.  
* Nothing overwrites the source without approval.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Whiteboard photo \+ Sheets \+ meeting notes \+ vision/text AI

**1\.** Make a fake whiteboard photo, req sheet and meeting note with overlapping information.

**2\.** Ask AI to propose a consolidated role-status table and show conflicts such as two different owners or close dates.

## **PAIN-063 — AI candidate identity and outreach-memory layer**

**Pain: Candidate touchpoints are fragmented across LinkedIn, email and outreach tools, causing duplicate messages.**

### **Narration**

This case started with one question from the client: 'Why are we still doing this by hand?' The 'this' was candidate touchpoints are fragmented across LinkedIn, email and outreach tools, causing duplicate messages. Their current process was straightforward but painful: remember/log who was contacted where; accidental LinkedIn \+ email double-message occurs. We built a aI candidate identity and outreach-memory layer, but the interesting part was not the word AI. Email, LinkedIn exports and outreach tools refer to candidates differently. AI/entity matching links likely same people using name, email, employer and profile URL. Before a recruiter sends a message, the system can say 'we emailed this person two days ago' with source evidence. That split gave us a safer design: AI interprets the ambiguous input, code enforces the hard rules, and the employee approves exceptions. The goal is not another CRM; it is preventing embarrassing duplicate outreach across the tools recruiters already use. The simple prototype is something anyone can test with fake files first. The custom version only becomes necessary when you want it running continuously across real accounts, permissions and business-specific rules.

### **Backend — what we actually built**

* Email, LinkedIn exports and outreach tools refer to candidates differently.  
* AI/entity matching links likely same people using name, email, employer and profile URL.  
* Before a recruiter sends a message, the system can say 'we emailed this person two days ago' with source evidence.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Email/outreach CSVs \+ candidate export \+ fuzzy/AI identity matching

**1\.** Create three contact exports with spelling variations and duplicate people.

**2\.** Build an identity table and a simple lookup that shows last contact channel/date.

**3\.** Keep ambiguous identities unmerged until approved.

## **PAIN-064 — AI weekly recruiting narrative from live pipeline data**

**Pain: Management reporting is maintained in a live role spreadsheet plus separate weekly stats.**

### **Narration**

At first the client thought they needed a completely new system because management reporting is maintained in a live role spreadsheet plus separate weekly stats. They did not. Their existing tools already held the right data; the missing piece was intelligence between them. Update candidate/role counts manually in one operational sheet and rebuild weekly metrics elsewhere. So we added a aI weekly recruiting narrative from live pipeline data. Under the hood, Code calculates open roles, stage counts, aging and movement. AI converts those metrics plus recruiter notes into a management brief: what changed, which roles are blocked and what needs a decision. It cites the rows behind every claim. That means the AI never gets to silently make the final business decision. It produces a structured answer, confidence and evidence, then normal code handles the predictable next step. The weekly report becomes an interpretation of the live pipeline rather than another spreadsheet someone has to maintain. This is the kind of AI automation I like most: invisible enough that staff keep their normal workflow, but smart enough to remove the repetitive interpretation in the middle.

### **Backend — what we actually built**

* Code calculates open roles, stage counts, aging and movement.  
* AI converts those metrics plus recruiter notes into a management brief: what changed, which roles are blocked and what needs a decision.  
* It cites the rows behind every claim.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Recruiting sheet/ATS export \+ Python metrics \+ AI summary

**1\.** Create a two-week pipeline dataset.

**2\.** Calculate counts/aging in code and ask AI to write a five-bullet update using only the computed table and notes.

**3\.** Include role IDs in each bullet for traceability.

## **PAIN-065 — AI rediscovery search for runner-up candidates**

**Pain: Runner-up / 'keep warm' candidates disappear when the main pipeline is homegrown or weak.**

### **Narration**

One of the easiest ways to find a good AI automation is to watch what somebody does every Friday. In this client scenario, the recurring headache was runner-up / 'keep warm' candidates disappear when the main pipeline is homegrown or weak. By the time the task started, manually remember or color-code good \#2 candidates across jobs. We replaced the repetitive middle with a aI rediscovery search for runner-up candidates. Past candidates are converted into a searchable evidence index. When a new requisition opens, the recruiter searches in plain English and AI retrieves prior candidates whose stored experience appears relevant, showing the supporting resume snippets. The recruiter decides who to contact. The model is not there to be clever for the sake of it; it is there because the input is inconsistent, handwritten, conversational or differently named. Once the information becomes structured, normal code takes over. Good candidates stop disappearing simply because they lost the last role by one position. A viewer can build the small version with exports and sample files. The production version is where we connect the same logic to the client's real tools and put monitoring, permissions and human review around it.

### **Backend — what we actually built**

* Past candidates are converted into a searchable evidence index.  
* When a new requisition opens, the recruiter searches in plain English and AI retrieves prior candidates whose stored experience appears relevant, showing the supporting resume snippets.  
* The recruiter decides who to contact.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Resume archive \+ embeddings/vector search \+ simple UI

**1\.** Use ten fictional past resumes.

**2\.** Chunk and embed the text, then search with a new role description.

**3\.** Return candidates with matching evidence snippets and previous status.

**4\.** Never auto-message or score protected attributes.

## **PAIN-066 — AI-assisted page-by-page candidate export cleanup**

**Pain: Candidate profiles are exported page by page and then copied into one spreadsheet.**

### **Narration**

We discovered this problem only because the client showed us a mistake that had already happened. The root cause was candidate profiles are exported page by page and then copied into one spreadsheet. Their team was export/download each results page, copy/append files, dedupe candidates. Instead of adding another checklist, we built a aI-assisted page-by-page candidate export cleanup. A browser script handles the repetitive page export. AI then normalizes role titles/company names and resolves duplicate profiles when the same candidate appears on multiple pages or searches. The original source URL stays attached. What I like about this architecture is that it is explicit about uncertainty. High-confidence, rule-safe cases can flow through; questionable cases are surfaced with the reason the system is unsure. Automation handles the mechanical pagination; AI handles the messy identity cleanup afterward. That is a much better use of AI than asking a model to 'do everything'. It makes the messy information legible, then lets the business keep control of the important action.

### **Backend — what we actually built**

* A browser script handles the repetitive page export.  
* AI then normalizes role titles/company names and resolves duplicate profiles when the same candidate appears on multiple pages or searches.  
* The original source URL stays attached.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Browser automation on a test/local page \+ AI dedupe \+ CSV

**1\.** Create a local mock candidate directory with three pages.

**2\.** Use Playwright to export rows, then dedupe with email/profile URL first and AI for name/company variations.

**3\.** Produce one clean CSV with duplicate reasons.

## **PAIN-067 — AI-safe ATS-to-Sheet sync when fields change**

**Pain: Outdated ATS data is recopied into Google Sheets every week for usable dashboards.**

### **Narration**

The client described this as 'just admin', but it was happening often enough to deserve a proper solution: outdated ATS data is recopied into Google Sheets every week for usable dashboards. The workflow was export/open ATS, update sheet rows/statuses, then dashboard reads the sheet. Our approach was a aI-safe ATS-to-Sheet sync when fields change. Old ATS exports change labels and column names over time. AI detects semantic field changes—'Phone Screen' becomes 'Recruiter Screen'—and proposes a mapping before the weekly sync runs. Code updates rows by stable candidate/requisition IDs and refuses unknown schemas. We deliberately separated understanding from execution. The AI reads, interprets or matches; deterministic logic validates numbers, dates and permissions; a human gets the final say on exceptions. The weekly sheet stays useful without a recruiter hand-copying data or a silent schema change corrupting the dashboard. The DIY build is useful because it lets the owner test the idea with a handful of records. If it works, the custom integration can remove the upload, copy-paste and manual trigger altogether.

### **Backend — what we actually built**

* Old ATS exports change labels and column names over time.  
* AI detects semantic field changes—'Phone Screen' becomes 'Recruiter Screen'—and proposes a mapping before the weekly sync runs.  
* Code updates rows by stable candidate/requisition IDs and refuses unknown schemas.

### **Viewer DIY — easiest version to build**

**Suggested stack:** ATS CSV \+ Google Sheets \+ AI schema mapper \+ Apps Script/Python

**1\.** Create two fake ATS exports with renamed stage fields.

**2\.** Have AI propose the mapping, manually approve it, then sync into a fixed dashboard sheet by stable IDs.

**3\.** Unknown columns should stop the run rather than guess.

## **PAIN-068 — AI hiring-manager view generator**

**Pain: Candidate status is tracked outside the ATS because hiring managers want a simpler weekly sheet.**

### **Narration**

This is a good example of why 'just automate it' is usually the wrong starting point. The client's actual pain was candidate status is tracked outside the ATS because hiring managers want a simpler weekly sheet. They were copy stage/interview/result notes into a client/hiring-manager spreadsheet. If we had automated those clicks blindly, we would only have made the bad workflow faster. Instead we built a aI hiring-manager view generator. The recruiter's tracker contains sourcing notes and internal detail that managers do not need. AI turns candidate status into a concise, neutral update while code filters out internal-only columns and limits each manager to their own roles. The AI's job is to understand context; the software's job is to enforce the business rules. The recruiter keeps a rich internal system while managers receive a simple view without manual copying. So the final workflow is not a flashy chatbot. It is a quiet system that knows when it has enough evidence to proceed and when it needs to ask a person.

### **Backend — what we actually built**

* The recruiter's tracker contains sourcing notes and internal detail that managers do not need.  
* AI turns candidate status into a concise, neutral update while code filters out internal-only columns and limits each manager to their own roles.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Recruiter sheet/ATS export \+ AI summarization \+ filtered report

**1\.** Create one internal candidate tracker with a sensitivity flag.

**2\.** Filter deterministically by hiring manager/role, then let AI rewrite stage notes into factual one-line updates.

**3\.** Export a manager-specific sheet or email draft.

## **PAIN-069 — AI handwriting-to-searchable interview notes**

**Pain: Interview/client briefing notes are scribbled on a CV or job description and later hard to search.**

### **Narration**

The interesting part of this client case was that the software was not broken. The gap was between the software and the way people actually work. Interview/client briefing notes are scribbled on a CV or job description and later hard to search. Day to day, handwrite/type notes, then manually re-enter key factual points into tracker/ATS. We filled that gap with a aI handwriting-to-searchable interview notes. A recruiter can photograph notes scribbled on a CV or job description. Vision transcribes the handwriting, separates factual candidate statements from recruiter impressions, links the note to the right person/role and creates a draft searchable record for review. Because the AI output is structured and evidence-backed, the next step can be ordinary code: calculate, rename, file, sync or draft. The notes become searchable without pretending AI can reliably infer what a rushed scribble meant when confidence is low. That is the pattern I would teach in the Short: use AI where language, images or messy naming create ambiguity; use code everywhere else.

### **Backend — what we actually built**

* A recruiter can photograph notes scribbled on a CV or job description.  
* Vision transcribes the handwriting, separates factual candidate statements from recruiter impressions, links the note to the right person/role and creates a draft searchable record for review.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone photo \+ vision/handwriting AI \+ candidate tracker

**1\.** Create two fake handwritten note pages.

**2\.** Extract Candidate, Role, Factual Notes, Follow-up Questions and Unclear Text.

**3\.** Require manual confirmation before adding anything to the tracker.

## **PAIN-070 — AI scheduling agent that understands constraints in email**

**Pain: High-volume interview scheduling requires repetitive Excel/Outlook coordination.**

### **Narration**

A client in recruiting / staffing brought us a process they had stopped questioning years ago. Check interviewer/candidate availability, build meetings, update spreadsheet, send details, repeat 10+ times. The reason was high-volume interview scheduling requires repetitive Excel/Outlook coordination. We rebuilt only the painful part as a aI scheduling agent that understands constraints in email. Candidates and interviewers say things like 'any time after 3 except Thursday'. AI converts that language into availability constraints. Code intersects calendars/time zones and proposes valid slots. A coordinator confirms the invite and any edge case. There is no magic 'agent' making uncontrolled decisions here. The model turns unstructured business information into a reviewable structure, and the rest of the workflow follows explicit rules. AI handles human language; calendar math and the final invitation remain deterministic and supervised. That makes it easy to demo, easy for a viewer to reproduce at small scale, and much easier to harden into a real client integration later.

### **Backend — what we actually built**

* Candidates and interviewers say things like 'any time after 3 except Thursday'.  
* AI converts that language into availability constraints.  
* Code intersects calendars/time zones and proposes valid slots.  
* A coordinator confirms the invite and any edge case.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Test email text \+ Calendar free/busy \+ AI constraint extraction \+ scheduling code

**1\.** Create four availability emails with natural language and a test calendar.

**2\.** Extract time windows/time zones to JSON, intersect them in code and show the top three slots with any uncertainty.

**3\.** Do not auto-send the invite.

# **Law Firm**

## **PAIN-071 — AI deadline exception reader over the firm's own spreadsheet**

**Pain: Deadlines and file status are color-coded in Excel and periodically reviewed row by row.**

### **Narration**

The fastest way to explain this client problem is with the before-and-after. Before: maintain case/date spreadsheet; every couple months staff sit down and review all files to see what is upcoming. The underlying issue was deadlines and file status are color-coded in Excel and periodically reviewed row by row. After: a aI deadline exception reader over the firm's own spreadsheet. The system does not calculate legal deadlines from law. It reads the firm's already-entered dates/statuses, spots blanks, conflicts, stale matters and upcoming events, and summarizes which rows need a lawyer or clerk to verify. The important design choice is the handoff point. AI stops once it has interpreted the messy input and attached confidence/evidence. Code takes over for exact calculations or updates, and a person handles anything uncertain. The intelligence is in surfacing anomalies without pretending the model knows the controlling legal deadline. That one separation is what makes the prototype feel impressive without becoming unsafe or impossible for the audience to understand.

### **Backend — what we actually built**

* The system does not calculate legal deadlines from law.  
* It reads the firm's already-entered dates/statuses, spots blanks, conflicts, stale matters and upcoming events, and summarizes which rows need a lawyer or clerk to verify.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Existing Excel \+ Python rules \+ AI explanation

**1\.** Create a fictional matter sheet with missing dates, two conflicting dates and several upcoming events.

**2\.** Use code to flag conditions.

**3\.** Ask AI only to write a concise morning summary pointing back to row IDs.

## **PAIN-072 — AI turns terse time notes into invoice-ready narratives**

**Pain: Time is entered in Excel and then copied into a Word invoice template.**

### **Narration**

The client did not ask us for AI. They asked us to stop time is entered in Excel and then copied into a Word invoice template. That distinction changed the solution. Their team was record time in spreadsheet, copy client/time/narrative into Word, calculate totals, save/send invoice. We used a aI turns terse time notes into invoice-ready narratives because the bottleneck involved information that was too inconsistent for simple rules. Lawyers often write shorthand like 'rev docs re motion 0.4'. AI expands only the narrative using the matter name and approved billing style. Hours/rates/totals stay untouched in code, and every rewritten narrative is reviewed before invoice generation. Once the AI converts that mess into structured data, the rest is intentionally boring software. The firm saves retyping while preserving the attorney's control over what gets billed and how it is described. For a Short, I would show the messy input first, then the AI's structured interpretation, then the tiny exception list. That tells the audience exactly where the intelligence lives.

### **Backend — what we actually built**

* Lawyers often write shorthand like 'rev docs re motion 0.4'.  
* AI expands only the narrative using the matter name and approved billing style.  
* Hours/rates/totals stay untouched in code, and every rewritten narrative is reviewed before invoice generation.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Time-entry Excel \+ approved billing examples \+ AI rewrite \+ Word template

**1\.** Create ten fictional time entries and three approved narrative examples.

**2\.** Ask AI to rewrite each entry without adding work that is not stated.

**3\.** Merge approved rows into a Word invoice template.

## **PAIN-073 — AI matter-code verifier for billing re-entry**

**Pain: Attorney records time in Excel; assistant re-enters the same entries into firm billing software the next day.**

### **Narration**

This client case had a very specific failure point: attorney records time in Excel; assistant re-enters the same entries into firm billing software the next day. It was not happening because staff were careless. The process itself required them to attorney logs client/matter/task/time; assistant opens sheet and keys each row into billing system. We solved that with a aI matter-code verifier for billing re-entry. Before any entry is posted to legacy billing, AI compares the attorney's shorthand client/matter name with the firm's master matter list and suggests the likely code. A desktop/import script handles the repetitive entry, but pauses on any low-confidence matter or task code. The system is designed to prove its work—source link, reason or confidence—before anything important happens. The valuable AI step is preventing the wrong matter from receiving a perfectly typed time entry. That makes the same idea useful as a DIY prototype and credible as a professional integration, because the viewer can see that we are not just wrapping a prompt around a spreadsheet.

### **Backend — what we actually built**

* Before any entry is posted to legacy billing, AI compares the attorney's shorthand client/matter name with the firm's master matter list and suggests the likely code.  
* A desktop/import script handles the repetitive entry, but pauses on any low-confidence matter or task code.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Time sheet \+ matter master \+ AI matching \+ supported import/RPA

**1\.** Create a fake matter master with similar names and a time sheet containing abbreviations.

**2\.** Resolve candidate matter codes with evidence, then simulate posting into a test form.

**3\.** Require approval on ambiguous cases.

## **PAIN-074 — Private AI unbilled-activity reconstruction**

**Pain: Time spent repeatedly reopening an email may not be captured automatically and is entered manually.**

### **Narration**

I like this case because the best solution was not obvious from the pain. Time spent repeatedly reopening an email may not be captured automatically and is entered manually. The client's routine was remember/reconstruct email work and add separate time entries. Rather than automating the routine literally, we changed where the decision happens by building a private AI unbilled-activity reconstruction. A local activity layer looks at approved metadata from email/documents—subject, file path, timestamps, matter tags—and groups activity by matter. AI drafts possible time entries and descriptions. The attorney decides whether the activity is billable and edits the final time. Now AI performs the interpretation at the moment the data arrives, and the downstream steps become simple rules. AI becomes a memory aid for the lawyer, not an invisible timekeeper that bills clients automatically. That is the kind of redesign that makes a one-minute story worth sharing: the audience sees not just a tool, but a better way to structure the work.

### **Backend — what we actually built**

* A local activity layer looks at approved metadata from email/documents—subject, file path, timestamps, matter tags—and groups activity by matter.  
* AI drafts possible time entries and descriptions.  
* The attorney decides whether the activity is billable and edits the final time.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Local email/document metadata \+ AI classification \+ daily review UI

**1\.** Use synthetic email subjects and document filenames.

**2\.** Map them to a fictional matter list and create a daily 'possible unbilled activity' timeline.

**3\.** Do not upload privileged content; show how metadata-only mode works.

## **PAIN-075 — AI matter brief from spreadsheet plus recent file activity**

**Pain: Client/case status and important dates are maintained in a custom Excel organizer.**

### **Narration**

The client's team had accepted this as normal: update rows and formulas manually to know what file/date/task needs attention. But that normal behavior was hiding a real problem—client/case status and important dates are maintained in a custom Excel organizer. We built a aI matter brief from spreadsheet plus recent file activity. The custom Excel organizer remains the source for key dates/status, but AI can combine that row with the latest approved document titles and notes to generate a one-screen matter brief: last action, next entered date, open questions and missing fields. The system does not replace the employee's judgment; it compresses the amount of information they have to judge. The lawyer can reopen a file after two weeks and understand where it stands without scanning ten columns and a folder tree. In a DIY version you can demonstrate the exact same architecture with five fake records. In the production version the inputs simply arrive automatically from the real business systems.

### **Backend — what we actually built**

* The custom Excel organizer remains the source for key dates/status, but AI can combine that row with the latest approved document titles and notes to generate a one-screen matter brief: last action, next entered date, open questions and missing fields.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Matter spreadsheet \+ folder index \+ AI summarizer

**1\.** Create five fictional matters and a folder listing.

**2\.** For one matter, assemble the row plus recent file names into a brief.

**3\.** Require citations/links to the source row/file for every point.

## **PAIN-076 — AI document assembly with locked source facts**

**Pain: The same client/matter data is retyped into recurring standard documents.**

### **Narration**

This was one of those workflows where adding more software would have made things worse. The client already had tools; what they lacked was a way to understand the information moving between them. Copy names/addresses/matter numbers/dates from client record into letters/forms/templates. That created the same client/matter data is retyped into recurring standard documents. Our fix was a aI document assembly with locked source facts. The system pulls client/matter facts once from a controlled record, chooses the correct approved template based on matter type, and asks AI only to draft variable prose sections from explicit source facts. Missing facts remain placeholders instead of guesses. The model's output is not the final answer—it is a structured proposal with evidence. AI helps with language while the template and source record control the legal structure and factual data. That is the story I would tell: we did not sell them another dashboard; we made the systems they already pay for work together intelligently.

### **Backend — what we actually built**

* The system pulls client/matter facts once from a controlled record, chooses the correct approved template based on matter type, and asks AI only to draft variable prose sections from explicit source facts.  
* Missing facts remain placeholders instead of guesses.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Matter data sheet \+ approved DOCX templates \+ AI drafting \+ python-docx

**1\.** Create two fictional matter records and two templates.

**2\.** Populate names/dates mechanically.

**3\.** Let AI draft one variable paragraph from a short fact set and mark \[MISSING\] for absent facts.

**4\.** Generate a draft DOCX for attorney review.

## **PAIN-077 — AI phone-scan docket capture from paper files**

**Pain: Paper folders and sticky notes hold the next court date/task, so there is no reliable 'what is due next' view.**

### **Narration**

If you only looked at this process once, you might ignore it. But the client repeated it constantly: write next date/task on paper file; physically search piles for upcoming work. Eventually that led to paper folders and sticky notes hold the next court date/task, so there is no reliable 'what is due next' view. We built a aI phone-scan docket capture from paper files. A lawyer or clerk photographs the sticky note/file cover. Vision extracts matter ID, the written next court date and next action, then compares it with the existing calendar. Any unreadable date or discrepancy is highlighted for human confirmation. I would show the backend in one sentence on screen: messy input goes to AI, AI returns structured facts plus confidence, normal code runs the business rule, and the human sees exceptions. The paper can stay, but the office gains a digital exception view of what might otherwise be missed. That is simple enough for the audience to follow but deep enough to show there is real integration work behind it.

### **Backend — what we actually built**

* A lawyer or clerk photographs the sticky note/file cover.  
* Vision extracts matter ID, the written next court date and next action, then compares it with the existing calendar.  
* Any unreadable date or discrepancy is highlighted for human confirmation.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Phone photo \+ vision/handwriting AI \+ matter list/calendar export

**1\.** Create five fake file-cover notes with handwriting.

**2\.** Extract matter/date/action, match to a fictional matter list and compare to a test calendar.

**3\.** Show 'Calendar missing' or 'Handwriting unclear' without creating events automatically.

## **PAIN-078 — AI document-pack assembler**

**Pain: Client document packs need repeated batch PDF conversion and can hit software limits.**

### **Narration**

The client showed us the end result first: a spreadsheet, folder or queue that took far too much effort to keep correct. The cause was client document packs need repeated batch PDF conversion and can hit software limits. Behind it, staff had to select many client files, convert individually/in batches, merge/rename and repeat. We attacked the cause with a aI document-pack assembler. The client folder may contain Word files, PDFs, scans and images with inconsistent names. AI classifies document type and likely chronological/order position, while code converts, renames, merges and creates an index/bookmarks. Sensitive transformations stay local where possible. Because the AI is grounded in the client's own records and rules, it can interpret business-specific language without becoming the source of truth itself. The model understands what the documents are; deterministic file tools perform the actual conversion and packaging. The audience can reproduce the prototype with exports; the professional version connects those same steps to live systems with security and monitoring.

### **Backend — what we actually built**

* The client folder may contain Word files, PDFs, scans and images with inconsistent names.  
* AI classifies document type and likely chronological/order position, while code converts, renames, merges and creates an index/bookmarks.  
* Sensitive transformations stay local where possible.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Local folder \+ document AI/local OCR \+ Python PDF tools

**1\.** Create a fictional client folder with mixed file types.

**2\.** Classify each as correspondence, invoice, pleading, evidence, etc., approve the order, then run a local script to convert/merge and create a manifest.

## **PAIN-079 — AI semantic dual-calendar reconciler**

**Pain: Cobbled low-cost apps and a required dual-calendar setup must be cross-checked.**

### **Narration**

Here is what made this client problem interesting: the data already existed, but not in a form the next step could use. Cobbled low-cost apps and a required dual-calendar setup must be cross-checked. Staff were enter deadlines/events in two calendars and manually verify both contain the same critical entries. We built a aI semantic dual-calendar reconciler to translate that messy information into a clean intermediate structure. Two calendars may contain the same hearing with slightly different titles or times. Exact matching misses those. AI compares event meaning plus matter identifiers and suggests likely pairs; code flags missing, time-conflicting or date-conflicting critical events. From there, deterministic code handles the rest. The firm gets a cross-check without trusting AI to create or calculate the legal event itself. That is the core AI-integration lesson behind the case: do not ask the model to run the business; ask it to understand the part that ordinary software cannot understand reliably.

### **Backend — what we actually built**

* Two calendars may contain the same hearing with slightly different titles or times.  
* Exact matching misses those.  
* AI compares event meaning plus matter identifiers and suggests likely pairs; code flags missing, time-conflicting or date-conflicting critical events.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Two calendar CSV/ICS exports \+ AI semantic match \+ Python

**1\.** Create two test calendar exports with renamed events, one missing event and one wrong time.

**2\.** Match by matter ID/date first, then AI for title variants.

**3\.** Output Only in A, Only in B and Time Conflict.

## **PAIN-080 — AI legacy matter cockpit**

**Pain: Old billing/payment/file systems make it hard to see what is happening with a client file or bill.**

### **Narration**

The client initially described the task as 'copying information'. When we looked closer, the hard part was not copying at all—it was deciding what the information meant. Old billing/payment/file systems make it hard to see what is happening with a client file or bill. Their current process was open legacy billing, server folders and Excel notes separately; payments may be paper check/wire. So we built a aI legacy matter cockpit. The old practice has billing exports, paper-payment records, server folders and spreadsheets. Instead of migrating everything immediately, the system indexes the exports and file metadata and lets AI answer bounded questions such as 'what is the latest document, unpaid invoice and next entered action for Matter 42?'. Once meaning becomes structured, every later step can be boring, testable code. The first win is visibility across the old tools; migration can wait until the firm understands what it actually needs. That is also why the DIY version is approachable: start with sample exports, make the interpretation visible, and only automate the final handoff once you trust it.

### **Backend — what we actually built**

* The old practice has billing exports, paper-payment records, server folders and spreadsheets.  
* Instead of migrating everything immediately, the system indexes the exports and file metadata and lets AI answer bounded questions such as 'what is the latest document, unpaid invoice and next entered action for Matter 42?'.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Read-only exports \+ file index \+ local search/AI \+ simple dashboard

**1\.** Create a fictional billing CSV, payment CSV, matter sheet and folder list.

**2\.** Join by matter ID and expose a search box that returns a source-linked status summary.

**3\.** Keep the system read-only.

# **Dental Clinic**

## **PAIN-081 — AI portal-reading assistant for insurance status**

**Pain: Insurance eligibility and pre-determinations require logging into many separate payer portals.**

### **Narration**

The client in this example was a front desk in dental clinic, and the problem looked almost too small to automate: insurance eligibility and pre-determinations require logging into many separate payer portals. When we watched the workflow, maintain credentials/reference sheet, open portal after portal, check status, note result/pending date. We did not replace their main software. We built a aI portal-reading assistant for insurance status. In the background, The browser automation handles login/navigation only in an approved environment. AI reads the inconsistent payer page or downloaded response and extracts factual status—active, pending, deductible shown, missing information—with source text. Staff interprets coverage and makes the decision. The important part is that AI is only handling the messy interpretation; anything exact is handled by normal code, and uncertain cases stay with a person. The result was simple: the useful AI skill is understanding twenty different portal layouts, not pretending to decide what insurance will pay. If I were building the first version today, I would prove this with sample data first, then connect the real systems only after the team trusts the decisions. That is usually how a useful AI integration should start: one painful workflow, one measurable exception queue, and no unnecessary new platform.

### **Backend — what we actually built**

* The browser automation handles login/navigation only in an approved environment.  
* AI reads the inconsistent payer page or downloaded response and extracts factual status—active, pending, deductible shown, missing information—with source text.  
* Staff interprets coverage and makes the decision.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Test/mock payer pages \+ Playwright \+ vision/text AI \+ patient queue

**1\.** Build two local HTML mock payer portals with different layouts.

**2\.** Use Playwright to open a patient record and AI to extract defined status fields.

**3\.** Store only synthetic patient data and keep any coverage interpretation out of the prototype.

## **PAIN-082 — AI pre-determination follow-up agent**

**Pain: Pending pre-determinations can sit for days and need manual re-checking.**

### **Narration**

The first thing this dental clinic client showed us was not their software. It was the workaround. Remember which payer/case is still pending, revisit portal later, update patient note. That workaround existed because pending pre-determinations can sit for days and need manual re-checking. Our fix was a aI pre-determination follow-up agent. Each submitted pre-D gets a case record with payer, sent date and expected next check. The agent reads new portal/email updates, recognizes which case they belong to and changes the follow-up priority. It does not approve treatment or interpret clinical necessity. Notice what the AI is doing here: it is understanding information that a rigid rule struggles with. The calculations, file moves or final updates are still deterministic. That design matters because it gives the team a visible REVIEW state instead of pretending the model is always right. In practice, instead of staff repeatedly opening every payer, the system tells them which cases changed and which ones are simply old enough to recheck. For a small business, the DIY version can stop there. At higher volume, the same logic can sit behind the inbox, portal or existing system so the employee never has to start the workflow manually.

### **Backend — what we actually built**

* Each submitted pre-D gets a case record with payer, sent date and expected next check.  
* The agent reads new portal/email updates, recognizes which case they belong to and changes the follow-up priority.  
* It does not approve treatment or interpret clinical necessity.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Case sheet \+ sample payer emails/portal exports \+ AI classification \+ scheduler

**1\.** Create ten fake pre-D cases and several update messages such as 'additional information required' or 'still processing'.

**2\.** Match messages to cases, update status and display today's recheck queue.

## **PAIN-083 — AI lab-case readiness agent**

**Pain: Lab cases must move through sent → received → dentist QC → ready, with a handwritten box check as backup.**

### **Narration**

This case started with one question from the client: 'Why are we still doing this by hand?' The 'this' was lab cases must move through sent → received → dentist QC → ready, with a handwritten box check as backup. Their current process was straightforward but painful: update software at several handoffs and physically look for dentist handwriting if readiness is uncertain. We built a aI lab-case readiness agent, but the interesting part was not the word AI. The clinic's appointment list is compared with lab messages, case notes and received/QC status. AI understands messages like '21 zirconia dispatched' or 'shade correction needed', matches them to the patient/case and estimates administrative readiness. Rules flag tomorrow's appointment when required stages are missing. That split gave us a safer design: AI interprets the ambiguous input, code enforces the hard rules, and the employee approves exceptions. The system stays quiet when everything is fine and interrupts the team only when tomorrow's appointment is at risk. The simple prototype is something anyone can test with fake files first. The custom version only becomes necessary when you want it running continuously across real accounts, permissions and business-specific rules.

### **Backend — what we actually built**

* The clinic's appointment list is compared with lab messages, case notes and received/QC status.  
* AI understands messages like '21 zirconia dispatched' or 'shade correction needed', matches them to the patient/case and estimates administrative readiness.  
* Rules flag tomorrow's appointment when required stages are missing.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Appointment CSV \+ fake lab WhatsApp/email text \+ AI extraction \+ Python rules

**1\.** Create tomorrow's appointments and ten fake lab messages.

**2\.** Extract patient/case/status/expected arrival, match them, and flag Appointment Before Arrival, Not Received and QC Pending.

**3\.** Use fake patient names only.

## **PAIN-084 — AI dental-supply purchasing copilot**

**Pain: Supply ordering involves comparing prior orders/latest prices, building a new sheet, owner review, then ordering from reps/sites.**

### **Narration**

At first the client thought they needed a completely new system because supply ordering involves comparing prior orders/latest prices, building a new sheet, owner review, then ordering from reps/sites. They did not. Their existing tools already held the right data; the missing piece was intelligence between them. Review stock/order history, compare pricing, prepare 'to order' list, call/order online. So we added a aI dental-supply purchasing copilot. Under the hood, The system learns the clinic's approved items, supplier aliases and historical prices from invoices. Staff can type or photograph what is low. AI maps the request to the exact catalog item, compares current supplier offers and explains price/pack changes; owner approves the order. That means the AI never gets to silently make the final business decision. It produces a structured answer, confidence and evidence, then normal code handles the predictable next step. AI removes the catalog-search and naming headache while the owner keeps control of brand, quantity and purchase. This is the kind of AI automation I like most: invisible enough that staff keep their normal workflow, but smart enough to remove the repetitive interpretation in the middle.

### **Backend — what we actually built**

* The system learns the clinic's approved items, supplier aliases and historical prices from invoices.  
* Staff can type or photograph what is low.  
* AI maps the request to the exact catalog item, compares current supplier offers and explains price/pack changes; owner approves the order.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Inventory sheet \+ supplier price files/invoices \+ vision/text AI \+ comparison code

**1\.** Create 20 fake dental supplies with aliases and two supplier price files.

**2\.** Enter 'blue microbrushes' or upload an item photo, map it to the approved SKU and compare unit-normalized supplier prices.

**3\.** Draft, do not submit, the order.

## **PAIN-085 — AI cash anomaly explainer**

**Pain: Cash collection, count and deposit are manually logged/signed to detect discrepancies.**

### **Narration**

One of the easiest ways to find a good AI automation is to watch what somebody does every Friday. In this client scenario, the recurring headache was cash collection, count and deposit are manually logged/signed to detect discrepancies. By the time the task started, record collected cash, two-person count/signoff and deposit amount in paper/spreadsheet. We replaced the repetitive middle with a aI cash anomaly explainer. Code compares PMS cash payments, drawer count and bank deposit. AI only examines exceptions and supporting notes to explain likely reasons—late deposit, refund, split tender, missing signoff—without clearing the discrepancy automatically. The model is not there to be clever for the sake of it; it is there because the input is inconsistent, handwritten, conversational or differently named. Once the information becomes structured, normal code takes over. The control becomes stronger because AI focuses attention; it does not replace two-person cash verification. A viewer can build the small version with exports and sample files. The production version is where we connect the same logic to the client's real tools and put monitoring, permissions and human review around it.

### **Backend — what we actually built**

* Code compares PMS cash payments, drawer count and bank deposit.  
* AI only examines exceptions and supporting notes to explain likely reasons—late deposit, refund, split tender, missing signoff—without clearing the discrepancy automatically.

### **Viewer DIY — easiest version to build**

**Suggested stack:** PMS cash export \+ count/deposit sheet \+ Python \+ AI exception summary

**1\.** Create a week of fake cash totals with two mismatches.

**2\.** Reconcile deterministically and give AI only the mismatched day plus notes.

**3\.** Return 'Possible explanation / Evidence / Required human check'.

## **PAIN-086 — AI patient-payment matcher for online card transactions**

**Pain: Online card transactions are manually posted into OpenDental.**

### **Narration**

We discovered this problem only because the client showed us a mistake that had already happened. The root cause was online card transactions are manually posted into OpenDental. Their team was look at processor transactions and enter payment/patient/reference into PMS one by one. Instead of adding another checklist, we built a aI patient-payment matcher for online card transactions. Processor transactions may carry partial names, email or reference text that do not exactly match the PMS. AI uses those clues plus amount/date/open balances to propose likely patient matches. Staff confirms before any payment is posted. What I like about this architecture is that it is explicit about uncertainty. High-confidence, rule-safe cases can flow through; questionable cases are surfaced with the reason the system is unsure. The staff stop searching every transaction manually, while the final financial posting remains supervised. That is a much better use of AI than asking a model to 'do everything'. It makes the messy information legible, then lets the business keep control of the important action.

### **Backend — what we actually built**

* Processor transactions may carry partial names, email or reference text that do not exactly match the PMS.  
* AI uses those clues plus amount/date/open balances to propose likely patient matches.  
* Staff confirms before any payment is posted.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Processor CSV \+ fictional patient/open-balance export \+ AI matching

**1\.** Create 15 fake card transactions and patient balances with three ambiguous names.

**2\.** Exact-match known references first; use AI to propose candidates for the rest.

**3\.** Display patient, amount, evidence and confidence with an Approve column.

## **PAIN-087 — AI remittance-to-claim exception engine**

**Pain: Every insurance payment line is manually searched in PMS and balance/action updated, taking hours daily.**

### **Narration**

The client described this as 'just admin', but it was happening often enough to deserve a proper solution: every insurance payment line is manually searched in PMS and balance/action updated, taking hours daily. The workflow was for each report line: search patient/claim, enter paid/date, update balance, decide whether follow-up is needed. Our approach was a aI remittance-to-claim exception engine. AI reads insurer EOB/remittance lines and identifies patient, procedure/date, allowed/paid/adjustment/denial text. Code matches the line to claims and calculates differences. The queue shows underpayment, denial, missing claim or ambiguous match rather than asking staff to search every patient. We deliberately separated understanding from execution. The AI reads, interprets or matches; deterministic logic validates numbers, dates and permissions; a human gets the final say on exceptions. AI turns the insurer's document into structured evidence; deterministic rules decide which lines need human follow-up. The DIY build is useful because it lets the owner test the idea with a handful of records. If it works, the custom integration can remove the upload, copy-paste and manual trigger altogether.

### **Backend — what we actually built**

* AI reads insurer EOB/remittance lines and identifies patient, procedure/date, allowed/paid/adjustment/denial text.  
* Code matches the line to claims and calculates differences.  
* The queue shows underpayment, denial, missing claim or ambiguous match rather than asking staff to search every patient.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Synthetic EOB PDFs \+ claim export \+ document AI \+ Python reconciliation

**1\.** Create two fake EOBs and 20 claim rows.

**2\.** Extract each remittance line with page reference, match by patient/date/procedure/amount, and calculate expected-vs-paid differences.

**3\.** Keep denial/coverage interpretation for staff.

## **PAIN-088 — AI canonical insurance-plan builder**

**Pain: Insurance plan details may be entered twice for in-network/out-of-network and vary by provider/location.**

### **Narration**

This is a good example of why 'just automate it' is usually the wrong starting point. The client's actual pain was insurance plan details may be entered twice for in-network/out-of-network and vary by provider/location. They were copy plan fields/fee schedules/provider/location mappings repeatedly into PMS. If we had automated those clicks blindly, we would only have made the bad workflow faster. Instead we built a aI canonical insurance-plan builder. Plan documents and payer screens describe network levels, frequency limits and provider/location details differently. AI extracts those facts into one canonical plan profile and highlights contradictions between sources. Staff approves the profile before it is copied into PMS fields. The AI's job is to understand context; the software's job is to enforce the business rules. The clinic enters the plan once from a reviewed profile instead of retyping similar data into multiple variations. So the final workflow is not a flashy chatbot. It is a quiet system that knows when it has enough evidence to proceed and when it needs to ask a person.

### **Backend — what we actually built**

* Plan documents and payer screens describe network levels, frequency limits and provider/location details differently.  
* AI extracts those facts into one canonical plan profile and highlights contradictions between sources.  
* Staff approves the profile before it is copied into PMS fields.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Redacted sample plan docs \+ structured schema \+ document AI

**1\.** Create three fictional plan documents for the same employer/payer with one conflicting field.

**2\.** Extract into a fixed schema, compare sources, and show Conflict / Missing / Confirmed.

**3\.** Do not use the prototype to advise a patient on coverage.

## **PAIN-089 — AI dental-to-accounting journal mapper**

**Pain: Daily Eaglesoft figures are manually re-entered into QuickBooks because systems do not integrate.**

### **Narration**

The interesting part of this client case was that the software was not broken. The gap was between the software and the way people actually work. Daily Eaglesoft figures are manually re-entered into QuickBooks because systems do not integrate. Day to day, run daily dental report, type selected totals/categories into accounting system. We filled that gap with a aI dental-to-accounting journal mapper. The daily dental report contains production, collections and payment categories; QuickBooks wants accounting accounts. A reviewed mapping table controls the journal. AI handles only unusual/new report labels and explains where they likely belong; code builds and balances the journal draft. Because the AI output is structured and evidence-backed, the next step can be ordinary code: calculate, rename, file, sync or draft. AI handles changing labels around the edge while accounting logic and approval stay deterministic. That is the pattern I would teach in the Short: use AI where language, images or messy naming create ambiguity; use code everywhere else.

### **Backend — what we actually built**

* The daily dental report contains production, collections and payment categories; QuickBooks wants accounting accounts.  
* A reviewed mapping table controls the journal.  
* AI handles only unusual/new report labels and explains where they likely belong; code builds and balances the journal draft.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Synthetic Eaglesoft-style report \+ account mapping \+ Python \+ AI fallback

**1\.** Create five days of fake dental summary reports.

**2\.** Map known labels mechanically, ask AI about one unknown label with the approved account list, and generate a balanced journal-entry CSV for bookkeeper review.

## **PAIN-090 — AI unscheduled-treatment conversation intelligence**

**Pain: Unscheduled treatment is tracked in a separate spreadsheet with booked yes/no and reason.**

### **Narration**

A client in dental clinic brought us a process they had stopped questioning years ago. After checkout, manually add treatment to sheet and later update whether it was scheduled/reason not scheduled. The reason was unscheduled treatment is tracked in a separate spreadsheet with booked yes/no and reason. We rebuilt only the painful part as a aI unscheduled-treatment conversation intelligence. The system takes the unscheduled-treatment list and the front desk's follow-up notes/texts. AI classifies only the administrative reason—couldn't reach, wants later date, checking insurance, cost concern, already booked elsewhere—and suggests the next contact window based on the clinic's rules. There is no magic 'agent' making uncontrolled decisions here. The model turns unstructured business information into a reviewable structure, and the rest of the workflow follows explicit rules. The spreadsheet becomes a live follow-up queue built from conversations instead of another list staff must manually maintain. That makes it easy to demo, easy for a viewer to reproduce at small scale, and much easier to harden into a real client integration later.

### **Backend — what we actually built**

* The system takes the unscheduled-treatment list and the front desk's follow-up notes/texts.  
* AI classifies only the administrative reason—couldn't reach, wants later date, checking insurance, cost concern, already booked elsewhere—and suggests the next contact window based on the clinic's rules.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Synthetic treatment list \+ call/text notes \+ AI classification \+ follow-up sheet

**1\.** Create 15 fake patients and follow-up notes.

**2\.** Extract reason/status and map to a clinic-defined next-action rule.

**3\.** Show Today's Follow-ups with the original note attached.

**4\.** Never change clinical treatment recommendations.

# **Logistics / Freight**

## **PAIN-091 — AI PO-to-container allocation reader**

**Pain: A PO can span multiple containers, but the spreadsheet doesn't clearly show which line items are in which container.**

### **Narration**

The fastest way to explain this client problem is with the before-and-after. Before: track vessel/container separately, email supplier for item details, manually split long PO lines among containers. The underlying issue was a PO can span multiple containers, but the spreadsheet doesn't clearly show which line items are in which container. After: a aI PO-to-container allocation reader. Supplier packing lists, commercial invoices and PO lines describe products differently. AI maps document line items back to the canonical PO lines; code checks quantities across containers and flags unallocated, duplicated or over-shipped quantities. The important design choice is the handoff point. AI stops once it has interpreted the messy input and attached confidence/evidence. Code takes over for exact calculations or updates, and a person handles anything uncertain. The coordinator gets a container-level truth table without manually reconstructing the PO from supplier emails. That one separation is what makes the prototype feel impressive without becoming unsafe or impossible for the audience to understand.

### **Backend — what we actually built**

* Supplier packing lists, commercial invoices and PO lines describe products differently.  
* AI maps document line items back to the canonical PO lines; code checks quantities across containers and flags unallocated, duplicated or over-shipped quantities.

### **Viewer DIY — easiest version to build**

**Suggested stack:** PO CSV \+ packing-list PDFs \+ document AI \+ Python

**1\.** Create one PO split across three fake packing lists with a quantity error.

**2\.** Extract each line, map it to PO SKU/description, and calculate allocated vs ordered quantity.

**3\.** Show the one discrepancy with document/page evidence.

## **PAIN-092 — AI import-status synthesizer across everyone's spreadsheets**

**Pain: Each colleague keeps a separate import spreadsheet because shared Excel is unpleasant, creating fragmented tracking.**

### **Narration**

The client did not ask us for AI. They asked us to stop each colleague keeps a separate import spreadsheet because shared Excel is unpleasant, creating fragmented tracking. That distinction changed the solution. Their team was maintain own ETA/container/status sheet and email updates; consolidate manually when needed. We used a aI import-status synthesizer across everyone's spreadsheets because the bottleneck involved information that was too inconsistent for simple rules. Rather than forcing a new shared tool immediately, the system reads each colleague's spreadsheet, recognizes equivalent fields and shipment IDs, and creates one synthesized view. When two people disagree on ETA/status, AI explains the conflict and shows both sources. Once the AI converts that mess into structured data, the rest is intentionally boring software. The first automation is a read-only coordination layer, so adoption does not depend on everyone changing how they work on day one. For a Short, I would show the messy input first, then the AI's structured interpretation, then the tiny exception list. That tells the audience exactly where the intelligence lives.

### **Backend — what we actually built**

* Rather than forcing a new shared tool immediately, the system reads each colleague's spreadsheet, recognizes equivalent fields and shipment IDs, and creates one synthesized view.  
* When two people disagree on ETA/status, AI explains the conflict and shows both sources.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Multiple Excel files \+ AI schema/entity mapping \+ Python dashboard

**1\.** Create three colleague trackers with different column names and one conflicting ETA.

**2\.** Normalize them into a common shipment schema and display conflicts without overwriting anyone's file.

## **PAIN-093 — AI shipment-email thread memory**

**Pain: Important supplier/forwarder information gets lost in long email threads and folders.**

### **Narration**

This client case had a very specific failure point: important supplier/forwarder information gets lost in long email threads and folders. It was not happening because staff were careless. The process itself required them to sort email into subfolders, remember next action, occasionally miss a PO/update. We solved that with a aI shipment-email thread memory. The agent groups emails and attachments by PO, booking, container or BL number, then reads the latest thread to extract current ETA, document status and next promised action. It marks stale promises—'will send BL tomorrow' from four days ago—and drafts the right follow-up. The system is designed to prove its work—source link, reason or confidence—before anything important happens. The AI is acting like a memory layer over the inbox, not sending autonomous freight instructions. That makes the same idea useful as a DIY prototype and credible as a professional integration, because the viewer can see that we are not just wrapping a prompt around a spreadsheet.

### **Backend — what we actually built**

* The agent groups emails and attachments by PO, booking, container or BL number, then reads the latest thread to extract current ETA, document status and next promised action.  
* It marks stale promises—'will send BL tomorrow' from four days ago—and drafts the right follow-up.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Test Gmail mailbox/export \+ AI thread reasoning \+ shipment master

**1\.** Create four fake email threads with shipment references and delayed promises.

**2\.** Extract Latest Status, Last Promise, Due Date and Next Action.

**3\.** Show only shipments whose promise date passed or required document is missing.

## **PAIN-094 — AI 3PL charge semantic auditor**

**Pain: 3PL invoices must be checked against originally quoted unit prices.**

### **Narration**

I like this case because the best solution was not obvious from the pain. 3PL invoices must be checked against originally quoted unit prices. The client's routine was open monthly invoice and rate/quote file, compare line items/units manually. Rather than automating the routine literally, we changed where the decision happens by building a aI 3PL charge semantic auditor. 3PL invoices and rate cards use inconsistent charge names—pick fee, order handling, carton pick, outbound processing. AI maps each invoice charge to the approved rate concept; code recalculates the expected amount from quantity/unit and flags new fees or rate mismatches. Now AI performs the interpretation at the moment the data arrives, and the downstream steps become simple rules. AI solves the vocabulary mismatch; the money check itself is exact and auditable. That is the kind of redesign that makes a one-minute story worth sharing: the audience sees not just a tool, but a better way to structure the work.

### **Backend — what we actually built**

* 3PL invoices and rate cards use inconsistent charge names—pick fee, order handling, carton pick, outbound processing.  
* AI maps each invoice charge to the approved rate concept; code recalculates the expected amount from quantity/unit and flags new fees or rate mismatches.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Rate card PDF/CSV \+ 3PL invoice \+ AI charge mapping \+ Python

**1\.** Create a rate card and invoice with renamed charges and two deliberate errors.

**2\.** Map charge semantics, calculate expected totals deterministically, and output Rate Mismatch, Quantity Mismatch and Unknown Fee.

## **PAIN-095 — AI multimodal freight-quote normalizer**

**Pain: Freight quotes arrive as PDF, merged-cell Excel and WhatsApp and are retyped into one master comparison sheet.**

### **Narration**

The client's team had accepted this as normal: read each quote, locate base freight and surcharges, manually type an apples-to-apples table for 3–5 quotes per shipment. But that normal behavior was hiding a real problem—freight quotes arrive as PDF, merged-cell Excel and WhatsApp and are retyped into one master comparison sheet. We built a aI multimodal freight-quote normalizer. PDF, Excel, email and WhatsApp quotes all go through one intake. AI extracts lane, equipment, base freight, surcharges, transit, free days and validity, then reasons whether each quote is complete enough to compare. Code converts currencies/units and calculates comparable totals. The system does not replace the employee's judgment; it compresses the amount of information they have to judge. The AI understands four different commercial languages; code prevents an incomplete quote from being crowned the cheapest. In a DIY version you can demonstrate the exact same architecture with five fake records. In the production version the inputs simply arrive automatically from the real business systems.

### **Backend — what we actually built**

* PDF, Excel, email and WhatsApp quotes all go through one intake.  
* AI extracts lane, equipment, base freight, surcharges, transit, free days and validity, then reasons whether each quote is complete enough to compare.  
* Code converts currencies/units and calculates comparable totals.

### **Viewer DIY — easiest version to build**

**Suggested stack:** n8n \+ email/file input \+ vision/text AI \+ Python/Sheets

**1\.** Prepare four fake quotes in four formats.

**2\.** Extract them into one JSON schema, mark missing destination charges as INCOMPLETE, and calculate totals only for comparable quotes.

**3\.** Show source evidence for every fee.

## **PAIN-096 — AI invoice-payment identity matcher for ops**

**Pain: Ops cannot easily tell whether a sent invoice is still unpaid without asking accounts or checking manually.**

### **Narration**

This was one of those workflows where adding more software would have made things worse. The client already had tools; what they lacked was a way to understand the information moving between them. Maintain Excel/reminders and periodically ask finance/check payment status. That created ops cannot easily tell whether a sent invoice is still unpaid without asking accounts or checking manually. Our fix was a aI invoice-payment identity matcher for ops. The operations invoice register and accounting payment export rarely line up by the same reference. AI uses customer, amount, invoice number fragments and remittance text to propose matches. Code calculates age only after identity is established. The model's output is not the final answer—it is a structured proposal with evidence. Ops can see what is genuinely unpaid without constantly asking accounting for a manual status check. That is the story I would tell: we did not sell them another dashboard; we made the systems they already pay for work together intelligently.

### **Backend — what we actually built**

* The operations invoice register and accounting payment export rarely line up by the same reference.  
* AI uses customer, amount, invoice number fragments and remittance text to propose matches.  
* Code calculates age only after identity is established.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Ops invoice CSV \+ accounting/payment CSV \+ AI matching \+ Python

**1\.** Create 20 invoices and payment rows with altered references and one partial payment.

**2\.** Exact-match invoice numbers first, AI-match the remaining candidates, and show Paid, Partial, Overdue and Review.

## **PAIN-097 — AI shipment-update composer with document verification**

**Pain: Shipment documents in a folder and ETA/ETD spreadsheet updates lead to repetitive templated emails.**

### **Narration**

If you only looked at this process once, you might ignore it. But the client repeated it constantly: update every ETA/ETD cell; check docs exist; attach/send the same style email. Eventually that led to shipment documents in a folder and ETA/ETD spreadsheet updates lead to repetitive templated emails. We built a aI shipment-update composer with document verification. The system reads the current tracker row and approved shipment documents, verifies that the attachment set matches the shipment, and drafts the routine customer update in the company's style. AI summarizes changes; code attaches only files whose shipment ID matches. I would show the backend in one sentence on screen: messy input goes to AI, AI returns structured facts plus confidence, normal code runs the business rule, and the human sees exceptions. The email becomes the last step of a verified shipment state, not another place staff retype the same ETA. That is simple enough for the audience to follow but deep enough to show there is real integration work behind it.

### **Backend — what we actually built**

* The system reads the current tracker row and approved shipment documents, verifies that the attachment set matches the shipment, and drafts the routine customer update in the company's style.  
* AI summarizes changes; code attaches only files whose shipment ID matches.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Shipment tracker \+ document folder \+ AI \+ email draft workflow

**1\.** Create three fake shipment folders and a tracker.

**2\.** Extract document IDs, check required files, and have AI draft a concise ETA/ETD update from structured fields.

**3\.** Generate an email draft but do not send automatically.

## **PAIN-098 — AI import-exception agent**

**Pain: Import status depends on remembering where each shipment stands across origin, vessel, container, ETA and warehouse.**

### **Narration**

The client showed us the end result first: a spreadsheet, folder or queue that took far too much effort to keep correct. The cause was import status depends on remembering where each shipment stands across origin, vessel, container, ETA and warehouse. Behind it, staff had to maintain manual tracker and chase updates from forwarders/suppliers. We attacked the cause with a aI import-exception agent. The system listens to new forwarder/supplier messages and compares them with the shipment master. AI identifies meaningful state changes—booking confirmed, rolled vessel, customs hold, arrival notice—and updates a proposed timeline. Code flags shipments whose ETA passed or whose next milestone lacks evidence. Because the AI is grounded in the client's own records and rules, it can interpret business-specific language without becoming the source of truth itself. The coordinator stops relying on memory because the tracker is fed by the conversations that actually change shipment status. The audience can reproduce the prototype with exports; the professional version connects those same steps to live systems with security and monitoring.

### **Backend — what we actually built**

* The system listens to new forwarder/supplier messages and compares them with the shipment master.  
* AI identifies meaningful state changes—booking confirmed, rolled vessel, customs hold, arrival notice—and updates a proposed timeline.  
* Code flags shipments whose ETA passed or whose next milestone lacks evidence.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Email/message export \+ shipment tracker \+ AI event extraction \+ rules

**1\.** Create ten fake shipments and six update messages.

**2\.** Extract Shipment ID, Event, New Date, Evidence and Confidence.

**3\.** Apply updates to a proposed view and show only late/stale/uncertain shipments.

## **PAIN-099 — AI freight-cost classifier against budget**

**Pain: Freight invoices across fulfillment/parcel/LTL/FTL/returns are manually entered against budget.**

### **Narration**

Here is what made this client problem interesting: the data already existed, but not in a form the next step could use. Freight invoices across fulfillment/parcel/LTL/FTL/returns are manually entered against budget. Staff were type invoice totals/cost categories into spreadsheet and compare budget/actual. We built a aI freight-cost classifier against budget to translate that messy information into a clean intermediate structure. Carrier invoices contain many fee descriptions across parcel, LTL, FTL, fulfillment and returns. AI maps each charge to the company's fixed budget categories and identifies genuinely new fees. Code sums actual vs budget and writes a variance report. From there, deterministic code handles the rest. AI makes the messy invoice language comparable; finance sees the exact category that is driving the budget variance. That is the core AI-integration lesson behind the case: do not ask the model to run the business; ask it to understand the part that ordinary software cannot understand reliably.

### **Backend — what we actually built**

* Carrier invoices contain many fee descriptions across parcel, LTL, FTL, fulfillment and returns.  
* AI maps each charge to the company's fixed budget categories and identifies genuinely new fees.  
* Code sums actual vs budget and writes a variance report.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Carrier invoices/CSVs \+ budget map \+ AI classification \+ Python

**1\.** Create 30 fake freight charge lines with varied descriptions.

**2\.** Map them to a fixed budget taxonomy, calculate variance by mode/category, and show unknown/new charges separately.

**3\.** Keep all amounts deterministic.

## **PAIN-100 — AI quote-intake agent with rate-table grounding**

**Pain: 30–40 quote requests/day use Outlook/Excel email templates, manual sequential quote numbers and weekly conversion counting.**

### **Narration**

The client initially described the task as 'copying information'. When we looked closer, the hard part was not copying at all—it was deciding what the information meant. 30–40 quote requests/day use Outlook/Excel email templates, manual sequential quote numbers and weekly conversion counting. Their current process was choose email signature/template, increment quote number, send; later inspect number sequence and manually collect wins/losses. So we built a aI quote-intake agent with rate-table grounding. Incoming quote requests are read from email: origin, destination, cargo, mode, weight, dates and missing facts. AI extracts the request and asks only the necessary clarification. Once complete, code pulls approved rates, generates the next quote ID and calculates the price; AI drafts the customer-facing email. Once meaning becomes structured, every later step can be boring, testable code. AI handles messy customer language and the email; the commercial rate calculation stays grounded in the company's own table. That is also why the DIY version is approachable: start with sample exports, make the interpretation visible, and only automate the final handoff once you trust it.

### **Backend — what we actually built**

* Incoming quote requests are read from email: origin, destination, cargo, mode, weight, dates and missing facts.  
* AI extracts the request and asks only the necessary clarification.  
* Once complete, code pulls approved rates, generates the next quote ID and calculates the price; AI drafts the customer-facing email.

### **Viewer DIY — easiest version to build**

**Suggested stack:** Shared quote inbox \+ AI extraction \+ approved rate table \+ Python \+ email drafts

**1\.** Create five fake quote-request emails and a small rate table.

**2\.** Extract shipment fields, return Need Clarification when a required field is missing, otherwise calculate a deterministic price and generate a numbered quote draft.

**3\.** Track reply outcome manually in the prototype.