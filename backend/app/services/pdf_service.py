from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import os
import re
from urllib.parse import urlparse


SECTION_TITLES = [
    "COMPANY SUMMARY",
    "SCORECARDS",
    "WEBSITE POSITIONING",
    "CTA & CONVERSION ANALYSIS",
    "UX OBSERVATIONS",
    "WEBSITE STRENGTHS",
    "WEBSITE WEAKNESSES",
    "GROWTH OPPORTUNITIES",
    "AI AUTOMATION IDEAS",
    "AI AUTOMATION OPPORTUNITIES",
    "HIGH-IMPACT RECOMMENDATIONS",
    "PERSONALIZED RECOMMENDATIONS"
]

SCORECARD_LABELS = [
    "Website Clarity",
    "CTA Effectiveness",
    "Automation Readiness",
    "Growth Potential"
]


def _split_insights(insights):
    sections = []
    current_title = "Executive Insights"
    current_lines = []

    for line in insights.splitlines():
        clean_line = line.strip()
        normalized = clean_line.rstrip(":").upper()

        if normalized in SECTION_TITLES:
            if current_lines:
                _append_section(sections, current_title, current_lines)

            current_title = clean_line.rstrip(":").title()
            current_lines = []
            continue

        if clean_line:
            current_lines.append(clean_line)

    if current_lines:
        _append_section(sections, current_title, current_lines)

    return sections or [
        {
            "title": "Executive Insights",
            "items": [insights]
        }
    ]


def _append_section(sections, title, lines):
    if title.upper() == "SCORECARDS":
        return

    sections.append(
        {
            "title": title,
            "items": _format_items(lines)
        }
    )


def _format_items(lines):
    items = []

    for line in lines:
        item = re.sub(r"^[-*]\s*", "", line).strip()

        if item:
            items.append(item)

    return items


def _extract_scorecards(insights):
    scorecards = []

    for label in SCORECARD_LABELS:
        pattern = rf"{re.escape(label)}\s*:\s*(\d+(?:\.\d+)?)\s*/\s*10(?:\s*[-–:]\s*(.*))?"
        match = re.search(pattern, insights, re.IGNORECASE)

        if match:
            score = min(10, max(0, float(match.group(1))))
            reason = match.group(2).strip() if match.group(2) else ""
        else:
            score = _fallback_score(label)
            reason = _fallback_reason(label)

        scorecards.append(
            {
                "label": label,
                "score": int(score) if (isinstance(score, float) and score.is_integer()) or isinstance(score, int) else score,
                "percent": int(score * 10),
                "reason": reason or _fallback_reason(label)
            }
        )

    return scorecards


def _extract_scorecards(insights, deterministic_scores=None):
    scorecards = []
    deterministic_scores = deterministic_scores or {}

    for label in SCORECARD_LABELS:
        pattern = rf"{re.escape(label)}\s*:\s*(\d+(?:\.\d+)?)\s*/\s*10(?:\s*[-–:]\s*(.*))?"
        match = re.search(pattern, insights, re.IGNORECASE)
        deterministic = deterministic_scores.get(label, {})

        if deterministic.get("score") is not None:
            score = min(10, max(0, float(deterministic["score"])))
            reason = ""

            if match and match.group(2):
                reason = match.group(2).strip()
            elif deterministic.get("evidence"):
                reason = "; ".join(deterministic["evidence"])
        elif match:
            score = min(10, max(0, float(match.group(1))))
            reason = match.group(2).strip() if match.group(2) else ""
        else:
            score = _fallback_score(label)
            reason = _fallback_reason(label)

        scorecards.append(
            {
                "label": label,
                "score": int(score) if (isinstance(score, float) and score.is_integer()) or isinstance(score, int) else score,
                "percent": int(score * 10),
                "reason": reason or _fallback_reason(label)
            }
        )

    return scorecards


def _fallback_score(label):
    fallback_scores = {
        "Website Clarity": 8,
        "CTA Effectiveness": 7,
        "Automation Readiness": 9,
        "Growth Potential": 8
    }

    return float(fallback_scores[label])


def _fallback_reason(label):
    fallback_reasons = {
        "Website Clarity": "Messaging has enough structure to support a clear first-pass buyer narrative.",
        "CTA Effectiveness": "Primary conversion paths can be made sharper with stronger action-oriented prompts.",
        "Automation Readiness": "Lead capture, qualification, follow-up, and reporting are strong automation candidates.",
        "Growth Potential": "The business has multiple practical opportunities to improve conversion and efficiency."
    }

    return fallback_reasons[label]


def _build_metrics(scorecards):
    average_score = sum(card["score"] for card in scorecards) / len(scorecards)
    automation_score = next(
        card["score"]
        for card in scorecards
        if card["label"] == "Automation Readiness"
    )

    return [
        {
            "label": "Audit Score",
            "value": f"{average_score:.1f}/10",
            "detail": "Blended website and growth readiness"
        },
        {
            "label": "Automation Fit",
            "value": f"{int(automation_score * 10)}%",
            "detail": "Estimated AI workflow opportunity"
        },
        {
            "label": "Priority",
            "value": "30 Days",
            "detail": "Recommended implementation window"
        }
    ]


def _company_initials(company):
    words = re.findall(r"[A-Za-z0-9]+", company)

    if not words:
        return "AI"

    return "".join(word[0].upper() for word in words[:2])


def _safe_file_name(company):
    file_name = re.sub(r"[^A-Za-z0-9_-]+", "_", company).strip("_")
    return file_name or "audit_report"


def _file_uri(path):
    if not path:
        return None

    absolute_path = os.path.abspath(path)

    if not os.path.exists(absolute_path):
        return None

    return f"file:///{absolute_path.replace(os.sep, '/')}"


def generate_pdf(
    company,
    summary,
    insights,
    website=None,
    deterministic_scores=None,
    screenshot_path=None,
    extracted_data=None
):

    try:
        print(f"📄 PDF Service: Starting PDF generation for {company}")
        print(f"📄 PDF Service: Received extracted_data: {bool(extracted_data)}")
        if extracted_data and 'error' in extracted_data:
            print(f"📄 PDF Service: ❌ Scraper error detected: {extracted_data.get('error', 'Unknown')}")
        print(f"📄 PDF Service: Hero headings available: {len(extracted_data.get('hero_headings', []) if extracted_data else [])}")
        print(f"📄 PDF Service: Buttons available: {len(extracted_data.get('buttons', []) if extracted_data else [])}")
        print(f"📄 PDF Service: Nav items available: {len(extracted_data.get('nav_items', []) if extracted_data else [])}")
        
        logo = None
        if website:
            try:
                domain = urlparse(website).netloc or website
                logo_url = f"https://logo.clearbit.com/{domain}"
                print(f"📄 PDF Service: Logo URL: {logo_url}")
                
                # Try to verify the logo is accessible
                import requests
                try:
                    response = requests.head(logo_url, timeout=3)
                    if response.status_code == 200:
                        logo = logo_url
                        print(f"📄 PDF Service: ✅ Logo verified")
                    else:
                        print(f"📄 PDF Service: ⚠ Logo URL returned {response.status_code}")
                except Exception as e:
                    print(f"📄 PDF Service: ⚠ Logo verification failed: {str(e)}")
            except Exception as e:
                print(f"📄 PDF Service: ⚠ Logo generation failed: {str(e)}")
        
        env = Environment(
            loader=FileSystemLoader(
                "app/templates"
            )
        )

        template = env.get_template(
            "report.html"
        )

        scorecards = _extract_scorecards(
            insights,
            deterministic_scores
        )
        extracted_data = extracted_data or {}
        business_signals = extracted_data.get("business_signals", {})
        cta_hierarchy = (
            extracted_data.get("cta_hierarchy")
            or business_signals.get("cta_hierarchy")
            or {}
        )
        strategic_signals = business_signals.get("strategic_signals", {})
        semantic_sections = extracted_data.get("semantic_sections", {})

        # Extract website structure data
        hero_heading = extracted_data.get("hero_headings", [])[0] if extracted_data.get("hero_headings") else None
        primary_buttons = extracted_data.get("buttons", [])[:6]
        nav_items = extracted_data.get("nav_items", [])[:10]
        confidence = extracted_data.get("ai_ready_context", {}).get("confidence", 0) if isinstance(extracted_data.get("ai_ready_context"), dict) else 0
        
        logo_text = _company_initials(company)
        print(f"📄 PDF Service: Template variables:")
        print(f"   - logo_text: {logo_text}")
        print(f"   - logo: {logo}")
        print(f"   - hero_heading: {bool(hero_heading)}")
        print(f"   - buttons: {len(primary_buttons)}")
        print(f"   - nav_items: {len(nav_items)}")
        
        html_content = template.render(
            company=company,
            logo_text=logo_text,
            logo=logo,
            website=website,
            screenshot=_file_uri(screenshot_path),
            summary=summary,
            insights=insights,
            insight_sections=_split_insights(insights),
            scorecards=scorecards,
            metrics=_build_metrics(scorecards),
            cta_hierarchy=cta_hierarchy,
            strategic_signals=strategic_signals,
            semantic_sections=semantic_sections,
            visual_evidence=extracted_data.get("visual_evidence"),
            hero_heading=hero_heading,
            primary_buttons=primary_buttons,
            nav_items=nav_items,
            confidence=confidence,
            extracted_data=extracted_data
        )

        reports_dir = "reports"

        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
            print(f"📄 PDF Service: Created reports directory")

        file_path = f"{reports_dir}/{_safe_file_name(company)}.pdf"

        print(f"📄 PDF Service: Generating PDF at {file_path}")
        
        HTML(
            string=html_content
        ).write_pdf(file_path)

        print(f"📄 PDF Service: ✓ PDF generated successfully")
        
        return file_path
    
    except Exception as e:
        print(f"📄 PDF Service ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        raise
