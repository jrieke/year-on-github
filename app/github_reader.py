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
    # print(f"Quota remaining: {rem} of {quota}")
    pass


load_dotenv()
api = GhApi(token=os.getenv("GH_TOKEN"), limit_cb=limit_cb)


def read_graph_ql(username, year, verbose=False):
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
    return {"contributions": contributions}


def read_api(username, year, verbose=False):
    """
    Reads several stats for the year from Github's API and returns as dict.
    
    Note that the API has a rate limit of 5000 calls per hour.
    """
    new_repos = 0
    new_stars_per_repo = defaultdict(lambda: 0)

    print("-" * 80)
    print("Reading API for user:", username)
    start_time = time.time()

    # Iterate through all repos.
    # Use `paged` instead of `pages` here because most users will have <100 repos anyway
    # and getting the number of pages would require an additional API call.
    for repos in paged(api.repos.list_for_user, username, per_page=100):

        print("Got one page of repos:", time.time() - start_time)
        for repo in repos:
            # print()
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

            stars_start_time = time.time()
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

                # TODO: This gives stargazers in reverse order (i.e. oldest come first).
                # To iterate over this more quickly/with less API calls,
                # I could reverse the order (i.e. retrieve the last pages first)
                # and then cut off when year reaches 2019.
                # If there are a lot of stars, I could also go in and look at the last page,
                # then jump a few pages backward and so on, until we find one that starred in 2019,
                # and then backtrack to find the exact number.
                # TODO: Set a maximum number of API calls/pages here.

                # Calculate number of pages of stargazers through total number of
                # stargazers. Each page has 100 items.
                num_pages = 1 + int(repo.stargazers_count / 100)  # round up

                # METHOD 1: PAGES (with an S)
                # jrieke: 6 seconds, 15 API calls
                # chrieke: 7 seconds, 34 API calls
                # tiangolo: 280 API calls,

                # This automatically inserts per_page=100.
                for stargazer in pages(
                    api.activity.list_stargazers_for_repo,
                    num_pages,
                    username,
                    repo.name,
                    headers={"Accept": "application/vnd.github.v3.star+json"},
                ).concat():
                    # for stargazer in stargazers:
                    # print(stargazer)
                    if int(stargazer.starred_at[:4]) == year:
                        new_stars_per_repo[repo.name] += 1

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
                print("-> option 3:", time.time() - stars_start_time, end="")
            print()

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

    if verbose:
        print(f"New repos: {new_repos}")
        print(f"New stars per repo: {new_stars_per_repo}")
        print(f"New stars: {new_stars}")
        print(f"Hottest repo (+{hottest_new_stars} stars): {hottest_full_name}")

    return stats


def get_stats(username, year, verbose=False):
    """Returns a dict of several Github stats for one year."""

    # Read stats from the normal Github API and the GraphQL API
    # TODO: Could do this concurrently to save some time (but GraphQL only takes 0.4s
    # at the moment anyway).
    api_stats = read_api(username, year, verbose)
    graph_ql_stats = read_graph_ql(username, year, verbose)

    # Merge them.
    stats = {**api_stats, **graph_ql_stats}
    return stats

