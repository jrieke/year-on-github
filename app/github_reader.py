import os
from ghapi.core import GhApi
from ghapi.page import paged, pages

# from urllib.request import urlopen
# from PIL import Image
from collections import defaultdict
from dotenv import load_dotenv
import requests
import time


# def get_image(url):
#     img = Image.open(urlopen(url))
#     return img


def limit_cb(rem, quota):
    print(f"Quota remaining: {rem} of {quota}")
    pass


load_dotenv()
api = GhApi(token=os.getenv("GH_TOKEN"), limit_cb=limit_cb)


def get_contributions(username, year, verbose=False):
    """
    Reads total contributions from Github's GraphQL API and returns as dict.
    
    Contributions = Commits + issues + PRs (public and private). This is the same value
    that's shown on the user's profile page on the commit calendar.
    
    Endpoint: https://docs.github.com/en/free-pro-team@latest/graphql/reference/objects#contributioncalendar
    Some examples at: https://stackoverflow.com/questions/18262288/finding-total-contributions-of-a-user-from-github-api
    GraphQL API Explorer: https://docs.github.com/en/free-pro-team@latest/graphql/overview/explorer
    """
    print("-" * 80)
    print("Reading GraphQL API for user:", username)
    start_time = time.time()
    # Set up request params.
    url = "https://api.github.com/graphql"
    headers = {"Authorization": f"bearer {os.getenv('GH_TOKEN')}"}
    json = {
        "query": f"""query {{ 
    user(login: "{username}") {{
        contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{year}-12-31T23:59:59Z") {{
        contributionCalendar {{
            totalContributions
        }}
        }}
    }}
    }}"""
    }

    # Make POST request to GraphQL API. Takes 0.3-0.6 s.
    response = requests.post(url, headers=headers, json=json)
    # TODO: Filter bad response.
    contributions = response.json()["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]["totalContributions"]

    if verbose:
        print(f"Contributions: {contributions}")

    print("Read contributions:", time.time() - start_time)
    return contributions


def get_stats(username, year, verbose=False):
    """
    Reads several stats for the year from Github's API and returns as dict.
    
    Note that the API has a rate limit of 5000 calls per hour.
    """
    new_repos = 0
    new_stars_per_repo = defaultdict(lambda: 0)

    def calculate_summary_stats():
        # Calculate summary statistics. Take e-5 s.
        # stats_start_time = time.time()
        new_stars = sum(new_stars_per_repo.values())
        if new_stars > 0:
            hottest = max(new_stars_per_repo.items(), key=lambda item: item[1])
            hottest_name, hottest_new_stars = hottest
            hottest_full_name = username + "/" + hottest_name
        else:
            # TODO: Select repo with most stars overall instead, or just the first one.
            hottest_name, hottest_full_name, hottest_new_stars = None, None, None
        # print("Calculated summary stats:", time.time() - stats_start_time)

        stats = {
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

    # Make one quick loop through all repos and crawl some basic stats.
    # Repos that need closer inspection (i.e. where we need to look at all stargazers
    # in detail) are added to `repos_to_inspect`.
    # Use `paged` instead of `pages` here because most users will have <100 repos anyway
    # and getting the number of pages would require an additional API call.
    print("Quick inspection:")
    for repos in paged(api.repos.list_for_user, username, per_page=100):

        print("Got one page of repos:", time.time() - start_time)
        for repo in repos:
            print(repo.name[:30].ljust(30), end="")
            # repo_start_time = time.time()
            # Check if repo is new. Takes e-7 s.
            if verbose:
                print(
                    f"{repo.name[:30]:30} -> created_at: {repo.created_at}   -> Stars: {repo.stargazers_count}"
                )
            if int(repo.created_at[:4]) == year:
                new_repos += 1
            # print("Checked for newness:", time.time() - repo_start_time)

            # stars_start_time = time.time()
            # Count new stars (several options to minimize amount of API calls).
            if repo.stargazers_count == 0:
                # Option 1: 0 stars, so also 0 new stars. Takes e-6 s.
                new_stars_per_repo[repo.name] = 0
                # print("Checked for stars w/ option 1:", time.time() - stars_start_time)
            elif int(repo.created_at[:4]) == year:
                # Option 2: Created this year, therefore get all stars. Takes e-5 s.
                new_stars_per_repo[repo.name] = repo.stargazers_count
                # print("Checked for stars w/ option 2:", time.time() - stars_start_time)
            else:
                # Option 3: Look at all stargazers and find starred date.
                # Takes 0.3 s for few stars, 1.5 s for 1.5k stars, 4.7 s for 25k stars.
                repos_to_inspect.append((repo.name, repo.stargazers_count))
                print("-> needs closer inspection", end="")
            print()

    # Inspect repo with most stars first.
    # TODO: If people have very large repos, it's probably better to do a medium sized
    # one first.
    repos_to_inspect = sorted(repos_to_inspect, key=lambda item: item[1], reverse=True)

    # Yield some preliminary results.
    # TODO: Handle case when there are no repos to inspect.
    progress = 0.2
    next_repo_name = repos_to_inspect[0][0]
    if repos_to_inspect[0][1] > 1000:
        next_repo_name += " (wow, so many ⭐, this takes a bit!)"
    yield calculate_summary_stats(), progress, next_repo_name

    print()
    print("Closer inspection:")
    for i, (repo_name, stargazers_count) in enumerate(repos_to_inspect):
        # TODO: This gives stargazers in reverse order (i.e. oldest come first).
        # To iterate over this more quickly/with less API calls,
        # I could reverse the order (i.e. retrieve the last pages first)
        # and then cut off when year reaches 2019.
        # If there are a lot of stars, I could also go in and look at the last page,
        # then jump a few pages backward and so on, until we find one that starred in 2019,
        # and then backtrack to find the exact number.
        # TODO: Set a maximum number of API calls/pages here.

        print(
            f"{i+1:<3} / {len(repos_to_inspect)} {repo_name[:30]:30} ({stargazers_count} stars)",
            end="",
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
        #     new_stars_per_repo[repo_name] = find_stars_via_counting(
        #         username, repo_name, stargazers_count, year
        #     )
        # else:

        # METHOD 3: BINARY SEARCH
        # jrieke: 6 seconds, 16 API calls
        # chrieke: 10 seconds, 19 API calls
        # tiangolo: 55 seconds, 94 API calls
        print(" -> Using binary search")
        new_stars_per_repo[repo_name] = find_stars_via_binary_search(
            username, repo_name, stargazers_count, year
        )

        print("Took", time.time() - stars_start_time)
        print()

        progress = 0.2 + 0.8 * ((i + 1) / len(repos_to_inspect))
        try:
            next_repo_name = repos_to_inspect[i + 1][0]
            if repos_to_inspect[i + 1][1] > 1000:
                next_repo_name += " (wow, so many ⭐, this takes a bit!)"
        except IndexError:  # last repo doesn't have next one
            next_repo_name = ""
        yield calculate_summary_stats(), progress, next_repo_name

    if verbose:
        print(f"New repos: {new_repos}")
        print(f"New stars per repo: {new_stars_per_repo}")
        print(f"New stars: {new_stars}")
        print(f"Hottest repo (+{hottest_new_stars} stars): {hottest_full_name}")


# def get_stats(username, year, verbose=False):
#     """Returns a dict of several Github stats for one year."""

#     # Read stats from the normal Github API and the GraphQL API
#     # TODO: Could do this concurrently to save some time (but GraphQL only takes 0.4s
#     # at the moment anyway).
#     api_stats = read_api(username, year, verbose)
#     graph_ql_stats = read_graph_ql(username, year, verbose)

#     # Merge them.
#     stats = {**api_stats, **graph_ql_stats}
#     return stats


def find_stars_via_counting(username, repo_name, stargazers_count, year):

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


def find_stars_via_binary_search(username, repo_name, stargazers_count, year):

    # Calculate number of pages. Each page has 100 items.
    num_pages = 1 + int(stargazers_count / 100)  # round up

    # Use binary search to find the page with the break from 2019 to 2020.
    if num_pages == 1:
        print("Only one page found!")
        page = 1
        stargazers = api.activity.list_stargazers_for_repo(
            username,
            repo_name,
            headers={"Accept": "application/vnd.github.v3.star+json"},
            per_page=100,
            page=page,
        )
    else:
        from_page = 1
        to_page = num_pages
        while from_page <= to_page:
            page = (from_page + to_page) // 2
            print(f"Searching from page {from_page} to {to_page}, looking at {page}")
            stargazers = api.activity.list_stargazers_for_repo(
                username,
                repo_name,
                headers={"Accept": "application/vnd.github.v3.star+json"},
                per_page=100,
                page=page,
            )
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

    print("Year break is on page:", page)

    # Calculate stars on all pages that are newer than `page`.
    new_stars = (num_pages - page) * 100

    # Add the stars on page.
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
