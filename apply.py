import asyncio
from playwright.async_api import async_playwright
from config import LINKEDIN_EMAIL, LINKEDIN_PASSWORD, LINKEDIN_PHONE


async def easy_apply(job_url: str) -> str:
    """
    Opens LinkedIn Easy Apply form, fills it, and stops before final submit.
    Returns: 'ready' | 'not_available' | 'error'
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Step 1: Login
            await page.goto("https://www.linkedin.com/login")
            await page.fill("#username", LINKEDIN_EMAIL)
            await page.fill("#password", LINKEDIN_PASSWORD)
            await page.click('[data-litms-control-urn="login-submit"]')

            try:
                await page.wait_for_url("**/feed/**", timeout=15000)
            except Exception:
                await browser.close()
                return "error"  # login failed or 2FA needed

            # Step 2: Go to job page
            await page.goto(job_url)
            await page.wait_for_timeout(2500)

            # Step 3: Click Easy Apply
            easy_btn = page.locator(".jobs-apply-button--top-card")
            if not await easy_btn.count():
                await browser.close()
                return "not_available"

            await easy_btn.click()
            await page.wait_for_timeout(1500)

            # Step 4: Walk through form steps (max 10 pages)
            for _ in range(10):
                await page.wait_for_timeout(1000)

                # Fill phone if empty
                phone = page.locator('input[id*="phoneNumber"]')
                if await phone.count() and not await phone.input_value():
                    await phone.fill(LINKEDIN_PHONE)

                submit = page.locator('button[aria-label="Submit application"]')
                review = page.locator('button[aria-label="Review your application"]')
                next_btn = page.locator('button[aria-label="Continue to next step"]')

                if await submit.count():
                    # Stop here — user must confirm final submit manually
                    print("[apply] Form ready. Waiting 90s for user to review and submit...")
                    await page.wait_for_timeout(90000)
                    await browser.close()
                    return "ready"

                elif await review.count():
                    await review.click()
                elif await next_btn.count():
                    await next_btn.click()
                else:
                    break

        except Exception as e:
            print(f"[apply] Error: {e}")
            await browser.close()
            return "error"

        await browser.close()
        return "error"
