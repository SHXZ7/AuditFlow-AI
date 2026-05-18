import os
from groq import Groq
from dotenv import load_dotenv
import time
import json

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def generate_company_insights(data):

    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"🤖 AI Service: Retry attempt {attempt} (waiting {retry_delay}s)")
                time.sleep(retry_delay)
                retry_delay *= 2
            
            print(f"🤖 AI Service: Generating insights (attempt {attempt + 1}/{max_retries})")

            business_signals = data.get("business_signals") or {}
            strategic_signals = business_signals.get("strategic_signals") or {}
            semantic_sections = data.get("semantic_sections") or {}
            deterministic_scores = data.get("deterministic_scores") or {}
            cta_hierarchy = data.get("cta_hierarchy") or business_signals.get("cta_hierarchy") or {}

            website_context = {
                "identity": {
                    "url": data.get("url"),
                    "title": data.get("title"),
                    "meta_description": data.get("meta_description")
                },
                "positioning": {
                    "hero_headings": data.get("hero_headings"),
                    "headings": data.get("headings"),
                    "hero_section": semantic_sections.get("hero_section")
                },
                "cta_buttons": data.get("buttons"),
                "cta_hierarchy": cta_hierarchy,
                "navigation": {
                    "items": data.get("nav_items"),
                    "footer_links": semantic_sections.get("footer_links")
                },
                "semantic_sections": {
                    "pricing_section": semantic_sections.get("pricing_section"),
                    "testimonials_section": semantic_sections.get("testimonials_section")
                },
                "product_signals": {
                    "product_keywords": business_signals.get("product_signals"),
                    "ai_keywords": business_signals.get("ai_signals"),
                    "conversion_keywords": business_signals.get("conversion_signals"),
                    "trust_keywords": business_signals.get("trust_signals"),
                    "growth_keywords": business_signals.get("growth_signals")
                },
                "forms": {
                    "count": data.get("forms"),
                    "field_count": data.get("form_fields"),
                    "has_forms": business_signals.get("has_forms")
                },
                "seo_signals": {
                    "has_title": bool(data.get("title")),
                    "has_meta_description": bool(data.get("meta_description")),
                    "has_blog_or_resources": strategic_signals.get("has_blog"),
                    "links": data.get("links")
                },
                "conversion_signals": {
                    "primary_ctas": business_signals.get("primary_ctas"),
                    "has_pricing_page": strategic_signals.get("has_pricing_page"),
                    "has_demo_cta": strategic_signals.get("has_demo_cta"),
                    "has_free_trial": strategic_signals.get("has_free_trial"),
                    "has_login_signup": strategic_signals.get("has_login_signup"),
                    "has_lead_capture_forms": strategic_signals.get("has_lead_capture_forms")
                },
                "trust_signals": {
                    "has_testimonials": strategic_signals.get("has_testimonials"),
                    "testimonials_section": semantic_sections.get("testimonials_section")
                },
                "deterministic_scores": deterministic_scores,
                "visual_evidence": data.get("visual_evidence"),
                "supporting_content": {
                    "ai_ready_context": data.get("ai_ready_context"),
                    "page_content_excerpt": data.get("content")
                }
            }

            prompt = f"""
You are a senior AI growth consultant helping B2B companies improve:
- conversion rates
- positioning
- onboarding
- automation
- lead generation

Your task is to generate a highly personalized business audit.

DO NOT give generic startup advice.

Base every insight ONLY on the provided website data.

CRITICAL ACCURACY RULES:
- Only make observations directly supported by the extracted website content.
- Do not invent missing features, pages, customer types, integrations, metrics, testimonials, pricing, or product capabilities.
- Do not assume missing sections exist.
- If a section is missing, say it appears absent from the extracted content and explain why that matters.
- If the evidence is weak or unclear, use cautious language such as "the extracted page suggests" or "based on visible content."
- Scores are already calculated deterministically in WEBSITE_DATA.deterministic_scores.
- Do not change, inflate, or invent scores.
- Use the exact deterministic score values in the SCORECARDS section.
- Your job is to explain WHY each deterministic score is justified using its evidence and the extracted website content.
- Do not mention information that is not present in the Website Data below.

Mention:
- messaging clarity
- CTA quality
- positioning
- conversion opportunities
- UX observations
- automation opportunities
- growth suggestions

Be specific and practical.

Return this format:

COMPANY SUMMARY:
...

SCORECARDS:
- Website Clarity: use WEBSITE_DATA.deterministic_scores["Website Clarity"].score/10 - explain using evidence
- CTA Effectiveness: use WEBSITE_DATA.deterministic_scores["CTA Effectiveness"].score/10 - explain using evidence
- Automation Readiness: use WEBSITE_DATA.deterministic_scores["Automation Readiness"].score/10 - explain using evidence
- Growth Potential: use WEBSITE_DATA.deterministic_scores["Growth Potential"].score/10 - explain using evidence

WEBSITE POSITIONING:
...

CTA & CONVERSION ANALYSIS:
...

UX OBSERVATIONS:
...

GROWTH OPPORTUNITIES:
...

AI AUTOMATION OPPORTUNITIES:
...

HIGH-IMPACT RECOMMENDATIONS:
...

Use the deterministic scores out of 10 from WEBSITE_DATA.deterministic_scores.
Include a short reason after each score, but do not alter the score values.
Scorecard output example: Website Clarity: 7/10 - Clear hero copy is present, but pricing evidence is limited.

Website Data is provided as structured JSON-like content below.
Use the field names to reason carefully:
- TITLE and META DESCRIPTION are in identity.
- HEADINGS and HERO SECTION are in positioning.
- CTA BUTTONS are in cta_buttons and conversion_signals.primary_ctas.
- CTA HIERARCHY is in cta_hierarchy. Use it to identify the first CTA, hero CTA emphasis, navbar items, and button priority.
- NAVIGATION is in navigation.
- PRODUCT SIGNALS are in product_signals.
- FORMS are in forms.
- SEO SIGNALS are in seo_signals.
- TRUST SIGNALS are in trust_signals.
- DETERMINISTIC SCORES are in deterministic_scores.
- VISUAL EVIDENCE indicates whether a homepage screenshot was captured for the PDF.

WEBSITE_DATA:
```json
{json.dumps(website_context, indent=2)}
```
"""

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5
            )

            result = completion.choices[0].message.content
            print(f"🤖 AI Service: ✓ Insights generated successfully")
            return result
            
        except Exception as e:
            print(f"🤖 AI Service: ⚠ Error on attempt {attempt + 1}: {type(e).__name__}: {str(e)}")
            if attempt == max_retries - 1:
                print(f"🤖 AI Service: ✗ Failed after {max_retries} attempts")
                raise
            continue
