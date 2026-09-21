import asyncio
import httpx

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


USER_AGENT = (
    "Mozilla/5.0 "
    "(compatible; WhatsAppRAGBot/1.0)"
)

MAX_CONCURRENT_REQUESTS = 2
MAX_RETRIES = 2
REQUEST_DELAY = 1.0


async def fetch_page(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    page_number: int,
    total_pages: int
) -> tuple[str, str | None]:

    async with semaphore:

        for attempt in range(MAX_RETRIES + 1):

            try:
                print(
                    f"[{page_number}/{total_pages}] "
                    f"Fetching: {url}"
                )

                response = await client.get(
                    url,
                    headers={
                        "User-Agent": USER_AGENT
                    }
                )

                # Rate limit
                if response.status_code == 429:

                    if attempt < MAX_RETRIES:

                        wait_time = 3 * (attempt + 1)

                        print(
                            f"  429 Too Many Requests. "
                            f"Waiting {wait_time}s..."
                        )

                        await asyncio.sleep(
                            wait_time
                        )

                        continue

                    print(
                        "  ✗ Skipped after retries."
                    )

                    return url, None

                response.raise_for_status()

                # Only process HTML
                content_type = response.headers.get(
                    "content-type",
                    ""
                ).lower()

                if "text/html" not in content_type:

                    print(
                        "  - Skipped: not HTML"
                    )

                    return url, None

                soup = BeautifulSoup(
                    response.text,
                    "html.parser"
                )

                # Remove elements that aren't useful
                # for the knowledge base.
                for tag in soup([
                    "script",
                    "style",
                    "noscript",
                    "nav",
                    "footer",
                    "header",
                    "aside"
                ]):
                    tag.decompose()

                # Remove common WordPress/WooCommerce noise
                for selector in [
                    ".site-header",
                    ".site-footer",
                    ".main-navigation",
                    ".menu",
                    ".navbar",
                    ".woocommerce-breadcrumb",
                    ".woocommerce-products-header",
                    ".widget",
                    ".sidebar",
                    ".compare",
                    ".compare-popup",
                    ".yith-wcwl-add-button"
                ]:

                    for element in soup.select(
                        selector
                    ):
                        element.decompose()

                # Prefer main article/content area
                main_content = (
                    soup.find("main")
                    or soup.find("article")
                    or soup.find(
                        id="content"
                    )
                    or soup.body
                )

                if not main_content:

                    print(
                        "  ✗ No usable content"
                    )

                    return url, None

                # Extract text
                text = main_content.get_text(
                    separator=" ",
                    strip=True
                )

                # Clean repeated whitespace
                text = " ".join(
                    text.split()
                )

                # Ignore extremely small pages
                if len(text) < 50:

                    print(
                        "  - Skipped: too little content"
                    )

                    return url, None

                print(
                    f"  ✓ Success "
                    f"({len(text)} chars)"
                )

                await asyncio.sleep(
                    REQUEST_DELAY
                )

                return url, text

            except httpx.ReadTimeout:

                if attempt < MAX_RETRIES:

                    wait_time = 2 * (attempt + 1)

                    print(
                        f"  Read timeout. "
                        f"Retrying in {wait_time}s..."
                    )

                    await asyncio.sleep(
                        wait_time
                    )

                    continue

                print(
                    "  ✗ Read timeout. Skipped."
                )

                return url, None

            except httpx.ConnectTimeout:

                print(
                    "  ✗ Connection timeout. Skipped."
                )

                return url, None

            except httpx.HTTPStatusError as e:

                print(
                    f"  ✗ HTTP "
                    f"{e.response.status_code}"
                )

                return url, None

            except Exception as e:

                print(
                    f"  ✗ {type(e).__name__}: {e}"
                )

                return url, None

    return url, None


async def get_website_links(
    url: str
) -> list[str]:

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=15,
            read=30,
            write=15,
            pool=15
        ),
        follow_redirects=True
    ) as client:

        response = await client.get(
            url,
            headers={
                "User-Agent": USER_AGENT
            }
        )

        response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    base_domain = urlparse(
        url
    ).netloc.lower()

    links = set()

    for tag in soup.find_all(
        "a",
        href=True
    ):

        absolute_url = urljoin(
            url,
            tag["href"]
        )

        parsed = urlparse(
            absolute_url
        )

        # Same domain only
        if parsed.netloc.lower() != base_domain:
            continue

        # HTTP / HTTPS only
        if parsed.scheme not in {
            "http",
            "https"
        }:
            continue

        clean_url = absolute_url.split(
            "#"
        )[0]

        lower_url = clean_url.lower()

        # Block WordPress/admin URLs
        blocked_paths = (
            "/wp-login.php",
            "/wp-admin",
            "/wp-json",
            "/xmlrpc.php",
            "/feed/",
            "/author/"
        )

        if any(
            path in lower_url
            for path in blocked_paths
        ):
            continue

        # Block files
        blocked_extensions = (
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".webp",
            ".svg",
            ".pdf",
            ".zip",
            ".mp4",
            ".mp3"
        )

        if lower_url.endswith(
            blocked_extensions
        ):
            continue

        links.add(
            clean_url
        )

    return sorted(links)


async def crawl_website(
    url: str
) -> list[tuple[str, str]]:

    links = await get_website_links(
        url
    )

    print(
        f"\nFound {len(links)} pages.\n"
    )

    semaphore = asyncio.Semaphore(
        MAX_CONCURRENT_REQUESTS
    )

    timeout = httpx.Timeout(
        connect=15,
        read=60,
        write=15,
        pool=15
    )

    limits = httpx.Limits(
        max_connections=MAX_CONCURRENT_REQUESTS,
        max_keepalive_connections=MAX_CONCURRENT_REQUESTS
    )

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=True
    ) as client:

        tasks = [
            fetch_page(
                client,
                semaphore,
                link,
                index,
                len(links)
            )
            for index, link in enumerate(
                links,
                start=1
            )
        ]

        results = await asyncio.gather(
            *tasks
        )

    pages = [
        (page_url, text)
        for page_url, text in results
        if text
    ]

    print(
        f"\nSuccessfully fetched "
        f"{len(pages)} pages."
    )

    return pages

async def fetch_page_direct(
    url: str
) -> str | None:

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True
    ) as client:

        try:

            response = await client.get(
                url,
                headers={
                    "User-Agent": USER_AGENT
                }
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            for tag in soup([
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "aside"
            ]):
                tag.decompose()

            main_content = (
                soup.find("main")
                or soup.find("article")
                or soup.body
            )

            if not main_content:
                return None

            text = main_content.get_text(
                separator=" ",
                strip=True
            )

            return " ".join(
                text.split()
            )

        except Exception as e:

            print(
                f"Website search failed: "
                f"{type(e).__name__}: {e}"
            )

            return None

async def find_candidate_urls(
    query: str,
    website: str
) -> list[str]:

    links = await get_website_links(
        website
    )

    query_words = set(
        query.lower().split()
    )

    scored = []

    for url in links:

        url_text = (
            urlparse(url)
            .path
            .replace("/", " ")
            .replace("-", " ")
            .replace("_", " ")
            .lower()
        )

        score = sum(
            1
            for word in query_words
            if word in url_text
        )

        scored.append(
            (score, url)
        )

    scored.sort(
        key=lambda x: x[0],
        reverse=True
    )

    return [
        url
        for score, url in scored[:5]
        if score > 0
    ]