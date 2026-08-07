import csv
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ddgs import DDGS


# ============================================================
# SETTINGS
# ============================================================

MAX_RESULTS_PER_QUERY = 20
SEARCH_TIMEOUT_SECONDS = 6

# Prevents the search from running forever
MAX_TOTAL_SEARCH_SECONDS = 150

MAX_JOBS_IN_ISSUE = 40


# ============================================================
# SEARCH QUERIES
#
# ANYWHERE IN THE UNITED STATES
# ============================================================

def build_search_queries():

    return [

        # ====================================================
        # VP - PRODUCT DEVELOPMENT
        # ====================================================

        '"VP Product Development" "United States"',
        '"VP of Product Development" "United States"',
        '"Vice President Product Development" "United States"',
        '"Vice President of Product Development" "United States"',


        # ====================================================
        # VP - PRODUCT
        # ====================================================

        '"VP Product" "United States"',
        '"VP of Product" "United States"',
        '"Vice President Product" "United States"',
        '"Vice President of Product" "United States"',


        # ====================================================
        # VP - SOURCING
        # ====================================================

        '"VP Sourcing" "United States"',
        '"VP of Sourcing" "United States"',
        '"Vice President Sourcing" "United States"',
        '"Vice President of Sourcing" "United States"',


        # ====================================================
        # PRODUCT DEVELOPMENT DIRECTORS
        # ====================================================

        '"Director Product Development" "United States"',
        '"Director of Product Development" "United States"',
        '"Senior Director Product Development" "United States"',
        '"Senior Director of Product Development" "United States"',


        # ====================================================
        # SOURCING DIRECTORS
        # ====================================================

        '"Director Sourcing" "United States"',
        '"Director of Sourcing" "United States"',
        '"Senior Director Sourcing" "United States"',
        '"Director Strategic Sourcing" "United States"',


        # ====================================================
        # CATEGORY DIRECTORS
        # ====================================================

        '"Category Director" "United States"',
        '"Senior Category Director" "United States"',
        '"Director Category Management" "United States"',
        '"Director of Category Management" "United States"',


        # ====================================================
        # CATEGORY MANAGERS
        # ====================================================

        '"Category Manager" "United States"',
        '"Senior Category Manager" "United States"',
        '"Category Management Manager" "United States"',


        # ====================================================
        # PRODUCT DEVELOPMENT + SOURCING
        # ====================================================

        '"VP" "Product Development" "Sourcing" "United States"',
        '"Director" "Product Development" "Sourcing" "United States"',


        # ====================================================
        # HEAD POSITIONS
        # ====================================================

        '"Head of Product Development" "United States"',
        '"Head of Product" "United States"',
        '"Head of Sourcing" "United States"',


        # ====================================================
        # DIRECT CAREER SYSTEM SEARCHES
        # ====================================================

        'site:myworkdayjobs.com '
        '("VP Product" OR '
        '"VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing" OR '
        '"Category Director" OR '
        '"Category Manager") '
        '"United States"',

        'site:greenhouse.io '
        '("VP Product" OR '
        '"VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing" OR '
        '"Category Director" OR '
        '"Category Manager") '
        '"United States"',

        'site:lever.co '
        '("VP Product" OR '
        '"VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing" OR '
        '"Category Director" OR '
        '"Category Manager") '
        '"United States"',

        'site:smartrecruiters.com '
        '("VP Product" OR '
        '"VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing" OR '
        '"Category Director" OR '
        '"Category Manager") '
        '"United States"',

        'site:ashbyhq.com '
        '("VP Product" OR '
        '"VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing" OR '
        '"Category Director" OR '
        '"Category Manager") '
        '"United States"',
    ]


# ============================================================
# JOB SITES WE COMPLETELY BLOCK
#
# THESE ARE SEARCH SITES — NOT EMPLOYERS.
# ============================================================

BLOCKED_JOB_SITES = (
    "indeed.com",
    "linkedin.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "simplyhired.com",
    "monster.com",
    "careerbuilder.com",
    "talent.com",
    "jooble.org",
    "lensa.com",
    "jobgether.com",
)


# ============================================================
# REAL ATS / COMPANY RECRUITING SYSTEMS
#
# THESE ARE ALLOWED.
# ============================================================

ATS_DOMAINS = (
    "myworkdayjobs.com",
    "greenhouse.io",
    "lever.co",
    "smartrecruiters.com",
    "icims.com",
    "taleo.net",
    "successfactors.com",
    "ashbyhq.com",
)


# ============================================================
# NAMES THAT CAN NEVER BE AN EMPLOYER
# ============================================================

INVALID_COMPANY_NAMES = (
    "indeed",
    "linkedin",
    "glassdoor",
    "ziprecruiter",
    "zip recruiter",
    "simplyhired",
    "simply hired",
    "monster",
    "careerbuilder",
    "career builder",
    "talent",
    "jooble",
    "lensa",
    "jobgether",

    "google",
    "google jobs",
    "bing",

    "job",
    "jobs",
    "career",
    "careers",
    "employment",
    "apply",

    "workday",
    "myworkdayjobs",
    "greenhouse",
    "lever",
    "smartrecruiters",
    "icims",
    "taleo",
    "successfactors",
    "ashby",
    "ashbyhq",
)


# ============================================================
# USA LOCATION DETECTION
# ============================================================

US_STATE_NAMES = (
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
    "district of columbia",
)


US_STATE_CODES = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE",
    "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
    "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
)


REMOTE_TERMS = (
    "remote",
    "fully remote",
    "work from home",
    "work-from-home",
    "remote - us",
    "remote us",
    "remote, us",
    "remote united states",
    "remote - united states",
)


# ============================================================
# CSV COLUMNS
# ============================================================

CSV_FIELDS = [
    "company",
    "title",
    "role_category",
    "location_type",
    "first_seen_utc",
    "priority_score",
    "source_domain",
    "url",
    "search_query",
    "snippet",
]


TRACKING_KEYS = {
    "ref",
    "referrer",
    "source",
    "src",
    "trk",
    "trackingid",
    "gh_src",
}


# ============================================================
# BASIC CLEANING
# ============================================================

def clean_text(text):

    text = str(text or "")

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return (
        text
        .replace("<", "")
        .replace(">", "")
    )


def canonicalize_url(url):

    try:

        parts = urlsplit(
            url.strip()
        )

        kept_query = []

        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True
        ):

            lower_key = key.lower()

            if lower_key.startswith("utm_"):
                continue

            if lower_key in TRACKING_KEYS:
                continue

            kept_query.append(
                (key, value)
            )

        path = (
            parts.path.rstrip("/")
            or "/"
        )

        return urlunsplit(
            (
                parts.scheme.lower(),
                parts.netloc.lower(),
                path,
                urlencode(
                    kept_query,
                    doseq=True
                ),
                "",
            )
        )

    except Exception:

        return url.strip()


def domain_from_url(url):

    try:

        return (
            urlsplit(url)
            .netloc
            .lower()
            .removeprefix("www.")
        )

    except Exception:

        return ""


# ============================================================
# BLOCK INDEED / LINKEDIN / ETC.
# ============================================================

def is_blocked_job_site(url):

    domain = domain_from_url(
        url
    )

    return any(
        blocked in domain
        for blocked in BLOCKED_JOB_SITES
    )


# ============================================================
# USA LOCATION DETECTION
# ============================================================

def get_location_type(
    title,
    snippet,
    query=""
):

    combined = (
        f"{title} {snippet} {query}"
        .lower()
    )


    # --------------------------------------------------------
    # REMOTE USA
    # --------------------------------------------------------

    if any(
        term in combined
        for term in REMOTE_TERMS
    ):

        return "Remote - USA"


    # --------------------------------------------------------
    # UNITED STATES LANGUAGE
    # --------------------------------------------------------

    if any(
        term in combined
        for term in (
            "united states",
            "usa",
            "u.s.",
            "u.s.a.",
            "us based",
            "us-based",
        )
    ):

        return "USA"


    # --------------------------------------------------------
    # FULL STATE NAME
    # --------------------------------------------------------

    if any(
        state in combined
        for state in US_STATE_NAMES
    ):

        return "USA"


    # --------------------------------------------------------
    # CITY, STATE CODE
    #
    # Examples:
    # Chicago, IL
    # New York, NY
    # Dallas, TX
    # --------------------------------------------------------

    state_pattern = (
        r",\s*("
        + "|".join(
            US_STATE_CODES
        )
        + r")\b"
    )

    if re.search(
        state_pattern,
        f"{title} {snippet}",
        flags=re.IGNORECASE
    ):

        return "USA"


    # Every broad query in this bot is explicitly
    # targeted to the United States.
    if "united states" in query.lower():

        return "USA"


    return None


# ============================================================
# ROLE CATEGORY
# ============================================================

def get_role_category(title):

    title_lower = (
        title.lower()
    )


    has_product_development = (
        "product development"
        in title_lower
    )


    has_product = (
        "product"
        in title_lower
    )


    has_sourcing = (
        "sourcing"
        in title_lower
    )


    has_category = (
        "category"
        in title_lower
        or
        "category management"
        in title_lower
    )


    is_vp = any(
        term in title_lower
        for term in (
            "vice president",
            "vp ",
            "vp,",
            "vp -",
            "vp:",
            "vp/",
        )
    )


    is_senior_director = any(
        term in title_lower
        for term in (
            "senior director",
            "sr director",
            "sr. director",
        )
    )


    is_director = (
        "director"
        in title_lower
    )


    is_head = (
        "head of"
        in title_lower
    )


    is_senior_category_manager = any(
        term in title_lower
        for term in (
            "senior category manager",
            "sr category manager",
            "sr. category manager",
        )
    )


    is_category_manager = (
        "category manager"
        in title_lower
    )


    # ========================================================
    # VP
    # ========================================================

    if (
        is_vp
        and has_product_development
        and has_sourcing
    ):

        return (
            "VP - Product Development & Sourcing"
        )


    if (
        is_vp
        and has_product_development
    ):

        return (
            "VP - Product Development"
        )


    if (
        is_vp
        and has_sourcing
    ):

        return (
            "VP - Sourcing"
        )


    if (
        is_vp
        and has_product
    ):

        return (
            "VP - Product"
        )


    # ========================================================
    # SENIOR CATEGORY DIRECTOR
    # ========================================================

    if (
        is_senior_director
        and has_category
    ):

        return (
            "Senior Category Director"
        )


    # ========================================================
    # SENIOR DIRECTORS
    # ========================================================

    if (
        is_senior_director
        and has_product_development
        and has_sourcing
    ):

        return (
            "Senior Director - "
            "Product Development & Sourcing"
        )


    if (
        is_senior_director
        and has_product_development
    ):

        return (
            "Senior Director - Product Development"
        )


    if (
        is_senior_director
        and has_sourcing
    ):

        return (
            "Senior Director - Sourcing"
        )


    # ========================================================
    # CATEGORY DIRECTOR
    # ========================================================

    if (
        is_director
        and has_category
    ):

        return (
            "Category Director"
        )


    # ========================================================
    # DIRECTORS
    # ========================================================

    if (
        is_director
        and has_product_development
        and has_sourcing
    ):

        return (
            "Director - Product Development & Sourcing"
        )


    if (
        is_director
        and has_product_development
    ):

        return (
            "Director - Product Development"
        )


    if (
        is_director
        and has_sourcing
    ):

        return (
            "Director - Sourcing"
        )


    # ========================================================
    # HEAD
    # ========================================================

    if (
        is_head
        and has_product_development
    ):

        return (
            "Head - Product Development"
        )


    if (
        is_head
        and has_sourcing
    ):

        return (
            "Head - Sourcing"
        )


    if (
        is_head
        and has_product
    ):

        return (
            "Head - Product"
        )


    # ========================================================
    # CATEGORY MANAGEMENT
    # ========================================================

    if is_senior_category_manager:

        return (
            "Senior Category Manager"
        )


    if is_category_manager:

        return (
            "Category Manager"
        )


    return None


# ============================================================
# RELEVANT ROLE FILTER
# ============================================================

def is_relevant_role(title):

    title_lower = (
        title.lower()
    )


    category = (
        get_role_category(
            title
        )
    )


    if category is None:
        return False


    # --------------------------------------------------------
    # REMOVE JUNIOR / UNWANTED ROLES
    # --------------------------------------------------------

    bad_levels = (
        "intern",
        "internship",
        "assistant category manager",
        "associate category manager",
        "category management associate",
        "category management coordinator",
        "coordinator",
    )


    if any(
        bad in title_lower
        for bad in bad_levels
    ):

        return False


    return True


# ============================================================
# COMPANY VALIDATION
# ============================================================

def validate_company(company):

    if not company:
        return None


    company = (
        clean_text(
            company
        )
    )


    company = (
        company
        .replace("®", "")
        .replace("™", "")
        .strip(" -|:")
    )


    normalized = (
        company
        .lower()
        .replace("www.", "")
        .strip()
    )


    normalized = re.sub(
        r"\.(com|org|net|co|io)$",
        "",
        normalized
    )


    for invalid in INVALID_COMPANY_NAMES:

        invalid_normalized = (
            invalid
            .lower()
            .replace("www.", "")
        )


        invalid_normalized = re.sub(
            r"\.(com|org|net|co|io)$",
            "",
            invalid_normalized
        )


        if (
            normalized
            == invalid_normalized
        ):

            return None


    if len(company) < 2:
        return None


    if len(company) > 80:
        return None


    return company


# ============================================================
# CLEAN COMPANY NAME FROM URL SLUG
# ============================================================

def humanize_slug(text):

    text = (
        str(text)
        .replace("-", " ")
        .replace("_", " ")
    )


    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()


    if not text:
        return None


    return validate_company(
        text.title()
    )


# ============================================================
# COMPANY FROM ATS URL
# ============================================================

def company_from_ats_url(url):

    try:

        parts = urlsplit(
            url
        )


        host = (
            parts.netloc
            .lower()
            .removeprefix("www.")
        )


        path_parts = [
            part
            for part in
            parts.path.split("/")
            if part
        ]


        # ====================================================
        # WORKDAY
        # ====================================================

        if host.endswith(
            "myworkdayjobs.com"
        ):

            first = (
                host.split(".")[0]
            )


            if not re.fullmatch(
                r"wd\d+",
                first
            ):

                company = (
                    humanize_slug(
                        first
                    )
                )


                if company:
                    return company


        # ====================================================
        # LEVER
        # ====================================================

        if host.endswith(
            "lever.co"
        ):

            if path_parts:

                company = (
                    humanize_slug(
                        path_parts[0]
                    )
                )


                if company:
                    return company


        # ====================================================
        # GREENHOUSE
        # ====================================================

        if host.endswith(
            "greenhouse.io"
        ):

            ignored = {
                "jobs",
                "job",
                "embed",
            }


            for part in path_parts:

                if (
                    part.lower()
                    not in ignored
                ):

                    company = (
                        humanize_slug(
                            part
                        )
                    )


                    if company:
                        return company


        # ====================================================
        # SMARTRECRUITERS
        # ====================================================

        if host.endswith(
            "smartrecruiters.com"
        ):

            if path_parts:

                company = (
                    humanize_slug(
                        path_parts[0]
                    )
                )


                if company:
                    return company


        # ====================================================
        # ASHBY
        # ====================================================

        if host.endswith(
            "ashbyhq.com"
        ):

            if path_parts:

                company = (
                    humanize_slug(
                        path_parts[0]
                    )
                )


                if company:
                    return company


    except Exception:

        pass


    return None


# ============================================================
# COMPANY FROM TITLE
# ============================================================

def company_from_title(title):

    separators = (
        " at ",
        " | ",
        " - ",
        " – ",
        " — ",
    )


    for separator in separators:

        if (
            separator.lower()
            not in title.lower()
        ):

            continue


        parts = re.split(
            re.escape(separator),
            title,
            flags=re.IGNORECASE
        )


        if len(parts) < 2:
            continue


        candidate = (
            parts[-1]
            .strip()
        )


        lower = (
            candidate.lower()
        )


        bad_terms = (
            "remote",
            "united states",
            "director",
            "vice president",
            "product development",
            "category manager",
            "category director",
            "sourcing",
        )


        if any(
            bad in lower
            for bad in bad_terms
        ):

            continue


        company = (
            validate_company(
                candidate
            )
        )


        if company:
            return company


    return None


# ============================================================
# COMPANY FROM SEARCH DESCRIPTION
# ============================================================

def company_from_snippet(
    title,
    snippet
):

    combined = (
        f"{title} {snippet}"
    )


    patterns = (

        r"([A-Z][A-Za-z0-9&.'’ -]{1,50}?) "
        r"is hiring",

        r"at "
        r"([A-Z][A-Za-z0-9&.'’ -]{1,50}?)"
        r"(?:[,.|]| in | is | - )",

        r"join "
        r"([A-Z][A-Za-z0-9&.'’ -]{1,50}?)"
        r"(?:[,.|]| in | as | - )",
    )


    for pattern in patterns:

        match = re.search(
            pattern,
            combined
        )


        if not match:
            continue


        candidate = (
            match.group(1)
            .strip()
        )


        company = (
            validate_company(
                candidate
            )
        )


        if company:
            return company


    return None


# ============================================================
# COMPANY FROM DIRECT EMPLOYER DOMAIN
#
# careers.nike.com -> Nike
# ============================================================

def company_from_regular_domain(url):

    domain = (
        domain_from_url(
            url
        )
    )


    if not domain:
        return None


    if is_blocked_job_site(
        url
    ):

        return None


    if any(
        ats in domain
        for ats in ATS_DOMAINS
    ):

        return None


    pieces = (
        domain.split(".")
    )


    if len(pieces) < 2:
        return None


    candidate = (
        pieces[-2]
    )


    return humanize_slug(
        candidate
    )


# ============================================================
# IDENTIFY ACTUAL EMPLOYER
# ============================================================

def identify_company(
    title,
    snippet,
    url
):

    # ATS URL
    company = (
        company_from_ats_url(
            url
        )
    )


    company = (
        validate_company(
            company
        )
    )


    if company:
        return company


    # Job title
    company = (
        company_from_title(
            title
        )
    )


    company = (
        validate_company(
            company
        )
    )


    if company:
        return company


    # Search description
    company = (
        company_from_snippet(
            title,
            snippet
        )
    )


    company = (
        validate_company(
            company
        )
    )


    if company:
        return company


    # Employer's own website
    company = (
        company_from_regular_domain(
            url
        )
    )


    company = (
        validate_company(
            company
        )
    )


    if company:
        return company


    return None


# ============================================================
# PRIORITY SCORE
# ============================================================

def priority_score(
    title,
    snippet,
    url,
    company
):

    category = (
        get_role_category(
            title
        )
    )


    domain = (
        domain_from_url(
            url
        )
    )


    score = 0


    # ========================================================
    # VP - HIGHEST PRIORITY
    # ========================================================

    scoring = {

        "VP - Product Development & Sourcing": 35,

        "VP - Product Development": 32,

        "VP - Product": 30,

        "VP - Sourcing": 28,

        "Senior Director - Product Development & Sourcing": 27,

        "Senior Director - Product Development": 25,

        "Senior Category Director": 24,

        "Senior Director - Sourcing": 23,

        "Director - Product Development & Sourcing": 23,

        "Director - Product Development": 22,

        "Category Director": 21,

        "Head - Product Development": 22,

        "Head - Product": 21,

        "Director - Sourcing": 20,

        "Head - Sourcing": 20,

        "Senior Category Manager": 18,

        "Category Manager": 15,
    }


    score += scoring.get(
        category,
        0
    )


    location = (
        get_location_type(
            title,
            snippet
        )
    )


    if location == "Remote - USA":

        score += 4


    elif location == "USA":

        score += 3


    if company:

        score += 3


    # Direct company ATS gets bonus
    if any(
        ats in domain
        for ats in ATS_DOMAINS
    ):

        score += 5


    return score


# ============================================================
# DUPLICATE KEY
# ============================================================

def normalize_for_key(text):

    text = (
        str(text or "")
        .lower()
    )


    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text
    )


    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def job_key(job):

    return (

        normalize_for_key(
            job.get(
                "company",
                ""
            )
        ),

        normalize_for_key(
            job.get(
                "title",
                ""
            )
        ),
    )


# ============================================================
# LOAD EXISTING JOBS
# ============================================================

def load_existing_jobs():

    existing = {}


    if not os.path.exists(
        "jobs.csv"
    ):

        return existing


    with open(
        "jobs.csv",
        "r",
        newline="",
        encoding="utf-8"
    ) as file:

        reader = (
            csv.DictReader(
                file
            )
        )


        for row in reader:

            title = clean_text(
                row.get(
                    "title",
                    ""
                )
            )


            snippet = clean_text(
                row.get(
                    "snippet",
                    ""
                )
            )


            url = clean_text(
                row.get(
                    "url",
                    ""
                )
            )


            if not title or not url:
                continue


            # Remove blocked search sites
            if is_blocked_job_site(
                url
            ):

                continue


            # Remove irrelevant positions
            if not is_relevant_role(
                title
            ):

                continue


            company = (
                validate_company(
                    row.get(
                        "company",
                        ""
                    )
                )
            )


            if not company:

                company = (
                    identify_company(
                        title,
                        snippet,
                        url
                    )
                )


            if not company:
                continue


            row[
                "company"
            ] = company


            row[
                "role_category"
            ] = get_role_category(
                title
            )


            row[
                "url"
            ] = canonicalize_url(
                url
            )


            key = (
                job_key(
                    row
                )
            )


            existing[
                key
            ] = row


    return existing


# ============================================================
# PROCESS ONE SEARCH RESULT
# ============================================================

def process_result(
    result,
    query
):

    title = (
        clean_text(
            result.get(
                "title"
            )
        )
    )


    url = (
        clean_text(
            result.get(
                "href"
            )
            or result.get(
                "url"
            )
        )
    )


    snippet = (
        clean_text(
            result.get(
                "body"
            )
            or result.get(
                "snippet"
            )
        )
    )


    if not title or not url:

        return None


    # ========================================================
    # BLOCK INDEED/LINKEDIN/etc.
    # ========================================================

    if is_blocked_job_site(
        url
    ):

        print(
            "  BLOCKED:",
            domain_from_url(url)
        )

        return None


    # ========================================================
    # CORRECT ROLE
    # ========================================================

    if not is_relevant_role(
        title
    ):

        return None


    # ========================================================
    # USA ONLY
    # ========================================================

    location_type = (
        get_location_type(
            title,
            snippet,
            query
        )
    )


    if not location_type:

        print(
            "  SKIPPED - could not verify USA:",
            title
        )

        return None


    url = (
        canonicalize_url(
            url
        )
    )


    # ========================================================
    # REAL EMPLOYER REQUIRED
    # ========================================================

    company = (
        identify_company(
            title,
            snippet,
            url
        )
    )


    company = (
        validate_company(
            company
        )
    )


    if not company:

        print(
            "  SKIPPED - no real employer:",
            title
        )

        return None


    category = (
        get_role_category(
            title
        )
    )


    score = (
        priority_score(
            title,
            snippet,
            url,
            company
        )
    )


    return {

        "company":
            company,

        "title":
            title,

        "role_category":
            category,

        "location_type":
            location_type,

        "first_seen_utc":
            datetime.now(
                timezone.utc
            ).isoformat(
                timespec="seconds"
            ),

        "priority_score":
            str(score),

        "source_domain":
            domain_from_url(
                url
            ),

        "url":
            url,

        "search_query":
            query,

        "snippet":
            snippet[:500],
    }


# ============================================================
# SEARCH THE WEB
# ============================================================

def search_web():

    queries = (
        build_search_queries()
    )


    print(
        f"Running {len(queries)} "
        "USA leadership searches."
    )


    print(
        f"Maximum search time: "
        f"{MAX_TOTAL_SEARCH_SECONDS} seconds."
    )


    print()


    found = {}

    successful_queries = 0

    start_time = (
        time.monotonic()
    )


    search_engine = (
        DDGS(
            timeout=
            SEARCH_TIMEOUT_SECONDS
        )
    )


    for number, query in enumerate(
        queries,
        start=1
    ):

        elapsed = (
            time.monotonic()
            - start_time
        )


        if (
            elapsed
            >= MAX_TOTAL_SEARCH_SECONDS
        ):

            print()

            print(
                "Search time limit reached."
            )

            print(
                "Saving results found so far."
            )

            break


        print(
            f"[{number}/{len(queries)}] "
            f"{query}"
        )


        try:

            results = list(
                search_engine.text(
                    query,

                    region="us-en",

                    safesearch="moderate",

                    timelimit="y",

                    max_results=
                    MAX_RESULTS_PER_QUERY,

                    backend="auto",
                )
                or []
            )


            successful_queries += 1


        except Exception as error:

            print(
                "  Search failed:",
                type(error).__name__,
                str(error)[:150]
            )

            continue


        print(
            "  Raw results:",
            len(results)
        )


        for result in results:

            job = (
                process_result(
                    result,
                    query
                )
            )


            if not job:

                continue


            key = (
                job_key(
                    job
                )
            )


            previous = (
                found.get(
                    key
                )
            )


            if previous:

                old_score = int(
                    previous.get(
                        "priority_score",
                        0
                    )
                    or 0
                )


                new_score = int(
                    job.get(
                        "priority_score",
                        0
                    )
                    or 0
                )


                if (
                    new_score
                    <= old_score
                ):

                    continue


            found[
                key
            ] = job


        time.sleep(
            0.25
        )


    if successful_queries == 0:

        raise RuntimeError(
            "Every web search failed. "
            "Try again later."
        )


    elapsed = (
        time.monotonic()
        - start_time
    )


    print()

    print(
        f"Search finished in "
        f"{elapsed:.1f} seconds."
    )


    print(
        "Valid unique jobs found:",
        len(found)
    )


    return found


# ============================================================
# SAVE JOBS.CSV
# ============================================================

def save_master_csv(
    existing,
    found
):

    combined = dict(
        existing
    )


    for key, job in found.items():

        if key in combined:

            old_first_seen = (
                combined[key]
                .get(
                    "first_seen_utc"
                )
            )


            old_score = int(
                combined[key]
                .get(
                    "priority_score",
                    0
                )
                or 0
            )


            new_score = int(
                job.get(
                    "priority_score",
                    0
                )
                or 0
            )


            if new_score > old_score:

                if old_first_seen:

                    job[
                        "first_seen_utc"
                    ] = old_first_seen


                combined[
                    key
                ] = job


        else:

            combined[
                key
            ] = job


    rows = list(
        combined.values()
    )


    rows.sort(

        key=lambda row: (

            int(
                row.get(
                    "priority_score",
                    0
                )
                or 0
            ),

            row.get(
                "first_seen_utc",
                ""
            ),
        ),

        reverse=True,
    )


    with open(
        "jobs.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = (
            csv.DictWriter(
                file,
                fieldnames=
                CSV_FIELDS
            )
        )


        writer.writeheader()


        for row in rows:

            writer.writerow(
                {
                    field:
                    row.get(
                        field,
                        ""
                    )

                    for field
                    in CSV_FIELDS
                }
            )


# ============================================================
# NEW JOB ALERT
# ============================================================

def write_new_jobs_report(
    new_jobs
):

    ordered = sorted(

        new_jobs,

        key=lambda job:
        int(
            job.get(
                "priority_score",
                0
            )
            or 0
        ),

        reverse=True,
    )


    with open(
        "new_jobs_count.txt",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            str(
                len(ordered)
            )
        )


    now = (
        datetime.now(
            timezone.utc
        )
        .strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    )


    lines = [

        f"# {len(ordered)} new leadership job(s)",

        "",

        f"Search completed: {now}",

        "",

        "**Search criteria:**",

        "- United States only",

        "- U.S. remote positions included",

        "- VP Product",

        "- VP Product Development",

        "- VP Sourcing",

        "- Director / Senior Director Product Development",

        "- Director / Senior Director Sourcing",

        "- Category Director",

        "- Category Manager",

        "- Senior Category Manager",

        "- Head of Product / Product Development / Sourcing",

        "- Actual employer required",

        "- Indeed / LinkedIn / Glassdoor / "
        "ZipRecruiter blocked",

        "",
    ]


    if not ordered:

        lines.append(
            "No new matching leadership "
            "positions were found."
        )


    else:

        for number, job in enumerate(
            ordered[
                :MAX_JOBS_IN_ISSUE
            ],
            start=1
        ):

            lines.extend(
                [

                    f"## {number}. "
                    f"{job['company']}",

                    f"### {job['title']}",

                    "",

                    f"- **Company:** "
                    f"{job['company']}",

                    f"- **Category:** "
                    f"{job['role_category']}",

                    f"- **Location:** "
                    f"{job['location_type']}",

                    f"- **Priority Score:** "
                    f"{job['priority_score']}",

                    f"- **Source:** "
                    f"{job['source_domain']}",

                    f"- **Apply / View:** "
                    f"{job['url']}",

                    "",
                ]
            )


            if job.get(
                "snippet"
            ):

                lines.append(
                    f"> {job['snippet']}"
                )

                lines.append("")


    report = "\n".join(
        lines
    )


    with open(
        "new_jobs.md",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            report
        )


    summary_path = (
        os.getenv(
            "GITHUB_STEP_SUMMARY"
        )
    )


    if summary_path:

        with open(
            summary_path,
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                report
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "======================================"
    )

    print(
        "PRODUCT / SOURCING LEADERSHIP FINDER"
    )

    print(
        "======================================"
    )

    print()

    print(
        "Searching anywhere in the USA for:"
    )

    print(
        "- VP Product"
    )

    print(
        "- VP Product Development"
    )

    print(
        "- VP Sourcing"
    )

    print(
        "- Director Product Development"
    )

    print(
        "- Director Sourcing"
    )

    print(
        "- Category Director"
    )

    print(
        "- Category Manager"
    )

    print(
        "- Senior Category Manager"
    )

    print(
        "- Head roles"
    )

    print()

    print(
        "Indeed / LinkedIn / Glassdoor / "
        "ZipRecruiter are blocked."
    )

    print()


    existing = (
        load_existing_jobs()
    )


    existing_keys = set(
        existing.keys()
    )


    print(
        "Previously saved valid jobs:",
        len(existing)
    )

    print()


    found = (
        search_web()
    )


    new_jobs = [

        job

        for key, job
        in found.items()

        if key
        not in existing_keys
    ]


    print()

    print(
        "Valid jobs found this search:",
        len(found)
    )


    print(
        "Brand-new jobs:",
        len(new_jobs)
    )


    save_master_csv(
        existing,
        found
    )


    write_new_jobs_report(
        new_jobs
    )


    print()

    print(
        "======================================"
    )

    print(
        "DONE"
    )

    print(
        "======================================"
    )

    print(
        "Master database: jobs.csv"
    )

    print(
        "New-job report: new_jobs.md"
    )


if __name__ == "__main__":
    main()
