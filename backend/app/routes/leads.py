from fastapi import APIRouter, BackgroundTasks
from datetime import datetime
from bson.objectid import ObjectId

from app.models.lead import LeadSchema
from app.utils.db import db

from app.services.scraper_sync import scrape_website
from app.services.ai_service import generate_company_insights
from app.services.pdf_service import generate_pdf
from app.services.email_service import send_report_email
from app.services.sheets_service import log_lead_to_sheet
from app.services.drive_service import upload_pdf_to_drive

router = APIRouter()


async def process_lead(lead_id, data):

    try:
        print(f"\n{'='*60}")
        print(f"[{lead_id}] 🚀 PROCESSING LEAD")
        print(f"{'='*60}")
        
        print(f"[{lead_id}] ⏱️  Status: processing")
        print(f"[{lead_id}] 🔗 Website: {data.website}")
        print(f"[{lead_id}] Step 1: Scraping website...") 
        scraped_data = scrape_website(
            data.website
        )
        print(f"[{lead_id}] ✓ Scraped successfully")
        
        # STEP 1: Verify extraction data
        print(f"\n[{lead_id}] 📊 EXTRACTION VERIFICATION:")
        print(f"[{lead_id}] - Has error: {'error' in scraped_data}")
        if 'error' in scraped_data:
            print(f"[{lead_id}] ❌ ERROR: {scraped_data['error']}")
        print(f"[{lead_id}] - Title: {scraped_data.get('title', 'N/A')}")
        print(f"[{lead_id}] - Meta: {scraped_data.get('meta_description', 'N/A')[:50]}")
        print(f"[{lead_id}] - Hero headings: {len(scraped_data.get('hero_headings', []))}") 
        print(f"[{lead_id}] - Buttons: {len(scraped_data.get('buttons', []))}")
        print(f"[{lead_id}] - Nav items: {len(scraped_data.get('nav_items', []))}") 
        print(f"[{lead_id}] - Screenshot: {bool(scraped_data.get('screenshot_path'))}")
        if scraped_data.get('hero_headings'):
            print(f"[{lead_id}] - First hero: {scraped_data['hero_headings'][0][:60]}...")
        print(f"[{lead_id}] - Deterministic scores: {list(scraped_data.get('deterministic_scores', {}).keys())}")
        
        # CHECK: If URL is invalid or website unreachable, stop processing
        if 'error' in scraped_data and scraped_data.get('error_type') in ['INVALID_URL', 'WEBSITE_UNREACHABLE']:
            error_msg = scraped_data.get('error', 'Unknown error')
            error_type = scraped_data.get('error_type', 'UNKNOWN')
            
            print(f"\n{'='*60}")
            print(f"[{lead_id}] ⚠️  VALIDATION FAILED - {error_type}")
            print(f"[{lead_id}] {error_msg}")
            print(f"{'='*60}\n")
            
            # Save error to MongoDB
            await db.leads.update_one(
                {"_id": ObjectId(lead_id)},
                {
                    "$set": {
                        "status": "validation_failed",
                        "error": error_msg,
                        "error_type": error_type,
                        "failed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return  # Stop processing, don't generate PDF or send email

        print(f"[{lead_id}] Step 2: Generating AI insights...")
        insights = generate_company_insights(
            scraped_data
        )
        print(f"[{lead_id}] ✓ AI insights generated")

        print(f"[{lead_id}] Step 3: Creating PDF...")
        pdf_path = generate_pdf(
            company=data.company,
            summary=scraped_data.get(
                "meta_description",
                ""
            ),
            insights=insights,
            website=data.website,
            deterministic_scores=scraped_data.get(
                "deterministic_scores"
            ),
            screenshot_path=scraped_data.get(
                "screenshot_path"
            ),
            extracted_data=scraped_data
        )
        print(f"[{lead_id}] ✓ PDF created at: {pdf_path}")

        print(f"[{lead_id}] Step 4: Uploading PDF to Google Drive...")
        drive_link = None
        try:
            drive_link = upload_pdf_to_drive(
                pdf_path,
                f"{data.company}.pdf"
            )
            if drive_link:
                print(f"[{lead_id}] ✓ Drive link: {drive_link}")
            else:
                print(f"[{lead_id}] ⚠ Drive upload skipped (optional service)")
        except Exception as drive_error:
            print(f"[{lead_id}] ⚠ Drive upload failed: {str(drive_error)}")
            print(f"[{lead_id}] ⚠ Continuing without Drive link...")

        print(f"[{lead_id}] Step 5: Sending email...")
        email_response = send_report_email(
            to_email=data.email,
            company=data.company,
            pdf_path=pdf_path
        )
        print(f"[{lead_id}] ✓ Email sent successfully")

        await db.leads.update_one(
            {"_id": ObjectId(lead_id)},
            {
                "$set": {
                    "scraped_data": scraped_data,
                    "ai_insights": insights,
                    "pdf_path": pdf_path,
                    "drive_link": drive_link,
                    "email_response": email_response,
                    "status": "completed",
                    "updated_at": datetime.utcnow()
                }
            }
        )

        print(f"[{lead_id}] Step 6: Logging to Google Sheets...")
        
        lead_data = {
            "name": data.name,
            "email": data.email,
            "company": data.company,
            "website": data.website,
            "status": "completed",
            "drive_link": drive_link,
            "created_at": datetime.utcnow()
        }
        
        try:
            log_lead_to_sheet(lead_data)
            print(f"[{lead_id}] ✓ Logged to Google Sheets")
        except Exception as sheets_error:
            print(f"[{lead_id}] ⚠ Sheets logging failed: {str(sheets_error)}")

        print(f"\n{'='*60}")
        print(f"[{lead_id}] ✅ SUCCESS: All steps completed")
        print(f"[{lead_id}] Status: completed")
        print(f"{'='*60}\n")

    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        print(f"\n{'='*60}")
        print(f"[{lead_id}] ❌ FAILED ({error_type})")
        print(f"[{lead_id}] Status: failed")
        print(f"[{lead_id}] Error: {error_msg}")
        print(f"{'='*60}\n")
        import traceback
        print(traceback.format_exc())
        
        await db.leads.update_one(
            {"_id": ObjectId(lead_id)},
            {
                "$set": {
                    "status": "failed",
                    "error": error_msg,
                    "error_type": error_type,
                    "failed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )


@router.post("/leads")
async def create_lead(
    data: LeadSchema,
    background_tasks: BackgroundTasks
):

    lead = {
        "name": data.name,
        "email": data.email,
        "company": data.company,
        "website": data.website,
        "notes": data.notes,
        "status": "processing",
        "created_at": datetime.utcnow()
    }

    result = await db.leads.insert_one(lead)
    lead_id = str(result.inserted_id)
    
    print(f"\n📝 New lead created: {lead_id}")
    print(f"📝 Company: {data.company}")
    print(f"📝 Status: processing")
    print(f"📝 Queued for background processing...")

    background_tasks.add_task(
        process_lead,
        lead_id,
        data
    )

    return {
        "success": True,
        "lead_id": lead_id,
        "message": "Audit generation started"
    }


@router.get("/leads/{lead_id}")
async def get_lead_status(lead_id: str):
    """Get lead status and error details."""
    try:
        lead = await db.leads.find_one(
            {"_id": ObjectId(lead_id)}
        )
        
        if not lead:
            return {
                "success": False,
                "error": "Lead not found"
            }
        
        return {
            "success": True,
            "lead_id": lead_id,
            "status": lead.get("status", "unknown"),
            "company": lead.get("company", ""),
            "website": lead.get("website", ""),
            "error": lead.get("error", ""),
            "error_type": lead.get("error_type", ""),
            "created_at": lead.get("created_at"),
            "updated_at": lead.get("updated_at"),
            "pdf_path": lead.get("pdf_path", ""),
            "drive_link": lead.get("drive_link", "")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
