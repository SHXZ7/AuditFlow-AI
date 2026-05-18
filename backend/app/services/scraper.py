import os
import re
from urllib.parse import urlparse

from playwright.async_api import async_playwright


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

BUSINESS_SIGNAL_KEYWORDS = {
    "ai_signals": ["ai", "automation", "machine learning", "workflow", "agent"],
    "conversion_signals": ["demo", "trial", "pricing", "contact", "lead", "sales"],
    "trust_signals": ["customer", "testimonial", "case study", "trusted", "security"],
    "growth_signals": ["growth", "revenue", "scale", "conversion", "pipeline"],
    "product_signals": ["platform", "software", "solution", "service", "dashboard"]
}

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
    parsed = urlparse(url)

    if parsed.scheme:
        return url

    return f"https://{url}"


def _clean_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _is_noise(text: str) -> bool:
    normalized = _clean_text(text).lower()

    if not normalized:
        return True

    if len(normalized) < 2:
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


def _safe_file_name(value):
    parsed = urlparse(value)
    base = parsed.netloc or parsed.path or "homepage"
    file_name = re.sub(r"[^A-Za-z0-9_-]+", "_", base).strip("_")

    return file_name or "homepage"


async def _capture_homepage_screenshot(page, url):
    screenshots_dir = os.path.join(
        "reports",
        "screenshots"
    )
    os.makedirs(
        screenshots_dir,
        exist_ok=True
    )

    screenshot_path = os.path.join(
        screenshots_dir,
        f"{_safe_file_name(url)}_homepage.png"
    )

    await page.screenshot(
        path=screenshot_path,
        full_page=True
    )

    return screenshot_path


async def _render_page(url: str):
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True
    )

    page = await browser.new_page(
        viewport={
            "width": 1440,
            "height": 1200
        },
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )

    print(f"📱 Rendering: {url}")
    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )
    print(f"📱 Page loaded (domcontentloaded)")

    # Wait for networkidle to ensure JS has executed
    try:
        await page.wait_for_load_state(
            "networkidle",
            timeout=15000
        )
        print(f"📱 Network idle reached")
    except Exception as e:
        print(f"📱 Network idle timeout (continuing anyway): {str(e)}")

    # Additional wait for complex SPAs like Notion
    await page.wait_for_timeout(3000)
    print(f"📱 Post-render delay complete")

    # Try to capture screenshot
    screenshot_path = None
    try:
        screenshot_path = await _capture_homepage_screenshot(
            page,
            url
        )
        print(f"📸 Screenshot captured: {screenshot_path}")
    except Exception as screenshot_error:
        print(f"📸 Screenshot failed: {str(screenshot_error)}")

    # Remove scripts/styles to clean DOM
    await page.locator(
        "script, style, noscript, svg, iframe"
    ).evaluate_all(
        "(nodes) => nodes.forEach((node) => node.remove())"
    )
    print(f"📝 Cleaned DOM (removed scripts/styles/etc)")

    return playwright, browser, page, screenshot_path


async def _extract_structured_dom(page):
    return await page.evaluate(
        """
        () => {
            const textOf = (selector) =>
                Array.from(document.querySelectorAll(selector))
                    .map((element) =>
                        element.innerText ||
                        element.value ||
                        element.getAttribute("aria-label") ||
                        element.getAttribute("content") ||
                        ""
                    );

            const links = Array.from(document.querySelectorAll("a"))
                .map((element) => ({
                    text: element.innerText || element.getAttribute("aria-label") || "",
                    href: element.href || ""
                }));

            const forms = Array.from(document.querySelectorAll("form"))
                .map((form) => ({
                    inputs: form.querySelectorAll("input, textarea, select").length,
                    buttonText: Array.from(form.querySelectorAll("button, input[type='submit']"))
                        .map((element) => element.innerText || element.value || "")
                }));

            const linkOf = (element) => ({
                text: element.innerText || element.getAttribute("aria-label") || "",
                href: element.href || ""
            });

            const sectionText = (selector) => {
                const element = document.querySelector(selector);

                if (!element) {
                    return "";
                }

                return element.innerText || "";
            };

            const findSection = (keywords) => {
                const sections = Array.from(
                    document.querySelectorAll("section, main > div, article, aside")
                );

                const section = sections.find((element) => {
                    const text = (element.innerText || "").toLowerCase();
                    const id = (element.id || "").toLowerCase();
                    const className = (element.className || "").toString().toLowerCase();
                    const haystack = `${id} ${className} ${text}`;

                    return keywords.some((keyword) => haystack.includes(keyword));
                });

                return section ? section.innerText || "" : "";
            };

            const title = document.title || "";
            const metaDescription = document
                .querySelector('meta[name="description"]')
                ?.getAttribute("content") || "";

            const navigationLinks = Array.from(document.querySelectorAll("nav a"))
                .map(linkOf);

            const footerLinks = Array.from(document.querySelectorAll("footer a"))
                .map(linkOf);

            return {
                title,
                metaDescription,
                headings: textOf("h1, h2, h3"),
                heroHeadings: textOf("main h1, header h1, section h1").slice(0, 3),
                paragraphs: textOf("p"),
                buttons: textOf("button, a[role='button'], input[type='submit']"),
                links,
                forms,
                navItems: navigationLinks.map((link) => link.text || link.href),
                semanticSections: {
                    hero_section: sectionText("main section, header, main"),
                    pricing_section: findSection(["pricing", "price", "plans", "packages"]),
                    testimonials_section: findSection([
                        "testimonial",
                        "testimonials",
                        "customer",
                        "customers",
                        "case study",
                        "trusted by",
                        "reviews"
                    ]),
                    footer_links: footerLinks,
                    navigation_items: navigationLinks
                },
                bodyText: document.body?.innerText || ""
            };
        }
        """
    )


def _clean_dom(dom):
    links = [
        link
        for link in dom.get("links", [])
        if not _is_noise(link.get("text") or link.get("href"))
    ]

    paragraphs = _clean_items(
        dom.get("paragraphs", []),
        35
    )

    body_text = _clean_text(dom.get("bodyText", ""))
    semantic_sections = _clean_semantic_sections(
        dom.get("semanticSections", {})
    )

    return {
        "title": _clean_text(dom.get("title", "")),
        "meta_description": _clean_text(dom.get("metaDescription", "")),
        "headings": _clean_items(dom.get("headings", []), 20),
        "hero_headings": _clean_items(dom.get("heroHeadings", []), 5),
        "paragraphs": paragraphs,
        "buttons": _clean_items(dom.get("buttons", []), 20),
        "links": _clean_items(
            [link.get("text") or link.get("href") for link in links],
            30
        ),
        "nav_items": _clean_items(dom.get("navItems", []), 15),
        "semantic_sections": semantic_sections,
        "forms": len(dom.get("forms", [])),
        "form_fields": sum(form.get("inputs", 0) for form in dom.get("forms", [])),
        "content": " ".join(paragraphs)[:5000] or body_text[:5000]
    }


def _clean_link_objects(links, limit):
    cleaned = []

    for link in links:
        text = _clean_text(link.get("text", ""))
        href = _clean_text(link.get("href", ""))
        label = text or href

        if label and not _is_noise(label):
            cleaned.append(
                {
                    "text": text,
                    "href": href
                }
            )

        if len(cleaned) >= limit:
            break

    return cleaned


def _clean_section_text(text, limit=1200):
    lines = _clean_items(
        (text or "").splitlines(),
        18
    )

    return " ".join(lines)[:limit]


def _clean_semantic_sections(sections):
    return {
        "hero_section": _clean_section_text(
            sections.get("hero_section", ""),
            900
        ),
        "pricing_section": _clean_section_text(
            sections.get("pricing_section", ""),
            1000
        ),
        "testimonials_section": _clean_section_text(
            sections.get("testimonials_section", ""),
            1000
        ),
        "footer_links": _clean_link_objects(
            sections.get("footer_links", []),
            20
        ),
        "navigation_items": _clean_link_objects(
            sections.get("navigation_items", []),
            20
        )
    }


def _identify_business_signals(clean_dom):
    link_text = " ".join(clean_dom.get("links", []))
    nav_text = " ".join(clean_dom.get("nav_items", []))
    button_text = " ".join(clean_dom.get("buttons", []))
    semantic_sections = clean_dom.get("semantic_sections", {})
    semantic_text = " ".join(
        [
            semantic_sections.get("hero_section", ""),
            semantic_sections.get("pricing_section", ""),
            semantic_sections.get("testimonials_section", "")
        ]
    )

    searchable_text = " ".join(
        [
            clean_dom.get("title", ""),
            clean_dom.get("meta_description", ""),
            " ".join(clean_dom.get("headings", [])),
            button_text,
            link_text,
            nav_text,
            semantic_text,
            clean_dom.get("content", "")
        ]
    ).lower()

    signals = {}

    for signal_name, keywords in BUSINESS_SIGNAL_KEYWORDS.items():
        matches = [
            keyword
            for keyword in keywords
            if keyword in searchable_text
        ]
        signals[signal_name] = matches

    ctas = [
        button
        for button in clean_dom.get("buttons", [])
        if any(keyword in button.lower() for keyword in CTA_KEYWORDS)
    ]

    signals["primary_ctas"] = ctas[:8]
    signals["cta_hierarchy"] = _extract_cta_hierarchy(
        clean_dom,
        ctas
    )
    signals["has_forms"] = clean_dom.get("forms", 0) > 0
    signals["form_fields"] = clean_dom.get("form_fields", 0)
    signals["positioning_clues"] = clean_dom.get("hero_headings") or clean_dom.get("headings", [])[:3]
    signals["semantic_sections_found"] = {
        "hero_section": bool(semantic_sections.get("hero_section")),
        "pricing_section": bool(semantic_sections.get("pricing_section")),
        "testimonials_section": bool(semantic_sections.get("testimonials_section")),
        "footer_links": bool(semantic_sections.get("footer_links")),
        "navigation_items": bool(semantic_sections.get("navigation_items"))
    }
    signals["strategic_signals"] = _detect_strategic_signals(
        clean_dom,
        searchable_text
    )

    return signals


def _extract_cta_hierarchy(clean_dom, primary_ctas):
    buttons = clean_dom.get("buttons", [])
    nav_items = clean_dom.get("nav_items", [])
    semantic_sections = clean_dom.get("semantic_sections", {})
    hero_text = semantic_sections.get("hero_section", "")
    hero_text_lower = hero_text.lower()

    button_priority = []

    for index, button in enumerate(buttons):
        button_lower = button.lower()
        priority = 3
        source = "page"

        if button_lower in hero_text_lower:
            priority = 1
            source = "hero"
        elif any(keyword in button_lower for keyword in CTA_KEYWORDS):
            priority = 2

        button_priority.append(
            {
                "rank": index + 1,
                "text": button,
                "source": source,
                "priority": priority
            }
        )

    button_priority = sorted(
        button_priority,
        key=lambda item: (item["priority"], item["rank"])
    )

    return {
        "first_cta": primary_ctas[0] if primary_ctas else (buttons[0] if buttons else None),
        "hero_text": hero_text[:700],
        "navbar_items": nav_items,
        "button_priority": button_priority[:10]
    }


def _detect_strategic_signals(clean_dom, searchable_text):
    strategic_signals = {}

    for signal_name, rule in STRATEGIC_SIGNAL_RULES.items():
        evidence = [
            keyword
            for keyword in rule["keywords"]
            if keyword in searchable_text
        ]

        strategic_signals[signal_name] = {
            "present": bool(evidence),
            "evidence": evidence[:5],
            "why_it_matters": rule["why_it_matters"]
        }

    if clean_dom.get("forms", 0) > 0:
        strategic_signals["has_lead_capture_forms"]["present"] = True
        strategic_signals["has_lead_capture_forms"]["evidence"] = [
            f"{clean_dom.get('forms')} form(s)",
            f"{clean_dom.get('form_fields')} field(s)"
        ]

    return strategic_signals


def _clamp_score(score):
    return max(1, min(10, score))


def _score_reason(label, score, evidence):
    return {
        "label": label,
        "score": _clamp_score(score),
        "evidence": evidence
    }


def _calculate_deterministic_scores(clean_dom, business_signals):
    strategic = business_signals.get("strategic_signals", {})
    sections_found = business_signals.get("semantic_sections_found", {})
    headings_count = len(clean_dom.get("headings", []))
    cta_count = len(business_signals.get("primary_ctas", []))
    nav_count = len(clean_dom.get("nav_items", []))
    content_length = len(clean_dom.get("content", ""))

    clarity_score = 4
    clarity_evidence = []

    if clean_dom.get("hero_headings"):
        clarity_score += 2
        clarity_evidence.append("Hero heading detected")

    if headings_count >= 5:
        clarity_score += 1
        clarity_evidence.append(f"{headings_count} headings detected")

    if clean_dom.get("meta_description"):
        clarity_score += 1
        clarity_evidence.append("Meta description present")

    if content_length >= 800:
        clarity_score += 1
        clarity_evidence.append("Sufficient visible page copy")

    if sections_found.get("navigation_items"):
        clarity_score += 1
        clarity_evidence.append(f"{nav_count} navigation items detected")

    cta_score = 3
    cta_evidence = []

    if cta_count > 0:
        cta_score += 2
        cta_evidence.append(f"{cta_count} primary CTA(s) detected")

    if strategic.get("has_demo_cta", {}).get("present"):
        cta_score += 2
        cta_evidence.append("Demo CTA detected")

    if strategic.get("has_free_trial", {}).get("present"):
        cta_score += 1
        cta_evidence.append("Free trial CTA detected")

    if strategic.get("has_pricing_page", {}).get("present"):
        cta_score += 1
        cta_evidence.append("Pricing signal detected")

    if strategic.get("has_lead_capture_forms", {}).get("present"):
        cta_score += 1
        cta_evidence.append("Lead capture form detected")

    automation_score = 4
    automation_evidence = []

    if business_signals.get("ai_signals"):
        automation_score += 2
        automation_evidence.append("AI or automation language detected")

    if clean_dom.get("forms", 0) > 0:
        automation_score += 1
        automation_evidence.append("Form workflow can be automated")

    if strategic.get("has_demo_cta", {}).get("present"):
        automation_score += 1
        automation_evidence.append("Demo request workflow detected")

    if strategic.get("has_login_signup", {}).get("present"):
        automation_score += 1
        automation_evidence.append("Login/signup motion detected")

    if business_signals.get("conversion_signals"):
        automation_score += 1
        automation_evidence.append("Conversion workflow signals detected")

    growth_score = 4
    growth_evidence = []

    if strategic.get("has_pricing_page", {}).get("present"):
        growth_score += 1
        growth_evidence.append("Pricing or plans signal detected")

    if strategic.get("has_blog", {}).get("present"):
        growth_score += 1
        growth_evidence.append("Blog/resources signal detected")

    if strategic.get("has_testimonials", {}).get("present"):
        growth_score += 1
        growth_evidence.append("Trust proof signal detected")

    if cta_count > 1:
        growth_score += 1
        growth_evidence.append("Multiple conversion paths detected")

    if business_signals.get("growth_signals") or business_signals.get("product_signals"):
        growth_score += 1
        growth_evidence.append("Growth or product positioning language detected")

    if clean_dom.get("forms", 0) > 0:
        growth_score += 1
        growth_evidence.append("Lead capture mechanism detected")

    return {
        "Website Clarity": _score_reason(
            "Website Clarity",
            clarity_score,
            clarity_evidence or ["Limited clarity signals found in extracted content"]
        ),
        "CTA Effectiveness": _score_reason(
            "CTA Effectiveness",
            cta_score,
            cta_evidence or ["Limited CTA signals found in extracted content"]
        ),
        "Automation Readiness": _score_reason(
            "Automation Readiness",
            automation_score,
            automation_evidence or ["Limited automation signals found in extracted content"]
        ),
        "Growth Potential": _score_reason(
            "Growth Potential",
            growth_score,
            growth_evidence or ["Limited growth signals found in extracted content"]
        )
    }


def _build_ai_context(clean_dom, business_signals):
    context_parts = [
        f"Title: {clean_dom.get('title', '')}",
        f"Meta description: {clean_dom.get('meta_description', '')}",
        f"Hero positioning: {' | '.join(business_signals.get('positioning_clues', []))}",
        f"Hero section: {clean_dom.get('semantic_sections', {}).get('hero_section', '')}",
        f"Pricing section: {clean_dom.get('semantic_sections', {}).get('pricing_section', '')}",
        f"Testimonials section: {clean_dom.get('semantic_sections', {}).get('testimonials_section', '')}",
        f"Primary CTAs: {' | '.join(business_signals.get('primary_ctas', []))}",
        f"CTA hierarchy: {business_signals.get('cta_hierarchy', {})}",
        f"Navigation: {' | '.join(clean_dom.get('nav_items', []))}",
        f"Footer links: {clean_dom.get('semantic_sections', {}).get('footer_links', [])}",
        f"Strategic signals: {business_signals.get('strategic_signals', {})}",
        f"Business signals: {business_signals}",
        f"Page content: {clean_dom.get('content', '')}"
    ]

    return "\n".join(part for part in context_parts if part.strip())[:7000]


async def scrape_website(url: str):
    target_url = _normalize_url(url)
    playwright = None
    browser = None

    try:
        print(f"\n🔍 Scraper: Starting extraction for {target_url}")
        playwright, browser, page, screenshot_path = await _render_page(target_url)
        print(f"🔍 Scraper: Page rendered, screenshot at {screenshot_path}")
        
        structured_dom = await _extract_structured_dom(page)
        print(f"🔍 Scraper: Structured DOM extracted")
        
        clean_dom = _clean_dom(structured_dom)
        print(f"🔍 Scraper: Clean DOM processed - title: {clean_dom['title'][:50] if clean_dom['title'] else 'NONE'}")
        print(f"🔍 Scraper: Hero headings: {len(clean_dom.get('hero_headings', []))}")
        print(f"🔍 Scraper: Buttons: {len(clean_dom.get('buttons', []))}")
        print(f"🔍 Scraper: Nav items: {len(clean_dom.get('nav_items', []))}")
        
        business_signals = _identify_business_signals(clean_dom)
        deterministic_scores = _calculate_deterministic_scores(
            clean_dom,
            business_signals
        )
        ai_context = _build_ai_context(clean_dom, business_signals)
        
        print(f"🔍 Scraper: ✅ Success - all data extracted")

        return {
            "url": target_url,
            "title": clean_dom["title"],
            "meta_description": clean_dom["meta_description"],
            "headings": clean_dom["headings"],
            "hero_headings": clean_dom["hero_headings"],
            "buttons": clean_dom["buttons"],
            "links": clean_dom["links"],
            "nav_items": clean_dom["nav_items"],
            "semantic_sections": clean_dom["semantic_sections"],
            "forms": clean_dom["forms"],
            "form_fields": clean_dom["form_fields"],
            "content": clean_dom["content"],
            "screenshot_path": screenshot_path,
            "visual_evidence": {
                "homepage_screenshot_captured": bool(screenshot_path),
                "screenshot_path": screenshot_path,
                "viewport": "1440x1200",
                "full_page": True
            },
            "business_signals": business_signals,
            "cta_hierarchy": business_signals.get("cta_hierarchy", {}),
            "deterministic_scores": deterministic_scores,
            "ai_ready_context": ai_context
        }

    except Exception as e:
        print(f"\n🔍 Scraper: ❌ ERROR during extraction")
        print(f"🔍 Scraper: Error type: {type(e).__name__}")
        print(f"🔍 Scraper: Error message: {str(e)}")
        import traceback
        print(f"🔍 Scraper: Traceback:\n{traceback.format_exc()}")
        
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
            "semantic_sections": {
                "hero_section": "",
                "pricing_section": "",
                "testimonials_section": "",
                "footer_links": [],
                "navigation_items": []
            },
            "forms": 0,
            "form_fields": 0,
            "content": "",
            "screenshot_path": None,
            "visual_evidence": {
                "homepage_screenshot_captured": False,
                "screenshot_path": None,
                "viewport": "1440x1200",
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
                "Website Clarity": {
                    "label": "Website Clarity",
                    "score": 1,
                    "evidence": ["Scraping failed, so no clarity signals were available"]
                },
                "CTA Effectiveness": {
                    "label": "CTA Effectiveness",
                    "score": 1,
                    "evidence": ["Scraping failed, so no CTA signals were available"]
                },
                "Automation Readiness": {
                    "label": "Automation Readiness",
                    "score": 1,
                    "evidence": ["Scraping failed, so no automation signals were available"]
                },
                "Growth Potential": {
                    "label": "Growth Potential",
                    "score": 1,
                    "evidence": ["Scraping failed, so no growth signals were available"]
                }
            },
            "ai_ready_context": ""
        }

    finally:
        if browser:
            await browser.close()

        if playwright:
            await playwright.stop()
