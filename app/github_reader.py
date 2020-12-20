import os
from ghapi.core import GhApi
from ghapi.page import paged
# from urllib.request import urlopen
# from PIL import Image
from collections import defaultdict
from dotenv import load_dotenv
import requests


# def get_image(url):
#     img = Image.open(urlopen(url))
#     return img


def limit_cb(rem, quota):
    print(f"Quota remaining: {rem} of {quota}")


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
    
    # Make POST request to GraphQL API.
    response = requests.post(url, headers=headers, json=json)
    # TODO: Filter bad response.
    contributions = response.json()["data"]["user"]["contributionsCollection"][
        "contributionCalendar"
    ]["totalContributions"]
    
    if verbose:
        print(f"Contributions: {contributions}")
    
    return {"contributions": contributions}


def read_api(username, year, verbose=False):
    """
    Reads several stats for the year from Github's API and returns as dict.
    
    Note that the API has a rate limit of 5000 calls per hour.
    """
    new_repos = 0
    new_stars_per_repo = defaultdict(lambda: 0)

    # Iterate through all repos.
    for repos in paged(api.repos.list_for_user, username, per_page=100):
        for repo in repos:

            # Check if repo is new.
            if verbose:
                print(
                    f"{repo.name[:30]:30} -> created_at: {repo.created_at}   -> Stars: {repo.stargazers_count}"
                )
            if int(repo.created_at[:4]) == year:
                new_repos += 1

            # Count new stars (several options to minimize amount of API calls).
            # Option 1: 0 stars, so also 0 new stars.
            if repo.stargazers_count == 0:
                new_stars_per_repo[repo.name] = 0
            # Option 2: Created this year, therefore get all stars.
            elif int(repo.created_at[:4]) == year:
                new_stars_per_repo[repo.name] = repo.stargazers_count
            # Option 3 (most API calls): Look at all stargazers and find starred date.
            else:
                # TODO: This gives stargazers in reverse order (i.e. oldest come first).
                # To iterate over this more quickly/with less API calls,
                # I could reverse the order (i.e. retrieve the last pages first)
                # and then cut off when year reaches 2019.
                # If there are a lot of stars, I could also go in and look at the last page,
                # then jump a few pages backward and so on, until we find one that starred in 2019,
                # and then backtrack to find the exact number.
                # TODO: Set a maximum number of API calls/pages here.
                for stargazers in paged(
                    api.activity.list_stargazers_for_repo,
                    username,
                    repo.name,
                    per_page=100,
                    headers={"Accept": "application/vnd.github.v3.star+json"},
                ):
                    for stargazer in stargazers:
                        # print(stargazer)
                        if int(stargazer.starred_at[:4]) == year:
                            new_stars_per_repo[repo.name] += 1

    # Calculate summary statistics.
    new_stars = sum(new_stars_per_repo.values())
    if new_stars > 0:
        hottest = max(new_stars_per_repo.items(), key=lambda item: item[1])
        hottest_name, hottest_new_stars = hottest
        hottest_full_name = username + "/" + hottest_name
    else:
        # TODO: Select repo with most stars overall instead, or just the first one.
        hottest_name, hottest_full_name, hottest_new_stars = None, None, None

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
    api_stats = read_api(username, year, verbose)
    graph_ql_stats = read_graph_ql(username, year, verbose)
    
    # Merge them.
    stats = {**api_stats, **graph_ql_stats}
    return stats

