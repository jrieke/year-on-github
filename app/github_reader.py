import os
from ghapi.core import GhApi
from ghapi.page import paged, pages

# from urllib.request import urlopen
# from PIL import Image
from collections import defaultdict
from dotenv import load_dotenv
import requests
import time
from datetime import datetime
# from joblib import Parallel, delayed
import utils


# def get_image(url):
#     img = Image.open(urlopen(url))
#     return img


# Set up the Github API client.
def limit_cb(rem, quota):
    print(f"Quota remaining: {rem} of {quota}")
    pass


load_dotenv()
api = GhApi(token=os.getenv("GH_TOKEN"), limit_cb=limit_cb)


def rate_limit_info():
    limits = api.rate_limit.get()
    d = {
        "core_remaining": limits.resources.core.remaining,
        "core_reset": utils.format_timedelta(
            datetime.fromtimestamp(limits.resources.core.reset) - datetime.now()
        ),
        "graphql_remaining": limits.resources.graphql.remaining,
        "graphql_reset": utils.format_timedelta(
            datetime.fromtimestamp(limits.resources.graphql.reset) - datetime.now()
        ),
    }
    return d


def _get_contributions(username, year, verbose=False):
    """
    Returns number of total contributions from Github's GraphQL API.
    
    Contributions = Commits + issues + PRs (public and private). This is the same value
    that's shown on the user's profile page on the commit calendar.
    
    Endpoint: https://docs.github.com/en/free-pro-team@latest/graphql/reference/objects#contributioncalendar
    Some examples at: https://stackoverflow.com/questions/18262288/finding-total-contributions-of-a-user-from-github-api
    GraphQL API Explorer: https://docs.github.com/en/free-pro-team@latest/graphql/overview/explorer
    """
    print("-" * 80)
    print("Reading GraphQL API for user:", username)
    start_time = time.time()

    # Set up query params.
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"bearer {os.getenv('GH_TOKEN')}"}
    query = f"""query {{ 
        user(login: "{username}") {{
            contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{year}-12-31T23:59:59Z") {{
                contributionCalendar {{
                    totalContributions
                }}
            }}
        }}
    }}"""

    # Make POST request to GraphQL API. Takes 0.3-0.6 s.
    response = requests.post(url, headers=headers, json={"query": query})
    # TODO: Filter bad response.
    contributions = response.json()["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]["totalContributions"]

    if verbose:
        print(f"Contributions: {contributions}")

    print("Read contributions:", time.time() - start_time)
    return contributions


def stream_stats(username, year, verbose=False):
    """
    Generator that reads user stats from Github and yields them while reading.
    
    Note that this function calls Github's REST API (v3) as well as its GraphQL API 
    (v4). The REST API has a rate limit of 5000 calls per hour, the GraphQL has a 
    similar rate limit (which is not straightforward to calculate though).
    """

    # Fetch number of contributions through GraphQL API.
    contributions = _get_contributions(username, year, verbose=verbose)

    new_repos = 0
    new_stars_per_repo = defaultdict(lambda: 0)

    def summary_stats():
        """Calculate summary stats out of the values retrieved so far."""
        # Takes e-5 s.
        new_stars = sum(new_stars_per_repo.values())
        if new_stars > 0:
            hottest = max(new_stars_per_repo.items(), key=lambda item: item[1])
            hottest_name, hottest_new_stars = hottest
            hottest_full_name = username + "/" + hottest_name
        else:
            # TODO: Select repo with most stars overall instead, or just the first one.
            hottest_name, hottest_full_name, hottest_new_stars = None, None, None

        stats = {
            "contributions": contributions,
            "new_repos": new_repos,
            "new_stars": new_stars,
            "hottest_name": hottest_name,
            "hottest_full_name": hottest_full_name,
            "hottest_new_stars": hottest_new_stars,
        }
        return stats

    print("-" * 80)
    print("Reading API for user:", username)
    start_time = time.time()
    repos_to_inspect = []

    # Make one quick loop through all repos and crawl basic stats where possible.
    # Repos that need closer inspection (i.e. where we need to look at all stargazers
    # in detail) are added to `repos_to_inspect`.
    # Use `paged` instead of `pages` here because most users will have <100 repos anyway
    # and getting the number of pages would require an additional API call.
    print("Quick inspection:")
    for repos in paged(api.repos.list_for_user, username, per_page=100):
        print("Got one page of repos:", time.time() - start_time)
        for repo in repos:
            print(
                f"{repo.name[:30]:30}: created: {repo.created_at}, stars: {repo.stargazers_count}",
                end="",
            )

            # Check if repo is new. Takes e-7 s.
            if int(repo.created_at[:4]) == year:
                new_repos += 1

            # Count new stars (several options to minimize time & amount of API calls).
            if repo.stargazers_count == 0:
                # Option 1: 0 stars, so also 0 new stars. Takes e-6 s.
                new_stars_per_repo[repo.name] = 0
            elif int(repo.created_at[:4]) == year:
                # Option 2: Created this year, therefore take all stars. Takes e-5 s.
                new_stars_per_repo[repo.name] = repo.stargazers_count
            else:
                # Option 3: Save for later inspection (see below; looks at all
                # stargazers in detail).
                repos_to_inspect.append((repo.name, repo.stargazers_count))
                print("-> closer inspection", end="")
            print()

    # Sort repos_to_inspect so we look at the ones with most stars first.
    # TODO: If people have very large repos, it might be better to do a medium sized
    # one first, so they see some progress.
    repos_to_inspect = sorted(repos_to_inspect, key=lambda item: item[1], reverse=True)

    def progress_msg(next_repo_idx):
        """Generate progress message for the next repo in closer inspection."""
        try:
            msg = f"Parsing repo: {username}/{repos_to_inspect[next_repo_idx][0]}"
            if repos_to_inspect[next_repo_idx][1] > 1000:
                msg += " (wow, so many ⭐, this takes a bit!)"
        except IndexError:  # last repo doesn't have next one
            msg = ""
        return msg

    # Yield intermediate results.
    yield summary_stats(), 0.2, progress_msg(0)

    print()
    print("Closer inspection:")
    for i, (repo_name, stargazers_count) in enumerate(repos_to_inspect):
        # TODO: Maybe set a maximum number of API calls/pages here. Then again,
        # even for the repo with the most stars on Github (300k), the binary search
        # shouldn't take more than 19 steps.
        print(
            f"{repo_name[:30]:30}: stars: ({stargazers_count})", end="",
        )
        stars_start_time = time.time()

        # COMBINED WITH 1000 STARS LIMIT
        # jrieke: 6 seconds, 16 API calls
        # chrieke: 8 seconds, 19 API calls
        # tiangolo: 53 seconds, 124 API calls

        # if stargazers_count < 0:
        # METHOD 1: PAGES (with an S)
        # jrieke: 6 seconds, 15 API calls
        # chrieke: 7 seconds, 34 API calls
        # tiangolo: 280 API calls, GIVES ERRORS OR STOPS
        #     print(" -> Using counting")
        #     new_stars_per_repo[repo_name] = _find_stars_via_counting(
        #         username, repo_name, stargazers_count, year
        #     )
        # else:

        # METHOD 3: BINARY SEARCH
        # jrieke: 6 seconds, 16 API calls
        # chrieke: 10 seconds, 19 API calls
        # tiangolo: 55 seconds, 94 API calls
        print(" -> binary search")
        new_stars_per_repo[repo_name] = _find_stars_via_binary_search(
            username, repo_name, stargazers_count, year
        )

        print("Took", time.time() - stars_start_time)
        print()

        # TODO: Use stargazers_count to calculate more accurate progress.
        progress = 0.2 + 0.8 * ((i + 1) / len(repos_to_inspect))
        yield summary_stats(), progress, progress_msg(i + 1)

    # TODO: Maybe do API calls in parallel like below. Seems to speed things up
    # a bit on local computer (especially for large repos) but needs to be tested on
    # server. Cons: Makes progress bar/text more difficult; harder to debug;
    # might lead to problems if too many jobs are run at the same time.
    # new_stars_list = Parallel(n_jobs=21)(
    #     delayed(_find_stars_via_binary_search)(
    #         username, repo_name, stargazers_count, year
    #     )
    #     for repo_name, stargazers_count in repos_to_inspect
    # )
    # new_stars_per_repo = dict(zip(repos_to_inspect, new_stars_list))

    if verbose:
        print(f"New repos: {new_repos}")
        print(f"New stars per repo: {new_stars_per_repo}")
        print(f"New stars: {new_stars}")
        print(f"Hottest repo (+{hottest_new_stars} stars): {hottest_full_name}")


def _find_stars_via_counting(username, repo_name, stargazers_count, year):
    """Returns the number of stars in a year by counting all the ones in that year."""

    # Calculate number of pages. Each page has 100 items.
    num_pages = 1 + int(stargazers_count / 100)  # round up

    # Retrieve all pages. This automatically inserts per_page=100.
    # TODO: This here is the bottleneck where it stops sometimes if there are many
    # stars/pages.
    # TODO: In any way, make a timeout here!!
    retrieved_pages = pages(
        api.activity.list_stargazers_for_repo,
        num_pages,
        username,
        repo_name,
        headers={"Accept": "application/vnd.github.v3.star+json"},
    )
    print("Retrieved pages", end="")
    concat_pages = retrieved_pages.concat()
    print(", concatenated, iterating: ", end="")

    # Iterate through all pages and count new stars.
    new_stars = 0
    for stargazer in concat_pages:
        # for stargazer in stargazers:
        # print(stargazer)
        print(".", end="")
        if int(stargazer.starred_at[:4]) == year:
            new_stars += 1
    print()

    return new_stars


def _find_stars_via_binary_search(username, repo_name, stargazers_count, year):
    """Returns the number of stars in a year through binary search on the Github API."""

    # Calculate number of pages. Each page has 100 items.
    num_pages = 1 + int(stargazers_count / 100)  # round up

    def get_stargazers(page):
        """Retrieve a page of stargazers from the Github API."""
        # TODO: This throws an error when parsing very big and old repos, because very
        # old records are not returned. E.g. sindresorhus/awesome has 150k stars,
        # but it stops after around 400 pages. fastcore.basics.HTTP422UnprocessableEntityError
        return api.activity.list_stargazers_for_repo(
            username,
            repo_name,
            headers={"Accept": "application/vnd.github.v3.star+json"},
            per_page=100,
            page=page,
        )

    # Use binary search to find the page that contains the break from 2019 to 2020.
    if num_pages == 1:
        print("Only one page found!")
        page = 1
        stargazers = get_stargazers(page)
    else:
        from_page = 1
        to_page = num_pages

        while from_page <= to_page:
            page = (from_page + to_page) // 2
            print(f"Searching from page {from_page} to {to_page}, looking at {page}")

            stargazers = get_stargazers(page)
            top_year = int(stargazers[0].starred_at[:4])
            bottom_year = int(stargazers[-1].starred_at[:4])
            # print(top_year, bottom_year)

            # TODO: Check if this works properly for 2021.
            if top_year < year and bottom_year >= year:  # 2019 and 2020
                print("Page:", page, "-> found it!")
                break
            elif bottom_year < year and top_year < year:  # before 2020
                from_page = page + 1
                print("Page:", page, "-> before 2020, setting from_page to:", from_page)
            elif bottom_year >= year and top_year >= year:  # equal to or after 2020
                to_page = page - 1
                print("Page:", page, "-> before 2020, setting to_page to:", to_page)
            else:
                raise RuntimeError()
            # print()

    # Calculate stars on all pages that are newer than `page`.
    new_stars = (num_pages - page) * 100

    # Add the stars on `page` by counting.
    for stargazer in stargazers:
        if int(stargazer.starred_at[:4]) == year:
            new_stars += 1

    print("Total new stars:", new_stars)
    return new_stars


# METHOD 2: PAGED (with a D)
# jrieke: 9 seconds, 29 API calls
# chrieke: 23 seconds, 48 API calls
# for stargazers in paged(
#     api.activity.list_stargazers_for_repo,
#     username,
#     repo.name,
#     per_page=100,
#     headers={"Accept": "application/vnd.github.v3.star+json"},
# ):
#     for stargazer in stargazers:
#         # print(stargazer)
#         if int(stargazer.starred_at[:4]) == year:
#             new_stars_per_repo[repo.name] += 1

