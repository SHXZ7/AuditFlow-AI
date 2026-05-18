"""
Synchronous website scraper using requests + BeautifulSoup.

This module extracts structured data from websites without JavaScript rendering.
It implements a three-layer validation pipeline:
1. URL format validation (regex check)
2. Website accessibility check (HTTP status)
3. Content extraction (BeautifulSoup parsing)

Why synchronous?
- FastAPI background tasks on Windows don't support subprocess spawning
- Playwright requires asyncio.create_subprocess_exec (fails in thread pool context)
- Synchronous HTTP is simpler, reliable, and sufficient for static content

Trade-offs:
- No JavaScript rendering (acceptable for most marketing sites)
- Slightly lower performance (mitigated by short scraping time)
- Much higher reliability on Windows deployment

Extracted Data Structure:
{
  "title": "Company name",
  "meta_description": "Company tagline",
  "hero_headings": ["Main heading", "Subheading"],
  "buttons": [{"text": "Sign up", "url": "/signup", "type": "cta"}],
  "nav_items": ["Product", "Pricing", "About"],
  "deterministic_scores": {"clarity": 8, "cta_presence": 7},
  "strategic_signals": {"has_pricing": true, "has_contact": false},
  "error": "Error message if validation failed",
  "error_type": "INVALID_URL" | "WEBSITE_UNREACHABLE"
}
"""

import os
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


# =============================================================================
# FILTERING KEYWORDS
# =============================================================================
# These help us identify and filter out noisy/irrelevant content

NOISY_PHRASES = {
    "privacy policy",
    "terms of service",
    "cookie policy",
    "all rights reserved",
    "accept cookies",
    "manage cookies",
    "skip to content",
    "sign in",
    "log in"
}

# Keywords indicating a call-to-action button
CTA_KEYWORDS = {
    "book",
    "call",
    "contact",
    "demo",
    "get started",
    "join",
    "learn more",
    "request",
    "schedule",
    "sign up",
    "start",
    "subscribe",
    "try"
}

# Strategic business signals extracted from content
BUSINESS_SIGNAL_KEYWORDS = {
    "ai_signals": ["ai", "automation", "machine learning", "workflow", "agent"],
    "conversion_signals": ["demo", "trial", "pricing", "contact", "lead", "sales"],
    "trust_signals": ["customer", "testimonial", "case study", "trusted", "security"],
    "growth_signals": ["growth", "revenue", "scale", "conversion", "pipeline"],
    "product_signals": ["platform", "software", "solution", "service", "dashboard"]
}

# Rules for detecting strategic page features
STRATEGIC_SIGNAL_RULES = {
    "has_pricing_page": {
        "keywords": ["pricing", "plans", "packages"],
        "why_it_matters": "Indicates conversion maturity and clearer buyer qualification."
    },
    "has_lead_capture_forms": {
        "keywords": ["form", "contact", "newsletter", "email"],
        "why_it_matters": "Shows the site has a mechanism to capture and route demand."
    },
    "has_testimonials": {
        "keywords": ["testimonial", "customer", "case study", "review", "trusted by"],
        "why_it_matters": "Creates trust proof and reduces buyer hesitation."
    },
    "has_blog": {
        "keywords": ["blog", "resources", "articles", "insights", "guides"],
        "why_it_matters": "Signals SEO maturity and a content-led acquisition motion."
    },
    "has_login_signup": {
        "keywords": ["login", "log in", "sign in", "signup", "sign up", "register"],
        "why_it_matters": "Suggests product-led growth or an existing customer portal."
    },
    "has_demo_cta": {
        "keywords": ["book demo", "request demo", "schedule demo", "get a demo", "demo"],
        "why_it_matters": "Shows a sales-assisted funnel for qualified prospects."
    },
    "has_free_trial": {
        "keywords": ["free trial", "start free", "try free", "trial"],
        "why_it_matters": "Signals a SaaS-style self-serve acquisition strategy."
    }
}


def _normalize_url(url: str) -> str:
    """Normalize URL to always have https:// scheme."""
    parsed = urlparse(url)
    if parsed.scheme:
        return url
    return f"https://{url}"


def _is_valid_url(url: str) -> tuple[bool, str]:
    """
    Validate URL format and structure.
    
    Checks:
    1. URL is not empty
    2. URL contains at least one dot (domain.tld)
    3. URL has valid TLD (2+ characters)
    4. URL doesn't contain gibberish patterns
    
    Returns:
        (is_valid, error_message) tuple
    """
    if not url or len(url.strip()) == 0:
        return False, "URL cannot be empty"
    
    # Basic format check
    if len(url) < 4:
        return False, "URL too short (minimum 4 characters, e.g., a.co)"
    
    # Check for invalid characters
    if any(char in url for char in [' ', '\n', '\t']):
        return False, "URL contains invalid characters (spaces/whitespace)"
    
    # If it looks like gibberish (no dots, short, no vowels)
    if '.' not in url:
        return False, "Invalid URL format (must contain a domain, e.g., example.com)"
    
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    
    # Check if domain part exists
    if not parsed.netloc:
        return False, "Invalid domain in URL"
    
    # Check if domain has valid TLD
    domain = parsed.netloc.lower()
    if domain.count('.') < 1:
        return False, "Invalid domain (missing top-level domain, e.g., .com)"
    
    # Block obviously invalid TLDs
    invalid_tlds = ['localhost', 'test', '123', 'invalid']
    tld = domain.split('.')[-1]
    if tld in invalid_tlds or len(tld) < 2:
        return False, f"Invalid top-level domain '{tld}'"
    
    return True, ""


def _check_website_accessibility(url: str) -> tuple[bool, str]:
    """
    Check if website responds to HTTP requests without blocking access.
    
    Detects:
    - 403 Forbidden (blocked access)
    - 401 Unauthorized (requires authentication)
    - 404 Not Found
    - 5xx Server Errors
    - Timeouts (slow/protected sites)
    
    Returns:
        (is_accessible, status_message) tuple
    """
    normalized = _normalize_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.head(url=normalized, headers=headers, timeout=5, allow_redirects=True)
        
        # 2xx/3xx = accessible
        if 200 <= response.status_code < 400:
            return True, "Accessible"
        
        # 4xx = client errors (not found, forbidden, etc.)
        if 400 <= response.status_code < 500:
            if response.status_code == 403:
                return False, f"❌ Access Denied (403) - Website blocks automated access"
            elif response.status_code == 401:
                return False, f"❌ Authentication Required (401) - Website requires login"
            else:
                return False, f"❌ Not Found (404) - Website doesn't exist or is unavailable"
        
        # 5xx = server errors
        if 500 <= response.status_code < 600:
            return False, f"⚠️  Server Error ({response.status_code}) - Website is temporarily unavailable"
        
        return False, f"⚠️  Unexpected response ({response.status_code})"
        
    except requests.exceptions.Timeout:
        return False, "⚠️  Connection Timeout - Website took too long to respond (may be protected or slow)"
    except requests.exceptions.ConnectionError:
        return False, "❌ Connection Failed - Website is unreachable or doesn't exist"
    except requests.exceptions.InvalidURL:
        return False, "❌ Invalid URL format"
    except Exception as e:
        return False, f"⚠️  Unable to access website: {type(e).__name__}"


def _clean_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _is_noise(text: str) -> bool:
    normalized = _clean_text(text).lower()
    if not normalized or len(normalized) < 2:
        return True
    return any(phrase in normalized for phrase in NOISY_PHRASES)


def _clean_items(items, limit):
    cleaned = []
    for item in items:
        text = _clean_text(item)
        if text and text not in cleaned and not _is_noise(text):
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def scrape_website(url: str):
    """
    Extract structured website data using synchronous HTTP requests.
    
    Three-layer validation pipeline:
    1. URL Format Validation - Check URL structure and TLD validity
    2. Website Accessibility Check - Verify server responds without blocking
    3. Content Extraction - Scrape HTML with BeautifulSoup
    
    Returns:
        dict with extracted data or error details:
        {
            "error": "Error message if validation failed",
            "error_type": "INVALID_URL|WEBSITE_UNREACHABLE|..." if failed,
            "title": "Company name",
            "meta_description": "Company tagline",
            "hero_headings": ["Main heading", "Subheading"],
            "buttons": [{"text": "Sign up", "url": "/signup", "type": "cta"}],
            "nav_items": ["Product", "Pricing", "About"],
            "deterministic_scores": {"clarity": 8, "cta": 7},
            "business_signals": {"has_pricing": true, "has_blog": false},
            ...
        }
    """
    target_url = _normalize_url(url)
    
    # STEP 1: Validate URL format
    is_valid, validation_error = _is_valid_url(url)
    if not is_valid:
        print(f"\n🔍 Scraper: ❌ INVALID URL")
        print(f"🔍 Scraper: {validation_error}")
        return {
            "url": url,
            "error": validation_error,
            "error_type": "INVALID_URL",
            "is_accessible": False,
            "title": "",
            "meta_description": "",
            "headings": [],
            "hero_headings": [],
            "buttons": [],
            "links": [],
            "nav_items": [],
            "forms": 0,
            "form_fields": 0,
            "content": [],
            "screenshot_path": None,
            "visual_evidence": {
                "homepage_screenshot_captured": False,
                "screenshot_path": None,
                "viewport": "N/A",
                "full_page": False
            },
            "business_signals": {},
            "cta_hierarchy": {"first_cta": None, "hero_text": "", "navbar_items": [], "button_priority": []},
            "deterministic_scores": {
                "Website Clarity": {"score": 0, "evidence": ["Invalid URL"]},
                "CTA Effectiveness": {"score": 0, "evidence": ["Invalid URL"]},
                "Automation Readiness": {"score": 0, "evidence": ["Invalid URL"]},
                "Growth Potential": {"score": 0, "evidence": ["Invalid URL"]}
            },
            "ai_ready_context": ""
        }
    
    # STEP 2: Check website accessibility
    is_accessible, accessibility_message = _check_website_accessibility(target_url)
    if not is_accessible:
        print(f"\n🔍 Scraper: ⚠️  WEBSITE NOT ACCESSIBLE")
        print(f"🔍 Scraper: {accessibility_message}")
        return {
            "url": target_url,
            "error": accessibility_message,
            "error_type": "WEBSITE_UNREACHABLE",
            "is_accessible": False,
            "title": "",
            "meta_description": "",
            "headings": [],
            "hero_headings": [],
            "buttons": [],
            "links": [],
            "nav_items": [],
            "forms": 0,
            "form_fields": 0,
            "content": [],
            "screenshot_path": None,
            "visual_evidence": {
                "homepage_screenshot_captured": False,
                "screenshot_path": None,
                "viewport": "N/A",
                "full_page": False
            },
            "business_signals": {},
            "cta_hierarchy": {"first_cta": None, "hero_text": "", "navbar_items": [], "button_priority": []},
            "deterministic_scores": {
                "Website Clarity": {"score": 0, "evidence": ["Website unreachable"]},
                "CTA Effectiveness": {"score": 0, "evidence": ["Website unreachable"]},
                "Automation Readiness": {"score": 0, "evidence": ["Website unreachable"]},
                "Growth Potential": {"score": 0, "evidence": ["Website unreachable"]}
            },
            "ai_ready_context": ""
        }
    
    # STEP 3: Scrape website (only if URL is valid and accessible)
    try:
        print(f"\n🔍 Scraper: Starting extraction for {target_url}")
        
        # Fetch HTML
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status()
        print(f"🔍 Scraper: HTML fetched ({len(response.content)} bytes)")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract metadata
        title = soup.title.string if soup.title else ""
        meta_desc = ""
        if soup.find("meta", attrs={"name": "description"}):
            meta_desc = soup.find("meta", attrs={"name": "description"}).get("content", "")
        
        # Extract headings
        headings = [_clean_text(h.get_text()) for h in soup.find_all(["h1", "h2", "h3"])]
        headings = _clean_items(headings, 10)
        
        # Hero headings (first h1-h3)
        hero_headings = []
        for tag in ["h1", "h2", "h3"]:
            elements = soup.find_all(tag)
            if elements:
                text = _clean_text(elements[0].get_text())
                if text and not _is_noise(text):
                    hero_headings.append(text)
                if len(hero_headings) >= 3:
                    break
        
        # Extract buttons (look for button elements and links that look like buttons)
        buttons = []
        for btn in soup.find_all("button"):
            text = _clean_text(btn.get_text())
            if text and not _is_noise(text):
                buttons.append(text)
        
        # Look for common CTA patterns in links
        for link in soup.find_all("a"):
            text = _clean_text(link.get_text())
            if any(keyword in text.lower() for keyword in CTA_KEYWORDS):
                if text and not _is_noise(text) and text not in buttons:
                    buttons.append(text)
                    if len(buttons) >= 10:
                        break
        
        buttons = _clean_items(buttons, 10)
        
        # Extract navigation items
        nav_items = []
        for nav in soup.find_all(["nav", "header"]):
            for link in nav.find_all("a"):
                text = _clean_text(link.get_text())
                if text and not _is_noise(text) and len(text) < 50:
                    nav_items.append(text)
        
        nav_items = _clean_items(nav_items, 10)
        
        # Extract links (for semantic analysis)
        links = []
        for link in soup.find_all("a"):
            text = _clean_text(link.get_text())
            if text and not _is_noise(text):
                links.append({"text": text, "href": link.get("href", "")})
        links = links[:20]
        
        # Count forms
        forms = len(soup.find_all("form"))
        
        # Count form fields
        form_fields = len(soup.find_all(["input", "textarea", "select"]))
        
        # Extract main content
        content = []
        for p in soup.find_all("p"):
            text = _clean_text(p.get_text())
            if text and not _is_noise(text):
                content.append(text)
        content = content[:15]
        
        # Identify business signals
        page_text = soup.get_text().lower()
        business_signals = {}
        
        for signal_type, keywords_list in BUSINESS_SIGNAL_KEYWORDS.items():
            business_signals[signal_type] = {
                "found": any(kw in page_text for kw in keywords_list),
                "keywords": keywords_list
            }
        
        # Identify strategic signals
        strategic_signals = {}
        for signal_name, signal_config in STRATEGIC_SIGNAL_RULES.items():
            keywords = signal_config["keywords"]
            present = any(kw in page_text for kw in keywords)
            strategic_signals[signal_name] = {
                "present": present,
                "why": signal_config["why_it_matters"]
            }
        
        # Calculate deterministic scores
        deterministic_scores = _calculate_deterministic_scores(
            {
                "title": title,
                "meta_description": meta_desc,
                "headings": headings,
                "hero_headings": hero_headings,
                "buttons": buttons,
                "nav_items": nav_items,
                "links": links,
                "forms": forms,
                "content": content
            },
            business_signals
        )
        
        print(f"🔍 Scraper: ✅ Success - all data extracted")
        print(f"   - Title: {title[:50]}")
        print(f"   - Hero headings: {len(hero_headings)}")
        print(f"   - Buttons: {len(buttons)}")
        print(f"   - Nav items: {len(nav_items)}")
        
        return {
            "url": target_url,
            "title": title,
            "meta_description": meta_desc,
            "headings": headings,
            "hero_headings": hero_headings,
            "buttons": buttons,
            "links": links,
            "nav_items": nav_items,
            "forms": forms,
            "form_fields": form_fields,
            "content": content,
            "screenshot_path": None,  # No screenshots in sync mode
            "visual_evidence": {
                "homepage_screenshot_captured": False,
                "screenshot_path": None,
                "viewport": "N/A",
                "full_page": False
            },
            "business_signals": business_signals,
            "cta_hierarchy": {
                "first_cta": buttons[0] if buttons else None,
                "hero_text": hero_headings[0] if hero_headings else "",
                "navbar_items": nav_items,
                "button_priority": [{"text": btn, "source": "DOM", "priority": i+1} for i, btn in enumerate(buttons[:6])]
            },
            "deterministic_scores": deterministic_scores,
            "ai_ready_context": _build_ai_context(
                {"buttons": buttons, "nav_items": nav_items},
                business_signals
            )
        }
    
    except Exception as e:
        print(f"\n🔍 Scraper: ❌ ERROR during extraction")
        print(f"🔍 Scraper: Error type: {type(e).__name__}")
        print(f"🔍 Scraper: Error message: {str(e)}")
        
        return {
            "url": target_url,
            "error": str(e),
            "title": "",
            "meta_description": "",
            "headings": [],
            "hero_headings": [],
            "buttons": [],
            "links": [],
            "nav_items": [],
            "forms": 0,
            "form_fields": 0,
            "content": [],
            "screenshot_path": None,
            "visual_evidence": {
                "homepage_screenshot_captured": False,
                "screenshot_path": None,
                "viewport": "N/A",
                "full_page": False
            },
            "business_signals": {},
            "cta_hierarchy": {
                "first_cta": None,
                "hero_text": "",
                "navbar_items": [],
                "button_priority": []
            },
            "deterministic_scores": {
                "Website Clarity": {"score": 1, "evidence": ["Scraping failed"]},
                "CTA Effectiveness": {"score": 1, "evidence": ["Scraping failed"]},
                "Automation Readiness": {"score": 1, "evidence": ["Scraping failed"]},
                "Growth Potential": {"score": 1, "evidence": ["Scraping failed"]}
            },
            "ai_ready_context": ""
        }


def _calculate_deterministic_scores(page_data, business_signals):
    """Calculate deterministic scores based on extracted data."""
    scores = {}
    
    # Website Clarity
    clarity_score = 0
    if page_data.get("title"):
        clarity_score += 2
    if page_data.get("meta_description"):
        clarity_score += 2
    if len(page_data.get("headings", [])) >= 3:
        clarity_score += 2
    if len(page_data.get("hero_headings", [])) >= 1:
        clarity_score += 2
    if len(page_data.get("content", [])) >= 3:
        clarity_score += 2
    
    scores["Website Clarity"] = {
        "score": min(10, clarity_score),
        "evidence": ["Clear messaging present" if clarity_score >= 6 else "Messaging needs clarity"]
    }
    
    # CTA Effectiveness
    cta_score = 0
    if len(page_data.get("buttons", [])) >= 1:
        cta_score += 3
    if len(page_data.get("buttons", [])) >= 3:
        cta_score += 3
    if page_data.get("forms", 0) >= 1:
        cta_score += 2
    if page_data.get("form_fields", 0) >= 3:
        cta_score += 2
    
    scores["CTA Effectiveness"] = {
        "score": min(10, cta_score),
        "evidence": ["Multiple CTAs detected" if cta_score >= 5 else "CTAs need enhancement"]
    }
    
    # Automation Readiness
    automation_score = 0
    if page_data.get("forms", 0) >= 1:
        automation_score += 3
    if business_signals.get("conversion_signals", {}).get("found"):
        automation_score += 3
    if page_data.get("form_fields", 0) >= 2:
        automation_score += 2
    if business_signals.get("ai_signals", {}).get("found"):
        automation_score += 2
    
    scores["Automation Readiness"] = {
        "score": min(10, automation_score),
        "evidence": ["Good automation foundation" if automation_score >= 5 else "Automation opportunities exist"]
    }
    
    # Growth Potential
    growth_score = 0
    if len(page_data.get("buttons", [])) >= 2:
        growth_score += 2
    if len(page_data.get("content", [])) >= 5:
        growth_score += 2
    if business_signals.get("trust_signals", {}).get("found"):
        growth_score += 2
    if business_signals.get("growth_signals", {}).get("found"):
        growth_score += 2
    if len(page_data.get("nav_items", [])) >= 4:
        growth_score += 2
    
    scores["Growth Potential"] = {
        "score": min(10, growth_score),
        "evidence": ["Growth-ready positioning" if growth_score >= 6 else "Growth opportunities identified"]
    }
    
    return scores


def _build_ai_context(page_data, business_signals):
    """Build AI context string."""
    parts = []
    
    if page_data.get("buttons"):
        parts.append(f"Primary CTAs: {', '.join(page_data['buttons'][:3])}")
    
    if page_data.get("nav_items"):
        parts.append(f"Navigation: {', '.join(page_data['nav_items'][:5])}")
    
    if business_signals.get("conversion_signals", {}).get("found"):
        parts.append("Has conversion signals")
    
    if business_signals.get("ai_signals", {}).get("found"):
        parts.append("Shows AI/automation interest")
    
    return " | ".join(parts) if parts else ""
