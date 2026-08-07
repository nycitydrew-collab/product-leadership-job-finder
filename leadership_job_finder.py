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

# Hard limit so the search does not run forever
MAX_TOTAL_SEARCH_SECONDS = 150

MAX_JOBS_IN_ISSUE = 40


# ============================================================
# LOCATION FILTER
#
# ONLY:
# - NEW YORK CITY
# - REMOTE
# ============================================================

NYC_TERMS = (
    "new york, ny",
    "new york ny",
    "new york city",
    "new york, new york",
    "nyc",
    "manhattan",
    "brooklyn",
    "queens",
    "bronx",
    "staten island",
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


NOT_REMOTE_TERMS = (
    "not remote",
    "no remote",
    "onsite only",
    "on-site only",
    "must work onsite",
    "must work on-site",
)


# ============================================================
# JOB BOARD / AGGREGATOR SITES
#
# IMPORTANT:
# WE COMPLETELY REJECT RESULTS FROM THESE SITES.
#
# We do not want Indeed to show as the company.
# We don't even save the Indeed result.
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
# REAL RECRUITING SYSTEMS
#
# These are allowed because they host jobs FOR companies.
# We will try to identify the actual employer.
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
# INVALID COMPANY NAMES
#
# THESE CAN NEVER BE SAVED AS THE EMPLOYER
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
# SEARCH QUERIES
#
# These are deliberately targeted so we do not make
# 100+ searches like the first version of the actuarial bot.
# ============================================================

def build_search_queries():

    return [

        # ====================================================
        # VP - PRODUCT DEVELOPMENT
        # ====================================================

        '"VP Product Development" ("New York" OR remote)',

        '"VP of Product Development" ("New York" OR remote)',

        '"Vice President Product Development" '
        '("New York" OR remote)',

        '"Vice President of Product Development" '
        '("New York" OR remote)',


        # ====================================================
        # VP - SOURCING
        # ====================================================

        '"VP Sourcing" ("New York" OR remote)',

        '"VP of Sourcing" ("New York" OR remote)',

        '"Vice President Sourcing" '
        '("New York" OR remote)',

        '"Vice President of Sourcing" '
        '("New York" OR remote)',


        # ====================================================
        # VP - PRODUCT DEVELOPMENT + SOURCING
        # ====================================================

        '"VP" "Product Development" "Sourcing" '
        '("New York" OR remote)',


        # ====================================================
        # DIRECTOR - PRODUCT DEVELOPMENT
        # ====================================================

        '"Director Product Development" '
        '("New York" OR remote)',

        '"Director of Product Development" '
        '("New York" OR remote)',

        '"Senior Director Product Development" '
        '("New York" OR remote)',


        # ====================================================
        # DIRECTOR - SOURCING
        # ====================================================

        '"Director Sourcing" '
        '("New York" OR remote)',

        '"Director of Sourcing" '
        '("New York" OR remote)',

        '"Senior Director Sourcing" '
        '("New York" OR remote)',

        '"Director Strategic Sourcing" '
        '("New York" OR remote)',


        # ====================================================
        # PRODUCT DEVELOPMENT + SOURCING
        # ====================================================

        '"Director" "Product Development" "Sourcing" '
        '("New York" OR remote)',


        # ====================================================
        # HEAD ROLES
        # ====================================================

        '"Head of Product Development" '
        '("New York" OR remote)',

        '"Head of Sourcing" '
        '("New York" OR remote)',


        # ====================================================
        # DIRECT ATS SEARCHES
        # ====================================================

        'site:myworkdayjobs.com '
        '("VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing") '
        '("New York" OR remote)',

        'site:greenhouse.io '
        '("VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing") '
        '("New York" OR remote)',

        'site:lever.co '
        '("VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing") '
        '("New York" OR remote)',

        'site:jobs.smartrecruiters.com '
        '("VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing") '
        '("New York" OR remote)',

        'site:ashbyhq.com '
        '("VP Product Development" OR '
        '"Director Product Development" OR '
        '"Director Sourcing") '
        '("New York" OR remote)',
    ]


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
# LOCATION DETECTION
# ============================================================

def get_location_type(
    title,
    snippet
):

    combined = (
        f"{title} {snippet}"
        .lower()
    )

    is_nyc = any(
        term in combined
        for term in NYC_TERMS
    )

    explicitly_not_remote = any(
        term in combined
        for term in NOT_REMOTE_TERMS
    )

    is_remote = (
        any(
            term in combined
            for term in REMOTE_TERMS
        )
        and not explicitly_not_remote
    )

    if is_nyc and is_remote:
        return "NYC / Remote"

    if is_nyc:
        return "NYC"

    if is_remote:
        return "Remote"

    return None


# ============================================================
# ROLE CATEGORY
#
# This lets jobs.csv organize positions.
# ============================================================

def get_role_category(title):

    title_lower = title.lower()

    has_product = (
        "product development"
        in title_lower
    )

    has_sourcing = (
        "sourcing"
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
        )
    )

    is_senior_director = (
        "senior director"
        in title_lower
    )

    is_director = (
        "director"
        in title_lower
    )

    is_head = (
        "head of"
        in title_lower
    )


    if is_vp and has_product and has_sourcing:

        return (
            "VP - Product Development & Sourcing"
        )


    if is_vp and has_product:

        return (
            "VP - Product Development"
        )


    if is_vp and has_sourcing:

        return (
            "VP - Sourcing"
        )


    if (
        is_senior_director
        and has_product
        and has_sourcing
    ):

        return (
            "Senior Director - "
            "Product Development & Sourcing"
        )


    if (
        is_senior_director
        and has_product
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


    if (
        is_director
        and has_product
        and has_sourcing
    ):

        return (
            "Director - Product Development & Sourcing"
        )


    if (
        is_director
        and has_product
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


    if (
        is_head
        and has_product
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


    return None


# ============================================================
# CHECK WHETHER TITLE IS ACTUALLY RELEVANT
# ============================================================

def is_relevant_role(title):

    title_lower = (
        title.lower()
    )


    # Must involve either Product Development or Sourcing
    has_target_function = any(
        phrase in title_lower
        for phrase in (
            "product development",
            "sourcing",
        )
    )


    if not has_target_function:
        return False


    # Must be leadership level
    has_leadership_level = any(
        phrase in title_lower
        for phrase in (
            "vice president",
            "vp ",
            "vp,",
            "vp -",
            "vp:",
            "director",
            "head of",
        )
    )


    if not has_leadership_level:
        return False


    # Remove obviously wrong junior roles
    bad_levels = (
        "intern",
        "internship",
        "assistant",
        "associate",
        "coordinator",
        "specialist",
    )


    if any(
        bad in title_lower
        for bad in bad_levels
    ):

        return False


    return (
        get_role_category(title)
        is not None
    )


# ============================================================
# COMPANY VALIDATION
# ============================================================

def validate_company(company):

    if not company:
        return None


    company = clean_text(
        company
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
# COMPANY SLUG CLEANING
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

        parts = urlsplit(url)

        host = (
            parts.netloc
            .lower()
            .removeprefix("www.")
        )

        path_parts = [
            part
            for part
            in parts.path.split("/")
            if part
        ]


        # ====================================================
        # WORKDAY
        #
        # Example:
        # nike.wd1.myworkdayjobs.com
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
        #
        # jobs.lever.co/company/job
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
#
# Examples:
#
# Director, Product Development - Nike
# VP Product Development | Ralph Lauren
# Director of Sourcing at Example Company
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


        possible_company = (
            parts[-1]
            .strip()
        )


        lower = (
            possible_company
            .lower()
        )


        # Avoid mistaking a location
        # for a company.
        bad_terms = (
            "new york",
            "remote",
            "nyc",
            "manhattan",
            "brooklyn",
            "queens",
            "bronx",
            "director",
            "vice president",
            "product development",
            "sourcing",
        )


        if any(
            bad in lower
            for bad in bad_terms
        ):

            continue


        company = (
            validate_company(
                possible_company
            )
        )


        if company:
            return company


    return None


# ============================================================
# COMPANY FROM SEARCH SNIPPET
#
# Search engines sometimes return text like:
#
# "Nike is hiring a Director of Product Development..."
# "Director Product Development at Ralph Lauren..."
# ============================================================

def company_from_snippet(
    title,
    snippet
):

    combined = (
        f"{title} {snippet}"
    )


    patterns = (

        r"([A-Z][A-Za-z0-9&.'’ -]{1,60}) "
        r"is hiring",

        r"at "
        r"([A-Z][A-Za-z0-9&.'’ -]{1,60})",

        r"join "
        r"([A-Z][A-Za-z0-9&.'’ -]{1,60})",
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


        # Stop very long accidental captures
        if len(candidate) > 60:
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
# COMPANY FROM DIRECT EMPLOYER DOMAIN
#
# careers.nike.com -> Nike
# jobs.coach.com -> Coach
# ============================================================

def company_from_regular_domain(url):

    domain = (
        domain_from_url(url)
    )


    if not domain:
        return None


    # Never identify company from a blocked board
    if is_blocked_job_site(
        url
    ):

        return None


    # ATS needs special logic instead
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

    # ========================================================
    # 1. ATS URL
    # ========================================================

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


    # ========================================================
    # 2. TITLE
    # ========================================================

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


    # ========================================================
    # 3. SEARCH DESCRIPTION
    # ========================================================

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


    # ========================================================
    # 4. DIRECT EMPLOYER WEBSITE
    # ========================================================

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


    # ========================================================
    # NO COMPANY = NO JOB
    # ========================================================

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

    title_lower = (
        title.lower()
    )

    combined = (
        f"{title} {snippet}"
        .lower()
    )

    domain = (
        domain_from_url(url)
    )

    category = (
        get_role_category(
            title
        )
    )

    score = 0


    # ========================================================
    # VP ROLES = HIGHEST PRIORITY
    # ========================================================

    if category == (
        "VP - Product Development & Sourcing"
    ):

        score += 30


    elif category == (
        "VP - Product Development"
    ):

        score += 28


    elif category == (
        "VP - Sourcing"
    ):

        score += 24


    # ========================================================
    # SENIOR DIRECTOR
    # ========================================================

    elif (
        category
        == "Senior Director - Product Development & Sourcing"
    ):

        score += 23


    elif (
        category
        == "Senior Director - Product Development"
    ):

        score += 22


    elif (
        category
        == "Senior Director - Sourcing"
    ):

        score += 20


    # ========================================================
    # DIRECTOR
    # ========================================================

    elif (
        category
        == "Director - Product Development & Sourcing"
    ):

        score += 20


    elif (
        category
        == "Director - Product Development"
    ):

        score += 19


    elif (
        category
        == "Director - Sourcing"
    ):

        score += 17


    # ========================================================
    # HEAD
    # ========================================================

    elif category == (
        "Head - Product Development"
    ):

        score += 20


    elif category == (
        "Head - Sourcing"
    ):

        score += 18


    # ========================================================
    # LOCATION
    # ========================================================

    location = (
        get_location_type(
            title,
            snippet
        )
    )


    if location == "NYC":
        score += 5


    elif location == "Remote":
        score += 5


    elif location == "NYC / Remote":
        score += 6


    # ========================================================
    # STRONG PHRASES
    # ========================================================

    if (
        "product development"
        in title_lower
    ):

        score += 4


    if (
        "sourcing"
        in title_lower
    ):

        score += 3


    # ========================================================
    # REAL COMPANY IDENTIFIED
    # ========================================================

    if company:
        score += 3


    # ========================================================
    # DIRECT ATS / CAREER PAGE
    # ========================================================

    if any(
        ats in domain
        for ats in ATS_DOMAINS
    ):

        score += 5


    return score


# ============================================================
# DUPLICATE KEY
#
# Same company + same title + same location
# is considered the same job.
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

        job.get(
            "location_type",
            ""
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

            title = (
                clean_text(
                    row.get(
                        "title",
                        ""
                    )
                )
            )


            snippet = (
                clean_text(
                    row.get(
                        "snippet",
                        ""
                    )
                )
            )


            url = (
                clean_text(
                    row.get(
                        "url",
                        ""
                    )
                )
            )


            if not title or not url:
                continue


            # Delete anything from Indeed,
            # LinkedIn, Glassdoor, etc.
            if is_blocked_job_site(
                url
            ):

                continue


            # Delete roles that no longer meet criteria
            if not is_relevant_role(
                title
            ):

                continue


            location = (
                get_location_type(
                    title,
                    snippet
                )
            )


            if not location:
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


            # No actual company?
            # Throw away the old row.
            if not company:
                continue


            row["company"] = company

            row["location_type"] = (
                location
            )

            row["role_category"] = (
                get_role_category(
                    title
                )
            )

            row["url"] = (
                canonicalize_url(
                    url
                )
            )


            key = job_key(
                row
            )


            existing[
                key
            ] = row


    return existing


# ============================================================
# PROCESS SEARCH RESULT
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
    # HARD BLOCK:
    #
    # INDEED / LINKEDIN / GLASSDOOR ETC.
    # NEVER ENTER THE DATABASE.
    # ========================================================

    if is_blocked_job_site(
        url
    ):

        print(
            "  BLOCKED job-board result:",
            domain_from_url(url)
        )

        return None


    # ========================================================
    # TITLE MUST MATCH OUR LEADERSHIP ROLES
    # ========================================================

    if not is_relevant_role(
        title
    ):

        return None


    # ========================================================
    # LOCATION MUST BE NYC OR REMOTE
    # ========================================================

    location_type = (
        get_location_type(
            title,
            snippet
        )
    )


    if not location_type:

        return None


    url = (
        canonicalize_url(
            url
        )
    )


    # ========================================================
    # MUST IDENTIFY REAL COMPANY
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
            "  SKIPPED - could not identify real employer:",
            title
        )

        return None


    role_category = (
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
            role_category,

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
# SEARCH WEB
# ============================================================

def search_web():

    queries = (
        build_search_queries()
    )


    print(
        f"Running {len(queries)} "
        "leadership searches."
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


        # ====================================================
        # HARD TIME LIMIT
        # ====================================================

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


            key = job_key(
                job
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
        f"Valid unique jobs found: "
        f"{len(found)}"
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
                    ] = (
                        old_first_seen
                    )


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


    # Highest priority first
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
# NEW JOB REPORT
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

        f"# {len(ordered)} new product leadership job(s)",

        "",

        f"Search completed: {now}",

        "",

        "**Filters:**",

        "- VP / Vice President",

        "- Director / Senior Director",

        "- Head of",

        "- Product Development",

        "- Sourcing",

        "- NYC OR Remote",

        "- Must have identifiable real employer",

        "- Indeed / LinkedIn / Glassdoor / "
        "ZipRecruiter completely excluded",

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
        "PRODUCT LEADERSHIP JOB FINDER"
    )

    print(
        "======================================"
    )

    print()

    print(
        "Searching for:"
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
        "- Senior Director roles"
    )

    print(
        "- Head of Product Development / Sourcing"
    )

    print(
        "- NYC OR Remote"
    )

    print(
        "- REAL employer required"
    )

    print(
        "- Indeed / LinkedIn / "
        "Glassdoor / ZipRecruiter blocked"
    )

    print()


    # ========================================================
    # LOAD PREVIOUS JOBS
    # ========================================================

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


    # ========================================================
    # SEARCH
    # ========================================================

    found = (
        search_web()
    )


    # ========================================================
    # FIND NEW JOBS
    # ========================================================

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


    # ========================================================
    # SAVE
    # ========================================================

    save_master_csv(
        existing,
        found
    )


    # ========================================================
    # ALERT
    # ========================================================

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
